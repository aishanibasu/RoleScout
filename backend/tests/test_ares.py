import copy

import pytest
from fastapi.testclient import TestClient
from app import ares, db
from app.collect import collect
from app.main import create_app
from app.scheduler import run
from threading import Event

@pytest.fixture
def detail():
    return {'jobPostingInfo': {
        'id': 'test-posting-1', 'title': '2028 Software Engineering Intern',
        'jobDescription': '<p>Applicants must be in the graduating class of 2029.</p>',
        'location': 'Bellevue, WA', 'country': {'descriptor': 'United States of America'},
        'additionalLocations': ['London, UK'], 'timeType': 'Full time',
        'posted': True, 'canApply': True, 'jobReqId': 'R123', 'startDate': '2026-09-17',
    }}

class Response:
    def __init__(self, data):
        self.data = data
    def json(self):
        return self.data

def test_normalization_preserves_multiple_countries_and_internship(detail):
    j = ares.normalize(detail, '/job/Bellevue/Intern_R123')
    assert j['company'] == 'Ares Management'
    assert j['type'] == 'Internship'  # Full-time internship is still an internship.
    assert j['graduation'] == [2029]  # Not the internship year in the title.
    assert j['locations'][0]['region'] == 'Washington'
    assert j['locations'][0]['country'] == 'United States'
    assert j['locations'][1]['country'] == 'United Kingdom'
    assert j['posted_at'] == '2026-09-17'
    assert j['evidence']['level']['status'] == 'inferred'
    assert j['url'].startswith(ares.URL + '/job/')

def test_unknown_secondary_location_does_not_inherit_primary_country(detail):
    detail['jobPostingInfo']['additionalLocations'] = ['Unmapped office']
    job = ares.normalize(detail, '/job/test')
    assert job['locations'][1]['country'] == ''

@pytest.mark.parametrize('field,value', [('canApply', False), ('posted', False), ('id', None), ('jobDescription', '')])
def test_missing_or_closed_detail_aborts_snapshot(detail, field, value):
    detail['jobPostingInfo'][field] = value
    with pytest.raises(ValueError):
        ares.normalize(detail, '/job/test')

def test_all_pages_and_details_collected_with_zero_later_total(detail):
    calls = []
    def request(url, body=None):
        calls.append((url, body))
        if body is not None:
            offset = body['offset']
            return Response({'total': 21 if offset == 0 else 0, 'jobPostings': [
                {'externalPath': '/job/example/' + str(i)} for i in range(offset, min(offset + 20, 21))]})
        payload = copy.deepcopy(detail)
        payload['jobPostingInfo']['id'] = url.rsplit('/', 1)[-1]
        return Response(payload)
    jobs = ares.fetch_snapshot(request)
    assert len(jobs) == 21
    assert len(calls) == 23
    assert [body['offset'] for _, body in calls if body] == [0, 20]
    assert len({j['external_id'] for j in jobs}) == 21

@pytest.mark.parametrize('mode', ['missing_page', 'duplicate', 'changed_total', 'bad_path'])
def test_incomplete_search_rejected(mode):
    def request(url, body=None):
        offset = body['offset']
        if not offset:
            return Response({'total': 2, 'jobPostings': [{'externalPath': '/job/one'}]})
        return Response({'total': 3 if mode == 'changed_total' else 0, 'jobPostings':
            [] if mode == 'missing_page' else [{'externalPath': '/job/one' if mode == 'duplicate' else
                'https://other.example/job/two' if mode == 'bad_path' else '/job/two'}]})
    with pytest.raises(ValueError):
        ares.fetch_snapshot(request)

def test_multisource_storage_isolation_and_company_filter(tmp_path, detail):
    path = tmp_path / 'db.sqlite3'
    ares_job = ares.normalize(detail, '/job/test')
    point72_job = dict(ares_job, company='Point72')
    collect(path, lambda: [point72_job])
    collect(path, lambda: [ares_job], source_id='ares')
    assert len(db.active_jobs(path)) == 2  # Same external ID, different employers.
    with pytest.raises(ValueError):
        collect(path, lambda: [], source_id='ares')
    with db.connect(path) as conn:
        point72 = conn.execute("SELECT * FROM sources WHERE id='point72'").fetchone()
        assert point72['status'] == 'active' and point72['error'] is None
        assert conn.execute("SELECT misses FROM jobs WHERE source_id='point72'").fetchone()[0] == 0
    with TestClient(create_app(path)) as client:
        assert client.get('/jobs?company=Ares%20Management').json()['total'] == 1
        assert client.get('/jobs?company=Point72&company=Ares%20Management').json()['total'] == 2
        assert client.get('/jobs?company=Unknown').json()['total'] == 0
        assert client.get('/filters').json()['company'] == ['Ares Management', 'Point72']
        assert {s['source'] for s in client.get('/scheduler').json()['sources']} == set(__import__('app.collect', fromlist=['ADAPTERS']).ADAPTERS)

def test_scheduler_continues_other_source_after_failure(tmp_path):
    stop, calls = Event(), []
    def collector(**kwargs):
        calls.append(kwargs['source_id'])
        if kwargs['source_id'] == 'point72':
            raise RuntimeError('Point72 temporarily unavailable')
        stop.set()
        return 1
    run(tmp_path / 'jobs.sqlite3', stop, collector)
    assert calls == ['point72', 'ares']
