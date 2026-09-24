import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.collect import with_source
from app.bam import public_action
value=with_source('bam',lambda request:public_action(request,'getDescription',{'req':'a0DUN00000EuNjR2AV'},'rolePage'))
Path('data/research/bam_description.json').write_text(json.dumps(value))
print(type(value).__name__,str(value)[:400])
