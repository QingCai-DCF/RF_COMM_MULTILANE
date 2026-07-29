# P8B state consistency summary

- `test_id`: `P8B-STATE-NONPROMOTION`
- `status`: `PASS`
- `hardware_actions_executed`: `False`

```json
{
  "expected": {
    "current_program_stage": [
      "P8D_SELECTIVE_REPEAT_SACK_DMA_DATA_PLANE",
      "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING",
      "P9_Z7010_PLATFORM_LIMITED_HARDWARE_VALIDATION"
    ],
    "current_run_hardware_authorization": false,
    "current_z7010_platform_status": "PLATFORM_LIMITED_PASS",
    "final_product_status": "PENDING_HW",
    "no_hardware_default": true,
    "p7_status": "PASS",
    "product_final_acceptance": "PENDING",
    "rotation_status": "PENDING_FINAL_MECHANICAL",
    "z7020_target_status": "PENDING_Z7020_HW"
  },
  "hardware_actions_executed": false,
  "mismatches": {},
  "status": "PASS",
  "test_id": "P8B-STATE-NONPROMOTION"
}
```
