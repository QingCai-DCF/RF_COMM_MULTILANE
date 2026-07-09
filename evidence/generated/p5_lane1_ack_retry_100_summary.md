# Lane1 Ack Retry 100

generated_at_utc: 2026-07-09T15:07:53+00:00
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

LANE1_ACK_RETRY_100: PASS
LANE1_ACK_RETRY_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit`
BITSTREAM_SHA256: `b072db80e4c88b36e9f2d326d6d5c2027357763a1cd47ffafaaa147572996f9f`
PROFILE: `profiles/p5/p5_lane1_ack_retry_100.json`
PROFILE_SHA256: `d1c19f9fda5da22c04e4335a40f9ee9ee84d7059026673e99995f2f123295284`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_protocol_lane1_ack_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `cfcf74e52cf6b5e317f1e3a9a975e083c195c2bdbea53988c0da852d3cfff1d8`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/lane1_ack_retry_100`

## Counters

SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x2
ACK_LANE_MASK_READBACK: 0x2
REQUESTED_FRAMES: 100
A_SENT_FRAMES: 100
B_RX_GOOD: 100
B_ACK_SENT: 100
A_ACK_SEEN: 100
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
