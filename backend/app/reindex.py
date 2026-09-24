"""Re-extract eligibility from stored descriptions without fetching or changing freshness."""
import json
from . import db
from .eligibility import enrich


def reindex(path=None):
    db.initialize(path)
    with db.connect(path) as conn:
        # Acquire the write transaction before reading, so a concurrent refresh cannot be overwritten.
        conn.execute('BEGIN IMMEDIATE')
        rows = conn.execute('SELECT id,payload FROM jobs').fetchall()
        for row in rows:
            job = enrich(json.loads(row['payload']))
            conn.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(job), row['id']))
    return len(rows)

if __name__ == '__main__':
    print(f'Reprocessed {reindex()} stored jobs; source verification dates unchanged.')
