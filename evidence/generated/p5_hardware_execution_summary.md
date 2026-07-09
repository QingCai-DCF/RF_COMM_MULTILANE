# P5 Hardware Execution Summary

generated_at_utc: 2026-07-09T15:42:46+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS_WITH_NOTES
reason: authorized P5 hardware execution summary
hardware_actions_executed: true
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

P5_HARDWARE_EXECUTION: PASS_WITH_NOTES
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
SHUTDOWN_ON_EXIT: PASS
STOP_CONDITIONS_TRIGGERED: none

## Stages

- `safe_idle_recheck` -> PASS
- `tfdu_control_idle_recheck` -> PASS
- `raw_lane_matrix_fresh` -> PASS
- `lane0_frame_crc_100` -> PASS
- `lane1_frame_crc_100` -> PASS
- `lane0_ack_retry_100` -> PASS
- `lane1_ack_retry_100` -> PASS
- `two_lane_minimal_100` -> PASS
- `payload_sweep` -> PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED
- `mask_regression` -> PASS
- `two_lane_30min_soak` -> PASS
