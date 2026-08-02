# P8D acceptance core

- Status: `PASS`
- Test ID: `P8D-ACCEPTANCE-CORE`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "exit_gates": {
    "19P2MBPS_STRETCH_FEASIBILITY": "FAIL",
    "8LANE_16MBPS_ARCHITECTURE_FEASIBILITY": "PASS",
    "ACKED_FRAME_NEVER_MIGRATES": "PASS",
    "ACK_AGGREGATION": "PASS",
    "ACK_LOSS_RECOVERY": "PASS",
    "AGGREGATE_AXI_STREAM": "PASS",
    "AIRTIME_BUDGET_MODEL": "PASS",
    "AXIS_NO_LOSS_NO_DUPLICATE": "PASS",
    "AXIS_RANDOM_BACKPRESSURE": "PASS",
    "BOUNDED_SELECTIVE_REPEAT_RX": "PASS",
    "BOUNDED_SELECTIVE_REPEAT_TX": "PASS",
    "DESCRIPTOR_LEAK_ZERO": "PASS",
    "DESCRIPTOR_SINGLE_COMPLETION": "PASS",
    "DMA_DESCRIPTOR_RING_MODEL": "PASS",
    "DUPLICATE_APPLICATION_DELIVERY_ZERO": "PASS",
    "EVIDENCE_CONSISTENCY": "PASS",
    "GLOBAL_OUTSTANDING_32": "PASS",
    "HEALTH_AWARE_WEIGHTED_SCHEDULER": "PASS",
    "LANE_FAULT_ISOLATION": "PASS",
    "NO_HARDWARE_STATIC_SCAN": "PASS",
    "OFFLINE_FULL_REGRESSION": "PASS",
    "P0_P8C_REGRESSION": "PASS",
    "P8C_BASELINE_RECHECK": "PASS",
    "P8D_CANONICAL_CONFIG": "PASS",
    "PARTIAL_OBJECT_COMMIT_ZERO": "PASS",
    "PS_DRIVER_OFFLINE": "PASS",
    "REGISTER_MAP_CONSISTENCY": "PASS",
    "RESET_ABORT_DETERMINISTIC_RECLAIM": "PASS",
    "RETRY_EXHAUSTION_BOUNDED": "PASS",
    "RETRY_MIGRATION": "PASS",
    "RFAP_V1_REGRESSION": "PASS",
    "RFAP_VNEXT_STREAMING_MODEL": "PASS",
    "RTL_PYTHON_CROSSCHECK": "PASS",
    "SACK_ENCODE_DECODE": "PASS",
    "SACK_WINDOW_32": "PASS",
    "SCHEDULER_FAIRNESS": "PASS",
    "SEQUENCE_WIDTH_16": "PASS",
    "SEQUENCE_WRAP": "PASS",
    "STALE_GENERATION_REJECTION": "PASS",
    "STALE_PATH_EPOCH_REJECTION": "PASS",
    "STALE_SESSION_REJECTION": "PASS",
    "TX_RX_RING_INDEPENDENCE": "PASS",
    "Z7010_2LANE_PROFILE": "PASS",
    "Z7020_FIXED_32MODULE_PLUS_DATA_PLANE_PROFILE": "PASS",
    "Z7020_OUTSTANDING_64_PROFILE": "PASS",
    "Z7020_ROTATING_8LANE_PROFILE": "PASS"
  },
  "failures": [],
  "generated_utc": "2026-08-02T12:37:11.064393Z",
  "hardware_scope_promoted": false,
  "mode": "FULL",
  "no_hardware_scan": {
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
    "NO_HARDWARE": "1",
    "existing_scan": "PASS",
    "existing_scan_log": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f/no_hardware_existing_scan.log",
    "p8d_forbidden_hits": [],
    "status": "PASS",
    "test_id": "P8D-NO-HARDWARE-STATIC-SCAN"
  },
  "performance_blockers": [
    "The 18% duty-limited RFAP useful ceiling is below 19.2 Mbit/s; the stretch target is not feasible with the frozen v1 frame/chunk geometry."
  ],
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "schema_version": 1,
  "selected_raw_run": "evidence/generated/p10_1r_exact_source_p8d_af46d3b9/p8d_raw/formal_af46d3b9d09f",
  "source_commit": "af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c",
  "status": "PASS",
  "test_id": "P8D-ACCEPTANCE-CORE",
  "timing_followup": "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING"
}
```
