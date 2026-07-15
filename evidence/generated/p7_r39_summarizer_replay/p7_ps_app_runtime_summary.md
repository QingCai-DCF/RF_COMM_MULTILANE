# ps_runtime

RESULT: FAIL
REASON: real PS runtime or its redundant boundary regression failed closed
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

- `evidence/hardware/p7/authorized_sequence/p7_20260713_stationary_app_r31_diag_suffix55/062_p7_ps_functional/p7_ps_application_stage_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `functional_cases`: `0`
- `functional_4k_checkpoint`: `False`
- `redundant_ps_boundary_pairs`: `0`

## Errors

- runner status is FAIL_STAGE, not PASS
- hardware source commit does not match current repository HEAD
- authorization extension hash mismatch: P6_PS_BUILD_SUMMARY_PATH
- authorization extension hash mismatch: P7_LANE1_PROMOTION_SUMMARY_PATH
- authorization extension hash mismatch: P7_PS_BUILD_SUMMARY_PATH
- authorization extension hash mismatch: P7_PS_CORE_READINESS_PATH
- PS core readiness SHA256 mismatch
- PS core readiness recorded actual SHA256 mismatch
- hardware stage process passed is not true
- raw PS PASS marker missing
- PS postprocess is not PASS
- PS postprocess failures are nonempty
- PS mailbox shutdown_result is nonzero/missing
- PS mailbox service state is not SHUTDOWN
- PS functional matrix must contain exactly eight case objects
- PS functional large-object/pattern matrix is incomplete/duplicated
- PS functional case slots are not exactly 0..7
- PS functional 4 KiB stripe checkpoint record missing
- redundant PS boundary regression: runner status is FAIL_STAGE, not PASS
- redundant PS boundary regression: hardware source commit does not match current repository HEAD
- redundant PS boundary regression: authorization extension hash mismatch: P6_PS_BUILD_SUMMARY_PATH
- redundant PS boundary regression: authorization extension hash mismatch: P7_LANE1_PROMOTION_SUMMARY_PATH
- redundant PS boundary regression: authorization extension hash mismatch: P7_PS_BUILD_SUMMARY_PATH
- redundant PS boundary regression: authorization extension hash mismatch: P7_PS_CORE_READINESS_PATH
- redundant PS boundary regression: PS core readiness SHA256 mismatch
- redundant PS boundary regression: PS core readiness recorded actual SHA256 mismatch
- redundant PS boundary regression: hardware stage process passed is not true
- redundant PS boundary regression: raw PS PASS marker missing
- redundant PS boundary regression: PS postprocess is not PASS
- redundant PS boundary regression: PS postprocess failures are nonempty
- redundant PS boundary regression: PS mailbox shutdown_result is nonzero/missing
- redundant PS boundary regression: PS mailbox service state is not SHUTDOWN
- redundant PS boundary regression: hardware boundary matrix case count is not exactly 48
- redundant PS boundary regression: hardware boundary matrix does not exactly cover every required length x lane policy

## Hardware evidence envelope

### profile

```json
[
  {
    "actual_sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "expected_sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "label": "artifact:profile",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json"
  }
]
```

### bitstream

```json
[
  {
    "actual_sha256": "34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249",
    "expected_sha256": "34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249",
    "label": "artifact:bitstream",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249.bit"
  }
]
```

### ltx

```json
[]
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
    "actual_sha256": "743511690b72a83ff61f90b672d62107e3f1e4412c7235e90d98aa9a9d11b7f1",
    "expected_sha256": "743511690b72a83ff61f90b672d62107e3f1e4412c7235e90d98aa9a9d11b7f1",
    "label": "authorization",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260713_stationary_app_r31_diag_suffix55_062_p7_ps_functional.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "ACTIVE_PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\board_profiles\\ACTIVE_PROFILE.json",
    "sha256": "f6fb603f20dced9eaebb3aaaaa8f492931a28cb6466c7511f797341bf41b1b9b",
    "size_bytes": 899
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990",
    "size_bytes": 2052
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249.bit",
    "sha256": "34cdf1c1f7c36595760cc56ae6636209fa64f9b0eebad4d145a4ed5763f23249",
    "size_bytes": 2083856
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b.elf",
    "sha256": "47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b",
    "size_bytes": 309096
  },
  {
    "authorization_sha256_key": "P6_PS_BUILD_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\generated\\vivado\\p6_ps_candidate\\p6_ps_candidate_build_summary.json",
    "sha256": "d5c85cb396ed8913449c5a17e4c456225ac9014fb8106278eeb7ee1091f760ef",
    "size_bytes": 3100
  },
  {
    "authorization_sha256_key": "P7_FROZEN_SHUTDOWN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\shutdown\\p7_frozen_shutdown_bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "P7_INPUT_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\inputs\\p7_ps_seed_247.bin",
    "sha256": "49b1170cf0b069be048c0a2674829870fcb89eebe0618ef45a0b01d3da533093",
    "size_bytes": 247
  },
  {
    "authorization_sha256_key": "P7_LANE1_PROMOTION_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\generated\\p7_lane1_promotion_summary.json",
    "sha256": "b2e836c9440c29e23702ea76612315a92eb7fb802b529b309bd3bc2e3a4a4cdb",
    "size_bytes": 1795
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "P7_PS_BUILD_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\generated\\vitis\\p7_ps_runtime\\p7_ps_runtime_build_summary.json",
    "sha256": "a78360ac204e97e071c537fa94b7779c355acb9de0cfd5426622b16fc5043d9d",
    "size_bytes": 11793
  },
  {
    "authorization_sha256_key": "P7_PS_CORE_READINESS_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\generated\\p7_ps_core_hardware_readiness.json",
    "sha256": "a5a796191553354b54fd8dc1785a76847b02bbc79a45b5bb3229107470a2d40b",
    "size_bytes": 16264
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a",
    "size_bytes": 1429
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json",
    "sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "size_bytes": 528
  },
  {
    "authorization_sha256_key": "PS7_INIT_SHA256",
    "path": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\build\\p7_ps_vitis_workspace\\p7_platform\\hw\\ps7_init.tcl",
    "sha256": "84e478d79c0b7bfe6dfc45a5a99ab850c30c7db11d8fec1dae064133dd64b448",
    "size_bytes": 25544
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
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r35validate_1d0c30f\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9.xsa",
    "sha256": "b5d1174eb46d12eb395ceabbbea3c132c5771ca6777194138e68c2eacb2e4fc9",
    "size_bytes": 560408
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
    "result_file": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\062_p7_ps_functional\\shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\Documents\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260713_stationary_app_r31_diag_suffix55\\062_p7_ps_functional\\shutdown_after_result.txt",
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

