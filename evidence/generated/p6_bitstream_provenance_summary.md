# P6 Bitstream Provenance Summary

generated_at_utc: 2026-07-09T16:43:58+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b863a2377f4dbb6dd70bcf8064f138739cf0d00`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS_WITH_NOTES
reason: P6 immutable artifact provenance recorded; local transport artifact is missing
script_hardware_actions_executed: false
source_evidence_contains_hardware_actions: false
stage_programmed_fpga: false
stage_drove_tfdu_txd: false
stage_enabled_tfdu_receiver: false
shutdown_on_exit_observed: false
product_final_acceptance: pending
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
max_lane_mask: 0x3

P6_BITSTREAM_PROVENANCE: PASS_WITH_NOTES
missing_or_blocked_count: 2
vivado: `D:\Xilinx\Vivado\2023.1\bin\vivado.bat`

## Artifacts

| Artifact | Status | Immutable Bitstream | SHA256 | Applicability |
| --- | --- | --- | --- | --- |
| p6_safe_idle | PASS | `evidence/hardware/p6/bitstreams/p6_safe_idle_6925b69eb0d43aa788cb3d2fe8a8ce543de93da0200183d737214b899c5d394b.bit` | `6925b69eb0d43aa788cb3d2fe8a8ce543de93da0200183d737214b899c5d394b` | P6_SAFE_IDLE_DIAGNOSTIC |
| p6_tfdu_idle | PASS | `evidence/hardware/p6/bitstreams/p6_tfdu_idle_08f3bc790fb8da67c642c69f695e9bcd66b27a40030be971d2d7d9bb4cbbc442.bit` | `08f3bc790fb8da67c642c69f695e9bcd66b27a40030be971d2d7d9bb4cbbc442` | P6_TFDU_RECEIVE_ACTIVE_IDLE_DIAGNOSTIC |
| p6_local_transport | BLOCKED_BY_RUNTIME_ENVIRONMENT | `MISSING` | `MISSING` | MISSING_P6_DYNAMIC_PAYLOAD_JTAG_AXI_ARTIFACT |
| p6_two_lane_soak | BLOCKED_BY_RUNTIME_ENVIRONMENT | `MISSING` | `MISSING` | MISSING_P6_DYNAMIC_TWO_LANE_SOAK_ARTIFACT |

## Active Input Hashes

- constraint_file: `cff1a17ee77bbaf90080cf4f97e5920e961aefae3b6752f080e35fcf4d4b1f11`
- active_profile: `7c932dfed5d29298cdfad2164aed2fcfca554aadbe4aed86eed7715864f9f2b1`
- pinmap: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
- active_xdc: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
- register_map: `4006851bdfaedea14d10cea9e7b4c2a39310bc7e7228bed911cf642521cb03a9`
- tfdu_safety_contract: `ff8f94e0aaba1d4bad239de59fea46a7a044f779e95bc04f00269d9fce5f03ae`
- tfdu_safety_summary: `0bc9af6cfeeb9dae03a9cafe7a645bcbfee8522454a18d3cbd6f816bd8861a0f`
- shutdown_bitstream: `bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`
