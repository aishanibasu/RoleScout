from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app import db
from app.collect import collect
from app.main import create_app
from app.point72 import normalize


def seed(path):
    job = normalize({"job": {"Job_Code__c": "TRACK-1", "Name": "Research Analyst"}})
    collect(path, lambda: [job])
    return db.active_jobs(path)[0]["id"]


def test_tracking_persists_and_retains_closed_jobs(tmp_path):
    path = tmp_path / "roles.sqlite3"
    job_id = seed(path)
    with TestClient(create_app(path)) as client:
        assert client.put(f"/tracked/{job_id}", json={"status": "Saved"}).status_code == 200
        assert (
            client.put(
                f"/tracked/{job_id}", json={"status": "Applied", "notes": "Follow up Friday"}
            ).status_code
            == 200
        )
    with db.connect(path) as conn:
        conn.execute("UPDATE jobs SET status='inactive' WHERE id=?", (job_id,))
    with TestClient(create_app(path)) as client:
        items = client.get("/tracked").json()
        assert len(items) == 1
        assert items[0]["tracking"]["status"] == "Applied"
        assert items[0]["tracking"]["notes"] == "Follow up Friday"
        assert items[0]["status"] == "inactive"
        assert client.get("/jobs").json()["total"] == 0
        assert client.delete(f"/tracked/{job_id}").status_code == 200
        assert client.get("/tracked").json() == []
        assert client.get(f"/jobs/{job_id}").status_code == 200


def test_tracking_validation_and_cross_site_writes(tmp_path):
    path = tmp_path / "roles.sqlite3"
    job_id = seed(path)
    with TestClient(create_app(path)) as client:
        assert client.put("/tracked/9999", json={"status": "Saved"}).status_code == 404
        assert client.put(f"/tracked/{job_id}", json={"status": "Anything"}).status_code == 422
        assert (
            client.put(
                f"/tracked/{job_id}", json={"status": "Saved", "notes": "x" * 5001}
            ).status_code
            == 422
        )
        assert (
            client.put(
                f"/tracked/{job_id}",
                json={"status": "Saved"},
                headers={"sec-fetch-site": "cross-site"},
            ).status_code
            == 403
        )
        assert (
            client.delete(
                f"/tracked/{job_id}", headers={"sec-fetch-site": "cross-site"}
            ).status_code
            == 403
        )


def test_new_jobs_since_visit(tmp_path):
    path = tmp_path / "roles.sqlite3"
    seed(path)
    now = datetime.now(timezone.utc)
    with TestClient(create_app(path)) as client:
        assert (
            client.get("/jobs", params={"since": (now - timedelta(days=1)).isoformat()}).json()[
                "total"
            ]
            == 1
        )
        assert (
            client.get("/jobs", params={"since": (now + timedelta(days=1)).isoformat()}).json()[
                "total"
            ]
            == 0
        )
        assert client.get("/jobs", params={"since": "2026-01-01T00:00:00"}).status_code == 422
        assert client.get("/jobs", params={"since": "invalid"}).status_code == 422
