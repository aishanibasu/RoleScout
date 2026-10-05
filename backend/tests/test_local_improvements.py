from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import launcher
from app.collect import collect
from app.eligibility import enrich
from app.feed_common import job
from app.locks import process_lock
from app.main import create_app
from app.search import eligibility_status, matches


def role(description, identifier="1"):
    return enrich(
        job("Example", identifier, "Analyst", f"https://example.com/{identifier}", description)
    )


@pytest.mark.parametrize(
    "text, minimum, maximum",
    [
        ("5+ years Corporate/Commercial credit experience", 5, None),
        ("Seven or more years of experience.", 7, None),
        ("Two to five years of relevant banking experience.", 2, 5),
        (
            "7+ year of technology development experience. (Previous experience with SN is a plus.)",
            7,
            None,
        ),
    ],
)
def test_real_world_experience_phrasing(text, minimum, maximum):
    item = role(text)
    requirement = item["experience_requirements"][0]
    assert (requirement["minimum"], requirement["maximum"]) == (minimum, maximum)
    assert requirement["preference"] == "stated"
    assert matches(item, {"level": ["Entry level", "New graduate"]}) == (minimum <= 2)


@pytest.mark.parametrize(
    "text", ["Five years of experience (preferred).", "5 years of experience preferred."]
)
def test_actual_preferred_experience_stays_optional(text):
    assert role(text)["experience_requirements"][0]["preference"] == "preferred"


def test_uncertainty_is_not_presented_as_confirmed():
    item = role("Bachelor's degree in Mathematics required.")
    assert eligibility_status(item, {"major": ["Mathematics"]}) == "confirmed"
    assert (
        eligibility_status(item, {"major": ["Mathematics"], "graduation": ["2027"]})
        == "needs_review"
    )
    assert eligibility_status(item, {}) == "not_assessed"


def test_expired_jobs_hidden_by_default_but_saved_data_retained(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    collect(
        path,
        lambda: [
            role("Apply by 2000-01-01", "past"),
            role("Apply by 2099-01-01", "future"),
            role("Rolling applications", "unknown"),
        ],
    )
    with TestClient(create_app(path)) as client:
        normal = client.get("/jobs").json()
        assert normal["total"] == 2
        assert all(j["deadline_status"] != "passed" for j in normal["items"])
        assert client.get("/jobs?deadline=Has+a+deadline").json()["total"] == 1
        past = client.get("/jobs?deadline=Deadline+passed").json()
        assert past["total"] == 1
        item = past["items"][0]
        client.put(f"/tracked/{item['id']}", json={"status": "Applied", "notes": "Keep this"})
        assert client.get("/tracked").json()[0]["tracking"]["notes"] == "Keep this"
        assert client.get("/jobs?q=Analyst&page_size=1").json()["total"] == 2
        assert client.get("/jobs?page=3&page_size=1").json()["items"] == []


def test_launcher_refuses_unrelated_port(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "listening", lambda port: True)
    monkeypatch.setattr(launcher, "ready", lambda *args: False)
    monkeypatch.setattr(
        launcher, "spawn", lambda *args: pytest.fail("Must not start over occupied port")
    )
    with pytest.raises(RuntimeError, match="occupied"):
        launcher.ensure_service(8000, "url", "marker", [], tmp_path, tmp_path / "log")


def test_launcher_reuses_healthy_service(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "listening", lambda port: True)
    monkeypatch.setattr(launcher, "ready", lambda *args: True)
    monkeypatch.setattr(launcher, "spawn", lambda *args: pytest.fail("Duplicate process"))
    launcher.ensure_service(8000, "url", "marker", [], tmp_path, tmp_path / "log")


def test_launcher_reports_failed_process(monkeypatch, tmp_path):
    monkeypatch.setattr(launcher, "listening", lambda port: False)
    monkeypatch.setattr(launcher, "ready", lambda *args: False)
    monkeypatch.setattr(launcher, "spawn", lambda *args: SimpleNamespace(poll=lambda: 1))
    with pytest.raises(RuntimeError, match="Startup failed"):
        launcher.ensure_service(8000, "url", "marker", [], tmp_path, tmp_path / "log")


def test_launcher_uses_scheduler_lock_even_if_heartbeat_is_old(monkeypatch, tmp_path):
    monkeypatch.setenv("ROLE_SEARCHER_DB", str(tmp_path / "jobs.sqlite3"))
    monkeypatch.setattr(launcher, "spawn", lambda *args: pytest.fail("Duplicate scheduler"))
    with process_lock(None, "scheduler"):
        launcher.ensure_scheduler(tmp_path / "log")
