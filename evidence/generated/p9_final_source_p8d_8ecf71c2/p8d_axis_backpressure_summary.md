# P8D aggregate AXI-Stream backpressure

- Status: `PASS`
- Test ID: `P8D-AXIS-BACKPRESSURE`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `8ecf71c2a795b887daac7c8f91300b1eb8a2921f`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-29T11:19:58.882356Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_axis_backpressure",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_axis_tx_frontend.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_axis_rx_backend.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_axis_backpressure.sv",
        "finished_utc": "2026-07-29T11:19:22.114910Z",
        "log": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_axis_backpressure/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-29T11:19:21.374235Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_axis_backpressure -debug typical -s tb_ir_axis_backpressure_snapshot",
        "finished_utc": "2026-07-29T11:19:23.195551Z",
        "log": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_axis_backpressure/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-29T11:19:22.115652Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_axis_backpressure_snapshot -runall",
        "finished_utc": "2026-07-29T11:19:25.746121Z",
        "log": "evidence/generated/p9_final_source_p8d_8ecf71c2/p8d_raw/formal_8ecf71c2a795/xsim/tb_ir_axis_backpressure/run.log",
        "returncode": 0,
        "started_utc": "2026-07-29T11:19:23.196166Z",
        "timed_out": false
      }
    },
    "required_markers": [
      "P8D_AXIS_RANDOM_BACKPRESSURE_PASS=1",
      "P8D_AXIS_NO_LOSS_NO_DUPLICATE_PASS=1",
      "P8D_AXIS_MALFORMED_PACKET_REJECTION_PASS=1",
      "TB_IR_AXIS_BACKPRESSURE_PASS=1"
    ],
    "sources": [
      "rtl/ir_axis_tx_frontend.sv",
      "rtl/ir_axis_rx_backend.sv",
      "sim/tb/tb_ir_axis_backpressure.sv"
    ],
    "status": "PASS",
    "top": "tb_ir_axis_backpressure"
  },
  "source_commit": "8ecf71c2a795b887daac7c8f91300b1eb8a2921f",
  "status": "PASS",
  "test_id": "P8D-AXIS-BACKPRESSURE"
}
```
