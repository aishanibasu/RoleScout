"""Shared shape for listings with source-provided metadata; missing details remain explicit."""
import re
from urllib.parse import urlparse
from .normalization import plain

def job(company, external_id, title, url, description='', locs=None, role_type='Not specified', level='Not specified', tags=None, posted=None, pending=False):
    if not external_id or not title or urlparse(url).scheme not in ('http','https'):
        raise ValueError('Public listing missing ID, title or safe source URL')
    locs=locs or []
    tags=[str(tag) for tag in (tags or []) if tag]
    if re.search(r'\bintern(?:ship)?\b',title,re.I):role_type='Internship'
    interest=['Finance']
    for name,pattern in [('Technology',r'technology|software|data scien|engineering'),('Research',r'research|quantitative'),('Operations',r'operations')]:
        if re.search(pattern,' '.join(tags),re.I):interest.append(name)
    return {'external_id':str(external_id),'company':company,'title':title,'description':plain(description),
        'locations':locs,**{k:' | '.join(dict.fromkeys(l.get(k,'') for l in locs if l.get(k))) for k in ('city','region','country')},
        'type':role_type,'level':level,'interest':interest,'studies':[],'area':'','graduation':[],
        'arrangement':'Not specified','source_url':url,'url':url,'is_sample':False,'posted_at':posted,
        'source_updated_at':None,'source_experience':', '.join(tags),'details_pending':pending,
        'details_available':bool(description),
        'evidence':{'type':{'status':'explicit' if role_type!='Not specified' else 'unknown','text':role_type},
        'level':{'status':'explicit' if level!='Not specified' else 'unknown','text':', '.join(tags)},
        'interest':{'status':'inferred','text':', '.join(tags)}}}
