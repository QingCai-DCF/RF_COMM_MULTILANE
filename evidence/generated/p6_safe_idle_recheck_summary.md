# P6 Safe Idle Recheck

generated_at_utc: 2026-07-09T17:43:15+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `7a5f0ca068f983d85a6b85c95fa0d4fa3eee4ff2`
stage: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
result: PASS
reason: authorized P6 hardware stage executed
script_hardware_actions_executed: true
source_evidence_contains_hardware_actions: true
stage_programmed_fpga: see stage section
stage_drove_tfdu_txd: see stage section
stage_enabled_tfdu_receiver: see stage section
shutdown_on_exit_observed: see stage section
product_final_acceptance: pending
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
max_lane_mask: 0x3

P6_SAFE_IDLE_RECHECK: PASS
SAFE_IDLE_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
script_hardware_actions_executed: true
source_evidence_contains_hardware_actions: true
stage_programmed_fpga: true
stage_drove_tfdu_txd: false
stage_enabled_tfdu_receiver: false
shutdown_on_exit_observed: true
BITSTREAM: `evidence/hardware/p6/bitstreams/p6_safe_idle_6925b69eb0d43aa788cb3d2fe8a8ce543de93da0200183d737214b899c5d394b.bit`
BITSTREAM_SHA256: `6925b69eb0d43aa788cb3d2fe8a8ce543de93da0200183d737214b899c5d394b`
PROFILE: `profiles/p6/p6_safe_idle_recheck.json`
PROFILE_SHA256: `a174d1de3da3e7787219407be46bb65ce7caaabd755a38b329d18615c6bd7776`

## Boundary

- This P6 hardware action is stationary, 2-lane, automated Vivado/JTAG/ILA evidence.
- It does not use Ethernet, motion, rotation, 4-lane/8-lane, or lane mask above 0x3.
- It is not P6 dynamic payload or product-final acceptance.
