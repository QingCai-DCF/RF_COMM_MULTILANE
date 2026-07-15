# large_object_jtag

RESULT: FAIL
REASON: direct JTAG large-object evidence failed closed
GENERATED_AT_UTC: 2026-07-15T05:11:52+00:00
REPO: C:\Users\user\.codex\worktrees\r40validate_3718276\RF_COMM_MULTILANE
HEAD: 37182768047dc4afdc18699a1142852418b382b5
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

- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/055_p7_large_jtag_64k_rr_prbs15/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/055_p7_large_jtag_64k_rr_prbs15/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/056_p7_large_jtag_64k_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/056_p7_large_jtag_64k_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/057_p7_large_jtag_64k_rr_all_bytes/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/057_p7_large_jtag_64k_rr_all_bytes/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/058_p7_large_jtag_1m_l0_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/058_p7_large_jtag_1m_l0_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/059_p7_large_jtag_1m_l1_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/059_p7_large_jtag_1m_l1_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/060_p7_large_jtag_1m_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/060_p7_large_jtag_1m_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/061_p7_large_jtag_1m_rep3_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/061_p7_large_jtag_1m_rep3_random/p7_jtag_backend_parse_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `required_cases`: `9`
- `observed_required_cases`: `7`
- `cases`: `[{'pattern': 'binary_all_byte_values_repeated', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 97.647516, 'host_end_to_end_goodput_bps': 5369.18932, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 96.821676, 'host_end_to_end_goodput_bps': 5414.985793, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'prbs15', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 96.842513, 'host_end_to_end_goodput_bps': 5413.820684, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'LANE0_ONLY', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 836.086627, 'host_end_to_end_goodput_bps': 10033.180449, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'LANE1_ONLY', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 830.843202, 'host_end_to_end_goodput_bps': 10096.499532, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'REPLICATE_0X3', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 834.921801, 'host_end_to_end_goodput_bps': 10047.178059, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 904.242954, 'host_end_to_end_goodput_bps': 9276.94041, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}]`

## Errors

- direct JTAG large-object matrix missing tuples: [(4096, 'STRIPE_ROUND_ROBIN', 'deterministic_random'), (65536, 'STRIPE_ROUND_ROBIN', 'counter')]

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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx"
  }
]
```

### xsa

```json
[
  {
    "actual_sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "expected_sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "label": "artifact:xsa",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa"
  }
]
```

### elf

```json
[
  {
    "actual_sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "expected_sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "label": "artifact:elf",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf"
  }
]
```

### authorization

```json
[
  {
    "actual_sha256": "182fbb801f675c45eee4973f697fb784965e4050cb64e55c06fc1979b6990dbd",
    "expected_sha256": "182fbb801f675c45eee4973f697fb784965e4050cb64e55c06fc1979b6990dbd",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_055_p7_large_jtag_64k_rr_prbs15.txt"
  },
  {
    "actual_sha256": "cf790511ac3717dec9d7b575c36661ff321e37177d3bee568c7add35a881caff",
    "expected_sha256": "cf790511ac3717dec9d7b575c36661ff321e37177d3bee568c7add35a881caff",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_056_p7_large_jtag_64k_rr_random.txt"
  },
  {
    "actual_sha256": "2efe649b1719f204aaaea31879857608d42b3428485ca716806adb02febcef90",
    "expected_sha256": "2efe649b1719f204aaaea31879857608d42b3428485ca716806adb02febcef90",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_057_p7_large_jtag_64k_rr_all_bytes.txt"
  },
  {
    "actual_sha256": "0807d94ab840c40685681efabe44ab0385b9d3199a7ada60dc1e14b76562602c",
    "expected_sha256": "0807d94ab840c40685681efabe44ab0385b9d3199a7ada60dc1e14b76562602c",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_058_p7_large_jtag_1m_l0_random.txt"
  },
  {
    "actual_sha256": "c1bcddf11d75fad4cd8ed935b1848722ef05dff40f81806ddd568747d33d499c",
    "expected_sha256": "c1bcddf11d75fad4cd8ed935b1848722ef05dff40f81806ddd568747d33d499c",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_059_p7_large_jtag_1m_l1_random.txt"
  },
  {
    "actual_sha256": "78d6fb4bd4ff9994f64a472dac0677e62e270f92b1ee97979259de7945d1709b",
    "expected_sha256": "78d6fb4bd4ff9994f64a472dac0677e62e270f92b1ee97979259de7945d1709b",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_060_p7_large_jtag_1m_rr_random.txt"
  },
  {
    "actual_sha256": "be0073c13d5dc84a0cd64326e5b4ba5f918374959f535111ca1e082e5fd3a540",
    "expected_sha256": "be0073c13d5dc84a0cd64326e5b4ba5f918374959f535111ca1e082e5fd3a540",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_061_p7_large_jtag_1m_rep3_random.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\055_p7_large_jtag_64k_rr_prbs15.transactions.txt",
    "sha256": "31dbc2e8d86406f3c0106714e7a849a464d09f2665b7383904af855098c5b8bf",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\manifests\\055_p7_large_jtag_64k_rr_prbs15.manifest.json",
    "sha256": "fd41bd5fde989f81640ab0aea9930b921e49e8bae4a07f17c79bb86f756a2dc0",
    "size_bytes": 167580
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\056_p7_large_jtag_64k_rr_random.transactions.txt",
    "sha256": "e20df7ea6c20c1da0e56054b96fe95f6df13341de23e66c863900359ca4826c6",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\manifests\\056_p7_large_jtag_64k_rr_random.manifest.json",
    "sha256": "4bfc79c689a939c2d8dcca0745d25cac06f1450ebde7ece6eca36298b551e01c",
    "size_bytes": 167294
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\057_p7_large_jtag_64k_rr_all_bytes.transactions.txt",
    "sha256": "679db96746011c61bf36094e86a2deb4046a919d1a108ca16ea49f00c9833228",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\manifests\\057_p7_large_jtag_64k_rr_all_bytes.manifest.json",
    "sha256": "b259da4aace4d6a978f890cb66eb808e4413384eca4e71d07c0b78c977a21b12",
    "size_bytes": 167613
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\058_p7_large_jtag_1m_l0_random.transactions.txt",
    "sha256": "7a4018b7c0b3d7ef82a79c26f3727851f3a62220189dbb7f2fc029e3838418c5",
    "size_bytes": 32614920
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\manifests\\058_p7_large_jtag_1m_l0_random.manifest.json",
    "sha256": "d0cc77f4d1b76578d7399d63f6a886b78b0b3545d7beb7b61b48678b7709b97c",
    "size_bytes": 2649095
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\059_p7_large_jtag_1m_l1_random.transactions.txt",
    "sha256": "f327c67b8b478269a96c2a1dc9e512b263634848f27dae503a9926807b53f1df",
    "size_bytes": 32614920
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\manifests\\059_p7_large_jtag_1m_l1_random.manifest.json",
    "sha256": "5b87abf7680491e934ccbdbdb00e788d320c0e2a9657af35032b70d51028cb7c",
    "size_bytes": 2649077
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\060_p7_large_jtag_1m_rr_random.transactions.txt",
    "sha256": "39e63ac1a4d10e53e8e3a796b95bdb9c3f0f764de16c74022d543a58a182a50b",
    "size_bytes": 32614928
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\manifests\\060_p7_large_jtag_1m_rr_random.manifest.json",
    "sha256": "4c0d8afac83d3bcbad7d606f6b417e72e73fa346253bd7578314848235f8d467",
    "size_bytes": 2649100
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\061_p7_large_jtag_1m_rep3_random.transactions.txt",
    "sha256": "dfcdb193344109aa17bc601c3953003c91435b5772c3439abdabe2d161711817",
    "size_bytes": 32614923
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\manifests\\061_p7_large_jtag_1m_rep3_random.manifest.json",
    "sha256": "dca5722e0bad1aa1fee998af40557df018c9b7a98e42c68ea2962a2cf4f873e2",
    "size_bytes": 2649047
  }
]
```

### output_file_hashes

```json
[
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\055_p7_large_jtag_64k_rr_prbs15\\p7_jtag_reassembled_output.bin",
    "sha256": "ca45ccdf9f0c2be72656e6414cd71ae407b860df22830092d92fb0dbf1a0f1eb",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\056_p7_large_jtag_64k_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "ca1a191acfd778bc9609a3d9c88d7ff52b710af06ce7cbf8ff98999680deead7",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\057_p7_large_jtag_64k_rr_all_bytes\\p7_jtag_reassembled_output.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\058_p7_large_jtag_1m_l0_random\\p7_jtag_reassembled_output.bin",
    "sha256": "de7e28fb7ae8b57b4280dc13d61316442d564631d71caa52b28284929b0a8549",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\059_p7_large_jtag_1m_l1_random\\p7_jtag_reassembled_output.bin",
    "sha256": "92981a26065607345aece3ce7a4bf428997814425a847a5f374d564a955ef822",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\060_p7_large_jtag_1m_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "847ff69ec3010814fe5af6530d426b620fae9988a6ea18fed1260b8f74ef4774",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\061_p7_large_jtag_1m_rep3_random\\p7_jtag_reassembled_output.bin",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\055_p7_large_jtag_64k_rr_prbs15\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\056_p7_large_jtag_64k_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\057_p7_large_jtag_64k_rr_all_bytes\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\058_p7_large_jtag_1m_l0_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\059_p7_large_jtag_1m_l1_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\060_p7_large_jtag_1m_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\061_p7_large_jtag_1m_rep3_random\\p7_shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\055_p7_large_jtag_64k_rr_prbs15\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\056_p7_large_jtag_64k_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\057_p7_large_jtag_64k_rr_all_bytes\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\058_p7_large_jtag_1m_l0_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\059_p7_large_jtag_1m_l1_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\060_p7_large_jtag_1m_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\061_p7_large_jtag_1m_rep3_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  }
]
```

### envelope_status

```json
{
  "HEAD": "37182768047dc4afdc18699a1142852418b382b5",
  "SHUTDOWN_EXIT": 0,
  "drove_tfdu_txd": true,
  "enabled_tfdu_receiver": true,
  "hardware_actions_executed": true,
  "programmed_fpga": true,
  "repo": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE",
  "uart_access": false
}
```

