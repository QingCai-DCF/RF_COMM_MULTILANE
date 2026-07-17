# P3 Pre-Hardware Acceptance Package

> `DOCUMENT_STATUS: HISTORICAL_STAGE_RULE` — retained for P3 replay/audit; it does not govern P8 or authorize hardware.

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P3 prepares the repository for a future P4 hardware acceptance run. It generates
authorization gates, dry-run script checks, constraint freeze records, evidence
schemas, and runbooks. It does not run hardware and it does not claim any
TFDU6102, lane, Ethernet, rotation, soak, or product-final hardware result.

P3 completion criteria:

- Hardware scripts default to dry-run or authorization failure.
- Hardware authorization is missing by design.
- Active XDC and pinmap hashes are frozen.
- TFDU6102 safety contract remains enforced.
- Evidence directories contain blank templates only.
- P4 remains blocked until a new explicit user instruction authorizes hardware.
