import copy,json,tempfile,threading,unittest
from pathlib import Path
from cadence_mcp.core import Config,CadenceError,sha256
from cadence_mcp.capture_pspice_project import describe_project,parse_project,freeze_project,validate_snapshot,stage_snapshot

PROJECT='''(ExpressProject "demo"
 (ProjectVersion "19981106") (ProjectType "Analog or A/D Mixed Mode")
 (Folder "Design Resources" (Folder "Library") (File ".\\demo.dsn" (Type "Schematic Design")))
 (Folder "Outputs" (File ".\\demo-PSpiceFiles\\ROOT\\ROOT.net" (Type "Report")))
 (Folder "PSpice Resources" (Folder "Simulation Profiles"
 (File.PSpice.{09528990-3187-11D2-BC7B-00A0C90CBF91} ".\\demo-PSpiceFiles\\ROOT\\AC.sim" (Type "PSpice Profile"))
 (ActiveProfile ".\\demo-PSpiceFiles\\ROOT\\AC.sim"))
 (Folder "Model Libraries" (Sort User)) (Folder "Stimulus Files") (Folder "Include Files"))
 (GlobalState (Doc (Path "D:/real/project.dsn") (Schematic "ROOT")))
)'''
PROFILE='''@OrCAD Simulation Server Version: 1.0
@Settings: 2 1
@General:
ProfileName= "AC"
ProfileFile= "AC.sim"
Connectivity= "ROOT.net"
NetlistFile= "AC.cir"
DataFile= "AC.dat"
OutFile= "AC.out"
Notes=
@#$BEGINNOTES
@#$ENDNOTES
@End General
@Analysis: 1 1
+0 "100"
+1 "0.1"
+2 "200"
@End Analysis
'''
class ProjectSnapshotTests(unittest.TestCase):
 def describe(self,project=PROJECT,profile=PROFILE):return describe_project(project.encode(),profile.encode(),'demo.opj')
 def fixture(self):
  tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);root=Path(tmp.name);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();src=root/'source';src.mkdir();project=src/'demo.opj';project.write_text(PROJECT);profile=src/'demo-PSpiceFiles/ROOT/AC.sim';profile.parent.mkdir(parents=True);profile.write_text(PROFILE);work=root/'work';work.mkdir();design=work/'design.dsn';design.write_bytes(b'owned DSN snapshot');config=Config(install,work,(src,))
  class Capture:
   lock=threading.RLock()
   def _session(self,sid):
    if sid!='s':raise CadenceError('session_lost','closed')
    return {'design':design,'revision':sha256(design),'data':{'schematic':[{'name':'ROOT'}]}}
  capture=Capture();snapshot=freeze_project(config,capture,'s',str(project),str(profile));return config,capture,snapshot,project,profile
 def test_roles_preserve_resource_bytes_but_remove_ui_restoration(self):
  d,staged=self.describe();self.assertEqual(d['designTarget'],'demo.dsn');self.assertEqual(d['profileTarget'],'demo-PSpiceFiles/ROOT/AC.sim');self.assertEqual(d['aliasesTarget'],'demo-PSpiceFiles/ROOT/ROOT.als');self.assertEqual(d['circuitTarget'],'demo-PSpiceFiles/ROOT/AC/AC.cir');self.assertNotIn(b'GlobalState',staged);self.assertNotIn(b'D:/real',staged);self.assertIn(b'(ProjectVersion "19981106")',staged);parse_project(staged.decode())
 def test_nested_quoted_parentheses_are_data_not_tree_nodes(self):
  project=PROJECT.replace('D:/real/project.dsn','D:/real/(project).dsn');d,staged=self.describe(project);self.assertNotIn(b'(project)',staged)
 def test_ui_state_absence_and_utf8_bom_are_deterministic(self):
  first=self.describe()[1];d,second=describe_project(b'\xef\xbb\xbf'+first,PROFILE.encode(),'demo.opj');self.assertEqual(first,second)
 def test_ambiguous_or_foreign_design_and_profile_refused(self):
  for text in [PROJECT.replace('demo.dsn','../demo.dsn'),PROJECT.replace('demo.dsn','other.dsn'),PROJECT.replace('(Type "Schematic Design")','(Type "Library")'),PROJECT.replace('(ActiveProfile ".\\demo-PSpiceFiles\\ROOT\\AC.sim")','(ActiveProfile "other.sim")'),PROJECT.replace('(Folder "Library")','(Folder "Library" (File "x.olb" (Type "Library")))')]:
   with self.subTest(text=text),self.assertRaises(CadenceError):self.describe(text)
 def test_profile_root_name_outputs_and_duplicates_refused(self):
  for profile in [PROFILE.replace('ROOT.net','OTHER.net'),PROFILE.replace('AC.cir','../AC.cir'),PROFILE.replace('AC.dat','foreign.dat'),PROFILE.replace('ProfileName= "AC"','ProfileName= "AC"\nProfileName= "AC"'),PROFILE.replace('@End General','@End General\n@General:\n@End General')]:
   with self.subTest(profile=profile),self.assertRaises(CadenceError):self.describe(profile=profile)
 def test_absolute_unc_traversal_reserved_and_empty_path_parts_refused(self):
  for target in ['C:/outside/demo.dsn','//server/demo.dsn','../demo.dsn','sub//demo.dsn','CON.dsn','demo.dsn ','.\\..\\demo.dsn']:
   with self.subTest(target=target),self.assertRaises(CadenceError):self.describe(PROJECT.replace('.\\demo.dsn',target))
 def test_unknown_project_nodes_and_duplicate_global_state_refused(self):
  for text in [PROJECT.replace('(ProjectVersion','(Path "D:/outside/foreign.dsn") (ProjectVersion'),PROJECT.replace('(ProjectVersion','(StartupScript "evil.tcl") (ProjectVersion'),PROJECT.replace('(GlobalState','(GlobalState) (GlobalState'),PROJECT.replace('09528990-3187-11D2-BC7B-00A0C90CBF91','00000000-0000-0000-0000-000000000000')]:
   with self.assertRaises(CadenceError):self.describe(text)
 def test_duplicate_report_and_invalid_snapshot_rows_refused(self):
  extra='(File ".\\demo-PSpiceFiles\\ROOT\\ROOT.net" (Type "Report"))'
  with self.assertRaises(CadenceError):self.describe(PROJECT.replace('(Folder "Outputs"','(Folder "Outputs" '+extra))
  config,capture,snapshot,project,profile=self.fixture();snapshot['sources']=[None]
  with self.assertRaises(CadenceError):validate_snapshot(config,snapshot)
 def test_malformed_unbounded_and_non_utf8_inputs_refused(self):
  for text in ['','()','("ExpressProject" "demo")',PROJECT+')',PROJECT[:-1],PROJECT.replace('"demo"','"demo'), '\x00'+PROJECT, '(' * 66+'x'+')'*66]:
   with self.subTest(text=text[:20]),self.assertRaises(CadenceError):self.describe(text)
  with self.assertRaises(CadenceError):describe_project(b'\xff',PROFILE.encode(),'demo.opj')
  with self.assertRaises(CadenceError):self.describe(PROJECT+' '*1048576)
 def test_stage_copies_session_design_not_template_and_preserves_sources(self):
  config,capture,snapshot,project,profile=self.fixture();original={p:sha256(p) for p in [project,profile]};(project.parent/'demo.dsn').write_bytes(b'old project template design');job=config.workspace_root/'job';job.mkdir();paths=stage_snapshot(config,snapshot,job);self.assertEqual(Path(paths['design']).read_bytes(),b'owned DSN snapshot');self.assertNotIn('D:/real',Path(paths['project']).read_text());self.assertEqual(Path(paths['profile']).read_text(),PROFILE);self.assertEqual(original,{p:sha256(p) for p in original});self.assertEqual((project.parent/'demo.dsn').read_bytes(),b'old project template design')
 def test_source_change_and_snapshot_role_tampering_refused(self):
  config,capture,snapshot,project,profile=self.fixture();changed=copy.deepcopy(snapshot);changed['description']['designTarget']='../outside.dsn'
  with self.assertRaises(CadenceError):validate_snapshot(config,changed)
  profile.write_text(PROFILE+'\nchanged')
  with self.assertRaises(CadenceError) as c:validate_snapshot(config,snapshot)
  self.assertEqual(c.exception.code,'source_changed')
 def test_closed_session_wrong_root_and_profile_mismatch_refused(self):
  config,capture,snapshot,project,profile=self.fixture()
  with self.assertRaises(CadenceError):freeze_project(config,capture,'closed',str(project),str(profile))
  other=profile.parent/'other.sim';other.write_text(PROFILE)
  with self.assertRaises(CadenceError):freeze_project(config,capture,'s',str(project),str(other))
  capture._session=lambda sid:{'design':Path(snapshot['sources'][0]['path']),'revision':snapshot['sources'][0]['sha256'],'data':{'schematic':[{'name':'OTHER'}]}}
  with self.assertRaises(CadenceError):freeze_project(config,capture,'s',str(project),str(profile))
 def test_stage_does_not_merge_existing_project_or_escape_workspace(self):
  config,capture,snapshot,project,profile=self.fixture();job=config.workspace_root/'job';job.mkdir();(job/'project').mkdir();marker=job/'project/keep';marker.write_bytes(b'keep')
  with self.assertRaises(CadenceError) as c:stage_snapshot(config,snapshot,job)
  self.assertEqual(c.exception.code,'preexisting_native_input');self.assertEqual(marker.read_bytes(),b'keep')
  with self.assertRaises(CadenceError):stage_snapshot(config,snapshot,project.parent)
if __name__=='__main__':unittest.main()
