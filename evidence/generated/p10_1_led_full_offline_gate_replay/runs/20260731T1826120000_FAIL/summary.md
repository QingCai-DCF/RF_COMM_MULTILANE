# P10.1 AX7020 PL activity LED full offline gate replay

- Status: `FAIL`
- Detached source commit: `201a05e199a56e785a06d61910d42139fa0248e5`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`
- Replay environment: disposable detached Git worktree

## Commands

- `p10_1_full_offline_gate`: `FAIL` (`903.981 s`, `evidence/generated/p10_1_led_full_offline_gate_replay/raw/p10_1_full_offline_gate.log`)
- `canonical_p0_p8b_offline_regression`: `FAIL` (`3310.131 s`, `evidence/generated/p10_1_led_full_offline_gate_replay/raw/canonical_p0_p8b_offline_regression.log`)

## Errors

- p10_1_full_offline_gate returned 1
- canonical_p0_p8b_offline_regression returned 1
- missing P10.1 full-gate marker: p10_1_offline_gate_pass

This replay is offline evidence only. It does not reuse or promote any historical hardware result for the LED-enabled artifacts.
