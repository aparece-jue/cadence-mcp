"""Compare explicit named pin expectations with immutable Dbo definitions.

This compares observations, not net equivalence or occurrence connectivity.
"""
from collections import Counter, defaultdict

from .core import CadenceError


KEYS = ("schematicName", "pageName", "reference", "pinNumber")


def compare_connections(data: dict, expectations: list[dict], source: str) -> dict:
    if not isinstance(source, str) or not source.strip() or len(source) > 1024:
        raise CadenceError("invalid_expectations", "A bounded expectation source is required.")
    if not isinstance(expectations, list) or not 1 <= len(expectations) <= 10000:
        raise CadenceError("invalid_expectations", "Provide between 1 and 10000 explicit pin expectations.")
    seen = set()
    for expected in expectations:
        if not isinstance(expected, dict) or set(expected) != {*KEYS, "connected", "net"}:
            raise CadenceError("invalid_expectations", "Unexpected pin expectation fields.")
        if any(not isinstance(expected[k], str) or not expected[k] or len(expected[k]) > 512 for k in KEYS):
            raise CadenceError("invalid_expectations", "Each pin locator must contain bounded, exact names.")
        if type(expected["connected"]) is not bool or (
            expected["connected"] and (not isinstance(expected["net"], str) or not expected["net"] or len(expected["net"]) > 512)
        ) or (not expected["connected"] and expected["net"] is not None):
            raise CadenceError("invalid_expectations", "Connected pins require a nonempty net name; disconnected pins require null.")
        key = tuple(expected[k] for k in KEYS)
        if key in seen:
            raise CadenceError("invalid_expectations", "Duplicate pin expectations are not allowed.")
        seen.add(key)

    schematics = {s["objectId"]: s["name"] for s in data["schematic"]}
    pages = {p["objectId"]: p["name"] for p in data["page"]}
    index = defaultdict(list)
    for pin in data["pin"]:
        if pin["schematicId"] not in schematics or pin["pageId"] not in pages:
            raise CadenceError("invalid_worker_result", "Pin definitions contain missing parents.", "decode")
        key = (schematics[pin["schematicId"]], pages[pin["pageId"]], pin["reference"], pin["number"])
        index[key].append(pin)

    findings, matched = [], set()
    for expected in expectations:
        key = tuple(expected[k] for k in KEYS)
        candidates = index.get(key, [])
        observed = None
        object_ref = None
        if not candidates:
            status, reason = "fail", "pin_not_found"
        elif len(candidates) != 1:
            status, reason = "unverified", "ambiguous_pin_definition"
        else:
            pin = candidates[0]
            matched.add(pin["objectId"])
            object_ref = {k: pin[k] for k in ("objectId", "partId", "pageId", "schematicId")}
            observed = {"connected": pin["connected"], "net": pin["net"] if pin["connected"] else None}
            if pin["connected"] and not pin["net"]:
                status, reason = "unverified", "connected_net_name_unavailable"
            elif observed != {k: expected[k] for k in ("connected", "net")}:
                status, reason = "fail", "connection_observation_mismatch"
            else:
                status, reason = "pass", "matches_explicit_expectation"
        findings.append({"ruleId": "SCH-CONN-EXPECTED-PIN", "ruleVersion": "0.1.0",
                         "status": status, "reason": reason,
                         "locator": {k: expected[k] for k in KEYS}, "objectRef": object_ref,
                         "expected": {k: expected[k] for k in ("connected", "net")},
                         "observed": observed, "candidateCount": len(candidates)})
    counts = dict(Counter(f["status"] for f in findings))
    verdict = "fail" if counts.get("fail") else "unverified" if counts.get("unverified") else "pass"
    return {"checkerVersion": "0.1.0", "scope": "selected_pin_definitions",
            "expectationSource": source, "expectationSourceIndependentlyVerified": False,
            "comparisonStatus": verdict, "comparisonComplete": not counts.get("unverified", 0),
            "findings": findings, "countsByStatus": counts, "expectedPinCount": len(expectations),
            "observedPinCount": len(data["pin"]), "matchedPinCount": len(matched),
            "uncheckedObservedPinCount": len(data["pin"]) - len(matched),
            "designPassed": None, "electricalConnectivityVerified": False,
            "notChecked": ["unlisted_pins", "net_equivalence", "junction_semantics",
                           "occurrence_connectivity", "bus_and_bundle_semantics", "native_drc"]}
