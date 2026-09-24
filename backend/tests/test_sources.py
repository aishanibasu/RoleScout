import json
from types import SimpleNamespace
import pytest
from app import db, collect as collector, workday, morganstanley, oracle, goldman
from app.feed_common import job
from app.dedup import deduplicate
from app.hydrate import hydrate
from app.main import create_app
from fastapi.testclient import TestClient

def response(data):return SimpleNamespace(json=lambda:data)

def test_nullable_morgan_fields_and_full_count():
    row={'jobNumber':'1','jobTitle':'Summer Intern','url':'https://example.com/job/1','division':None,'employmentType':None,'jobDescription':'Finance internship'}
    jobs=morganstanley.fetch_snapshot(lambda _:response({'status':200,'resultSet':[row],'totalResults':1}))
    assert jobs[0]['type']=='Internship'
    assert jobs[0]['details_available']
    with pytest.raises(ValueError):morganstanley.fetch_snapshot(lambda _:response({'status':200,'resultSet':[row],'totalResults':2}))

def test_workday_index_pagination_and_metadata():
    calls=[]
    def fetch(url,body):
        calls.append(body['offset'])
        if body['offset']==0:return response({'total':2,'jobPostings':[{'externalPath':'/job/one','title':'Analyst','locationsText':'3 Locations'}]})
        return response({'total':0,'jobPostings':[{'externalPath':'/job/two','title':'Intern','locationsText':'New York'}]})
    jobs=workday.bofa.fetch_snapshot(fetch)
    assert calls==[0,1]
    assert jobs[0]['company']=='Bank of America' and jobs[0]['locations']==[]
    assert jobs[0]['details_pending'] and not jobs[0]['details_available']
    assert jobs[1]['type']=='Internship'

def test_oracle_rejects_overlapping_pages():
    with pytest.raises(ValueError,match='Oracle'):
        oracle.bny.fetch_snapshot(lambda _:response({'items':[{'TotalJobsCount':2,'requisitionList':[{'Id':'123','Title':'Analyst'}]}]}))

def test_goldman_rejects_query_errors():
    with pytest.raises(ValueError,match='rejected'):
        goldman.fetch_snapshot(lambda *a,**k:response({'errors':[{'message':'Invalid query'}]}))

def test_dedup_prefers_official_and_preserves_different_requisitions():
    base={'url':'https://example.com/job/123','source':'point72','id':1}
    jobs=[dict(base,source='hft',id=2,url=base['url']+'?utm_source=hft'),base,dict(base,id=3,url='https://example.com/job/456')]
    result=deduplicate(jobs)
    assert len(result)==2 and result[0]['id']==1 and result[0]['also_listed_on']==['hft']
    assert 'also_listed_on' not in base

def test_hydration_preserves_freshness_and_cached_description(tmp_path,monkeypatch):
    path=tmp_path/'jobs.db'
    item=job('RBC','one','Analyst','https://example.com/job/one',pending=True)
    collector.collect(path,lambda:[item],source_id='rbc')
    before=db.active_jobs(path)[0]
    monkeypatch.setattr(workday.rbc,'fetch_detail',lambda request,item:dict(item,description='A degree in Computer Science is required.'))
    monkeypatch.setattr('app.hydrate.with_source',lambda source,action:action(None))
    assert hydrate('rbc',path)==1
    after=db.active_jobs(path)[0]
    assert after['id']==before['id'] and after['last_verified']==before['last_verified'] and after['first_seen']==before['first_seen']
    assert not after['details_pending'] and after['details_available']
    collector.collect(path,lambda:[item],source_id='rbc')
    assert db.active_jobs(path)[0]['description']==after['description']

def test_hydration_failure_delays_retry(tmp_path,monkeypatch):
    path=tmp_path/'jobs.db';item=job('RBC','one','Analyst','https://example.com/job/one',pending=True)
    collector.collect(path,lambda:[item],source_id='rbc')
    def fail(*args):raise ValueError('source unavailable')
    monkeypatch.setattr(workday.rbc,'fetch_detail',fail)
    monkeypatch.setattr('app.hydrate.with_source',lambda source,action:action(None))
    assert hydrate('rbc',path)==0
    assert db.active_jobs(path)[0]['detail_retry_after']
    monkeypatch.setattr(workday.rbc,'fetch_detail',lambda *args:pytest.fail('Retried too early'))
    assert hydrate('rbc',path)==0

def test_coverage_explains_unconnected_sources(tmp_path):
    with TestClient(create_app(tmp_path/'jobs.db')) as client:
        sources={s['id']:s for s in client.get('/sources').json()}
        assert len(sources)==17
        assert 'experienced-hire' in sources['ubs']['scope']
        assert 'Campus' in sources['jefferies']['scope']
        assert sources['hudsonbay']['status']=='manual' and sources['hudsonbay']['job_count']==0
