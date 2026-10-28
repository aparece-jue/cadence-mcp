"""Exact linear symbol-boundary/wire contact candidates, never a clearance pass."""
from collections import Counter
from datetime import datetime,timezone
from .core import CadenceError,new_id,sha256,write_json
from .wiring import intersection
from .closed_outline import simple_ring,segment_inside
from .capture_part_vectors import query_part_vectors
from .capture_objects import query_objects

def analyze_symbol_contacts(vectors,wires,part_id,page_id):
    def point(p):return isinstance(p,list) and len(p)==2 and all(type(v) is int and -2147483648<=v<=2147483647 for v in p)
    boundaries=[];segments=[];skipped=[];ids=set();other_pages=0;closed=[];skipped_closed=[];simplicity_pairs=0
    try:
        if not isinstance(vectors,list) or len(vectors)>4096 or not isinstance(wires,list) or len(wires)>10000:raise ValueError('count')
        for row in vectors:
            if row['partId']!=part_id or row['pageId']!=page_id or not isinstance(row['objectId'],str) or not row['objectId'] or row['objectId'] in ids:raise ValueError('vector identity')
            ids.add(row['objectId']);points=row['pageControlPoints'];kind=row['kind']
            if not isinstance(points,list) or any(not point(p) for p in points):raise ValueError('coordinates')
            if kind not in ('line','polyline','polygon','box'):
                skipped.append({'objectId':row['objectId'],'kind':kind,'reason':'not_a_linear_boundary'});continue
            if (kind=='line' and len(points)!=2) or (kind=='box' and len(points)!=4) or (kind in ('polyline','polygon') and not 2<=len(points)<=4096):raise ValueError('linear coverage')
            if kind in ('polygon','box'):
                simplicity_pairs+=len(points)*len(points)
                if simplicity_pairs>1000000:raise CadenceError('geometry_limit','Closed-outline simplicity pair budget exceeded.')
                ring=simple_ring(points)
                if ring is None:skipped_closed.append({'objectId':row['objectId'],'reason':'not_a_simple_nonzero_area_ring'})
                else:closed.append({'vectorId':row['objectId'],'ring':ring})
            path=points+[points[0]] if kind in ('polygon','box') else points
            for index,(a,b) in enumerate(zip(path,path[1:])):
                if a!=b:boundaries.append({'a':a,'b':b,'vectorId':row['objectId'],'vectorSegmentIndex':index})
            if len(boundaries)>2000:raise CadenceError('geometry_limit','At most2000 linear symbol segments are supported.')
        ids=set()
        for row in wires:
            if row['kind']!='wire' or not isinstance(row['objectId'],str) or not row['objectId'] or row['objectId'] in ids:raise ValueError('wire identity')
            ids.add(row['objectId']);points=row['attributes']['points']
            if not isinstance(points,list) or not 2<=len(points)<=10000 or any(not point(p) for p in points):raise ValueError('wire points')
            if row['pageId']!=page_id:other_pages+=1;continue
            for index,(a,b) in enumerate(zip(points,points[1:])):
                if a!=b:segments.append({'a':a,'b':b,'wireId':row['objectId'],'wireSegmentIndex':index})
            if len(segments)>2000:raise CadenceError('geometry_limit','At most2000 page wire segments are supported.')
        if len(segments)*len(boundaries)>1000000:raise CadenceError('geometry_limit','At most1000000 wire/symbol segment pairs are supported.')
    except (KeyError,TypeError,ValueError) as error:raise CadenceError('invalid_worker_result','Invalid bounded symbol/wire geometry.','decode') from error
    findings=[]
    for boundary in boundaries:
        for wire in segments:
            hit=intersection(boundary,wire)
            if hit is None:continue
            if len(findings)>=10000:raise CadenceError('geometry_limit','Too many symbol contact candidates.')
            rule=hit.pop('ruleId');kind={'WIRE-CROSSING-CANDIDATE':'crossing','WIRE-T-CONTACT-CANDIDATE':'t_contact','WIRE-COLLINEAR-OVERLAP':'collinear_overlap'}[rule]
            findings.append({'ruleId':'SYMBOL-WIRE-CONTACT-CANDIDATE','severity':'info','pageId':page_id,'partId':part_id,'vectorId':boundary['vectorId'],'vectorSegmentIndex':boundary['vectorSegmentIndex'],'wireId':wire['wireId'],'wireSegmentIndex':wire['wireSegmentIndex'],'contactKind':kind,**hit,'electricalConnection':'not_evaluated'})
    for outline in closed:
        for wire in segments:
            if not segment_inside(wire['a'],wire['b'],outline['ring']):continue
            if len(findings)>=10000:raise CadenceError('geometry_limit','Too many symbol contact candidates.')
            findings.append({'ruleId':'SYMBOL-WIRE-CONTAINMENT-CANDIDATE','severity':'info','pageId':page_id,'partId':part_id,'vectorId':outline['vectorId'],'vectorSegmentIndex':None,'wireId':wire['wireId'],'wireSegmentIndex':wire['wireSegmentIndex'],'contactKind':'contained_segment','wireStart':wire['a'],'wireEnd':wire['b'],'electricalConnection':'not_evaluated'})
    return {'profile':'symbol-wire-linear-contacts@0.2.0','partId':part_id,'pageId':page_id,'units':'capture_native_integer','linearBoundarySegmentsChecked':len(boundaries),'wireSegmentsChecked':len(segments),'wiresOutsidePageSkipped':other_pages,'findings':findings,'countsByContactKind':dict(Counter(f['contactKind'] for f in findings)),'skippedVectors':skipped,'simpleClosedOutlinesChecked':len(closed),'skippedContainmentOutlines':skipped_closed,'simpleClosedContainmentCoverageComplete':not skipped_closed,'linearBoundaryCoverageComplete':not skipped,'renderedClearanceVerified':False,'electricalConnectivityVerified':False,'designPassed':None,'notChecked':['glyph_and_stroke_bounds','display_property_and_pin_graphics','curves_bitmap_fill_and_nested_geometry','self_intersecting_or_degenerate_outline_containment','shared_endpoints','occurrence_geometry','native_drc']}

def check_symbol_contacts(capture,sid,part_id):
    with capture.lock:
        session=capture._session(sid);vectors=[];cursor=None
        while True:
            page=query_part_vectors(capture,sid,part_id,cursor,1000);vectors+=page['items'];cursor=page['nextCursor']
            if cursor is None:break
        page_id=page['pageId'];wires=[];cursor=None
        while True:
            page=query_objects(capture,sid,'connections','wire',page_id,cursor,1000);wires+=page['items'];cursor=page['nextCursor']
            if cursor is None:break
        capture._session(sid);report=analyze_symbol_contacts(vectors,wires,part_id,page_id)
        artifact_id=new_id('symbol-contacts');destination=session['design'].parent/(artifact_id+'.json')
        report.update(sessionId=sid,revision=session['revision'],pdfRequired=False);write_json(destination,report)
        artifact={'artifactId':artifact_id,'kind':'capture_symbol_contact_report','workspaceRelativePath':destination.name,'sha256':sha256(destination),'size':destination.stat().st_size,'producedByJob':new_id('sync'),'sourceFingerprint':session['revision'],'createdAt':datetime.now(timezone.utc).isoformat(),'validationState':'unverified'}
        return {**report,'artifact':artifact}
