import re
import xml.etree.ElementTree as ET
from .feed_common import job
from .html_tree import Tree
from .ares import location
URL='https://jefferies.tal.net/vx/mobile-0/appcentre-1/brand-4/candidate/jobboard/vacancy/2/feed'
SCOPE='Campus opportunities only; the experienced-hire portal is not connected.'

def fetch_snapshot(request):
    root=ET.fromstring(request(URL).text);ns={'a':'http://www.w3.org/2005/Atom'}
    if root.find('a:link[@rel="next"]',ns) is not None:raise ValueError('Jefferies feed now requires pagination')
    entries=root.findall('a:entry',ns)
    if not entries:raise ValueError('Jefferies feed empty')
    result=[]
    for entry in entries:
        link=entry.find('a:link[@rel="alternate"]',ns)
        url=link.attrib['href'] if link is not None else entry.findtext('a:id',namespaces=ns)
        url=re.sub(r'/xf-[^/]+','',url).split('?')[0]
        match=re.search(r'/opp/(\d+)',url)
        if not match:raise ValueError('Jefferies application ID missing')
        tree=Tree(request(url).text).root
        fields=tree.find(lambda n:n.attrs.get('role')=='definition' and n.has_class('hform_value_view'))
        if not fields:raise ValueError('Jefferies details layout changed')
        description=max((n.text() for n in fields),key=len)
        if len(description)<200:raise ValueError('Jefferies description incomplete')
        title=entry.findtext('a:title',namespaces=ns)
        city=next((n.text() for n in fields if n.has_class('item78763')), '')
        loc=location(city)
        result.append(job('Jefferies',match.group(1),title,url,description,locs=[loc] if loc else []))
    return result
