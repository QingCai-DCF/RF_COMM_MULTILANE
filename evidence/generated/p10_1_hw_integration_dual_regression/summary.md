# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `3f827490263de22031df978136e47b275e5f4c3ea68a5e38db3735c5bbd142a6` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `45fcadaf4b18f1963ef9d1941edfabd06d1334c0992b3ae0a2ec40af7be22323` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `450b3e63504d6125e945688f77c0739b05de755938ebb549160eeb97fa93e9a5` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `1f0b3f7742f5abd65d58e68d23f3b7494885aabf3fc212ffb8b48c5387326593` |

Raw run: `evidence/generated/p10_1_hw_integration_dual_regression/raw/20260731T151440.756972Z`
