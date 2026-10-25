# Batch 31 — source-bound global/offpage symbols, explicit wire leads and symbol query

## Scope

Public tool count127. New capture_query_net_symbols reads immutable library net-symbol definitions. Global/offpage writes remain internal owned-fixture construction, not a public plan/apply lifecycle. D04/C04/L01 remain partial, original34 full gates unchanged. No full cross-page/global/occurrence/DRC verdict.

## Official source and typed definitions

Local Tcl reference p194 provides GetGlobalSymbol/GetOffPageSymbol, p203 NewSymbolsIter, p223 CopySymbol; p444–447 provides typed NewGlobal/NewOffPageConnector. Existing local hierarchy notes distinguish global, child port and offpage classes. No empty or global symbol is substituted for a different class.

Only Python reads original installation capsym.olb to make owned copies; Cadence opens owned copies, not the installation library. Original and copies SHA dbfe9f22628c42985db09bb2630f356ca7b65721af1366a4c9ad8fafee320aa8 stay unchanged. `.local/net-symbol-inventory-20261023/report.json` enumerates40 native symbols:21 relevant net symbols (11global/type33,8port/type34,2offpage/type35), plus title/bookmark objects outside the new query scope. Type codes are validated on this24.1 host, not promised for untested versions.

fixture_net_symbol_add.tcl opens one owned DSN/copy of capsym, finds HALFADD/MCP_PLACE, resolves exact source symbol by typed getter, CopySymbol into local MCP_NETSYM, resolves the typed copied symbol, places NewGlobal or NewOffPageConnector with explicit name/location/rotation/mirror and saves page/schematic/design. Null objects/states checked, iterators released before editing. This internal fixed fixture has no generic public source/page/durable write contract yet.

## Placement origin is not the connection hotspot

`.local/net-symbol-add-20261023/report.json` initial discovery4 cases confirm native save/readback, not complete electrical acceptance. VCC at origin(290,310) has actual offset hotspot(300,320); OFFPAGELEFT-L has(290,320). GND and offpage at rotation1/mirror1 have different offsets. Discovery passed flags mean execution/readback only. It did not certify pin connection. Source/body geometry or all rotations are not inferred from these measurements.

`.local/net-symbol-connected-20261023/report.json` freezes expected hotspots on R101.1(290,310), expected native pin net names and connection objects before mutation. Native save and symbol position/type/rotation/mirror match, but all4 definition expectations fail: R101.1 remains unbound even when symbol and pin hotspots coincide. Original failures retained. This is evidence for these specific Dbo construction paths, not a universal statement that Capture never connects coincident symbols/pins.

## Explicit lead-wire positives and independent native object evidence

`.local/net-symbol-wire-lead-20261023/report.json` introduces a declared new wire from(240,310) to original R101.1(290,310), with symbol hotspot at(240,310). Predeclared origins: VCC(230,300), OFFPAGELEFT-L(240,300), GND rotation1/mirror1(240,300), offpage rotation1/mirror1(230,310). All4 save/reopen cases now match full definition pin-net oracle and expected connection-object digest: R101.1 connects to MCP_SUPPLY/MCP_LINK/MCP_GROUND as specified, original MCP_MIDDLE connection and unrelated definitions/objects stay unchanged. Library copies/originals stay unchanged. The GND glyph is named MCP_GROUND in this fixture; this does not certify PSpice node0 semantics.

New read-only inspect_net_symbol_bindings.tcl derives from the project's native page partition reader, retaining pin/wire and global/offpage/port GetNet object identity in one process and one page scope. `.local/net-symbol-native-bindings-20261023/report.json` passes8 cases:4 lead positives explicitly require one nonnull native net object shared by selected symbol, wire and physical pin with expected net name;4 coincident negatives require selected pin unbound. Names are not used to infer object identity, and null groups do not count as connection. Source/output files unchanged. This reader does not establish global merging across pages or hierarchy instances.

`.local/net-symbol-read-mcp-20261023/report.json` actual126-tool stdio snapshot before query-tool addition passes4 saved fixture queries: exact global/offpage name/sourceSymbol/local origin/hotspot/rotation/mirror/isBus values; explicit four-pin expected connections via opened revision; schema and closed session refusal. Sources intact, no tamper. These are public reads of internally generated fixtures, not a public write workflow.

## New public net-symbol query

capture_query_net_symbols(libraryId,kind?,cursor?,limit) uses existing capture_library_open private OLB snapshots. Native symbol list reads verify source snapshot hash; parser returns only global/port/offpage exact native types, rejecting malformed/control/duplicate casefold kind-name identities. Other native object classes remain outside query scope. Snapshot/revision-scoped symbol IDs and paging; cursor binds library session/kind/limit. Metadata query explicitly does not verify glyph geometry/hotspots, embedding closure or electrical behavior.

`.local/net-symbol-library-mcp-20261023/report.json` actual127-tool stdio validates all21 identities by pagination and counts11/8/2, key VCC/GND/0/OFFPAGELEFT-L/PORTLEFT-L names, exact native schemas, strict inputs, cursor kind/limit/session isolation, second-session repeat, closed session and source-copy tamper refusal. Only the second private library copy is deliberately corrupted at the end; original installation library remains unchanged. First private copy remains intact.

Three new host tests verify exact native type filtering/order-stable source metadata, malformed/bool/extra/control rejection and ambiguity handling. Final287 tests286pass1 original file-symlink permission skip. Historical process-directory handle issue remains open. No GUI, installation/real design edits, commit or push.

## Remaining and next

D04 still needs generic source-bound net-symbol creation tasks with complete pin/geometry oracles and durable apply/cancel/recover/open/fault acceptance, subsequent rename/move/rotation/delete, source cache/closure, cross-page and hierarchy global/offpage network matrices, full orientation/Unicode/multiple-source cases, PSpice ground0 semantics and remaining original tests. Coincident placement failures remain evidence, not claimed completed. C04 broader cross-page/name-collision and H02 flat-net failures are unchanged. Next integrate source-bound symbol+explicit lead creation into durable task interfaces or advance another independent net-symbol operation after a failed gate is retained. Goal active.
