# P8C physical module accounting

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
  "generated_at_utc": "2026-07-28T11:47:46+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_a2bd5c12/p8d_raw/formal_a2bd5c120564/regression/p8c/p8c_raw/xsim/tb_p8c_profile_matrix",
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
  "source_commit": "a2bd5c120564be38c9641c6281870e1676073030",
  "status": "PASS",
  "test_id": "P8C-PHYSICAL-MODULE-ACCOUNTING"
}
```
