# P5 Raw Lane Matrix Failure Package

P5_FAILURE_PACKAGE: GENERATED
FAILURE_STAGE: RAW_LANE_MATRIX_FRESH
FAILURE_CLASS: RAW_LANE_MATRIX_DIRECTION_FAILURE
SHUTDOWN_ON_EXIT: PASS
STOP_CONDITIONS_TRIGGERED: hardware_stage_failure:RAW_LANE_MATRIX_FRESH
HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Failing Directions

- BA_L1: status=FAIL_WITH_EVIDENCE tx_observed=44 expected=64 rx_active_low_pulse_count=44

## Boundary

- Hardware progression is stopped before frame/CRC, ACK/retry, payload sweep, mask regression, and soak expansion.
- Shutdown was attempted after the failed stage and must be PASS to consider this failure package complete.
