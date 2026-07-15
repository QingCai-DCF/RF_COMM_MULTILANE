# safe_idle

RESULT: FAIL
REASON: safe-idle evidence failed closed
GENERATED_AT_UTC: 2026-07-15T01:13:23+00:00
REPO: C:\Users\user\.codex\worktrees\r35validate_1d0c30f\RF_COMM_MULTILANE
HEAD: 0539667cfbaa29a8ddb0b137bb9d4b222f1e4eb4
HARDWARE_ACTIONS_EXECUTED_BY_SUMMARIZER: false
HARDWARE_ACTIONS_EXECUTED: true
PROGRAMMED_FPGA: True
DROVE_TFDU_TXD: False
ENABLED_TFDU_RECEIVER: False
SHUTDOWN_EXIT: 0
NETWORK_USED: false
MOTION_USED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3
PRODUCT_FINAL_ACCEPTANCE: PENDING
PRODUCT_FINAL_ACCEPTANCE_REASON: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

## Evidence

- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/001_p7_safe_idle/p7_jtag_axi_stage_summary.json`

## Checks

- `non_transmitting_semantic_mode`: `False`
- `shutdown_before_after`: `True`

## Metrics

- No metrics available.

## Errors

- hardware source commit does not match current repository HEAD

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
    "actual_sha256": "862ee42172f5c974d7c50b8d874bce67ccc2ea8f33e898aa7c6d05ef24d53849",
    "expected_sha256": "862ee42172f5c974d7c50b8d874bce67ccc2ea8f33e898aa7c6d05ef24d53849",
    "label": "authorization",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260713_stationary_app_r31_diag_suffix55_001_p7_safe_idle.txt"
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
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\transactions\\001_p7_safe_idle.transactions.txt",
    "sha256": "c164be9bf94510474c01711914bb37bdc800f28b9f5a3134e59f344e912c391d",
    "size_bytes": 790
  }
]
```

### output_file_hashes

```json
[]
```

### shutdown_before

```json
[
  {
    "attempted": true,
    "passed": true,
    "programming_attempted": true,
    "result_file": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\001_p7_safe_idle\\p7_shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\001_p7_safe_idle\\p7_shutdown_after_result.txt",
    "returncode": 0
  }
]
```

### envelope_status

```json
{
  "HEAD": "0539667cfbaa29a8ddb0b137bb9d4b222f1e4eb4",
  "SHUTDOWN_EXIT": 0,
  "drove_tfdu_txd": false,
  "enabled_tfdu_receiver": false,
  "hardware_actions_executed": true,
  "programmed_fpga": true,
  "repo": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE",
  "uart_access": false
}
```

