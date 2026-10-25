import asyncio,copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from mcp import Client
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture import CaptureService
from cadence_mcp.capture_wire import CaptureWireAdds,geometry_union,path_key,connection_digest,expected_definitions
from cadence_mcp.server import create_server
from test_connections import design


def spec():return [{'schematicName':'main','pageName':'page1','reference':'U1','pinNumber':number,
    'connected':number=='1','net':'MCP_NEW' if number=='1' else None} for number in ('1','2')]


class GeometryOracleTests(unittest.TestCase):
    def test_union_accepts_splits_reversal_and_diagonal_primitive_direction(self):
        for old,new in [([[[0,0],[10,0]]],[[[10,0],[5,0]],[[0,0],[5,0]]]),
                        ([[[0,0],[9,6]]],[[[9,6],[3,2]],[[0,0],[3,2]]])]:
            self.assertEqual(geometry_union(old),geometry_union(new))
        self.assertEqual(path_key([[0,0],[5,0]]),path_key([[5,0],[0,0]]))

    def test_union_rejects_parallel_offset_extra_geometry_and_gap(self):
        base=geometry_union([[[0,0],[10,0]]])
        for paths in [[[[0,1],[10,1]]],[[[0,0],[11,0]]],[[[0,0],[4,0]],[[5,0],[10,0]]]]:
            self.assertNotEqual(base,geometry_union(paths))
        with self.assertRaises(CadenceError):geometry_union([[[1,1],[1,1]]])


class WireAddTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);install=self.root/'install'
        (install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        source=self.root/'source.dsn';source.write_bytes(b'mock DSN')
        self.config=Config(install,self.root/'work',(self.root,));self.capture=CaptureService(self.config)
        workspace=self.capture.create_workspace(str(source))
        def read(config,script,args,cwd):Path(args[1]).write_text(json.dumps(design()),encoding='utf-8')
        with patch('cadence_mcp.capture.run_tcl',read):self.sid=self.capture.open(workspace['workspaceId'])['sessionId']
        self.writer=CaptureWireAdds(self.config,self.capture)

    def plan(self,**kwargs):
        values={'session_id':self.sid,'page_id':'p','start':[0,0],'end':[10,0],'name':'MCP_NEW','expectations':spec()}
        values.update(kwargs)
        with patch('cadence_mcp.capture_wire.inventory',return_value=[]):return self.writer.plan(**values)

    def payload(self,plan):return self.writer._load(plan['planId'])[2]['plan']['payload']

    def test_complete_exact_pin_spec_required_and_source_remains_immutable(self):
        before=copy.deepcopy(self.capture.sessions[self.sid]['data']);self.plan()
        self.assertEqual(before,self.capture.sessions[self.sid]['data'])
        for rows in [spec()[:1],spec()+[spec()[0]],[{**row,'pageName':'other'} for row in spec()]]:
            with self.assertRaises(CadenceError):self.plan(expectations=rows)

    def test_geometry_alias_and_scalar_name_preconditions(self):
        for changes in [{'start':[True,0]},{'end':[0,0]},{'alias_location':[5,1]},
                        {'name':'NET[0:7]'},{'name':'x; source bad'},
                        {'expected_paths':[[[0,0],[11,0]]]},{'expected_paths':[[[0,0],[0,0]]]}]:
            with self.assertRaises(CadenceError):self.plan(**changes)

    def test_wrong_page_and_shared_pin_identities_refused(self):
        with self.assertRaises(CadenceError):self.plan(page_id='outside')
        data=self.capture.sessions[self.sid]['data'];extra=copy.deepcopy(data['pin'][0]);extra['objectId']='other-pin';data['pin'].append(extra)
        with self.assertRaises(CadenceError):self.plan()

    def test_expected_paths_allow_declared_split_but_no_added_geometry(self):
        plan=self.plan(expected_paths=[[[0,0],[5,0]],[[5,0],[10,0]]])
        self.assertEqual(len(self.payload(plan)['expectedWirePaths']),2)

    def test_stale_source_and_cancelled_plan_do_not_execute(self):
        plan=self.plan();self.writer.cancel(plan['planId'],plan['planDigest'])
        with self.assertRaises(CadenceError):self.writer.apply(plan['planId'],plan['planDigest'],'key')
        plan=self.plan();payload=self.payload(plan);Path(payload['sourceDesign']).write_bytes(b'changed')
        with self.assertRaises(CadenceError):self.writer.apply(plan['planId'],plan['planDigest'],'another-key')

    def test_independent_verify_rejects_changed_net_or_wire_geometry(self):
        plan=self.plan();payload=self.payload(plan);directory=self.writer._load(plan['planId'])[0]
        (directory/'design.dsn').write_bytes(b'saved mock')
        expected=expected_definitions(self.capture.sessions[self.sid]['data'],'p',spec())
        wire={'kind':'wire','objectId':'new-wire','pageId':'p','attributes':{'net':'MCP_NEW','points':[[0,0],[10,0]]}}
        alias={'kind':'alias','objectId':'new-alias','pageId':'p','attributes':{'wireId':'new-wire','name':'MCP_NEW','location':[0,0]}}
        class Verifier:
            workspaces={}
            def __init__(self,data):self.sessions={'verified':{'data':data}}
            def open(self,key):return {'sessionId':'verified'}
            def close(self,key):pass
        for wrong in ('net','geometry','wire_net'):
            data=copy.deepcopy(expected);objects=copy.deepcopy([wire,alias])
            if wrong=='net':data['pin'][0]['net']='UNEXPECTED'
            elif wrong=='geometry':objects[0]['attributes']['points'][1]=[11,0]
            else:objects[0]['attributes']['net']='WRONG_OWNER_NET'
            with patch('cadence_mcp.capture_wire.CaptureService',return_value=Verifier(data)),patch('cadence_mcp.capture_wire.inventory',return_value=objects):
                with self.assertRaises(CadenceError):self.writer.verify(directory,payload,False)

    def test_semantic_inventory_does_not_use_ordinal_or_native_ids(self):
        data=self.capture.sessions[self.sid]['data']
        obj={'kind':'wire','objectId':'w1','nativeId':1,'pageId':'p','attributes':{'net':'INPUT','points':[[0,0],[10,0]]}}
        renamed={**obj,'objectId':'another-id','nativeId':999}
        self.assertEqual(connection_digest(data,[obj]),connection_digest(data,[renamed]))
        renamed['attributes']={**renamed['attributes'],'points':[[0,0],[11,0]]}
        self.assertNotEqual(connection_digest(data,[obj]),connection_digest(data,[renamed]))

    def test_mcp_strict_arguments_and_pending_job_lifecycle(self):
        async def run():
            with patch('cadence_mcp.server.CaptureService',return_value=self.capture),patch('cadence_mcp.capture_wire.inventory',return_value=[]):
                async with Client(create_server(self.config)) as client:
                    args={'sessionId':self.sid,'pageId':'p','start':[0,0],'end':[10,0],'netName':'MCP_NEW','expectedConnections':spec()}
                    row=await client.call_tool('capture_plan_wire_add',args);self.assertFalse(row.is_error)
                    plan=row.structured_content['data'];keys={k:plan[k] for k in ('planId','planDigest')}
                    self.assertTrue((await client.call_tool('capture_plan_wire_add',{**args,'eval':'bad'})).is_error)
                    self.assertFalse((await client.call_tool('capture_cancel_wire_add',keys)).is_error)
                    self.assertTrue((await client.call_tool('capture_apply_wire_add',{**keys,'idempotencyKey':'key'})).is_error)
                    jobs=await client.call_tool('capture_wire_add_jobs',{});self.assertFalse(jobs.is_error)
                    self.assertEqual(jobs.structured_content['data']['jobs'][0]['state'],'cancelled')
        asyncio.run(run())
