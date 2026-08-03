# Lane 1 post-power-cycle connectivity probe - 2026-08-03

```text
LANE1_CONNECTIVITY_RESULT=FAIL
EVIDENCE_LEVEL=RAW_PHYSICAL_ONLY
REQUESTED_PHYSICAL_LANE=1
LOGICAL_PROBE_LANE=1
F_TO_R_L1_RAW=FAIL_NO_REMOTE_RAW_ACTIVITY_POST_POWER_CYCLE
R_TO_F_L1_RAW=NOT_REEXECUTED_PRESERVED_1000_OF_1000
FIXED_FINAL_TXD_EVENT=OBSERVED
FIXED_F1_LOCAL_RAW_WHILE_TX=OBSERVED
ROTATING_R1_RAW=NOT_OBSERVED
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
```

After the user reported power-cycling/re-powering the setup, Codex created and committed a fresh run-bound authorization, then used the frozen role-bound AX7020 P10.1R artifacts and canonical lane1 mapping `F1-R1` at J10 position B. The safe stage programmed shutdown before the test and made `F1 -> R1` the first physical raw command.

The first sample failed exactly as before. Fixed completed the command and recorded one physical A1 TX event, one local F1 raw event while final Txd was high, and a final-Txd rise/fall at `34007980`/`34007985` (five protocol cycles). Rotating R1 recorded zero raw events and returned `P9_RUNTIME_RAW_TIMEOUT`. The user-reported power-cycle therefore did not restore `F1 -> R1`.

The stage failed closed at that first required direction, so `R1 -> F1` was not re-executed after the power-cycle. Its earlier 1000/1000 same-bundle result remains preserved evidence, not a fresh post-power-cycle verdict. Overall bidirectional lane1 connectivity is FAIL because one required direction directly failed.

This is `RAW_PHYSICAL_ONLY` evidence. It closes the host command, lane selection, raw generator, permit/duty/kill, and internal fixed final-Txd tap for the observed pulse; it does not prove external optical power or identify a particular failed TFDU, connector, FPGA pin, or receiver.

Primary evidence:

- [XSDB transcript](../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/echo_tail/xsdb.result.txt), SHA256 `ebfb1cb86e0242d9aeb86d93b44060985aca8305073719a87621da49855a08a5`;
- [fixed atomic snapshot](../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/echo_tail/dumps/echo_F1_failure_0000.fixed.p10_1r.psv), SHA256 `8ed9373af25269ba024ab53e4a563582354d33134c3fd308bb9f7a549bb4abdf`;
- [rotating atomic snapshot](../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/echo_tail/dumps/echo_F1_failure_0000.rotating.p10_1r.psv), SHA256 `a3b0c219c1aad1ce271c6fbac90c35fd5009be3218c750cbb7029d5ddac920e5`;
- [orchestrator result](../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/final/orchestrator_result.json), SHA256 `c9d84b226c29eb8f21e5289238613b5d773077414e076fa2c2439658a9b0ad80`;
- [evidence manifest](../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/final/run_evidence_sha256_manifest.json), SHA256 `5075dfdb1923e1af379355f337ff272ba04321984976c026fb9804fb717efdf3`.

Both boards were returned to verified shutdown: `SHUTDOWN_FIXED=PASS`, `SHUTDOWN_ROTATING=PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, `SHUTDOWN_EXIT=0`, both active TX masks `0`, both endpoints disarmed, and both SD requests active. The authorization is consumed and false. No Ethernet, SPI, movement, alignment, module exchange, or rewiring was performed.
