# Tfdu Control Idle Recheck

generated_at_utc: 2026-07-09T14:55:33+00:00
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

TFDU_CONTROL_IDLE_RECHECK: PASS
TFDU_CONTROL_IDLE_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit`
BITSTREAM_SHA256: `08f3bc790fb8da67c642c69f695e9bcd66b27a40030be971d2d7d9bb4cbbc442`
PROFILE: `profiles/p5/p5_tfdu_control_idle_recheck.json`
PROFILE_SHA256: `56e8afc772759bb769315b99700d653bfa9d5525dd81a56f0acf7451e799a983`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_tfdu_control_idle_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `aeca9440d645b5144d5df67f2bf074125a08807d937a1215f1a4bd16ac395723`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/tfdu_control_idle_recheck`

## Counters

TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 0
TXD_HIGH_TOTAL_CYCLES: 0
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0

## Boundary

- This is authorized P5 stationary 2-lane internal/proxy JTAG/ILA evidence.
- It is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.
