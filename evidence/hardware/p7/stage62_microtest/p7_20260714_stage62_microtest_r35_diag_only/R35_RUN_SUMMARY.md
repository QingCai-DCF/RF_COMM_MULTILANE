# R35 Stage62-only microtest summary

RESULT: `FAIL_WRAPPER_POSTPROCESS`

- `run_id=p7_20260714_stage62_microtest_r35_diag_only`
- `diagnostic_valid=false`
- `acceptance_valid=false`
- `functional_stages_1_61_executed=false`
- `stage62_executed=false`
- `coverage_claimed=false`
- `HARDWARE_ACCEPTANCE=PENDING_HW`
- `failure=NameError(P7_STAGE62_MICROTEST_RECORD_MAGIC)`
- `posthoc_parser_replay=REJECTED_OFFLINE_ONLY`
- `secondary_defect=COPY_OK retained CONTROL error_code and zero first_bad_index`
- `shutdown_before=PASS`
- `shutdown_after=PASS`
- `independent_recovery=PASS`
- `safe_shutdown_complete=true`
- `active_runner=false`
- `active_xsdb_transaction=false`
- `runner_lock=free`

The raw microtest markers and dumps are preserved but are not promoted as a
diagnostic or acceptance result because the official host wrapper failed before
publishing its terminal summary. The post-hoc parser replay is offline-only; it
confirmed a microtest record-initialization defect but is not a hardware result.
R35 is immutable and must never be resumed or reused; the next eligible run ID
is `p7_20260714_stage62_microtest_r36_diag_only`.
