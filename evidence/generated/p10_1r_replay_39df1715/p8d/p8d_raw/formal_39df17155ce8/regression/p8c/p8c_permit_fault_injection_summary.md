# P8C permit fault injection

```text
STATUS: FAIL
NO_HARDWARE_ACTIONS_EXECUTED: true
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
HARDWARE_SCOPE_PROMOTED: false
```

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "HARDWARE_SCOPE_PROMOTED": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "failures": [
    "parent_offline_provenance"
  ],
  "generated_at_utc": "2026-08-03T09:06:34+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p10_1r_replay_39df1715/p8d/p8d_raw/formal_39df17155ce8/regression/p8c/p8c_raw/xsim/tb_p8c_endpoint_safety",
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
  "source_commit": "39df17155ce82e38366fbdac00c79584f0fe1afa",
  "status": "FAIL",
  "test_id": "P8C-PERMIT-FAULT-INJECTION"
}
```
