# P10.5 Run 1 Failure Diagnosis

- Status: `DIAGNOSIS_IN_PROGRESS`
- Run: `p10_5_20260830T095106Z_e1f8c01a_4015142e_79607d01`
- Authorization: `1/10` consumed; `9` remain
- Result: `FAIL_CLOSED`
- Fixed shutdown: `PASS`
- Rotating shutdown: `PASS`

The first run passed 11 of the 12 ordered `1+1` combinations. The final case, `oneplusone_f3_r2`, ran `F3->R3` simultaneously with `R2->F2` and ended with P10.1 status `0x103` (`DMA_COMPLETION`) on both endpoints. The outer P9 mailboxes consequently reported status `12` (`PL_OBJECT`) and entered the fault state.

Direct frozen evidence shows that `R2->F2` reached one complete 262144-byte PL object. `F3->R3` made physical and byte progress but stalled before completing the first object. The fixed lane-3 TX counter was `238179` and rotating lane-3 raw RX was `238186`; rotating lane-2 TX and fixed lane-2 raw RX were both `1641633`. These counters rule out a simple permanent open circuit, but raw pulses alone do not prove valid-frame reception.

There was no safety fault. Maximum continuous high was 16 cycles, maximum rolling duty was 11504 cycles against the 11520-cycle design target, and hard-fault count remained zero. The measured stage runtime and required half-runtime cooldown both passed.

Adjacent controls matter: `f3_r0`, `f3_r1`, `f0_r2`, `f1_r2`, and `f2_r3` all passed. The failure is therefore currently bounded to the simultaneous `f3/r2` pair, its final position after eleven cases, or a transient condition. It is not yet evidence that F3/R3 or R2/F2 is permanently unusable.

The next controlled action is one repeat with the identical committed freeze and case order. Reproduction at the same case will justify a fresh-program order-isolation diagnostic before any RTL or firmware change.

Machine-readable details and source hashes are in [p10_5_20260830_run1_failure_diagnosis.json](p10_5_20260830_run1_failure_diagnosis.json).
