# PS Driver Sequence Summary

RESULT: PASS
REASON: PS driver static sequence markers found
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

- IR_CONTROL_RESET: PASS
- ir_driver_write_profile_registers: PASS
- IR_CONTROL_COMMIT: PASS
- IR_CONTROL_ENABLE_PHY: PASS
- ir_driver_wait_startup: PASS
- IR_CONTROL_CLEAR_STICKY: PASS
- ir_driver_start_transaction: PASS
- ir_driver_poll_done: PASS
- ir_driver_stop: PASS
- ir_driver_read_final_counters: PASS
- ir_driver_shutdown: PASS
