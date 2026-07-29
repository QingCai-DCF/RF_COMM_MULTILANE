# P8C continuous-high guard

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
    "NO_HARDWARE/current authorization precondition",
    "parent_offline_provenance"
  ],
  "generated_at_utc": "2026-07-26T16:59:37+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_4a7c0b22aada/regression/p8c/p8c_raw/xsim/tb_p8c_physical_safety",
    "markers": [
      "P8C_CONTINUOUS_VECTOR_MATRIX_PASS=1",
      "P8C_SD_HISTORY_PRESERVED_PASS=1",
      "TB_P8C_PHYSICAL_SAFETY_PASS=1"
    ],
    "phase_returncodes": {
      "compile": 0,
      "elaborate": 0,
      "run": 0
    },
    "sources": [
      "rtl/ir_tfdu_exact_duty_accountant.sv",
      "rtl/ir_tfdu_physical_module_safety.sv",
      "sim/tb/tb_p8c_physical_safety.sv"
    ],
    "status": "PASS"
  },
  "source_commit": "4a7c0b22aadad2984e2ab90ef2363bf00c20cff6",
  "status": "FAIL",
  "test_id": "P8C-RTL-CONTINUOUS-HIGH"
}
```
