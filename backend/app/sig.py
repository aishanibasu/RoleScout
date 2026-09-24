"""Public Susquehanna/iCIMS search feed, with full descriptions in each page."""
from .normalization import plain
from .ares import location
import re

URL = 'https://careers.sig.com/jobs'

def normalize(j):
    if not j.get('req_id') or not j.get('title') or not j.get('description'):
        raise ValueError('Susquehanna listing missing ID, title or description')
    locs = []
    raw = ', '.join(j.get(k, '') for k in ('city', 'state', 'country') if j.get(k))
    if raw:
        locs.append({'city': j.get('city',''), 'region':j.get('state',''), 'country':j.get('country',''), 'raw':raw})
    if j.get('multipleLocations'):
        # Preserve every provided structured location; never silently collapse multiple offices.
        extras = j.get('locations', [])
        if not extras:
            raise ValueError('Susquehanna multi-location payload needs additional mapping')
        for extra in extras:
            if not isinstance(extra,dict):raise ValueError('Unknown Susquehanna location shape')
            locs.append({'city':extra.get('city',''),'region':extra.get('state',''),'country':extra.get('country',''),'raw':str(extra.get('full_location',''))})
    tags = [x['name'] for x in j.get('categories',[])] + j.get('tags1',[]) + j.get('tags2',[])
    internship = any('intern' in t.lower() or 'co-op' in t.lower() for t in tags) or bool(re.search(r'\bintern(?:ship)?\b',j['title'],re.I))
    graduate = any(t.lower().strip()=='new graduates' for t in tags)
    level = 'Student' if internship else 'New graduate' if graduate else 'Not specified'
    interest = ['Finance']
    if any(re.search('technology|software|engineer',t,re.I) for t in tags):interest.append('Technology')
    if any(re.search('quant|research',t,re.I) for t in tags):interest.append('Research')
    if any('operations' in t.lower() for t in tags):interest.append('Operations')
    source_url = URL + '/' + str(j['slug'])
    return {'external_id':str(j['req_id']), 'company':'Susquehanna', 'title':j['title'],
        'description':plain(j['description']), 'type':'Internship' if internship else 'Not specified',
        'level':level,'interest':interest,'studies':[],'area':'','graduation':[],
        'arrangement':'Not specified','locations':locs,
        **{k:' | '.join(dict.fromkeys(l[k] for l in locs if l[k])) for k in ('city','region','country')},
        'url':source_url,'source_url':source_url,'source_experience':', '.join(tags),
        'posted_at':j.get('posted_date'),'source_updated_at':j.get('update_date'),'is_sample':False,
        'evidence':{'type':{'status':'explicit' if internship else 'unknown','text':', '.join(tags)},
                    'level':{'status':'explicit' if graduate or internship else 'unknown','text':', '.join(tags)},
                    'interest':{'status':'inferred','text':', '.join(tags)}}}

def fetch_snapshot(request):
    jobs, total, page = [], None, 1
    while total is None or len(jobs) < total:
        payload=request(f'https://careers.sig.com/api/jobs?page={page}&limit=100').json()
        count=payload.get('totalCount');rows=payload.get('jobs')
        if type(count) is not int or not 0<count<10000 or not isinstance(rows,list) or not rows:
            raise ValueError('Invalid or empty Susquehanna feed')
        if total is not None and total!=count:raise ValueError('Susquehanna feed changed during pagination')
        total=count
        jobs.extend(normalize(row['data']) for row in rows)
        if len({j['external_id'] for j in jobs})!=len(jobs) or len(jobs)>total:
            raise ValueError('Susquehanna pagination duplicated or exceeded total')
        page+=1
    return jobs
