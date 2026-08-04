# P10.3 current-artifact completion audit

`P10_3_ACCEPTANCE=PENDING_CURRENT_ARTIFACT_HARDWARE`

`P10_3F_OFFLINE_READINESS=PASS`

`CURRENT_RUN_HARDWARE_AUTHORIZATION=false`

`HARDWARE_ACTIONS_EXECUTED_THIS_FOLLOWUP=false`

`MANUAL_INSTRUMENTATION=OMITTED_BY_USER`

The first-fault forensic RTL and its fixed/rotating-role bitstream, XSA, BSP, and ELF bundle are frozen. The complete 23-stage hardware campaign wrapper is also frozen and passes its focused unit, Tcl completeness, canonical consistency, register-map, traceability, P8C, P10, P10.1R, P10.2, and no-hardware gates. This establishes offline readiness only; it does not establish current-artifact hardware acceptance.

## Immutable inputs

- Goal SHA256: `6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281`
- Artifact source commit: `5b2e9e8a22038b15308faf435163f1787054f41d`
- Host campaign source commit: `5d63c69ca92377cec90f0f9694b7e8b15c8cac62`
- Campaign-freeze checkpoint: `6f5787eae9cb0d0758196c41173d6e1514dbf94a`
- First-fault artifact freeze: `evidence/generated/p10_3_fault_forensics_artifact_freeze.json` (`5346c774f9ec65cb02d6a08fb8e989ccfa3f84f6ab8e77ae70de4052d1d3dc82`)
- Full-campaign freeze: `evidence/generated/p10_3f_full_campaign_freeze.json` (`9b1aa8e29f8001e37c4978e50b115bf7a428fa468009b4de1df1583c36de4331`)

The ten artifact SHA256 values are recorded verbatim in the machine-readable audit. Board identities remain fixed/JTAG `210249855178` and rotating/JTAG `210512180081`; module identities are F0=A0019, F1=B0012, F2=B0001, F3=B0020, R0=A0010, R1=A0017, R2=B0023, and R3=B0025.

## Safety and evidence order

The offline design makes a detected safety or terminal-object fault immediately assert the endpoint-wide TX kill and full shutdown without waiting for software. On an exception or timeout, each endpoint that has not already frozen receives a direct terminal PL abort so that the recorder freezes before readout; an already-frozen first fault is left intact. The host may read forensic registers only after it verifies frozen state, completed post-fault tail, forensic hold, full shutdown, zero effective TX mask, and no physical-TX count advance over a bounded interval. It then archives the ordered snapshot and circular event log as raw binary plus parsed JSON, verifies SHA256, commits the archive in PL, and only then loads the independent role-bound shutdown bitstream. If archival cannot complete, the run fails but the independent dual-board shutdown still executes.

Functional reset and functional shutdown do not clear the recorder. PL state is volatile: FPGA reconfiguration and power loss do not preserve it, so archive-before-reconfiguration is mandatory. The operational path does not issue the explicit capture-clear command before loading the independent shutdown image.

Every stage has shutdown-before and independently verified shutdown-after. Error, timeout, Ctrl+C, normal exit, and wrapper failure all take the same freeze/archive-attempt-before-independent-shutdown cleanup path. The five 1/4/16/64/256 KiB staircase stages run immediately after module intake and before fault capture or longer diagnostics. No long-test command exceeds 256 KiB, every functional case is followed by a safety snapshot, and the single formal run is bounded to 1800 seconds.

The runner binds each run ID to the host commit and both functional-bitstream digest prefixes, validates an exact custom observation-plan shape, allocates non-overlapping stage-local object IDs, publishes the Goal-named evidence views, and verifies the final evidence manifest against both the exact file set and every SHA256 before classifying the run.

## Acceptance boundary

All four P10.3F offline requirements are PASS. All three P10.3F hardware requirements remain PENDING. The canonical 28 P10.3 requirements also remain PENDING for this current artifact bundle. Historical raw-connectivity and P10.3 hardware results are retained but are not inherited by the new bitstreams or runtime.

Per the user's latest instruction, oscilloscope, current/temperature, supply-rail, photodiode, and other manual-instrumentation work is omitted. No external electrical or optical measurement claim is made. Ethernet, movement, rotation, realignment, rewiring, lane masks above `0xF`, the two-hour test, P11, and product-final acceptance remain forbidden.

## Blocking condition

No new current-run authorization exists for full-campaign freeze SHA256 `9b1aa8e29f8001e37c4978e50b115bf7a428fa468009b4de1df1583c36de4331` and its exact artifact/host-input bundle. Under `AGENTS.md`, prior authorization cannot authorize this new run. Hardware therefore remains untouched until a new explicit authorization binds the freeze hash, host source commit `5d63c69ca92377cec90f0f9694b7e8b15c8cac62`, artifact source commit `5b2e9e8a22038b15308faf435163f1787054f41d`, all artifact hashes, both JTAG serials, all eight module identities, the 1800-second bound, maximum mask `0xF`, and the archive-before-independent-shutdown policy.

The authoritative structured record is `evidence/generated/p10_3_current_artifact_completion_audit.json`.
