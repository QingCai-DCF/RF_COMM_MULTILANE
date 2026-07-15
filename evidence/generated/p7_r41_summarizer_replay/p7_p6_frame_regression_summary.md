# p6_frame_regression

RESULT: PASS
REASON: strict raw-log-bound backend parses prove at least ten P6 frames on masks 0x1/0x2/0x3
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

- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/004_p7_p6_frame_regression_m3/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/004_p7_p6_frame_regression_m3/p7_jtag_backend_parse_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `frame_counts`: `{'LANE0_ONLY': 20, 'LANE1_ONLY': 20, 'REPLICATE_0X3': 20}`

## Errors

- None.

## Scope notes

- preserved superseded P6 regression attempts: 2

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
    "actual_sha256": "ae6ff0c7f110e934f49332de5bc3a015f05f1c2ef6fe6abe6b5c452987b1c8cc",
    "expected_sha256": "ae6ff0c7f110e934f49332de5bc3a015f05f1c2ef6fe6abe6b5c452987b1c8cc",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_004_p7_p6_frame_regression_m3.txt"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\transactions\\004_p7_p6_frame_regression_m3.transactions.txt",
    "sha256": "152fefaac51ab25feebddb5349b85d53e43da6dfa969c20b2cc089f212cf3b1e",
    "size_bytes": 130273
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\manifests\\004_p7_p6_frame_regression_m3.manifest.json",
    "sha256": "3abe8057c375685569886e07d6a275e2d493be35caa87092b5a663d062aadbd2",
    "size_bytes": 14374
  }
]
```

### output_file_hashes

```json
[
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\004_p7_p6_frame_regression_m3\\p7_jtag_reassembled_output.bin",
    "sha256": "43812ad6447f6d7cbd02439ca869aff553eda792fa799ab066242fdccebefa30",
    "size_bytes": 4096
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\004_p7_p6_frame_regression_m3\\p7_shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\004_p7_p6_frame_regression_m3\\p7_shutdown_after_result.txt",
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

