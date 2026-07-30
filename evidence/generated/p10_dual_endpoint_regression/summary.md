# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `27bec543773004df8a79691980bf6a26d2fbec479b8a9986f6cc7aecec22418b` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `f849600ec67bda5ff126b7c3551b7f628b68ac96badd843203996b66f35423db` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `a88ca28a408cf35aa27aca70e29dd511e7ead31ce1c18bace55fe7c95aaeaf42` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `44ff822f0db7dcf055aab9b4546c9cfeb6a8786a3f2b881874b84cf46a617ac8` |

Raw run: `evidence/generated/p10_dual_endpoint_regression/raw/20260730T143224.799157Z`
