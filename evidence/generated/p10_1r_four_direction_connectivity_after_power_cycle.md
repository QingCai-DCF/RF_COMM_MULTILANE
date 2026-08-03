# P10.1R four-direction connectivity after power cycle

`P10_1R-FOUR-DIRECTION-CONNECTIVITY-AFTER-POWER-CYCLE: FAIL`

The complete reboot-isolated matrix produced three clean 1000/1000 raw-direction results and one direct failure:

| Direction | Result | Direct receiver evidence |
|---|---|---|
| F0 to R0 | PASS | rotating lane0 raw `1000/1000` |
| R0 to F0 | PASS | fixed lane0 raw `1000/1000` |
| F1 to R1 | FAIL | fixed final lane1 TX `1`, rotating lane1 raw `0` at sample 0 |
| R1 to F1 | PASS | fixed lane1 raw `1000/1000` |

The direction-isolation recovery completed after every direction. The F1 to R1 negative observation is therefore not a placeholder for an unexecuted case, and the other three PASS results are not inherited from historical evidence.

The raw receiver tap cannot distinguish an optical-path problem, the fixed F1 transmitter half, the rotating R1 receiver half, or their external electrical path. It does prove that the rotating FPGA receiver tap did not see a pulse for the observed final fixed-side lane1 TX event in this run.

Both role-bound shutdown images were programmed. Fixed and rotating shutdown were PASS, `TFDU_SHUTDOWN_PROGRAMMED=1`, and `SHUTDOWN_EXIT=0`.

Raw evidence: `evidence/hardware/p10_1r/p10_1r_20260803T062846Z_cce2180b_c1370686_bfb1c51d/`

Machine-readable summary: `evidence/generated/p10_1r_four_direction_connectivity_after_power_cycle.json`
