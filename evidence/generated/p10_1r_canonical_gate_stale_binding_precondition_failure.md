# P10.1R canonical-gate stale-binding precondition failure

- Status: `RECORDED_PRECONDITION_FAILURE`
- Source commit: `cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`

The first exact-source canonical run completed the real Vivado process but failed before acceptance because `config/project_requirements.yaml` still bound 19 P10.1R evidence records from the preceding immutable bundle. The two direct failures were `p8a_unit_tests` and `p8a_consistency`; plan-audit failures were downstream consequences.

The binding set and generated traceability matrix were refreshed mechanically, then the full canonical real-build gate was rerun rather than promoting the failed run. The corrected summary is `PASS` with `OFFLINE_REAL_BUILD_PROCESS_RAN=true` and SHA256 `91293a11f245f7abd45eef1ec9b6c7feb94cb9dff98b7dd6b8477df97dcf24a4`.

The first transient summary file was overwritten by the required corrected canonical run before it was archived. This evidence records that retention gap explicitly. The causal mismatch remains reproducible from the source-commit requirements blob (`b63148c2e31e6a486c22c6142d2bbee0fd127eb78b3ec999a6a0bf0386218391`) against the new exact-source evidence. No hardware scope or PASS is inferred from the failed run.
