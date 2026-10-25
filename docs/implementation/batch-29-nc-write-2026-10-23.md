# Batch 29 — durable NC marker tasks

## Behavior and contract

CaptureNcEdits(kind=capture_nc) exposes5 tools: capture_plan_nc_edit(sessionId,pinId,enabled), capture_apply_nc_edit, capture_nc_edit_jobs, capture_cancel_nc_edit, capture_recover_nc_edit. capture_open_edit_result adds kind=nc. Actual121 tools, contracts copied from real stdio. Capability experimental_single_unit_unbound_scalar_pin. D04 remains implemented_partial; all34 full requirements unchanged.

Plan resolves the immutable definition pin ID, validates strict bool, rejects connected pins, missing/repeated physical numbers and placed-part package scope other than internal single-unit. It binds source fingerprint, native part ID, qualified page/reference, physical pin number/name, observed old NC flag, actual global hotspot and unchanged affected-page geometry. Semantic NC expectation adds/removes exactly one target marker, keeping all other connection types/flags. Unchanged flags and duplicate NC identities are refused. Bounded JSON payload, literal native arguments; no arbitrary scripts/eval or source writes.

Fixed edit_nc.tcl rechecks qualified/native part identity, unique pin number, actual pin name/hotspot and old flag before mutation. Scalar object type16 is guarded based on this24.1 host's observed scalar port-instance type; this is not a claim of cross-version compatibility. Connected or unknown-native-unbound cases are refused. Iterators are released before SetIsNoConnect and full page/schematic/design save. Official local basis remains DboPortInst.GetIsNoConnect(p544)/SetIsNoConnect(p552), validated first by batch28 native fixtures.

The class reuses existing isolated-copy execution and CapturePartEdits verification. Exact full definition pin-net digest, complete connection-object semantic digest including the requested NC flag/location, and every affected-page part pose/global hotspot are checked in independent reopened workers. Source and output hashes checked; artifact is a verified edited DSN. Result scope single_unit_unbound_scalar_pin, scalarPinNCVerified=true, designPassed=null. Occurrence connectivity, multiunit/shared package lifecycle, bus pins, connected-NC cleanup, external closure, other-page geometry, unrelated properties/render/DRC remain explicitly unverified.

## Actual acceptance

`.local/nc-edits-mcp-20261023/report.json`: real121-tool stdio original connected resistor fixture. Strict bool/noop/connected/missing/extra refusal; plan/apply add NC on R101.1, open verified result and query exact(290,310), plan/apply remove using its new immutable pin identity, open/query no NC. Both saves independently verify full original definition/connection invariants and affected-page geometry. Pending cancel/jobs, fresh server same key no replay, recover/open and final tamper refusal all pass. Final remove DSN is deliberately appended and must remain rejected; add DSN/source remain intact.

`.local/nc-edits-centered-mcp-20261023/report.json`: independent created-library fixture R401, physical pin1/nameA at(680,300), both pins unbound. Same add/remove chain, strict/noop/missing/extra guards, pending cancel/jobs/fresh idempotency/recover/open/tamper refusal pass. This tests different qualified page/part/native identity/name/hotspot rather than only the original fixed fixture. Final remove output deliberately tampered; source and add output remain intact. The connected-pin negative applies to the first case; it is not claimed for this unbound fixture.

`.local/nc-faults-20261023/report.json`: three native cases pass: controlled native receipt loss after successful save -> fresh verification-only recovery/open, nativeCompletionVerified=false, artifact hash unchanged; native start-window cancellation; real1-second timeout. Cancel/timeout retain evidence, report owned processes0 and forbid replay. Not all save/interruption windows are covered. Historical process-directory release issue stays open despite green regression and owned0.

Four host tests cover hotspot-sensitive marker addition preserving all other connection objects and immutable inputs, removing only the selected marker while preserving other pins' NC flags, noop/duplicate rejection, and strict bool/connected/multiunit/drawn/external rejection before any plan file. Full276 tests275pass1 original file-symlink permission skip. No source design, installation, GUI, commits or pushes modified.

## Remaining

D04 standalone alias edit/delete; global/power/ground/offpage creation/edit/delete/rotation and source closure; full NC package/unit/occurrence/bus and connected-cleanup policies, additional faults/render/DRC and original matrix remain. H03 fresh-port native access violation and all other previous issues remain open. Next independent alias edit/delete task workflow; failed fresh port construction stays at the tail until independent work is accepted. Goal active.
