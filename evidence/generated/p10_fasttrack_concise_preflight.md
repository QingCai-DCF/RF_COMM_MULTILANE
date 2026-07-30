# P10 fast-track concise preflight

- Result: `PASS`
- Branch: `p10/ax7020-dual-node-2lane`
- Base/HEAD: `95da5672f29278c9e8129662715e9367312514d8`
- Includes main: `True`
- Includes P8E: `True`
- Includes P9: `True`
- Tracked worktree clean before checks: `True`
- Preflight subphase environment: `NO_HARDWARE=1`, `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`.
- Hardware actions executed: `false`.

| Check | Result | Exit | Duration (s) | Raw log |
|---|---|---:|---:|---|
| `p8a_consistency` | PASS | 0 | 13.194 | `evidence/generated/p10_preflight_raw/p8a_consistency.txt` |
| `p8e_verify_existing` | PASS | 0 | 8.074 | `evidence/generated/p10_preflight_raw/p8e_verify_existing.txt` |
| `p9_verify_existing` | PASS | 0 | 0.788 | `evidence/generated/p10_preflight_raw/p9_verify_existing.txt` |
| `no_hardware_static_scan` | PASS | 0 | 0.042 | `evidence/generated/p10_preflight_raw/no_hardware_static_scan.txt` |

The fast-track hardware authorization remains present, but the wiring audit separately blocks hardware admission.
