# stationary

RESULT: PASS
REASON: the unique real-PS stationary run completed the exact 1800-second 300+1500 contract
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

- `evidence/hardware/p7/authorized_sequence/p7_20260717_stationary_app_r74_formal_full/066_p7_ps_stationary/p7_ps_application_stage_summary.json`

## Checks

- No additional checks recorded.

## Metrics

- `observed_wall_seconds`: `1800.038`
- `objects`: `60`
- `samples`: `60`
- `calibration_samples`: `10`
- `acceptance_samples`: `50`
- `rolling_goodput_window_seconds`: `300`
- `calibration_median_bps`: `95253.0`
- `acceptance_median_bps`: `96337.0`

## Errors

- None.

## Scope notes

- sample object latency covers PS object processing from descriptor RUNNING through output integrity completion, but excludes host publication and JTAG observation

## Hardware evidence envelope

### profile

```json
[
  {
    "actual_sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "expected_sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "label": "artifact:profile",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json"
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
    "actual_sha256": "789ece582a1dd7f8585b9994470d65c4432b5cff8580b2863e80e6f7804ccc28",
    "expected_sha256": "789ece582a1dd7f8585b9994470d65c4432b5cff8580b2863e80e6f7804ccc28",
    "label": "authorization",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\.hardware_authorization\\p7_20260717_stationary_app_r74_formal_full_066_p7_ps_stationary.txt"
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
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\profiles\\p7\\p7_stationary_app_30min.json",
    "sha256": "65a36a8318e7fd1e3b647997aceca773c69e76eee85cb8fae922148ccd8f3c94",
    "size_bytes": 751
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
    "name": "stationary_deterministic_random_1048576_slot_0",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_counter_65536_slot_1",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_prbs15_65536_slot_2",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_binary_all_byte_values_repeated_65536_slot_3",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_deterministic_random_1048576_slot_4",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_counter_4096_slot_5",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_prbs15_65536_slot_6",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_binary_all_byte_values_repeated_65536_slot_7",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_1",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000001_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_2",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000002_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_3",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000003_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_4",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000004_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_5",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000005_output_result.bin",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_6",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000006_output_result.bin",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_terminal_7",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000007_output_result.bin",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_8",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000008_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_9",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000009_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_10",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000010_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_11",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000011_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_12",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000012_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_13",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000013_output_result.bin",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_14",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000014_output_result.bin",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_terminal_15",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000015_output_result.bin",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_16",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000016_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_17",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000017_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_18",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000018_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_19",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000019_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_20",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000020_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_21",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000021_output_result.bin",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_22",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000022_output_result.bin",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_terminal_23",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000023_output_result.bin",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_24",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000024_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_25",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000025_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_26",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000026_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_27",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000027_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_28",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000028_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_29",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000029_output_result.bin",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_30",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000030_output_result.bin",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_terminal_31",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000031_output_result.bin",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_32",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000032_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_33",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000033_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_34",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000034_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_35",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000035_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_36",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000036_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_37",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000037_output_result.bin",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_38",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000038_output_result.bin",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_terminal_39",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000039_output_result.bin",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_40",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000040_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_41",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000041_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_42",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000042_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_43",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000043_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_44",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000044_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_45",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000045_output_result.bin",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_46",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000046_output_result.bin",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_terminal_47",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000047_output_result.bin",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_48",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000048_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_49",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000049_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_50",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000050_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_51",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000051_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_52",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000052_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_53",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000053_output_result.bin",
    "sha256": "95647e4a543fc103ffbd0d4b0cffcbdccb1b304581d7e609cc4d7c909491e259",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_54",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000054_output_result.bin",
    "sha256": "feb07bd82ee49ad03fa5ad02148220e679c7457a8961cb23d1ceb146ce8d6c77",
    "size_bytes": 4096
  },
  {
    "name": "stationary_terminal_55",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000055_output_result.bin",
    "sha256": "9da06f7da81a794cd2f75205391c6ede1c44a6e14752ab6afa5661982268b7dd",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_56",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000056_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_57",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000057_output_result.bin",
    "sha256": "fcd7923cbb8e709738f05ba8c318a4df5c27c0451a987689fac429a17b292737",
    "size_bytes": 1048576
  },
  {
    "name": "stationary_terminal_58",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000058_output_result.bin",
    "sha256": "dd5cdd301adff15138b402ab190a143e8ff5ffed2d5e2fd24c3140fb652f11ff",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_59",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000059_output_result.bin",
    "sha256": "0765b0d1a9f493355595772f5a2ebaaf700d4d2cc7d8a781729a9771a380754f",
    "size_bytes": 65536
  },
  {
    "name": "stationary_terminal_60",
    "path": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\bundle\\stationary_00000060_output_result.bin",
    "sha256": "7daca2095d0438260fa849183dfc67faa459fdf4936e1bc91eec6b281b27e4c2",
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
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\shutdown_before_result.txt",
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
    "result_file": "D:\\CodexWorktrees\\p7formal_911e1a3\\RF_COMM_MULTILANE\\evidence\\hardware\\p7\\authorized_sequence\\p7_20260717_stationary_app_r74_formal_full\\066_p7_ps_stationary\\shutdown_after_result.txt",
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

