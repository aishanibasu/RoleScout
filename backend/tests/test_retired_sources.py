import json

from fastapi.testclient import TestClient

from app import db
from app.collect import ADAPTERS
from app.feed_common import job
from app.main import create_app


def test_retired_sources_removed_from_existing_installations(tmp_path):
    path = tmp_path / "roles.db"
    db.initialize(path)
    retired = {"bofa", "jpmorgan", "citadel", "hudsonbay"}
    with db.connect(path) as conn:
        for source in retired:
            conn.execute(
                "INSERT INTO sources(id,name,url,status) VALUES (?,?,?,?)",
                (source, source, "https://example.com", "active"),
            )
            conn.execute("INSERT INTO refresh_schedule(source_id) VALUES (?)", (source,))
            item = job(source, "1", "Analyst", "https://example.com/" + source)
            identifier = conn.execute(
                "INSERT INTO jobs(source_id,external_id,payload,first_seen,last_seen) VALUES (?,?,?,?,?)",
                (source, "1", json.dumps(item), db.now(), db.now()),
            ).lastrowid
            conn.execute(
                "INSERT INTO tracked_jobs(job_id,stage,notes,updated_at) VALUES (?,?,?,?)",
                (identifier, "Applied", "Keep my notes", db.now()),
            )
    with TestClient(create_app(path)) as client:
        assert not retired.intersection(s["id"] for s in client.get("/sources").json())
        assert len(client.get("/sources").json()) == 17
        assert not retired.intersection(
            s["source"] for s in client.get("/scheduler").json()["sources"]
        )
        assert client.get("/jobs").json()["total"] == 0
        saved = client.get("/tracked").json()
        assert len(saved) == 4
        assert all(j["tracking"]["notes"] == "Keep my notes" for j in saved)
    db.initialize(path)  # Migration is safe to repeat.
    assert not retired.intersection(ADAPTERS)
