# P10 dual-independent-endpoint portable regression

- Status: `FAIL`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | FAIL | `ee7e65d9a9fa13c0ca39bc6835b564e36903145b50df5b477915aefff064194a` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `2f3109fadbbae5f03138238cbff310dc6cf7a666a719f03bf2861e7d727cc9cd` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `8de99242952523d9c2e0ddb20a7717dbd77580a693155dcf9f83e2a1dacf7a4e` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `1f0b3f7742f5abd65d58e68d23f3b7494885aabf3fc212ffb8b48c5387326593` |

Raw run: `evidence/generated/p10_dual_endpoint_regression/raw/20260731T075929.891755Z`
