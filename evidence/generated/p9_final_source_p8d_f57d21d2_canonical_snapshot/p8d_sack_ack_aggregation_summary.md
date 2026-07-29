# P8D SACK and ACK aggregation

- Status: `PASS`
- Test ID: `P8D-SACK-ACK-AGGREGATION`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `f57d21d23fc0ffa7fe7866664ac5ed60747ce8f6`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "ack_loss_recovery_reference": true,
  "generated_utc": "2026-07-28T21:14:17.012222Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_sack_ack_aggregation",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_sack_codec.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_sack_ack_aggregation.sv",
        "finished_utc": "2026-07-28T21:13:31.361807Z",
        "log": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_sack_ack_aggregation/compile.log",
        "returncode": 0,
        "started_utc": "2026-07-28T21:13:30.627731Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_sack_ack_aggregation -debug typical -s tb_ir_sack_ack_aggregation_snapshot",
        "finished_utc": "2026-07-28T21:13:32.442797Z",
        "log": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_sack_ack_aggregation/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-07-28T21:13:31.362407Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_sack_ack_aggregation_snapshot -runall",
        "finished_utc": "2026-07-28T21:13:34.978717Z",
        "log": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/xsim/tb_ir_sack_ack_aggregation/run.log",
        "returncode": 0,
        "started_utc": "2026-07-28T21:13:32.443392Z",
        "timed_out": false
      }
    },
    "required_markers": [
      "P8D_SACK_ENCODE_DECODE_PASS=1",
      "P8D_ACK_AGGREGATION_BOUNDED_DELAY_PASS=1",
      "TB_IR_SACK_ACK_AGGREGATION_PASS=1"
    ],
    "sources": [
      "rtl/ir_seq_math_pkg.sv",
      "rtl/ir_sack_codec.sv",
      "rtl/ir_ack_aggregator.sv",
      "sim/tb/tb_ir_sack_ack_aggregation.sv"
    ],
    "status": "PASS",
    "top": "tb_ir_sack_ack_aggregation"
  },
  "source_commit": "f57d21d23fc0ffa7fe7866664ac5ed60747ce8f6",
  "status": "PASS",
  "test_id": "P8D-SACK-ACK-AGGREGATION"
}
```
