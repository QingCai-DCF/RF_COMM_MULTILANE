# Hardware Authorization

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

No hardware action is authorized by files in this directory during P3.

Future P4 hardware acceptance requires all of these controls at the same time:

- CLI flag `--execute-hardware`.
- CLI flag `--max-runtime-sec <N>`.
- CLI flag `--shutdown-on-exit`.
- Environment variable `RF_COMM_HW_AUTH=I_ACCEPT_TFDU6102_RISK_AND_AUTHORIZE_HW`.
- A real authorization file at `evidence/authorization/hardware_acceptance_authorized.md`.
- Explicit bitstream path, board identifier, active XDC hash, active pinmap hash, and test profile.
- Passing preflight from the same commit.

The `.template` file is not authorization.
