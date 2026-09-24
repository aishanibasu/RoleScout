"""Daily local refresh worker. Run separately from the API: python -m app.scheduler."""
import argparse
import logging
import signal
from threading import Event, Thread

from . import db
from .collect import collect, ADAPTERS
from .hydrate import hydrate
from .locks import AlreadyRunning, process_lock

log = logging.getLogger('role-searcher.scheduler')

def heartbeat(path):
    with db.connect(path) as conn:
        conn.execute('UPDATE scheduler_state SET heartbeat_at=? WHERE id=1', (db.now(),))

def tick(path=None, collector=collect, source_id='point72'):
    try:
        count = collector(path=path, scheduled=True, source_id=source_id)
        if count is not None:
            log.info('Refreshed %s: %s jobs', source_id, count)
        return count
    except AlreadyRunning:
        log.info('%s collector already running; checking again on the next tick', source_id)
    except Exception:
        log.exception('%s refresh failed; existing listings retained. Next attempt follows the persisted schedule.', source_id)
    return None

def run(path=None, stop=None, collector=collect, hydrator=hydrate):
    stop = stop if stop is not None else Event()
    db.initialize(path)
    with process_lock(path, 'scheduler'):
        stamp = db.now()
        with db.connect(path) as conn:
            conn.execute('''INSERT INTO scheduler_state(id,started_at,heartbeat_at,stopped_at)
                VALUES (1,?,?,NULL) ON CONFLICT(id) DO UPDATE SET
                started_at=excluded.started_at,heartbeat_at=excluded.heartbeat_at,stopped_at=NULL''', (stamp, stamp))
        heartbeat_stop = Event()
        def pulse():
            while not heartbeat_stop.wait(20):
                try:
                    heartbeat(path)
                except Exception:
                    log.exception('Could not record scheduler heartbeat')
        thread = Thread(target=pulse, daemon=True)
        thread.start()
        log.info('Daily refresh worker running. Checks every 30 seconds; only due sources are fetched.')
        try:
            while not stop.is_set():
                for source_id in ADAPTERS:
                    if stop.is_set():
                        break
                    tick(path, collector, source_id)
                    if not stop.is_set():
                        try:
                            count=hydrator(source_id,path=path)
                            if count:log.info('%s: added %s full descriptions',source_id,count)
                        except AlreadyRunning:
                            pass
                        except Exception:
                            log.exception('%s description update failed',source_id)
                stop.wait(30)
        finally:
            heartbeat_stop.set()
            thread.join()
            with db.connect(path) as conn:
                conn.execute('UPDATE scheduler_state SET stopped_at=? WHERE id=1', (db.now(),))
            log.info('Refresh worker stopped')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--once', action='store_true', help='Check due work once and exit; do not advertise a running scheduler')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    logging.getLogger('httpx').setLevel(logging.WARNING)
    stop = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stop.set())
    try:
        if args.once:
            db.initialize()
            for source_id in ADAPTERS:
                tick(source_id=source_id)
        else:
            run(stop=stop)
    except AlreadyRunning as exc:
        parser.exit(1, str(exc) + '\n')
