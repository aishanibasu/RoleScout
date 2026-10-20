from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app import db
from app.collect import collect
from app.deadlines import past_recruiting_program
from app.eligibility import enrich
from app.feed_common import job
from app.main import create_app
from app.search import matches


def role(title="Analyst", description="", identifier="1"):
    return enrich(
        job("Example", identifier, title, "https://example.com/" + identifier, description)
    )


def test_missing_and_stale_results_hidden_but_saved_retained(tmp_path):
    path = tmp_path / "roles.db"
    collect(path, lambda: [role(), role(identifier="2")])
    with TestClient(create_app(path)) as client:
        identifier = client.get("/jobs").json()["items"][0]["id"]
        client.put(f"/tracked/{identifier}", json={"status": "Saved", "notes": "Keep"})
        collect(path, lambda: [role()])
        assert client.get("/jobs").json()["total"] == 1
        with db.connect(path) as conn:
            conn.execute(
                "UPDATE jobs SET last_seen=?",
                ((datetime.now(timezone.utc) - timedelta(hours=49)).isoformat(),),
            )
        assert client.get("/jobs").json()["total"] == 0
        assert len(client.get("/tracked").json()) == 1
        collect(path, lambda: [role()])
        assert client.get("/jobs").json()["total"] == 1


@pytest.mark.parametrize(
    "title,expired",
    [
        ("2025 University Graduate", True),
        ("2025 Summer Analyst", True),
        ("2026 Internship", False),
        ("2027 Graduate Program", False),
        ("2025/2027 Graduate Program", False),
        ("ISO 2025 Compliance Analyst", False),
    ],
)
def test_past_intakes(title, expired):
    assert past_recruiting_program({"title": title}, date(2026, 10, 20)) == expired


@pytest.mark.parametrize(
    "description",
    [
        "Qualifications: 8 years of experience in finance.",
        "Build models. Requires 8 years of experience in finance.",
        "A degree in mathematics and at least 8 years of experience.",
        "Requirements: 8 years of experience. No relocation required.",
    ],
)
def test_flattened_requirements_override_junior_title(description):
    item = role("Junior Analyst", description)
    assert item["level"] == "Senior"
    assert not matches(item, {"level": ["Entry level", "New graduate"]})
    assert matches(item, {"level": ["Senior"]})


def test_preferred_years_and_company_history_do_not_override_entry():
    item = role(
        "Junior Analyst",
        "Our firm has 30 years of experience. Preferred qualifications: 8 years of experience.",
    )
    assert item["level"] == "Entry level"
    assert matches(item, {"level": ["Entry level"]})


def test_old_intake_is_hidden_even_if_feed_reverifies_it(tmp_path):
    path = tmp_path / "roles.db"
    year = datetime.now(timezone.utc).year
    collect(
        path,
        lambda: [
            role(f"{year - 1} University Graduate"),
            role(f"{year + 1} University Graduate", identifier="2"),
        ],
    )
    with TestClient(create_app(path)) as client:
        data = client.get("/jobs").json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == f"{year + 1} University Graduate"
