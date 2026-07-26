# P8C safety configuration

```text
STATUS: PASS
NO_HARDWARE_ACTIONS_EXECUTED: true
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
HARDWARE_SCOPE_PROMOTED: false
```

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "HARDWARE_SCOPE_PROMOTED": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "config": {
    "canonical_clock_hz": 64000000,
    "configuration_id": "TFDU_SAFETY_P8C_V1",
    "global_permit": {
      "active_level": "high",
      "assert_filter_cycles": 4,
      "count_per_endpoint": 1,
      "fpga_unconfigured_default": "low",
      "open_circuit_default": "low",
      "partial_power_default": "low",
      "power_up_default": "low",
      "reassert_auto_resume": false,
      "reset_default": "low",
      "rtl_deassert_kill": "asynchronous_or_combinational",
      "software_writable": false,
      "undriven_default": "low"
    },
    "hardware_followup": {
      "global_permit_board_pulldown_contract": "DEFINED",
      "global_permit_external_buffer_kill_latency": "PENDING_D17",
      "global_permit_partial_power": "PENDING_D17",
      "global_permit_physical_fail_low": "PENDING_D17",
      "tfdu_duty_external_measurement": "PENDING_P9_OR_LATER",
      "z7010_global_permit_pin_freeze": "PENDING_P9_PIN_FREEZE"
    },
    "kill_reasons": {
      "DUTY_HARD_FAULT": 10,
      "DUTY_TARGET_THROTTLE": 9,
      "FATAL_FAULT": 4,
      "FRAME_NOT_ADMITTED": 12,
      "GLOBAL_PERMIT_LOW": 2,
      "HISTORY_COOLDOWN": 14,
      "ILLEGAL_ONE_HOT": 5,
      "INVALID_SELECTED_MODULE": 6,
      "NONE": 0,
      "NOT_ARMED": 3,
      "PARTIAL_FRAME_ABORTED": 15,
      "RESET_OR_FULL_SHUTDOWN": 1,
      "SD_ACTIVE": 13,
      "STALE_OR_INVALID_PATH_EPOCH": 7,
      "STARTUP_NOT_COMPLETE": 8,
      "STUCK_HIGH_FAULT": 11
    },
    "long_term_duty_target_percent_max": 18,
    "long_term_duty_window_ms": 100,
    "max_continuous_txd_high_us": 1,
    "mode_strategy": "static_high_speed",
    "physical_profiles": {
      "Z7010_2LANE_DEV": {
        "bank_count": 2,
        "endpoint_role": "development",
        "modules_per_bank": 1,
        "physical_module_count": 2
      },
      "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL": {
        "bank_count": 8,
        "endpoint_role": "fixed",
        "modules_per_bank": 4,
        "physical_module_count": 32
      },
      "Z7020_ROTATING_8LANE_MODEL": {
        "bank_count": 8,
        "endpoint_role": "rotating",
        "modules_per_bank": 1,
        "physical_module_count": 8
      }
    },
    "receiver_startup_us": 500,
    "rolling_duty_design_percent_max": 18,
    "rolling_duty_hard_percent_strict_lt": 20,
    "rolling_duty_window_us": 1000,
    "schema_version": 1
  },
  "config_sha256": "e9069e49c1fd835ac7d1aee7e75b8e5b5cb13533fd703ddddf2ac3d8da61fb06",
  "derived": {
    "assert_filter_cycles": 4,
    "canonical_clock_hz": 64000000,
    "configuration_id": "TFDU_SAFETY_P8C_V1",
    "hard_max_high_cycles": 12799,
    "hardware_followup": {
      "global_permit_board_pulldown_contract": "DEFINED",
      "global_permit_external_buffer_kill_latency": "PENDING_D17",
      "global_permit_partial_power": "PENDING_D17",
      "global_permit_physical_fail_low": "PENDING_D17",
      "tfdu_duty_external_measurement": "PENDING_P9_OR_LATER",
      "z7010_global_permit_pin_freeze": "PENDING_P9_PIN_FREEZE"
    },
    "kill_reasons": {
      "DUTY_HARD_FAULT": 10,
      "DUTY_TARGET_THROTTLE": 9,
      "FATAL_FAULT": 4,
      "FRAME_NOT_ADMITTED": 12,
      "GLOBAL_PERMIT_LOW": 2,
      "HISTORY_COOLDOWN": 14,
      "ILLEGAL_ONE_HOT": 5,
      "INVALID_SELECTED_MODULE": 6,
      "NONE": 0,
      "NOT_ARMED": 3,
      "PARTIAL_FRAME_ABORTED": 15,
      "RESET_OR_FULL_SHUTDOWN": 1,
      "SD_ACTIVE": 13,
      "STALE_OR_INVALID_PATH_EPOCH": 7,
      "STARTUP_NOT_COMPLETE": 8,
      "STUCK_HIGH_FAULT": 11
    },
    "long_term_duty_target_percent_max": 18,
    "long_term_duty_window_ms": 100,
    "long_term_window_cycles": 6400000,
    "max_continuous_cycles": 64,
    "max_continuous_txd_high_us": 1,
    "no_hardware": true,
    "physical_profiles": {
      "Z7010_2LANE_DEV": {
        "bank_count": 2,
        "endpoint_role": "development",
        "modules_per_bank": 1,
        "physical_module_count": 2
      },
      "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL": {
        "bank_count": 8,
        "endpoint_role": "fixed",
        "modules_per_bank": 4,
        "physical_module_count": 32
      },
      "Z7020_ROTATING_8LANE_MODEL": {
        "bank_count": 8,
        "endpoint_role": "rotating",
        "modules_per_bank": 1,
        "physical_module_count": 8
      }
    },
    "receiver_startup_us": 500,
    "rolling_duty_design_percent_max": 18,
    "rolling_duty_hard_percent_strict_lt": 20,
    "rolling_duty_window_us": 1000,
    "schema_version": 1,
    "source_path": "config/tfdu_safety.yaml",
    "source_sha256": "e9069e49c1fd835ac7d1aee7e75b8e5b5cb13533fd703ddddf2ac3d8da61fb06",
    "startup_cycles": 32000,
    "target_max_high_cycles": 11520,
    "window_cycles": 64000
  },
  "failures": [],
  "generated_at_utc": "2026-07-26T09:44:00+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "source_commit": "56fbf42788dc90779f7580ad86855ea935a3542c",
  "status": "PASS",
  "test_id": "P8C-SAFETY-CONFIG"
}
```
