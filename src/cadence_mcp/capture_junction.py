"""Explicit crossing identity and geometry for a planned native junction."""
from collections import defaultdict

from .capture_wire import path_key, point, point_on_path
from .core import CadenceError


def junction_crossing(objects, page_id, wire_ids, location):
    """Bind one proper orthogonal crossing and declare its exact saved split paths."""
    if (not point(location) or not isinstance(wire_ids, list) or len(wire_ids) != 2
            or any(not isinstance(wire_id, str) for wire_id in wire_ids) or wire_ids[0] == wire_ids[1]):
        raise CadenceError("invalid_junction_crossing", "Declare one grid point and two distinct scalar wire IDs.")
    wires = [row for row in objects if row["kind"] == "wire" and row["pageId"] == page_id]
    indexed = {row["objectId"]: row["attributes"]["points"] for row in wires}
    if any(wire_id not in indexed for wire_id in wire_ids):
        raise CadenceError("object_not_found", "Both crossing wires must belong to the selected page.")
    selected = [indexed[wire_id] for wire_id in wire_ids]
    if any(len(path) != 2 or location in path or not point_on_path(location, path) for path in selected):
        raise CadenceError("invalid_junction_crossing", "The junction must be in the interior of both straight wires.")
    horizontal = sum(path[0][1] == path[1][1] for path in selected)
    vertical = sum(path[0][0] == path[1][0] for path in selected)
    if horizontal != 1 or vertical != 1:
        raise CadenceError("invalid_junction_crossing", "The crossing must contain one horizontal and one vertical wire.")
    if {wire_id for wire_id, path in indexed.items() if point_on_path(location, path)} != set(wire_ids):
        raise CadenceError("ambiguous_junction_crossing", "Additional wires touch the declared crossing.")
    expected = [path for wire_id, path in indexed.items() if wire_id not in wire_ids]
    for start, end in selected:
        expected.extend(([start, location], [location, end]))
    if len({path_key(path) for path in expected}) != len(expected):
        raise CadenceError("ambiguous_junction_crossing", "Saved split paths cannot be uniquely identified.")
    return expected

def junction_groups(rows, scope, crossed_paths, location, saved_paths, expected_pins):
    """Freeze the source memberships with only the two selected nodes merged."""
    selected = {path_key(path) for path in crossed_paths}
    wire_indexes = {path_key(path): i for i, path in enumerate(saved_paths)}
    pins = {(pin["reference"], pin["pinNumber"]): (i, pin["connected"])
            for i, pin in enumerate(expected_pins)}
    groups = defaultdict(lambda: {"wireIndexes": [], "pinIndexes": []})
    targets, seen_pins = [], set()
    for row in rows:
        if (row["schematicName"], row["pageName"]) != scope:
            continue
        group = row["group"]
        if row["kind"] == "wire":
            path = row["points"]
            identity = path_key(path)
            if identity in selected:
                targets.append(group)
                keys = [path_key([path[0], location]), path_key([location, path[-1]])]
            else:
                keys = [identity]
            if any(key not in wire_indexes for key in keys):
                raise CadenceError("junction_source_mismatch", "Native wire inventory differs from the planned paths.")
            groups[group]["wireIndexes"].extend(wire_indexes[key] for key in keys)
        else:
            expected = pins.get((row["reference"], row["number"]))
            if expected is None or expected[0] in seen_pins or expected[1] != (group is not None):
                raise CadenceError("junction_pin_state_change", "A junction may merge existing nodes but may not bind or unbind pins.")
            index, connected = expected
            seen_pins.add(index)
            if connected:
                groups[group]["pinIndexes"].append(index)
    if len(seen_pins) != len(pins) or len(targets) != 2 or None in targets:
        raise CadenceError("junction_source_mismatch", "The source pin or crossing wire membership is incomplete.")
    first, second = targets
    if first == second:
        raise CadenceError("junction_already_connected", "The crossing wires already belong to the same native node.")
    other = groups.pop(second)
    for key, members in other.items():
        groups[first][key].extend(members)
    return sorted(({name: sorted(values) for name, values in group.items()} for group in groups.values()),
                  key=lambda group: (group["wireIndexes"], group["pinIndexes"]))
