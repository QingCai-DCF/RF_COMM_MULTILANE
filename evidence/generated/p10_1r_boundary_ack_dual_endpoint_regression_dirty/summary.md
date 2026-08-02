# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `32e06dc101c7d2b393cef94bc213db300efb27a55d22f8fb958f210d113192ba` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `5ec40c44b5e24b2871c3cf11d4db3ad3d057982baf11128b3ef74804cae1bb70` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `6efc5232c117c3224e7ea40b0a758f1391d1bccc4b00050fbb6b933bf0742982` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_boundary_ack_dual_endpoint_regression_dirty/raw/20260802T093637.103915Z`
