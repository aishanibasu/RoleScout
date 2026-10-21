from types import SimpleNamespace

import pytest

from app.dedup import deduplicate
from app.employer_feeds import GTS, Millennium, dvtrading, schonfeld


def response(data):
    return SimpleNamespace(json=lambda: data)


def greenhouse_row(identifier=1):
    return {
        "id": identifier,
        "absolute_url": f"https://job-boards.greenhouse.io/schonfeld/jobs/{identifier}",
        "title": "Analyst",
        "content": "<p>2 years of experience required.</p>",
        "location": {"name": "New York"},
        "application_deadline": "2027-01-01",
    }


def test_greenhouse_complete_snapshot_with_description_and_deadline():
    jobs = schonfeld.fetch_snapshot(
        lambda _: response({"jobs": [greenhouse_row()], "meta": {"total": 1}})
    )
    assert jobs[0]["company"] == "Schonfeld"
    assert "2 years of experience required." in jobs[0]["description"]
    assert "Applications close on 2027-01-01" in jobs[0]["description"]
    assert jobs[0]["locations"][0]["region"] == "New York"


@pytest.mark.parametrize(
    "rows,total", [([], 0), ([greenhouse_row()], 2), ([greenhouse_row(), greenhouse_row()], 2)]
)
def test_greenhouse_rejects_incomplete_or_duplicate_snapshot(rows, total):
    with pytest.raises(ValueError):
        schonfeld.fetch_snapshot(lambda _: response({"jobs": rows, "meta": {"total": total}}))


def test_greenhouse_rejects_other_employer_links():
    with pytest.raises(ValueError):
        dvtrading.fetch_snapshot(
            lambda _: response({"jobs": [greenhouse_row()], "meta": {"total": 1}})
        )


def test_millennium_pages_and_detail_validation():
    calls = []

    def request(url):
        calls.append(url)
        return response(
            {
                "count": 2,
                "positions": [{"id": len(calls), "name": "Analyst", "locations": ["New York"]}],
            }
        )

    jobs = Millennium().fetch_snapshot(request)
    assert len(jobs) == 2 and "start=1" in calls[1]
    assert jobs[0]["details_pending"]
    with pytest.raises(ValueError):
        Millennium().fetch_detail(
            lambda _: response({"id": 999, "job_description": "Wrong job"}), jobs[0]
        )


def test_millennium_repeated_page_rejected():
    with pytest.raises(ValueError):
        Millennium().fetch_snapshot(
            lambda _: response({"count": 2, "positions": [{"id": 1, "name": "Analyst"}]})
        )


def test_old_aggregator_copies_never_resurrect_employer_jobs():
    for company in ["Apollo", "Schonfeld", "DV Trading", "Millennium", "GTS"]:
        old = {"id": 1, "company": company, "source": "hft", "url": "https://example.com/old/123"}
        current = dict(old, id=2, source="direct", url="https://example.com/current/456")
        assert deduplicate([old, current]) == [current]
        assert deduplicate([old]) == []


def test_gts_full_description_and_real_location():
    index = '<h2 class="iCIMS_SubHeader_Jobs">Page 1 of 1</h2><li class="iCIMS_JobCardItem"><a class="iCIMS_Anchor" title="1622 - Analyst" href="https://careers-gtsx.icims.com/jobs/1622/analyst/job?in_iframe=1">Analyst</a><dd class="iCIMS_JobHeaderData">US-NY-New York</dd></li>'
    detail = '<div class="iCIMS_Expandable_Text"><p>Qualifications</p><ul><li>2 years of experience.</li></ul></div>'
    jobs = GTS().fetch_snapshot(
        lambda url: SimpleNamespace(text=index if "search?" in url else detail)
    )
    assert jobs[0]["locations"][0]["region"] == "New York"
    assert "\n2 years of experience." in jobs[0]["description"]
    assert not jobs[0]["details_pending"]


def test_gts_missing_pagination_not_accepted_as_complete():
    with pytest.raises(ValueError):
        GTS().fetch_snapshot(lambda _: SimpleNamespace(text="<html>Temporarily unavailable</html>"))


def test_explicit_public_api_allow_wins_over_root_disallow(monkeypatch):
    import httpx

    from app.collect import with_source

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def get(self, url):
            body = (
                "User-agent: *\nDisallow: /\nAllow: /api/apply\n"
                if url.endswith("/robots.txt")
                else "{}"
            )
            return httpx.Response(200, text=body, request=httpx.Request("GET", url))

    monkeypatch.setattr("app.collect.httpx.Client", Client)
    monkeypatch.setattr("app.collect.time.sleep", lambda _: None)
    assert with_source("millennium", lambda request: request(Millennium.API).json()) == {}
    with pytest.raises(ValueError, match="robots"):
        with_source("millennium", lambda request: request("https://career.mlp.com/private"))
