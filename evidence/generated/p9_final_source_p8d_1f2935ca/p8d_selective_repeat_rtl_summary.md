# P8D selective-repeat RTL

- Status: `PASS`
- Test ID: `P8D-SELECTIVE-REPEAT-RTL`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `1f2935cabb88ec46c32ecfae961fde9e55a6b3c0`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-28T08:52:07.701442Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "rtl_python_crosscheck": {
    "actual_records": 2048,
    "expected_path": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/reference/crosscheck_expected.json",
    "expected_records": 2048,
    "first_mismatches": [],
    "mismatch_count": 0,
    "rtl_log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8d_python_crosscheck/run.log",
    "status": "PASS",
    "test_id": "P8D-RTL-PYTHON-CROSSCHECK"
  },
  "schema_version": 1,
  "simulations": {
    "tb_ir_data_plane_integration_2lane": {
      "log_directory": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_2lane",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_health_weighted_scheduler.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_data_plane_top.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\p8d_data_plane_integration_common.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_data_plane_integration_2lane.sv",
          "finished_utc": "2026-07-28T08:51:38.363996Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_2lane/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:37.527783Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_data_plane_integration_2lane -debug typical -s tb_ir_data_plane_integration_2lane_snapshot",
          "finished_utc": "2026-07-28T08:51:39.721606Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_2lane/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:38.364684Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_data_plane_integration_2lane_snapshot -runall",
          "finished_utc": "2026-07-28T08:51:42.477444Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_2lane/run.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:39.722170Z",
          "timed_out": false
        }
      },
      "required_markers": [
        "P8D_DATA_PLANE_GLOBAL_WINDOW_SAFETY_INTEGRATION_PASS=1",
        "P8D_DATA_PLANE_DUPLICATE_APPLICATION_DELIVERY_ZERO_PASS=1",
        "TB_IR_DATA_PLANE_INTEGRATION_2LANE_PASS=1"
      ],
      "sources": [
        "rtl/ir_seq_math_pkg.sv",
        "rtl/ir_ack_aggregator.sv",
        "rtl/ir_health_weighted_scheduler.sv",
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_selective_repeat_rx.sv",
        "rtl/ir_data_plane_top.sv",
        "sim/tb/p8d_data_plane_integration_common.sv",
        "sim/tb/tb_ir_data_plane_integration_2lane.sv"
      ],
      "status": "PASS",
      "top": "tb_ir_data_plane_integration_2lane"
    },
    "tb_ir_data_plane_integration_8lane": {
      "log_directory": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_8lane",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_health_weighted_scheduler.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_data_plane_top.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\p8d_data_plane_integration_common.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_data_plane_integration_8lane.sv",
          "finished_utc": "2026-07-28T08:51:43.685219Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_8lane/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:42.518370Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_data_plane_integration_8lane -debug typical -s tb_ir_data_plane_integration_8lane_snapshot",
          "finished_utc": "2026-07-28T08:51:45.278604Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_8lane/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:43.686510Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_data_plane_integration_8lane_snapshot -runall",
          "finished_utc": "2026-07-28T08:51:48.061632Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_data_plane_integration_8lane/run.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:45.279464Z",
          "timed_out": false
        }
      },
      "required_markers": [
        "P8D_DATA_PLANE_GLOBAL_WINDOW_SAFETY_INTEGRATION_PASS=1",
        "P8D_DATA_PLANE_DUPLICATE_APPLICATION_DELIVERY_ZERO_PASS=1",
        "TB_IR_DATA_PLANE_INTEGRATION_8LANE_PASS=1"
      ],
      "sources": [
        "rtl/ir_seq_math_pkg.sv",
        "rtl/ir_ack_aggregator.sv",
        "rtl/ir_health_weighted_scheduler.sv",
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_selective_repeat_rx.sv",
        "rtl/ir_data_plane_top.sv",
        "sim/tb/p8d_data_plane_integration_common.sv",
        "sim/tb/tb_ir_data_plane_integration_8lane.sv"
      ],
      "status": "PASS",
      "top": "tb_ir_data_plane_integration_8lane"
    },
    "tb_ir_p8b_p8c_p8d_integration": {
      "log_directory": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8b_p8c_p8d_integration",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\generated\\tfdu_safety_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_mapping_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_mapping_engine.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_tfdu_exact_duty_accountant.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_tfdu_physical_module_safety.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_tfdu_safety_endpoint.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_health_weighted_scheduler.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_data_plane_top.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8b_p8c_p8d_integration.sv",
          "finished_utc": "2026-07-28T08:51:48.877630Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8b_p8c_p8d_integration/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:48.078277Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8b_p8c_p8d_integration -debug typical -s tb_ir_p8b_p8c_p8d_integration_snapshot",
          "finished_utc": "2026-07-28T08:51:50.538663Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8b_p8c_p8d_integration/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:48.878259Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8b_p8c_p8d_integration_snapshot -runall",
          "finished_utc": "2026-07-28T08:51:53.232961Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8b_p8c_p8d_integration/run.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:50.539403Z",
          "timed_out": false
        }
      },
      "required_markers": [
        "P8D_P8B_MAPPING_GATE_INTEGRATION_PASS=1",
        "P8D_P8C_SINGLE_PERMIT_FINAL_KILL_INTEGRATION_PASS=1",
        "P8D_PARTIAL_FRAME_NOT_RESUMED_PASS=1",
        "TB_IR_P8B_P8C_P8D_INTEGRATION_PASS=1"
      ],
      "sources": [
        "rtl/generated/tfdu_safety_pkg.sv",
        "rtl/ir_path_mapping_pkg.sv",
        "rtl/ir_path_mapping_engine.sv",
        "rtl/ir_tfdu_exact_duty_accountant.sv",
        "rtl/ir_tfdu_physical_module_safety.sv",
        "rtl/ir_tfdu_safety_endpoint.sv",
        "rtl/ir_seq_math_pkg.sv",
        "rtl/ir_ack_aggregator.sv",
        "rtl/ir_health_weighted_scheduler.sv",
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_selective_repeat_rx.sv",
        "rtl/ir_data_plane_top.sv",
        "sim/tb/tb_ir_p8b_p8c_p8d_integration.sv"
      ],
      "status": "PASS",
      "top": "tb_ir_p8b_p8c_p8d_integration"
    },
    "tb_ir_p8d_cdc_ratios": {
      "log_directory": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8d_cdc_ratios",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_p8d_async_descriptor_bridge.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8d_cdc_ratios.sv",
          "finished_utc": "2026-07-28T08:51:58.466843Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8d_cdc_ratios/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:57.707600Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_cdc_ratios -debug typical -s tb_ir_p8d_cdc_ratios_snapshot",
          "finished_utc": "2026-07-28T08:52:00.244660Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8d_cdc_ratios/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:58.467448Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_cdc_ratios_snapshot -runall",
          "finished_utc": "2026-07-28T08:52:02.904473Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_p8d_cdc_ratios/run.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:52:00.245398Z",
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
    "tb_ir_selective_repeat_rx": {
      "log_directory": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_rx",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_selective_repeat_rx.sv",
          "finished_utc": "2026-07-28T08:51:14.821412Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_rx/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:14.054084Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_selective_repeat_rx -debug typical -s tb_ir_selective_repeat_rx_snapshot",
          "finished_utc": "2026-07-28T08:51:15.988423Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_rx/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:14.822238Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_selective_repeat_rx_snapshot -runall",
          "finished_utc": "2026-07-28T08:51:18.652386Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_rx/run.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:15.989041Z",
          "timed_out": false
        }
      },
      "required_markers": [
        "P8D_RX_REORDER_DUPLICATE_SUPPRESSION_PASS=1",
        "P8D_STALE_SESSION_PATH_REJECTION_PASS=1",
        "TB_IR_SELECTIVE_REPEAT_RX_PASS=1"
      ],
      "sources": [
        "rtl/ir_seq_math_pkg.sv",
        "rtl/ir_selective_repeat_rx.sv",
        "sim/tb/tb_ir_selective_repeat_rx.sv"
      ],
      "status": "PASS",
      "top": "tb_ir_selective_repeat_rx"
    },
    "tb_ir_selective_repeat_tx": {
      "log_directory": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_tx",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_selective_repeat_tx.sv",
          "finished_utc": "2026-07-28T08:51:10.305504Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_tx/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:09.516138Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_selective_repeat_tx -debug typical -s tb_ir_selective_repeat_tx_snapshot",
          "finished_utc": "2026-07-28T08:51:11.378492Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_tx/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:10.306075Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_selective_repeat_tx_snapshot -runall",
          "finished_utc": "2026-07-28T08:51:14.036568Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_selective_repeat_tx/run.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:11.379072Z",
          "timed_out": false
        }
      },
      "required_markers": [
        "P8D_GLOBAL_OUTSTANDING_32_PASS=1",
        "P8D_RETRY_EXHAUSTION_BOUNDED_PASS=1",
        "P8D_ACKED_FRAME_SINGLE_COMPLETION_PASS=1",
        "TB_IR_SELECTIVE_REPEAT_TX_PASS=1"
      ],
      "sources": [
        "rtl/ir_seq_math_pkg.sv",
        "rtl/ir_selective_repeat_tx.sv",
        "sim/tb/tb_ir_selective_repeat_tx.sv"
      ],
      "status": "PASS",
      "top": "tb_ir_selective_repeat_tx"
    },
    "tb_ir_seq_math": {
      "log_directory": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_seq_math",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_seq_math.sv",
          "finished_utc": "2026-07-28T08:51:03.560982Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_seq_math/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:01.451538Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_seq_math -debug typical -s tb_ir_seq_math_snapshot",
          "finished_utc": "2026-07-28T08:51:04.943660Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_seq_math/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:03.562031Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_seq_math_snapshot -runall",
          "finished_utc": "2026-07-28T08:51:09.498892Z",
          "log": "evidence/generated/p9_final_source_p8d_1f2935ca/p8d_raw/formal_1f2935cabb88/xsim/tb_ir_seq_math/run.log",
          "returncode": 0,
          "started_utc": "2026-07-28T08:51:04.944671Z",
          "timed_out": false
        }
      },
      "required_markers": [
        "P8D_SEQUENCE_WIDTH_16_PASS=1",
        "P8D_SEQUENCE_WRAP_PASS=1",
        "TB_IR_SEQ_MATH_PASS=1"
      ],
      "sources": [
        "rtl/ir_seq_math_pkg.sv",
        "sim/tb/tb_ir_seq_math.sv"
      ],
      "status": "PASS",
      "top": "tb_ir_seq_math"
    }
  },
  "source_commit": "1f2935cabb88ec46c32ecfae961fde9e55a6b3c0",
  "status": "PASS",
  "test_id": "P8D-SELECTIVE-REPEAT-RTL"
}
```
