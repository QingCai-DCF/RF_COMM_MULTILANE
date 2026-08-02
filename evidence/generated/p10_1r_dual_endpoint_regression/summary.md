# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `f150204196b8b0a77f7e5dde3917e000b8b2c8f0cf4718f7ac53f4aeb1743dd8` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `9b8662a76265c00fe0540f4ee28f9a1d0311cb9b40e8326ffd5df58548ef31c9` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `b2b79a07d7fef7a7659d2aabe7ebef19d06d5491c8be7e2de0096954ed3797bd` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260802T151042.991323Z`
