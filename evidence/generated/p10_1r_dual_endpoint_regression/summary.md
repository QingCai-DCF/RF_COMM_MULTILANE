# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `d0d3aedcb8b0c180ad18e71835345dc33a4d8f72d09ab8c7b586d9b863057c1d` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `42e9674a0d4ab2fc779ee2c9fd8e767b9ca37114e08954fff9bccdf5dd3ef906` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `06b39044efd8e54a2b173836a2bf6e935cf21ae6af1bf09db3cd875a10ef0661` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `12019a04b734315db3d4c7a1a826cae11979b179ebd1dee1ba4d3e142bfcbd36` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260801T160108.112427Z`
