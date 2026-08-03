# P10.1R reboot-isolated lane1 failure

`P10_1R-REBOOT-ISOLATED-LANE1-FAILURE: FAIL`

Run `p10_1r_20260803T062223Z_cce2180b_c1370686_bfb1c51d` used the frozen `cce2180b` functional artifacts and reboot-isolated echo-tail plan. The first direction, F1 to R1, failed at sample 0:

- final fixed-side lane1 physical TX count: `1`;
- fixed-side lane1 raw and blanked-raw taps: `1`;
- rotating-side lane1 raw tap: `0`;
- rotating-side accepted-remote count: `0`;
- result: `RAW_PHYSICAL_ONLY` failure for this artifact/run.

F0 to R0, R1 to F1, and R0 to F0 were not executed. They are not classified as failed. After the F1 to R1 failure, the rotating mailbox still exposed the preceding command's terminal FAULT value (`state=5`, `status=14`) while the diagnostic reboot helper began polling. The helper misclassified that stale value as a new reboot failure and aborted the remaining matrix. This is a test-orchestration coverage defect; it does not invalidate the F1 to R1 snapshot captured before recovery.

The result is stronger than the preceding post-lane0 degradation because it occurred as the first direction after initial programming and safe boot. It conflicts with the earlier same-artifact 1000/1000 F1 to R1 run and therefore establishes intermittency, not a uniquely identified external component failure. A raw FPGA receiver tap cannot by itself distinguish optical alignment, TFDU hardware, connector wiring, or FPGA IO.

Both role-bound shutdown images were programmed after the failure. Fixed and rotating shutdown were PASS, `TFDU_SHUTDOWN_PROGRAMMED=1`, and `SHUTDOWN_EXIT=0`.

Raw evidence: `evidence/hardware/p10_1r/p10_1r_20260803T062223Z_cce2180b_c1370686_bfb1c51d/`

Machine-readable summary: `evidence/generated/p10_1r_reboot_isolated_lane1_failure.json`
