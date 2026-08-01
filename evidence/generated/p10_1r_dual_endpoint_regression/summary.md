# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `71fc0fce1ae3a28615e93ee78f07af8c0f409d4e516bf17ca09e8b35207ef6d8` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `3d6b5b5175d365b8362efdf750286c263a4ac2898793a26803932c9858850d56` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `8de99242952523d9c2e0ddb20a7717dbd77580a693155dcf9f83e2a1dacf7a4e` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260801T193120.580306Z`
