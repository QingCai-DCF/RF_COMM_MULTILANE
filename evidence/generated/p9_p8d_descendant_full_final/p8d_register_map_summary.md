# P8D register-map consistency

- Status: `PASS`
- Test ID: `P8D-REGISTER-MAP-CONSISTENCY`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `36e7ecd07b67b385d433f69ec754af6db473a3a6`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/register_map_verify.log",
  "generated_utc": "2026-07-26T13:44:09.146955Z",
  "generator_manifest_path": "config/register_map/generated/ir_regs_manifest.json",
  "generator_manifest_sha256": "7b5c00dc806d704ff4d9b4867e404dfcf2c3820087a3e9e4ef69131806020889",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "register_map_path": "config/register_map/ir_axi_regs.yaml",
  "register_map_sha256": "2e422c25a68b3d013a96e9c9df7aaf4664ddd3e9e5d551aff40516004468387e",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/xsim/tb_ir_p8d_data_plane_regs",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_p8d_data_plane_regs.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8d_data_plane_regs.sv",
        "finished_utc": "2026-07-26T13:44:03.404943Z",
        "log": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/xsim/tb_ir_p8d_data_plane_regs/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-26T13:44:02.658929Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_data_plane_regs -debug typical -s tb_ir_p8d_data_plane_regs_snapshot",
        "finished_utc": "2026-07-26T13:44:04.667678Z",
        "log": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/xsim/tb_ir_p8d_data_plane_regs/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-26T13:44:03.405748Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_data_plane_regs_snapshot -runall",
        "finished_utc": "2026-07-26T13:44:07.308028Z",
        "log": "evidence/generated/p9_p8d_descendant_full_final/p8d_raw/formal_36e7ecd07b67/xsim/tb_ir_p8d_data_plane_regs/run.log",
        "returncode": 0,
        "started_utc": "2026-07-26T13:44:04.668249Z",
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
  "source_commit": "36e7ecd07b67b385d433f69ec754af6db473a3a6",
  "status": "PASS",
  "test_id": "P8D-REGISTER-MAP-CONSISTENCY"
}
```
