"""Read the anonymous jobs action used by Balyasny's public careers website."""
import json,re
from urllib.parse import unquote,quote
from .feed_common import job
from .ares import location
from .normalization import plain
URL='https://bambusdev.my.site.com/s/'
SCOPE='Public Balyasny career listings, including internships. Full descriptions populate in background.'

def public_action(request,method,params,classname='BamJobRequisitionInfoDataService'):
    context=getattr(request,'_bam_context',None)
    if context is None:
        text=request(URL).text
        configs=[json.JSONDecoder().raw_decode(unquote(value))[0] for value in re.findall(r'/s/sfsites/l/(%7B[^"\s]+)',text)]
        config=next((c for c in configs if 'fwuid' in c and 'loaded' in c),None)
        if not config:raise ValueError('Balyasny public bootstrap configuration missing')
        context={k:config[k] for k in ('mode','fwuid','app','loaded')}
        context.update(dn=[],globals={},uad=True)
        request._bam_context=context
    action={'id':'1;a','descriptor':'aura://ApexActionController/ACTION$execute','callingDescriptor':'UNKNOWN','params':{'namespace':'','classname':classname,'method':method,'params':params,'cacheable':True,'isContinuation':False}}
    data=request(URL+'sfsites/aura',form={'message':json.dumps({'actions':[action]}),'aura.context':json.dumps(context),'aura.pageURI':'/s/','aura.token':'null'}).json()
    actions=data.get('actions') or []
    if len(actions)!=1 or actions[0].get('state')!='SUCCESS':raise ValueError('Balyasny public jobs request failed')
    return actions[0]['returnValue']['returnValue']

def normalize(row):
    title=row.get('Publish_Title__c') or row['Name']
    slug=row['Job_Req_Title_in_URL__c']+'_'+row['Requisition_Number__c']
    locs=[location(r['Location__r']['External_Name__c']) for r in row.get('Job_Requisition_Positions__r',[])]
    tags=[row.get('Department__c'),row.get('Experience_Level__c')]
    level='Student' if row.get('Experience_Level__c')=='Internships' else 'Not specified'
    item=job('Balyasny Asset Management',row['Requisition_Number__c'],title,URL+'details?jobReq='+quote(slug,safe=''),locs=[l for l in locs if l],level=level,tags=tags,pending=True)
    item['detail_id']=row['Id']
    item['description_note']='Read full requirements on the employer’s application page.'
    return item

def fetch_snapshot(request):
    rows=public_action(request,'searchJobRequisitions',{'isVendorPortal':False,'site':'BAM Website','searchKey':'','locationFilters':[],'departmentFilter':[],'availableLocations':[],'experienceLevelFilter':[]})
    if not isinstance(rows,list) or not rows or len(rows)>5000:raise ValueError('Invalid Balyasny public listings')
    return [normalize(row) for row in rows]


def fetch_detail(request,item):
    data=public_action(request,'getDescription',{'req':item['detail_id']},'rolePage')
    if not isinstance(data,dict) or not data.get('Description__c'):raise ValueError('Balyasny full description unavailable')
    return dict(item,description=plain(data['Description__c']),details_available=True,details_pending=False)
