# P4 No Hardware Or Authorized Hardware Scan

generated_at_utc: 2026-07-08T15:50:15+00:00
repo: `C:\Users\user\Documents\RF_COMM_MULTILANE`
HEAD: `4768ef76c1d9bc6042d4058f52eef5fc0da5ca01`
RESULT: PASS
REASON: P4 entrypoint either produced dry-run evidence or used only the authorized safe wrapper
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: FAIL_WITH_EVIDENCE

P4_NO_HARDWARE_OR_AUTHORIZED_HARDWARE_SCAN: PASS
NO_HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: FAIL_WITH_EVIDENCE

- authorization status: AUTHORIZED
- environment capture: PASS
- safe-idle programming/readback: PASS_WITH_LIMITED_READBACK
- shutdown-on-exit: PASS
- no PS ELF start
- no UART command
- no ILA capture
- no intentional TFDU TX pulse
