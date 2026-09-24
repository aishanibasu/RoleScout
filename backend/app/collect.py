"""Run with python -m app.collect {point72,ares}. No public write endpoint."""
import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

import httpx
from . import db, point72, ares, workday, sig, hft, morganstanley, oracle, twosigma, jefferies, goldman, ubs, bam
from .locks import process_lock
from .scheduling import due_at
from .eligibility import enrich

AGENT = 'RoleSearcher/0.1'

class RetryLater(ValueError):
    def __init__(self, value):
        at = datetime.now(timezone.utc)
        try:
            until = at + timedelta(seconds=max(0, int(value)))
        except (ValueError, OverflowError):
            try:
                until = parsedate_to_datetime(value)
                if until.tzinfo is None:
                    until = until.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, OverflowError):
                until = at + timedelta(days=1)
        self.until = max(at, until).isoformat()
        super().__init__('Source requested retry no earlier than ' + self.until)

def respect_retry_after(response):
    if response.status_code in (429, 503) and response.headers.get('Retry-After'):
        raise RetryLater(response.headers['Retry-After'])

ADAPTERS = {'point72': point72, 'ares': ares, 'apollo': workday.apollo, 'sig': sig, 'hft':hft, 'morganstanley':morganstanley, 'bofa':workday.bofa, 'rbc':workday.rbc, 'bny':oracle.bny, 'twosigma':twosigma, 'jefferies':jefferies, 'gs':goldman, 'ubs':ubs, 'bam':bam}

def with_source(source_id, action):
    adapter = ADAPTERS[source_id]
    origin = '{0.scheme}://{0.netloc}'.format(urlparse(adapter.URL))
    with httpx.Client(timeout=45, follow_redirects=True, headers={'User-Agent': AGENT, **getattr(adapter, 'HEADERS', {})}) as client:
        robots = client.get(origin + '/robots.txt')
        respect_retry_after(robots)
        rules = RobotFileParser()
        delay = 1
        if robots.status_code != 404:
            robots.raise_for_status()
            rules.parse(robots.text.splitlines())
            delay = rules.crawl_delay(AGENT) or 1
            if delay > 60:
                raise ValueError('Source requests a longer delay; schedule collection separately')
        last_request = time.monotonic()
        def request(url, body=None, headers=None, form=None):
            nonlocal last_request
            if urlparse(url).netloc != urlparse(origin).netloc:
                raise ValueError('Collector attempted to leave its configured source')
            if robots.status_code != 404 and not rules.can_fetch(AGENT, url):
                raise ValueError('Source robots directives disallow collection')
            for attempt in range(3):
                time.sleep(max(0, delay - (time.monotonic() - last_request)))
                last_request = time.monotonic()
                response = client.post(url, data=form, headers=headers) if form is not None else client.get(url) if body is None else client.post(url, json=body, headers=headers)
                respect_retry_after(response)
                if response.status_code not in (429, 500, 502, 503, 504) or attempt == 2:
                    response.raise_for_status()
                    return response
                if response.headers.get('Retry-After'):
                    raise RetryLater(response.headers['Retry-After'])
                time.sleep(2 ** attempt)
            raise ValueError('No source response')
        return action(request)

def fetch_snapshot(source_id='point72'):
    adapter=ADAPTERS[source_id]
    return with_source(source_id, lambda request: adapter.fetch_snapshot(request) if hasattr(adapter,'fetch_snapshot') else point72.parse_page(request(point72.URL).text))

def collect(path=None, fetch=None, scheduled=False, source_id='point72'):
    if source_id not in ADAPTERS:
        raise ValueError('Unknown collector: ' + source_id)
    fetch = fetch if fetch is not None else lambda: fetch_snapshot(source_id)
    db.initialize(path)
    with process_lock(path, source_id):
        with db.connect(path) as conn:
            source = conn.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
            schedule = conn.execute("SELECT * FROM refresh_schedule WHERE source_id=?", (source_id,)).fetchone()
            at = datetime.now(timezone.utc)
            if schedule['not_before'] and at < datetime.fromisoformat(schedule['not_before']):
                return None
            if scheduled and due_at(source, schedule, at) > at:
                return None
            # Owning the lock proves any prior running entry was abandoned.
            conn.execute("UPDATE runs SET status='interrupted',finished_at=?,error='Previous collector exited before completion' WHERE source_id=? AND status='running'", (db.now(), source_id))
        return _collect_locked(path, fetch, source_id)

def _collect_locked(path, fetch, source_id):
    started = db.now()
    with db.connect(path) as conn:
        run_id = conn.execute("INSERT INTO runs(source_id,started_at,status) VALUES (?,?,'running')", (source_id, started)).lastrowid
        conn.execute("UPDATE sources SET last_attempt=? WHERE id=?", (started, source_id))
    try:
        jobs = [enrich(job) for job in fetch()]
        if not jobs or len({j['external_id'] for j in jobs}) != len(jobs):
            raise ValueError('Empty or duplicate snapshot; existing data retained')
        with db.connect(path) as conn:
            previous = conn.execute("SELECT count(*) FROM jobs WHERE source_id=? AND status='active'", (source_id,)).fetchone()[0]
            if previous > 20 and len(jobs) < previous * 0.5:
                raise ValueError('Unexpected drop in listing count; refusing possible partial refresh')
            stamp = db.now()
            conn.execute("UPDATE jobs SET misses=misses+1 WHERE source_id=? AND status='active'", (source_id,))
            for job in jobs:
                if job.get('details_pending'):
                    prior=conn.execute('SELECT payload FROM jobs WHERE source_id=? AND external_id=?',(source_id,job['external_id'])).fetchone()
                    if prior:
                        old=json.loads(prior['payload'])
                        if old.get('details_available') and old['title']==job['title']:
                            job={**job, **old}
                conn.execute('''INSERT INTO jobs(source_id,external_id,payload,first_seen,last_seen)
                    VALUES (?,?,?,?,?) ON CONFLICT(source_id,external_id) DO UPDATE SET
                    payload=excluded.payload,last_seen=excluded.last_seen,status='active',misses=0''',
                    (source_id, job['external_id'], json.dumps(job), stamp, stamp))
            conn.execute("UPDATE jobs SET status='inactive' WHERE source_id=? AND misses>=2", (source_id,))
            conn.execute("UPDATE sources SET status='active',last_success=?,error=NULL WHERE id=?", (stamp, source_id))
            conn.execute("UPDATE refresh_schedule SET not_before=NULL WHERE source_id=?", (source_id,))
            conn.execute("UPDATE runs SET finished_at=?,status='success',count=? WHERE id=?", (stamp, len(jobs), run_id))
        return len(jobs)
    except Exception as exc:
        with db.connect(path) as conn:
            if isinstance(exc, RetryLater):
                conn.execute("UPDATE refresh_schedule SET not_before=? WHERE source_id=?", (exc.until, source_id))
            conn.execute("UPDATE sources SET status='error',error=? WHERE id=?", (str(exc)[:1000], source_id))
            conn.execute("UPDATE runs SET finished_at=?,status='failure',error=? WHERE id=?", (db.now(), str(exc)[:1000], run_id))
        raise

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', choices=sorted(ADAPTERS))
    args = parser.parse_args()
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    try:
        count = collect(source_id=args.source)
        print(f'Collected {count} {args.source} jobs.' if count is not None else 'Collection deferred until the source retry window ends.')
    except Exception as exc:
        parser.exit(1, f'Collection failed; existing listings retained: {exc}\n')
