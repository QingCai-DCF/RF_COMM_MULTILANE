# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `5ff39d9c62aff3cddefd53591ef864e69bfb84c3ef1754964f4e605780ac4557` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `7ca39038adef8e8de4f7b5bce4dd59a8c898eb0f9d061165d0be61fe7d45940d` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `174bf35d14ec2b102c4881fc42c7976e1ad2fefab86b7ed659134e128ff7eb73` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260802T023203.923940Z`
