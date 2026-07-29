# P8B phase acquisition summary

- `test_id`: `P8B-HDL-PHASE-ACQUISITION`
- `status`: `PASS`
- `max_motion_model_mdeg_per_us`: `3.6`
- `no_acceleration_assumption`: `True`
- `randomized_hdl_samples`: `896`

```json
{
  "fail_closed_conditions": [
    "phase_invalid",
    "data_stale",
    "uncertainty_over_budget",
    "illegal_encoder_jump",
    "direction_invalid_while_moving",
    "mapping_readback_mismatch",
    "epoch_mismatch",
    "reversal",
    "mapping_not_fresh"
  ],
  "max_motion_model_mdeg_per_us": 3.6,
  "no_acceleration_assumption": true,
  "random_seeds": [
    1,
    7,
    17,
    31,
    127,
    1024,
    20260717
  ],
  "randomized_hdl_samples": 896,
  "status": "PASS",
  "test_id": "P8B-HDL-PHASE-ACQUISITION"
}
```
