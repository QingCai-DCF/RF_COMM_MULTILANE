# P6 Hardware Execution Summary

generated_at_utc: 2026-07-10T09:15:55+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b90d41a6750aad8023071433996fee3f068efe2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: existing authorized stage evidence aggregated without new hardware actions
script_hardware_actions_executed: false
source_evidence_contains_hardware_actions: true
stage_programmed_fpga: false
stage_drove_tfdu_txd: false
stage_enabled_tfdu_receiver: false
shutdown_on_exit_observed: false
product_final_acceptance: pending
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
max_lane_mask: 0x3

P6_HARDWARE_EXECUTION: PASS
HARDWARE_ACTIONS_EXECUTED: true
SHUTDOWN_ON_EXIT: PASS
STOP_CONDITIONS_TRIGGERED: none

## Executed stages

- P6_SAFE_IDLE_RECHECK
- P6_TFDU_CONTROL_IDLE_RECHECK
- P6_JTAG_AXI_PAYLOAD_RAM_SMOKE
- P6_LANE0_DYNAMIC_PAYLOAD
- P6_LANE1_DYNAMIC_PAYLOAD
- P6_TWO_LANE_DYNAMIC_PAYLOAD
- P6_PS_DRIVER_RUNTIME
- P6_HOST_FILE_TRANSPORT_JTAG
- P6_LANE_FALLBACK_REGRESSION
- P6_TWO_LANE_2H_STATIONARY_SOAK

## Blocked stages
