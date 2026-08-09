# P10.5 zero-credit reopen diagnosis

- Status: `CONFIRMED_REMEDIATED_OFFLINE_PENDING_NEW_HARDWARE`
- Failed run: `p10_5_20260809T193616Z_33273a1a_3aa03b83_605dd1b6`
- Failed stage/case: `one_plus_one / oneplusone_f0_r1`
- Root cause: both local RX windows had reopened to 32 credits, while both
  transmitters retained the last advertised peer credit of zero.
- Focused regression: `PASS`, forced 32-entry zero-credit state followed by
  8500-byte exact transfer in each direction.
- Hardware actions executed by remediation: `false`
- Old hardware PASS inherited: `false`
