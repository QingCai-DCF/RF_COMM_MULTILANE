# P8D register-map consistency

- Status: `PASS`
- Test ID: `P8D-REGISTER-MAP-CONSISTENCY`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `493955d5788942ac448a9cfd99c97f0c526281fe`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "build/p10_1r_p8d_exact_branch/p8d_raw/formal_493955d57889/register_map_verify.log",
  "generated_utc": "2026-08-01T17:43:35.168754Z",
  "generator_manifest_path": "config/register_map/generated/ir_regs_manifest.json",
  "generator_manifest_sha256": "e0a2dceb83371310bac897de4dd4bcf558f836f38b74ca5af5dc1fb80b48ad4f",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "register_map_path": "config/register_map/ir_axi_regs.yaml",
  "register_map_sha256": "2a82d64c377d71a4e95d80d0d23b938d42e91b782444c572fe82466153d711a6",
  "schema_version": 1,
  "simulation": {
    "log_directory": "build/p10_1r_p8d_exact_branch/p8d_raw/formal_493955d57889/xsim/tb_ir_p8d_data_plane_regs",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R_GATE_TMP\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R_GATE_TMP\\rtl\\ir_p8d_data_plane_regs.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R_GATE_TMP\\sim\\tb\\tb_ir_p8d_data_plane_regs.sv",
        "finished_utc": "2026-08-01T17:43:29.882680Z",
        "log": "build/p10_1r_p8d_exact_branch/p8d_raw/formal_493955d57889/xsim/tb_ir_p8d_data_plane_regs/compile.log",
        "returncode": 0,
        "started_utc": "2026-08-01T17:43:29.149940Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_data_plane_regs -debug typical -s tb_ir_p8d_data_plane_regs_snapshot",
        "finished_utc": "2026-08-01T17:43:31.124477Z",
        "log": "build/p10_1r_p8d_exact_branch/p8d_raw/formal_493955d57889/xsim/tb_ir_p8d_data_plane_regs/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-08-01T17:43:29.883330Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_data_plane_regs_snapshot -runall",
        "finished_utc": "2026-08-01T17:43:33.719966Z",
        "log": "build/p10_1r_p8d_exact_branch/p8d_raw/formal_493955d57889/xsim/tb_ir_p8d_data_plane_regs/run.log",
        "returncode": 0,
        "started_utc": "2026-08-01T17:43:31.125055Z",
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
  "source_commit": "493955d5788942ac448a9cfd99c97f0c526281fe",
  "status": "PASS",
  "test_id": "P8D-REGISTER-MAP-CONSISTENCY"
}
```
