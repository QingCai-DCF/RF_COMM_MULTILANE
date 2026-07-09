# P4 Auto Safe Idle Direct Proxy Summary

generated_at_utc: 2026-07-09T10:02:47+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL
result: PASS_OFFLINE_ILA_INSTRUMENTED
reason: safe-idle static internal proxy evidence generated
hardware_actions_executed: false
user_confirmed_supply_ok: true
manual_intervention_required: false
shutdown_on_exit: required
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

SAFE_IDLE_DIRECT_PROXY: PASS_OFFLINE_ILA_INSTRUMENTED
SAFE_IDLE_PROGRAM: SKIP_NO_HARDWARE_ACTIONS
BITSTREAM_SHA_MATCH: PASS_STATIC_MANIFEST_ONLY
DEBUG_READBACK_AVAILABLE: PASS_OFFLINE_STATIC_PROXY
ILA_INSTRUMENTED: 0
ILA_CORE_INSERTION: PASS
ILA_PROBE0_WIDTH: 768
DEBUG_PROBES_LTX: `evidence/generated/vivado/p4_auto_safe_idle_debug.ltx`
MODE_CMD_ALL_LANES: 1
SD_CMD_ALL_LANES: 0
TXD_CMD_ALL_LANES: 0
TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 0
TXD_STUCK_HIGH_VIOLATION: 0
DUTY_WINDOW_VIOLATION: 0
UNEXPECTED_TX_PULSE_COUNT: 0
SHUTDOWN_STATE: 0
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Boundary

- This is static internal/proxy evidence from the active safe-idle RTL and debug probe.
- It is not external pin oscilloscope verification.
- It does not promote hardware acceptance to PASS without authorized programming and readback.
