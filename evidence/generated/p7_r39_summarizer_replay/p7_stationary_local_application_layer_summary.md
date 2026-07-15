# P7 final hardware acceptance summary

GENERATED_AT_UTC: 2026-07-15T01:13:23+00:00
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: FAIL
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: FAIL
STATIONARY_2LANE_APPLICATION_ACCEPTANCE: FAIL
COMMIT: PENDING_FINAL_EVIDENCE_COMMIT
SOURCE_COMMIT: 0539667cfbaa29a8ddb0b137bb9d4b222f1e4eb4
USER_HARDWARE_AUTHORIZATION_FOR_P7: GRANTED
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
NO_ETHERNET_USED: true
NO_HARDWARE_MOVEMENT: true
AVAILABLE_LANES: 2
AVAILABLE_PHYSICAL_LANES: 2
MAX_LANE_MASK: 0x3
MAX_LANE_MASK_USED: 0x3
HARDWARE_ACTIONS_EXECUTED: true
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
BITSTREAM_SHA256: 34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249
PS_ELF_SHA256: 47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## Gate results

| Gate | Result | Reason |
|---|---|---|
| safe_idle | FAIL | safe-idle evidence failed closed |
| p6_frame_regression | FAIL | P6 frame regression evidence failed closed |
| fragment_boundary | PENDING_HW | direct-JTAG 12-length x 4-policy boundary matrix is missing |
| large_object_jtag | FAIL | direct JTAG large-object evidence failed closed |
| ps_runtime | FAIL | real PS runtime or its redundant boundary regression failed closed |
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

- safe_idle: safe-idle evidence failed closed
- p6_frame_regression: P6 frame regression evidence failed closed
- large_object_jtag: direct JTAG large-object evidence failed closed
- ps_runtime: real PS runtime or its redundant boundary regression failed closed
- consistency: evidence consistency failed closed

## SKIP_WITH_REASON

- None.

## PENDING_HW

- fragment_boundary: direct-JTAG 12-length x 4-policy boundary matrix is missing
- lane_fallback: lane_fallback hardware stage is missing
- abort_restart: abort_restart hardware stage is missing
- queue_backpressure: queue_backpressure hardware stage is missing
- calibration: embedded 300-second calibration window is missing
- stationary: the unique 1800-second real-PS stationary run is missing
- application_metrics: stationary application metrics are missing

## GENERATED_SUMMARIES

- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_30min_calibration_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_30min_calibration_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_abort_restart_atomicity_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_abort_restart_atomicity_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_abort_restart_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_abort_restart_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_abort_restart_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_abort_restart_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_application_30min_stationary_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_application_30min_stationary_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_application_metrics_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_application_metrics_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_artifact_provenance_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_artifact_provenance_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_calibration_5min_embedded_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_calibration_5min_embedded_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_evidence_consistency_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_evidence_consistency_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_final_acceptance_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_final_acceptance_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_final_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_final_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_fragment_boundary_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_fragment_boundary_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_fragment_boundary_matrix_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_fragment_boundary_matrix_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_hardware_authorization_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_hardware_authorization_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_hardware_evidence_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_lane_fallback_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_lane_fallback_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_lane_fault_fallback_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_lane_fault_fallback_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_lane_scheduler_fallback_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_lane_scheduler_fallback_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_large_object_jtag_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_large_object_jtag_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_large_object_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_large_object_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_p6_frame_regression_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_p6_frame_regression_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_performance_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_performance_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_provenance.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_provenance.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_ps_app_runtime_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_ps_app_runtime_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_ps_runtime_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_ps_runtime_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_queue_backpressure_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_queue_backpressure_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_queue_backpressure_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_queue_backpressure_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_result_consistency_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_result_consistency_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_safe_idle_recheck_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_safe_idle_recheck_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_shutdown_evidence_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_shutdown_evidence_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_shutdown_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_shutdown_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_stationary_30min_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_stationary_30min_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_stationary_app_30min_soak_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_stationary_app_30min_soak_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_stationary_local_application_layer_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r39_summarizer_replay/p7_stationary_local_application_layer_summary.md`

NEXT_RECOMMENDED_STAGE: REMEDIATE_SAFE_IDLE

## Boundary

This result is limited to a stationary, local, two-lane application path. It does not prove Ethernet, rotation, eight-lane operation, or product-final acceptance. JTAG/AXI is auxiliary; only the real PS ELF/runtime path can set `PS_PL_PHY_PL_PS_APPLICATION_PASS: true`.
