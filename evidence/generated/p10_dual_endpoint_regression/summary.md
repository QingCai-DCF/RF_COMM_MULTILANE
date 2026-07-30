# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `65402de96d34761219593d4601f8cb7e0d7df1cde013241a175c4fbefb6507ed` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `ce24252c45bba7e09354ee6b8f2ddc021fb2cb490fe723951a8afc6e74577be1` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `b2b79a07d7fef7a7659d2aabe7ebef19d06d5491c8be7e2de0096954ed3797bd` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `44ff822f0db7dcf055aab9b4546c9cfeb6a8786a3f2b881874b84cf46a617ac8` |

Raw run: `evidence/generated/p10_dual_endpoint_regression/raw/20260730T154545.758867Z`
