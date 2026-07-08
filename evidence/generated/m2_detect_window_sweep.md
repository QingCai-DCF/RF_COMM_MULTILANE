# M2 Detect Window Sweep

M2_DETECT_WINDOW_SWEEP_REPORT=1
M2_DETECT_WINDOW_SWEEP_POSITIVE_CASES_PASS=1
M2_DETECT_WINDOW_SWEEP_NEGATIVE_CASES_DETECTED=1
M2_DETECT_WINDOW_SWEEP=PASS

| Case | CNT_CHIP_MAX | Window | Required offsets | Missed required | Expected | Verdict |
|---|---:|---|---|---|---|---|
| G1_A_DETECT_0_5 | 7 | 0..5 | 0,1,2,3,4,5 | none | pass | PASS |
| G1_B_DETECT_0_7 | 7 | 0..7 | 0,1,2,3,4,5,6,7 | none | pass | PASS |
| TFDU_MODEL_DETECT_14_30 | 31 | 14..30 | 14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30 | none | pass | PASS |
| NEGATIVE_NARROW_WINDOW_3_4 | 7 | 3..4 | 0,1,2,3,4,5 | 0,1,2,5 | miss | PASS |

This is an offline reference sweep for the abstract pulse-stream decoder. It does not claim hardware timing acceptance or replace SystemVerilog simulation.
