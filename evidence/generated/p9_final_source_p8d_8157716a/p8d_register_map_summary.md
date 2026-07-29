# P8D register-map consistency

- Status: `PASS`
- Test ID: `P8D-REGISTER-MAP-CONSISTENCY`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `8157716a47a9da45e07255c7453517dff6f1cb1b`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "evidence/generated/p9_final_source_p8d_8157716a/p8d_raw/formal_8157716a47a9/register_map_verify.log",
  "generated_utc": "2026-07-28T12:12:49.726249Z",
  "generator_manifest_path": "config/register_map/generated/ir_regs_manifest.json",
  "generator_manifest_sha256": "7a9d7c4f55218b2a6cd6e59cd34993281541c698ac3c60750b5297e4c3e3054d",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "register_map_path": "config/register_map/ir_axi_regs.yaml",
  "register_map_sha256": "9afd713909fdfc4da15fe342546f161f6d9fc6a6e79e55d2c9cbec9fcf35f13a",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_8157716a/p8d_raw/formal_8157716a47a9/xsim/tb_ir_p8d_data_plane_regs",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_p8d_data_plane_regs.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8d_data_plane_regs.sv",
        "finished_utc": "2026-07-28T12:12:44.296411Z",
        "log": "evidence/generated/p9_final_source_p8d_8157716a/p8d_raw/formal_8157716a47a9/xsim/tb_ir_p8d_data_plane_regs/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-28T12:12:43.561178Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_data_plane_regs -debug typical -s tb_ir_p8d_data_plane_regs_snapshot",
        "finished_utc": "2026-07-28T12:12:45.539257Z",
        "log": "evidence/generated/p9_final_source_p8d_8157716a/p8d_raw/formal_8157716a47a9/xsim/tb_ir_p8d_data_plane_regs/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-28T12:12:44.297114Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_data_plane_regs_snapshot -runall",
        "finished_utc": "2026-07-28T12:12:48.114941Z",
        "log": "evidence/generated/p9_final_source_p8d_8157716a/p8d_raw/formal_8157716a47a9/xsim/tb_ir_p8d_data_plane_regs/run.log",
        "returncode": 0,
        "started_utc": "2026-07-28T12:12:45.539821Z",
        "timed_out": false
      }
    },
    "required_markers": [
      "P8D_REGISTER_RO_SNAPSHOT_PASS=1",
      "P8D_REGISTER_CONFIG_FAIL_CLOSED_PASS=1",
      "TB_IR_P8D_DATA_PLANE_REGS_PASS=1"
    ],
    "sources": [
      "rtl/ir_p8d_data_plane_regs.sv",
      "sim/tb/tb_ir_p8d_data_plane_regs.sv"
    ],
    "status": "PASS",
    "top": "tb_ir_p8d_data_plane_regs"
  },
  "source_commit": "8157716a47a9da45e07255c7453517dff6f1cb1b",
  "status": "PASS",
  "test_id": "P8D-REGISTER-MAP-CONSISTENCY"
}
```
