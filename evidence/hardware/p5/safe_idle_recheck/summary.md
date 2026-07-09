# Safe Idle Recheck

generated_at_utc: 2026-07-09T14:53:07+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS
reason: authorized P5 hardware stage executed
hardware_actions_executed: true
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

SAFE_IDLE_RECHECK: PASS
SAFE_IDLE_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_safe_idle.bit`
BITSTREAM_SHA256: `6925b69eb0d43aa788cb3d2fe8a8ce543de93da0200183d737214b899c5d394b`
PROFILE: `profiles/p5/p5_safe_idle_recheck.json`
PROFILE_SHA256: `a87424b9e52b088f20b756c5dd32ef7aaf6fc81cbc7399351e56bff56f34b657`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_safe_idle_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `1f5258d51a906547942b5f7260a691fd45ad31cd88734b9aeb26f2d626fce561`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/safe_idle_recheck`

## Counters

TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 0
TXD_HIGH_TOTAL_CYCLES: 0
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0

## Boundary

- This is authorized P5 stationary 2-lane internal/proxy JTAG/ILA evidence.
- It is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.
