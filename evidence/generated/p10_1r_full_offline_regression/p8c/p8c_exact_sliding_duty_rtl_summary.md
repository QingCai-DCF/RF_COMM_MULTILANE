# P8C exact duty RTL

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
  "full_scale": {
    "log_directory": "evidence/generated/p10_1r_exact_source_p8c_8bb75904/p8c_raw/xsim/tb_p8c_full_scale",
    "markers": [
      "P8C_LONG_PERIODIC_4PPM_LIKE_PASS=1",
      "TB_P8C_FULL_SCALE_PASS=1"
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
      "sim/tb/tb_p8c_full_scale.sv"
    ],
    "status": "PASS"
  },
  "generated_at_utc": "2026-08-02T03:41:15+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "reduced": {
    "log_directory": "evidence/generated/p10_1r_exact_source_p8c_8bb75904/p8c_raw/xsim/tb_p8c_exact_duty",
    "markers": [
      "P8C_TELEMETRY_CLEAR_HISTORY_PRESERVED_PASS=1",
      "P8C_EXACT_VECTOR_MATRIX_PASS=1",
      "TB_P8C_EXACT_DUTY_PASS=1"
    ],
    "phase_returncodes": {
      "compile": 0,
      "elaborate": 0,
      "run": 0
    },
    "sources": [
      "rtl/ir_tfdu_exact_duty_accountant.sv",
      "sim/tb/tb_p8c_exact_duty.sv"
    ],
    "status": "PASS"
  },
  "source_commit": "8bb759047276e5bb9952403013d1d33cea6bba92",
  "status": "PASS",
  "test_id": "P8C-RTL-EXACT-DUTY",
  "trace_comparison": {
    "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
    "HARDWARE_SCOPE_PROMOTED": false,
    "NO_HARDWARE_ACTIONS_EXECUTED": true,
    "first_mismatch": null,
    "profile": "P8C_REDUCED_1MHZ_100CYCLE_WINDOW",
    "random_seed": null,
    "record_count": 250,
    "status": "PASS",
    "test_id": "P8C-RTL-PYTHON-CYCLE-TRACE"
  }
}
```
