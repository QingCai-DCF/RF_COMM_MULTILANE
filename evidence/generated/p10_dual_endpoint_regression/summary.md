# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `1ebb09a45c9efe20ae077b1ca02500738adc7b03d744e44044289e427d0761fd` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `19720401ae1342b223172ab8e875282d76afec13571fc1a8b68db7d1a9e04995` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `b2b79a07d7fef7a7659d2aabe7ebef19d06d5491c8be7e2de0096954ed3797bd` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `44ff822f0db7dcf055aab9b4546c9cfeb6a8786a3f2b881874b84cf46a617ac8` |

Raw run: `evidence/generated/p10_dual_endpoint_regression/raw/20260730T151137.434158Z`
