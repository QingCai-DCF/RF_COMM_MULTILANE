# P4 Auto Lane0 Frame CRC Summary

generated_at_utc: 2026-07-09T07:24:55+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: PASS
reason: lane0 deterministic frame/CRC runtime evidence generated
hardware_actions_executed: true
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

LANE0_FRAME_CRC: PASS
LANE0_FRAME_CRC_PROGRAM: PASS
CONFIG_READBACK: PASS
BITSTREAM_SHA_MATCH: PASS
DEBUG_READBACK_AVAILABLE: PASS
SESSION_READBACK: 0x2201
LANE_MASK_READBACK: 0x1
ACK_LANE_MASK_READBACK: 0x0
SENT_FRAMES: 2
RX_GOOD: 2
FRAME_BAD: 0
CRC_BAD: 0
PAYLOAD_MISMATCH: 0
TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 8
TXD_HIGH_TOTAL_CYCLES: 2432
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACCEPTANCE: PENDING_HW

## Boundary

- This is authorized lane0 deterministic frame/CRC smoke evidence with ACK disabled.
- It is not ACK/retry, lane1, two-lane, Ethernet, rotation, soak, or product-final acceptance.
