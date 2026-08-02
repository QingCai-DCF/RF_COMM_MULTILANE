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
  "generated_at_utc": "2026-08-02T03:41:15+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p10_1r_exact_source_p8c_8bb75904/p8c_raw/xsim/tb_p8c_profile_matrix",
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
  "source_commit": "8bb759047276e5bb9952403013d1d33cea6bba92",
  "status": "PASS",
  "test_id": "P8C-PHYSICAL-MODULE-ACCOUNTING"
}
```
