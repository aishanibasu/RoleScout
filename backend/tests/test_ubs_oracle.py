import html,json
from types import SimpleNamespace
from urllib.parse import parse_qs,urlparse
import pytest
from app import ubs,oracle

def page(data,inputs=''):
    return '<input id="preLoadJSON" value="'+html.escape(json.dumps(data),quote=True)+'">'+inputs

def row(identifier):
    return {'Questions':[{'QuestionName':'reqid','Value':identifier},{'QuestionName':'jobtitle','Value':'Analyst'}],'Link':'https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5012&jobid='+identifier}

def test_ubs_anonymous_pagination_and_duplicate_guard():
    initial={'SmartSearchJSONValue':json.dumps({'KeywordCustomSolrFields':'jobtitle','LocationCustomSolrFields':'location'}),'searchResultsResponse':{'JobsCount':2,'Jobs':{'Job':[row('1')]}}}
    calls=[]
    def request(url,**kwargs):
        if url==ubs.URL:return SimpleNamespace(text=page(initial,'<input id="CookieValue" value="anonymous-test">'))
        calls.append(kwargs)
        return SimpleNamespace(json=lambda:{'JobsCount':2,'Jobs':{'Job':[row('2')]}})
    jobs=ubs.fetch_snapshot(request)
    assert len(jobs)==2 and all(j['details_pending'] for j in jobs)
    assert calls[0]['body']['pageNumber']==2 and calls[0]['body']['encryptedSessionValue']=='anonymous-test'
    with pytest.raises(ValueError,match='Duplicate'):
        ubs.fetch_snapshot(lambda url,**kwargs:request(url,**kwargs) if url==ubs.URL else SimpleNamespace(json=lambda:{'JobsCount':2,'Jobs':{'Job':[row('1')]}}))

def test_ubs_details_identity_and_qualifications():
    data={'JobId':1,'Jobdetails':{'JobDetailQuestions':[{'VerityZone':'jobdescription','AnswerValue':'Build software','QuestionType':'textarea','QuestionName':'Role'},{'VerityZone':'formtext59','AnswerValue':'Degree in Computer Science','QuestionType':'textarea','QuestionName':'Qualifications'}]}}
    item=ubs.normalize(row('1'))
    result=ubs.fetch_detail(lambda _:SimpleNamespace(text=page(data)),item)
    assert 'Computer Science' in result['description'] and result['details_available']
    with pytest.raises(ValueError,match='ID mismatch'):ubs.fetch_detail(lambda _:SimpleNamespace(text=page(data)),dict(item,external_id='2'))

def test_oracle_overlapping_windows_verify_terminal_and_count():
    offsets=[]
    def request(url):
        offset=int(url.split('offset=')[1].split(',')[0]);offsets.append(offset)
        rows=[{'Id':str(i),'Title':'Analyst'} for i in range(offset,min(offset+199,400))]
        return SimpleNamespace(json=lambda:{'items':[{'TotalJobsCount':402,'requisitionList':rows}]})
    jobs=oracle.bny.fetch_snapshot(request)
    assert len(jobs)==400 and offsets==[0,179,358,557]
    assert jobs[0]['source_reported_total']==402

def test_oracle_rejects_large_count_gap():
    def request(url):
        offset=int(url.split('offset=')[1].split(',')[0])
        rows=[{'Id':str(i),'Title':'Analyst'} for i in range(offset,min(offset+199,400))]
        return SimpleNamespace(json=lambda:{'items':[{'TotalJobsCount':410,'requisitionList':rows}]})
    with pytest.raises(ValueError,match='Incomplete'):oracle.bny.fetch_snapshot(request)

def test_bam_public_feed_excludes_staff_metadata_and_keeps_locations():
    from app import bam
    source={'Id':'public-job-id','Name':'Software Intern','Requisition_Number__c':'REQ1','Job_Req_Title_in_URL__c':'Software-Intern','Experience_Level__c':'Internships','Department__c':'Engineering','Primary_Recruiter__r':{'Name':'Not part of the listing'},'Job_Requisition_Positions__r':[{'Location__r':{'External_Name__c':'London'}},{'Location__r':{'External_Name__c':'New York'}}]}
    result=bam.normalize(source)
    assert result['external_id']=='REQ1' and result['level']=='Student'
    assert len(result['locations'])==2 and result['details_pending']
    assert 'Primary_Recruiter__r' not in result and 'Not part of the listing' not in json.dumps(result)
    assert result['url'].endswith('details?jobReq=Software-Intern_REQ1')

def test_bam_public_action_checks_response_and_refreshes_bootstrap():
    from app import bam
    from urllib.parse import quote
    config={'mode':'PROD','fwuid':'public-version','app':'siteforce:communityApp','loaded':{}}
    requests=[]
    def request(url,**kwargs):
        if url==bam.URL:return SimpleNamespace(text='<script src="/s/sfsites/l/'+quote(json.dumps(config),safe='')+'/app.js"></script>')
        requests.append(kwargs['form'])
        return SimpleNamespace(json=lambda:{'actions':[{'state':'SUCCESS','returnValue':{'returnValue':[]}}]})
    assert bam.public_action(request,'searchJobRequisitions',{'site':'BAM Website'})==[]
    assert requests[0]['aura.token']=='null'
    assert json.loads(requests[0]['aura.context'])['fwuid']=='public-version'


def test_oracle_offsets_count_unavailable_positions():
    offsets=[]
    def request(url):
        offset=int(url.split('offset=')[1].split(',')[0]);offsets.append(offset)
        # The final window contains two unavailable slots; using len(rows)
        # as the next offset would repeat the last public listing.
        rows=[{'Id':str(i),'Title':'Analyst'} for i in range(offset,min(offset+199,402)) if i not in (395,396)]
        return SimpleNamespace(json=lambda:{'items':[{'TotalJobsCount':402,'requisitionList':rows}]})
    jobs=oracle.bny.fetch_snapshot(request)
    assert len(jobs)==400 and offsets[-1]==557
    assert jobs[-1]['external_id']=='401'
