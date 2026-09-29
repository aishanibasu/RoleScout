import json

import pytest
from fastapi.testclient import TestClient

from app import db
from app.collect import collect
from app.eligibility import enrich
from app.feed_common import job
from app.main import create_app
from app.search import matches

EARLY = {"level": ["New graduate", "Entry level"]}


def role(title="Analyst", description="", level="Not specified"):
    return enrich(
        job("Example", "1", title, "https://example.com/jobs/1", description, level=level)
    )


@pytest.mark.parametrize(
    "title",
    [
        "Managing Director, Portfolio Compliance",
        "Principal or Managing Director, Originator",
        "Senior Director, POM Product Management Manager",
        "VP, Events & Sponsorships",
        "Product Control Vice President",
        "Head of Engineering",
        "Senior Strategist",
        "Sr. Software Engineer",
        "Staff Engineer",
        "Engineering Manager",
    ],
)
def test_senior_titles_excluded_without_descriptions(title):
    item = role(title)
    assert not matches(item, EARLY)
    assert not matches(item, {"level": ["Entry level", "Not specified"]})
    assert matches(item, {})
    assert item["evidence"]["level"]["status"] == "inferred"


@pytest.mark.parametrize(
    "description",
    [
        "15+ years of experience in finance.",
        "A minimum of 15 years of relevant work experience.",
        "You have 15 years of experience.",
        "10+ years as a BDO and/or an underwriter, preferably with an asset-based lending institution",
        "15+ years of experience in a systems SCM environment; experience in financial services is a plus.",
        "8+ years of progressive experience in executive events, ideally within financial services.",
        "5+ years of experience in engineering.\n2+ years of experience in Python.",
    ],
)
def test_required_experience_overrides_incorrect_entry_label(description):
    item = role(description=description, level="Entry level")
    assert not matches(item, EARLY)
    assert not matches(item, EARLY, confirmed=True)
    assert matches(item, {})


@pytest.mark.parametrize(
    "description",
    [
        "Preferred qualifications:\n10+ years of experience in finance.",
        "5+ years of experience in finance preferred.",
        "Our firm has over 30 years of investing experience.",
        "0-2 years of experience.",
        "No experience required.",
        "",
    ],
)
def test_preferences_and_unknowns_not_hard_exclusions(description):
    assert matches(role(description=description), EARLY)


@pytest.mark.parametrize(
    "title",
    ["Executive Assistant to Managing Director", "Product Manager Intern", "Research Analyst"],
)
def test_support_and_intern_titles_not_executive_roles(title):
    assert matches(role(title), EARLY)


def test_explicit_label_preserved_and_broad_selection_allowed():
    item = role("Managing Director", level="Manager / leadership")
    assert matches(item, {"level": ["Manager / leadership"]}, confirmed=True)
    assert matches(item, {"level": ["Entry level", "Manager / leadership"]})


def test_legacy_records_corrected_in_api_without_mutating_dates(tmp_path):
    path = tmp_path / "jobs.sqlite3"
    collect(path, lambda: [role("Managing Director", "15+ years of experience.")])
    with db.connect(path) as conn:
        row = dict(conn.execute("SELECT * FROM jobs").fetchone())
        payload = json.loads(row["payload"])
        payload.update(extraction_version=1, level="Not specified", experience_requirements=[])
        conn.execute("UPDATE jobs SET payload=?", (json.dumps(payload),))
    with TestClient(create_app(path)) as client:
        assert (
            client.get(
                "/jobs", params=[("level", "New graduate"), ("level", "Entry level")]
            ).json()["total"]
            == 0
        )
        item = client.get("/jobs").json()["items"][0]
        assert item["level"] == "Manager / leadership"
        assert item["experience_requirements"][0]["minimum"] == 15
        assert item["last_verified"] == row["last_seen"]
        assert item["first_seen"] == row["first_seen"]
