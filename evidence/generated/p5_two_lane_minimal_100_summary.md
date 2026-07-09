# Two Lane Minimal 100

generated_at_utc: 2026-07-09T15:10:21+00:00
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

TWO_LANE_MINIMAL_100: PASS
TWO_LANE_MINIMAL_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit`
BITSTREAM_SHA256: `bed545a125e77116788eb9fd665f69dc3f02775b09eb8e9400f4fd06c492d608`
PROFILE: `profiles/p5/p5_two_lane_minimal_100.json`
PROFILE_SHA256: `7b2d8b7b41e7eb54e07645cd078efcd5be734c4f0dddce2188b5ffd9ccfcbac9`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_protocol_two_lane_minimal_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `098689de82971c9fbe157057cea85c0b012c5bcd1146ba1c4b07e27d6d8d3a71`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/two_lane_minimal_100`

## Counters

SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x3
ACK_LANE_MASK_READBACK: 0x3
A_SENT_FRAMES_PER_LANE: 100
REQUESTED_FRAMES_PER_LANE: 100
LANE0_RX_GOOD: 100
LANE1_RX_GOOD: 100
TOTAL_RX_GOOD: 200
LANE0_ACK_SENT: 100
LANE1_ACK_SENT: 100
CRC_BAD: 0
PAYLOAD_MISMATCH: 0
TX_RETRY_EXHAUSTED: 0
TX_FAIL: 0
TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 8
TXD_HIGH_TOTAL_CYCLES: 25728
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0

## Boundary

- This is authorized P5 stationary 2-lane internal/proxy JTAG/ILA evidence.
- It is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.
