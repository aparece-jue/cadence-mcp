import argparse,json
from pathlib import Path
from cadence_mcp.capture_wire import connection_digest
from cadence_mcp.core import sha256
p=argparse.ArgumentParser();p.add_argument('--fixture-root',type=Path,required=True);p.add_argument('--enumeration-root',type=Path,required=True);a=p.parse_args();root=a.fixture_root.resolve(strict=True);eroot=a.enumeration_root.resolve(strict=True)
r=json.loads((root/'report.json').read_text());props=json.loads((root/'property-order-audit.json').read_text());en=json.loads((eroot/'report.json').read_text());assert en['passed']
base=json.loads((root/'baseline/definition.json').read_text());connections=json.loads((root/'audit-source-connections.json').read_text());expected=connection_digest(base,connections['objects']);audit={'passed':False,'scope':'two explicit single-unit connected-fixture replacements with declared reference/value/footprint preservation','originalReportStillFailed':not r['passed'],'mutationReplayed':False,'cases':[]}
for i,c in enumerate(r['cases']):
 d=root/(c['selector']+'-'+str(c['update']));definition=json.loads((d/'definition-after.json').read_text());obs=json.loads((d/'audit-connections.json').read_text());cache=json.loads((eroot/('replace'+str(c['update'])+'.json')).read_text());ep=next(x for x in en['cases'] if x['name']=='replace'+str(c['update']))
 assert sha256(d/'design.dsn')==ep['sourceSha256Before']==c['outputSha256']
 pkg=next(x for x in cache['package'] if x['name']=='R')
 row={'update':c['update'],'saved':c['receipt']['saved'],'definitionMatchesDeclared':c['definitionMatchesDeclared'],'propertiesAndGeometryMatch':all(x['effectivePropertiesMatch'] and x['geometryMatches'] for x in props['cases'][i]['checks']),'newCachedPinVerified':any(x['packageId']==pkg['objectId'] and x['number']=='1' and x['name']=='CACHE_INPUT' for x in cache['pin']),'connectionSemanticsMatch':connection_digest(definition,obs['objects'])==expected,'artifactSha256':sha256(d/'design.dsn')}
 row['passed']=all(row[k] for k in ('saved','definitionMatchesDeclared','propertiesAndGeometryMatch','newCachedPinVerified','connectionSemanticsMatch'));audit['cases'].append(row)
audit['passed']=all(c['passed'] for c in audit['cases']);audit['notChecked']=['multiunit_and_occurrence','automatic_override_inheritance_policy','all_unrelated_instance_properties_and_geometry','cache_source_qualified_identity','graphics_render','durable_mcp_write_lifecycle','all_failure_windows','DRC']
(root/'combined-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit))
