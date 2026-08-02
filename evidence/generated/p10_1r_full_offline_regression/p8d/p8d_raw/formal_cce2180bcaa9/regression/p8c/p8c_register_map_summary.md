# P8C register map

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
  "map_sha256": "cfc2f097218a618b461299e54765af29aa19d380c6f974101011ddc46c0301ea",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p10_1r_exact_source_p8d_cce2180b/p8d_raw/formal_cce2180bcaa9/regression/p8c/p8c_raw/xsim/tb_p8c_safety_regs",
    "markers": [
      "TB_P8C_SAFETY_REGS_PASS=1"
    ],
    "phase_returncodes": {
      "compile": 0,
      "elaborate": 0,
      "run": 0
    },
    "sources": [
      "rtl/ir_p8c_safety_regs.sv",
      "sim/tb/tb_p8c_safety_regs.sv"
    ],
    "status": "PASS"
  },
  "software": {
    "log": "evidence/generated/p10_1r_exact_source_p8d_cce2180b/p8d_raw/formal_cce2180bcaa9/regression/p8c/p8c_raw/software/ps_driver_host_compile_and_run.log",
    "status": "PASS"
  },
  "source_commit": "cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d",
  "status": "FAIL",
  "test_id": "P8C-REGISTER-MAP"
}
```
