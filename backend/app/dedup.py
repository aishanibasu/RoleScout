"""Prefer direct employers over identical aggregator application links."""
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

def key(job):
    url=urlsplit(job['url'])
    # Keep requisition parameters; remove only known attribution parameters.
    query=[(k,v) for k,v in parse_qsl(url.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('source','gh_src')]
    return urlunsplit((url.scheme.lower(),url.netloc.lower(),url.path.rstrip('/'),urlencode(sorted(query)),''))

def deduplicate(jobs):
    result={}
    for job in sorted(jobs,key=lambda j:j['source']=='hft'):
        canonical=key(job)
        # Do not merge generic careers landing pages or source-local duplicates.
        previous=result.get(canonical)
        if previous is not None and previous['source'] != job['source'] and (previous['source']=='hft' or job['source']=='hft') and len(urlsplit(canonical).path.strip('/').split('/'))>=2:
            previous['also_listed_on']=sorted(set(previous.get('also_listed_on',[])+[job['source']]))
        else:
            result[canonical if previous is None else canonical+'#'+str(job['id'])]=dict(job)
    return list(result.values())
