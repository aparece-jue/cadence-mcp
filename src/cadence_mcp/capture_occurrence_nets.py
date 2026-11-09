"""Session-bound native occurrence pins and comparison against a complete oracle."""
import json

from .capture_hierarchy_edit import read_flat
from .core import CadenceError
from .hierarchy_semantics import flat_pin_key, net_partition
from .schematic_dependencies import schematic_dependencies


def snapshot(capture, sid):
    session = capture._session(sid)
    if "occurrenceFlatPins" not in session:
        if schematic_dependencies(capture, sid)["unresolved"]:
            raise CadenceError("occurrence_connectivity_incomplete",
                               "An external or unresolved implementation prevents a closed native pin snapshot.")
        rows = read_flat(capture, sid)
        if not rows:
            raise CadenceError("occurrence_connectivity_incomplete", "No native occurrence pin rows are available.")
        session["occurrenceFlatPins"] = rows
    return session, session["occurrenceFlatPins"]


def query_occurrence_nets(capture, sid, offset, limit):
    with capture.lock:
        if type(offset) is not int or not 0 <= offset <= 100000 or type(limit) is not int or not 1 <= limit <= 1000:
            raise CadenceError("invalid_query", "Invalid occurrence pin page.")
        session, rows = snapshot(capture, sid)
        items = rows[offset:offset + limit]
        return {"sessionId": sid, "revision": session["revision"], "items": items, "total": len(rows),
                "nextOffset": offset + limit if offset + limit < len(rows) else None,
                "scope": "native_occurrence_pin_flat_membership",
                "flatIdentityScope": "session_snapshot", "independentOracleCompared": False}


def compare_partition(rows, groups, unbound):
    partition = net_partition(rows)
    indexed = {flat_pin_key(row): row for row in rows}
    actual = {tuple(group["pins"]): group for group in partition["groups"]}
    seen, expected, visibility = set(), {}, {}
    invalid = "invalid_occurrence_expectations"

    def member(pin):
        key = flat_pin_key(pin)
        if key in seen or len(seen) >= 10000:
            raise CadenceError(invalid, "Declare each expected pin once, with at most 10000 expected pins.")
        seen.add(key)
        if pin["isVisible"] is not None:
            visibility[key] = pin["isVisible"]
        return key

    for group in groups:
        if not group["pins"] or (group["isGlobal"] and not group["name"]):
            raise CadenceError(invalid, "Every node requires members, and every global node requires a name.")
        expected[tuple(sorted(member(pin) for pin in group["pins"]))] = group
    expected_unbound = {member(pin) for pin in unbound}
    if not seen:
        raise CadenceError(invalid, "An independent pin oracle is required.")
    missing, unexpected = seen - indexed.keys(), indexed.keys() - seen
    mismatch = 0
    for members, group in expected.items():
        row = actual.get(members)
        if (row is None or row["isGlobal"] != group["isGlobal"]
                or (group["name"] is not None and group["name"] != row["name"])):
            mismatch += 1
    visibility_mismatch = sum(key in indexed and indexed[key]["isVisible"] != value for key, value in visibility.items())
    unbound_mismatch = len(expected_unbound.symmetric_difference(partition["unbound"]))
    unexpected_groups = len(actual.keys() - expected.keys())
    passed = not (missing or unexpected or mismatch or visibility_mismatch or unbound_mismatch or unexpected_groups)
    return {"comparisonStatus": "pass" if passed else "fail", "expectedPinCount": len(seen),
            "observedPinCount": len(rows), "expectedFlatNodeCount": len(expected),
            "observedFlatNodeCount": len(actual), "missingPinCount": len(missing),
            "unexpectedPinCount": len(unexpected), "mismatchedNodeCount": mismatch,
            "unexpectedNodeCount": unexpected_groups, "visibilityMismatchCount": visibility_mismatch,
            "unboundMismatchCount": unbound_mismatch,
            "missingPins": [json.loads(key) for key in sorted(missing)[:20]],
            "unexpectedPins": [json.loads(key) for key in sorted(unexpected)[:20]]}


def compare_occurrence_nets(capture, sid, expected_revision, groups, unbound):
    with capture.lock:
        session = capture._session(sid)
        if session["revision"] != expected_revision:
            raise CadenceError("stale_revision", "The oracle must bind the exact design revision.")
        _, rows = snapshot(capture, sid)
        return {"sessionId": sid, "revision": expected_revision,
                "scope": "native_occurrence_pin_flat_membership", **compare_partition(rows, groups, unbound)}
