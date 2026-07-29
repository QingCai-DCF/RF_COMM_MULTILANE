# P8C continuous-high guard

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
  "generated_at_utc": "2026-07-27T09:03:31+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d/p8d_raw/formal_aa07bac1690f/regression/p8c/p8c_raw/xsim/tb_p8c_physical_safety",
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
  "source_commit": "aa07bac1690f4d7db77532ec79a043781518fcab",
  "status": "PASS",
  "test_id": "P8C-RTL-CONTINUOUS-HIGH"
}
```
