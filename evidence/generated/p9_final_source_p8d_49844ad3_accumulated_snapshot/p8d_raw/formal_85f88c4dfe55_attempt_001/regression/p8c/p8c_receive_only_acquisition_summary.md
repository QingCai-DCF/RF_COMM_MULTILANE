# P8C receive-only acquisition

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
  "generated_at_utc": "2026-07-26T19:16:59+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_85f88c4dfe55_attempt_001/regression/p8c/p8c_raw/xsim/tb_p8c_endpoint_safety",
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
  "source_commit": "85f88c4dfe5599600c80dbe50b2dac6c312e73c0",
  "status": "PASS",
  "test_id": "P8C-RECEIVE-ONLY-ACQUISITION"
}
```
