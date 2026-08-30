# P10.5 ten-run hardware authorization — 2026-08-30

- Status: `GRANTED`
- Maximum distinct current-run authorizations: `10`
- One unique run ID and committed current-run authorization per attempt: `true`
- Duplicate offline regression rerun before the first unchanged-bundle run: `waived by user`
- Existing immutable freeze remains mandatory: `PASS`, `acceptance_eligible=true`, zero errors
- Hardware actions executed by this authorization record: `false`

The authorization remains limited to the P10.5 Goal, exact AX7020 board bindings, lane masks up to `0xF`, a maximum 1800-second formal stage, required interstage cooldown, and verified dual shutdown before and after every stage. It does not authorize Ethernet, SPI, movement, rotation, realignment, rewiring, module replacement, P11, or a two-hour run.
