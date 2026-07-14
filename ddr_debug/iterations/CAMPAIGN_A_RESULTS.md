# DDR External-Master Campaign A Results

- Campaign: `p7_20260714_ddr_external_campaign_a`
- Source commit: `516a92435eb0aa2608bc3e31860573c44b7722f2`
- Mode: diagnostic only; no acceptance coverage claimed
- Hardware runs completed: 9 of the authorized maximum 10
- Shutdown/recovery: passed after every completed run
- Campaign stop: run 09 proved that the unaligned scalar-write branch passed
  the unsupported XSDB option `-unaligned-accesses`; source changes were
  therefore required and the remaining run 10 authorization became invalid.

| Run | Address | Access | Result | Observation |
| --- | --- | --- | --- | --- |
| 01 | `0x00900000` | download | FAIL | `0x00900041 A5->00`, `0x009000CD C3->00`, `0x009000E9 C3->00` |
| 02 | `0x00900000` | block | FAIL | `0x009000E8 C3->00` |
| 03 | `0x00900000` | byte | FAIL | `0x009000E1 C3->00` |
| 04 | `0x00900000` | aligned halfword | FAIL | `0x009000C1 C3->00` |
| 05 | `0x00900000` | aligned word | FAIL | `0x00900020 C3->00` |
| 06 | `0x00900100` | download | PASS | Exact 256-byte readback; SHA256 equals the fixture SHA256 |
| 07 | `0x00900200` | download | FAIL | `0x00900214 C3->02`, `0x00900285 C3->00`, `0x009002B4 C3->02`, `0x009002E5 C3->00` |
| 08 | `0x00900300` | download | FAIL | `0x00900358 A5->00`, `0x009003C0 C3->00` |
| 09 | `0x00900001` | unaligned halfword | FIX REQUIRED | XSDB rejected plural option `-unaligned-accesses`; no readback was produced |
| 10 | not executed | unaligned word | INVALIDATED | Not consumed after the source-fix stop condition |

The aligned results show sparse, non-stationary corruption across address,
access-width, and download/block paths.  They do not support an offset-9-only
host packing or parser explanation.  The pass at `0x00900100` also prevents a
claim that every write to the approved scratch window fails.  Campaign A does
not yet establish the underlying DDR/external-master mechanism; Campaign B
must first retest the corrected unaligned branch and then continue the bounded
matrix.

All raw files, exact execution plans, preflight results, wrapper output,
readbacks when produced, shutdown-before/after evidence, and per-run SHA256
manifests are preserved under
`evidence/hardware/p7/ddr_external_master/<run_id>/`.

`HARDWARE_ACCEPTANCE: PENDING_HW`
