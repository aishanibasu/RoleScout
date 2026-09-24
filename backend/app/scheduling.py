from datetime import datetime, timedelta, timezone
from . import db

def due_at(source, schedule, at=None):
    at = at or datetime.now(timezone.utc)
    due = (datetime.fromisoformat(source['last_attempt']) +
           timedelta(seconds=schedule['interval_seconds'])) if source['last_attempt'] else at
    if schedule['not_before']:
        due = max(due, datetime.fromisoformat(schedule['not_before']))
    return due

def status(path=None, at=None):
    at = at or datetime.now(timezone.utc)
    with db.connect(path) as conn:
        row = conn.execute('SELECT * FROM scheduler_state WHERE id=1').fetchone()
        schedules = [dict(r) for r in conn.execute('''SELECT r.*,s.name,s.status,s.error,s.last_attempt,s.last_success
            FROM refresh_schedule r JOIN sources s ON s.id=r.source_id''')]
    running = bool(row and not row['stopped_at'] and row['heartbeat_at'] and
                   at - datetime.fromisoformat(row['heartbeat_at']) < timedelta(seconds=90))
    return {
        'running': running,
        'heartbeat_at': row['heartbeat_at'] if row else None,
        'sources': [{'source': s['source_id'], 'name': s['name'], 'status': s['status'],
                     'error': s['error'], 'interval_hours': s['interval_seconds'] / 3600,
                     'last_success': s['last_success'], 'next_due': due_at(s, s, at).isoformat()}
                    for s in schedules],
    }
