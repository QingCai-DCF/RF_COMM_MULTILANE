# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `472817c6f8a8709e386f2c5a47b4b5eb9ce61ffaab1a1323de2bab5f7c01d2d3` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `e1e9a4aa96fbad52f167b726c5f5259015b793e810c18021b7480ee80fb53b96` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `06b39044efd8e54a2b173836a2bf6e935cf21ae6af1bf09db3cd875a10ef0661` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260802T100858.127125Z`
