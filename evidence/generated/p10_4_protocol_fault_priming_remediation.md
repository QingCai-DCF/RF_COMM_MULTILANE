# P10.4 protocol-fault priming remediation

- Status: `PASS`
- Prior run: `p10_4_20260805T144037Z_a32afe5b_6f915067_ace48b07` (`PARTIAL`)
- Prior shutdown: fixed `PASS`, rotating `PASS`
- Direct failure: `duplicate_segment:rotating:injected fault not observed`
- Cause: object 1 was not directly receiver-primed before the sender consumed its bounded corrupt-attempt budget.
- Repair: duplicate/stale diagnostics now use host-verified, receiver-primed object 0.
- Safety-path change: `false`
- New artifact source: `6c7418e630d07be54e01d51ba05d90d6ceac3990`
- New artifact freeze SHA256: `2b745161c67aedc1bd62725f5e2d1d35f6f4ac1d3c19b805c1934d1b2ba2b5e3`
- Offline gates: `13/13 PASS`
- XSIM: `PASS`
- Old hardware PASS inherited: `false`
- Hardware actions executed during remediation/build: `false`
