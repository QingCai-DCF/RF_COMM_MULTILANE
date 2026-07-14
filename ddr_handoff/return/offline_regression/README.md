# Offline regression evidence

`complete_suite_summary.json` is the current durable source-bound summary for
the required complete suites at commit
`6e8043716a6797257bbc46c172c287abed93198d`.

The raw current logs remain in the ignored build checkpoint and are bound by
exact size and SHA256 in the summary:

`build/p7_regression_stage62_evidence_fix_6e804371_logs/`

The older `focused_tests.*`, `top_level_discovery.*`, and
`tests_p7_discovery.*` files in this directory belong to the superseded
`af7b5bb6` checkpoint and are retained only as historical evidence. They are
not inputs to the current authorization checkpoint.

The canonical gate at `evidence/generated/p7_offline_gate_summary.json` embeds
the validated current summary payload and its SHA256. Hardware acceptance
remains `PENDING_HW`.
