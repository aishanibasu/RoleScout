import ast
from .feed_common import job
from .ares import location
URL='https://deibfndusyfrjgtfvkae.supabase.co/rest/v1/jobs'
# Publishable browser key, intentionally public; no user session or private tables are accessed.
HEADERS={'apikey':'sb_publishable_RO9akeUU4FR5zKF1JJXJhw_ZTai0pdm','Prefer':'count=exact'}
SCOPE='Public active listings from HFT Jobs; descriptions must be read on the employer website.'
FIELDS='id,date_added,company_name,title,classifications,experienced_hire,country,location,remote,job_url,careers_url'

def fetch_snapshot(request):
    result,total,offset=[],None,0
    while total is None or offset<total:
        response=request(f'{URL}?select={FIELDS}&is_active=eq.true&order=id.asc&limit=1000&offset={offset}')
        rows=response.json()
        reported=response.headers.get('content-range','').rsplit('/',1)[-1]
        if not reported.isdigit() or not isinstance(rows,list) or not rows:
            raise ValueError('Incomplete HFT Jobs response')
        if total is not None and int(reported)!=total:raise ValueError('HFT Jobs changed during pagination')
        total=int(reported)
        if total>50000:raise ValueError('Unexpected HFT Jobs count')
        for r in rows:
            tags=r.get('classifications') or []
            if isinstance(tags,str):
                try:tags=ast.literal_eval(tags)
                except (SyntaxError,ValueError):tags=[]
            if not isinstance(tags,list):tags=[]
            loc=location(r.get('location'),r.get('country') or '')
            item=job(r['company_name'],r['id'],r['title'],r['job_url'],locs=[loc] if loc else [],tags=tags,posted=None)
            item['source_added_at']=r.get('date_added')
            item['description_note']='This job board provides listing metadata. Read the full requirements on the original application page.'
            result.append(item)
        offset+=len(rows)
        if offset>total:raise ValueError('HFT Jobs pagination exceeded total')
    return result
