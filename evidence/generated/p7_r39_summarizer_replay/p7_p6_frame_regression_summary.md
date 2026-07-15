# p6_frame_regression

RESULT: FAIL
REASON: P6 frame regression evidence failed closed
GENERATED_AT_UTC: 2026-07-15T01:13:23+00:00
REPO: C:\Users\user\.codex\worktrees\r35validate_1d0c30f\RF_COMM_MULTILANE
HEAD: 0539667cfbaa29a8ddb0b137bb9d4b222f1e4eb4
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

- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/004_p7_p6_frame_regression_m3/p7_jtag_axi_stage_summary.json`
- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/004_p7_p6_frame_regression_m3/p7_jtag_backend_parse_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `frame_counts`: `{'LANE0_ONLY': 20, 'LANE1_ONLY': 20, 'REPLICATE_0X3': 20}`

## Errors

- LANE0_ONLY: hardware source commit does not match current repository HEAD
- LANE1_ONLY: hardware source commit does not match current repository HEAD
- REPLICATE_0X3: hardware source commit does not match current repository HEAD

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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx"
  }
]
```

### xsa

```json
[
  {
    "actual_sha256": "b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9",
    "expected_sha256": "b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9",
    "label": "artifact:xsa",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9.xsa"
  }
]
```

### elf

```json
[
  {
    "actual_sha256": "47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b",
    "expected_sha256": "47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b",
    "label": "artifact:elf",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b.elf"
  }
]
```

### authorization

```json
[
  {
    "actual_sha256": "7d4de99026a331812c704bb130bdbbfc7b25315d77558a47960dbcde682c916c",
    "expected_sha256": "7d4de99026a331812c704bb130bdbbfc7b25315d77558a47960dbcde682c916c",
    "label": "authorization",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260713_stationary_app_r31_diag_suffix55_004_p7_p6_frame_regression_m3.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
    "sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
    "size_bytes": 2083847
  },
  {
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9.xsa",
    "sha256": "b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9",
    "size_bytes": 560408
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b.elf",
    "sha256": "47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b",
    "size_bytes": 309096
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990",
    "size_bytes": 2052
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a",
    "size_bytes": 1429
  },
  {
    "authorization_sha256_key": "REGISTER_MAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\config\\register_map\\ir_axi_regs.yaml",
    "sha256": "d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d",
    "size_bytes": 7692
  },
  {
    "authorization_sha256_key": "SHUTDOWN_BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\shutdown_bitstream\\tfdu_shutdown_j10_j11.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "LTX_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
    "sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
    "size_bytes": 32384
  },
  {
    "authorization_sha256_key": "P7_JTAG_TRANSACTION_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\transactions\\004_p7_p6_frame_regression_m3.transactions.txt",
    "sha256": "152fefaac51ab25feebddb5349b85d53e43da6dfa969c20b2cc089f212cf3b1e",
    "size_bytes": 130273
  },
  {
    "authorization_sha256_key": "P7_JTAG_BACKEND_MANIFEST_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\manifests\\004_p7_p6_frame_regression_m3.manifest.json",
    "sha256": "6fce525fa8cb1a3a0d876a4095757055307d80eee233855ae5d8d180e8014ca6",
    "size_bytes": 14349
  }
]
```

### output_file_hashes

```json
[
  {
    "name": "jtag_reassembled_output",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\004_p7_p6_frame_regression_m3\\p7_jtag_reassembled_output.bin",
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
    "result_file": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\004_p7_p6_frame_regression_m3\\p7_shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\004_p7_p6_frame_regression_m3\\p7_shutdown_after_result.txt",
    "returncode": 0
  }
]
```

### envelope_status

```json
{
  "HEAD": "0539667cfbaa29a8ddb0b137bb9d4b222f1e4eb4",
  "SHUTDOWN_EXIT": 0,
  "drove_tfdu_txd": true,
  "enabled_tfdu_receiver": true,
  "hardware_actions_executed": true,
  "programmed_fpga": true,
  "repo": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE",
  "uart_access": false
}
```

