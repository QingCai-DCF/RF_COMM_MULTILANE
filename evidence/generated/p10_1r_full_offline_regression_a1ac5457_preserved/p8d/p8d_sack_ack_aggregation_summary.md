# P8D SACK and ACK aggregation

- Status: `PASS`
- Test ID: `P8D-SACK-ACK-AGGREGATION`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `a1ac5457bc1555312c00dda81f2e2ad3a7c9751a`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "ack_loss_recovery_reference": true,
  "generated_utc": "2026-08-02T07:21:51.130092Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "schema_version": 1,
  "simulation": {
    "log_directory": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_sack_ack_aggregation",
    "phases": {
      "compile": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\rtl\\ir_sack_codec.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P10_1R\\sim\\tb\\tb_ir_sack_ack_aggregation.sv",
        "finished_utc": "2026-08-02T07:21:05.294661Z",
        "log": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_sack_ack_aggregation/compile.log",
        "returncode": 0,
        "started_utc": "2026-08-02T07:21:04.570914Z",
        "timed_out": false
      },
      "elaborate": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_sack_ack_aggregation -debug typical -s tb_ir_sack_ack_aggregation_snapshot",
        "finished_utc": "2026-08-02T07:21:06.375460Z",
        "log": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_sack_ack_aggregation/elaborate.log",
        "returncode": 0,
        "started_utc": "2026-08-02T07:21:05.296585Z",
        "timed_out": false
      },
      "fatal_detected": false,
      "missing_markers": [],
      "run": {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_sack_ack_aggregation_snapshot -runall",
        "finished_utc": "2026-08-02T07:21:08.989385Z",
        "log": "evidence/generated/p10_1r_exact_source_p8d_a1ac5457/p8d_raw/formal_a1ac5457bc15/xsim/tb_ir_sack_ack_aggregation/run.log",
        "returncode": 0,
        "started_utc": "2026-08-02T07:21:06.376157Z",
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
  "source_commit": "a1ac5457bc1555312c00dda81f2e2ad3a7c9751a",
  "status": "PASS",
  "test_id": "P8D-SACK-ACK-AGGREGATION"
}
```
