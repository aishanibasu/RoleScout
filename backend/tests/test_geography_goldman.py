import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import db, goldman
from app.collect import collect
from app.feed_common import job
from app.geography import normalize_locations, state_name
from app.main import create_app
from app.search import matches


@pytest.mark.parametrize("identifier", ["170820_GS_CAMPUS", "183697_GS_MID_CAREER", "183697"])
def test_goldman_public_ids(identifier):
    assert (
        goldman.application_url(identifier)
        == "https://higher.gs.com/roles/" + identifier.split("_")[0]
    )


def test_goldman_uuid_and_invalid_ids():
    identifier = "0565380c-d0e8-40e8-a4dc-1b53361eafaf"
    assert goldman.application_url(identifier).endswith(identifier)
    with pytest.raises(ValueError):
        goldman.application_url("../other")


def test_states_normalize_only_in_us():
    assert state_name("NY", "USA") == "New York"
    assert state_name("New York", "United States") == "New York"
    assert state_name("CA", "Canada") == "CA"
    original = {"locations": [{"country": "US", "region": "NJ", "city": "Jersey City"}]}
    normalized = normalize_locations(original)
    assert normalized["region"] == "New Jersey"
    assert original["locations"][0]["region"] == "NJ"


def test_legacy_goldman_links_and_saved_jobs_corrected_without_freshness_changes(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    gs = job(
        "Goldman Sachs",
        "183697_GS_MID_CAREER",
        "Analyst",
        "https://higher.gs.com/roles/183697_GS_MID_CAREER",
        locs=[{"city": "New York", "region": "NY", "country": "United States"}],
    )
    other = job(
        "Point72",
        "other",
        "Analyst",
        "https://example.com/jobs/other",
        locs=[{"city": "New York", "region": "New York", "country": "United States"}],
    )
    collect(path, lambda: [gs], source_id="gs")
    collect(path, lambda: [other], source_id="point72")
    with db.connect(path) as conn:
        before = dict(conn.execute("SELECT * FROM jobs WHERE source_id='gs'").fetchone())
    with TestClient(create_app(path)) as client:
        params = [
            ("country", "United States"),
            ("region", "NY"),
            ("major", "Mathematics"),
            ("major", "Economics"),
            ("major", "Data Science"),
            ("level", "New graduate"),
            ("level", "Entry level"),
            ("graduation", "2027"),
        ]
        data = client.get("/jobs", params=params).json()
        assert {item["company"] for item in data["items"]} == {"Point72", "Goldman Sachs"}
        assert all(item["region"] == "New York" for item in data["items"])
        assert client.get("/filters").json()["region"] == ["New York"]
        client.put(f"/tracked/{before['id']}", json={"status": "Applied", "notes": "Keep notes"})
        saved = client.get("/tracked").json()[0]
        assert saved["url"] == "https://higher.gs.com/roles/183697"
        assert saved["tracking"]["notes"] == "Keep notes"
        assert saved["first_seen"] == before["first_seen"]
        assert saved["last_verified"] == before["last_seen"]
    with db.connect(path) as conn:
        after = dict(conn.execute("SELECT * FROM jobs WHERE id=?", (before["id"],)).fetchone())
    assert before == after
    assert json.loads(after["payload"])["url"].endswith("_GS_MID_CAREER")


def test_goldman_collector_uses_public_urls_and_canonical_states():
    response = {
        "data": {
            "roleSearch": {
                "totalCount": 1,
                "items": [
                    {
                        "roleId": "183697_GS_MID_CAREER",
                        "jobTitle": "Analyst",
                        "locations": [
                            {"state": "NY", "country": "United States", "city": "New York"}
                        ],
                    }
                ],
            }
        }
    }
    result = goldman.fetch_snapshot(lambda *args, **kwargs: SimpleNamespace(json=lambda: response))[
        0
    ]
    assert result["url"] == "https://higher.gs.com/roles/183697"
    assert result["region"] == "New York"
    assert result["external_id"] == "183697_GS_MID_CAREER"


def test_multilocation_state_does_not_cross_country_boundaries():
    item = job(
        "Example",
        "1",
        "Analyst",
        "https://example.com/jobs/1",
        locs=[{"country": "United States", "region": "NJ"}, {"country": "Canada", "region": "NY"}],
    )
    assert not matches(item, {"country": ["United States"], "region": ["NY"]})
