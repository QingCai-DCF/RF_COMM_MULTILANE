# P10 dual-independent-endpoint portable regression

- Status: `PASS`
- Hardware actions executed: `false`
- Roles: independent fixed endpoint (`DEPLOYMENT_ROLE=1`) and rotating endpoint (`DEPLOYMENT_ROLE=2`).
- Legacy compatibility: the default P9 monolithic role is rerun from the same modified common RTL.

| Test ID | Result | Log SHA256 |
|---|---|---|
| P10-RTL-DUAL-INDEPENDENT-ENDPOINT | PASS | `8bcc0233fc07da51c791294728bb622b9fea39e8e4036709b9505185d2114a62` |
| P10-REGRESSION-P9-LEGACY-MONOLITHIC | PASS | `8df4525dd4848cddde82b1b010c6b89fd2317e6e5f693d3829c4b4f3d119aa42` |
| P10-REGRESSION-P9-RUNNER-UNIT | PASS | `174bf35d14ec2b102c4881fc42c7976e1ad2fefab86b7ed659134e128ff7eb73` |
| P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY | PASS | `69fd6c2ff9cb50eedee1dc433fbd56547d25bf77a87680403d586228c512c38f` |

Raw run: `evidence/generated/p10_1r_dual_endpoint_regression/raw/20260801T223958.542362Z`
