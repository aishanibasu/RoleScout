import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from app import db
from app.collect import collect
from app.main import create_app
from app.point72 import normalize, parse_page
from app.search import matches

@pytest.fixture
def listing():
    return normalize({'job': {'Job_Code__c': 'TEST-1', 'Name': '2028 Software Engineering Intern',
        'Area__c': 'Technology & Engineering', 'Job_Description_External__c': '<p>Build software.</p>',
        'Apply_Now_URL__c': 'https://example.com/apply/1'}, 'formattedLocation': 'New York | London'})

@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'test.sqlite3'
    db.initialize(path)
    return path

def test_parser_decodes_without_executing_javascript():
    record = {'job': {'Job_Code__c': 'T', 'Name': 'Engineer',
        'Job_Description_External__c': '<p>A &quot;quoted&quot; role at Point72&#39;s team.</p>'}}
    js_literal = json.dumps(json.dumps([record]), ensure_ascii=True)[1:-1].replace("'", "\\'")
    parsed = parse_page("CSSearchModule.init('" + js_literal + "', 'other');")
    assert '"quoted"' in parsed[0]['description']
    assert "Point72's" in parsed[0]['description']

@pytest.mark.parametrize('page', ['', "CSSearchModule.init('[]')", "CSSearchModule.init('[{}]')"])
def test_invalid_or_empty_payload_rejected(page):
    with pytest.raises((ValueError, KeyError)):
        parse_page(page)

def test_title_year_does_not_imply_graduation(listing):
    assert listing['graduation'] == []
    assert matches(listing, {'graduation': ['2028']})
    assert not matches(listing, {'graduation': ['2028']}, confirmed=True)

def test_graduation_exact_evidence():
    job = normalize({'job': {'Job_Code__c': 'T', 'Name': '2028 Internship',
        'Job_Description_External__c': '<p>Applicants must be in the graduating class of 2029.</p>'}})
    assert matches(job, {'graduation': ['2029']}, confirmed=True)
    assert not matches(job, {'graduation': ['2028']})

def test_multilocation_filters_apply_to_same_location(listing):
    assert matches(listing, {'city': ['London'], 'country': ['United Kingdom']})
    assert not matches(listing, {'city': ['London'], 'country': ['United States']})
    assert matches(listing, {'city': ['Chicago', 'New York City'], 'interest': ['Technology']})

def test_unknown_education_and_inferred_level_not_confirmed(listing):
    assert matches(listing, {'major': ['Computer Science']})
    assert not matches(listing, {'major': ['Computer Science']}, confirmed=True)
    assert not matches(listing, {'level': ['Student']}, confirmed=True)

def test_upsert_and_two_complete_refresh_closure(database, listing):
    other = copy.deepcopy(listing)
    other['external_id'] = 'TEST-2'
    collect(database, lambda: [listing, other])
    first = db.active_jobs(database)[0]
    collect(database, lambda: [listing, other])
    assert len(db.active_jobs(database)) == 2
    assert db.active_jobs(database)[0]['first_seen'] == first['first_seen']
    collect(database, lambda: [other])
    assert len(db.active_jobs(database)) == 2
    collect(database, lambda: [other])
    assert len(db.active_jobs(database)) == 1
    collect(database, lambda: [listing, other])
    assert len(db.active_jobs(database)) == 2

def test_failure_preserves_data_and_records_error(database, listing):
    collect(database, lambda: [listing])
    def fail():
        raise RuntimeError('simulated network failure')
    with pytest.raises(RuntimeError):
        collect(database, fail)
    assert len(db.active_jobs(database)) == 1
    with db.connect(database) as conn:
        assert conn.execute('SELECT misses FROM jobs').fetchone()[0] == 0
        assert conn.execute('SELECT status FROM runs ORDER BY id DESC').fetchone()[0] == 'failure'

def test_partial_snapshot_guard(database, listing):
    jobs = [dict(listing, external_id=str(i)) for i in range(30)]
    collect(database, lambda: jobs)
    with pytest.raises(ValueError):
        collect(database, lambda: jobs[:2])
    assert len(db.active_jobs(database)) == 30

def test_api_pagination_filters_detail_sources(database, listing):
    collect(database, lambda: [listing, dict(listing, external_id='TEST-2', title='Operations')])
    with TestClient(create_app(database)) as client:
        assert client.get('/health').json() == {'status': 'ok'}
        result = client.get('/jobs?page_size=1&interest=Technology').json()
        assert result['total'] == 2 and len(result['items']) == 1
        assert client.get('/jobs?q=operations').json()['total'] == 1
        assert client.get('/jobs?page=0').status_code == 422
        assert client.get('/jobs?page_size=101').status_code == 422
        assert client.get('/jobs?certainty=invalid').status_code == 422
        assert client.get('/jobs/99999').status_code == 404
        assert client.get('/jobs/' + str(result['items'][0]['id'])).status_code == 200
        assert 'United Kingdom' in client.get('/filters').json()['country']
        assert len(client.get('/sources').json()) == 17
        assert client.get('/runs').json()[0]['status'] == 'success'
