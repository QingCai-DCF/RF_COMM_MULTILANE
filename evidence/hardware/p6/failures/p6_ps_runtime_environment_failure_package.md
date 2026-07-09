# P6 Failure Package

generated_at_utc: 2026-07-09T17:40:49+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `7a5f0ca068f983d85a6b85c95fa0d4fa3eee4ff2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: FAIL
reason: missing_rebuilt_top_xsa_ps7_platform
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

stage: p6_ps_runtime_environment
root-cause classification: missing_rebuilt_top_xsa_ps7_platform

## Last Payload

```json
{
  "P6_PS_RUNTIME_ENVIRONMENT": "BLOCKED_BY_RUNTIME_ENVIRONMENT",
  "reason": "no rebuilt-top XSA/PS7 hardware platform found outside legacy/imported evidence",
  "xsct": "D:\\Xilinx\\Vitis\\2023.1\\bin\\xsct.bat",
  "xsct_exists": true,
  "xsdb": "D:\\Xilinx\\Vitis\\2023.1\\bin\\xsdb.bat",
  "xsdb_exists": true,
  "runtime_source": "software/ps_driver/p6_runtime_mailbox.c",
  "runtime_source_sha256": "89db0842d774c5fa408f6953f1b72edab8a13b3299d55f3b9c8ee9e3c430e183",
  "rebuilt_xsa_candidates": [],
  "legacy_or_imported_xsa_candidates": [],
  "syntax_only_accepted_as_pass": false,
  "script_hardware_actions_executed": false,
  "source_evidence_contains_hardware_actions": false
}
```
