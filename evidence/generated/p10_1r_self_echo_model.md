# P10.1R self-echo/admission model

- Status: `PASS`
- Hardware actions executed: `false`

```json
{
  "admission_stress": {
    "blanked_raw_echo_count": 50000,
    "cross_lane_accepted_frame_count": 0,
    "cross_lane_raw_coupling_count": 3082,
    "echo_delay_semantics": "last_local_echo_edge_after_txd_fall",
    "echo_delay_sweep_us": [
      0,
      1,
      2,
      4,
      8,
      16,
      32,
      60,
      64
    ],
    "echo_duration_options_us": [
      0.125,
      0.5,
      1,
      4,
      16
    ],
    "echo_jitter_options_us": [
      -2,
      -1,
      0,
      1,
      2
    ],
    "event_count": 50000,
    "events_by_seed": {
      "1": 7142,
      "1024": 7143,
      "127": 7143,
      "17": 7143,
      "20260801": 7143,
      "31": 7143,
      "7": 7143
    },
    "local_source_rejected_count": 12682,
    "other_lane_unaffected_count": 50000,
    "pass": true,
    "raw_same_module_echo_count": 50000,
    "reflection_tail_component_options_us": [
      0,
      1,
      4,
      16,
      64
    ],
    "remote_ack_accepted_count": 25062,
    "remote_data_accepted_count": 24938,
    "same_module_accepted_frame_count": 0,
    "seeds": [
      1,
      7,
      17,
      31,
      127,
      1024,
      20260801
    ],
    "tx_rx_overlap_count": 0
  },
  "current_run_hardware_authorization": false,
  "generated_at_utc": "2026-08-02T15:08:46+00:00",
  "guard_selection_evidence": "evidence/generated/p10_1r_echo_guard_selection.json",
  "guard_status": "HARDWARE_MEASURED_SELECTION_OFFLINE_REBUILD",
  "hardware_actions_executed": false,
  "model_source": "scripts/model_p10_1r.py",
  "model_source_sha256": "fe361dbf8d634e844b28301588081c6d7b3e35bcec482a7db73b4dadf776e1b3",
  "no_hardware": true,
  "reset_fault_stress": {
    "descriptor_leak_count": 0,
    "duplicate_or_stale_commit_count": 0,
    "event_count": 25000,
    "events_by_seed": {
      "1": 3571,
      "1024": 3572,
      "127": 3572,
      "17": 3571,
      "20260801": 3572,
      "31": 3571,
      "7": 3571
    },
    "fault_count": 16707,
    "partial_commit_count": 0,
    "pass": true,
    "reset_count": 8293,
    "seeds": [
      1,
      7,
      17,
      31,
      127,
      1024,
      20260801
    ],
    "unsafe_tx_count": 0
  },
  "schema_version": 1,
  "source_commit": "cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d",
  "status": "PASS",
  "test_id": "P10_1R_SELF_ECHO_ADMISSION_MODEL"
}
```
