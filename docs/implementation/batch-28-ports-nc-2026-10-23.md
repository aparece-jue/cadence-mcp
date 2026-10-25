# Batch 28 — fresh hierarchy-port failure and independent NC lifecycle

## Full scope retained

H03/D04 remain implemented_partial. Public tools remain116. This batch adds internal native fixtures and acceptance scripts; no fresh hierarchy-port or NC mutation endpoint is published. Latest full regression remains batch27's272 tests271pass1 original file-symlink permission skip, not a new run. Only new independent native/MCP acceptance and script compilation were necessary for these internal additions; public production code is unchanged.

## Fresh parent/child port graph: failed and moved to tail

Official local Tcl reference declares NewPortSymbol(p221), Page.NewPort(p445–446), NewDrawnInst(p429–430), NewPortInstScalar(p536–537), Port.SetPinType(p579). Installed capDParts/capDynObjects.tcl confirms drawn block constructor and pin API calling convention. The original fixture constructs a new TOP/MAIN and CHILD/CHILD_PAGE, dedicated real DboPortSymbol objects, two child ports and an intended through-wire, plus a parent block with corresponding scalar pins. Predeclared expected.json retains IN/OUT names/types, locations and intended parent/child connection rule. It never opens or overwrites a source design.

`.local/hierarchy-fresh-ports-20261023/report.json` crashes with native access violation3221225477, owned processes0, no saved DSN. V2 adds phase logging only, preserving the same operation; `.local/hierarchy-fresh-ports-v2-20261023/phases.log` reaches create_design/create_child/create_port_symbols/create_child_ports. The last phase contains multiple NewPort/SetPinType calls, so it does not identify one exact crashing method. No receipt, saved design, independent read, port direction/mapping or electrical acceptance is available. The initialization requirements for newly constructed port symbols remain unverified; do not infer a general NewPort API defect. New issue ISS-H03-fresh-port-native-crash remains open; moved to tail while NC work proceeds. No GUI fallback or unsupported public port operation was added.

## NC independent native positive and negative cases

Official DboPortInst GetIsNoConnect(p544)/SetIsNoConnect(p552) supply the fixed scalar flag operation. fixture_nc_edit.tcl operates only on a fresh fixture copy, uniquely locates HALFADD/MCP_PLACE/R101 with physical pin1 or2, releases iterators before mutation, validates old flag and native unbound state, applies flag and saves page/schematic/design. It explicitly refuses connected pins and unknown unbound status. It is a fixed internal probe, not a generic protected writer.

`.local/nc-lifecycle-20261023/report.json` passes4 cases: add NC to unbound R101.1; remove it in a separate copy of the saved add output; refuse NC on connected R101.2; refuse wrong expected old flag. Positive outputs independently reopen through definition and connection-object readers. Exact full definition pin-net digest stays unchanged, expected NC object/reference/physical number/hotspot(290,310) is added/removed, and all other connection semantics remain. Negative cases exit1 with specific connected_pin_refused/old_flag_mismatch, no save, and copied bytes unchanged. All owned native processes0; original connected fixture SHA1baf... unchanged. Markers are not used as proof of DRC or electrical safety.

## Real MCP reads

First `.local/nc-read-mcp-20261023/report.json` fails because the test omitted required expectedRevision from capture_compare_connections; original failure retained. Corrected harness uses the exact opened immutable revision without altering production contract.

`.local/nc-read-mcp-v2-20261023/report.json` passes2 actual116-tool stdio cases: saved add fixture returns one R101.1 NC at(290,310); saved remove fixture returns none. Explicit predeclared four-pin resistor expectations still pass: R101.2/R102.1 bound MCP_MIDDLE, outer pins unbound. Schema, invalid bool limit and closed-session rejection checked. Source outputs retain hashes; none deliberately tampered. This certifies public NC query of the saved fixtures, not an unpublished write lifecycle.

## Remaining and next

NC still needs typed generic plan/apply/jobs/cancel/recover/open, session/native pin identity and source/expected-state binding, other package/unit/occurrence and NC-on-connected cleanup policies, arbitrary pin/geometry/property invariants and real fault matrix. D04 also retains standalone alias edit/delete, global/power/ground/offpage creation/edit/delete/rotation/closure requirements and original acceptance matrix. C04 still needs remaining global/offpage and same-name local-net cases; NC positive reading now has real evidence. H03 fresh-child/port failure and all earlier issues remain open. Next independent D04 NC protected task integration, then other available D04 operations before returning to failed fresh port construction. No GUI, installation/real design edits, commit or push. Goal active; all34 original gates unchanged.
