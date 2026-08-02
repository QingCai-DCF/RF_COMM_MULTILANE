# Lane 1 connectivity probe — 2026-08-02

```text
LANE1_CONNECTIVITY_RESULT=FAIL
EVIDENCE_LEVEL=RAW_AB_BA
REQUESTED_PHYSICAL_LANE=1
LOGICAL_PROBE_LANE=1
F_TO_R_L1_RAW=FAIL_NO_REMOTE_RAW_ACTIVITY
R_TO_F_L1_RAW=PASS_1000_OF_1000
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
```

This role-bound P10.1R diagnostic used the frozen AX7020 2-lane artifacts and the canonical `F1-R1` J10 position-B mapping. It did not remap a lane0 artifact, use data loopback, or use external electrical/optical instrumentation.

The reverse-first run passed `R1 -> F1` for 1000/1000 raw samples and then failed `F1 -> R1` at sample 0: fixed status `0x0`/state `4` (complete), rotating status `0xE`/state `5` (`P9_RUNTIME_RAW_TIMEOUT`/fault), with zero PHY status and error-detail registers. A separate fresh-boot lane1-first run reproduced the same `F1 -> R1` failure before any lane0 traffic.

The frozen bundle had passed all four directions earlier in the campaign, then showed rotating lane1 degradation during F-to-R performance before the persistent directional timeout. The present result therefore applies to the current artifact/setup state and does not identify a defective component.

Transmit waveform boundary: the tested raw action exercises the project TFDU active-high Txd pulse path and the remote active-low Rxd input path on lane1. Raw activity is not a protocol DATA PASS. This report makes only the direction-level raw-connectivity claim above.

Authoritative audit and evidence index: [p10_1r_lane1_directional_blocker.md](../evidence/generated/p10_1r_lane1_directional_blocker.md).
