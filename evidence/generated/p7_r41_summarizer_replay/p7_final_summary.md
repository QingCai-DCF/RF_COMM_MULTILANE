# P7 final hardware acceptance summary

GENERATED_AT_UTC: 2026-07-15T11:52:06+00:00
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: FAIL
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: FAIL
STATIONARY_2LANE_APPLICATION_ACCEPTANCE: FAIL
COMMIT: PENDING_FINAL_EVIDENCE_COMMIT
SOURCE_COMMIT: 946ccbad66d64d715ad6745449b95f6c261ddf76
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
FRAGMENTATION_REASSEMBLY: PASS
FILE_INTEGRITY_SHA256: FAIL
QUEUE_BACKPRESSURE: PASS
SOFTWARE_LANE_FALLBACK: FAIL
STATIONARY_30MIN: FAIL
SHUTDOWN_BEFORE: PASS
SHUTDOWN_AFTER: PASS
BITSTREAM_SHA256: 532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0
PS_ELF_SHA256: 3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## Gate results

| Gate | Result | Reason |
|---|---|---|
| safe_idle | PASS | fresh safe-idle readback and both shutdown barriers passed |
| p6_frame_regression | PASS | strict raw-log-bound backend parses prove at least ten P6 frames on masks 0x1/0x2/0x3 |
| fragment_boundary | PASS | direct-JTAG strict parser passed all 12 boundary lengths on lane0/lane1/stripe/replicate |
| large_object_jtag | PASS | strict safe-wrapper + raw-log-bound backend parser passed the required 1 MiB/64 KiB matrix |
| ps_runtime | FAIL | real PS runtime or its redundant boundary regression failed closed |
| lane_fallback | FAIL | lane_fallback evidence failed closed |
| abort_restart | FAIL | abort_restart evidence failed closed |
| queue_backpressure | PASS | depth-1/depth-8/FIFO/overflow/STOP/ABORT queue cases passed |
| calibration | FAIL | no unique qualified stationary run can own calibration |
| stationary | FAIL | no unique qualified stationary PASS exists |
| application_metrics | FAIL | no unique qualified stationary run can own metrics |
| shutdown | PASS | every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker |
| consistency | FAIL | evidence consistency failed closed |

## PASS

- safe_idle: fresh safe-idle readback and both shutdown barriers passed
- p6_frame_regression: strict raw-log-bound backend parses prove at least ten P6 frames on masks 0x1/0x2/0x3
- fragment_boundary: direct-JTAG strict parser passed all 12 boundary lengths on lane0/lane1/stripe/replicate
- large_object_jtag: strict safe-wrapper + raw-log-bound backend parser passed the required 1 MiB/64 KiB matrix
- queue_backpressure: depth-1/depth-8/FIFO/overflow/STOP/ABORT queue cases passed
- shutdown: every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker

## FAIL

- ps_runtime: real PS runtime or its redundant boundary regression failed closed
- lane_fallback: lane_fallback evidence failed closed
- abort_restart: abort_restart evidence failed closed
- calibration: no unique qualified stationary run can own calibration
- stationary: no unique qualified stationary PASS exists
- application_metrics: no unique qualified stationary run can own metrics
- consistency: evidence consistency failed closed

## SKIP_WITH_REASON

- None.

## PENDING_HW

- None.

## GENERATED_SUMMARIES

- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_30min_calibration_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_30min_calibration_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_abort_restart_atomicity_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_abort_restart_atomicity_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_abort_restart_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_abort_restart_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_abort_restart_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_abort_restart_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_application_30min_stationary_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_application_30min_stationary_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_application_metrics_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_application_metrics_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_artifact_provenance_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_artifact_provenance_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_calibration_5min_embedded_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_calibration_5min_embedded_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_evidence_consistency_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_evidence_consistency_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_final_acceptance_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_final_acceptance_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_final_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_final_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_fragment_boundary_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_fragment_boundary_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_fragment_boundary_matrix_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_fragment_boundary_matrix_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_hardware_authorization_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_hardware_authorization_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_hardware_evidence_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_lane_fallback_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_lane_fallback_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_lane_fault_fallback_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_lane_fault_fallback_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_lane_scheduler_fallback_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_lane_scheduler_fallback_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_large_object_jtag_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_large_object_jtag_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_large_object_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_large_object_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_p6_frame_regression_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_p6_frame_regression_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_performance_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_performance_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_provenance.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_provenance.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_ps_app_runtime_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_ps_app_runtime_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_ps_runtime_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_ps_runtime_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_queue_backpressure_hw_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_queue_backpressure_hw_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_queue_backpressure_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_queue_backpressure_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_result_consistency_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_result_consistency_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_safe_idle_recheck_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_safe_idle_recheck_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_shutdown_evidence_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_shutdown_evidence_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_shutdown_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_shutdown_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_stationary_30min_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_stationary_30min_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_stationary_app_30min_soak_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_stationary_app_30min_soak_summary.md`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_stationary_local_application_layer_summary.json`
- `C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/p7_r41_summarizer_replay/p7_stationary_local_application_layer_summary.md`

NEXT_RECOMMENDED_STAGE: REMEDIATE_PS_RUNTIME

## Boundary

This result is limited to a stationary, local, two-lane application path. It does not prove Ethernet, rotation, eight-lane operation, or product-final acceptance. JTAG/AXI is auxiliary; only the real PS ELF/runtime path can set `PS_PL_PHY_PL_PS_APPLICATION_PASS: true`.
