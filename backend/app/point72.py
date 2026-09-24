"""Read the public career page's embedded job list without executing JavaScript."""
import json
import re
from urllib.parse import urlencode, urlparse

URL = 'https://careers.point72.com/'

from .normalization import plain, decode_js_string, locations

def normalize(item):
    job = item['job']
    external_id = job.get('Job_Code__c') or job.get('Id')
    title = job.get('Name')
    if not external_id or not isinstance(title, str) or not title.strip():
        raise ValueError('Listing missing stable ID or title; refusing partial import')
    description = plain(job.get('Job_Description_External__c', ''))
    locs = locations(item.get('formattedLocation') or job.get('Posted_Location__c'))
    career_url = URL + 'CSJobDetail?' + urlencode({'jobName': item.get('friendlyJobName', ''), 'jobCode': external_id, 'locale': 'English'})
    apply_url = job.get('Apply_Now_URL__c') or career_url
    if urlparse(apply_url).scheme != 'https':
        apply_url = career_url
    raw_area = job.get('Area__c') or item.get('formattedArea', '')
    raw_experience = job.get('Experience__c', '')
    interests = ['Finance']
    if re.search(r'technology|engineering', raw_area, re.I):
        interests.append('Technology')
    if re.search(r'research', raw_area, re.I):
        interests.append('Research')
    if re.search(r'operations', job.get('Team__c', ''), re.I):
        interests.append('Operations')
    # Only literal internship titles establish this classification. Do not infer full-time.
    internship = bool(re.search(r'\bintern(?:ship)?\b', title, re.I))
    evidence = {'interest': {'status': 'inferred', 'text': raw_area},
                'studies': {'status': 'unknown'}, 'graduation': {'status': 'unknown'},
                'level': {'status': 'inferred' if internship else 'unknown', 'text': raw_experience},
                'type': {'status': 'explicit' if internship else 'unknown', 'text': title}}
    # Exact graduation-class statements only; never use the year from a title.
    graduation = []
    for line in description.splitlines():
        match = re.search(r'\bgraduating class of (20\d{2})\b', line, re.I)
        if match:
            graduation.append(int(match.group(1)))
            evidence['graduation'] = {'status': 'explicit', 'text': line}
    return {'external_id': str(external_id), 'company': 'Point72', 'title': title.strip(),
            'type': 'Internship' if internship else 'Not specified', 'interest': interests,
            'studies': [], 'area': '', 'locations': locs,
            'city': ' | '.join(x['city'] for x in locs),
            'region': ' | '.join(dict.fromkeys(x['region'] for x in locs if x['region'])),
            'country': ' | '.join(dict.fromkeys(x['country'] for x in locs if x['country'])),
            'arrangement': 'Not specified', 'level': 'Student' if internship else 'Not specified',
            'graduation': sorted(set(graduation)), 'description': description,
            'url': apply_url, 'source_url': career_url, 'evidence': evidence,
            'source_experience': raw_experience, 'source_updated_at': job.get('LastModifiedDate'),
            'posted_at': None, 'is_sample': False}

def parse_page(page):
    match = re.search(r"CSSearchModule\.init\(\s*'((?:\\.|[^'\\])*)'", page, re.S)
    if not match:
        raise ValueError('Point72 job payload not found; page format may have changed')
    data = json.loads(decode_js_string(match.group(1)))
    if not isinstance(data, list) or not data:
        raise ValueError('Empty or invalid source payload; existing jobs retained')
    jobs = [normalize(item) for item in data]
    if len({j['external_id'] for j in jobs}) != len(jobs):
        raise ValueError('Duplicate source IDs; refusing ambiguous snapshot')
    return jobs
