# Batch 24 — task-bound OUT inspection and native MEASURE discovery

## Scope and outcome

P03 remains implemented_partial; original 34 gates unchanged. New public pspice_inspect_run_output(planId, planDigest) binds diagnostics/bias observations to an already verified durable engine job. 111 actual MCP tools. No native execution, arbitrary path or public read-root expansion in this tool. It holds the job guard, checks digest/state and all manifest input/OUT/DAT hashes before and after parsing; exact read bytes must equal the OUT manifest hash. Recovered artifacts keep nativeCompletionVerified=false and solverSuccessVerified=false. Numerical acceptance is inherited only for the original declared trace rows; designPassed=null. Native measurements are explicitly notChecked.

## Official evidence and failed native gate

Local doc/pspcref/01commands.html #63807 documents .MEASURE DC/AC/TRAN FIND/WHEN/AVG/MIN/MAX and says results are generated in a text file. doc/psptclcmdref/PSpiceCommandDo.html documents doDCAN/doACAN/doTRAN/FINISH; FINISH flushes outputs. New isolated circuits and the fixed engine adapter were used, no installation or real design changes.

`.local/native-measure-20261023/report.json`: all three native processes returned 0, with receipt phases zero and owned processes zero. DC divider MAX/AVG/FIND and transient RC WHEN/FIND produced OUT/DAT but no measurement values or additional measurement result file within their owned directories. This does not prove no file could exist elsewhere or that a GUI workflow cannot compute it. AC VM(2) explicitly reported ORPSIM-16646 and ORPSIM-16634 despite return 0. Original predeclared numerical expectations remain saved, none counted as native MEASURE acceptance. Root cause of missing DC/TRAN measurements and supported AC expression remains unresolved. Issue ISS-P03-native-measure-results is open and moved to the tail; sampled DAT measurements remain distinct.

## Acceptance

`.local/run-output-mcp-20261023/report.json`: actual stdio DC and transient solve/save/independent DAT verify then new OUT read; schema validation, plan identity, explicit absence of native measurement/numerical acceptance claims, wrong digest and extra field rejection. Actual AC error classified pspice_output_error; its unverified OUT cannot be promoted via this tool. Fresh server OUT reads and apply with same key do not replay; changing the newly owned DC DAT invalidates the OUT read. That DC artifact is intentionally tampered and remains rejected; transient output is intact. All input circuit hashes unchanged. No claim of independent numerical DC/RC acceptance in this batch (these fixtures were discovery inputs).

Three host tests cover provenance, recovered native-completion uncertainty and digest/state/read-byte mismatch. Initial full run accidentally collected 10 inherited/imported RunTests duplicates (270 tests, 269 pass/1 skip); corrected test class composition, not acceptance logic. Final full suite260 tests259 pass1 original file-symlink permission skip. Previous intermittent process-directory release error remains open; a green run is not its fix.

## Remaining and next

Native measurement extraction and numerical oracles, broader diagnostic grammar and units, original full P03 remain. Next independent work L05/H03/D04. Goal active; no GUI actions, commits or pushes.
