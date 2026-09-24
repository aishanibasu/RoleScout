from .feed_common import job
from .ares import location
URL='https://www.morganstanley.com/careers/career-opportunities-search'
SCOPE='Student and graduate programs; experienced-hire feed not returning listings.'

def fetch_snapshot(request):
    data=request('https://www.morganstanley.com/web/career_services/webapp/service/careerservice/resultset.json?opportunity=sg&lang=en').json()
    rows=data.get('resultSet')
    if data.get('status')!=200 or not rows or len(rows)!=data.get('totalResults'):
        raise ValueError('Incomplete Morgan Stanley student feed')
    jobs=[]
    for r in rows:
        loc=location(r.get('location',''),r.get('country',''))
        kind={'Internship':'Internship','Full-Time':'Full-time','Full Time':'Full-time'}.get(r.get('employmentType'),'Not specified')
        level='Student' if kind=='Internship' else 'Not specified'
        jobs.append(job('Morgan Stanley',r['jobNumber'],r['jobTitle'],r['url'],r.get('jobDescription',''),[loc] if loc else [],kind,level,[r.get('division',''),r.get('employmentType','')]))
    return jobs
