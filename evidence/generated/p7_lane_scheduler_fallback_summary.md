# lane_fallback

RESULT: PASS
REASON: software-injected scheduler fallback and strict-negative cases passed
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

- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/063_p7_ps_fault_fallback/p7_ps_application_stage_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `case_count`: `7`

## Errors

- None.

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
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json"
  }
]
```

### bitstream

```json
[
  {
    "actual_sha256": "756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a",
    "expected_sha256": "756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a",
    "label": "artifact:bitstream",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a.bit"
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
    "actual_sha256": "8fd14157f4659570e530d6e94419018d6fa74ff468ec28382cc32caca9fcf2a1",
    "expected_sha256": "8fd14157f4659570e530d6e94419018d6fa74ff468ec28382cc32caca9fcf2a1",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_063_p7_ps_fault_fallback.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "ACTIVE_PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ACTIVE_PROFILE.json",
    "sha256": "f6fb603f20dced9eaebb3aaaaa8f492931a28cb6466c7511f797341bf41b1b9b",
    "size_bytes": 899
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a.bit",
    "sha256": "756c318e6393d765ecac89db46e2d5f98fefe5bf44871804a9b5a0545f42207a",
    "size_bytes": 2083856
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949.elf",
    "sha256": "2efe94a236b8c287b8287ada06505253f455447cb88492b3f61e87accebf9949",
    "size_bytes": 355872
  },
  {
    "authorization_sha256_key": "P6_PS_BUILD_SUMMARY_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\generated\\vivado\\p6_ps_candidate\\p6_ps_candidate_build_summary.json",
    "sha256": "73c7ef399fbd7925f9e0c538f660118b09eda9aa4893c305111c978d6ddfd46c",
    "size_bytes": 3100
  },
  {
    "authorization_sha256_key": "P7_FROZEN_SHUTDOWN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\shutdown\\p7_frozen_shutdown_bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "P7_INPUT_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\inputs\\p7_ps_seed_247.bin",
    "sha256": "49b1170cf0b069be048c0a2674829870fcb89eebe0618ef45a0b01d3da533093",
    "size_bytes": 247
  },
  {
    "authorization_sha256_key": "P7_LANE1_PROMOTION_SUMMARY_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\generated\\p7_lane1_promotion_summary.json",
    "sha256": "6cc4cb4141133c7381874873137bfe78d5d73d337cf9c663b51ce5d1851a6363",
    "size_bytes": 1795
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "P7_PS_BUILD_SUMMARY_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\generated\\vitis\\p7_ps_runtime\\p7_ps_runtime_build_summary.json",
    "sha256": "a765c095926c9e792ef8f325df9e6a32ff425cf8b05830d22e070ebaf0692a19",
    "size_bytes": 11778
  },
  {
    "authorization_sha256_key": "P7_PS_CORE_READINESS_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\generated\\p7_ps_core_hardware_readiness.json",
    "sha256": "9659f58fcc71f87e0d21f9171d3323c88b1823a0c97f23773fdd7df00c267c51",
    "size_bytes": 16084
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json",
    "sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "size_bytes": 528
  },
  {
    "authorization_sha256_key": "PS7_INIT_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\build\\p7_ps_vitis_workspace\\p7_platform\\hw\\ps7_init.tcl",
    "sha256": "86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d",
    "size_bytes": 25544
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
    "authorization_sha256_key": "XSA_SHA256",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0.xsa",
    "sha256": "45e39fa92e0199eef24892968e49e8abdaa9a7d9e4f571866b188316c6dc4cf0",
    "size_bytes": 560425
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
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\063_p7_ps_fault_fallback\\shutdown_before_result.txt",
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
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\063_p7_ps_fault_fallback\\shutdown_after_result.txt",
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

