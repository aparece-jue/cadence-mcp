"""Strict BMP assets for declared Capture library creation; no native decoding here."""
import copy
import hashlib
import struct
from pathlib import Path

from .core import CadenceError, checked_path, new_id, write_json

MAX_BMP_BYTES = 16 * 1024 * 1024


def inspect_bmp(blob):
    """Accept exact bottom-up BI_RGB24/32 BITMAPINFOHEADER files only."""
    if not isinstance(blob,bytes) or not 54 <= len(blob) <= MAX_BMP_BYTES:
        raise CadenceError('invalid_bitmap_asset','BMP size is outside the supported bounds.')
    signature,size,reserved1,reserved2,offset=struct.unpack_from('<2sIHHI',blob)
    header,width,height,planes,bits,compression,image_size,_,_,colors,important=struct.unpack_from('<IiiHHIIiiII',blob,14)
    stride=((width*bits+31)//32)*4 if width>0 else 0
    if (signature!=b'BM' or size!=len(blob) or reserved1 or reserved2 or offset!=54
        or header!=40 or not 1<=width<=4096 or not 1<=height<=4096 or planes!=1
        or bits not in (24,32) or compression!=0 or colors or important
        or image_size not in (0,stride*height) or len(blob)!=54+stride*height):
        raise CadenceError('unsupported_bitmap_asset','Use an exact bottom-up uncompressed RGB24/RGB32 BMP without palette, extra headers or trailing bytes.')
    return {'expectedDimensions':[width,height],'expectedDibSize':len(blob)-14,
            'expectedDibSha256':hashlib.sha256(blob[14:]).hexdigest(),
            'expectedBmpSha256':hashlib.sha256(blob).hexdigest()}


def read_asset(path):
    if not path.is_file() or path.suffix.lower()!='.bmp' or path.stat().st_size>MAX_BMP_BYTES:
        raise CadenceError('invalid_bitmap_asset','Asset must be a bounded BMP file.')
    with path.open('rb') as stream:
        blob=stream.read(MAX_BMP_BYTES+1)
    return blob,inspect_bmp(blob)


def bitmap_rows(spec):
    return [v for s in spec['symbols'] for v in s.get('vectors',[]) if v['kind']=='bitmap']


def matches_declaration(vector,metadata):
    if any(vector[key]!=value for key,value in metadata.items()):
        raise CadenceError('bitmap_asset_mismatch','BMP bytes or metadata differ from the independent declaration.')


def freeze_assets(config,spec):
    spec=copy.deepcopy(spec);vectors=bitmap_rows(spec)
    if not vectors:return spec
    if len(vectors)>32:raise CadenceError('bitmap_asset_limit','At most32 bitmap declarations per plan.')
    # The complete graph reader repeats shared views for each declared device scope.
    native_bytes=sum(v['expectedDibSize'] for s in spec['symbols'] for v in s.get('vectors',[]) if v['kind']=='bitmap'
                     for d in spec['devices'] if d['cellName']==s['cellName'])
    if native_bytes>64*1024*1024:raise CadenceError('bitmap_asset_limit','Complete native graph exceeds the DIB read budget.')
    loaded={};sources=[]
    for vector in vectors:
        source=checked_path(vector['sourceBmp'],config.read_roots)
        sources.append(source)
        if source not in loaded:loaded[source]=read_asset(source)
        matches_declaration(vector,loaded[source][1])
    directory=config.workspace_root/new_id('bitmap-assets');directory.mkdir()
    directory=checked_path(str(directory),(config.workspace_root,))
    records=[];copied={}
    for source,(blob,metadata) in loaded.items():
        target=directory/(metadata['expectedBmpSha256']+'.bmp')
        if target not in copied:
            with target.open('xb') as stream:stream.write(blob)
            copied[target]=True
            _,check=read_asset(target)
            if check!=metadata:raise CadenceError('target_changed','Frozen BMP changed while copying.')
        records.append({'sourcePath':str(source),'frozenPath':str(target),**metadata})
    for vector,source in zip(vectors,sources):
        vector['sourceBmp']=str(directory/(loaded[source][1]['expectedBmpSha256']+'.bmp'))
    write_json(directory/'manifest.json',{'sourceKind':'declared_bitmap_assets','assets':records})
    return spec


def verify_assets(config,spec):
    for vector in bitmap_rows(spec):
        path=checked_path(vector['sourceBmp'],(config.workspace_root,))
        _,metadata=read_asset(path)
        matches_declaration(vector,metadata)
