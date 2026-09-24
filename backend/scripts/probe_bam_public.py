import sys,json,re
from pathlib import Path
from urllib.parse import unquote
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.collect import with_source,ADAPTERS
from types import SimpleNamespace
ADAPTERS['bam']=SimpleNamespace(URL='https://bambusdev.my.site.com/s/')
def run(request):
 text=request(ADAPTERS['bam'].URL).text
 configs=[json.JSONDecoder().raw_decode(unquote(value))[0] for value in re.findall(r'/s/sfsites/l/(%7B[^"\s]+)',text)]
 config=next(c for c in configs if 'fwuid' in c)
 context={k:config[k] for k in ('mode','fwuid','app','loaded')};context.update(dn=[],globals={},uad=True)
 action={'id':'1;a','descriptor':'aura://ApexActionController/ACTION$execute','callingDescriptor':'UNKNOWN','params':{'namespace':'','classname':'BamJobRequisitionInfoDataService','method':'searchJobRequisitions','params':{'isVendorPortal':False,'site':'BAM Website','searchKey':'','locationFilters':[],'departmentFilter':[],'availableLocations':[],'experienceLevelFilter':[]},'cacheable':True,'isContinuation':False}}
 data=request('https://bambusdev.my.site.com/s/sfsites/aura',form={'message':json.dumps({'actions':[action]}),'aura.context':json.dumps(context),'aura.pageURI':'/s/','aura.token':'null'}).json()
 Path('data/research/bam_public.json').write_text(json.dumps(data))
 print([(a['state'],len(a.get('returnValue',{}).get('returnValue',[]))) for a in data['actions']])
with_source('bam',run)
