# P10.1 single/two-lane baseline

- Status: `FAIL`
- Test ID: `P10_1-HW-BASELINE`
- Hardware actions executed: `true`
- Current-run hardware authorization: `false`

## Errors

- XSDB PASS marker missing
- exactly one final endpoint shutdown row is required
- baseline_two_lane_f_to_r_60s: bounded-window PASS marker missing
- baseline_two_lane_f_to_r_60s: window case count mismatch
- baseline_two_lane_f_to_r_60s: window elapsed time is not bounded
- baseline_two_lane_r_to_f_60s: bounded-window PASS marker missing
- baseline_two_lane_r_to_f_60s: window case count mismatch
- baseline_two_lane_r_to_f_60s: window elapsed time is not bounded
- baseline_two_lane_r_to_f_60s: host fast-path exclusion failed
- baseline_two_lane_r_to_f_60s: aggregate PS/PL timer error exceeds 1%
- baseline f_to_r two-lane scaling 0.125000 < 1.6
- baseline r_to_f two-lane scaling 0.000000 < 1.6

## Machine-readable evidence

`evidence/generated/p10_1_hw_baseline_summary.json`
