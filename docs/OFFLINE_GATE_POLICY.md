# Offline Gate Policy

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

All P1 gates are offline. A gate result is exactly one of PASS, FAIL, or
SKIP_WITH_REASON. Missing tools can be skipped with a reason only; they cannot be
reported as PASS. Offline gates cannot change PENDING_HW to PASS.
