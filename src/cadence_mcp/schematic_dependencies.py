"""Definition-wide dependency guards for isolated schematic mutations."""
from .capture_references import read_units
from .core import CadenceError


def schematic_dependencies(capture, session_id):
    """Scan definitions, including schematics with no occurrence under the root."""
    session = capture._session(session_id)
    schematics = [row["name"] for row in session["data"]["schematic"]]
    return classify_dependencies(schematics, read_units(capture, session_id, include_contents=True).values())


def classify_dependencies(schematics, units):
    by_folded_name = {}
    for name in schematics:
        key = name.casefold()
        if key in by_folded_name:
            raise CadenceError("ambiguous_target", "Schematic names must be unambiguous ignoring case.")
        by_folded_name[key] = name
    incoming = {name: [] for name in schematics}
    unresolved = []
    for unit in units:
        contents = unit["contents"]
        identity = {key: unit[key] for key in ("partId", "nativeId", "schematicName", "pageName", "reference")}
        target = by_folded_name.get(contents["viewName"].casefold())
        if unit["isExternalDesignPart"] or contents["libraryName"]:
            unresolved.append({**identity, "reason": "external_implementation"})
        elif contents["viewType"] == 1 and target is not None:
            # SPB 24.1 native schematic view code. Preserve incoming
            # references even if the instance is excluded from occurrences.
            incoming[target].append(identity)
        elif contents["viewType"] != 0 or contents["viewName"] or not contents["primitive"]:
            unresolved.append({**identity, "reason": "unresolved_implementation"})
    return {"incoming": incoming, "unresolved": unresolved}


def require_unreferenced(dependencies, name):
    if dependencies["incoming"][name]:
        raise CadenceError("schematic_referenced", "Schematic is referenced by a local design definition.")
    if dependencies["unresolved"]:
        raise CadenceError("schematic_dependencies_unverified", "External or unresolved implementations prevent proving that the schematic is unreferenced.")
