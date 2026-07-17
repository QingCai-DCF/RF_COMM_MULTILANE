# P8B phase, acquisition and handover model

## Phase contract

The independent input contract includes phase validity, absolute phase-derived `m0`, sample age, estimator uncertainty, bounded absolute speed, direction validity, absolute-reference validity represented by the phase-valid state, encoder fault, mapping readback match and path-epoch match. It uses generated trajectories and no real ABZ, motor or hardware input.

No acceleration or constant-speed prediction is assumed. With only `|rpm| <= 600`, maximum unknown motion is conservatively 3.6 millidegrees per microsecond. The model reports, without merging:

```text
phase estimator uncertainty
phase-data-age motion
prepare-latency motion
commit-latency motion
total effective phase uncertainty
```

Invalid/stale phase, excess uncertainty, encoder fault/illegal jump, direction invalid while moving, mapping/readback mismatch, epoch mismatch, stale mapping or reversal forces `tx_admission_allowed=0` and `ACQUISITION`. Active mapping may remain visible for diagnostics/RX, but no stale shadow can commit. Recovery requires a fresh prepare/atomic commit indication. P8B's admission output is logic semantics only; P8C owns physical TX kill.

At an arbitrary stop, direction is `STOPPED`, speed is zero, and phase remains unchanged. A restart or direction reversal re-enters acquisition. Reversal near any slot/bank boundary follows the same rule and cannot reuse the former candidate epoch.

## Independent timing metrics

`ir_handover_metrics` timestamps six separate intervals:

- phase sample to mapping prepare;
- mapping prepare to ready;
- commit request to atomic accept;
- application service interruption to resume;
- commit accept to epoch visibility;
- acquisition start to acquisition complete.

The offline logic targets are 50 us phase update, 100 us prepare, 10 us commit and 100 us application service gap. At 600 rpm those consume 0.18, 0.36, 0.036 and 0.36 degrees respectively. Candidate startup lead 700 us consumes 2.52 degrees. Any remaining margin is nominal/provisional until mechanical and optical tolerances are frozen. P8B makes no `REAL_600RPM_HANDOVER` or electrical-settle claim.

