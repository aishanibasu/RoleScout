"""Inspect known public career pages and report links; never bypass access challenges."""
import concurrent.futures
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
import httpx

PAGES = {
 'apollo':'https://www.apollo.com/careers',
 'morganstanley':'https://www.morganstanley.com/people-opportunities',
 'bofa':'https://careers.bankofamerica.com/en-us',
 'bny':'https://www.bny.com/corporate/global/en/about-us/careers/work-with-us.html',
 'ubs':'https://www.ubs.com/global/en/careers/search-jobs.html',
 'rbc':'https://jobs.rbc.com/ca/en',
 'gs':'https://www.goldmansachs.com/careers',
 'jefferies':'https://www.jefferies.com/careers/apply-now/',
 'twosigma':'https://www.twosigma.com/careers/',
 'sig':'https://sig.com/careers/',
 'jpmorgan':'https://www.jpmorganchase.com/careers',
 'hft':'https://www.hft-jobs.com/jobs',
 'bam':'https://bambusdev.my.site.com/s/',
}
OUT=Path(__file__).resolve().parents[1]/'data'/'research'
OUT.mkdir(parents=True,exist_ok=True)
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  if tag=='a':
   a=dict(attrs)
   if a.get('href'):self.links.append(a['href'])
def probe(item):
 name,url=item
 try:
  with httpx.Client(timeout=25,follow_redirects=True,headers={'User-Agent':'RoleSearcher/0.1'}) as c:
   robots=c.get(urljoin(url,'/robots.txt'))
   (OUT/(name+'-robots.txt')).write_text(robots.text)
   if robots.status_code==200:
    rules=RobotFileParser();rules.parse(robots.text.splitlines())
    if not rules.can_fetch('RoleSearcher/0.1',url):return {'id':name,'status':'robots-disallowed','url':url}
   elif robots.status_code!=404:return {'id':name,'status':'robots-http-'+str(robots.status_code),'url':url}
   r=c.get(url)
   (OUT/(name+'.html')).write_text(r.text)
   p=Links();p.feed(r.text)
   links=list(dict.fromkeys(urljoin(str(r.url),h) for h in p.links if any(s in h.lower() for s in ('career','job','opportunit','workday','taleo','avature','apply','oracle','eightfold','phenom'))))
   return {'id':name,'status':r.status_code,'url':str(r.url),'bytes':len(r.content),'links':links[:35]}
 except Exception as e:return {'id':name,'error':str(e)}
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  results=list(pool.map(probe,PAGES.items()))
 (OUT/'discovery.json').write_text(json.dumps(results,indent=2))
 for r in results:print(json.dumps(r),flush=True)
