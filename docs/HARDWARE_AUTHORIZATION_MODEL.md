# Hardware Authorization Model

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

Hardware is locked by default. P3 only defines the future P4 authorization model.

## Required Controls

Future hardware execution must provide:

- `--execute-hardware`
- `--max-runtime-sec <N>`
- `--shutdown-on-exit`
- `--bitstream <path>`
- `--board-id <id>`
- `--test-profile <profile>`
- `--active-xdc-hash <sha256>`
- `--active-pinmap-hash <sha256>`
- `RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW`
- `evidence/authorization/hardware_acceptance_authorized.md`

The checker exits before any hardware connection or device IO when a required
control is missing. The template file is deliberately insufficient.

## P3 Expected State

AUTHORIZATION_GATE_DRY_RUN: PASS
HARDWARE_AUTHORIZATION: MISSING_BY_DESIGN
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
