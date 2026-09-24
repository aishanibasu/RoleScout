"""Adapter for the public Workday portal linked from Ares's official careers page."""
import logging
import re
from urllib.parse import urlparse
from .normalization import plain, locations

NAME = 'Ares Management'
ORIGIN = 'https://aresmgmt.wd1.myworkdayjobs.com'
URL = ORIGIN + '/External'
API = ORIGIN + '/wday/cxs/aresmgmt/External'
log = logging.getLogger('role-searcher.ares')
US_REGIONS = dict(pair.split(':') for pair in (
    'NY:New York|NJ:New Jersey|CA:California|TX:Texas|FL:Florida|IL:Illinois|CT:Connecticut|'
    'MA:Massachusetts|WA:Washington|CO:Colorado|GA:Georgia|NC:North Carolina|VA:Virginia|'
    'PA:Pennsylvania|MD:Maryland|AZ:Arizona|TN:Tennessee|DC:District of Columbia|OH:Ohio|'
    'MN:Minnesota|UT:Utah|NV:Nevada|OR:Oregon|MI:Michigan|MO:Missouri|WI:Wisconsin|'
    'IN:Indiana|SC:South Carolina|AL:Alabama|LA:Louisiana|OK:Oklahoma|KY:Kentucky|'
    'IA:Iowa|KS:Kansas|NE:Nebraska|AR:Arkansas|MS:Mississippi|DE:Delaware|RI:Rhode Island|'
    'NH:New Hampshire|VT:Vermont|ME:Maine|ID:Idaho|MT:Montana|WY:Wyoming|ND:North Dakota|'
    'SD:South Dakota|NM:New Mexico|AK:Alaska|HI:Hawaii|WV:West Virginia').split('|'))

def location(raw, country=''):
    if not isinstance(raw, str) or not raw.strip():
        return None
    normalized = locations(raw)[0]
    pieces = [s.strip() for s in raw.split(',')]
    if len(pieces) > 1 and pieces[-1] in US_REGIONS:
        normalized.update(region=US_REGIONS[pieces[-1]], country='United States')
    if country:
        # A primary location's explicit country never propagates to other locations.
        normalized['country'] = {'United States of America': 'United States'}.get(country, country)
    return normalized

def normalize(payload, external_path, company=NAME, base_url=URL):
    j = payload.get('jobPostingInfo')
    if not isinstance(j, dict):
        raise ValueError('Ares detail missing jobPostingInfo; refusing partial snapshot')
    title, posting_id = j.get('title'), j.get('id')
    if not isinstance(title, str) or not title.strip() or not posting_id or not j.get('jobDescription'):
        raise ValueError('Ares job missing ID, title, or description')
    if j.get('canApply') is not True or j.get('posted') is not True:
        raise ValueError('Ares listing changed during collection; retry a complete snapshot later')
    description = plain(j['jobDescription'])
    primary = location(j.get('location'), (j.get('country') or {}).get('descriptor', ''))
    locs = [primary] if primary else []
    for extra in j.get('additionalLocations', []):
        if not isinstance(extra, str):
            raise ValueError('Unrecognized Ares additional location shape')
        mapped = location(extra)
        if mapped and mapped not in locs:
            locs.append(mapped)
    internship = bool(re.search(r'\bintern(?:ship)?\b', title, re.I))
    graduate = bool(re.search(r'\b(?:new graduate|university graduate)\b', title, re.I))
    role_type = 'Internship' if internship else {'Full time': 'Full-time', 'Part time': 'Part-time'}.get(j.get('timeType'), 'Not specified')
    interests = ['Finance']
    if re.search(r'software|data engineer|data scien|cyber|information technology', title, re.I):
        interests.append('Technology')
    if re.search(r'\bresearch\b', title, re.I):
        interests.append('Research')
    if re.search(r'\boperations\b', title, re.I):
        interests.append('Operations')
    grad = []
    evidence = {k: {'status': 'unknown'} for k in ('studies', 'graduation', 'level')}
    evidence['interest'] = {'status': 'inferred', 'text': title}
    evidence['type'] = {'status': 'explicit' if role_type != 'Not specified' else 'unknown', 'text': title if internship else j.get('timeType', '')}
    if internship or graduate:
        evidence['level'] = {'status': 'inferred', 'text': title}
    for line in description.splitlines():
        m = re.search(r'\bgraduating class of (20\d{2})\b', line, re.I)
        if m:
            grad.append(int(m.group(1)))
            evidence['graduation'] = {'status': 'explicit', 'text': line}
    source_url = base_url + external_path
    if j.get('externalUrl') and urlparse(j['externalUrl']).netloc != urlparse(base_url).netloc:
        raise ValueError('Unexpected application URL host')
    return {
        'external_id': str(posting_id), 'requisition_id': j.get('jobReqId'), 'company': company,
        'title': title.strip(), 'type': role_type, 'interest': interests, 'studies': [], 'area': '',
        'locations': locs, 'city': ' | '.join(l['city'] for l in locs),
        'region': ' | '.join(dict.fromkeys(l['region'] for l in locs if l['region'])),
        'country': ' | '.join(dict.fromkeys(l['country'] for l in locs if l['country'])),
        'arrangement': 'Not specified', 'level': 'Student' if internship else 'New graduate' if graduate else 'Not specified',
        'graduation': sorted(set(grad)), 'description': description,
        'url': source_url, 'source_url': source_url, 'source_experience': '', 'evidence': evidence,
        'source_updated_at': None, 'posted_at': j.get('startDate'), 'is_sample': False,
    }

def listing_path(value):
    if not isinstance(value, str) or not value.startswith('/job/') or urlparse(value).netloc or '?' in value or '#' in value or '..' in value:
        raise ValueError('Invalid Ares listing path')
    return value

def fetch_snapshot(request, api=API, company=NAME, base_url=URL):
    """Read every listing page, then details. Any failure aborts the entire snapshot."""
    paths, total, offset = [], None, 0
    while total is None or offset < total:
        page = request(api + '/jobs', body={'appliedFacets': {}, 'limit': 20, 'offset': offset, 'searchText': ''}).json()
        reported = page.get('total')
        batch = page.get('jobPostings')
        if type(reported) is not int or reported < 0 or reported > 10000 or not isinstance(batch, list) or not batch:
            raise ValueError('Invalid or empty Ares search response')
        # Workday returns total=0 on subsequent pages even when jobs are present.
        if total is None and reported == 0:
            raise ValueError('Ares first page has no total')
        if total is not None and reported not in (0, total):
            raise ValueError('Ares listing count changed during pagination')
        total = reported if total is None else total
        paths.extend(listing_path(item.get('externalPath')) for item in batch)
        offset += len(batch)
        if len(set(paths)) != len(paths) or offset > total:
            raise ValueError('Duplicate or inconsistent Ares pagination')
    if len(paths) != total:
        raise ValueError('Incomplete Ares snapshot')
    jobs = []
    for index, path in enumerate(paths, 1):
        jobs.append(normalize(request(api + path).json(), path, company, base_url))
        if index % 25 == 0 or index == total:
            log.info('%s: read %s/%s job descriptions', company, index, total)
    return jobs
