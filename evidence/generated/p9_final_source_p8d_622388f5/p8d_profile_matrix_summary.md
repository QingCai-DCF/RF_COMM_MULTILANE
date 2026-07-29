# P8D multi-profile matrix

- Status: `PASS`
- Test ID: `P8D-MULTI-PROFILE-MATRIX`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `622388f5394839e3554a0a7c489715a80b26bff8`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "cdc_ratio_simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_622388f5/p8d_raw/formal_622388f53948/xsim/tb_ir_p8d_cdc_ratios",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_p8d_async_descriptor_bridge.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8d_cdc_ratios.sv",
        "finished_utc": "2026-07-27T14:49:52.210414Z",
        "log": "evidence/generated/p9_final_source_p8d_622388f5/p8d_raw/formal_622388f53948/xsim/tb_ir_p8d_cdc_ratios/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-27T14:49:51.481825Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_cdc_ratios -debug typical -s tb_ir_p8d_cdc_ratios_snapshot",
        "finished_utc": "2026-07-27T14:49:53.942028Z",
        "log": "evidence/generated/p9_final_source_p8d_622388f5/p8d_raw/formal_622388f53948/xsim/tb_ir_p8d_cdc_ratios/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-27T14:49:52.210993Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_cdc_ratios_snapshot -runall",
        "finished_utc": "2026-07-27T14:49:56.594015Z",
        "log": "evidence/generated/p9_final_source_p8d_622388f5/p8d_raw/formal_622388f53948/xsim/tb_ir_p8d_cdc_ratios/run.log",
        "returncode": 0,
        "started_utc": "2026-07-27T14:49:53.942616Z",
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
  "generated_utc": "2026-07-27T15:52:47.036943Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "profile_statuses": {
    "Z7010_2LANE_PROFILE": "PASS",
    "Z7020_FIXED_32MODULE_PLUS_DATA_PLANE_PROFILE": "PASS",
    "Z7020_ROTATING_8LANE_PROFILE": "PASS"
  },
  "schema_version": 1,
  "source_commit": "622388f5394839e3554a0a7c489715a80b26bff8",
  "status": "PASS",
  "test_id": "P8D-MULTI-PROFILE-MATRIX"
}
```
