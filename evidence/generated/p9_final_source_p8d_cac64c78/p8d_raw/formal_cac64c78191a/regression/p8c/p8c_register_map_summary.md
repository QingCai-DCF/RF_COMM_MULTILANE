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
  "generated_at_utc": "2026-07-28T18:22:37+00:00",
  "map_sha256": "9afd713909fdfc4da15fe342546f161f6d9fc6a6e79e55d2c9cbec9fcf35f13a",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_cac64c78/p8d_raw/formal_cac64c78191a/regression/p8c/p8c_raw/xsim/tb_p8c_safety_regs",
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
    "log": "evidence/generated/p9_final_source_p8d_cac64c78/p8d_raw/formal_cac64c78191a/regression/p8c/p8c_raw/software/ps_driver_host_compile_and_run.log",
    "status": "PASS"
  },
  "source_commit": "cac64c78191a0acd4b6b30fb58c57984651535fb",
  "status": "FAIL",
  "test_id": "P8C-REGISTER-MAP"
}
```
