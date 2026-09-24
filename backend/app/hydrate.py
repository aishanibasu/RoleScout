"""Fill missing bank job descriptions in small, independently retryable batches."""
import argparse
import json
from datetime import datetime,timedelta,timezone
from . import db
from .collect import ADAPTERS, with_source, RetryLater
from .eligibility import enrich
from .locks import process_lock, AlreadyRunning


def hydrate(source_id, path=None, limit=20):
    adapter=ADAPTERS[source_id]
    if not hasattr(adapter,'fetch_detail'):return 0
    db.initialize(path)
    at=datetime.now(timezone.utc)
    with process_lock(path,source_id):
        with db.connect(path) as conn:
            schedule=conn.execute('SELECT not_before FROM refresh_schedule WHERE source_id=?',(source_id,)).fetchone()
            if schedule['not_before'] and datetime.fromisoformat(schedule['not_before'])>at:return 0
            rows=conn.execute("SELECT id,payload FROM jobs WHERE source_id=? AND status='active' ORDER BY id",(source_id,)).fetchall()
        pending=[]
        for row in rows:
            item=json.loads(row['payload'])
            if item.get('detail_retry_after') and datetime.fromisoformat(item['detail_retry_after'])>at:continue
            checked=item.get('details_checked_at')
            if item.get('details_pending') or (checked and datetime.fromisoformat(checked)<at-timedelta(days=7)):
                pending.append((row['id'],item))
            if len(pending)>=limit:break
        if not pending:return 0
        def batch(request):
            completed=0
            for identifier,item in pending:
                try:
                    full=enrich(adapter.fetch_detail(request,item))
                    full.update(details_checked_at=db.now(),details_pending=False,details_available=True)
                    full.pop('detail_error',None);full.pop('detail_retry_after',None)
                    with db.connect(path) as conn:
                        conn.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(full),identifier))
                    completed+=1
                except Exception as exc:
                    item.update(detail_error=str(exc)[:400],detail_retry_after=(at+timedelta(days=1)).isoformat())
                    with db.connect(path) as conn:
                        conn.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps(item),identifier))
                        if isinstance(exc,RetryLater):conn.execute('UPDATE refresh_schedule SET not_before=? WHERE source_id=?',(exc.until,source_id))
                    # Stop this batch on a source error; never hammer a failing source.
                    break
            return completed
        try:
            return with_source(source_id,batch)
        except Exception as exc:
            until=exc.until if isinstance(exc,RetryLater) else (at+timedelta(hours=1)).isoformat()
            with db.connect(path) as conn:
                conn.execute('UPDATE refresh_schedule SET not_before=? WHERE source_id=?',(until,source_id))
            raise

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',choices=sorted(ADAPTERS));parser.add_argument('--limit',type=int,default=20)
    args=parser.parse_args()
    if not 1<=args.limit<=100:parser.error('limit must be between 1 and 100')
    print(f'Added descriptions for {hydrate(args.source,limit=args.limit)} jobs.')
