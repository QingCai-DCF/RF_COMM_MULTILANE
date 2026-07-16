# P7 final hardware acceptance summary

GENERATED_AT_UTC: 2026-07-16T16:36:25+00:00
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: FAIL
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: FAIL
STATIONARY_2LANE_APPLICATION_ACCEPTANCE: FAIL
COMMIT: PENDING_FINAL_EVIDENCE_COMMIT
SOURCE_COMMIT: INCONSISTENT_OR_MISSING
USER_HARDWARE_AUTHORIZATION_FOR_P7: GRANTED
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
NO_ETHERNET_USED: true
NO_HARDWARE_MOVEMENT: true
AVAILABLE_LANES: 2
AVAILABLE_PHYSICAL_LANES: 2
MAX_LANE_MASK: 0x3
MAX_LANE_MASK_USED: 0x3
HARDWARE_ACTIONS_EXECUTED: false
PS_PL_PHY_PL_PS_APPLICATION_PASS: false
JTAG_AXI_AUXILIARY_PATH_PASS: false
JTAG_AXI_PL_PHY_PL_PASS: false
FRAGMENTATION_REASSEMBLY: PENDING_HW
FILE_INTEGRITY_SHA256: FAIL
QUEUE_BACKPRESSURE: PENDING_HW
SOFTWARE_LANE_FALLBACK: PENDING_HW
STATIONARY_30MIN: PENDING_HW
SHUTDOWN_BEFORE: PASS
SHUTDOWN_AFTER: PASS
BITSTREAM_SHA256: INCONSISTENT_OR_MISSING
PS_ELF_SHA256: INCONSISTENT_OR_MISSING
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## Gate results

| Gate | Result | Reason |
|---|---|---|
| safe_idle | PENDING_HW | safe-idle hardware stage is missing |
| p6_frame_regression | PENDING_HW | P6 one-frame lane-mask regression is missing |
| fragment_boundary | PENDING_HW | direct-JTAG 12-length x 4-policy boundary matrix is missing |
| large_object_jtag | PENDING_HW | no fresh direct JTAG/AXI large-object safe-wrapper evidence |
| ps_runtime | PENDING_HW | real PS functional runtime hardware stage is missing |
| lane_fallback | PENDING_HW | lane_fallback hardware stage is missing |
| abort_restart | PENDING_HW | abort_restart hardware stage is missing |
| queue_backpressure | PENDING_HW | queue_backpressure hardware stage is missing |
| calibration | PENDING_HW | embedded 300-second calibration window is missing |
| stationary | PENDING_HW | the unique 1800-second real-PS stationary run is missing |
| application_metrics | PENDING_HW | stationary application metrics are missing |
| shutdown | PASS | every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker |
| consistency | FAIL | evidence consistency failed closed |

## PASS

- shutdown: every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker

## FAIL

- consistency: evidence consistency failed closed

## SKIP_WITH_REASON

- None.

## PENDING_HW

- safe_idle: safe-idle hardware stage is missing
- p6_frame_regression: P6 one-frame lane-mask regression is missing
- fragment_boundary: direct-JTAG 12-length x 4-policy boundary matrix is missing
- large_object_jtag: no fresh direct JTAG/AXI large-object safe-wrapper evidence
- ps_runtime: real PS functional runtime hardware stage is missing
- lane_fallback: lane_fallback hardware stage is missing
- abort_restart: abort_restart hardware stage is missing
- queue_backpressure: queue_backpressure hardware stage is missing
- calibration: embedded 300-second calibration window is missing
- stationary: the unique 1800-second real-PS stationary run is missing
- application_metrics: stationary application metrics are missing

## GENERATED_SUMMARIES

- `build/p7_r72_stage66_c06_summarizer_terminal/p7_30min_calibration_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_30min_calibration_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_abort_restart_atomicity_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_abort_restart_atomicity_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_abort_restart_hw_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_abort_restart_hw_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_abort_restart_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_abort_restart_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_application_30min_stationary_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_application_30min_stationary_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_application_metrics_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_application_metrics_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_artifact_provenance_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_artifact_provenance_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_calibration_5min_embedded_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_calibration_5min_embedded_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_evidence_consistency_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_evidence_consistency_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_final_acceptance_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_final_acceptance_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_final_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_final_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_fragment_boundary_hw_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_fragment_boundary_hw_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_fragment_boundary_matrix_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_fragment_boundary_matrix_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_hardware_authorization_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_hardware_authorization_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_hardware_evidence_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_lane_fallback_hw_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_lane_fallback_hw_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_lane_fault_fallback_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_lane_fault_fallback_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_lane_scheduler_fallback_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_lane_scheduler_fallback_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_large_object_jtag_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_large_object_jtag_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_large_object_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_large_object_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_p6_frame_regression_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_p6_frame_regression_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_performance_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_performance_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_provenance.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_provenance.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_ps_app_runtime_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_ps_app_runtime_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_ps_runtime_hw_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_ps_runtime_hw_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_queue_backpressure_hw_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_queue_backpressure_hw_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_queue_backpressure_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_queue_backpressure_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_result_consistency_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_result_consistency_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_safe_idle_recheck_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_safe_idle_recheck_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_shutdown_evidence_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_shutdown_evidence_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_shutdown_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_shutdown_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_stationary_30min_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_stationary_30min_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_stationary_app_30min_soak_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_stationary_app_30min_soak_summary.md`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_stationary_local_application_layer_summary.json`
- `build/p7_r72_stage66_c06_summarizer_terminal/p7_stationary_local_application_layer_summary.md`

NEXT_RECOMMENDED_STAGE: REMEDIATE_CONSISTENCY

## Boundary

This result is limited to a stationary, local, two-lane application path. It does not prove Ethernet, rotation, eight-lane operation, or product-final acceptance. JTAG/AXI is auxiliary; only the real PS ELF/runtime path can set `PS_PL_PHY_PL_PS_APPLICATION_PASS: true`.
