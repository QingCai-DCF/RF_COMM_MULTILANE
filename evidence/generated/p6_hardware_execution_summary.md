# P6 Hardware Execution Summary

generated_at_utc: 2026-07-09T16:48:49+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b863a2377f4dbb6dd70bcf8064f138739cf0d00`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS_WITH_NOTES
reason: authorized P6 hardware stages executed until missing dynamic payload backend boundary
script_hardware_actions_executed: true
source_evidence_contains_hardware_actions: true
stage_programmed_fpga: see stage section
stage_drove_tfdu_txd: see stage section
stage_enabled_tfdu_receiver: see stage section
shutdown_on_exit_observed: see stage section
product_final_acceptance: pending
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
max_lane_mask: 0x3

P6_HARDWARE_EXECUTION: PASS_WITH_NOTES
HARDWARE_ACTIONS_EXECUTED: true
SHUTDOWN_ON_EXIT: PASS
STOP_CONDITIONS_TRIGGERED: p6_dynamic_payload_backend_missing

## Executed Stages

- `safe_idle_recheck`
- `tfdu_control_idle_recheck`

## Blocked Stages

- `P6_JTAG_AXI_PAYLOAD_RAM_SMOKE`
- `P6_LANE0_DYNAMIC_PAYLOAD`
- `P6_LANE1_DYNAMIC_PAYLOAD`
- `P6_TWO_LANE_DYNAMIC_PAYLOAD`
- `P6_PS_DRIVER_RUNTIME`
- `P6_HOST_FILE_TRANSPORT_JTAG`
- `P6_LANE_FALLBACK_REGRESSION`
- `P6_TWO_LANE_2H_STATIONARY_SOAK`
