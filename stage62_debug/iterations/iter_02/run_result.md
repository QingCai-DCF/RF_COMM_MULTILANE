# Iteration 02 result

Result: `FAIL_WRAPPER_POSTPROCESS`

- `run_id=p7_20260714_stage62_microtest_r35_diag_only`
- `wrapper_returncode=1`
- `failure=NameError(P7_STAGE62_MICROTEST_RECORD_MAGIC)`
- `official_wrapper_summary_created=false`
- `diagnostic_valid=false`
- `acceptance_valid=false`
- `functional_stages_1_61_executed=false`
- `stage62_executed=false`
- `shutdown_before=PASS`
- `shutdown_after=PASS`
- `independent_recovery=PASS`
- `safe_shutdown_complete=true`

A post-hoc parser replay also rejected the raw COPY_OK record because the
firmware retained `error_code=CONTROL` and `first_bad_index=0`. That replay is
offline-only and is not a hardware diagnostic PASS/FAIL claim.
