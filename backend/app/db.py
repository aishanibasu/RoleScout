import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)

DEFAULT_DB = Path(__file__).resolve().parents[1] / "data" / "roles.sqlite3"
SOURCES = [
    ("hudsonbay", "Hudson Bay Capital", "https://www.hudsonbaycapital.com/careers", "manual"),
    ("point72", "Point72", "https://careers.point72.com/", "ready"),
    ("hft", "HFT Jobs", "https://www.hft-jobs.com/jobs", "planned"),
    ("apollo", "Apollo", "https://www.apollo.com/careers", "planned"),
    ("ares", "Ares Management", "https://www.ares.com/us/careers", "ready"),
    ("bam", "Balyasny Asset Management", "https://www.bamfunds.com/careers", "planned"),
    ("citadel", "Citadel", "https://www.citadel.com/careers/", "planned"),
    ("twosigma", "Two Sigma", "https://www.twosigma.com/careers/", "planned"),
    ("sig", "Susquehanna", "https://sig.com/careers/", "planned"),
    ("jpmorgan", "JPMorgan Chase", "https://www.jpmorganchase.com/careers", "planned"),
    (
        "morganstanley",
        "Morgan Stanley",
        "https://www.morganstanley.com/people-opportunities",
        "planned",
    ),
    ("bofa", "Bank of America", "https://careers.bankofamerica.com/en-us", "planned"),
    (
        "bny",
        "BNY",
        "https://www.bny.com/corporate/global/en/about-us/careers/work-with-us.html",
        "planned",
    ),
    ("ubs", "UBS", "https://www.ubs.com/global/en/careers.html", "planned"),
    ("rbc", "RBC", "https://jobs.rbc.com/", "planned"),
    ("gs", "Goldman Sachs", "https://www.goldmansachs.com/careers", "planned"),
    ("jefferies", "Jefferies", "https://www.jefferies.com/careers/", "planned"),
]


def now():
    return datetime.now(timezone.utc).isoformat()


def database_path(path=None):
    return Path(path or os.environ.get("ROLE_SEARCHER_DB", DEFAULT_DB)).expanduser().resolve()


@contextmanager
def connect(path=None):
    path = database_path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def initialize(path=None):
    with connect(path) as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, url TEXT NOT NULL,
            status TEXT NOT NULL, last_attempt TEXT, last_success TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
            external_id TEXT NOT NULL, payload TEXT NOT NULL,
            first_seen TEXT NOT NULL, last_seen TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active', misses INTEGER NOT NULL DEFAULT 0,
            UNIQUE(source_id, external_id));
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
            started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0, error TEXT);
        CREATE TABLE IF NOT EXISTS tracked_jobs (
            job_id INTEGER PRIMARY KEY REFERENCES jobs(id),
            stage TEXT NOT NULL, notes TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS jobs_source_status ON jobs(source_id, status);
        CREATE TABLE IF NOT EXISTS refresh_schedule (
            source_id TEXT PRIMARY KEY REFERENCES sources(id),
            interval_seconds INTEGER NOT NULL DEFAULT 86400,
            not_before TEXT);
        CREATE TABLE IF NOT EXISTS scheduler_state (
            id INTEGER PRIMARY KEY CHECK(id=1),
            started_at TEXT, heartbeat_at TEXT, stopped_at TEXT);
        """)
        db.executemany(
            """INSERT INTO sources(id,name,url,status) VALUES (?,?,?,?)
            ON CONFLICT(id) DO UPDATE SET name=excluded.name,url=excluded.url""",
            SOURCES,
        )
        db.execute("UPDATE sources SET status='researching' WHERE id='bam' AND status='planned'")
        db.execute(
            "UPDATE sources SET status='blocked',error='Public collector received an access challenge; integration pending' WHERE id='citadel' AND status='planned'"
        )
        from .coverage import LIMITATIONS

        for identifier, reason in LIMITATIONS.items():
            db.execute(
                "UPDATE sources SET status=?,error=? WHERE id=? AND last_success IS NULL",
                ("researching" if identifier == "bam" else "blocked", reason, identifier),
            )
        db.executemany(
            "INSERT OR IGNORE INTO refresh_schedule(source_id) VALUES (?)",
            [
                (name,)
                for name in (
                    "point72",
                    "ares",
                    "apollo",
                    "sig",
                    "hft",
                    "morganstanley",
                    "bofa",
                    "rbc",
                    "bny",
                    "twosigma",
                    "jefferies",
                    "gs",
                    "ubs",
                    "bam",
                )
            ],
        )


def serialize(row):
    item = json.loads(row["payload"])
    item.update(
        id=row["id"],
        source=row["source_id"],
        first_seen=row["first_seen"],
        last_verified=row["last_seen"],
        status=row["status"],
    )
    from .geography import normalize_locations
    from .goldman import application_url

    if row["source_id"] == "gs":
        item["url"] = item["source_url"] = application_url(row["external_id"])
    return normalize_locations(item)


def active_jobs(path=None):
    with connect(path) as db:
        return [serialize(r) for r in db.execute("SELECT * FROM jobs WHERE status='active'")]
