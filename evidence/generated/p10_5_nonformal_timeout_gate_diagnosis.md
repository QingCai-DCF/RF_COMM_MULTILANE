# P10.5 Non-Formal Timeout Gate Diagnosis

## Outcome

The run `p10_5_20260810T064401Z_eefca40c_78726594_498ca074` remains an immutable `FAIL` with both endpoints verifiably shut down. The failure was caused by a host acceptance-policy mismatch, not by an integrity failure, retry exhaustion, missing TX/RX, or failed application commit.

## Direct evidence

- Final summary: `evidence/hardware/p10_5/p10_5_20260810T064401Z_eefca40c_78726594_498ca074/final/p10_5_final_summary.json`
- Summary SHA256: `63ca37a9dba28fed272f116e1e98079ef4204f003bac20a6a935cb8995c9ca1a`
- `one_plus_one` executed all 12 ordered pairs.
- Every pair recorded positive physical TX/RX and positive application commit in both roles.
- CRC, SHA mismatch, integrity, retry-exhaustion, commit, and descriptor hard-error counters were zero.
- Three fixed-role cases each recorded one timeout followed by one successful retry: `oneplusone_f0_r1`, `oneplusone_f1_r0`, and `oneplusone_f3_r2`.
- Each affected result still recorded `tx_bytes=262144`, `rx_bytes=262144`, and `application_committed=2621440`.
- Final shutdown: fixed `PASS`, rotating `PASS`.

## Goal reconciliation

Goal Section 33 does not require a zero transport-timeout diagnostic count for the 1+1 matrix. It requires executed TX, positive commits in both directions, zero CRC/SHA errors, zero same-module/cross-lane acceptance, and zero deadlock. Goal Section 40 explicitly requires `transport timeout=0` for the 30-minute formal run.

The runner therefore keeps non-formal timeout/retry counts in evidence but does not treat a recovered non-formal timeout as a hard failure. Retry exhaustion, integrity, commit, terminal-service, safety, and shutdown checks remain hard gates. A nonzero timeout count remains a hard failure in `formal_30min`, and the final summary independently requires the formal timeout count to be zero.

An offline re-evaluation of the immutable 12-case `one_plus_one` stage evidence with the corrected policy returned `PASS` with no evaluation errors while preserving `maximum tx_timeouts=1` as a diagnostic value. This replay validates the host gate change only; it is not a new hardware result.

## Change boundary

Only the host runner and its unit test changed. RTL, firmware, bitstreams, XSA, BSP, and ELF files did not change. The old failed run and its consumed authorization were not modified, and no hardware PASS is inherited. A clean new artifact/harness freeze and a new current-run authorization are required before retrying hardware.
