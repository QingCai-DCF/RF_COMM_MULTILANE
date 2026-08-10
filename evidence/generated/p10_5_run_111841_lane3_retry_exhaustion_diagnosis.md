# P10.5 run 111841 lane-3 retry-exhaustion diagnosis

`P10_5-RUN-111841-LANE3-RETRY-EXHAUSTION-DIAGNOSIS = FAIL_WITH_DIRECT_RAW_PHYSICAL_EVIDENCE`

Run `p10_5_20260810T111841Z_e1f8c01a_4015142e_79607d01` failed closed in `oneplustwo_f1_rA` with both endpoints reporting `0x50090004` retry exhaustion. The frozen snapshots show no safety fault, CRC/SHA error, descriptor leak, continuous-high violation, or duty violation.

The direction-level evidence is asymmetric:

- `F3 -> R3`: `PASS_RAW_PHYSICAL_ONLY`. In the immediately preceding `twoplusone_fA_r1` case, fixed F3 produced 12,847,821 physical TX counts and rotating R3 recorded 12,847,821 raw RX counts.
- `R3 -> F3`: `FAIL_NO_RX_ACTIVITY`. In the failed case, rotating R3 produced 427,200 physical TX counts while fixed F3 recorded zero raw RX counts.
- `R1 -> F1`: partial activity was present: 496,597 rotating R1 physical TX counts versus 429,044 fixed F1 raw RX counts.

The result is tied to the frozen P10.5 fixed/rotating bitstreams (`4015142e...` and `79607d01...`) and this run only. FPGA raw counters are direct digital evidence for the pins seen by the design, but they are not an external electrical or optical measurement and cannot by themselves distinguish alignment, module, wiring, or receiver-electrical causes.

Both boards were independently programmed with the shutdown bitstreams after failure. `SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, and `SHUTDOWN_EXIT=0`.

The next bounded action is a new immutable full-run authorization. The complete runner's early 1+1 matrix provides a fresh lane-matching recheck without changing XDC, wiring, or artifacts. The campaign may proceed only if that matrix passes.

