import asyncio,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from mcp import Client
from cadence_mcp.core import CadenceError,Config
from cadence_mcp.server import create_server,packed
from cadence_mcp.validated_profile import TOOLS,guard,protect

class ReleaseGuards(unittest.TestCase):
 def test_wire_backend_required_and_endpoint_path_excluded(self):
  for name,args in [('capture_plan_wire_add',{}),('capture_plan_wire_edit',dict(guiSessionId='g',hostProject='h',operation='set_endpoints'))]:
   with self.subTest(name=name),self.assertRaises(CadenceError):guard(name,args,{})
 def test_legacy_tasks_refused_before_apply_recover_or_open(self):
  task=SimpleNamespace(_load=lambda _: (None,None,{'plan':{'payload':{'operation':'delete'}}}))
  for name,args in [('capture_apply_wire_add',{'planId':'p'}),('capture_recover_wire_edit',{'planId':'p'}),('capture_open_edit_result',{'planId':'p','kind':'wire_edit'})]:
   with self.subTest(name=name),self.assertRaises(CadenceError):guard(name,args,dict(wire_add=task,wire_edit=task))
 def test_unsupported_backend_kind_and_gui_note_access_refused(self):
  for name,args in [('pspice_open_run_dat',{'backend':'cli'}),('pspice_inspect_run_failure',{'kind':'measurement'}),('capture_gui_attach',{'access':'write'}),('capture_open_edit_result',{'kind':'placement'})]:
   with self.subTest(name=name),self.assertRaises(CadenceError):guard(name,args,{})
 def test_supported_native_delete_and_engine_remain_available(self):
  task=SimpleNamespace(_load=lambda _: (None,None,{'plan':{'payload':{'operation':'delete','editorHost':{'pid':123}}}}))
  guard('capture_apply_wire_edit',{'planId':'p'},dict(wire_edit=task));guard('pspice_open_run_dat',{'backend':'engine'},{});guard('capture_plan_wire_add',{'guiSessionId':'g','hostProject':'h'},{} )
 def test_direct_wrapper_cannot_bypass_guard_via_omitted_defaults(self):
  calls=[]
  async def capture_plan_wire_add(guiSessionId=None,hostProject=None):calls.append(True)
  result=asyncio.run(protect(capture_plan_wire_add,{},packed)())
  self.assertTrue(result.is_error);self.assertFalse(calls)

class ReleaseRegistration(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);r=Path(self.temp.name);install=r/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch();self.config=Config(install,r/'work',(r,))
 async def test_manifest_matches_actual_surface_and_development_stays_expanded(self):
  async with Client(create_server(self.config,profile='validated'),mode='legacy') as client:
   names={t.name for t in (await client.list_tools()).tools};self.assertEqual(names,TOOLS)
   caps=(await client.call_tool('cadence_get_capabilities',{})).structured_content['data'];self.assertEqual(set(caps['tools']),TOOLS);self.assertFalse(caps['fullProjectComplete']);self.assertNotIn('pspice.cli_run',caps['features'])
  async with Client(create_server(self.config),mode='legacy') as client:self.assertEqual(len((await client.list_tools()).tools),223)
 async def test_schema_requires_editor_host_and_limits_operation_and_backends(self):
  async with Client(create_server(self.config,profile='validated'),mode='legacy') as client:
   tools={t.name:t for t in (await client.list_tools()).tools}
   for name in ('capture_plan_wire_add','capture_plan_wire_edit'):
    schema=tools[name].input_schema;self.assertTrue({'guiSessionId','hostProject'}<=set(schema['required']))
   self.assertEqual(tools['capture_plan_wire_edit'].input_schema['properties']['operation']['const'],'delete')
   self.assertEqual(tools['pspice_open_run_dat'].input_schema['properties']['backend']['const'],'engine')
   self.assertNotIn('capture_plan_placement',tools);self.assertNotIn('pspice_dat_digital_samples',tools)
 async def test_schema_refuses_excluded_branch_before_native_method(self):
  async with Client(create_server(self.config,profile='validated'),mode='legacy') as client:
   with patch('cadence_mcp.pspice_cli_runs.PSpiceCliRuns.open_dat',side_effect=AssertionError('must not run')):
    result=await client.call_tool('pspice_open_run_dat',dict(planId='p',planDigest='d',backend='cli'));self.assertTrue(result.is_error)
 async def test_unknown_profile_refused(self):
  with self.assertRaises(ValueError):create_server(self.config,profile='all-validated')

if __name__=='__main__':unittest.main()
