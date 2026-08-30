# P10.5 run 3 formal runtime-guard diagnosis

- Diagnostic status: `PASS`
- Immutable campaign status: `FAIL`
- Run ID: `p10_5_20260830T123451Z_e1f8c01a_4015142e_79607d01`
- Root cause: the board-reported TX-capable interval was exactly `1800.000 s`, while the old host guard compared the longer `1800.336 s` observation-to-terminal envelope against the `1800 s` limit.
- Direct formal case: `PASS`; both endpoints reported `1,800,000 ms`, zero formal transport timeouts, and zero integrity/protocol/DMA hard counters.
- Formal goodput: `4,300,326.684 bit/s` in each direction.
- Shutdown: fixed `PASS`, rotating `PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, `SHUTDOWN_EXIT=0`.
- Rest: `900.955 s` observed after shutdown, exceeding the required `900.168 s`, before any subsequent hardware action.
- Remediation: limit the exact TX-capable interval, retain the longer conservative envelope for cooldown, complete cooldown even on a fail-closed limit error, and prevent duplicate stage settlement.
- Artifact/RTL/firmware changes: `false`; this is a host-harness-only remediation.
- Run 3 is not retroactively promoted; a new immutable authorization and run are required.
