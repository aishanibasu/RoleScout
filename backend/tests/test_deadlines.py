from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.collect import collect
from app.deadlines import extract_deadline, with_deadline
from app.feed_common import job
from app.main import create_app
from app.search import matches


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Application deadline: October 31, 2027", "2027-10-31"),
        ("Apply by 31st Oct. 2027", "2027-10-31"),
        ("Applications close on 2027-10-31.", "2027-10-31"),
        ("Applications must be submitted by October 31 2027", "2027-10-31"),
        ("Graduation date: October 31, 2027", None),
        ("Apply by 10/11/2027", None),
        ("Apply by October 31", None),
        ("Applications accepted on a rolling basis", None),
        ("Closing date: February 30, 2027", None),
        ("Apply by October 1, 2027. Apply by November 1, 2027.", None),
    ],
)
def test_explicit_dates_only(text, expected):
    assert extract_deadline(text)[0] == expected


@pytest.mark.parametrize(
    "day,status", [(9, "passed"), (10, "soon"), (17, "soon"), (18, "upcoming")]
)
def test_deadline_boundaries(day, status):
    item = with_deadline({"description": f"Apply by 2027-10-{day:02d}"}, date(2027, 10, 10))
    assert item["deadline_status"] == status
    item.update(title="Analyst", company="Example")
    assert matches(item, {"deadline": ["Has a deadline"]})
    assert matches(item, {"deadline": ["Closing within 7 days"]}) == (status == "soon")
    assert matches(item, {"deadline": ["Deadline passed"]}) == (status == "passed")
    assert not matches(item, {"deadline": ["No date found"]})


def test_api_existing_records_filter_and_details(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    dated = job("Point72", "dated", "Analyst", "https://example.com/1")
    dated["description"] = "Application deadline: October 31, 2099"
    unknown = dict(dated, external_id="unknown", title="Other", description="Rolling applications")
    collect(path, lambda: [dated, unknown])
    with TestClient(create_app(path)) as client:
        assert client.get("/jobs").json()["total"] == 2
        result = client.get("/jobs", params={"deadline": "Has a deadline"}).json()
        assert result["total"] == 1
        item = result["items"][0]
        assert item["application_deadline"] == "2099-10-31"
        assert client.get(f"/jobs/{item['id']}").json()["deadline_evidence"] == dated["description"]
        assert client.get("/jobs?deadline=No+date+found").json()["total"] == 1
        assert client.get("/jobs?deadline=Deadline+passed").json()["total"] == 0
        assert client.get("/jobs?deadline=Has+a+deadline&q=missing").json()["total"] == 0
