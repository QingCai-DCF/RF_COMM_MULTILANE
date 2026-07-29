# P8D multi-profile matrix

- Status: `PASS`
- Test ID: `P8D-MULTI-PROFILE-MATRIX`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `8ecf71c2a795b887daac7c8f91300b1eb8a2921f`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "cdc_ratio_simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_p8d_cdc_ratios",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_p8d_async_descriptor_bridge.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8d_cdc_ratios.sv",
        "finished_utc": "2026-07-29T11:19:49.922912Z",
        "log": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_p8d_cdc_ratios/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-29T11:19:49.189516Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_cdc_ratios -debug typical -s tb_ir_p8d_cdc_ratios_snapshot",
        "finished_utc": "2026-07-29T11:19:51.646293Z",
        "log": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_p8d_cdc_ratios/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-29T11:19:49.923566Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_cdc_ratios_snapshot -runall",
        "finished_utc": "2026-07-29T11:19:54.269741Z",
        "log": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_p8d_cdc_ratios/run.log",
        "returncode": 0,
        "started_utc": "2026-07-29T11:19:51.646870Z",
        "timed_out": false
      }
    },
    "required_markers": [
      "P8D_CDC_RATIO_1_1_PASS=1",
      "P8D_CDC_RATIO_2_1_PASS=1",
      "P8D_CDC_RATIO_3_2_PASS=1",
      "P8D_CDC_ASYNC_PHASE_PASS=1",
      "TB_IR_P8D_CDC_RATIOS_PASS=1"
    ],
    "sources": [
      "rtl/ir_p8d_async_descriptor_bridge.sv",
      "sim/tb/tb_ir_p8d_cdc_ratios.sv"
    ],
    "status": "PASS",
    "top": "tb_ir_p8d_cdc_ratios"
  },
  "generated_utc": "2026-07-29T12:23:13.994566Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "profile_statuses": {
    "Z7010_2LANE_PROFILE": "PASS",
    "Z7020_FIXED_32MODULE_PLUS_DATA_PLANE_PROFILE": "PASS",
    "Z7020_ROTATING_8LANE_PROFILE": "PASS"
  },
  "schema_version": 1,
  "source_commit": "8ecf71c2a795b887daac7c8f91300b1eb8a2921f",
  "status": "PASS",
  "test_id": "P8D-MULTI-PROFILE-MATRIX"
}
```
