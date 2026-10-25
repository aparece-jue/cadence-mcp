# Batch 26 — reused hierarchy block and native flat partition acceptance

## Scope and implementation

H03 now implemented_partial, with an internal fixed FULLADD clone fixture only. It is not a generic public hierarchy editor. Public tool count stays111. H02 stays deferred: the existing connected-resistor NULL schematic net failure is not fixed or bypassed by these FULLADD successes.

Official local Tcl reference p429–430 defines Page.NewDrawnInst(source,state); p522/524/535 supplies reference/location; p536–537 supplies fresh drawn scalar ports for the next stage. The fixed adapter finds the unique FULLADD/FULLADD halfadd_A drawn block, releases iterators, clones its existing internal HALFADD implementation, explicitly assigns halfadd_C at(2000,2000), then saves page/schematic/design in a new owned DSN. No installation or real design mutation. This adds an instance reusing an existing child definition; it does not create a fresh child schematic or new port.

## Native acceptance

`.local/hierarchy-clone-20261023/report.json` passes. Expected definition digest, new four scalar boundary pins unbound, translated global hotspots and pose, unchanged original connection-object semantic digest, and23 occurrences with six new descendants were frozen before native execution. Source16 occurrences become23 = original16 + one block + six children. Native receipt saved=true, return0, owned processes0; independent processes reopen the output and verify. Original FULLADD SHA27c6... unchanged; outputddf876... remains intact. Original geometry/properties/render outside the checks are not broadly certified.

`.local/hierarchy-clone-nets-20261023/report.json` first fails because the harness incorrectly declared30 child pins. The explicit composition is two inverters ×4(input/output/VCC/GND) plus four two-input gates ×5 =28. This arithmetic correction is recorded; the first report is retained, and no design is recreated or mutated for the corrected read-only run. V2 independently reads both saved designs and verifies original partition preservation, cloned internal physical-pin partition, private net isolation and onlyVCC/GND shared global objects. Names are not used to merge objects: equality/sharing comes from native flat object identity within each snapshot. Private names may differ across replicated contexts.

New hierarchy_semantics.py validates bounded occurrence-segment/physical-pin identities, rejects duplicate pins, invalid fields and inconsistent metadata for a single native flat object. net_partition ignores native flat ID spelling and enumeration order, but preserves all member identities, unbound state, global state and (by default) native net names. Cross-clone comparison deliberately ignores only private net names, while retaining global names/state and requiring the copied physical pin partition. Shared-object checks reject cloned private objects appearing in original contexts.

First typed-audit strict bool check rejects the native reader's integer0/1 GetIsGlobal values. An explicit boundary decoder now accepts only0/1, leaving the input untouched; typed rows remain strict bool/null. The initial observed stdout is retained in typed-partition-audit-v1-observed.json (the audit filename itself was reused). `.local/hierarchy-clone-nets-v2-20261023/typed-partition-audit.json` passes with original partition/name/global metadata intact,28 new child pin rows, private isolation, shared GND/VCC only; frozen native files and original report hashes unchanged, no mutation replay.

Six meaningful host tests exercise snapshot ID/order invariance, native integer decoding, all qualified physical pin identity changes, disconnects, duplicate pins, inconsistent metadata, private merges/shorts and unapproved global sharing. An initial unit test incorrectly treated renaming a singleton flat object's ID as a disconnect; corrected to an actual bound→unbound transition with null metadata. Renaming a snapshot ID must remain allowed.

## Real MCP acceptance

`.local/hierarchy-clone-mcp-20261023/report.json` actual111-tool stdio verifies exact23-node declared tree, the six expected halfadd_C children, unit-aware unique segment paths despite repeated raw paths, paging/schema/strict input, independent session reopen, cursor binding, close and deliberate tamper rejection. Only its new query workspace copy is intentionally corrupted at the end; the original saved clone DSN remains intact. This certifies public read access to the generated hierarchy, not an unpublished write endpoint or public full-net service.

Final269 regression268pass1 original file-symlink permission skip. Older process-directory resource issue remains open. No GUI actions, commits or pushes. Goal remains active and all original34 required gates remain.

## Full H03 implementation contract and remaining sequence

1. Integrate generic internal-block reuse into durable plan/apply/jobs/cancel/recover and verified output opening. Inputs bind session revision, source block ID/native ID, qualified parent page, explicit new reference/location and complete expected boundary pin bindings/hotspots. Source child implementation must be internal, uniquely resolved and nonrecursive. Reject unverified external dependencies, missing/duplicate semantic identities and unbounded baselines before writing. Every started job remains nonreplayable.
2. Add fresh drawn block creation using the verified NewDrawnInst overload and NewPortInstScalar; separately create/link the child schematic and real DboPortSymbol-backed child page ports. Preserve explicit direction/name/physical coordinates and parent/child mapping. No global symbol substitution for a hierarchy port.
3. Add rename/direction/delete/relink operations with incoming-reference and nonempty-content dependency guards. Include repeated subcircuit instances, cross-page and nested contexts, source closure and root-cycle rejection. A matching name alone never proves an electrical edge.
4. Predeclare positive and missing/direction/name/collision negative fixtures; verify saved parent/child port endpoints and native flat partitions. Wrong same-name local nets must remain separate, intentional cross-page/global edges must merge. Validate original and unrelated part properties/geometry, annotation/package ownership, affected rendered content and native DRC under their own gates.
5. Verify pending/active cancel, timeout, native save/receipt-loss recovery, immutable hashes and fresh-server idempotency for the actual public write tools. Do not use the current read-only stdio success as write-lifecycle evidence.

Fresh creation, port CRUD/linking, generic public write contracts and all listed matrix cases remain unimplemented/unaccepted. The prototype and narrow acceptance do not replace these requirements. Next work is generic hierarchy write integration or independent D04 where a hierarchy case fails and is moved to the tail.
