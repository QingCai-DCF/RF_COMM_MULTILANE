# P10.1 timer calibration and crosscheck

- Status: `PASS`
- Test ID: `P10_1-TIMER-CROSSCHECK`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`

## Clock sources

PL 64-bit free-running snapshots and PS global-timer snapshots agree within the 1% gate. Host monotonic time is retained only for host-orchestrated metrics, with its fixed command boundary explicit.

## Machine-readable evidence

`evidence/generated/p10_1_timer_crosscheck.json`
