from datetime import datetime, timedelta, timezone
from threading import Event

import pytest
from fastapi.testclient import TestClient
from app import db
from app.collect import collect, RetryLater
from app.locks import AlreadyRunning, process_lock
from app.main import create_app
from app.point72 import normalize
from app.scheduler import run, tick
from app.scheduling import due_at, status

@pytest.fixture
def path(tmp_path):
    value = tmp_path / 'jobs.sqlite3'
    db.initialize(value)
    return value

@pytest.fixture
def listing():
    return normalize({'job': {'Name': 'Intern', 'Job_Code__c': 'TEST-1'}})

def test_daily_due_boundary():
    at = datetime(2026, 9, 18, tzinfo=timezone.utc)
    source = {'last_attempt': (at - timedelta(days=1)).isoformat()}
    schedule = {'interval_seconds': 86400, 'not_before': None}
    assert due_at(source, schedule, at) == at
    source['last_attempt'] = (at - timedelta(hours=23)).isoformat()
    assert due_at(source, schedule, at) > at
    assert due_at({'last_attempt': None}, schedule, at) == at

def test_recent_collection_is_not_repeated(path, listing):
    collect(path, lambda: [listing])
    def fail_if_called():
        pytest.fail('Recent source fetched again')
    assert collect(path, fail_if_called, scheduled=True) is None
    with db.connect(path) as conn:
        assert conn.execute('SELECT count(*) FROM runs').fetchone()[0] == 1

def test_failed_collection_waits_until_next_day(path):
    def fail():
        raise RuntimeError('temporary source failure')
    with pytest.raises(RuntimeError):
        collect(path, fail)
    assert collect(path, lambda: pytest.fail('Failure retried too soon'), scheduled=True) is None

def test_locks_prevent_overlap_and_release_on_error(path, listing):
    with process_lock(path, 'point72'):
        with pytest.raises(AlreadyRunning):
            collect(path, lambda: pytest.fail('Overlapping network request'))
    assert collect(path, lambda: [listing]) == 1
    with pytest.raises(RuntimeError):
        with process_lock(path, 'point72'):
            raise RuntimeError('crash')
    with process_lock(path, 'point72'):
        pass

def test_retry_after_persists_and_blocks_manual_and_scheduled(path):
    def fail():
        raise RetryLater('172800')
    with pytest.raises(RetryLater):
        collect(path, fail)
    assert collect(path, lambda: pytest.fail('Retry deadline ignored')) is None
    due = datetime.fromisoformat(status(path)['sources'][0]['next_due'])
    assert due > datetime.now(timezone.utc) + timedelta(hours=47)

def test_retry_after_http_date_and_invalid_value():
    assert RetryLater('Fri, 01 Jan 2100 00:00:00 GMT').until.startswith('2100-01-01')
    assert datetime.fromisoformat(RetryLater('invalid').until) > datetime.now(timezone.utc)

def test_abandoned_run_recovered_after_lock_acquired(path, listing):
    with db.connect(path) as conn:
        conn.execute("INSERT INTO runs(source_id,started_at,status) VALUES ('point72',?,'running')", (db.now(),))
    collect(path, lambda: [listing])
    with db.connect(path) as conn:
        assert conn.execute('SELECT status FROM runs ORDER BY id').fetchone()[0] == 'interrupted'

def test_heartbeat_expiration_and_shutdown(path):
    assert not status(path)['running']
    at = datetime.now(timezone.utc)
    with db.connect(path) as conn:
        conn.execute('INSERT INTO scheduler_state(id,started_at,heartbeat_at) VALUES (1,?,?)', (at.isoformat(), at.isoformat()))
    assert status(path, at)['running']
    assert not status(path, at + timedelta(seconds=91))['running']
    with db.connect(path) as conn:
        conn.execute('UPDATE scheduler_state SET stopped_at=? WHERE id=1', (at.isoformat(),))
    assert not status(path, at)['running']

def test_worker_runs_due_work_and_marks_shutdown(path):
    stop = Event()
    def collector(**kwargs):
        assert kwargs == {'path': path, 'scheduled': True, 'source_id': 'point72'}
        assert status(path)['running']
        stop.set()
        return 1
    run(path, stop, collector)
    assert not status(path)['running']

def test_second_scheduler_rejected(path):
    with process_lock(path, 'scheduler'):
        with pytest.raises(AlreadyRunning):
            run(path, Event())

def test_tick_survives_collection_failure(path):
    def collector(**kwargs):
        raise RuntimeError('network failure')
    assert tick(path, collector) is None

def test_scheduler_endpoint(path):
    with TestClient(create_app(path)) as client:
        payload = client.get('/scheduler').json()
        assert payload['running'] is False
        assert payload['sources'][0]['interval_hours'] == 24
