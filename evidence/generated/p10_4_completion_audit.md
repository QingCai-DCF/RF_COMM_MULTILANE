# P10.4 completion audit

Overall status: `FAIL_CLOSED`.

P10.3 closeout, repository intake, immutable artifact freeze, preflight, and fail-closed local-source injection passed. The mandatory `counter_semantics` stage then failed on direct F2→R2 lane-2 progress: F2 emitted 5,324,445 physical TX events while R2 recorded only 99 raw RX events. The reverse direction R2→F2 recorded 4,450,326 TX and exactly 4,450,326 RX with no retries, timeouts, or migrations.

The runner obeyed the Goal's severe-blocker rule. It stopped the campaign before baseline smoke, tuning, 64/128 MiB streaming, lane degrade/recovery, direction switching, reset recovery, 8×8 digital crosstalk, 2+2, and the 1800-second mixed formal. Those stages are not PASS and were not inferred from P10.3 or proxy evidence.

Both role-bound shutdown images were programmed and verified: `SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, `SHUTDOWN_EXIT=0`, and `TFDU_SHUTDOWN_PROGRAMMED=1`. The current-run authorization is consumed and false.

The later verifier-only remediation corrected the generic M4 ownership audit and completed a fresh no-cache canonical offline gate: 31/31 subprocesses passed, with no hardware actions. This does not alter the frozen P10.4 artifact bundle or the hardware result.

Goal result fields:

- `P10_4_CORE_ROBUSTNESS=FAIL`
- `P10_4_HALF_DUPLEX_8MBPS_RETENTION=FAIL_NOT_EXECUTED_AFTER_FAIL_CLOSED`
- `P10_4_MARGIN_TARGET_9MBPS=FAIL_NONBLOCKING_NOT_EXECUTED`
- `P10_4_STRETCH_9P6MBPS=FAIL_NONBLOCKING_NOT_EXECUTED`
- `P10_4_2PLUS2_EXPERIMENT=PARTIAL_NOT_EXECUTED_AFTER_FAIL_CLOSED`
- `P10_4_EXTERNAL_ELECTRICAL=PENDING_NOT_IN_SCOPE`

No P10.4 canonical requirement is promoted by this audit. P10.3's scoped stationary four-lane PASS remains preserved; P11 and product-final scopes remain unstarted/pending.
