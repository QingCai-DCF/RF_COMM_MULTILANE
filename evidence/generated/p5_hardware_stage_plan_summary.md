# P5 Hardware Stage Plan Summary

generated_at_utc: 2026-07-09T14:50:41+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS_WITH_NOTES
reason: P5 hardware stage plan generated without executing hardware
hardware_actions_executed: false
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P5_HARDWARE_STAGE_PLAN: PASS_WITH_NOTES
REQUIRED_MISSING_ARTIFACTS: 0
OPTIONAL_NOTES: 2
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Active Input Hashes

- constraint_file: `cff1a17ee77bbaf90080cf4f97e5920e961aefae3b6752f080e35fcf4d4b1f11`
- active_profile: `7c932dfed5d29298cdfad2164aed2fcfca554aadbe4aed86eed7715864f9f2b1`
- pinmap: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
- active_xdc: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
- register_map: `4006851bdfaedea14d10cea9e7b4c2a39310bc7e7228bed911cf642521cb03a9`
- tfdu_safety_contract: `ff8f94e0aaba1d4bad239de59fea46a7a044f779e95bc04f00269d9fce5f03ae`
- tfdu_safety_summary: `0bc9af6cfeeb9dae03a9cafe7a645bcbfee8522454a18d3cbd6f816bd8861a0f`
- shutdown_bitstream: `bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`

## Stage Plan

| Order | Stage | Status | Profile | Bitstream SHA(s) | Stop on Fail |
| --- | --- | --- | --- | --- | --- |
| 1 | safe_idle_recheck | READY_FOR_AUTHORIZATION | `profiles/p5/p5_safe_idle_recheck.json` | `6925b69eb0d43aa788cb3d2fe8a8ce543de93da0200183d737214b899c5d394b` | true |
| 2 | tfdu_control_idle_recheck | READY_FOR_AUTHORIZATION | `profiles/p5/p5_tfdu_control_idle_recheck.json` | `08f3bc790fb8da67c642c69f695e9bcd66b27a40030be971d2d7d9bb4cbbc442` | true |
| 3 | raw_lane_matrix_fresh | READY_FOR_AUTHORIZATION | `profiles/p5/p5_raw_lane_matrix_fresh.json` | `84946ac4e0b160e45665a2a14c8d5c2e1c861d454c6f8805d3ee65e9228eb54a` | true |
| 4 | lane0_frame_crc_100 | READY_FOR_AUTHORIZATION | `profiles/p5/p5_lane0_frame_crc_100.json` | `7d92c8b86b74c75bd349f04545a22681cd3269b4c4ade40ec1aa7c6db8e84dfe` | true |
| 5 | lane1_frame_crc_100 | READY_FOR_AUTHORIZATION | `profiles/p5/p5_lane1_frame_crc_100.json` | `de7fae7325b107fe11c7f5e9e79c0ae83410984a7594eb7292c9c5652480af7d` | true |
| 6 | lane0_ack_retry_100 | READY_FOR_AUTHORIZATION | `profiles/p5/p5_lane0_ack_retry_100.json` | `e0e07d7f1d646ad8dd87b32efbeb24442daa6b74cd1f267a6ea8bb727d30c258` | true |
| 7 | lane1_ack_retry_100 | READY_FOR_AUTHORIZATION | `profiles/p5/p5_lane1_ack_retry_100.json` | `b072db80e4c88b36e9f2d326d6d5c2027357763a1cd47ffafaaa147572996f9f` | true |
| 8 | two_lane_minimal_100 | READY_FOR_AUTHORIZATION | `profiles/p5/p5_two_lane_minimal_100.json` | `bed545a125e77116788eb9fd665f69dc3f02775b09eb8e9400f4fd06c492d608` | true |
| 9 | payload_sweep | READY_FOR_AUTHORIZATION | `profiles/p5/p5_two_lane_payload_sweep.json` | `e0e07d7f1d646ad8dd87b32efbeb24442daa6b74cd1f267a6ea8bb727d30c258`<br>`b072db80e4c88b36e9f2d326d6d5c2027357763a1cd47ffafaaa147572996f9f`<br>`bed545a125e77116788eb9fd665f69dc3f02775b09eb8e9400f4fd06c492d608` | true |
| 10 | mask_regression | READY_FOR_AUTHORIZATION | `profiles/p5/p5_two_lane_mask_regression.json` | `bed545a125e77116788eb9fd665f69dc3f02775b09eb8e9400f4fd06c492d608` | true |
| 11 | retry_fault_injection_hw_optional | SKIP_NO_HW_FAULT_INJECTION_HOOK | `profiles/p5/p5_retry_fault_injection_hw_optional.json` | SKIP_NO_HW_FAULT_INJECTION_HOOK | false |
| 12 | two_lane_30min_soak | READY_FOR_AUTHORIZATION | `profiles/p5/p5_two_lane_30min_soak.json` | `32de20cf3c054f0e7ba909085e4f81c97f3bc74bac545b747583b8a0d33f2372` | true |
| 13 | two_lane_2h_soak_optional | NOT_RUN_OPTIONAL | `profiles/p5/p5_two_lane_2h_soak_optional.json` | `32de20cf3c054f0e7ba909085e4f81c97f3bc74bac545b747583b8a0d33f2372` | false |

## Boundary

- This is a dry-run hardware stage plan only.
- P5 hardware stages remain PENDING_HW until an authorized safe wrapper run writes fresh evidence and shutdown logs.
- Ethernet, motion/rotation, lane masks above 0x3, and 8-lane acceptance remain out of scope.
