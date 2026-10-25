"""Read-only acceptance of an independently declared LS32 package pin table."""
import argparse,json
from pathlib import Path
from cadence_mcp.core import sha256
p=argparse.ArgumentParser()
p.add_argument('--evidence-root',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
expected={'U1A':{'I0':'1','I1':'2','O':'3','VCC':'14','GND':'7'},
          'U1B':{'I0':'4','I1':'5','O':'6','VCC':'14','GND':'7'},
          'U1C':{'I0':'9','I1':'10','O':'8','VCC':'14','GND':'7'}}
def matches(rows):
    for reference,mapping in expected.items():
        selected=[p for p in rows if p['reference']==reference]
        if len(selected)!=len(mapping) or {p['name']:p['occurrencePhysicalNumber'] for p in selected}!=mapping:return False
    return True
native=a.evidence_root/'native.json';process=json.loads((a.evidence_root/'report.json').read_text(encoding='utf-8'))
data=json.loads(native.read_text(encoding='utf-8'))
assert process['passed'] and process['copyUnchanged']
assert process['sourceHashBefore']==process['sourceHashAfter']=='27c6d11ffbb8d677954d8e56eba26a4b725c677aa83a08020da682972e1ef104'
assert matches(data['pins'])
bad=[dict(p) for p in data['pins']]
for pin in bad:
    if pin['reference']=='U1C':pin['occurrencePhysicalNumber']=pin['number']
assert not matches(bad),'Definition pin numbering must fail the C-unit oracle'
report={'passed':True,'scope':'selected_ls32_occurrence_physical_pin_map','expected':expected,
        'source':'https://www.ti.com/document-viewer/SN7432/datasheet',
        'nativeEvidence':str(native),'nativeSha256':sha256(native),
        'checks':{'datasheet_pin_map':True,'definition_numbers_negative_rejected':True},
        'completeH02':False,'notChecked':['complete_flat_net_oracle','connected_resistor_fixture','bus','heterogeneous_cell_correspondence','DRC']}
with a.output.open('x',encoding='utf-8') as f:json.dump(report,f,indent=2)
print(json.dumps({'passed':True,'scope':report['scope'],'completeH02':False}))
