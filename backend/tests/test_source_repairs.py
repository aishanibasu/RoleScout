from types import SimpleNamespace

import pytest

from app import jefferies, workday


def feed(url="https://jefferies.tal.net/opp/123-Graduate/en-GB"):
    return f'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>{url}</id><title>Graduate Program</title><link rel="alternate" href="{url}?instant=apply"/></entry></feed>'


def test_jefferies_feed_survives_protected_description_pages():
    calls = []

    def request(url):
        calls.append(url)
        assert url == jefferies.URL
        return SimpleNamespace(text=feed())

    jobs = jefferies.fetch_snapshot(request)
    assert len(calls) == 1
    assert jobs[0]["external_id"] == "123"
    assert jobs[0]["details_pending"]
    assert jobs[0]["description"] == ""
    with pytest.raises(ValueError, match="browser verification"):
        jefferies.fetch_detail(
            lambda _: SimpleNamespace(text="<title>Quick Check Needed</title>"), jobs[0]
        )


def test_jefferies_rejects_offsite_application_urls():
    with pytest.raises(ValueError, match="URL"):
        jefferies.fetch_snapshot(
            lambda _: SimpleNamespace(text=feed("https://other.example/opp/123"))
        )


def test_jefferies_detail_extracts_available_requirements():
    item = jefferies.fetch_snapshot(lambda _: SimpleNamespace(text=feed()))[0]
    html = (
        '<div role="definition" class="hform_value_view">'
        + "Build financial models. " * 15
        + '</div><div role="definition" class="hform_value_view item78763">New York</div>'
    )
    result = jefferies.fetch_detail(lambda _: SimpleNamespace(text=html), item)
    assert result["details_available"]
    assert result["country"] == "United States"
    assert "Build financial models." in result["description"]


def response(rows, total):
    return SimpleNamespace(json=lambda: {"total": total, "jobPostings": rows})


def test_workday_counts_unavailable_positions_without_fabricating_jobs():
    calls = []

    def request(url, body):
        calls.append(body["offset"])
        if body["offset"] == 0:
            return response([{"bulletFields": ["R-0000149942"]}], 2)
        return response([{"externalPath": "/job/real", "title": "Analyst"}], 0)

    jobs = workday.rbc.fetch_snapshot(request)
    assert calls == [0, 1]
    assert len(jobs) == 1
    assert jobs[0]["source_unavailable_count"] == 1
    assert jobs[0]["external_id"] == "/job/real"


@pytest.mark.parametrize(
    "row", [{"title": "Analyst"}, {"bulletFields": []}, {"bulletFields": ["unknown"]}]
)
def test_workday_rejects_unrecognized_missing_paths(row):
    with pytest.raises(ValueError, match="no application path"):
        workday.rbc.fetch_snapshot(lambda *a, **kw: response([row], 1))


def test_workday_retries_entire_snapshot_after_duplicate_page():
    calls = []
    row = {"externalPath": "/job/one", "title": "Analyst"}

    def request(url, body):
        calls.append(body["offset"])
        if len(calls) == 3:
            return response([row, dict(row, externalPath="/job/two")], 2)
        return response([row], 2)

    jobs = workday.bofa.fetch_snapshot(request)
    assert calls == [0, 1, 0]
    assert len(jobs) == 2


def test_workday_persistently_duplicate_pages_are_not_accepted():
    calls = []

    def request(url, body):
        calls.append(body["offset"])
        return response([{"externalPath": "/job/one", "title": "Analyst"}], 2)

    with pytest.raises(ValueError, match="Duplicate"):
        workday.bofa.fetch_snapshot(request)
    assert calls == [0, 1, 0, 1]
