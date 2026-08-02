# Lane 1 connectivity localization probe - 2026-08-03

```text
LANE1_CONNECTIVITY_RESULT=FAIL
EVIDENCE_LEVEL=RAW_PHYSICAL_ONLY
REQUESTED_PHYSICAL_LANE=1
LOGICAL_PROBE_LANE=1
F_TO_R_L1_RAW=FAIL_NO_REMOTE_RAW_ACTIVITY
R_TO_F_L1_RAW=PASS_1000_OF_1000_PRESERVED
FIXED_FINAL_TXD_EVENT=OBSERVED
FIXED_F1_LOCAL_RAW_WHILE_TX=OBSERVED
ROTATING_R1_RAW=NOT_OBSERVED
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
```

This role-bound diagnostic used the frozen AX7020 P10.1R artifacts and the canonical lane1 mapping `F1-R1`, J10 position B on both boards. It did not remap a lane0 artifact, use DATA loopback, move or rewire hardware, or use external electrical/optical instrumentation.

Run `p10_1r_20260802T191315Z_cce2180b_c1370686_bfb1c51d` tested `F1 -> R1` first after a fresh boot. The fixed command completed and its coherent PL snapshot recorded:

- one completed raw pulse;
- fixed A1 physical-TX count `1`;
- final-Txd rise `40073142` and fall `40073147` (five protocol cycles);
- one fixed F1 raw event while final Txd was high;
- zero accepted remote frames.

The rotating coherent snapshot recorded zero R1 raw events and zero accepted remote frames, and firmware returned `P9_RUNTIME_RAW_TIMEOUT`. This closes the host-command, raw-generator, lane-select, permit/duty/kill, and internal final-Txd path for the observed pulse. It does not prove external optical power and does not identify a failed TFDU, connector, FPGA pin, or receiver.

The strongest supported remaining boundary begins after the fixed internal final-Txd tap and includes fixed F1 package-pin/J10 electrical delivery and module emission, the stationary F1-to-R1 optical path, and rotating R1 module/J10/input detection. The previously preserved reverse-direction run passed `R1 -> F1` for 1000/1000 samples, so this is directional rather than complete lane1 loss.

Primary evidence:

- `evidence/hardware/p10_1r/p10_1r_20260802T191315Z_cce2180b_c1370686_bfb1c51d/echo_tail/xsdb.result.txt`, SHA256 `b2c738e0152fea154abc7ee5afe9fa84b9570eaa0e41fea5cbb9762a623bd82b`;
- fixed atomic snapshot, SHA256 `8c75777e24f2c67dde4cf2e64201b3fc96df76207fb9abad700a200f0a265b14`;
- rotating atomic snapshot, SHA256 `a3b0c219c1aad1ce271c6fbac90c35fd5009be3218c750cbb7029d5ddac920e5`;
- final orchestrator result, SHA256 `639bcc130752bbbc2f3bd4663e074d30cf85be0958fd848f39d14ccf8dddab87`.

Both boards were returned to verified shutdown (`SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, `SHUTDOWN_EXIT=0`). Current-run authorization was consumed and is false. The authoritative machine-readable blocker is `evidence/generated/p10_1r_lane1_directional_blocker.json`.
