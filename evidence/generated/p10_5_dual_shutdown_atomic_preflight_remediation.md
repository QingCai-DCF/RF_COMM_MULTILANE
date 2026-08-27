# P10.5 dual-shutdown atomic-preflight remediation

- Status: `OFFLINE_VERIFIED`
- Hardware actions executed by this remediation: `false`
- Current-run hardware authorization: `false`
- Campaign stages executed in the triggering runs: `0`
- TX executed in the triggering runs: `false`

## Diagnosis

The dual-shutdown Tcl previously validated and programmed the fixed endpoint before validating the rotating endpoint. When exact rotating JTAG target `210512180081` was absent, this produced a safe but unnecessary fixed-only shutdown programming action before the overall shutdown-before gate failed. No functional bitstream or transmitting stage ran. Fixed shutdown was verified, while rotating shutdown could not be confirmed.

The final campaign summary also derived both endpoint fields from one aggregate Boolean. That discarded the accurate result `fixed=PASS`, `rotating=FAIL` from the failed runs.

## Remediation

The shutdown wrapper now performs a non-programming preflight of both exact target paths, serial bindings, and xc7z020 device topologies. It programs neither shutdown bitstream unless both preflights pass. Any missing or ambiguous endpoint therefore produces `TFDU_SHUTDOWN_PROGRAMMED=0`, blocks every campaign stage, and performs no one-sided programming.

The wrapper is now content-bound in both the current-run authorization and immutable freeze. Final evidence preserves the fixed and rotating shutdown result independently, while the combined safety gate still requires both endpoints and every shutdown attempt to pass.

## Regression evidence

The atomic-preflight test reproduced the original one-sided `PROGRAM xc7z020_1` call with only the fixed target present, then passed after the two-phase preflight change with no programming call. Separate red/green tests cover shutdown-wrapper content binding, exact post-artifact allowlisting, and per-endpoint evidence aggregation.

Fresh verification passed all 45 selected Python unit/consistency tests, Tcl completeness for all three P10.5 hardware scripts, JSON syntax validation, and `git diff --check`.

P10.5 remains pending because rotating JTAG target `210512180081` is still absent. No new hardware authorization or transmitting run is permitted until that exact endpoint is present and its shutdown can be confirmed.
