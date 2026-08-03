# P10.1R lane1 failure after the lane0 sequence

```text
RUN_ID=p10_1r_20260803T061448Z_cce2180b_c1370686_bfb1c51d
RESULT=FAIL
CLASSIFICATION=DIRECT_LANE1_F_TO_R_RAW_DEGRADATION_AFTER_LANE0_SEQUENCE
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
CURRENT_RUN_HARDWARE_AUTHORIZATION=false
```

The independent replicate completed all six lane0 cases: 64 raw pulses, 1024
raw pulses, and a 1 MiB frame transfer in each direction. The next case drove
64 physical pulses from F1. The fixed endpoint recorded 64 physical TX events
and 64 same-module raw observations, while R1 recorded only two remote raw
observations and returned `P9_RUNTIME_RAW_TIMEOUT`.

This is stronger than a frame-level retry symptom: at that point the intended
F1-to-R1 physical raw path delivered only 2/64 events. It does not yet prove
whether the path itself became unavailable or whether an endpoint/TFDU state
carried over from the preceding lane0 cases. The immediately preceding
standalone echo run, which reboots the pair between directions, had observed
F1-to-R1 at 1000/1000. A fresh per-direction rebooted probe is therefore the
next discriminating diagnostic.

No movement, alignment change, rewiring, Ethernet, or SPI was used. Completed
cases contained zero same-module accepted DATA, zero cross-lane accepted DATA,
and zero admission violations. The run failed closed and both boards reached
verified shutdown. The 60 manifest entries rehashed without size or digest
mismatch.
