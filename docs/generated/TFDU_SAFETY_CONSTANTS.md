# Generated TFDU Safety Constants

> Generated from `config/tfdu_safety.yaml`; do not edit by hand.

```text
CONFIGURATION_ID: TFDU_SAFETY_P8C_V1
SOURCE_SHA256: e9069e49c1fd835ac7d1aee7e75b8e5b5cb13533fd703ddddf2ac3d8da61fb06
CANONICAL_CLOCK_HZ: 64000000
WINDOW_CYCLES: 64000
STARTUP_CYCLES: 32000
MAX_CONTINUOUS_CYCLES: 64
HARD_MAX_HIGH_CYCLES_STRICT_LT_20_PERCENT: 12799
TARGET_MAX_HIGH_CYCLES_LE_18_PERCENT: 11520
GLOBAL_PERMIT_ASSERT_FILTER_CYCLES: 4
NO_HARDWARE_ACTIONS_EXECUTED: true
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
HARDWARE_SCOPE_PROMOTED: false
```

| Profile | Physical modules | Banks | Modules per bank |
|---|---:|---:|---:|
| `Z7010_2LANE_DEV` | 2 | 2 | 1 |
| `Z7020_ROTATING_8LANE_MODEL` | 8 | 8 | 1 |
| `Z7020_FIXED_32MODULE_ACCOUNTING_MODEL` | 32 | 8 | 4 |

| Kill reason | Value |
|---|---:|
| `TX_KILL_NONE` | 0 |
| `TX_KILL_RESET_OR_FULL_SHUTDOWN` | 1 |
| `TX_KILL_GLOBAL_PERMIT_LOW` | 2 |
| `TX_KILL_NOT_ARMED` | 3 |
| `TX_KILL_FATAL_FAULT` | 4 |
| `TX_KILL_ILLEGAL_ONE_HOT` | 5 |
| `TX_KILL_INVALID_SELECTED_MODULE` | 6 |
| `TX_KILL_STALE_OR_INVALID_PATH_EPOCH` | 7 |
| `TX_KILL_STARTUP_NOT_COMPLETE` | 8 |
| `TX_KILL_DUTY_TARGET_THROTTLE` | 9 |
| `TX_KILL_DUTY_HARD_FAULT` | 10 |
| `TX_KILL_STUCK_HIGH_FAULT` | 11 |
| `TX_KILL_FRAME_NOT_ADMITTED` | 12 |
| `TX_KILL_SD_ACTIVE` | 13 |
| `TX_KILL_HISTORY_COOLDOWN` | 14 |
| `TX_KILL_PARTIAL_FRAME_ABORTED` | 15 |

| Hardware follow-up | Status |
|---|---|
| `global_permit_board_pulldown_contract` | `DEFINED` |
| `z7010_global_permit_pin_freeze` | `PENDING_P9_PIN_FREEZE` |
| `global_permit_physical_fail_low` | `PENDING_D17` |
| `global_permit_external_buffer_kill_latency` | `PENDING_D17` |
| `global_permit_partial_power` | `PENDING_D17` |
| `tfdu_duty_external_measurement` | `PENDING_P9_OR_LATER` |
