"""Strict declarative basic library vectors and native field descriptors."""
from typing import Annotated,Literal
from pydantic import BaseModel,ConfigDict,Field,TypeAdapter,model_validator
from .core import CadenceError

Coordinate=Annotated[int,Field(ge=-1000000,le=1000000)]
Point=Annotated[list[Coordinate],Field(min_length=2,max_length=2)]
Bounds=Annotated[list[Coordinate],Field(min_length=4,max_length=4)]
class VectorModel(BaseModel):
 model_config=ConfigDict(extra='forbid',strict=True)
class VectorFont(VectorModel):
 faceName:Annotated[str,Field(min_length=1,max_length=31)]='Arial'
 height:Annotated[int,Field(ge=-2048,le=2048)]=-11
 width:Annotated[int,Field(ge=-2048,le=2048)]=0
 escapement:Annotated[int,Field(ge=-36000,le=36000)]=0
 orientation:Annotated[int,Field(ge=-36000,le=36000)]=0
 weight:Annotated[int,Field(ge=0,le=1000)]=400
 italic:bool=False
 underline:bool=False
 strikeOut:bool=False
 charSet:Annotated[int,Field(ge=0,le=255)]=0
 outPrecision:Annotated[int,Field(ge=0,le=255)]=7
 clipPrecision:Annotated[int,Field(ge=0,le=255)]=0
 quality:Annotated[int,Field(ge=0,le=255)]=1
 pitchAndFamily:Annotated[int,Field(ge=0,le=255)]=16
 @model_validator(mode='after')
 def valid(self):
  if not self.height or any(c in self.faceName for c in '\x00\r\n'):raise ValueError('Use a nonzero height and bounded font face.')
  return self
class BitmapGeometry(VectorModel):
 bounds:Bounds
 location:Point
 expectedDibSha256:Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')]
 @model_validator(mode='after')
 def valid(self):
  check_bounds(self.bounds);return self
class StrokeVector(VectorModel):
 style:Annotated[int,Field(ge=0,le=5)]=0
 width:Annotated[int,Field(ge=0,le=3)]=0
class LineVector(StrokeVector):
 kind:Literal['line']
 start:Point
 end:Point
 @model_validator(mode='after')
 def valid(self):
  if self.start==self.end:raise ValueError('Line endpoints must differ.')
  return self
class AreaVector(StrokeVector):
 kind:Literal['box','ellipse']
 bounds:Bounds
 fill:Annotated[int,Field(ge=0,le=2)]=1
 hatch:Annotated[int,Field(ge=0,le=5)]=0
 @model_validator(mode='after')
 def valid(self):
  check_bounds(self.bounds);return self
class ArcVector(StrokeVector):
 kind:Literal['arc']
 bounds:Bounds
 start:Point
 end:Point
 @model_validator(mode='after')
 def valid(self):
  check_bounds(self.bounds);return self
class PathVector(StrokeVector):
 kind:Literal['polyline','bezier']
 points:Annotated[list[Point],Field(min_length=2,max_length=256)]
class PolygonVector(StrokeVector):
 kind:Literal['polygon']
 points:Annotated[list[Point],Field(min_length=3,max_length=256)]
 fill:Annotated[int,Field(ge=0,le=2)]=1
 hatch:Annotated[int,Field(ge=0,le=5)]=0
 @model_validator(mode='after')
 def valid(self):
  if len({tuple(p) for p in self.points})<3:raise ValueError('Polygon requires three distinct vertices.')
  return self
class FillVector(VectorModel):
 kind:Literal['fill']
 start:Point
 fill:Annotated[int,Field(ge=0,le=2)]=0
 hatch:Annotated[int,Field(ge=0,le=5)]=0
class TextVector(VectorModel):
 kind:Literal['text']
 text:Annotated[str,Field(max_length=4096)]
 bounds:Bounds
 font:VectorFont=Field(default_factory=VectorFont)
 @model_validator(mode='after')
 def valid(self):
  check_bounds(self.bounds)
  if '\x00' in self.text:raise ValueError('Text cannot contain NUL.')
  return self
def check_bounds(v):
 if v[0]>=v[2] or v[1]>=v[3]:raise ValueError('Use ordered, nonempty left/top/right/bottom bounds.')

class BitmapVector(VectorModel):
 kind:Literal['bitmap']
 bounds:Bounds
 location:Point
 sourceBmp:Annotated[str,Field(min_length=1,max_length=4096)]
 expectedBmpSha256:Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')]
 expectedDibSha256:Annotated[str,Field(pattern=r'^[0-9a-f]{64}$')]
 expectedDimensions:Annotated[list[Annotated[int,Field(ge=1,le=4096)]],Field(min_length=2,max_length=2)]
 expectedDibSize:Annotated[int,Field(ge=40,le=16777202)]
 @model_validator(mode='after')
 def valid(self):
  check_bounds(self.bounds)
  if '\x00' in self.sourceBmp:raise ValueError('Invalid BMP path.')
  return self

LibraryVector=Annotated[LineVector|AreaVector|ArcVector|PathVector|PolygonVector|FillVector|TextVector,Field(discriminator='kind')]
VECTOR_ADAPTER=TypeAdapter(LibraryVector)
LibraryCreationVector=Annotated[LineVector|AreaVector|ArcVector|PathVector|PolygonVector|FillVector|TextVector|BitmapVector,Field(discriminator='kind')]
CREATION_VECTOR_ADAPTER=TypeAdapter(LibraryCreationVector)
FONT_KEYS=('faceName','height','width','escapement','orientation','weight','italic','underline','strikeOut','charSet','outPrecision','clipPrecision','quality','pitchAndFamily')
def validate_vectors(rows,allow_bitmaps=False):
 if not isinstance(rows,list) or len(rows)>256:raise CadenceError('invalid_library_vectors','Declare at most256 typed vectors per view.')
 try:
  adapter=CREATION_VECTOR_ADAPTER if allow_bitmaps else VECTOR_ADAPTER
  parsed=[adapter.validate_python(r,strict=True).model_dump() for r in rows]
  if sum(len(v.get('points',[])) for v in parsed)>8192 or sum(len(v.get('text','')) for v in parsed)>16384:raise ValueError('Vector point/text budget exceeded.')
  return parsed
 except ValueError as e:raise CadenceError('invalid_library_vectors','Invalid typed geometry/style/font declaration.') from e
def vector_descriptor(v):
 k=v['kind']
 if k=='bitmap':return [k,v['bounds'],v['location'],v['expectedDimensions'],v['expectedDibSize'],v['expectedDibSha256']]
 if k=='line':return [k,v['start'],v['end'],v['style'],v['width']]
 if k in ('box','ellipse'):return [k,v['bounds'],v['style'],v['width'],v['fill'],v['hatch']]
 if k=='arc':return [k,v['bounds'],v['start'],v['end'],v['style'],v['width']]
 if k in ('polygon','polyline','bezier'):return [k,v['points'],v['style'],v['width']]+([v['fill'],v['hatch']] if k=='polygon' else [])
 if k=='fill':return [k,v['start'],v['fill'],v['hatch']]
 font=[int(v['font'][key]) if isinstance(v['font'][key],bool) else v['font'][key] for key in FONT_KEYS]
 # Native default-font classification is derived; all requested LOGFONT values are compared.
 return [k,v['text'],v['bounds'][:2],v['bounds'],font]
def declared_descriptor(row):
 if not isinstance(row,list) or not row:raise CadenceError('invalid_library_metadata','Malformed vector descriptor.')
 if row[0]=='text':
  if len(row)!=6 or type(row[-1]) is not int or row[-1] not in (0,1):raise CadenceError('invalid_library_metadata','Malformed native text font classification.')
  return row[:-1]
 return row
