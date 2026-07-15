# queue_backpressure

RESULT: PASS
REASON: depth-1/depth-8/FIFO/overflow/STOP/ABORT queue cases passed
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

- `evidence/hardware/p7/authorized_sequence/p7_20260715_stationary_app_r41_formal_full/065_p7_ps_queue/p7_ps_application_stage_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `case_count`: `8`

## Errors

- None.

## Hardware evidence envelope

### profile

```json
[
  {
    "actual_sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "expected_sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "label": "artifact:profile",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json"
  }
]
```

### bitstream

```json
[
  {
    "actual_sha256": "532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0",
    "expected_sha256": "532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0",
    "label": "artifact:bitstream",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0.bit"
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
    "actual_sha256": "25e0acb799e8580d931f1b47d949e31572870aa7b20a871b08a791a85ee38508",
    "expected_sha256": "25e0acb799e8580d931f1b47d949e31572870aa7b20a871b08a791a85ee38508",
    "label": "authorization",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260715_stationary_app_r41_formal_full_065_p7_ps_queue.txt"
  }
]
```

### input_file_hashes

```json
[
  {
    "authorization_sha256_key": "ACTIVE_PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ACTIVE_PROFILE.json",
    "sha256": "f6fb603f20dced9eaebb3aaaaa8f492931a28cb6466c7511f797341bf41b1b9b",
    "size_bytes": 899
  },
  {
    "authorization_sha256_key": "ACTIVE_XDC_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\constraints\\active\\PORT1.generated.xdc",
    "sha256": "f53239e233c25509b6f15b5d0154be07f686c83c1568524a9ecf2e4bcbaa1344",
    "size_bytes": 2018
  },
  {
    "authorization_sha256_key": "BITSTREAM_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0.bit",
    "sha256": "532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0",
    "size_bytes": 2083856
  },
  {
    "authorization_sha256_key": "ELF_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_runtime_3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644.elf",
    "sha256": "3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644",
    "size_bytes": 355948
  },
  {
    "authorization_sha256_key": "P6_PS_BUILD_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\generated\\vivado\\p6_ps_candidate\\p6_ps_candidate_build_summary.json",
    "sha256": "c5bf3519be09a1e51f0b40b612e501aa9361224c767b8095fc16c88739d969fa",
    "size_bytes": 3100
  },
  {
    "authorization_sha256_key": "P7_FROZEN_SHUTDOWN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\shutdown\\p7_frozen_shutdown_bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810.bit",
    "sha256": "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810",
    "size_bytes": 2083853
  },
  {
    "authorization_sha256_key": "P7_INPUT_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\inputs\\p7_ps_seed_247.bin",
    "sha256": "49b1170cf0b069be048c0a2674829870fcb89eebe0618ef45a0b01d3da533093",
    "size_bytes": 247
  },
  {
    "authorization_sha256_key": "P7_LANE1_PROMOTION_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\generated\\p7_lane1_promotion_summary.json",
    "sha256": "ef159b9e20bc6c5bf1dce7d42b79b53285c2fcb464f470d737792a7fbfa1668f",
    "size_bytes": 1795
  },
  {
    "authorization_sha256_key": "P7_PLAN_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\artifacts\\p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
    "sha256": "c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd",
    "size_bytes": 34806
  },
  {
    "authorization_sha256_key": "P7_PS_BUILD_SUMMARY_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\generated\\vitis\\p7_ps_runtime\\p7_ps_runtime_build_summary.json",
    "sha256": "64c6bc23cb321688101b8a901f3214a5b8fba46cae50fd509269648a9d6a739c",
    "size_bytes": 11809
  },
  {
    "authorization_sha256_key": "P7_PS_CORE_READINESS_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\generated\\p7_ps_core_hardware_readiness.json",
    "sha256": "a55f0e7d4c62c82403c117cbddf2c5686d86e47bade0b8ca4193ecb5178524d6",
    "size_bytes": 16240
  },
  {
    "authorization_sha256_key": "PINMAP_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\board_profiles\\ax7010_tfdu_j10_j11_pinmap.csv",
    "sha256": "583a0151cb1e968f7d0782e38d20e1e4b9df387310966561c14fb2383a8541cd",
    "size_bytes": 1412
  },
  {
    "authorization_sha256_key": "PROFILE_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\profiles\\p7\\p7_ps_application_functional.json",
    "sha256": "eb0192a27d115a5b70730746982e16b954ed754f8e1a57961091a31c4d6afcd0",
    "size_bytes": 528
  },
  {
    "authorization_sha256_key": "PS7_INIT_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\build\\p7_ps_vitis_workspace\\p7_platform\\hw\\ps7_init.tcl",
    "sha256": "86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d",
    "size_bytes": 25544
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
    "authorization_sha256_key": "XSA_SHA256",
    "path": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p6\\bitstreams\\p6_ps_dynamic_transport_e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1.xsa",
    "sha256": "e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1",
    "size_bytes": 560423
  }
]
```

### output_file_hashes

```json
[
  {
    "name": "queue_0",
    "sha256": "e240cf65a5be69d481b92622ad290e9845ceb2c1d6a48eda9bcccd565e3355bb",
    "size_bytes": 512
  },
  {
    "name": "queue_1",
    "sha256": "d50e36d94a1d8bb7e0f4a9e67d027de810e1d49e48fbced64323b90896b5b8d4",
    "size_bytes": 529
  },
  {
    "name": "queue_2",
    "sha256": "fa3fb03926ef34f55f109458f7ba28a16dfd6fa62213541805e635094a268d3e",
    "size_bytes": 546
  },
  {
    "name": "queue_3",
    "sha256": "e48266cf2764057288aec3f8518febf7e5f51d7de0acee2231e36cd37795e4c8",
    "size_bytes": 563
  },
  {
    "name": "queue_4",
    "sha256": "049e8a98570114bc00c32fc965062b6429c2ee90a1cedc01c8267f8d6e4da876",
    "size_bytes": 580
  },
  {
    "name": "queue_5",
    "sha256": "86002f797fff7b30f4194bf9fbe34a8e1c3d70ca497e4b544c0e9f99893032b6",
    "size_bytes": 597
  },
  {
    "name": "queue_6",
    "sha256": "18dec502cb09df31cac689f477d2265b776d34fdbcee36d3e96d6d4866e040ee",
    "size_bytes": 614
  },
  {
    "name": "queue_7",
    "sha256": "6d3f2c3f71ca8743903a11747e1d8f9bc28a632c0f00ea1fa8d8eb4065ddf2f2",
    "size_bytes": 631
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\065_p7_ps_queue\\shutdown_before_result.txt",
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
    "result_file": "C:\\Users\\user\\.codex\\worktrees\\r41formal_946ccba\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260715_stationary_app_r41_formal_full\\065_p7_ps_queue\\shutdown_after_result.txt",
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

