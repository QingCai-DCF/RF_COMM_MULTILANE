# P5 Mask Regression Summary

generated_at_utc: 2026-07-09T15:10:21+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P5_2LANE_PROTOCOL_STABILIZATION
result: PASS
reason: mask regression generated from fresh P5 mask/session readbacks and bounded negative validators
hardware_actions_executed: true
user_confirmed_supply_ok: true
network_cable_connected: false
hardware_movement_allowed: false
available_lanes: 2
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW

MASK_REGRESSION: PASS
SOURCE_HARDWARE_ACTIONS_EXECUTED: true
MASK_REGRESSION_HARDWARE_ACTIONS_EXECUTED: false
NO_ADDITIONAL_HARDWARE_ACTIONS_EXECUTED_BY_MASK_REGRESSION: true
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
positive cases PASS
negative cases REJECTED_AS_EXPECTED or FAIL_SAFE_AS_EXPECTED
no infinite retry
TX_RETRY_EXHAUSTED: 0
TX_FAIL: 0
SHUTDOWN_ON_EXIT: PASS

## Cases

- lane0-only (positive): PASS expected_mask=0x1 actual_mask=0x1 expected_ack=0x1 actual_ack=0x1 expected_session=0x2201 actual_session=0x2201
- lane1-only (positive): PASS expected_mask=0x2 actual_mask=0x2 expected_ack=0x2 actual_ack=0x2 expected_session=0x2201 actual_session=0x2201
- two-lane (positive): PASS expected_mask=0x3 actual_mask=0x3 expected_ack=0x3 actual_ack=0x3 expected_session=0x2201 actual_session=0x2201
- lane0-expected-two-lane (negative): REJECTED_AS_EXPECTED expected_mask=0x3 actual_mask=0x1 expected_ack=0x1 actual_ack=0x1 expected_session=0x2201 actual_session=0x2201
- lane1-expected-two-lane (negative): REJECTED_AS_EXPECTED expected_mask=0x3 actual_mask=0x2 expected_ack=0x2 actual_ack=0x2 expected_session=0x2201 actual_session=0x2201
- session-mismatch (negative): REJECTED_AS_EXPECTED expected_mask=0x3 actual_mask=0x3 expected_ack=0x3 actual_ack=0x3 expected_session=0x2202 actual_session=0x2201
- ack-lane-mask-mismatch (negative): REJECTED_AS_EXPECTED expected_mask=0x1 actual_mask=0x1 expected_ack=0x3 actual_ack=0x1 expected_session=0x2201 actual_session=0x2201

## Boundary

- Negative cases are bounded offline rejections against fresh dynamic P5 readbacks; no unsupported lane mask or motion/Ethernet run was executed.
- This is not Ethernet, rotation/motion, lane_mask > 0x3, 8-lane, external oscilloscope, or product-final acceptance.
