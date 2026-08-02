# P10.1R offline finalizer precondition failure

- Status: `FAIL`
- Hardware actions executed: `false`
- Exact source commit: `a1ac5457bc1555312c00dda81f2e2ad3a7c9751a`
- Failure: `dual_endpoint_regression: source commit mismatch`
- Stale regression source: `8bb759047276e5bb9952403013d1d33cea6bba92`

The failed finalizer attempt was preserved rather than promoted. The portable
dual-endpoint regression was rerun from the exact frozen source, after which
the finalizer produced `OFFLINE_READY_HARDWARE_PENDING`. See
`evidence/generated/p10_1r_dual_endpoint_regression/summary.json` and
`evidence/generated/p10_1r_offline_final_summary.json`.
