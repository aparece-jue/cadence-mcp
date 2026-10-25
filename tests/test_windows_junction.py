import os
from pathlib import Path
import tempfile
import unittest
from cadence_mcp.core import CadenceError,checked_path

@unittest.skipUnless(os.name=='nt','Windows junction test')
class JunctionBoundaryTests(unittest.TestCase):
    def test_directory_junction_cannot_escape_read_root(self):
        import _winapi
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory).resolve();allowed=base/'allowed';outside=base/'outside'
            allowed.mkdir();outside.mkdir();(outside/'design.dsn').write_bytes(b'fixture')
            junction=allowed/'escape'
            _winapi.CreateJunction(str(outside),str(junction))
            try:
                self.assertEqual((junction/'design.dsn').resolve(),outside/'design.dsn')
                with self.assertRaises(CadenceError):checked_path(str(junction/'design.dsn'),(allowed,))
            finally:
                # Remove only the test junction; never recurse into its target.
                junction.rmdir()
