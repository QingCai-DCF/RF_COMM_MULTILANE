# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `a6074891d15c5616b32eb2c0261fb7dd7003bf5847060e9bf0d1630be112dce1` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `45634ddea88fe94ee0e8ba4587d68b3027af0a9e264649d99c2959760e8463e1` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `ebba9748ac48cdb4b3cf03fd01fd4e865b7265b2e958be35ea8a20768ff95e33` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260803T075534.515793Z`
