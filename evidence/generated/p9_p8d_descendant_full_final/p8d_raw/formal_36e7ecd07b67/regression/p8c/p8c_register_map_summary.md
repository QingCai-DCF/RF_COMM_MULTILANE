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
    "static_architecture",
    "parent_offline_provenance"
  ],
  "generated_at_utc": "2026-07-26T14:48:33+00:00",
  "map_sha256": "2e422c25a68b3d013a96e9c9df7aaf4664ddd3e9e5d551aff40516004468387e",
  "profile": "P8C_MULTI_PROFILE_OFFLINE",
  "simulation": {
    "log_directory": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/regression/p8c/p8c_raw/xsim/tb_p8c_safety_regs",
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
    "log": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/regression/p8c/p8c_raw/software/ps_driver_host_compile_and_run.log",
    "status": "PASS"
  },
  "source_commit": "36e7ecd07b67b385d433f69ec754af6db473a3a6",
  "status": "FAIL",
  "test_id": "P8C-REGISTER-MAP"
}
```
