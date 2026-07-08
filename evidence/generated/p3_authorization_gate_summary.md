# P3 Authorization Gate Summary

generated_at_utc: 2026-07-08T14:23:28+00:00
repo: C:\Users\user\Documents\RF_COMM_MULTILANE
HEAD: c3abf1171228f52f400e6e4a3233472e1dad90bf
RESULT: PASS
REASON: authorization dry-run gate is present and missing by design
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

AUTHORIZATION_GATE_DRY_RUN: PASS
HARDWARE_AUTHORIZATION: MISSING_BY_DESIGN
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Required Future Inputs

- `--execute-hardware`
- `--max-runtime-sec <N>`
- `--shutdown-on-exit`
- `--bitstream <path>`
- `--board-id <id>`
- `--test-profile <profile>`
- `--active-xdc-hash <sha256>`
- `--active-pinmap-hash <sha256>`
- `RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW`
- `evidence/authorization/hardware_acceptance_authorized.md` exists and is not the template
