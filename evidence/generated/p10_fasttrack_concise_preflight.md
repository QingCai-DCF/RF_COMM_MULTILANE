# P10 fast-track concise preflight

- Result: `FAIL`
- Branch: `p10/ax7020-dual-node-2lane`
- Base/HEAD: `d68bbca1bfb8e95fbb24278f953f8d56de24b910`
- Includes main: `True`
- Includes P8E: `True`
- Includes P9: `True`
- Tracked worktree clean before checks: `True`
- Preflight subphase environment: `NO_HARDWARE=1`, `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`.
- Hardware actions executed: `false`.

| Check | Result | Exit | Duration (s) | Raw log |
|---|---|---:|---:|---|
| `p8a_consistency` | FAIL | 1 | 0.048 | `evidence/generated/p10_preflight_raw/p8a_consistency.txt` |
| `p8e_verify_existing` | FAIL | 1 | 0.055 | `evidence/generated/p10_preflight_raw/p8e_verify_existing.txt` |
| `p9_verify_existing` | PASS | 0 | 0.942 | `evidence/generated/p10_preflight_raw/p9_verify_existing.txt` |
| `no_hardware_static_scan` | PASS | 0 | 0.046 | `evidence/generated/p10_preflight_raw/no_hardware_static_scan.txt` |

The fast-track hardware authorization remains present, but the wiring audit separately blocks hardware admission.
