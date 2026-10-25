"""Bounded exact linear geometry checks; never infer electrical connectivity."""
from collections import Counter
from fractions import Fraction
from .core import CadenceError

def grid_options(size,origin):
    if size is None:
        if origin is not None:raise CadenceError('invalid_grid','A grid origin requires an explicit grid size.')
        return None
    if type(size) is not int or not 1<=size<=1000000:raise CadenceError('invalid_grid','Grid size must be an integer from 1 to 1000000 native units.')
    origin=[0,0] if origin is None else origin
    if not isinstance(origin,list) or len(origin)!=2 or any(type(v) is not int or not -2147483648<=v<=2147483647 for v in origin):raise CadenceError('invalid_grid','Grid origin must contain two native integer coordinates.')
    return {'size':size,'origin':origin[:]}

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def subtract(a,b):return (a[0]-b[0],a[1]-b[1])
def intersection(first,second):
    a,b,c,d=first['a'],first['b'],second['a'],second['b']
    r,s=subtract(b,a),subtract(d,c);den=cross(r,s);ca=subtract(c,a)
    if den==0:
        if cross(ca,r)!=0:return None
        axis=0 if r[0] else 1
        lo=max(min(a[axis],b[axis]),min(c[axis],d[axis]));hi=min(max(a[axis],b[axis]),max(c[axis],d[axis]))
        if lo>=hi:return None
        points=(a,b,c,d)
        return {'ruleId':'WIRE-COLLINEAR-OVERLAP','start':next(p for p in points if p[axis]==lo),
                'end':next(p for p in points if p[axis]==hi)}
    t,u=Fraction(cross(ca,s),den),Fraction(cross(ca,r),den)
    if not (0<=t<=1 and 0<=u<=1):return None
    end_first=t in (0,1);end_second=u in (0,1)
    if end_first and end_second:return None
    p=[Fraction(a[i])+t*r[i] for i in range(2)]
    coordinates={'point':[int(v) for v in p]} if all(v.denominator==1 for v in p) else {
        'point':None,'pointExact':[{'numerator':v.numerator,'denominator':v.denominator} for v in p]}
    return {'ruleId':'WIRE-T-CONTACT-CANDIDATE' if end_first or end_second else 'WIRE-CROSSING-CANDIDATE',**coordinates}

def analyze_wiring(data:dict,grid_size=None,grid_origin=None)->dict:
    grid=grid_options(grid_size,grid_origin);findings=[];segments=[];ids=set();vertices=0
    def emit(row):
        if len(findings)>=10000:raise CadenceError('geometry_limit','Too many geometry findings; inspect a smaller design.')
        findings.append(row)
    try:
        if not isinstance(data,dict) or set(data)!={'schematic','page','wire'} or not isinstance(data['page'],list) or not isinstance(data['wire'],list):raise ValueError()
        page_ids=[p['objectId'] for p in data['page']]
        if any(not isinstance(p,str) for p in page_ids) or len(set(page_ids))!=len(page_ids) or len(data['wire'])>10000:raise ValueError()
        pages=set(page_ids)
        for wire in data['wire']:
            oid,page,points=wire['objectId'],wire['pageId'],wire['points']
            if not isinstance(oid,str) or not oid or oid in ids or page not in pages or not isinstance(wire['net'],str) or not isinstance(points,list) or not 2<=len(points)<=10000:raise ValueError()
            ids.add(oid);vertices+=len(points)
            if vertices>10000:raise CadenceError('geometry_limit','At most 10000 wire vertices are supported.')
            for i,point in enumerate(points):
                if not isinstance(point,list) or len(point)!=2 or any(type(v) is not int or not -2147483648<=v<=2147483647 for v in point):raise ValueError()
                if grid and any((point[j]-grid['origin'][j])%grid['size'] for j in (0,1)):
                    emit({'ruleId':'WIRE-OFF-GRID-VERTEX','severity':'warning','pageId':page,'objects':[{'objectId':oid,'vertexIndex':i}],'point':point})
            for i,(a,b) in enumerate(zip(points,points[1:])):
                ref={'objectId':oid,'segmentIndex':i}
                if a==b:
                    emit({'ruleId':'WIRE-ZERO-LENGTH','severity':'warning','pageId':page,'objects':[ref],'point':a});continue
                segments.append({'ref':ref,'page':page,'a':a,'b':b})
                if len(segments)>2000:raise CadenceError('geometry_limit','At most 2000 segments are supported.')
                if a[0]!=b[0] and a[1]!=b[1]:emit({'ruleId':'WIRE-NON-ORTHOGONAL','severity':'warning','pageId':page,'objects':[ref],'start':a,'end':b})
    except (KeyError,TypeError,ValueError) as error:raise CadenceError('invalid_worker_result','Invalid wire geometry document.','decode') from error
    for i,first in enumerate(segments):
        for second in segments[i+1:]:
            if first['page']!=second['page']:continue
            a,b,c,d=first['a'],first['b'],second['a'],second['b']
            if any(max(min(a[j],b[j]),min(c[j],d[j]))>min(max(a[j],b[j]),max(c[j],d[j])) for j in (0,1)):continue
            finding=intersection(first,second)
            if finding:emit({'severity':'info','pageId':first['page'],'objects':[first['ref'],second['ref']],
                             'electricalConnection':'not_evaluated',**finding})
    return {'scope':'design_definitions','units':'capture_native_integer','wireCount':len(ids),'segmentCount':len(segments),
            'vertexCount':vertices,'findings':findings,'countsByRule':dict(Counter(f['ruleId'] for f in findings)),
            'geometryComplete':True,'geometryCoverage':'bounded_linear_wire_intersections','grid':grid,
            'electricalConnectivityVerified':False,'designPassed':None,'profile':'wire-geometry-advisory@0.2.0',
            'notChecked':['junction_semantics','bus_and_bundle_semantics','occurrence_connectivity','pin_connectivity',
                          'symbol_text_clearance','native_drc']+(['grid_alignment'] if grid is None else [])}
