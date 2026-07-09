# Raw Lane Matrix Fresh

generated_at_utc: 2026-07-09T14:58:02+00:00
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

RAW_LANE_MATRIX_FRESH: PASS
RAW_LANE_MATRIX_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit`
BITSTREAM_SHA256: `84946ac4e0b160e45665a2a14c8d5c2e1c861d454c6f8805d3ee65e9228eb54a`
PROFILE: `profiles/p5/p5_raw_lane_matrix_fresh.json`
PROFILE_SHA256: `af75a6b4b9822fea18a9164577abac970f52908f14178d83a4c59494f59f0620`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_raw_lane_matrix_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `a55e0b2e49ed5c1541dbdc2ca0876359f274c7d0d3420746a532cdc1017a16ae`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/raw_lane_matrix`

## Counters

TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0

## Boundary

- This is authorized P5 stationary 2-lane internal/proxy JTAG/ILA evidence.
- It is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.
