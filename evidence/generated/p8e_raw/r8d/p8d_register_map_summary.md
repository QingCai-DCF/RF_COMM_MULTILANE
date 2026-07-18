# P8D register-map consistency

- Status: `PASS`
- Test ID: `P8D-REGISTER-MAP-CONSISTENCY`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `0c67e7717a5a0fb594a237a05184be65cf748f4f`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "evidence/generated/p8e_raw/r8d/p8d_raw/formal_0c67e7717a5a/register_map_verify.log",
  "generated_utc": "2026-07-18T21:16:09.449360Z",
  "generator_manifest_path": "config/register_map/generated/ir_regs_manifest.json",
  "generator_manifest_sha256": "a5ae6ed56704261fa197d95c0a5e7f58e793fd6a4bceec1ba891639f7b799fa6",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "register_map_path": "config/register_map/ir_axi_regs.yaml",
  "register_map_sha256": "8f029023d7871a7b8351c9c9256164d34a0ec2954754c261c31da410851d34b1",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p8e_raw/r8d/p8d_raw/formal_0c67e7717a5a/xsim/tb_ir_p8d_data_plane_regs",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_p8d_data_plane_regs.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\sim\\tb\\tb_ir_p8d_data_plane_regs.sv",
        "finished_utc": "2026-07-18T21:16:03.862071Z",
        "log": "evidence/generated/p8e_raw/r8d/p8d_raw/formal_0c67e7717a5a/xsim/tb_ir_p8d_data_plane_regs/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-18T21:16:03.117553Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_data_plane_regs -debug typical -s tb_ir_p8d_data_plane_regs_snapshot",
        "finished_utc": "2026-07-18T21:16:05.141634Z",
        "log": "evidence/generated/p8e_raw/r8d/p8d_raw/formal_0c67e7717a5a/xsim/tb_ir_p8d_data_plane_regs/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-18T21:16:03.862702Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_data_plane_regs_snapshot -runall",
        "finished_utc": "2026-07-18T21:16:07.778276Z",
        "log": "evidence/generated/p8e_raw/r8d/p8d_raw/formal_0c67e7717a5a/xsim/tb_ir_p8d_data_plane_regs/run.log",
        "returncode": 0,
        "started_utc": "2026-07-18T21:16:05.142266Z",
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
  "source_commit": "0c67e7717a5a0fb594a237a05184be65cf748f4f",
  "status": "PASS",
  "test_id": "P8D-REGISTER-MAP-CONSISTENCY"
}
```
