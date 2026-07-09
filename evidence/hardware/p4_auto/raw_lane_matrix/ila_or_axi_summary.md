# P4 Auto Raw Lane Matrix Summary

generated_at_utc: 2026-07-09T06:19:33+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: PASS
reason: low-duty raw lane matrix runtime evidence generated
hardware_actions_executed: true
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

RAW_LANE_MATRIX: PASS
RAW_LANE_MATRIX_PROGRAM: PASS
BITSTREAM_SHA_MATCH: PASS
DEBUG_READBACK_AVAILABLE: PASS

| Direction | Status | TX Count | RX Count | TXD High Max Cycles |
| --- | --- | --- | --- | --- |
| AB_L0 | PASS | 64 | 64 | 8 |
| BA_L0 | PASS | 64 | 64 | 8 |
| AB_L1 | PASS | 64 | 64 | 8 |
| BA_L1 | PASS | 64 | 64 | 8 |

TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0
SHUTDOWN_ON_EXIT: PASS
HARDWARE_ACCEPTANCE: PENDING_HW

## Boundary

- This is authorized low-duty raw physical pulse evidence for lane0/lane1 AB/BA only.
- It is not frame/CRC, ACK/retry, Ethernet, rotation, soak, or product-final acceptance.
