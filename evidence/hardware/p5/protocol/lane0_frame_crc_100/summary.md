# Lane0 Frame Crc 100

generated_at_utc: 2026-07-09T15:00:30+00:00
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

LANE0_FRAME_CRC_100: PASS
LANE0_FRAME_CRC_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_protocol_lane0.bit`
BITSTREAM_SHA256: `7d92c8b86b74c75bd349f04545a22681cd3269b4c4ade40ec1aa7c6db8e84dfe`
PROFILE: `profiles/p5/p5_lane0_frame_crc_100.json`
PROFILE_SHA256: `c23877ac72d1e7902a5eccd42d1810577b8be1114f1089003a1673d7190afc65`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_protocol_lane0_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `ddcdd15fc6aeec9d7cba82df6c14ecfb1396905e7328dad7b134ac08881b5c68`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/lane0_frame_crc_100`

## Counters

SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x1
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
