# P10.1R echo-calibration artifact freeze

- Status: `PASS`
- Test ID: `P10_1R-ECHO-CALIBRATION-ARTIFACT-FREEZE`
- Purpose: `ECHO_CALIBRATION_ONLY`
- Acceptance eligible: `false`
- Allowed hardware stages: `preflight`, `echo_tail`
- Hardware actions executed: `false`
- Current-run hardware authorization: `false`

The functional, XSA, and shutdown artifacts retain source provenance
`493955d5788942ac448a9cfd99c97f0c526281fe`. The identity-corrected BSP/ELF
artifacts retain source provenance
`38f83531f51ad052d72680a4df69920d76131728`. Every item records its own
`built_source_commit`, path, size, and SHA256 in the adjacent JSON.

This mixed-provenance bundle may only measure echo tails and select the final
guard. It cannot produce P10.1R acceptance PASS. Guard changes require a new
complete immutable build and hardware acceptance campaign.
