"""Explicit approved parameter and model reference edits, always producing a new DSN copy."""
from datetime import datetime, timezone
import json,copy,re,math
from pathlib import Path
import shutil

from .capture import CaptureService
from .capture_properties import read_part_properties
from .core import CadenceError, checked_path, sha256, new_id
from .environment import ADAPTERS, process_env, run_tcl
from .isolated_jobs import IsolatedJobs, digest
from .process_tree import run_owned_process


APPROVED_PROPERTIES={'Value','PCB Footprint','Implementation','TC1','TC2'}
MODEL_PROPERTIES={'Implementation','TC1','TC2'}

def validate_property_change(name,value):
    if name not in APPROVED_PROPERTIES or not isinstance(value,str) or len(value)>1024 or '\x00' in value:
        raise CadenceError('invalid_property_change','Use a bounded approved property string.')
    if name=='Implementation' and not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.+-]{0,127}',value):
        raise CadenceError('invalid_property_change','Implementation requires a literal model identifier, at most128 characters.')
    if name in ('TC1','TC2') and (len(value)>64 or not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?',value) or not math.isfinite(float(value))):
        raise CadenceError('invalid_property_change','Temperature coefficients require finite decimal numeric strings.')

def property_snapshot(rows):
    if not isinstance(rows,list) or len(rows)>1024:raise CadenceError('invalid_property_snapshot','Invalid bounded property snapshot.')
    result=[];ids=set();total=0;text_bytes=0
    for row in rows:
        if not isinstance(row,dict) or set(row)!={'partId','schematicName','pageName','reference','properties'}:raise CadenceError('invalid_property_snapshot','Invalid property snapshot row.')
        if any(not isinstance(row[k],str) or len(row[k])>4096 for k in ('partId','schematicName','pageName','reference')) or row['partId'] in ids:raise CadenceError('invalid_property_snapshot','Invalid property identity.')
        ids.add(row['partId']);props=row['properties']
        if not isinstance(props,list) or len(props)>512:raise CadenceError('invalid_property_snapshot','Invalid property count.')
        names=set()
        for prop in props:
            if not isinstance(prop,dict) or set(prop)!={'name','value'} or not isinstance(prop['name'],str) or not 1<=len(prop['name'])<=256 or not isinstance(prop['value'],str) or len(prop['value'])>16384 or prop['name'] in names:raise CadenceError('invalid_property_snapshot','Invalid or duplicate property.')
            names.add(prop['name']);total+=1;text_bytes+=len(prop['name'].encode('utf-8'))+len(prop['value'].encode('utf-8'))
        result.append({'scope':[row['schematicName'],row['pageName'],row['reference']],'properties':sorted(copy.deepcopy(props),key=lambda p:p['name'])})
    if total>16384 or text_bytes>8*1024*1024:raise CadenceError('invalid_property_snapshot','Total property count exceeds16384.')
    return sorted(result,key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))

def expected_property_snapshot(graph,scope,name,value):
    expected=copy.deepcopy(graph);matches=[r for r in expected if r['scope']==scope]
    if len(matches)!=1:raise CadenceError('ambiguous_target','Property snapshot target is not unique.')
    props=[p for p in matches[0]['properties'] if p['name']==name]
    if len(props)!=1:raise CadenceError('property_unavailable','Existing effective property is missing.')
    props[0]['value']=value
    return sorted(expected,key=lambda x:json.dumps(x,sort_keys=True,ensure_ascii=False))

def read_design_properties(config,design,directory):
    out=directory/(new_id('design-properties')+'.json')
    run_tcl(config,'inspect_design_properties.tcl',[str(design),str(out),'100000','512'],directory)
    if out.stat().st_size>16*1024*1024:raise CadenceError('output_limit','Design property snapshot exceeds16MiB.')
    graph=property_snapshot(json.loads(out.read_text(encoding='utf-8')));out.unlink();return graph


def definition_baseline(data):
    schematics = {row["objectId"]: row["name"] for row in data["schematic"]}
    pages = {row["objectId"]: row["name"] for row in data["page"]}
    def prefix(row):
        return [schematics[row["schematicId"]], pages[row["pageId"]], row["reference"]]
    return digest({
        "schematics": sorted(schematics.values()),
        "pages": sorted([schematics[row["schematicId"]], row["name"]] for row in data["page"]),
        "parts": sorted(prefix(row) for row in data["part"]),
        "pins": sorted(prefix(row) + [row["number"], row["name"], row["connected"], row["net"]] for row in data["pin"]),
    })


class CapturePropertyEdits(IsolatedJobs):
    kind = "capture_property"

    def __init__(self, config, capture):
        super().__init__(config)
        self.capture = capture

    def plan(self, session_id, part_id, property_name, value):
        validate_property_change(property_name,value)
        with self.capture.lock:
            session = self.capture._session(session_id)
            part = next((row for row in session["data"]["part"] if row["objectId"] == part_id), None)
            if part is None:
                raise CadenceError("object_not_found", "Part does not belong to this immutable session.")
            siblings = [row for row in session["data"]["part"] if row["pageId"] == part["pageId"] and row["reference"] == part["reference"]]
            if len(siblings) != 1:
                raise CadenceError("ambiguous_target", "Shared references/multi-unit editing require the dedicated unit-aware operation.")
            properties = read_part_properties(self.capture, session_id, part_id)
            if property_name=='Implementation' and next((p['value'] for p in properties['items'] if p['name']=='Implementation Type'),None)!='PSpice Model':
                raise CadenceError('model_type_required','Implementation edits require an existing PSpice Model implementation type; changing a symbol view type is a separate operation.')
            old = next((row["value"] for row in properties["items"] if row["name"] == property_name), None)
            if old is None:
                raise CadenceError("property_unavailable", "This operation changes an existing effective property only.")
            if len(old) > 4096 or "\x00" in old:
                raise CadenceError("input_limit", "Existing property value exceeds this operation's bounded argument size.")
            self.capture._session(session_id)
            payload = {"sourceDesign": str(session["design"]), "sourceFingerprint": session["revision"],
                       "partId": part_id, "schematicName": properties["schematicName"], "pageName": properties["pageName"],
                       "reference": properties["reference"], "property": property_name, "oldValue": old, "value": value,
                       "definitionBaselineDigest": definition_baseline(session["data"])}
            graph=read_design_properties(self.config,session['design'],session['design'].parent)
            if len(graph)!=len(session['data']['part']):raise CadenceError('target_changed','Property snapshot part count differs from the session.')
            expected=expected_property_snapshot(graph,[properties['schematicName'],properties['pageName'],properties['reference']],property_name,value)
            payload['expectedPropertySnapshotDigest']=digest(expected)
            self.capture._session(session_id)
        return self.create_plan(payload)

    def preview(self, payload):
        return {key: payload[key] for key in ("partId", "schematicName", "pageName", "reference", "property", "oldValue", "value", "sourceFingerprint")}

    def preflight(self, payload):
        source = checked_path(payload["sourceDesign"], (self.config.workspace_root,))
        if not source.is_file() or source.suffix.lower() != ".dsn" or sha256(source) != payload["sourceFingerprint"]:
            raise CadenceError("target_changed", "Source workspace snapshot changed after planning.")
        validate_property_change(payload['property'],payload['value'])
        if payload['property'] in MODEL_PROPERTIES and 'expectedPropertySnapshotDigest' not in payload:
            raise CadenceError('invalid_plan','Model/parameter edits require the complete effective-property preservation graph.')

    def execute(self, directory, payload, cancel, on_started):
        source = checked_path(payload["sourceDesign"], (self.config.workspace_root,))
        target = directory / "design.dsn"
        if target.exists():
            raise CadenceError("output_exists", "An existing isolated output must never be overwritten or replayed.")
        with source.open("rb") as original, target.open("xb") as copied:
            shutil.copyfileobj(original, copied)
        if sha256(source) != payload["sourceFingerprint"] or sha256(target) != payload["sourceFingerprint"]:
            raise CadenceError("target_changed", "Source changed while copying the isolated output.")
        return run_owned_process(self.native_command(directory, payload), directory, process_env(self.config),
                                 self.config.timeout_seconds, cancel=cancel, on_started=on_started)

    def native_command(self, directory, payload):
        return [self.config.install_root / "tcltk/bin/tclsh.exe", ADAPTERS / "edit_property.tcl",
                self.config.install_root, directory / "design.dsn", directory / "native-result.json", payload["partId"], "100000",
                payload["property"], payload["oldValue"], payload["value"],
                payload["schematicName"], payload["pageName"], payload["reference"]]

    def open_output(self, plan_id, plan_digest):
        """Register only a verified artifact as a new immutable query workspace."""
        guard = self._guard()
        try:
            directory, path, row = self._load(plan_id)
            if row["digest"] != plan_digest:
                raise CadenceError("plan_digest_mismatch", "Plan digest does not match.")
            if row["state"] not in {"verified", "verified_recovered"}:
                raise CadenceError("output_unverified", "Only independently verified outputs may be opened for further operations.")
            result = self._verified_result(directory, row)
            workspace_id = f"edit-output-{self.kind}-{plan_id}"
            manifest = {"workspaceId": workspace_id, "copiedFingerprint": result["artifact"]["sha256"],
                        "sourceFingerprint": result["artifact"]["sourceFingerprint"], "copyMode": "isolated_output",
                        "designRelativePath": "design.dsn", "dependencyClosureVerified": False}
        finally:
            guard.close()
        with self.capture.lock:
            self.capture.workspaces[workspace_id] = {"directory": directory, "manifest": manifest}
            opened = self.capture.open(workspace_id)
            return {**opened, "producedByPlan": plan_id, "outputKind": self.kind}

    def verify(self, directory, payload, native_completed):
        target = checked_path(str(directory / "design.dsn"), (directory,))
        if target.stat().st_size > 128 * 1024 * 1024:
            raise CadenceError("output_limit", "Isolated output exceeds the design limit.")
        before = sha256(target)
        if native_completed:
            receipt = checked_path(str(directory / "native-result.json"), (directory,))
            if receipt.stat().st_size > 16384:
                raise CadenceError("invalid_worker_result", "Invalid native save receipt.")
            data = json.loads(receipt.read_text(encoding="utf-8"))
            if data != {"saved": True, "partId": payload["partId"], "property": payload["property"]}:
                raise CadenceError("invalid_worker_result", "Native save receipt mismatch.")
        verifier = CaptureService(self.config)
        verifier.workspaces["isolated"] = {"directory": directory, "manifest": {"copiedFingerprint": before}}
        opened = verifier.open("isolated")
        sid = opened["sessionId"]
        try:
            observed = verifier.sessions[sid]["data"]
            if definition_baseline(observed) != payload["definitionBaselineDigest"]:
                raise CadenceError("unexpected_connectivity_change", "Saved definitions/pin nets differ from the pre-change snapshot.", "verify")
            names = {row["objectId"]: row["name"] for row in observed["schematic"]}
            pages = {row["objectId"]: row for row in observed["page"]}
            candidates = [row for row in observed["part"] if row["reference"] == payload["reference"]
                          and names[row["schematicId"]] == payload["schematicName"]
                          and pages[row["pageId"]]["name"] == payload["pageName"]]
            if len(candidates) != 1:
                raise CadenceError("ambiguous_target", "Saved property target is missing or ambiguous.", "verify")
            properties = read_part_properties(verifier, sid, candidates[0]["objectId"])
            actual = next((row["value"] for row in properties["items"] if row["name"] == payload["property"]), None)
            if actual != payload["value"]:
                raise CadenceError("property_verification_failed", "Saved property does not match the explicit plan.", "verify")
        finally:
            verifier.close(sid)
        if 'expectedPropertySnapshotDigest' in payload and digest(read_design_properties(self.config,target,directory))!=payload['expectedPropertySnapshotDigest']:
            raise CadenceError('unexpected_property_change','Saved effective properties differ from the declared target edit or unrelated property preservation.','verify')
        self.preflight(payload)
        if sha256(target) != before:
            raise CadenceError("target_changed", "Output changed during independent verification.")
        plan_id = directory.name.removeprefix("plan-")
        artifact = {"artifactId": f"edited-{plan_id}", "kind": "capture_edited_design",
                    "workspaceRelativePath": "design.dsn", "sha256": before, "size": target.stat().st_size,
                    "producedByJob": plan_id, "sourceFingerprint": payload["sourceFingerprint"],
                    "createdAt": datetime.now(timezone.utc).isoformat(), "validationState": "validated"}
        return {"planId": plan_id, "state": "verified" if native_completed else "verified_recovered",
                "property": payload["property"], "expectedValue": payload["value"], "observedValue": actual,
                "sourceModified": False, "outputWorkspaceRelativePath": directory.relative_to(self.config.workspace_root).as_posix(),
                "nativeCompletionVerified": native_completed, "independentReopenVerified": True,
                "definitionBaselinePreserved": True, "electricalBehaviorVerified": False,
                "effectivePropertyMultisetPreserved":'expectedPropertySnapshotDigest' in payload,
                "modelDefinitionResolved":False,"simulationInputRegenerated":False,
                "designPassed": None,
                "occurrenceConnectivityVerified": False, "artifact": artifact,
                "notChecked": ["occurrence_connectivity", "native_drc", "electrical_behavior", "external_footprint_exists"]}
