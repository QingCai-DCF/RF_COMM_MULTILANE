# Lane0 Ack Retry 100

generated_at_utc: 2026-07-09T15:05:25+00:00
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

LANE0_ACK_RETRY_100: PASS
LANE0_ACK_RETRY_ILA_PARSE: PASS
PROGRAM: PASS
ILA_CAPTURE: PASS
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACTIONS_EXECUTED: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
BITSTREAM: `evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit`
BITSTREAM_SHA256: `e0e07d7f1d646ad8dd87b32efbeb24442daa6b74cd1f267a6ea8bb727d30c258`
PROFILE: `profiles/p5/p5_lane0_ack_retry_100.json`
PROFILE_SHA256: `1a70862178dfcbf41aec53676c4ebe1f4f5e23b095a9eda84be5510b9ec54c74`
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_protocol_lane0_ack_debug.ltx`
DEBUG_PROBES_LTX_SHA256: `a08e045d7b2a1880897506fc94c99cc7f25b0f792a6a64bc2be92c48e18d602d`
ILA_CAPTURE_DIR: `evidence/hardware/p5/ila/lane0_ack_retry_100`

## Counters

SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x1
ACK_LANE_MASK_READBACK: 0x1
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
