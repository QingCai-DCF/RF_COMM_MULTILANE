# P8D multi-profile matrix

- Status: `PASS`
- Test ID: `P8D-MULTI-PROFILE-MATRIX`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `f57d21d23fc0ffa7fe7866664ac5ed60747ce8f6`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "cdc_ratio_simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_p8d_cdc_ratios",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_p8d_async_descriptor_bridge.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8d_cdc_ratios.sv",
        "finished_utc": "2026-07-28T21:14:08.099368Z",
        "log": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_p8d_cdc_ratios/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-28T21:14:07.363052Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_cdc_ratios -debug typical -s tb_ir_p8d_cdc_ratios_snapshot",
        "finished_utc": "2026-07-28T21:14:09.822328Z",
        "log": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_p8d_cdc_ratios/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-28T21:14:08.100038Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_cdc_ratios_snapshot -runall",
        "finished_utc": "2026-07-28T21:14:12.422310Z",
        "log": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_p8d_cdc_ratios/run.log",
        "returncode": 0,
        "started_utc": "2026-07-28T21:14:09.822900Z",
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
  "generated_utc": "2026-07-28T22:17:27.245258Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "profile_statuses": {
    "Z7010_2LANE_PROFILE": "PASS",
    "Z7020_FIXED_32MODULE_PLUS_DATA_PLANE_PROFILE": "PASS",
    "Z7020_ROTATING_8LANE_PROFILE": "PASS"
  },
  "schema_version": 1,
  "source_commit": "f57d21d23fc0ffa7fe7866664ac5ed60747ce8f6",
  "status": "PASS",
  "test_id": "P8D-MULTI-PROFILE-MATRIX"
}
```
