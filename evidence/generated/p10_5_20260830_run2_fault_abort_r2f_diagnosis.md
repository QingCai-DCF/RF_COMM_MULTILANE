# P10.5 Run 2 R→F Direction-abort Diagnosis

- Status: `REPRODUCED_HARDWARE_BOUNDARY_REMEDIATION_REQUIRED`
- Run: `p10_5_20260830T101446Z_e1f8c01a_4015142e_79607d01`
- Authorization: `2/10` consumed; `8` remain
- Result: `FAIL_CLOSED`
- Fixed shutdown: `PASS`
- Rotating shutdown: `PASS`
- Required cooldown: `PASS`

Run 2 passed all 12 `1+1` cases, the complete `2+1`/`1+2` matrix, all six complementary `2+2` partitions, role-commit readback, 300-second performance, and five simultaneous bidirectional 64 MiB transfers. It then failed closed in the mandatory `fault_abort_r2f` case; formal was not run after that failure.

The failure is a protocol boundary, not a missing raw physical path. At freeze, fixed had allocated 52 fragments, advanced only to ACK base 21, retained 31 outstanding entries, and recorded exactly 224 retries—seven retries for each of the 32-window entries—before `0x50090004` retry exhaustion. Rotating had correctly aborted its R→F TX context while its F→R RX context received all 12844 bytes and scheduled 115 control-only ACKs. Nevertheless, the fixed F→R window did not retire.

Physical pulse counts match exactly across every paired direction used in the case: fixed lane0/1 TX `154008/154001` equals rotating lane0/1 raw RX, and rotating lane2/3 TX `24669/13007` equals fixed lane2/3 raw RX. Maximum continuous high was 16 cycles, maximum rolling duty was 11504 cycles against the 11520-cycle design target, and no hard safety fault occurred. Raw equality does not prove that the ACK frames were CRC-valid or admitted.

The post-terminal P10.1R/P10.2 counters are zero because the fail-closed terminal path cleared them. The first-fault recorder preserves the decisive TX/raw/safety/window state, but its current schema does not include per-lane ACK-good, CRC-bad, direction-reject, or role-epoch-reject counters. Those missing counters therefore cannot be inferred.

The earlier dirty-bit repair did restore control-only ACK scheduling; this run disproves the narrower claim that no fallback ACK is emitted. The current XSIM test aborts as soon as 52 fragments are allocated and does not require the hardware-observed partial boundary `next=52, ack_base=20`. The next implementation step is a failing regression at that exact state, followed by the smallest demonstrated RTL/protocol repair and a wholly new immutable artifact freeze. No unchanged-bundle hardware retry is justified.

Machine-readable facts and hashes are in [p10_5_20260830_run2_fault_abort_r2f_diagnosis.json](p10_5_20260830_run2_fault_abort_r2f_diagnosis.json).
