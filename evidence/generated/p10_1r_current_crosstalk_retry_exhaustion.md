# P10.1R current-artifact crosstalk retry exhaustion

```text
RUN_ID=p10_1r_20260803T060521Z_cce2180b_c1370686_bfb1c51d
RESULT=FAIL
CLASSIFICATION=DIRECT_CURRENT_ARTIFACT_DATA_PATH_FAILURE_RETRY_EXHAUSTED
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
CURRENT_RUN_HARDWARE_AUTHORIZATION=false
```

The fresh current-artifact run passed lane0 raw and 1 MiB frame traffic in both
directions. The failing physical path was the defined `F1 -> R1` lane1
direction. Its 64- and 1024-pulse raw probes passed,
then the 1 MiB frame case stopped after exactly 524288 accepted bytes and two of
four 256 KiB objects. The fixed endpoint reported runtime status `0x104` and PL
object error `0x50090004`, which the frozen RTL assigns to retry exhaustion. The
rotating-role endpoint reported runtime status `0x103` (DMA completion failure).
No application bytes were committed.

This evidence proves a current DATA-path failure but does not by itself identify
whether the missing progress was caused by optical DATA loss, reverse ACK loss,
or a protocol/object-boundary race. The failure path resets the PL/DMA before
publishing the terminal P10.1 physical/performance counters, so the zeroed
terminal counters cannot be used to choose among those causes.

The completed observations contained zero same-module accepted DATA, zero
cross-lane accepted DATA, and zero admission violations. The stage failed closed,
both role-bound shutdown images were programmed successfully, and the run-bound
authorization was consumed.

Raw evidence is preserved under
`evidence/hardware/p10_1r/p10_1r_20260803T060521Z_cce2180b_c1370686_bfb1c51d/`.
The 70 manifest-declared files rehashed with zero size or digest mismatches.
