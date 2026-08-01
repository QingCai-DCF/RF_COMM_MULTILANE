# P10.1 PS/PL timer crosscheck

- Status: `FAIL`
- Test ID: `P10_1-HW-TIMER-CROSSCHECK`
- Hardware actions executed: `true`
- Current-run hardware authorization: `false`

## Errors

- pattern_prbs_1m: timer disagreement exceeds 1%
- pattern_zero_1m: timer disagreement exceeds 1%
- pattern_one_1m: timer disagreement exceeds 1%
- pattern_counter_1m: timer disagreement exceeds 1%
- pattern_corpus_1m: timer disagreement exceeds 1%
- preflight: complete timer coverage unavailable because stage is not PASS
- smoke: complete timer coverage unavailable because stage is not PASS
- baseline: complete timer coverage unavailable because stage is not PASS
- tuning: complete timer coverage unavailable because stage is not PASS
- pipeline: complete timer coverage unavailable because stage is not PASS
- streaming: complete timer coverage unavailable because stage is not PASS
- faults: complete timer coverage unavailable because stage is not PASS
- crosstalk: complete timer coverage unavailable because stage is not PASS
- half_duplex: complete timer coverage unavailable because stage is not PASS
- oneplusone: complete timer coverage unavailable because stage is not PASS
- formal: complete timer coverage unavailable because stage is not PASS
- preflight_identity: local PS/PL timer gate failed
- diagnostic_only_1byte: local PS/PL timer gate failed
- short_ring_wrap: local PS/PL timer gate failed
- idle_heavy_5s: local PS/PL timer gate failed

## Machine-readable evidence

`evidence/generated/p10_1_hw_timer_summary.json`
