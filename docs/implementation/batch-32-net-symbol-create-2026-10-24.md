# Batch 32 — durable source-bound net-symbol creation

Checkpoint recorded2026-10-24; native evidence directories retain their20261023 names. Actual132 public tools, H03/D04 and original34 full requirements remain incomplete. No goal completion claim.

## Final contract

CaptureNetSymbolCreates(kind=capture_net_symbol_create) adds capture_plan_net_symbol_create/apply_net_symbol_create/net_symbol_create_jobs/cancel_net_symbol_create/recover_net_symbol_create. capture_open_edit_result adds kind=net_symbol_create. Plan binds immutable design and library snapshot hashes, queried net-symbol ID/name/native kind, unique qualified page, generated private copied-symbol name, explicit origin/hotspot/rotation/mirror, and complete caller expectations for every selected-page pin. Only actual global/offpage definitions are supported; port definitions require their hierarchy workflow. Invalid scalar identifiers, unsupported pose/lead, duplicate instances/leads and incomplete pin tables are refused.

Optional orthogonal lead must terminate on exactly one existing unbound internal single-unit physical pin. The caller must explicitly expect that pin connected to the new name. A symbol without a lead can be stored with explicit unchanged pin expectations; it does not gain a claimed pin connection. Origin and hotspot are distinct caller inputs, never inferred equal or replaced by observed values.

The fixed JSON adapter checks source symbol type, copied-name collision among local symbols, exact typed getter and page locator. It copies the actual library glyph into the DSN, resolves the typed local definition, creates NewGlobal/NewOffPageConnector and optional explicit lead, then fully saves page/schematic/design. The source OLB is a private LibraryService snapshot, not the installation file. No arbitrary script/eval or original design edits.

Independent verification reuses full definition pin-net oracle, all connection object semantics and all affected-page part geometry/hotspots. With a lead, a separate reopened worker additionally requires exactly one selected symbol/lead/target pin, sharing the same nonnull native page-net object and expected name. Both source hashes and output hash are rechecked around execute/verification/recovery. Result scope source_bound_page_definition_net_symbol_create, leadBindingVerified only when applicable, occurrenceConnectivityVerified=false, designPassed=null. Dependency closure, source graphic equivalence, full rotation model, cross-page/global-flat semantics and PSpice ground0 are not certified.

## Native compatibility failure and fix

Initial `.local/net-symbol-create-mcp-20261023/report.json` fails at native0: generated40-character copied symbol name is rejected by CopySymbol with1099, saved=false/phase=copy_symbol. First fault suite's receipt-loss case consequently fails native_write_failed; cancel and timeout cases pass. Original jobs/reports remain failed; no payload or ledger rewritten/replayed.

`.local/net-symbol-name-lengths-20261023/report.json` isolates fresh owned copies:24 and31-character names save successfully;32 and40-character names fail CopySymbol/1099, all owned processes0. This is measured behavior on this24.1 host, not an unsupported universal version rule. Generator now creates24-character private names, with collision rejection; preflight rejects invalid or >31-character names. The compatibility probe was subsequently parameterized with required install/source/workspace arguments (same native cases, no production logic changed).

## Actual acceptance

`.local/net-symbol-create-mcp-v2-20261023/report.json`: actual132-tool stdio passes4 distinct source-bound cases: VCC/global, OFFPAGELEFT-L, GND/global with rotation1/mirror1, and offpage rotation1/mirror1 with another net name. Each has a short lead and complete predeclared four-pin table. Save, fresh-process definitions/objects/geometry/native binding, opening verified output and exact copied-symbol name/hotspot query pass. Port-as-global, bool rotation, invalid lead, missing pin expectations and extra field rejected. A deliberately incorrect glyph origin produces a failed post-save verification, refused output opening and same-key replay refusal; no expectation is overwritten. Pending cancel/jobs, fresh-server same-key idempotency/recover/open and final artifact tamper refusal pass. Only last successful offpage output is intentionally appended and remains rejected; other three outputs and original inputs stay intact.

`.local/net-symbol-create-faults-v2-20261023/report.json`: real native completion then controlled receipt deletion -> fresh verification-only recovery/open, nativeCompletionVerified=false, unchanged artifact hash; startup cancellation; actual1-second timeout. Owned processes0, no replay. Not all save/interruption windows or historical directory-handle behavior have been accepted.

Four host tests cover separate explicit origin/hotspot and immutable expected-object construction, invalid kind/bus-name/bool pose/lead refusal, duplicate-instance/lead refusal, and preflight design+library fingerprint/native copied-name limit. Full291 tests290pass1 original file-symlink permission skip. Historical process-directory release issue remains open. Original connected DSN SHA1baf... and installation capsym SHA dbfe... unchanged. No GUI, installation/real design mutation, commits or pushes.

## Remaining and next

D04 still needs global/offpage rename/move/rotation/delete, broader lead target/package/unit/occurrence and complex wire cases, cross-page/flat-global semantics, complete orientation/Unicode/source matrix, cache/closure, PSpice node0, full fault/render/DRC and original gate. The current producer does not certify cross-page connectivity merely because the created instance is an offpage connector. H03 fresh-port crash and previous issues remain open. Next standalone global/offpage edit/delete and cross-page fixtures, retaining failed gates at the tail. Goal active.
