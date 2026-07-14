# r32 terminal result

- Run ID: `p7_20260713_stationary_app_r32_diag_suffix55`
- Result: `FAILED`
- Acceptance: `HARDWARE_ACCEPTANCE=PENDING_HW`, `coverage_claimed=false`
- Timeout: `false`
- Sequence runner exit: `1`
- Failed ordinal: `62`
- Stage 62 safe-wrapper status: `FAIL_SHUTDOWN_BEFORE`
- Candidate programmed: `false`
- PS ELF downloaded/started: `false` / `false`
- Functional workload executed: `false`
- Firmware error code: `NOT_AVAILABLE_CANDIDATE_NOT_STARTED`
- Result descriptor/mailbox/OCM diagnostic: `MISSING_NOT_CREATED`
- Application output/pre-wipe snapshot: `MISSING_NOT_CREATED`
- Output wipe: `NOT_APPLICABLE_NO_APPLICATION_OUTPUT`
- Wrapper shutdown-after: `PASS`
- Independent shutdown recovery: `PASS`
- Relevant run process remaining: `false`
- New run queued: `false`

State-machine closure:

```text
RUN_TERMINAL_OR_TIMEOUT=FAILED_NOT_TIMEOUT
SAFE_CLEANUP_COMPLETE=true
HANDOFF_CAPTURED=true
MAIN_THREAD_BLOCKED=true
```

The ordinal-62 wrapper invocation is not a Stage 62 functional execution. Shutdown-before failed before candidate programming and ELF start. Diagnostic PASS results for ordinals 1–4 and 55–61 remain zero-coverage observations and do not contribute to formal acceptance.

The final valid safety evidence is the wrapper shutdown-after marker (`a01660d6...`) followed by independent recovery (`8ded9071...`) with `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1` and normalized `SHUTDOWN_EXIT=0`. The raw stage evidence manifest contains 248 records and rehashes without missing or mismatched entries.
