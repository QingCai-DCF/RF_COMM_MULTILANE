# safe_idle

RESULT: PASS
REASON: fresh safe-idle readback and both shutdown barriers passed
GENERATED_AT_UTC: 2026-07-15T05:11:52+00:00
REPO: C:\Users\user\.codex\worktrees\r40validate_3718276\RF_COMM_MULTILANE
HEAD: 37182768047dc4afdc18699a1142852418b382b5
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

- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/001_p7_safe_idle/p7_jtag_axi_stage_summary.json`

## Checks

- `non_transmitting_semantic_mode`: `True`
- `shutdown_before_after`: `True`

## Metrics

- No metrics available.

## Errors

- None.

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
    "actual_sha256": "a01f671542b0cbefa939fb9309d01c5dfbc1715ef886a989121161e66f325127",
    "expected_sha256": "a01f671542b0cbefa939fb9309d01c5dfbc1715ef886a989121161e66f325127",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_001_p7_safe_idle.txt"
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
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\transactions\\001_p7_safe_idle.transactions.txt",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\001_p7_safe_idle\\p7_shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\001_p7_safe_idle\\p7_shutdown_after_result.txt",
    "returncode": 0
  }
]
```

### envelope_status

```json
{
  "HEAD": "37182768047dc4afdc18699a1142852418b382b5",
  "SHUTDOWN_EXIT": 0,
  "drove_tfdu_txd": false,
  "enabled_tfdu_receiver": false,
  "hardware_actions_executed": true,
  "programmed_fpga": true,
  "repo": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE",
  "uart_access": false
}
```

