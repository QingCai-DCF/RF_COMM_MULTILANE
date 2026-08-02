# P8D register-map consistency

- Status: `PASS`
- Test ID: `P8D-REGISTER-MAP-CONSISTENCY`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `a1ac5457bc1555312c00dda81f2e2ad3a7c9751a`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "command_log": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/register_map_verify.log",
  "generated_utc": "2026-08-02T07:21:52.770653Z",
  "generator_manifest_path": "config/register_map/generated/ir_regs_manifest.json",
  "generator_manifest_sha256": "49d8bc3c1c5b9c6a1990c28be6dd861917b5e71668d483a4610e54ba59e2fdf8",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "register_map_path": "config/register_map/ir_axi_regs.yaml",
  "register_map_sha256": "cfc2f097218a618b461299e54765af29aa19d380c6f974101011ddc46c0301ea",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_p8d_data_plane_regs",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\rtl\\ir_p8d_data_plane_regs.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\sim\\tb\\tb_ir_p8d_data_plane_regs.sv",
        "finished_utc": "2026-08-02T07:21:47.265245Z",
        "log": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_p8d_data_plane_regs/compile.log",
        "returncode": 0,
        "started_utc": "2026-08-02T07:21:46.538390Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_data_plane_regs -debug typical -s tb_ir_p8d_data_plane_regs_snapshot",
        "finished_utc": "2026-08-02T07:21:48.504000Z",
        "log": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_p8d_data_plane_regs/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-08-02T07:21:47.267224Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_data_plane_regs_snapshot -runall",
        "finished_utc": "2026-08-02T07:21:51.112004Z",
        "log": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_p8d_data_plane_regs/run.log",
        "returncode": 0,
        "started_utc": "2026-08-02T07:21:48.504587Z",
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
  "source_commit": "a1ac5457bc1555312c00dda81f2e2ad3a7c9751a",
  "status": "PASS",
  "test_id": "P8D-REGISTER-MAP-CONSISTENCY"
}
```
