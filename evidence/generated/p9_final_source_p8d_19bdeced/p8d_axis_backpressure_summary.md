# P8D aggregate AXI-Stream backpressure

- Status: `PASS`
- Test ID: `P8D-AXIS-BACKPRESSURE`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `19bdeced49b01804611c2ce56a114b3fc164745c`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-28T18:38:55.536999Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_19bdeced/p8d_raw/formal_19bdeced49b0/xsim/tb_ir_axis_backpressure",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_axis_tx_frontend.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_axis_rx_backend.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_axis_backpressure.sv",
        "finished_utc": "2026-07-28T18:38:18.892325Z",
        "log": "evidence/generated/p9_final_source_p8d_19bdeced/p8d_raw/formal_19bdeced49b0/xsim/tb_ir_axis_backpressure/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-28T18:38:18.137739Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_axis_backpressure -debug typical -s tb_ir_axis_backpressure_snapshot",
        "finished_utc": "2026-07-28T18:38:19.990248Z",
        "log": "evidence/generated/p9_final_source_p8d_19bdeced/p8d_raw/formal_19bdeced49b0/xsim/tb_ir_axis_backpressure/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-28T18:38:18.892894Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_axis_backpressure_snapshot -runall",
        "finished_utc": "2026-07-28T18:38:22.544974Z",
        "log": "evidence/generated/p9_final_source_p8d_19bdeced/p8d_raw/formal_19bdeced49b0/xsim/tb_ir_axis_backpressure/run.log",
        "returncode": 0,
        "started_utc": "2026-07-28T18:38:19.990826Z",
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
  "source_commit": "19bdeced49b01804611c2ce56a114b3fc164745c",
  "status": "PASS",
  "test_id": "P8D-AXIS-BACKPRESSURE"
}
```
