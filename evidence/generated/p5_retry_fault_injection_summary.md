# P5 Retry Fault Injection Summary

generated_at_utc: 2026-07-09T15:42:46+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS
reason: simulation-level retry/fault injection completed
hardware_actions_executed: false
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

RETRY_FAULT_INJECTION_SIM: PASS
RETRY_FAULT_INJECTION_HW_OPTIONAL: SKIP_NO_HW_FAULT_INJECTION_HOOK
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

| Case | Status | Retry Count | Retry Exhausted | CRC Bad | Expected Negative |
| --- | --- | --- | --- | --- | --- |
| drop_every_10th_ack | PASS | 2 | 0 | 0 | false |
| drop_first_ack_only | PASS | 1 | 0 | 0 | false |
| drop_first_data_only | PASS | 1 | 0 | 0 | false |
| force_crc_error_simulation_only | PASS | 1 | 0 | 1 | false |
| force_lane0_disable_via_register | PASS | 60 | 20 | 0 | true |
| force_lane1_disable_via_register | PASS | 60 | 20 | 0 | true |

## Boundary

- This is a deterministic simulation-level retry/fault injection model.
- It does not move hardware, block optical paths, program FPGA hardware, or claim hardware fault-injection PASS.
- Hardware fault injection remains `SKIP_NO_HW_FAULT_INJECTION_HOOK` until a real debug-register hook exists.
