import tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.capture_references import CaptureReferenceEdits
from test_reference_map import definition

class ReferenceScopeTests(unittest.TestCase):
    def test_multunit_drawn_and_external_targets_refused_before_a_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
            config=Config(install,root/'work',(root,));session={'data':definition()}
            capture=SimpleNamespace(lock=threading.RLock(),_session=lambda sid:session)
            writer=CaptureReferenceEdits(config,capture)
            for kind,size,external in [('placed',2,False),('drawn',0,False),('placed',1,True)]:
                units={'a':{'kind':kind,'packageSize':size,'isExternalDesignPart':external}}
                with patch('cadence_mcp.capture_references.read_units',return_value=units),patch('cadence_mcp.capture_references.inventory',return_value=[]):
                    with self.assertRaises(CadenceError) as error:writer.plan('s',[{'partId':'a','newReference':'R201'}])
                self.assertEqual(error.exception.code,'unsupported_reference_scope');self.assertFalse(list(writer.root.glob('plan-*')))
