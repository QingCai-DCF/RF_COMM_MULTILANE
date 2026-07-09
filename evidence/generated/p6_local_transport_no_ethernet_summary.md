# P6 Local Transport No-Ethernet Summary

generated_at_utc: 2026-07-09T16:51:25+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b863a2377f4dbb6dd70bcf8064f138739cf0d00`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: FAIL
reason: P6 dynamic local transport backend is missing; completed safe gates and evidence boundary
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

P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET: FAIL
COMMIT: 5b863a2377f4dbb6dd70bcf8064f138739cf0d00
USER_CONFIRMED_SUPPLY_OK: true
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3
HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: PENDING
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## PASS

- P6_P5_INTAKE
- P6_EVIDENCE_SEMANTICS
- P6_PROFILES
- P6_DYNAMIC_PAYLOAD_SIM
- P6_BITSTREAM_PROVENANCE
- P6_NO_ETHERNET
- P6_NO_MOTION
- P6_2LANE_SCOPE
- P6_HOST_FILE_PAYLOADS
- P6_HARDWARE_EXECUTION
- P6_SAFE_IDLE_RECHECK
- P6_TFDU_CONTROL_IDLE_RECHECK
- P6_PROTOCOL_METRICS
- P6_EVIDENCE_CONSISTENCY
- P6_PROJECT_STATUS_UPDATE
- P6_RESULTS_PACKAGE

## FAIL

- P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET

## SKIP_WITH_REASON

- none

## BLOCKED

- P6_JTAG_AXI_PAYLOAD_RAM_SMOKE
- P6_LANE0_DYNAMIC_PAYLOAD
- P6_LANE1_DYNAMIC_PAYLOAD
- P6_TWO_LANE_DYNAMIC_PAYLOAD
- P6_PS_DRIVER_RUNTIME
- P6_HOST_FILE_TRANSPORT_JTAG
- P6_LANE_FALLBACK_REGRESSION
- P6_TWO_LANE_2H_STATIONARY_SOAK

## Generated Summaries

- `evidence/generated/p6_2lane_scope_summary.md`
- `evidence/generated/p6_bitstream_provenance_summary.md`
- `evidence/generated/p6_dynamic_payload_sim_summary.md`
- `evidence/generated/p6_evidence_consistency_summary.md`
- `evidence/generated/p6_evidence_semantics_summary.md`
- `evidence/generated/p6_hardware_authorization_summary.md`
- `evidence/generated/p6_hardware_execution_summary.md`
- `evidence/generated/p6_host_file_transport_jtag_summary.md`
- `evidence/generated/p6_jtag_axi_payload_ram_smoke_summary.md`
- `evidence/generated/p6_lane0_dynamic_payload_summary.md`
- `evidence/generated/p6_lane1_dynamic_payload_summary.md`
- `evidence/generated/p6_lane_fallback_regression_summary.md`
- `evidence/generated/p6_local_transport_no_ethernet_summary.md`
- `evidence/generated/p6_no_ethernet_summary.md`
- `evidence/generated/p6_no_motion_summary.md`
- `evidence/generated/p6_p5_intake_summary.md`
- `evidence/generated/p6_profiles_summary.md`
- `evidence/generated/p6_project_status_update_summary.md`
- `evidence/generated/p6_protocol_metrics_summary.md`
- `evidence/generated/p6_ps_driver_runtime_summary.md`
- `evidence/generated/p6_safe_idle_recheck_summary.md`
- `evidence/generated/p6_tfdu_control_idle_recheck_summary.md`
- `evidence/generated/p6_two_lane_2h_stationary_soak_summary.md`
- `evidence/generated/p6_two_lane_dynamic_payload_summary.md`

NEXT_RECOMMENDED_STAGE: P6_FIX_DYNAMIC_PAYLOAD_DATAPATH
