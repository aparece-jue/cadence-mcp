import asyncio
from pathlib import Path
import tempfile
import unittest

from mcp import Client
from cadence_mcp.core import CadenceError, Config, sha256
from cadence_mcp.pspice_output import parse_out, inspect_output
from cadence_mcp.server import create_server

BANNER = '**** 10/23/26 12:00:00 ******* PSpice 24.1.0 ******* ID# 0 ********\n'


class OutputTests(unittest.TestCase):
    def test_bias_scopes_duplicate_nodes_and_unparsed_digital(self):
        text = BANNER + ''' **** INITIAL TRANSIENT SOLUTION TEMPERATURE = 27 DEG C
 NODE VOLTAGE NODE VOLTAGE
( IN) 5.0E+00 ( OUT) 2.5D+00
( DIGITAL) : Z
 VOLTAGE SOURCE CURRENTS
( FAKE) 999
 **** SMALL SIGNAL BIAS SOLUTION TEMPERATURE = 27 DEG C
 NODE VOLTAGE
( OUT) 1.25
 JOB CONCLUDED
'''
        row = parse_out(text)
        self.assertEqual([(v['node'], v['value']) for v in row['biasVoltages']],
                         [('IN', 5), ('OUT', 2.5), ('OUT', 1.25)])
        self.assertEqual(len(row['unparsedBiasRows']), 1)
        self.assertFalse(row['solverSuccessVerified'])
        self.assertFalse(row['jobAssociationVerified'])

    def test_error_after_conclusion_and_repeated_sections_remain_errors(self):
        row = parse_out(BANNER + 'WARNING(ORPSIM-1): test\n JOB CONCLUDED\nERROR(ORPSIM-2): failed\nFATAL: stopped\n')
        self.assertTrue(row['hasErrorDiagnostics'])
        self.assertEqual([r['code'] for r in row['diagnostics']], ['ORPSIM-1', 'ORPSIM-2', None])
        self.assertEqual(len(row['jobConcludedLines']), 1)
        self.assertFalse(row['solverSuccessVerified'])

    def test_partial_numeric_row_never_becomes_valid_data(self):
        row = parse_out(BANNER + ' **** INITIAL TRANSIENT SOLUTION\n NODE VOLTAGE\n( A) 2.5 ( B) ???\n')
        self.assertEqual(row['biasVoltages'], [])
        self.assertEqual(len(row['unparsedBiasRows']), 1)
        with self.assertRaises(CadenceError):
            parse_out(BANNER + ' **** INITIAL TRANSIENT SOLUTION\n NODE VOLTAGE\n( A) 1e999\n')

    def test_reject_unknown_binary_and_oversized_line(self):
        for text in ('JOB CONCLUDED', BANNER + '\x00', BANNER + 'a' * 32769):
            with self.assertRaises(CadenceError): parse_out(text)

    def test_mcp_import_keeps_source_bytes_and_strict_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            install = root / 'install'
            (install / 'tcltk/bin').mkdir(parents=True)
            (install / 'tcltk/bin/tclsh.exe').touch()
            source = root / 'evidence.out'
            source.write_bytes((BANNER + 'ERROR(ORPSIM-1): 中文\n').encode('cp936'))
            config = Config(install, root / 'work', (root,))
            before = sha256(source)
            with self.assertRaises(CadenceError): inspect_output(config, str(source))
            async def exercise():
                async with Client(create_server(config)) as client:
                    result = await client.call_tool('pspice_inspect_output', {'sourceOutput': str(source), 'encoding': 'cp936'})
                    data = result.structured_content['data']
                    self.assertTrue(data['hasErrorDiagnostics'])
                    self.assertEqual(data['diagnostics'][0]['message'], '中文')
                    self.assertFalse(data['jobAssociationVerified'])
                    self.assertEqual(sha256(config.workspace_root / data['inspectionId'] / 'imported.out'), before)
                    self.assertTrue((await client.call_tool('pspice_inspect_output', {
                        'sourceOutput': str(source), 'encoding': 'auto'})).is_error)
            asyncio.run(exercise())
            self.assertEqual(sha256(source), before)
