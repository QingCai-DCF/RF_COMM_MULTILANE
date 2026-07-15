# large_object_jtag

RESULT: PASS
REASON: strict safe-wrapper + raw-log-bound backend parser passed the required 1 MiB/64 KiB matrix
GENERATED_AT_UTC: 2026-07-15T11:52:06+00:00
REPO: C:\Users\user\.codex\worktrees\r41formal_946ccba\RF_COMM_MULTILANE
HEAD: 946ccbad66d64d715ad6745449b95f6c261ddf76
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

- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/053_p7_large_jtag_4k_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/053_p7_large_jtag_4k_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/054_p7_large_jtag_64k_rr_counter/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/054_p7_large_jtag_64k_rr_counter/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/055_p7_large_jtag_64k_rr_prbs15/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/055_p7_large_jtag_64k_rr_prbs15/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/056_p7_large_jtag_64k_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/056_p7_large_jtag_64k_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/057_p7_large_jtag_64k_rr_all_bytes/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/057_p7_large_jtag_64k_rr_all_bytes/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/058_p7_large_jtag_1m_l0_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/058_p7_large_jtag_1m_l0_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/059_p7_large_jtag_1m_l1_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/059_p7_large_jtag_1m_l1_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/060_p7_large_jtag_1m_rr_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/060_p7_large_jtag_1m_rr_random/p7_jtag_backend_parse_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/061_p7_large_jtag_1m_rep3_random/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/061_p7_large_jtag_1m_rep3_random/p7_jtag_backend_parse_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `required_cases`: `9`
- `observed_required_cases`: `9`
- `cases`: `[{'pattern': 'deterministic_random', 'object_length': 4096, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 20, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 20, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 40000, 'poll_bound_application_goodput_lower_bound_bps': 819200, 'host_end_to_end_elapsed_seconds': 52.506208, 'host_end_to_end_goodput_bps': 624.078585, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'binary_all_byte_values_repeated', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 99.331109, 'host_end_to_end_goodput_bps': 5278.185306, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'counter', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 100.15739, 'host_end_to_end_goodput_bps': 5234.641198, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 99.986542, 'host_end_to_end_goodput_bps': 5243.585682, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'prbs15', 'object_length': 65536, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 305, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 305, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 610000, 'poll_bound_application_goodput_lower_bound_bps': 859488, 'host_end_to_end_elapsed_seconds': 100.173134, 'host_end_to_end_goodput_bps': 5233.818481, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'LANE0_ONLY', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 856.217628, 'host_end_to_end_goodput_bps': 9797.284856, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'LANE1_ONLY', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 854.41173, 'host_end_to_end_goodput_bps': 9817.99255, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'REPLICATE_0X3', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 835.074418, 'host_end_to_end_goodput_bps': 10045.341851, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}, {'pattern': 'deterministic_random', 'object_length': 1048576, 'lane_policy': 'STRIPE_ROUND_ROBIN', 'fragment_count': 4878, 'fragment_latency_upper_bound_us': {'max': 2000, 'mean': 2000.0, 'min': 2000, 'p50': 2000, 'p95': 2000, 'p99': 2000, 'percentile_method': 'nearest_rank', 'sample_count': 4878, 'semantics': 'upper_bound', 'source': 'bounded_commit_plus_transfer_poll_counts_x_manifest_poll_period'}, 'object_transport_latency_upper_bound_us': 9756000, 'poll_bound_application_goodput_lower_bound_bps': 859840, 'host_end_to_end_elapsed_seconds': 862.197824, 'host_end_to_end_goodput_bps': 9729.33098, 'host_end_to_end_time_source': 'host_monotonic_child_process_elapsed', 'host_end_to_end_semantics': 'includes Vivado startup, FPGA programming, JTAG/AXI operations, polling, and host overhead; not optical-only fragment latency'}]`

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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx"
  }
]
```

### xsa

```json
[
  {
    "actual_sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "expected_sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "label": "artifact:xsa",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa"
  }
]
```

### elf

```json
[
  {
    "actual_sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "expected_sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "label": "artifact:elf",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf"
  }
]
```

### authorization

```json
[
  {
    "actual_sha256": "660b667623849567b8993a0c5666454c5cebf050bb1703a324c795a0ac5acf7e",
    "expected_sha256": "660b667623849567b8993a0c5666454c5cebf050bb1703a324c795a0ac5acf7e",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_053_p7_large_jtag_4k_rr_random.txt"
  },
  {
    "actual_sha256": "f0cbf38ee2f6059a60dd2b6814e5a2472dbeb56b896734e18c013aefd767ada0",
    "expected_sha256": "f0cbf38ee2f6059a60dd2b6814e5a2472dbeb56b896734e18c013aefd767ada0",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_054_p7_large_jtag_64k_rr_counter.txt"
  },
  {
    "actual_sha256": "440ef5e39d4e8a33f639984025c785a5220785b0cf742e59ebee6bcf52d8628b",
    "expected_sha256": "440ef5e39d4e8a33f639984025c785a5220785b0cf742e59ebee6bcf52d8628b",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_055_p7_large_jtag_64k_rr_prbs15.txt"
  },
  {
    "actual_sha256": "a2fa112ac75e722381d909a29a831763f90b3cc95bcac0ad9f1ca57398f4b838",
    "expected_sha256": "a2fa112ac75e722381d909a29a831763f90b3cc95bcac0ad9f1ca57398f4b838",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_056_p7_large_jtag_64k_rr_random.txt"
  },
  {
    "actual_sha256": "67c0a1fd6b8da0ca76f125de5760fc872b26241cae9508da1de69d2147b8d394",
    "expected_sha256": "67c0a1fd6b8da0ca76f125de5760fc872b26241cae9508da1de69d2147b8d394",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_057_p7_large_jtag_64k_rr_all_bytes.txt"
  },
  {
    "actual_sha256": "e90695e613d0c234f205aeedd89b74c8b6d66616d09cd09610cdd0bd26c3710a",
    "expected_sha256": "e90695e613d0c234f205aeedd89b74c8b6d66616d09cd09610cdd0bd26c3710a",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_058_p7_large_jtag_1m_l0_random.txt"
  },
  {
    "actual_sha256": "65427f4f9268b7bd650b695951ef47631d6ffc37f52b6ccdb382679cc71d70ee",
    "expected_sha256": "65427f4f9268b7bd650b695951ef47631d6ffc37f52b6ccdb382679cc71d70ee",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_059_p7_large_jtag_1m_l1_random.txt"
  },
  {
    "actual_sha256": "10eb07ff1a8145610a2dd67b3ef475f960e1296d75796abbe12d4a4801f850c9",
    "expected_sha256": "10eb07ff1a8145610a2dd67b3ef475f960e1296d75796abbe12d4a4801f850c9",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_060_p7_large_jtag_1m_rr_random.txt"
  },
  {
    "actual_sha256": "6e0a115415c12c928a30953ef33feb6374bb9381aaa9497ef25b31f51fa09030",
    "expected_sha256": "6e0a115415c12c928a30953ef33feb6374bb9381aaa9497ef25b31f51fa09030",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_061_p7_large_jtag_1m_rep3_random.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\053_p7_large_jtag_4k_rr_random.transactions.txt",
    "sha256": "62fe518621e612e6a47d19c75a5591cef7089fb8c57cc726c7938d3888387f7c",
    "size_bytes": 130278
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\053_p7_large_jtag_4k_rr_random.manifest.json",
    "sha256": "deddee1df767bad308c8304ed0de6b91bd641e21d125dfbba3d0f8724e8917f7",
    "size_bytes": 14419
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\054_p7_large_jtag_64k_rr_counter.transactions.txt",
    "sha256": "43fc6ec6a6869dd8736d0fd41a9436c6017cb4f7f0e0225e9466a89540e31da7",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\054_p7_large_jtag_64k_rr_counter.manifest.json",
    "sha256": "58416329b213c56883cfcb6588f894c7a15cef359c4d0e1a199629bbfd3305d0",
    "size_bytes": 167591
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\055_p7_large_jtag_64k_rr_prbs15.transactions.txt",
    "sha256": "31dbc2e8d86406f3c0106714e7a849a464d09f2665b7383904af855098c5b8bf",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\055_p7_large_jtag_64k_rr_prbs15.manifest.json",
    "sha256": "0977f1e6616f9a439240c96052e6d5f3e6a00248757f3bc6320690c73a62c86e",
    "size_bytes": 167576
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\056_p7_large_jtag_64k_rr_random.transactions.txt",
    "sha256": "e20df7ea6c20c1da0e56054b96fe95f6df13341de23e66c863900359ca4826c6",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\056_p7_large_jtag_64k_rr_random.manifest.json",
    "sha256": "e1c0a791441cd707b590a488913a6214ac20567389243cc051b939bf9d917d79",
    "size_bytes": 167290
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\057_p7_large_jtag_64k_rr_all_bytes.transactions.txt",
    "sha256": "679db96746011c61bf36094e86a2deb4046a919d1a108ca16ea49f00c9833228",
    "size_bytes": 2039317
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\057_p7_large_jtag_64k_rr_all_bytes.manifest.json",
    "sha256": "1a03b1a36b5b069318e7db66956c5c9493a93a8c33c75dc3e83a9c4ed4471741",
    "size_bytes": 167609
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\058_p7_large_jtag_1m_l0_random.transactions.txt",
    "sha256": "7a4018b7c0b3d7ef82a79c26f3727851f3a62220189dbb7f2fc029e3838418c5",
    "size_bytes": 32614920
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\058_p7_large_jtag_1m_l0_random.manifest.json",
    "sha256": "a3a646be003f1463436de3d33ef121fbcb3792729a8febfbcde3209b333c69b0",
    "size_bytes": 2649091
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\059_p7_large_jtag_1m_l1_random.transactions.txt",
    "sha256": "f327c67b8b478269a96c2a1dc9e512b263634848f27dae503a9926807b53f1df",
    "size_bytes": 32614920
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\059_p7_large_jtag_1m_l1_random.manifest.json",
    "sha256": "60c957237dd91a98f1feafa9f0fb64b40e0b5e73aa88f329082f3767df771d54",
    "size_bytes": 2649073
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\060_p7_large_jtag_1m_rr_random.transactions.txt",
    "sha256": "39e63ac1a4d10e53e8e3a796b95bdb9c3f0f764de16c74022d543a58a182a50b",
    "size_bytes": 32614928
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\060_p7_large_jtag_1m_rr_random.manifest.json",
    "sha256": "35dd0b5887389a44bd042792acaac163ef5eb031c259027431698f898d06e04e",
    "size_bytes": 2649096
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\061_p7_large_jtag_1m_rep3_random.transactions.txt",
    "sha256": "dfcdb193344109aa17bc601c3953003c91435b5772c3439abdabe2d161711817",
    "size_bytes": 32614923
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\061_p7_large_jtag_1m_rep3_random.manifest.json",
    "sha256": "1cd60d9801bcce3de3908681f8fd81aa5f00aa5eb006d52743d3eeb90c6ea86e",
    "size_bytes": 2649043
  }
]
```

### output_file_hashes

```json
[
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\053_p7_large_jtag_4k_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "ca572f618177e1db6b69dfa8bdeb63b86862d348b63ddbdc11c7042c04c9058c",
    "size_bytes": 4096
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\054_p7_large_jtag_64k_rr_counter\\p7_jtag_reassembled_output.bin",
    "sha256": "48a92fb824afd752607d64c55e2467fbdcc8fda65deb25c2ed5b327d6dc88f11",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\055_p7_large_jtag_64k_rr_prbs15\\p7_jtag_reassembled_output.bin",
    "sha256": "ca45ccdf9f0c2be72656e6414cd71ae407b860df22830092d92fb0dbf1a0f1eb",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\056_p7_large_jtag_64k_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "ca1a191acfd778bc9609a3d9c88d7ff52b710af06ce7cbf8ff98999680deead7",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\057_p7_large_jtag_64k_rr_all_bytes\\p7_jtag_reassembled_output.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\058_p7_large_jtag_1m_l0_random\\p7_jtag_reassembled_output.bin",
    "sha256": "de7e28fb7ae8b57b4280dc13d61316442d564631d71caa52b28284929b0a8549",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\059_p7_large_jtag_1m_l1_random\\p7_jtag_reassembled_output.bin",
    "sha256": "92981a26065607345aece3ce7a4bf428997814425a847a5f374d564a955ef822",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\060_p7_large_jtag_1m_rr_random\\p7_jtag_reassembled_output.bin",
    "sha256": "847ff69ec3010814fe5af6530d426b620fae9988a6ea18fed1260b8f74ef4774",
    "size_bytes": 1048576
  },
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\061_p7_large_jtag_1m_rep3_random\\p7_jtag_reassembled_output.bin",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\053_p7_large_jtag_4k_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\054_p7_large_jtag_64k_rr_counter\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\055_p7_large_jtag_64k_rr_prbs15\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\056_p7_large_jtag_64k_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\057_p7_large_jtag_64k_rr_all_bytes\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\058_p7_large_jtag_1m_l0_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\059_p7_large_jtag_1m_l1_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\060_p7_large_jtag_1m_rr_random\\p7_shutdown_before_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\061_p7_large_jtag_1m_rep3_random\\p7_shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\053_p7_large_jtag_4k_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\054_p7_large_jtag_64k_rr_counter\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\055_p7_large_jtag_64k_rr_prbs15\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\056_p7_large_jtag_64k_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\057_p7_large_jtag_64k_rr_all_bytes\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\058_p7_large_jtag_1m_l0_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\059_p7_large_jtag_1m_l1_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\060_p7_large_jtag_1m_rr_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  },
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\061_p7_large_jtag_1m_rep3_random\\p7_shutdown_after_result.txt",
    "returncode": 0
  }
]
```

### envelope_status

```json
{
  "HEAD": "946ccbad66d64d715ad6745449b95f6c261ddf76",
  "SHUTDOWN_EXIT": 0,
  "drove_tfdu_txd": true,
  "enabled_tfdu_receiver": true,
  "hardware_actions_executed": true,
  "programmed_fpga": true,
  "repo": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE",
  "uart_access": false
}
```

