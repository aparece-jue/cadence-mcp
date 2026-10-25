"""Audit frozen expected vs observed records; never repair or replay a design."""
import argparse,json
from pathlib import Path
from cadence_mcp.cache_semantics import effective_property_snapshot
from cadence_mcp.core import sha256
p=argparse.ArgumentParser();p.add_argument('--fixture-root',type=Path,required=True);a=p.parse_args();root=a.fixture_root.resolve(strict=True)
reportfile=root/'report.json';initial=sha256(reportfile);report=json.loads(reportfile.read_text());audit={'passed':False,'originalReportPassed':report['passed'],'mutationReplayed':False,'cases':[]}
for c in report['cases']:
 d=root/(c['selector']+'-'+str(c['update']));out=d/'design.dsn';expectedfile=d/'expected-details.json';hashes={str(p.relative_to(root)):sha256(p) for p in (out,expectedfile,reportfile)}
 frozen=json.loads(expectedfile.read_text());checks=[]
 for part in c['details']:
  expected=frozen[part['partId']]
  assert expected==part['expected']
  actual_geometry=json.loads((d/('geometry-'+str(len(checks))+'.json')).read_text())
  actual_props=json.loads((d/('properties-'+str(len(checks))+'.json')).read_text())
  assert actual_geometry==part['after']['geometry'] and actual_props==part['after']['properties']
  checks.append({'partId':part['partId'],'geometryMatches':actual_geometry==expected['geometry'],'effectivePropertiesMatch':effective_property_snapshot(actual_props)==effective_property_snapshot(expected['properties']),'rawOrderEqual':actual_props==expected['properties']})
 row={'update':c['update'],'checks':checks,'definitionMatchesDeclared':c['definitionMatchesDeclared'],'cacheHasNewPin':c['cacheHasNewPin'],'filesUnchanged':all(sha256(root/k)==v for k,v in hashes.items()),'hashes':hashes}
 row['passed']=row['filesUnchanged'] and row['definitionMatchesDeclared'] and row['cacheHasNewPin'] and c['sourceUnchanged'] and all(p['geometryMatches'] and p['effectivePropertiesMatch'] for p in checks);audit['cases'].append(row)
audit['originalReportUnchanged']=sha256(reportfile)==initial;audit['passed']=audit['originalReportUnchanged'] and all(c['passed'] for c in audit['cases'])
(root/'property-order-audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8');print(json.dumps(audit))
