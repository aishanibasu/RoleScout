import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.collect import with_source

def run(request):
 seen=set()
 for offset in [0,180,360,540,720,900,1080,1260,1380]:
  url=f'https://eofe.fa.us2.oraclecloud.com/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true&expand=requisitionList&finder=findReqs;siteNumber=CX_3001,limit=499,offset={offset},sortBy=POSTING_DATES_DESC'
  d=request(url).json()['items'][0];rows=d.get('requisitionList') or [];ids=[r['Id'] for r in rows]
  Path(f'data/research/bny_diag{offset}.json').write_text(json.dumps(d))
  print(offset,d['Offset'],d['TotalJobsCount'],len(ids),len(set(ids)-seen),ids[:2],flush=True);seen.update(ids)
 print('unique',len(seen),flush=True)
with_source('bny',run)
