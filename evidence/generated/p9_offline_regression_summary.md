# P9 Complete Offline Full Regression

- Status: `PASS`
- Test ID: `P9-01-COMPLETE-OFFLINE-FULL-REGRESSION`
- Gates: `32/32 PASS`
- P8E exit gates: `43 PASS`, `0 FAIL`, `0 SKIP`
- P8E manifest: `1970` artifacts
- Runtime: `5224 seconds`
- Hardware actions executed: `false`

The complete base regression and the formal P8E descendant gate passed in one `run_offline_gates.py --include-p8e --json-summary` invocation. A subsequent immutable-manifest verification also passed with zero missing or mismatched artifacts. The adjacent JSON identifies the content-addressed logs and copied summaries. This result does not promote any hardware scope.
