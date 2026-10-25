import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from pydantic import ValidationError
from cadence_mcp.core import CadenceError,Config
from cadence_mcp.library import LibraryService
from cadence_mcp.library_create import LibraryCreates,validate_spec
from cadence_mcp.server import LibrarySymbolPin
from test_library_create import spec

class EmptyPinNameTests(unittest.TestCase):
 def test_unsupported_empty_literal_is_refused_before_assets_or_durable_plan(self):
  value=spec();value['symbols'][0]['pins'][0]['name']=''
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'install/tcltk/bin').mkdir(parents=True);(root/'install/tcltk/bin/tclsh.exe').touch();config=Config(root/'install',root/'work',(root,),60);creator=LibraryCreates(config,LibraryService(config))
   with patch('cadence_mcp.library_create.creation_assets') as assets,patch.object(creator,'create_plan') as durable:
    with self.assertRaises(CadenceError) as error:creator.plan(value)
    self.assertEqual(error.exception.code,'invalid_library_spec');assets.assert_not_called();durable.assert_not_called()
  with self.assertRaises(ValidationError):LibrarySymbolPin.model_validate(value['symbols'][0]['pins'][0])
 def test_explicit_names_keep_literal_unicode_and_length_boundary(self):
  for name in ('A','中文[x]$;','N'*128,'$PIN0'):
   value=spec();value['symbols'][0]['pins'][0]['name']=name
   self.assertEqual(validate_spec(value),value);self.assertEqual(LibrarySymbolPin.model_validate(value['symbols'][0]['pins'][0]).name,name)
