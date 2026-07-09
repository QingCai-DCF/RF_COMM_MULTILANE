# Lane1 Frame Crc 100

generated_at_utc: 2026-07-09T15:02:58+00:00
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

LANE1_FRAME_CRC_100: PASS
LANE1_FRAME_CRC_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_protocol_lane1.bit`
BITSTREAM_SHA256: `de7fae7325b107fe11c7f5e9e79c0ae83410984a7594eb7292c9c5652480af7d`
PROFILE: `profiles/p5/p5_lane1_frame_crc_100.json`
PROFILE_SHA256: `6ffd1a20431caca3405dcc81a59143b8d07f97dabcabdfaa71e975a4aae530b9`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_protocol_lane1_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `3c79f27f355c8a114f54059cccf27173b90819e67870544d9888daac6f7c424e`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/lane1_frame_crc_100`

## Counters

SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x2
ACK_LANE_MASK_READBACK: 0x0
SENT_FRAMES: 100
REQUESTED_FRAMES: 100
RX_GOOD: 100
FRAME_BAD: 0
CRC_BAD: 0
PAYLOAD_MISMATCH: 0
TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 8
TXD_HIGH_TOTAL_CYCLES: 56064
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0

## Boundary

- This is authorized P5 stationary 2-lane internal/proxy JTAG/ILA evidence.
- It is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.
