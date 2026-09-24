"""UBS public experienced-hire board, using its normal anonymous search session."""
import json
from urllib.parse import urlparse,parse_qs
from .html_tree import Tree
from .feed_common import job
from .normalization import plain
from .ares import location
URL='https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5012&PageType=searchResults&SearchType=linkquery&LinkID=15231'
SCOPE='Public UBS experienced-hire board (site 5012); other campus boards are separate. Full descriptions populate in background.'

def preload(text):
    root=Tree(text).root
    fields={n.attrs.get('id') or n.attrs.get('name'):n.attrs.get('value') for n in root.find(lambda n:n.tag=='input')}
    if not fields.get('preLoadJSON'):raise ValueError('UBS public page data missing')
    return json.loads(fields['preLoadJSON']),fields

def normalize(row):
    fields={q['QuestionName']:q.get('Value') for q in row['Questions']}
    identifier=str(fields['reqid']);url=row['Link']
    parsed=urlparse(url)
    if parsed.netloc!='jobs.ubs.com' or parse_qs(parsed.query).get('jobid')!=[identifier]:raise ValueError('UBS listing link does not match its ID')
    raw=fields.get('formtext23') or ''
    country,sep,region=raw.partition(' - ')
    loc={'city':'','region':region if sep else '', 'country':country if sep else '', 'raw':raw}
    return job('UBS',identifier,fields['jobtitle'],url,locs=[loc] if raw else [],tags=[fields.get('department'),fields.get('formtext21')],pending=True)

def fetch_snapshot(request):
    data,inputs=preload(request(URL).text)
    initial=data['searchResultsResponse'];total=initial['JobsCount']
    if type(total)is not int or not 0<total<20000:raise ValueError('Invalid UBS job count')
    rows=initial['Jobs']['Job'];result=[normalize(row) for row in rows]
    smart=json.loads(data['SmartSearchJSONValue'])
    body={'partnerId':'25008','siteId':'5012','keyword':'','location':'','keywordCustomSolrFields':smart['KeywordCustomSolrFields'],'locationCustomSolrFields':smart['LocationCustomSolrFields'],'linkId':'15231','Latitude':0,'Longitude':0,'facetfilterfields':{'Facet':[]},'powersearchoptions':{'PowerSearchOption':[]},'SortType':'LastUpdated','pageNumber':2,'encryptedSessionValue':inputs.get('CookieValue')}
    token=inputs.get('__RequestVerificationToken')
    while len(result)<total:
        data=request('https://jobs.ubs.com/TgNewUI/Search/Ajax/ProcessSortAndShowMoreJobs',body=dict(body),headers={'RFT':token} if token else {}).json()
        rows=(data.get('Jobs') or {}).get('Job')
        if data.get('JobsCount')!=total or not rows:raise ValueError('UBS index changed or pagination incomplete')
        result.extend(normalize(row) for row in rows)
        if len({j['external_id'] for j in result})!=len(result) or len(result)>total:raise ValueError('Duplicate or oversized UBS page')
        body['pageNumber']+=1
    return result

def fetch_detail(request,item):
    data,_=preload(request(item['url']).text)
    if str(data.get('JobId'))!=item['external_id']:raise ValueError('UBS detail ID mismatch')
    rows=(data.get('Jobdetails') or {}).get('JobDetailQuestions')
    if not rows:raise ValueError('UBS full details missing')
    fields={r['VerityZone']:r.get('AnswerValue') or '' for r in rows}
    if not fields.get('jobdescription'):raise ValueError('UBS description missing')
    description='\n'.join((r.get('QuestionName') or '')+'\n'+plain(r.get('AnswerValue')) for r in rows if r.get('QuestionType')=='textarea')
    loc=location(plain(fields.get('formtext2','')),item.get('country',''))
    result=dict(item,description=description,details_pending=False,details_available=True)
    if loc:
        result.update(locations=[loc],city=loc['city'],region=loc['region'],country=loc['country'])
    kind=plain(fields.get('formtext22','')).strip().lower()
    if kind in ('full time','part time'):
        result['type']='Full-time' if kind=='full time' else 'Part-time'
        result['evidence']={**item['evidence'],'type':{'status':'explicit','text':fields['formtext22']}}
    return result
