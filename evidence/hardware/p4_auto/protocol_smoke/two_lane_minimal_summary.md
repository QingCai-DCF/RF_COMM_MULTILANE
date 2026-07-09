# P4 Auto Two-Lane Minimal Summary

generated_at_utc: 2026-07-09T09:10:24+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: PASS
reason: bounded two-lane minimal runtime evidence generated
hardware_actions_executed: true
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

TWO_LANE_MINIMAL: PASS
TWO_LANE_MINIMAL_PROGRAM: PASS
CONFIG_READBACK: PASS
BITSTREAM_SHA_MATCH: PASS
DEBUG_READBACK_AVAILABLE: PASS
SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x3
ACK_LANE_MASK_READBACK: 0x3
A_SENT_FRAMES_PER_LANE: 1
LANE0_RX_GOOD: 1
LANE1_RX_GOOD: 1
TOTAL_RX_GOOD: 2
LANE0_ACK_SENT: 1
LANE1_ACK_SENT: 1
TX_RETRY_EXHAUSTED: 0
TX_FAIL: 0
CRC_BAD: 0
PAYLOAD_MISMATCH: 0
LANE0_DATA_RX_ACTIVE_LOW_PULSE_COUNT: 196
LANE1_DATA_RX_ACTIVE_LOW_PULSE_COUNT: 196
LANE0_ACK_RX_ACTIVE_LOW_PULSE_COUNT: 186
LANE1_ACK_RX_ACTIVE_LOW_PULSE_COUNT: 187
TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 8
TXD_HIGH_TOTAL_CYCLES: 1568
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACCEPTANCE: PENDING_HW

## Boundary

- This is authorized bounded two-lane minimal DATA plus ACK smoke evidence from one two-lane bitstream.
- It uses internal/proxy ILA readback and raw active-low counters, not external pin scope verification.
- It is not Ethernet, rotation, soak, throughput, 8-lane, or product-final acceptance.
