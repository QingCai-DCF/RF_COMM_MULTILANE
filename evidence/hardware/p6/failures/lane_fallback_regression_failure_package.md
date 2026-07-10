# P6 Failure Package

generated_at_utc: 2026-07-10T02:24:28+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b90d41a6750aad8023071433996fee3f068efe2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: FAIL
reason: BLOCKED_BY_RUNTIME_ENVIRONMENT:P6 bounded negative cases pass register-level simulation, but hardware fallback regression cannot run without live register write/read ingress
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

stage: lane_fallback_regression
root-cause classification: BLOCKED_BY_RUNTIME_ENVIRONMENT:P6 bounded negative cases pass register-level simulation, but hardware fallback regression cannot run without live register write/read ingress

## Last Payload

```json
{
  "P6_LANE_FALLBACK_REGRESSION": "BLOCKED_BY_RUNTIME_ENVIRONMENT",
  "reason": "P6 bounded negative cases pass register-level simulation, but hardware fallback regression cannot run without live register write/read ingress",
  "script_hardware_actions_executed": false,
  "source_evidence_contains_hardware_actions": false,
  "stage_programmed_fpga": false,
  "stage_drove_tfdu_txd": false,
  "stage_enabled_tfdu_receiver": false,
  "shutdown_on_exit_observed": false,
  "product_final_acceptance": "pending",
  "evidence_dir": "evidence/hardware/p6/lane_fallback_regression",
  "summary": "evidence/generated/p6_lane_fallback_regression_summary.md"
}
```
