# P7 final hardware acceptance summary

GENERATED_AT_UTC: 2026-07-17T03:30:50+00:00
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PASS
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PASS
STATIONARY_2LANE_APPLICATION_ACCEPTANCE: PASS
COMMIT: PENDING_FINAL_EVIDENCE_COMMIT
SOURCE_COMMIT: 911e1a303ff58593cac5ff4c4b70150d17f9a26b
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
PS_PL_PHY_PL_PS_APPLICATION_PASS: true
JTAG_AXI_AUXILIARY_PATH_PASS: true
JTAG_AXI_PL_PHY_PL_PASS: true
FRAGMENTATION_REASSEMBLY: PASS
FILE_INTEGRITY_SHA256: PASS
QUEUE_BACKPRESSURE: PASS
SOFTWARE_LANE_FALLBACK: PASS
STATIONARY_30MIN: PASS
SHUTDOWN_BEFORE: PASS
SHUTDOWN_AFTER: PASS
BITSTREAM_SHA256: 756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a
PS_ELF_SHA256: 2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949
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
| ps_runtime | PASS | real PS ELF completed the full large-object policy/pattern matrix |
| lane_fallback | PASS | software-injected scheduler fallback and strict-negative cases passed |
| abort_restart | PASS | abort, shutdown, new-epoch restart, atomicity, and replay rejection passed |
| queue_backpressure | PASS | depth-1/depth-8/FIFO/overflow/STOP/ABORT queue cases passed |
| calibration | PASS | the first 300 seconds of the same unique run supplied exactly ten clean calibration samples |
| stationary | PASS | the unique real-PS stationary run completed the exact 1800-second 300+1500 contract |
| application_metrics | PASS | bytes, goodput, latency, queue, retry, safety, and lane metrics are complete and source-labeled |
| shutdown | PASS | every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker |
| consistency | PASS | all selected summaries, raw records, hashes, targets, commits, risk order, and stationary-run cardinality agree |

## PASS

- safe_idle: fresh safe-idle readback and both shutdown barriers passed
- p6_frame_regression: strict raw-log-bound backend parses prove at least ten P6 frames on masks 0x1/0x2/0x3
- fragment_boundary: direct-JTAG strict parser passed all 12 boundary lengths on lane0/lane1/stripe/replicate
- large_object_jtag: strict safe-wrapper + raw-log-bound backend parser passed the required 1 MiB/64 KiB matrix
- ps_runtime: real PS ELF completed the full large-object policy/pattern matrix
- lane_fallback: software-injected scheduler fallback and strict-negative cases passed
- abort_restart: abort, shutdown, new-epoch restart, atomicity, and replay rejection passed
- queue_backpressure: depth-1/depth-8/FIFO/overflow/STOP/ABORT queue cases passed
- calibration: the first 300 seconds of the same unique run supplied exactly ten clean calibration samples
- stationary: the unique real-PS stationary run completed the exact 1800-second 300+1500 contract
- application_metrics: bytes, goodput, latency, queue, retry, safety, and lane metrics are complete and source-labeled
- shutdown: every hardware-mutating run has rc=0 plus a fresh TFDU shutdown marker
- consistency: all selected summaries, raw records, hashes, targets, commits, risk order, and stationary-run cardinality agree

## FAIL

- None.

## SKIP_WITH_REASON

- None.

## PENDING_HW

- None.

## GENERATED_SUMMARIES

- `evidence/generated/p7_30min_calibration_summary.json`
- `evidence/generated/p7_30min_calibration_summary.md`
- `evidence/generated/p7_abort_restart_atomicity_summary.json`
- `evidence/generated/p7_abort_restart_atomicity_summary.md`
- `evidence/generated/p7_abort_restart_hw_summary.json`
- `evidence/generated/p7_abort_restart_hw_summary.md`
- `evidence/generated/p7_abort_restart_summary.json`
- `evidence/generated/p7_abort_restart_summary.md`
- `evidence/generated/p7_application_30min_stationary_summary.json`
- `evidence/generated/p7_application_30min_stationary_summary.md`
- `evidence/generated/p7_application_metrics_summary.json`
- `evidence/generated/p7_application_metrics_summary.md`
- `evidence/generated/p7_artifact_provenance_summary.json`
- `evidence/generated/p7_artifact_provenance_summary.md`
- `evidence/generated/p7_calibration_5min_embedded_summary.json`
- `evidence/generated/p7_calibration_5min_embedded_summary.md`
- `evidence/generated/p7_evidence_consistency_summary.json`
- `evidence/generated/p7_evidence_consistency_summary.md`
- `evidence/generated/p7_final_acceptance_summary.json`
- `evidence/generated/p7_final_acceptance_summary.md`
- `evidence/generated/p7_final_summary.json`
- `evidence/generated/p7_final_summary.md`
- `evidence/generated/p7_fragment_boundary_hw_summary.json`
- `evidence/generated/p7_fragment_boundary_hw_summary.md`
- `evidence/generated/p7_fragment_boundary_matrix_summary.json`
- `evidence/generated/p7_fragment_boundary_matrix_summary.md`
- `evidence/generated/p7_hardware_authorization_summary.json`
- `evidence/generated/p7_hardware_authorization_summary.md`
- `evidence/generated/p7_hardware_evidence_summary.json`
- `evidence/generated/p7_lane_fallback_hw_summary.json`
- `evidence/generated/p7_lane_fallback_hw_summary.md`
- `evidence/generated/p7_lane_fault_fallback_summary.json`
- `evidence/generated/p7_lane_fault_fallback_summary.md`
- `evidence/generated/p7_lane_scheduler_fallback_summary.json`
- `evidence/generated/p7_lane_scheduler_fallback_summary.md`
- `evidence/generated/p7_large_object_jtag_summary.json`
- `evidence/generated/p7_large_object_jtag_summary.md`
- `evidence/generated/p7_large_object_summary.json`
- `evidence/generated/p7_large_object_summary.md`
- `evidence/generated/p7_p6_frame_regression_summary.json`
- `evidence/generated/p7_p6_frame_regression_summary.md`
- `evidence/generated/p7_performance_summary.json`
- `evidence/generated/p7_performance_summary.md`
- `evidence/generated/p7_provenance.json`
- `evidence/generated/p7_provenance.md`
- `evidence/generated/p7_ps_app_runtime_summary.json`
- `evidence/generated/p7_ps_app_runtime_summary.md`
- `evidence/generated/p7_ps_runtime_hw_summary.json`
- `evidence/generated/p7_ps_runtime_hw_summary.md`
- `evidence/generated/p7_queue_backpressure_hw_summary.json`
- `evidence/generated/p7_queue_backpressure_hw_summary.md`
- `evidence/generated/p7_queue_backpressure_summary.json`
- `evidence/generated/p7_queue_backpressure_summary.md`
- `evidence/generated/p7_result_consistency_summary.json`
- `evidence/generated/p7_result_consistency_summary.md`
- `evidence/generated/p7_safe_idle_recheck_summary.json`
- `evidence/generated/p7_safe_idle_recheck_summary.md`
- `evidence/generated/p7_shutdown_evidence_summary.json`
- `evidence/generated/p7_shutdown_evidence_summary.md`
- `evidence/generated/p7_shutdown_summary.json`
- `evidence/generated/p7_shutdown_summary.md`
- `evidence/generated/p7_stationary_30min_summary.json`
- `evidence/generated/p7_stationary_30min_summary.md`
- `evidence/generated/p7_stationary_app_30min_soak_summary.json`
- `evidence/generated/p7_stationary_app_30min_soak_summary.md`
- `evidence/generated/p7_stationary_local_application_layer_summary.json`
- `evidence/generated/p7_stationary_local_application_layer_summary.md`

NEXT_RECOMMENDED_STAGE: FINAL_EVIDENCE_COMMIT

## Boundary

This result is limited to a stationary, local, two-lane application path. It does not prove Ethernet, rotation, eight-lane operation, or product-final acceptance. JTAG/AXI is auxiliary; only the real PS ELF/runtime path can set `PS_PL_PHY_PL_PS_APPLICATION_PASS: true`.
