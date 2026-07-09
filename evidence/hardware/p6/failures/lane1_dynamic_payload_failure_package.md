# P6 Failure Package

generated_at_utc: 2026-07-09T17:45:41+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `7a5f0ca068f983d85a6b85c95fa0d4fa3eee4ff2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: FAIL
reason: BLOCKED_BY_RUNTIME_ENVIRONMENT:P6 dynamic payload datapath is implemented for register-level simulation, but lane1 hardware transport cannot be driven without live JTAG/AXI or PS runtime integration
script_hardware_actions_executed: false
source_evidence_contains_hardware_actions: false
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

stage: lane1_dynamic_payload
root-cause classification: BLOCKED_BY_RUNTIME_ENVIRONMENT:P6 dynamic payload datapath is implemented for register-level simulation, but lane1 hardware transport cannot be driven without live JTAG/AXI or PS runtime integration

## Last Payload

```json
{
  "P6_LANE1_DYNAMIC_PAYLOAD": "BLOCKED_BY_RUNTIME_ENVIRONMENT",
  "reason": "P6 dynamic payload datapath is implemented for register-level simulation, but lane1 hardware transport cannot be driven without live JTAG/AXI or PS runtime integration",
  "script_hardware_actions_executed": false,
  "source_evidence_contains_hardware_actions": false,
  "stage_programmed_fpga": false,
  "stage_drove_tfdu_txd": false,
  "stage_enabled_tfdu_receiver": false,
  "shutdown_on_exit_observed": false,
  "product_final_acceptance": "pending",
  "evidence_dir": "evidence/hardware/p6/protocol/lane1_dynamic_payload",
  "summary": "evidence/generated/p6_lane1_dynamic_payload_summary.md"
}
```
