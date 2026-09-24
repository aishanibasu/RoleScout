import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.collect import with_source
from app.oracle import bny

def run(request):
 def trace(url):
  r=request(url);p=r.json()['items'][0];rows=p.get('requisitionList') or []
  print('offset',p.get('Offset'),'limit',p.get('Limit'),'total',p.get('TotalJobsCount'),'rows',len(rows),'first',rows[0]['Id'] if rows else None,flush=True)
  return r
 return bny.fetch_snapshot(trace)
try:print('Complete:',len(with_source('bny',run)))
except Exception as e:print(type(e).__name__,str(e),flush=True)
