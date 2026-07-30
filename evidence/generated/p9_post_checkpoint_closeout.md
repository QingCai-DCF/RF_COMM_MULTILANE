# P9 Post-checkpoint Closeout

This is post-checkpoint metadata on `main`. It does not modify or supersede the immutable P9 hardware evidence, authorization record, shutdown record, source commit, or annotated acceptance tag.

```text
P9_CLOSEOUT_STATE: PASS
P9_STATUS: PASS
P9_RUN_ID: p9_20260729T134551Z_6d88b7854219_ac75bfe61bfc
P9_SOURCE_COMMIT: 6d88b7854219c8b514ef36109a456ffbda4972d8
P9_EVIDENCE_CHECKPOINT_TAG: p9-z7010-2lane-pass
P9_EVIDENCE_CHECKPOINT_COMMIT: 818d335c229d7b92223c279159aab84a5207ef92
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
LAST_HARDWARE_AUTHORIZATION_CONSUMED: true
FINAL_SHUTDOWN: PASS
SHUTDOWN_EXIT: 0
TFDU_SHUTDOWN_PROGRAMMED: true
EXTERNAL_TFDU_DUTY_MEASUREMENT: PENDING_EXTERNAL_MEASUREMENT
GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION: PENDING_D17
AB_L1_LEGACY_STATUS: BAD_DIR
AB_L1_CURRENT_P9_STATIONARY_STATUS: PASS
Z7020_TARGET_ACCEPTANCE: PENDING_Z7020_HW
ROTATION_ACCEPTANCE: PENDING_FINAL_MECHANICAL
FINAL_PRODUCT_HARDWARE_ACCEPTANCE: PENDING_HW
P10_STARTED: false
NO_HARDWARE_ACTIONS_EXECUTED_BY_CLOSEOUT: true
```

The P9 authorization was valid for the completed, immutable P9 run only. It is now marked consumed in current machine state and cannot authorize a later run. The original authorization and shutdown evidence remain byte-identical at the P9 checkpoint.

The current lane-1 PASS is limited to the stationary Z7010 two-lane P9 scope. The historical `AB_L1 BAD_DIR` record remains retained and this result is not extrapolated to Z7020, sector-bank, rotating, or final-product hardware.
