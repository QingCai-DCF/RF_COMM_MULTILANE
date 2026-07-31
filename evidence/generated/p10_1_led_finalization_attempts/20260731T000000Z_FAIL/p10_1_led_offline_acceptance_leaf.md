# P10.1 AX7020 PL activity LED offline acceptance leaf

- Status: `FAIL`
- Test ID: `P10_1-LED-OFFLINE-ACCEPTANCE-LEAF`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`

The fixed and rotating roles use the same active-low mapping: LED1 lane0 TX, LED2 lane0 RX, LED3 lane1 TX, LED4 lane1 RX.

This is offline acceptance only. The LED outputs are pure monitor taps and do not establish safety, electrical, protocol, or optical success.

## Errors

- tfdu_safety_regression: hardware_actions_executed is not false
- tfdu_safety_regression: current_run_hardware_authorization is not false
