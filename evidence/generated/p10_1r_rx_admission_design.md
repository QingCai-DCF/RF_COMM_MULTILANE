# P10.1R RX admission design evidence

- Status: `PASS`
- Source commit: `af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c`
- Hardware actions executed: `false`

```json
{
  "candidate_guard_cycles": 4096,
  "candidate_guard_us": 64,
  "config": {
    "bytes": 3477,
    "path": "config/tfdu_rx_admission.yaml",
    "sha256": "09924177deb60eee1889c2f622645ace41fc9dbd3bdf82e3c1fe4e5d3ffebb69"
  },
  "current_run_hardware_authorization": false,
  "direct_hardware_claim": false,
  "focused_xsim": {
    "bytes": 5899,
    "path": "evidence/generated/p10_1r_xsim/summary.json",
    "sha256": "b649f8768ac995626480011b43828233fe638ee59486526a6d9b9c0a4dd8ca2f"
  },
  "generated_at_utc": "2026-08-02T10:08:58+00:00",
  "guard_selection_evidence": {
    "bytes": 3571,
    "path": "evidence/generated/p10_1r_echo_guard_selection.json",
    "sha256": "91219cccda83a7edb68ffc26842c1a081583fa4f68005dd1c95344a7de342fe0"
  },
  "hardware_actions_executed": false,
  "hardware_measurement_status": "PASS_GUARD_SELECTION_REBUILD_PENDING",
  "idle_qualification_cycles": 256,
  "maximum_quarantine_cycles": 131072,
  "network_used": false,
  "no_hardware": true,
  "register_map": {
    "bytes": 60093,
    "path": "config/register_map/ir_axi_regs.yaml",
    "sha256": "cfc2f097218a618b461299e54765af29aa19d380c6f974101011ddc46c0301ea"
  },
  "rtl": [
    {
      "bytes": 8608,
      "path": "rtl/p10_1r_rx_admission.sv",
      "sha256": "0cc24c1c17d012f1e097e88f5161dd8fd1a8887e97b90d0c05bc9860dd0cbf4b"
    },
    {
      "bytes": 104826,
      "path": "rtl/p9_optical_transport_core.sv",
      "sha256": "6af5c5b3c3c1b7d106f6c48fb492ab0a0a8650deb833a299bc68e176a75eca2d"
    }
  ],
  "safety_noninterference": {
    "affects_global_permit": false,
    "affects_txd_kill_or_sd_or_mode": false,
    "configuration_update_hardware_actions_executed": false,
    "creates_backpressure": false,
    "hardware_authorization": false,
    "no_hardware": true,
    "selection_evidence_hardware_actions_executed": true
  },
  "schema_version": 1,
  "scope": "OFFLINE_DESIGN_AND_XSIM_ONLY",
  "selected_final_guard_cycles": 4096,
  "source_commit": "af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c",
  "source_identity": {
    "ack_header_encoding": "byte11_bits_7_2_source_bit_1_lane_bit_0_direction",
    "airtime_bytes_added": 0,
    "data_header_encoding": "byte13_bits_7_2",
    "fixed_node_id": 1,
    "rotating_role_node_id": 2,
    "width_bits": 6
  },
  "status": "PASS",
  "test_id": "P10_1R-RX-ADMISSION-DESIGN"
}
```
