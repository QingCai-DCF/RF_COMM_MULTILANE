# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `f4e4435926467a559d5ace63f4c1994fc3f5fe829d0b7520a274c27a8dd8bef3` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `c53337a209a7792de8c8916382c919d2f503e5a40b5de4dab8ebd1ef40e0cecb` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `fb30c6e4ca350e89e517066519d028e58acbfd08b193d4bb14169293c059c5cb` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260802T082719.485825Z`
