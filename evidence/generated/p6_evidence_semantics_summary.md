# P6 Evidence Semantics Summary

generated_at_utc: 2026-07-10T09:15:15+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b90d41a6750aad8023071433996fee3f068efe2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: hardware source evidence fields are separated from generator actions
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

P6_EVIDENCE_SEMANTICS: PASS

## Unified Fields

- script_hardware_actions_executed: false
- source_evidence_contains_hardware_actions: true
- stage_programmed_fpga: false
- stage_drove_tfdu_txd: false
- stage_enabled_tfdu_receiver: false
- shutdown_on_exit_observed: false
- product_final_acceptance: pending

## Boundary

- P5 evidence source can contain hardware actions even when a P6 parser/generator action itself does not touch hardware.
- P6 product-final acceptance remains pending regardless of stationary 2-lane local evidence.
