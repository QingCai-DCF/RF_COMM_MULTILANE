# P6 Profiles Summary

generated_at_utc: 2026-07-10T09:15:16+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `5b90d41a6750aad8023071433996fee3f068efe2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: P6 profiles generated for stationary 2-lane no-Ethernet scope
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

P6_PROFILES: PASS
P6_PROFILE_COUNT: 10
script_hardware_actions_executed: false
source_evidence_contains_hardware_actions: false

## Profiles

- `profiles/p6/p6_safe_idle_recheck.json` sha256=`a174d1de3da3e7787219407be46bb65ce7caaabd755a38b329d18615c6bd7776`
- `profiles/p6/p6_tfdu_control_idle_recheck.json` sha256=`275dcc27e0b9ea1c91140facadc1b8e02c7f6c63e52b003a97edfb9397a33042`
- `profiles/p6/p6_jtag_axi_payload_ram_smoke.json` sha256=`eedceda122ce4c9dcc48216c3a0b57ab89c64692005ecf23f9beaae504b57c82`
- `profiles/p6/p6_lane0_dynamic_payload_256.json` sha256=`50cf43a3dab72e14b70141c75acbe92792f1f0df38e29eab0346608041899a34`
- `profiles/p6/p6_lane1_dynamic_payload_256.json` sha256=`ffd08b15a355c4ec2047418a7533aba67c79858779025d043f92c29f1a79f6b3`
- `profiles/p6/p6_two_lane_dynamic_payload_256.json` sha256=`b64c68dc127a5c026f0eb978ed96ed7eb58ba56a5863c0818e613b45f282f069`
- `profiles/p6/p6_ps_driver_runtime_mailbox.json` sha256=`0a0185b3bfdc182d5659747e7c6c0d1f82d6c79ddb3f708044ffdab6c06e4edc`
- `profiles/p6/p6_host_file_transport_jtag.json` sha256=`7a9085b250dd595f37527c0438a982de2ae93f5dc55aef5e2fc4485bf07d9bcc`
- `profiles/p6/p6_lane_fallback_regression.json` sha256=`68e64976ba06e9b1cf3c8727cd887751af4cb68947f441158c145bc50abefeca`
- `profiles/p6/p6_two_lane_2h_stationary_soak.json` sha256=`52b44fe736130161bf88c9281d6b77492dbbecc0263244a7ded487f32568e64b`

## Active Inputs

- constraint_file: `cff1a17ee77bbaf90080cf4f97e5920e961aefae3b6752f080e35fcf4d4b1f11`
- active_profile: `7c932dfed5d29298cdfad2164aed2fcfca554aadbe4aed86eed7715864f9f2b1`
- pinmap: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
- active_xdc: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
- register_map: `d5b0bf1476d815a3ed69988c72097827356d4eade48813c8913fc1b2d448983d`
- tfdu_safety_contract: `ff8f94e0aaba1d4bad239de59fea46a7a044f779e95bc04f00269d9fce5f03ae`
- tfdu_safety_summary: `0bc9af6cfeeb9dae03a9cafe7a645bcbfee8522454a18d3cbd6f816bd8861a0f`
- shutdown_bitstream: `bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`
