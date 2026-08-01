# P10.1 baseline bounded-window timeout remediation

Status: **PASS** for the offline host-scheduler remediation. Hardware
confirmation remains pending a new run-bound authorization and retry.

The failed run
`p10_1_hw_20260801T025145Z_bfff4836_1585d1ad_9ad4f85f` is preserved at
checkpoint `059c48166e50162c56079a9d76bf2bb3b41ea517`. Its final evidence records
`SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, and a consumed current-run
authorization.

## Direct cause

The first two-lane 1 MiB object in the 60-second F-to-R baseline window took
4154 ms wall time. That left 55,846 ms in the window. At the same directly
measured rate, a 16 MiB object requires about 66,464 ms before safety margin,
but the old scheduler used a fixed 42,000 ms candidate budget and selected it.

The host deadline expired with both main service states equal to `3`, which is
`P9_SERVICE_RUNNING`. Thus the direct evidence is a bounded-window chunk
sizing error, not a completed object with failed integrity. The historical
stage remains FAIL and is not relabeled.

## Change

The XSDB bounded-window scheduler now:

1. completes a 1 MiB sample before considering a larger chunk;
2. scales the most recent completed wall time to the proposed chunk;
3. adds 25% plus 2 seconds of margin;
4. defers the large chunk when that budget plus 3 seconds cannot fit; and
5. emits richer P10.1 state/status/committed-byte diagnostics on any future
   paired timeout.

For the captured trace, the new 16 MiB budget is 85,080 ms, so the 16 MiB
candidate is correctly deferred. A slow campaign will therefore produce a
measured performance FAIL rather than an unrelated host timeout.

No bitstream or ELF changed. A fresh authorization must bind the new
`scripts/hw/p10_dual_xsdb_stage.tcl` SHA256
`747f24c2e9b001c673e75d5f872da5574dfe9b5a122f2259ef98257115b13af3`.

## Offline validation

- 27 focused unit tests: PASS
- Tcl parse through the pre-connect argument guard: PASS
- no-hardware-call check: PASS (`NO_HARDWARE_ACTIONS_EXECUTED=1`)
- `git diff --check`: PASS

Machine-readable evidence is in
`evidence/generated/p10_1_hw_baseline_window_timeout_remediation.json`.
