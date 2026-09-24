from urllib.parse import urljoin,urlparse,parse_qs
import re
from .html_tree import Tree
from .feed_common import job
from .ares import location
from .normalization import CITY_MAP
URL='https://careers.twosigma.com/careers/OpenRoles'
SCOPE='Public Two Sigma open roles, including early careers.'

def fetch_snapshot(request):
    jobs=[];seen=set();page=URL
    for _ in range(100):
        root=Tree(request(page).text).root
        articles=root.find(lambda n:n.tag=='article' and n.attrs.get('id','').startswith('article--'))
        if not articles:raise ValueError('Two Sigma listing layout changed')
        for article in articles:
            links=article.find(lambda n:n.tag=='a' and '/JobDetail/' in n.attrs.get('href',''))
            if not links:continue
            link=links[0];url=urljoin(URL,link.attrs['href']);identifier=urlparse(url).path.rstrip('/').split('/')[-1]
            if identifier in seen:raise ValueError('Duplicate Two Sigma page')
            seen.add(identifier)
            spans=article.find(lambda n:n.has_class('paragraph__inner__span') or n.has_class('paragraph_inner-span'))
            tags=[n.text() for n in spans]
            detail=Tree(request(url).text).root
            sections=detail.find(lambda n:n.tag=='article' and n.has_class('article--details'))
            if not sections:raise ValueError('Two Sigma description missing')
            description=max((n.text() for n in sections),key=len)
            if len(description)<200:raise ValueError('Two Sigma description incomplete')
            raw=tags[0] if tags else ''
            country,sep,city=raw.partition(' - ')
            city=re.sub(r'^[A-Z]{2} ', '', city) if sep else raw
            loc=location(city, country if sep else '')
            if loc:loc['raw']=raw
            jobs.append(job('Two Sigma',identifier,link.text(),url,description,[loc] if loc else [],tags=tags))
        pages=root.find(lambda n:n.tag=='a' and 'jobOffset=' in n.attrs.get('href',''))
        current=int(parse_qs(urlparse(page).query).get('jobOffset',['0'])[0])
        nexts=[(int(parse_qs(urlparse(n.attrs['href']).query).get('jobOffset',['0'])[0]),urljoin(URL,n.attrs['href'])) for n in pages]
        nexts=sorted((offset,url) for offset,url in nexts if offset>current)
        if not nexts:return jobs
        page=nexts[0][1]
    raise ValueError('Two Sigma pagination exceeded limit')
