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
  "generated_at_utc": "2026-07-28T19:42:20+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_19bdeced/p8d_raw/formal_19bdeced49b0/regression/p8c/p8c_raw/xsim/tb_p8c_endpoint_safety",
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
  "source_commit": "19bdeced49b01804611c2ce56a114b3fc164745c",
  "status": "FAIL",
  "test_id": "P8C-PERMIT-FAULT-INJECTION"
}
```
