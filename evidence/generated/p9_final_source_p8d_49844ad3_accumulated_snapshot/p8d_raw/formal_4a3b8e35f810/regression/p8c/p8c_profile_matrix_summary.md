# P8C profile matrix

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
  "generated_at_utc": "2026-07-26T22:15:42+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "profiles": {
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
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_4a3b8e35f810/regression/p8c/p8c_raw/xsim/tb_p8c_profile_matrix",
    "markers": [
      "P8C_ILLEGAL_COMMIT_DURING_FRAME_PASS=1",
      "P8C_PERMIT_DROP_DURING_PATH_COMMIT_PASS=1",
      "P8C_INDEPENDENT_FAULT_ISOLATION_PASS=1",
      "TB_P8C_PROFILE_MATRIX_PASS=1"
    ],
    "phase_returncodes": {
      "compile": 0,
      "elaborate": 0,
      "run": 0
    },
    "sources": [
      "rtl/generated/tfdu_safety_pkg.sv",
      "rtl/ir_path_mapping_pkg.sv",
      "rtl/ir_path_mapping_engine.sv",
      "rtl/ir_path_epoch_commit.sv",
      "rtl/ir_tfdu_exact_duty_accountant.sv",
      "rtl/ir_tfdu_physical_module_safety.sv",
      "rtl/ir_tfdu_safety_endpoint.sv",
      "rtl/ir_p8c_mapping_safety_adapter.sv",
      "rtl/ir_p8c_safety_integration.sv",
      "sim/tb/tb_p8c_profile_matrix.sv"
    ],
    "status": "PASS"
  },
  "source_commit": "4a3b8e35f81046334f97475258efa13ed37b231f",
  "status": "PASS",
  "test_id": "P8C-PROFILE-MATRIX"
}
```
