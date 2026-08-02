# P8C receive-only acquisition

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
  "generated_at_utc": "2026-08-02T17:29:50+00:00",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p10_1r_exact_source_p8d_cce2180b/p8d_raw/formal_cce2180bcaa9/regression/p8c/p8c_raw/xsim/tb_p8c_endpoint_safety",
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
  "source_commit": "cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d",
  "status": "FAIL",
  "test_id": "P8C-RECEIVE-ONLY-ACQUISITION"
}
```
