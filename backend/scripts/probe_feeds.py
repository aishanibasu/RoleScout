import concurrent.futures,json,re
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
import httpx
OUT=Path(__file__).resolve().parents[1]/'data'/'research'
TASKS={
'apollo_feed':('https://athene.wd5.myworkdayjobs.com/wday/cxs/athene/Apollo_Careers/jobs',{'appliedFacets':{},'limit':20,'offset':0,'searchText':''}),
'bofa_feed':('https://ghr.wd1.myworkdayjobs.com/wday/cxs/ghr/Lateral-US/jobs',{'appliedFacets':{},'limit':20,'offset':0,'searchText':''}),
'bny_feed':('https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_3001,limit=25,offset=0',None),
'sig_feed':('https://careers.sig.com/api/jobs?page=1&limit=100',None),
'rbc_page2':('https://jobs.rbc.com/ca/en/search-results?from=10&s=1',None),
'morgan_script':('https://www.morganstanley.com/etc.clientlibs/msdotcomr4/components/common/opportunity-aggregate/v1/opportunity-aggregate/clientlibs/site.min.13662067aae67620d74e0f7210299aec.js',None),
'gs_script':('https://higher.gs.com/_next/static/chunks/pages/results-5684534c241e9a32.js',None),
'gs_appscript':('https://higher.gs.com/_next/static/chunks/pages/_app-PLACEHOLDER.js',None),
 'twosigma_list':('https://careers.twosigma.com/careers/OpenRoles',None),
}
# Find the current publicly linked app bundle instead of assuming a build hash.
s=(OUT/'gs_jobs.html').read_text();m=re.search(r'src="([^"]*/pages/_app-[^"]+)"',s)
if m:TASKS['gs_appscript']=(urljoin('https://higher.gs.com',m.group(1)),None)
else:TASKS.pop('gs_appscript')
def go(item):
 name,(url,body)=item
 try:
  with httpx.Client(timeout=30,follow_redirects=True,headers={'User-Agent':'RoleSearcher/0.1'}) as c:
   robots=c.get(urljoin(url,'/robots.txt'))
   if robots.status_code not in (200,404):return name,'robots',robots.status_code
   if robots.status_code==200:
    rule=RobotFileParser();rule.parse(robots.text.splitlines())
    if not rule.can_fetch('RoleSearcher/0.1',url):return name,'robots-disallowed'
    import time;time.sleep(rule.crawl_delay('RoleSearcher/0.1') or 1)
   r=c.get(url) if body is None else c.post(url,json=body)
   (OUT/(name+'.txt')).write_text(r.text)
   return name,r.status_code,len(r.content),r.text[:160] if 'json' in r.headers.get('content-type','') else ''
 except Exception as e:return name,str(e)
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for r in pool.map(go,TASKS.items()):print(r,flush=True)
