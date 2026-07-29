# P8D selective-repeat reference campaign

- Status: `PASS`
- Test ID: `P8D-PYTHON-REFERENCE-CAMPAIGN`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `cac64c78191a0acd4b6b30fb58c57984651535fb`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "campaign": {
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
    "NO_HARDWARE_ACTIONS_EXECUTED": true,
    "failures": [],
    "fixed_seeds": [
      1,
      7,
      17,
      31,
      127,
      1024,
      20260718,
      20260719
    ],
    "long_run": {
      "deadlock": 0,
      "descriptor_double_completion": 0,
      "descriptor_leak": 0,
      "duplicate_application_delivery": 0,
      "duplicate_frames_suppressed": 9464,
      "lane_fault_recovery_events": 6,
      "ring_wraps": 1172,
      "sequence_wraps": 2,
      "state_transitions": 100000,
      "status": "PASS",
      "unbounded_queue_growth": 0,
      "window_corruption": 0
    },
    "profile": "P8D_MULTI_PROFILE_OFFLINE",
    "randomized": {
      "allocated_frames": 10000,
      "descriptor_double_completion": 0,
      "descriptor_leak": 0,
      "descriptor_ring_events": 2500,
      "duplicate_application_delivery": 0,
      "fixed_seeds": [
        1,
        7,
        17,
        31,
        127,
        1024,
        20260718,
        20260719
      ],
      "protocol_lifecycle_events": 10000,
      "scheduler_balanced_fairness_error": 0.0,
      "scheduler_fault_events": 2500,
      "scheduler_fault_workload_fairness_error": 0.5942809814341009,
      "scheduler_maximum_starvation": 14,
      "status": "PASS",
      "unique_application_deliveries": 10000
    },
    "rtl_crosscheck_record_count": 2048,
    "schema_version": 1,
    "status": "PASS",
    "targeted_exhaustive": {
      "checks": {
        "all_receive_orders_window4": "PASS",
        "sack_encode_decode_exhaustive": "PASS",
        "sequence_wrap": "PASS",
        "single_double_and_all_holes": "PASS",
        "tx_wrap_and_holes": "PASS"
      },
      "hole_patterns": 16,
      "receive_orders": 24,
      "sack_bitmaps": 48,
      "status": "PASS"
    },
    "test_id": "P8D-PYTHON-REFERENCE-CAMPAIGN"
  },
  "generated_utc": "2026-07-28T18:24:10.489440Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "reference_campaign_path": "evidence/generated/p9_timing_fix_quick_p8d/p8d_raw/quick_cac64c78191a/reference/reference_campaign.json",
  "reference_log": "evidence/generated/p9_timing_fix_quick_p8d/p8d_raw/quick_cac64c78191a/python_reference.log",
  "schema_version": 1,
  "source_commit": "cac64c78191a0acd4b6b30fb58c57984651535fb",
  "status": "PASS",
  "test_id": "P8D-PYTHON-REFERENCE-CAMPAIGN",
  "unit_test_log": "evidence/generated/p9_timing_fix_quick_p8d/p8d_raw/quick_cac64c78191a/python_unit_tests.log"
}
```
