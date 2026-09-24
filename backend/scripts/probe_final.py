from probe_feeds import go,OUT
import concurrent.futures,re,json
from urllib.parse import urljoin
TASKS={
'hft_rows':('https://deibfndusyfrjgtfvkae.supabase.co/rest/v1/jobs?select=id,date_added,company_name,title,classifications,experienced_hire,country,location,remote,job_url,careers_url&is_active=eq.true&limit=2',None),
'rbc_workday':('https://rbc.wd3.myworkdayjobs.com/wday/cxs/rbc/RBCGLOBAL1/jobs',{'appliedFacets':{},'limit':20,'offset':0,'searchText':''}),
'jefferies_roles':('https://jefferies.tal.net/vx/lang-en-GB/mobile-0/appcentre-ext/brand-4/candidate/jobboard/vacancy/2/adv/',None),
'gs_393':('https://higher.gs.com/_next/static/chunks/393-63f4b8bfd45b6c4d.js',None),
'gs_557':('https://higher.gs.com/_next/static/chunks/557-df2e2f15677ec87c.js',None),
'gs_402':('https://higher.gs.com/_next/static/chunks/402-828b996422748899.js',None),
}
# HFT exposes a public publishable key in its client; use it only for the public jobs query.
import httpx
key=re.search(r'Fw="([^"]+)"',(OUT/'hft_script.html').read_text()).group(1)
def probe(item):
 if item[0]!='hft_rows':return go(item)
 name,(url,body)=item
 try:
  with httpx.Client(timeout=20) as c:
   robots=c.get(urljoin(url,'/robots.txt'))
   if robots.status_code not in (200,404):return name,'robots',robots.status_code
   r=c.get(url,headers={'apikey':key});(OUT/(name+'.txt')).write_text(r.text)
   return name,r.status_code,len(r.content)
 except Exception as e:return name,str(e)
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
 for result in pool.map(probe,TASKS.items()):print(result,flush=True)
