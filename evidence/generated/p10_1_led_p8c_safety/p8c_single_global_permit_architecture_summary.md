# P8C single global permit architecture

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
  "failures": [],
  "generated_at_utc": "2026-07-31T09:15:45+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p10_1_led_p8c_safety/p8c_raw/xsim/tb_p8c_endpoint_safety",
    "markers": [
      "P8C_PERMIT_VECTOR_MATRIX_PASS=1",
      "P8C_FAULT_DROP_MID_HIGH_PASS=1",
      "P8C_HISTORY_PERMIT_LANE_PATH_PRESERVED_PASS=1",
      "P8C_KILL_REASON_PRIORITY_PASS=1",
      "TB_P8C_ENDPOINT_SAFETY_PASS=1"
    ],
    "phase_returncodes": {
      "compile": 0,
      "elaborate": 0,
      "run": 0
    },
    "sources": [
      "rtl/generated/tfdu_safety_pkg.sv",
      "rtl/ir_tfdu_exact_duty_accountant.sv",
      "rtl/ir_tfdu_physical_module_safety.sv",
      "rtl/ir_tfdu_safety_endpoint.sv",
      "sim/tb/tb_p8c_endpoint_safety.sv"
    ],
    "status": "PASS"
  },
  "source_commit": "a07f218434e2fb3000f1d7c086917169fb500163",
  "static": {
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
    "HARDWARE_SCOPE_PROMOTED": false,
    "NO_HARDWARE_ACTIONS_EXECUTED": true,
    "checks": {
      "active_source_manifest_complete": {
        "detail": null,
        "status": "PASS"
      },
      "active_z7010_xdc_unchanged": {
        "detail": null,
        "status": "PASS"
      },
      "ax7010_xdc_not_reused_for_z7020": {
        "detail": null,
        "status": "PASS"
      },
      "canonical_constants_consumed": {
        "detail": null,
        "status": "PASS"
      },
      "canonical_full_scale_vector_bound_to_config": {
        "detail": [
          ".CLOCK_HZ(64_000_000)",
          ".STARTUP_US(500)",
          ".WINDOW_US(1000)",
          ".MAX_CONTINUOUS_HIGH_US(1)"
        ],
        "status": "PASS"
      },
      "exact_math_guards_present": {
        "detail": null,
        "status": "PASS"
      },
      "fixed_bucket_excluded": {
        "detail": null,
        "status": "PASS"
      },
      "no_dual_heartbeat_or_bank_permit_identifier": {
        "detail": [],
        "status": "PASS"
      },
      "no_hardware_scan": {
        "detail": {
          "environment": "1",
          "stdout": "NO_HARDWARE_ACTIONS_EXECUTED=1"
        },
        "status": "PASS"
      },
      "p8b_checkpoint_evidence_immutable": {
        "detail": {
          "evidence/generated/p8b_checkpoint_acceptance_core.json": true,
          "evidence/generated/p8b_checkpoint_offline_gate_summary.json": true
        },
        "status": "PASS"
      },
      "p8b_sources_not_forked": {
        "detail": {
          "rtl/ir_bank_lane_crossbar.sv": {
            "actual": "97be64e23308e85768866c8bc5037d9f4f2bfb3670a9981915d3f5686519e886",
            "expected": "97be64e23308e85768866c8bc5037d9f4f2bfb3670a9981915d3f5686519e886",
            "match": true
          },
          "rtl/ir_path_epoch_commit.sv": {
            "actual": "1cd34f339393fdfce3f554d33501ba12a65b3daf85190ffa01bad2d95890db4c",
            "expected": "1cd34f339393fdfce3f554d33501ba12a65b3daf85190ffa01bad2d95890db4c",
            "match": true
          },
          "rtl/ir_path_mapping_engine.sv": {
            "actual": "248691b1186dfcd4524e8a988aa2424e4b2853852fea2fb645c0ac4c66613d2c",
            "expected": "248691b1186dfcd4524e8a988aa2424e4b2853852fea2fb645c0ac4c66613d2c",
            "match": true
          },
          "rtl/ir_path_mapping_pkg.sv": {
            "actual": "6be70a692a1b39ecae347c52b9440fd6f7b1e41434362423aeb53519dabd505b",
            "expected": "6be70a692a1b39ecae347c52b9440fd6f7b1e41434362423aeb53519dabd505b",
            "match": true
          }
        },
        "status": "PASS"
      },
      "permit_status_fields_read_only": {
        "detail": {
          "ENDPOINT_ARMED": "RO",
          "ENDPOINT_FATAL_FAULT": "RO",
          "GLOBAL_PERMIT_EFFECTIVE": "RO",
          "GLOBAL_PERMIT_RAW": "RO",
          "GLOBAL_PERMIT_SYNC": "RO",
          "PARTIAL_FRAME_ABORT_BLOCK": "RO",
          "SNAPSHOT_VALID": "RO",
          "TX_KILL_ACTIVE": "RO"
        },
        "status": "PASS"
      },
      "physical_module_accounting_instantiated": {
        "detail": null,
        "status": "PASS"
      },
      "production_safety_bypass_absent": {
        "detail": [],
        "status": "PASS"
      },
      "project_constraints_unchanged": {
        "detail": null,
        "status": "PASS"
      },
      "raw_permit_is_final_txd_kill": {
        "detail": null,
        "status": "PASS"
      },
      "receive_only_path_independent_of_permit": {
        "detail": null,
        "status": "PASS"
      },
      "register_contract_complete": {
        "detail": {
          "missing_controls": [],
          "missing_registers": [],
          "missing_snapshot_flags": []
        },
        "status": "PASS"
      },
      "sd_control_separate_from_permit": {
        "detail": null,
        "status": "PASS"
      },
      "single_global_permit_endpoint_port": {
        "detail": null,
        "status": "PASS"
      },
      "single_global_permit_integration_port": {
        "detail": null,
        "status": "PASS"
      },
      "software_permit_override_absent": {
        "detail": null,
        "status": "PASS"
      },
      "test_fault_injection_absent_from_production": {
        "detail": null,
        "status": "PASS"
      },
      "z7010_permit_pin_not_silently_assigned": {
        "detail": {
          "board_pulldown_contract": "DEFINED",
          "pin_freeze": "PENDING_P9_PIN_FREEZE"
        },
        "status": "PASS"
      }
    },
    "failures": [],
    "status": "PASS"
  },
  "status": "PASS",
  "test_id": "P8C-SINGLE-GLOBAL-PERMIT"
}
```
