"""Canonical native page-net memberships; no grouping by label text."""
from collections import defaultdict
import json
from .core import CadenceError, new_id
from .environment import run_tcl

def page_partition(rows,renamed_wire=None,expected_name=None):
    from .capture_wire import point, path_key

    if not isinstance(rows,list) or len(rows)>100000:raise CadenceError('invalid_page_partition','Invalid bounded native net records.')
    keys=set();groups={};unbound=[];selected=[]
    for r in rows:
        common={'kind','schematicName','pageName','group','netName'}
        if not isinstance(r,dict) or r.get('kind') not in ('pin','wire'):raise CadenceError('invalid_page_partition','Invalid native row kind.')
        fields=common|({'reference','number','name'} if r['kind']=='pin' else {'nativeId','points'})
        if set(r)!=fields or any(type(r[k]) is not str or '\x00' in r[k] or len(r[k])>1024 for k in ('schematicName','pageName','netName')):raise CadenceError('invalid_page_partition','Invalid native net record fields.')
        scope=(r['schematicName'],r['pageName'])
        if r['kind']=='pin':
            if any(type(r[k]) is not str or '\x00' in r[k] or len(r[k])>512 for k in ('reference','number','name')):raise CadenceError('invalid_page_partition','Invalid pin key.')
            identity=['pin',*scope,r['reference'],r['number'],r['name']]
        else:
            if type(r['nativeId']) is not int or not isinstance(r['points'],list) or not 2<=len(r['points'])<=256 or any(not point(p) for p in r['points']):raise CadenceError('invalid_page_partition','Invalid wire key.')
            identity=['wire',*scope,path_key(r['points'])]
        key=json.dumps(identity,ensure_ascii=False,separators=(',',':'))
        if key in keys:raise CadenceError('ambiguous_page_partition','Repeated native pin/wire semantic identity.')
        keys.add(key)
        if r['group'] is None:
            if r['kind']=='wire' or r['netName']!='':raise CadenceError('invalid_page_partition','Invalid unbound metadata.')
            unbound.append(key);continue
        if type(r['group']) is not str or not r['group']:raise CadenceError('invalid_page_partition','Invalid native group.')
        g=(*scope,r['group'])
        group=groups.setdefault(g,{'name':r['netName'],'members':[]})
        if group['name']!=r['netName']:raise CadenceError('invalid_page_partition','Inconsistent native group name.')
        group['members'].append(key)
        if r['kind']=='wire' and renamed_wire and (scope[0],scope[1],r['nativeId'])==tuple(renamed_wire):selected.append(g)
    if renamed_wire and len(selected)!=1:raise CadenceError('ambiguous_page_partition','Target native wire group is not unique.')
    result=[]
    for g,row in groups.items():
        if g in selected:
            if expected_name is not None and row['name']!=expected_name:raise CadenceError('alias_owner_name_mismatch','Edited alias wire name differs from explicit expectation.')
            name='__TARGET_NATIVE_NAME__'
        else:name=row['name']
        result.append({'name':name,'members':sorted(row['members'])})
    return {'groups':sorted(result,key=lambda row:json.dumps(row,sort_keys=True,ensure_ascii=False)),'unbound':sorted(unbound)}

def native_partition(capture, sid):
    session = capture._session(sid)
    directory = capture._workspace(session["workspaceId"])["directory"]
    output = directory / (new_id("page-partition") + ".json")
    run_tcl(capture.config, "inspect_page_net_partition.tcl", [str(session["design"]), str(output)], directory)
    capture._session(sid)
    if output.stat().st_size > 32 * 1024 * 1024:
        raise CadenceError("output_limit", "Native page net evidence exceeds limit.")
    rows = json.loads(output.read_text(encoding="utf-8"))
    page_partition(rows)
    output.unlink()
    return rows


def include_net_groups(payload, groups):
    """Require an exact partition of every saved wire and every connected pin."""
    from .capture_wire import path_key, paths_valid

    if groups is None:
        return
    wire_paths = payload["expectedWirePaths"]
    pin_expectations = payload["expectedConnections"]
    if not paths_valid(wire_paths) or any(len(path) > 256 for path in wire_paths):
        raise CadenceError("invalid_wire_geometry", "Saved wire paths exceed the bounds of native page net verification.")
    if len({path_key(path) for path in wire_paths}) != len(wire_paths):
        raise CadenceError("ambiguous_page_partition", "Coincident saved wire paths cannot be uniquely bound.")
    if not isinstance(groups, list) or len(groups) > len(wire_paths) + len(pin_expectations):
        raise CadenceError("invalid_page_net_groups", "Provide a bounded list of native groups.")
    expected_wires = set(range(len(wire_paths)))
    expected_pins = {index for index, pin in enumerate(pin_expectations) if pin["connected"]}
    wire_indexes, pin_indexes = set(), set()
    for group in groups:
        if not isinstance(group, dict) or group.keys() != {"wireIndexes", "pinIndexes"}:
            raise CadenceError("invalid_page_net_groups", "Every group must declare wireIndexes and pinIndexes.")
        if not (group["wireIndexes"] or group["pinIndexes"]):
            raise CadenceError("invalid_page_net_groups", "Empty native groups are not meaningful.")
        for name, seen, expected in (("wireIndexes", wire_indexes, expected_wires),
                                     ("pinIndexes", pin_indexes, expected_pins)):
            indexes = group[name]
            if not isinstance(indexes, list) or len(indexes) > len(expected):
                raise CadenceError("invalid_page_net_groups", "Invalid native group index list.")
            for index in indexes:
                if type(index) is not int or index not in expected or index in seen:
                    raise CadenceError("invalid_page_net_groups", "A member is unknown, duplicated or an unbound pin.")
                seen.add(index)
    if wire_indexes != expected_wires or pin_indexes != expected_pins:
        raise CadenceError("incomplete_page_net_groups", "Declare every saved wire and connected pin exactly once.")
    payload["expectedPageNetGroups"] = groups


def verify_net_groups(rows, payload):
    """Compare membership by native object token, independent of net name and ordinal."""
    from .capture_wire import path_key

    paths = {path_key(path): index for index, path in enumerate(payload["expectedWirePaths"])}
    pins = {(pin["reference"], pin["pinNumber"]): (index, pin["connected"])
            for index, pin in enumerate(payload["expectedConnections"])}
    scope = (payload["schematicName"], payload["pageName"])
    actual = defaultdict(list)
    seen_wires, seen_pins = set(), set()
    for row in rows:
        if (row["schematicName"], row["pageName"]) != scope:
            continue
        if row["kind"] == "wire":
            index = paths.get(path_key(row["points"]))
            if index is None or index in seen_wires or row["group"] is None:
                raise CadenceError("wire_page_partition_mismatch", "Saved wire membership cannot be bound uniquely.", "verify")
            seen_wires.add(index)
            actual[row["group"]].append(("wire", index))
        else:
            expected = pins.get((row["reference"], row["number"]))
            if expected is None or expected[0] in seen_pins or (row["group"] is not None) != expected[1]:
                raise CadenceError("wire_page_partition_mismatch", "Saved pin membership differs from the declaration.", "verify")
            index, connected = expected
            seen_pins.add(index)
            if connected:
                actual[row["group"]].append(("pin", index))
    expected_groups = [sorted([("wire", index) for index in group["wireIndexes"]]
                              + [("pin", index) for index in group["pinIndexes"]])
                       for group in payload["expectedPageNetGroups"]]
    if (len(seen_wires) != len(paths) or len(seen_pins) != len(pins)
            or sorted(sorted(group) for group in actual.values()) != sorted(expected_groups)):
        raise CadenceError("wire_page_partition_mismatch", "Native page node membership differs from the declared groups.", "verify")


def verify_optional_net_groups(capture, sid, payload):
    if "expectedPageNetGroups" in payload:
        verify_net_groups(native_partition(capture, sid), payload)
