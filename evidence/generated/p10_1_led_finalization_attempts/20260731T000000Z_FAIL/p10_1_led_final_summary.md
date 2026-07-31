# P10.1 AX7020 PL activity LED final offline checkpoint

- Status: `FAIL`
- Test ID: `P10_1-LED-FINAL-OFFLINE-CHECKPOINT`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`

Offline implementation, simulation, fixed/rotating routed builds, software builds, safety regression, and isolated complete-gate replay are closed.

The new bitstreams have no hardware PASS yet. Direct current-run hardware validation must use a separate authorization bound to the exact artifact hashes.

## Errors

- tfdu_safety_regression: hardware_actions_executed is not false
- tfdu_safety_regression: current_run_hardware_authorization is not false
