# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `bdbfcdea9ec97bd4498513d4ba251ef8c5d67135c6aa860a130888fe3aa0af4a` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `ee55aec4df27db7300ef8ae723d39eb0ebc7e01dbb235882d413201390363c1f` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `8de99242952523d9c2e0ddb20a7717dbd77580a693155dcf9f83e2a1dacf7a4e` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `32e150c4eb5f686ab75900e2add4b540f5852a0e437e0db74493e6c20c14f20f` |

Raw run: `evidence/generated/p10_1_led_dual_endpoint_regression/raw/20260731T083509.842875Z`
