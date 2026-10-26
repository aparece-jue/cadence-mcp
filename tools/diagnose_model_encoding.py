import json
from pathlib import Path
from cadence_mcp.pspice_input import PSpiceInputs
from cadence_mcp.core import Config,sha256
r=Path(r'D:\workspace\git\cadence-mcp');root=r/'.local/model-encoding-diagnosis-20261026';root.mkdir(exist_ok=False);install=Path(r'D:\Program Files\Cadence\SPB_24.1');source=r/'.local/profile-cir-native-v2-20261026/project/LowPassFilters-PSpiceFiles/LPFilters/AC/AC.cir';events=[];original=Path.read_bytes
def record(p):
 raw=original(p)
 try:raw.decode('utf-8-sig')
 except UnicodeDecodeError as e:
  bad=[]
  for number,line in enumerate(raw.splitlines(),1):
   try:line.decode('utf-8')
   except UnicodeDecodeError:bad.append({'line':number,'fullComment':line.lstrip().startswith(b'*'),'size':len(line)})
  events.append({'path':str(p),'sha256':sha256(p),'size':len(raw),'badLines':bad})
 return raw
Path.read_bytes=record
result={'files':events}
try:PSpiceInputs(Config(install,root/'work',(source.parent.parent,install/'tools/pspice/library'))).prepare(str(source))
except Exception as e:result.update(errorCode=getattr(e,'code',None),error=str(e))
finally:Path.read_bytes=original
(root/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result))
