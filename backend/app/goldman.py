from .feed_common import job
URL='https://api-higher.gs.com/gateway/api/v1/graphql'
SCOPE='Goldman Sachs public campus, early-career and professional role index; visit the employer for full requirements.'
QUERY='query GetRoles($searchQueryInput: RoleSearchQueryInput!) { roleSearch(searchQueryInput: $searchQueryInput) { totalCount items { roleId jobTitle jobFunction locations { primary state country city } status division jobType { code description } } } }'

def fetch_snapshot(request):
    results=[];total=None;page=0
    while total is None or len(results)<total:
        body={'operationName':'GetRoles','query':QUERY,'variables':{'searchQueryInput':{'page':{'pageSize':100,'pageNumber':page},'sort':{'sortStrategy':'POSTED_DATE','sortOrder':'DESC'},'filters':[],'experiences':['CAMPUS','EARLY_CAREER','PROFESSIONAL'],'searchTerm':''}}}
        response=request(URL,body=body).json()
        if response.get('errors'):raise ValueError('Goldman Sachs public query rejected')
        data=response['data']['roleSearch'];rows=data['items'];count=data['totalCount']
        if not rows or type(count)is not int or not 0<count<20000 or (total is not None and total!=count):raise ValueError('Goldman Sachs index incomplete or changed during collection')
        total=count
        for r in rows:
            locations=[dict(city=l.get('city') or '',region=l.get('state') or '',country=l.get('country') or '',raw=', '.join(l[k] for k in ('city','state','country') if l.get(k))) for l in r.get('locations') or []]
            item=job('Goldman Sachs',r['roleId'],r['jobTitle'],'https://higher.gs.com/roles/'+r['roleId'],locs=locations,tags=[r.get('jobFunction'),r.get('division')])
            item['description_note']='Full requirements are available on the employer’s website.'
            results.append(item)
        if len({r['external_id'] for r in results})!=len(results) or len(results)>total:raise ValueError('Duplicate Goldman Sachs page')
        page+=1
    return results
