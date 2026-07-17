# large_object_jtag

RESULT: PASS
REASON: strict safe-wrapper + raw-log-bound backend parser passed the required 1 MiB/64 KiB matrix
GENERATED_AT_UTC: 2026-07-17T03:30:50+00:00
REPO: D:\CodexWorktrees\p7formal_911e1a3\RF_COMM_MULTILANE
HEAD: 911e1a303ff58593cac5ff4c4b70150d17f9a26b
HARDWARE_ACTIONS_EXECUTED_BY_SUMMARIZER: false
HARDWARE_ACTIONS_EXECUTED: true
PROGRAMMED_FPGA: True
DROVE_TFDU_TXD: True
ENABLED_TFDU_RECEIVER: True
SHUTDOWN_EXIT: 0
NETWORK_USED: false
MOTION_USED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## Evidence

- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/053_p7_large_jtag_4k_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/053_p7_large_jtag_4k_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/054_p7_large_jtag_64k_rr_counter/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/054_p7_large_jtag_64k_rr_counter/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/055_p7_large_jtag_64k_rr_prbs15/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/055_p7_large_jtag_64k_rr_prbs15/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/056_p7_large_jtag_64k_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/056_p7_large_jtag_64k_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/057_p7_large_jtag_64k_rr_all_bytes/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/057_p7_large_jtag_64k_rr_all_bytes/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/058_p7_large_jtag_1m_l0_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/058_p7_large_jtag_1m_l0_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/059_p7_large_jtag_1m_l1_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/059_p7_large_jtag_1m_l1_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/060_p7_large_jtag_1m_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/060_p7_large_jtag_1m_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/061_p7_large_jtag_1m_rep3_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/061_p7_large_jtag_1m_rep3_random/p7_jtag_backend_parse_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `required_cases`: `9`
- `observed_required_cases`: `9`
- `cases`: `[{'pattern': 'deterministic_random', 'object_length': 4096, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 20, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 20, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 40000, 'poll_bound_application_goodput_lower_bound_bps': 819200, 'host_end_to_end_elapsed_seconds': 51.455404, 'host_end_to_end_goodput_bps': 636.823297, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'binary_all_byte_values_repeated', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 95.702182, 'host_end_to_end_goodput_bps': 5478.328592, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'counter', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 94.703824, 'host_end_to_end_goodput_bps': 5536.080571, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 95.767971, 'host_end_to_end_goodput_bps': 5474.565186, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'prbs15', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 95.684604, 'host_end_to_end_goodput_bps': 5479.335004, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'LANE0_ONLY', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 797.337432, 'host_end_to_end_goodput_bps': 10520.77535, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'LANE1_ONLY', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 796.673985, 'host_end_to_end_goodput_bps': 10529.536746, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'REPLICATE_0X3', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 795.532216, 'host_end_to_end_goodput_bps': 10544.649018, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 800.328612, 'host_end_to_end_goodput_bps': 10481.454585, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}]`

## Errors

- None.

## Scope notes

- JTAG/AXI is auxiliary evidence and cannot promote PS_PL_PHY_PL_PS_APPLICATION_PASS
- preserved superseded direct-JTAG attempts: 0

## Hardware evidence envelope

### profile

```json
[
  {
    "actual_sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "expected_sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "label": "artifact:profile",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json"
  }
]
```

### bitstream

```json
[
  {
    "actual_sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "expected_sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "label": "artifact:bitstream",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit"
  }
]
```

### ltx

```json
[
  {
    "actual_sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "expected_sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "label": "artifact:ltx",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx"
  }
]
```

### xsa

```json
[
  {
    "actual_sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "expected_sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "label": "artifact:xsa",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa"
  }
]
```

### elf

```json
[
  {
    "actual_sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "expected_sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "label": "artifact:elf",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf"
  }
]
```

### authorization

```json
[
  {
    "actual_sha256": "9602e7bcd1264466177068c2cac2027960cf093279709a4aa608974529a2b0ab",
    "expected_sha256": "9602e7bcd1264466177068c2cac2027960cf093279709a4aa608974529a2b0ab",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_053_p7_large_jtag_4k_rr_random.txt"
  },
  {
    "actual_sha256": "1306a40900066cdf1dd800b00f40c2ff79190c16f495910ff672492ef2244ab0",
    "expected_sha256": "1306a40900066cdf1dd800b00f40c2ff79190c16f495910ff672492ef2244ab0",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_054_p7_large_jtag_64k_rr_counter.txt"
  },
  {
    "actual_sha256": "184417e31cb0ba71d3a68fe33fc412f05af34ba26372fd7812b0216e1dfcd12b",
    "expected_sha256": "184417e31cb0ba71d3a68fe33fc412f05af34ba26372fd7812b0216e1dfcd12b",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_055_p7_large_jtag_64k_rr_prbs15.txt"
  },
  {
    "actual_sha256": "69a28168627c03ea817ea40ccfa660555f90c15a7659889b2268959fa0c129b3",
    "expected_sha256": "69a28168627c03ea817ea40ccfa660555f90c15a7659889b2268959fa0c129b3",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_056_p7_large_jtag_64k_rr_random.txt"
  },
  {
    "actual_sha256": "4f5cf71f55f45d265a1fae3acf835e51358a0c321aa977889f8544d4b03a354c",
    "expected_sha256": "4f5cf71f55f45d265a1fae3acf835e51358a0c321aa977889f8544d4b03a354c",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_057_p7_large_jtag_64k_rr_all_bytes.txt"
  },
  {
    "actual_sha256": "40d3d82f680fcef5d948baca4542ef021fc277182de3cb2dd9d5adf5093cba85",
    "expected_sha256": "40d3d82f680fcef5d948baca4542ef021fc277182de3cb2dd9d5adf5093cba85",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_058_p7_large_jtag_1m_l0_random.txt"
  },
  {
    "actual_sha256": "5b4c36f73cec5a255f631de7d38211c57f3ec8a9ac2f419d7e742e3299609c9c",
    "expected_sha256": "5b4c36f73cec5a255f631de7d38211c57f3ec8a9ac2f419d7e742e3299609c9c",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_059_p7_large_jtag_1m_l1_random.txt"
  },
  {
    "actual_sha256": "acea1de1ca0b3786d0387d9bff32a405d507a4f192a341b292ed1ff65506a3d5",
    "expected_sha256": "acea1de1ca0b3786d0387d9bff32a405d507a4f192a341b292ed1ff65506a3d5",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_060_p7_large_jtag_1m_rr_random.txt"
  },
  {
    "actual_sha256": "b8c89adc4c74058b7502141a3660fab58556b18c6e0438d80bc114df9531c59e",
    "expected_sha256": "b8c89adc4c74058b7502141a3660fab58556b18c6e0438d80bc114df9531c59e",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_061_p7_large_jtag_1m_rep3_random.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\053_p7_large_jtag_4k_rr_random.transactions.txt",
    "sha256": "62fe518621e612e6a47d19c75a5591cef7089fb8c57cc726c7938d3888387f7c",
    "size_bytes": 130278
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\053_p7_large_jtag_4k_rr_random.manifest.json",
    "sha256": "10c4b92b72d2556237636007d0d69348460f2143e5eb72e41d287125a788fa35",
    "size_bytes": 14402
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\054_p7_large_jtag_64k_rr_counter.transactions.txt",
    "sha256": "43fc6ec6a6869dd8736d0fd41a9436c6017cb4f7f0e0225e9466a89540e31da7",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\054_p7_large_jtag_64k_rr_counter.manifest.json",
    "sha256": "8a969ed734adb2647480d6a00ec1841dad7c1a626b8c6d34e26fd011ab7c2e89",
    "size_bytes": 167574
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\055_p7_large_jtag_64k_rr_prbs15.transactions.txt",
    "sha256": "31dbc2e8d86406f3c0106714e7a849a464d09f2665b7383904af855098c5b8bf",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\055_p7_large_jtag_64k_rr_prbs15.manifest.json",
    "sha256": "49604cce13b7f25dab1dfcc765727b045eba0203e0f2a7d0c6078f1561ab9d51",
    "size_bytes": 167559
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\056_p7_large_jtag_64k_rr_random.transactions.txt",
    "sha256": "e20df7ea6c20c1da0e56054b96fe95f6df13341de23e66c863900359ca4826c6",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\056_p7_large_jtag_64k_rr_random.manifest.json",
    "sha256": "0f850276d353de171deee0654a0cf3925e9185ddc57a9439c5d434499bbda1ab",
    "size_bytes": 167273
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\057_p7_large_jtag_64k_rr_all_bytes.transactions.txt",
    "sha256": "679db96746011c61bf36094e86a2deb4046a919d1a108ca16ea49f00c9833228",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\057_p7_large_jtag_64k_rr_all_bytes.manifest.json",
    "sha256": "71a0372ab4b35585b8235c546b451a64d1f9eee824b23bc252746955d9a2436c",
    "size_bytes": 167592
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\058_p7_large_jtag_1m_l0_random.transactions.txt",
    "sha256": "7a4018b7c0b3d7ef82a79c26f3727851f3a62220189dbb7f2fc029e3838418c5",
    "size_bytes": 32614920
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\058_p7_large_jtag_1m_l0_random.manifest.json",
    "sha256": "2238373c3b2384d35130963b6eff26869cb43c64e44a2e0588d81c0cc9171268",
    "size_bytes": 2649074
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\059_p7_large_jtag_1m_l1_random.transactions.txt",
    "sha256": "f327c67b8b478269a96c2a1dc9e512b263634848f27dae503a9926807b53f1df",
    "size_bytes": 32614920
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\059_p7_large_jtag_1m_l1_random.manifest.json",
    "sha256": "8083df8a3215f66f57f7401aa0f81b4880f2e81435d415e20a4c2c37056242a4",
    "size_bytes": 2649056
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\060_p7_large_jtag_1m_rr_random.transactions.txt",
    "sha256": "39e63ac1a4d10e53e8e3a796b95bdb9c3f0f764de16c74022d543a58a182a50b",
    "size_bytes": 32614928
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\060_p7_large_jtag_1m_rr_random.manifest.json",
    "sha256": "6173bc9ff6e16fc4aef694739c43e00eb691e2299989f81f08e9ebed01fe0266",
    "size_bytes": 2649079
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\transactions\\061_p7_large_jtag_1m_rep3_random.transactions.txt",
    "sha256": "dfcdb193344109aa17bc601c3953003c91435b5772c3439abdabe2d161711817",
    "size_bytes": 32614923
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\manifests\\061_p7_large_jtag_1m_rep3_random.manifest.json",
    "sha256": "ca86c48d639ae90e00a5876ad916d115cb255bb0e3857a8bc7b9a626dde87a8a",
    "size_bytes": 2649026
  }
]
```

### output_file_hashes

```json
[
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\053_p7_large_jtag_4k_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "ca572f618177e1db6b69dfa8bdeb63b86862d348b63ddbdc11c7042c04c9058c",
    "size_bytes": 4096
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\054_p7_large_jtag_64k_rr_counter\\p7_jtag_reassembled_output.bin",
    "sha256": "48a92fb824afd752607d64c55e2467fbdcc8fda65deb25c2ed5b327d6dc88f11",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\055_p7_large_jtag_64k_rr_prbs15\\p7_jtag_reassembled_output.bin",
    "sha256": "ca45ccdf9f0c2be72656e6414cd71ae407b860df22830092d92fb0dbf1a0f1eb",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\056_p7_large_jtag_64k_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "ca1a191acfd778bc9609a3d9c88d7ff52b710af06ce7cbf8ff98999680deead7",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\057_p7_large_jtag_64k_rr_all_bytes\\p7_jtag_reassembled_output.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\058_p7_large_jtag_1m_l0_random\\p7_jtag_reassembled_output.bin",
    "sha256": "de7e28fb7ae8b57b4280dc13d61316442d564631d71caa52b28284929b0a8549",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\059_p7_large_jtag_1m_l1_random\\p7_jtag_reassembled_output.bin",
    "sha256": "92981a26065607345aece3ce7a4bf428997814425a847a5f374d564a955ef822",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\060_p7_large_jtag_1m_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "847ff69ec3010814fe5af6530d426b620fae9988a6ea18fed1260b8f74ef4774",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\061_p7_large_jtag_1m_rep3_random\\p7_jtag_reassembled_output.bin",
    "sha256": "70a2712e321d4cdafa35830e852c0f0187d629050093fa246a7244bf7d799034",
    "size_bytes": 1048576
  }
]
```

### shutdown_before

```json
[
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\053_p7_large_jtag_4k_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\054_p7_large_jtag_64k_rr_counter\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\055_p7_large_jtag_64k_rr_prbs15\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\056_p7_large_jtag_64k_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\057_p7_large_jtag_64k_rr_all_bytes\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\058_p7_large_jtag_1m_l0_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\059_p7_large_jtag_1m_l1_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\060_p7_large_jtag_1m_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\061_p7_large_jtag_1m_rep3_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  }
]
```

### shutdown_after

```json
[
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\053_p7_large_jtag_4k_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\054_p7_large_jtag_64k_rr_counter\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\055_p7_large_jtag_64k_rr_prbs15\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\056_p7_large_jtag_64k_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\057_p7_large_jtag_64k_rr_all_bytes\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\058_p7_large_jtag_1m_l0_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\059_p7_large_jtag_1m_l1_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\060_p7_large_jtag_1m_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\061_p7_large_jtag_1m_rep3_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  }
]
```

### envelope_status

```json
{
  "HEAD": "911e1a303ff58593cac5ff4c4b70150d17f9a26b",
  "SHUTDOWN_EXIT": 0,
  "drove_tfdu_txd": true,
  "enabled_tfdu_receiver": true,
  "hardware_actions_executed": true,
  "programmed_fpga": true,
  "repo": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE",
  "uart_access": false
}
```

