# P4 Auto Lane1 ACK Retry Summary

generated_at_utc: 2026-07-09T08:50:38+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: PASS
reason: lane1 deterministic ACK/retry runtime evidence generated
hardware_actions_executed: true
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

LANE1_ACK_RETRY: PASS
LANE1_ACK_RETRY_PROGRAM: PASS
CONFIG_READBACK: PASS
BITSTREAM_SHA_MATCH: PASS
DEBUG_READBACK_AVAILABLE: PASS
SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x2
ACK_LANE_MASK_READBACK: 0x2
A_SENT_FRAMES: 1
B_RX_GOOD: 1
B_ACK_SENT: 1
A_ACK_SEEN: 1
ACK_SEEN_EVIDENCE: ACK_TX_WINDOW_ACTIVE_LOW_PROXY
TX_RETRY_EXHAUSTED: 0
TX_FAIL: 0
CRC_BAD: 0
PAYLOAD_MISMATCH: 0
A_ACK_RX_ACTIVE_LOW_PULSE_COUNT: 187
B_DATA_RX_ACTIVE_LOW_PULSE_COUNT: 196
TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 8
TXD_HIGH_TOTAL_CYCLES: 1568
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACCEPTANCE: PENDING_HW

## Boundary

- This is authorized lane1 deterministic DATA plus ACK/retry smoke evidence.
- A_ACK_SEEN is internal/proxy readback from A-side active-low RX during the bounded B ACK TX window, not external pin scope verification.
- It is not two-lane, Ethernet, rotation, soak, or product-final acceptance.
