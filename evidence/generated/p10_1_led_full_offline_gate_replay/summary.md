# P10.1 AX7020 PL activity LED full offline gate replay

- Status: `FAIL`
- Detached source commit: `88e28a24cbd6b13fba052c4fe7c0debd13c7b2c4`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`
- Replay environment: disposable detached Git worktree

## Commands

- `p10_1_full_offline_gate`: `PASS` (`1526.499 s`, `evidence/generated/p10_1_led_full_offline_gate_replay/raw/p10_1_full_offline_gate.log`)
- `canonical_p0_p8b_offline_regression`: `FAIL` (`3404.033 s`, `evidence/generated/p10_1_led_full_offline_gate_replay/raw/canonical_p0_p8b_offline_regression.log`)

## Errors

- canonical_p0_p8b_offline_regression returned 1

This replay is offline evidence only. It does not reuse or promote any historical hardware result for the LED-enabled artifacts.
