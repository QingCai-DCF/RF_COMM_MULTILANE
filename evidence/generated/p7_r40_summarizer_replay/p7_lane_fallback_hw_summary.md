# lane_fallback

RESULT: FAIL
REASON: lane_fallback evidence failed closed
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

- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r40_diag_suffix55/063_p7_ps_fault_fallback/p7_ps_application_stage_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `case_count`: `7`

## Errors

- lane_fallback:strict_lane0_unavailable: negative-case descriptor/host output SHA256 mismatch
- lane_fallback:strict_lane1_unavailable: negative-case descriptor/host output SHA256 mismatch
- lane_fallback:stripe_both_unavailable: negative-case descriptor/host output SHA256 mismatch

## Scope notes

- lane fault evidence is software scheduler injection, not a physical optical fault

## Hardware evidence envelope

### profile

```json
[
  {
    "actual_sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "expected_sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "label": "artifact:profile",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json"
  }
]
```

### bitstream

```json
[
  {
    "actual_sha256": "bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868",
    "expected_sha256": "bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868",
    "label": "artifact:bitstream",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868.bit"
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
    "actual_sha256": "b35fdcba4ec9ea0c7831a169f3d09671458134b1a3cd560411da68349aad55ff",
    "expected_sha256": "b35fdcba4ec9ea0c7831a169f3d09671458134b1a3cd560411da68349aad55ff",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r40_diag_suffix55_063_p7_ps_fault_fallback.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "ACTIVE_PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ACTIVE_PROFILE.json",
    "sha256": "f6fb603f20dced9eaebb3aaaaa8f492931a28cb6466c7511f797341bf41b1b9b",
    "size_bytes": 899
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868.bit",
    "sha256": "bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868",
    "size_bytes": 2083856
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
    "sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
    "size_bytes": 355944
  },
  {
    "authorization_sha256_key": "P6_PS_BUILD_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\generated\\vivado\\p6_ps_candidate\\p6_ps_candidate_build_summary.json",
    "sha256": "57cbc82ef207e464392ebe3a5bc4e7ce931259585729eec178d29eb49e3542b5",
    "size_bytes": 3100
  },
  {
    "authorization_sha256_key": "P7_FROZEN_SHUTDOWN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\shutdown\\p7_frozen_shutdown_bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "P7_INPUT_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\inputs\\p7_ps_seed_247.bin",
    "sha256": "49b1170cf0b069be048c0a2674829870fcb89eebe0618ef45a0b01d3da533093",
    "size_bytes": 247
  },
  {
    "authorization_sha256_key": "P7_LANE1_PROMOTION_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\generated\\p7_lane1_promotion_summary.json",
    "sha256": "932d799212dd76aa64b78563805a417687090a437afca964c9c49f71d8e61359",
    "size_bytes": 1795
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "P7_PS_BUILD_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\generated\\vitis\\p7_ps_runtime\\p7_ps_runtime_build_summary.json",
    "sha256": "3950c34f033b66413f2f481b40cbca2fe1542bfa2065941a5c180570773917c3",
    "size_bytes": 11807
  },
  {
    "authorization_sha256_key": "P7_PS_CORE_READINESS_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\generated\\p7_ps_core_hardware_readiness.json",
    "sha256": "c3961b381bb7f9276064f7220908640b7969bdbd02dfb877ad5453095b616d5d",
    "size_bytes": 16168
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json",
    "sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "size_bytes": 528
  },
  {
    "authorization_sha256_key": "PS7_INIT_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\build\\p7_ps_vitis_workspace\\p7_platform\\hw\\ps7_init.tcl",
    "sha256": "86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d",
    "size_bytes": 25544
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
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
    "sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
    "size_bytes": 560424
  }
]
```

### output_file_hashes

```json
[
  {
    "name": "stripe_lane0_to_lane1",
    "sha256": "766d012a0c43b3d04ba72af7cb4249517589945577bc1e1a06425417ff813f05",
    "size_bytes": 65536
  },
  {
    "name": "stripe_lane1_to_lane0",
    "sha256": "766d012a0c43b3d04ba72af7cb4249517589945577bc1e1a06425417ff813f05",
    "size_bytes": 65536
  },
  {
    "name": "replicate_lane0_unavailable",
    "sha256": "766d012a0c43b3d04ba72af7cb4249517589945577bc1e1a06425417ff813f05",
    "size_bytes": 65536
  },
  {
    "name": "replicate_lane1_unavailable",
    "sha256": "766d012a0c43b3d04ba72af7cb4249517589945577bc1e1a06425417ff813f05",
    "size_bytes": 65536
  },
  {
    "name": "strict_lane0_unavailable",
    "sha256": "de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31",
    "size_bytes": 65536
  },
  {
    "name": "strict_lane1_unavailable",
    "sha256": "de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31",
    "size_bytes": 65536
  },
  {
    "name": "stripe_both_unavailable",
    "sha256": "de2f256064a0af797747c2b97505dc0b9f3df0de4f489eac731c23ae9ca9cc31",
    "size_bytes": 65536
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\063_p7_ps_fault_fallback\\shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r40validate_3718276\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r40_diag_suffix55\\063_p7_ps_fault_fallback\\shutdown_after_result.txt",
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

