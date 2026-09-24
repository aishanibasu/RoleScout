import sys,json,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx
from app.html_tree import Tree
from urllib.robotparser import RobotFileParser
url='https://jobs.ubs.com/TGnewUI/Search/home/HomeWithPreLoad?partnerid=25008&siteid=5012&PageType=searchResults&SearchType=linkquery&LinkID=15231'
with httpx.Client(timeout=45,follow_redirects=True,headers={'User-Agent':'RoleSearcher/0.1'}) as c:
 robots=c.get('https://jobs.ubs.com/robots.txt');rules=RobotFileParser()
 if robots.status_code not in (200,404):raise ValueError('Robots unavailable')
 if robots.status_code==200:rules.parse(robots.text.splitlines())
 for endpoint in [url,'https://jobs.ubs.com/TgNewUI/Search/Ajax/ProcessSortAndShowMoreJobs']:
  if robots.status_code==200 and not rules.can_fetch('RoleSearcher/0.1',endpoint):raise ValueError('Robots disallowed')
 page=c.get(url);root=Tree(page.text).root
 inputs={n.attrs.get('id') or n.attrs.get('name'):n.attrs.get('value') for n in root.find(lambda n:n.tag=='input')}
 preload=json.loads(inputs['preLoadJSON']);body=json.loads(preload['SmartSearchJSONValue']);body['PageNumber']=2
 body={'partnerId':'25008','siteId':'5012','keyword':'','location':'','keywordCustomSolrFields':body['KeywordCustomSolrFields'],'locationCustomSolrFields':body['LocationCustomSolrFields'],'linkId':'15231','Latitude':0,'Longitude':0,'facetfilterfields':{'Facet':[]},'powersearchoptions':{'PowerSearchOption':[]},'SortType':'LastUpdated','pageNumber':2,'encryptedSessionValue':inputs.get('CookieValue')}
 token=next((n.attrs.get('value') for n in root.find(lambda n:n.tag=='input' and n.attrs.get('name')=='__RequestVerificationToken')),None)
 time.sleep(1)
 response=c.post('https://jobs.ubs.com/TgNewUI/Search/Ajax/ProcessSortAndShowMoreJobs',json=body,headers={'RFT':token} if token else {})
 Path('data/research/ubs_sort2.json').write_text(response.text)
 print(response.status_code,len(response.content));print(list(response.json())[:15])
