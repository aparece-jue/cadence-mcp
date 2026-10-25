import copy,hashlib,struct,tempfile,unittest
from pathlib import Path
from cadence_mcp.bitmap_assets import inspect_bmp,freeze_assets,verify_assets
from cadence_mcp.core import Config,CadenceError
from cadence_mcp.library_vectors import validate_vectors,vector_descriptor
from cadence_mcp.library_create import LibraryCreates
from cadence_mcp.library import LibraryService
from test_library_create import spec

def image(bits=24):
    # Independently constructed2x2 bottom-up image: each row is padded to4 bytes.
    pixels=bytes(range(16))
    dib=struct.pack('<IiiHHIIiiII',40,2,2,1,bits,0,16,0,0,0,0)+pixels
    return struct.pack('<2sIHHI',b'BM',14+len(dib),0,0,54)+dib

def declaration(path,blob):
    return {'kind':'bitmap','bounds':[0,0,20,20],'location':[3,4],'sourceBmp':str(path),
      'expectedDimensions':[2,2],'expectedDibSize':56,
      'expectedBmpSha256':hashlib.sha256(blob).hexdigest(),'expectedDibSha256':hashlib.sha256(blob[14:]).hexdigest()}

class BitmapAssetTests(unittest.TestCase):
    def test_independent_rgb24_and_rgb32_headers_and_complete_dib(self):
        for bits in (24,32):
            blob=image(bits);metadata=inspect_bmp(blob)
            self.assertEqual(metadata['expectedDimensions'],[2,2]);self.assertEqual(metadata['expectedDibSize'],56)
            self.assertEqual(metadata['expectedDibSha256'],hashlib.sha256(blob[14:]).hexdigest())
            self.assertEqual(metadata['expectedBmpSha256'],hashlib.sha256(blob).hexdigest())
    def test_reject_bad_headers_truncation_compression_palette_topdown_and_trailing_data(self):
        variants=[image()[:53],image()+b'x',b'xx'+image()[2:]]
        for offset,fmt,value in [(2,'I',71),(6,'H',1),(10,'I',55),(14,'I',108),(18,'i',0),(22,'i',-2),(26,'H',2),(28,'H',8),(30,'I',1),(34,'I',99),(46,'I',1)]:
            blob=bytearray(image());struct.pack_into('<'+fmt,blob,offset,value);variants.append(bytes(blob))
        for blob in variants:
            with self.subTest(blob=blob[:40]),self.assertRaises(CadenceError):inspect_bmp(blob)
    def setup_case(self,root):
        install=root/'install';(install/'tcltk/bin').mkdir(parents=True);(install/'tcltk/bin/tclsh.exe').touch()
        source=root/'sources';source.mkdir();bmp=source/'pattern.bmp';bmp.write_bytes(image())
        cfg=Config(install,root/'work',(source,))
        value=spec();value['symbols'][0]['vectors']=[declaration(bmp,image())]
        return cfg,bmp,value
    def test_freeze_deduplicates_and_original_removal_does_not_change_plan_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg,bmp,value=self.setup_case(Path(tmp));value['symbols'][0]['vectors']*=2
            frozen=freeze_assets(cfg,value)
            self.assertEqual(value['symbols'][0]['vectors'][0]['sourceBmp'],str(bmp))
            paths=[Path(v['sourceBmp']) for v in frozen['symbols'][0]['vectors']]
            self.assertEqual(paths[0],paths[1]);self.assertTrue(paths[0].is_relative_to(cfg.workspace_root))
            self.assertEqual(paths[0].read_bytes(),image());bmp.unlink();verify_assets(cfg,frozen)
    def test_wrong_hash_dimensions_and_size_rejected_before_any_native_worker(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg,_,value=self.setup_case(Path(tmp))
            for key,bad in [('expectedDimensions',[3,2]),('expectedDibSize',55),('expectedDibSha256','b'*64),('expectedBmpSha256','b'*64)]:
                changed=copy.deepcopy(value);changed['symbols'][0]['vectors'][0][key]=bad
                with self.subTest(key=key),self.assertRaises(CadenceError) as caught:freeze_assets(cfg,changed)
                self.assertEqual(caught.exception.code,'bitmap_asset_mismatch')
    def test_root_denial_and_frozen_valid_pixel_tamper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cfg,_,value=self.setup_case(root);outside=root/'outside.bmp';outside.write_bytes(image())
            denied=copy.deepcopy(value);denied['symbols'][0]['vectors'][0]['sourceBmp']=str(outside)
            with self.assertRaises(CadenceError) as caught:freeze_assets(cfg,denied)
            self.assertEqual(caught.exception.code,'path_denied')
            frozen=freeze_assets(cfg,value);path=Path(frozen['symbols'][0]['vectors'][0]['sourceBmp'])
            blob=bytearray(path.read_bytes());blob[-1]^=255;path.write_bytes(blob)
            with self.assertRaises(CadenceError) as caught:verify_assets(cfg,frozen)
            self.assertEqual(caught.exception.code,'bitmap_asset_mismatch')
    def test_create_only_union_and_native_descriptor(self):
        declared=declaration(Path('C:/input.bmp'),image())
        with self.assertRaises(CadenceError):validate_vectors([declared])
        parsed=validate_vectors([declared],allow_bitmaps=True)[0]
        self.assertEqual(vector_descriptor(parsed),['bitmap',[0,0,20,20],[3,4],[2,2],56,declared['expectedDibSha256']])
    def test_durable_creation_plan_asset_tamper_and_original_removal(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg,bmp,value=self.setup_case(Path(tmp));creator=LibraryCreates(cfg,LibraryService(cfg))
            plan=creator.plan(value);_,_,row=creator._load(plan['planId']);payload=row['plan']['payload']
            bmp.unlink();creator.preflight(payload)
            frozen=Path(payload['spec']['symbols'][0]['vectors'][0]['sourceBmp'])
            changed=bytearray(frozen.read_bytes());changed[-1]^=1;frozen.write_bytes(changed)
            with self.assertRaises(CadenceError):creator.preflight(payload)

if __name__=='__main__':unittest.main()
