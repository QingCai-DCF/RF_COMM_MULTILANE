# P6 Bitstream Provenance Summary

generated_at_utc: 2026-07-10T09:15:55+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b90d41a6750aad8023071433996fee3f068efe2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: P6 immutable bitstreams copied
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

P6_BITSTREAM_PROVENANCE: PASS
missing_or_blocked_count: 0
vivado: `D:\Xilinx\Vivado\2023.1\bin\vivado.bat`

## Artifacts

| Artifact | Status | Immutable Bitstream | SHA256 | Applicability |
| --- | --- | --- | --- | --- |
| p6_safe_idle | PASS | `evidence/hardware/p6/bitstreams/p6_safe_idle_0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d.bit` | `0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d` | P6_IMMUTABLE_JTAG_AXI_DYNAMIC_TRANSPORT_CANDIDATE_RESET_SAFE |
| p6_tfdu_idle | PASS | `evidence/hardware/p6/bitstreams/p6_tfdu_idle_0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d.bit` | `0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d` | P6_IMMUTABLE_JTAG_AXI_DYNAMIC_TRANSPORT_CANDIDATE_ACTIVE_IDLE |
| p6_local_transport | PASS | `evidence/hardware/p6/bitstreams/p6_local_transport_0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d.bit` | `0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d` | P6_LIVE_JTAG_AXI_DYNAMIC_PAYLOAD_PHYSICAL_TRANSPORT |
| p6_two_lane_soak | PASS | `evidence/hardware/p6/bitstreams/p6_two_lane_soak_0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d.bit` | `0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d` | P6_STATIONARY_TWO_LANE_2H_DYNAMIC_PAYLOAD_SOAK |
| p6_ps_runtime | PASS | `evidence/hardware/p6/bitstreams/p6_ps_runtime_4bdb0aaeb75c6dcf9837a06cda6b7f445063dd65bf07756162b5ea8fbf537cd5.bit` | `4bdb0aaeb75c6dcf9837a06cda6b7f445063dd65bf07756162b5ea8fbf537cd5` | P6_PS7_AXI_MAILBOX_RUNTIME_CANDIDATE |

## Active Input Hashes

- constraint_file: `cff1a17ee77bbaf90080cf4f97e5920e961aefae3b6752f080e35fcf4d4b1f11`
- active_profile: `7c932dfed5d29298cdfad2164aed2fcfca554aadbe4aed86eed7715864f9f2b1`
- pinmap: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
- active_xdc: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
- register_map: `d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d`
- tfdu_safety_contract: `ff8f94e0aaba1d4bad239de59fea46a7a044f779e95bc04f00269d9fce5f03ae`
- tfdu_safety_summary: `0bc9af6cfeeb9dae03a9cafe7a645bcbfee8522454a18d3cbd6f816bd8861a0f`
- shutdown_bitstream: `bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`

## Candidate Build Gates

- JTAG/AXI candidate: PASS
- JTAG/AXI timing met: true
- JTAG/AXI DRC clean: true
- PS candidate: PASS
- PS timing met: true
- PS DRC clean: true
- PS runtime ELF build: PASS
