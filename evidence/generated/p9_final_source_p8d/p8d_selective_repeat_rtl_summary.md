# P8D selective-repeat RTL

- Status: `PASS`
- Test ID: `P8D-SELECTIVE-REPEAT-RTL`
- Profile: `P8D_MULTI_PROFILE_OFFLINE`
- Source commit: `6d88b7854219c8b514ef36109a456ffbda4972d8`

```json
{
  "CURRENT_RUN_HARDWARE_AUTHORIZATION": false,
  "NO_HARDWARE_ACTIONS_EXECUTED": true,
  "generated_utc": "2026-07-29T12:26:02.343792Z",
  "hardware_scope_promoted": false,
  "profile": "P8D_MULTI_PROFILE_OFFLINE",
  "rtl_python_crosscheck": {
    "actual_records": 2048,
    "expected_path": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/reference/crosscheck_expected.json",
    "expected_records": 2048,
    "first_mismatches": [],
    "mismatch_count": 0,
    "rtl_log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8d_python_crosscheck/run.log",
    "status": "PASS",
    "test_id": "P8D-RTL-PYTHON-CROSSCHECK"
  },
  "schema_version": 1,
  "simulations": {
    "tb_ir_data_plane_integration_2lane": {
      "log_directory": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_2lane",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_health_weighted_scheduler.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_data_plane_top.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\p8d_data_plane_integration_common.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_data_plane_integration_2lane.sv",
          "finished_utc": "2026-07-29T12:25:34.161190Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_2lane/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:33.378770Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_data_plane_integration_2lane -debug typical -s tb_ir_data_plane_integration_2lane_snapshot",
          "finished_utc": "2026-07-29T12:25:35.542794Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_2lane/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:34.161946Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_data_plane_integration_2lane_snapshot -runall",
          "finished_utc": "2026-07-29T12:25:38.148013Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_2lane/run.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:35.543441Z",
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
      "log_directory": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_8lane",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_health_weighted_scheduler.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_data_plane_top.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\p8d_data_plane_integration_common.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_data_plane_integration_8lane.sv",
          "finished_utc": "2026-07-29T12:25:38.946027Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_8lane/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:38.165908Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_data_plane_integration_8lane -debug typical -s tb_ir_data_plane_integration_8lane_snapshot",
          "finished_utc": "2026-07-29T12:25:40.358309Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_8lane/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:38.946661Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_data_plane_integration_8lane_snapshot -runall",
          "finished_utc": "2026-07-29T12:25:42.978124Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_data_plane_integration_8lane/run.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:40.358875Z",
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
      "log_directory": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8b_p8c_p8d_integration",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\generated\\tfdu_safety_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_mapping_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_mapping_engine.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_tfdu_exact_duty_accountant.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_tfdu_physical_module_safety.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_tfdu_safety_endpoint.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_ack_aggregator.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_health_weighted_scheduler.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_data_plane_top.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8b_p8c_p8d_integration.sv",
          "finished_utc": "2026-07-29T12:25:43.798599Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8b_p8c_p8d_integration/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:42.995074Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8b_p8c_p8d_integration -debug typical -s tb_ir_p8b_p8c_p8d_integration_snapshot",
          "finished_utc": "2026-07-29T12:25:45.467242Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8b_p8c_p8d_integration/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:43.799785Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8b_p8c_p8d_integration_snapshot -runall",
          "finished_utc": "2026-07-29T12:25:48.195549Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8b_p8c_p8d_integration/run.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:45.467816Z",
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
      "log_directory": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8d_cdc_ratios",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_p8d_async_descriptor_bridge.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_p8d_cdc_ratios.sv",
          "finished_utc": "2026-07-29T12:25:53.300702Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8d_cdc_ratios/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:52.553992Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_p8d_cdc_ratios -debug typical -s tb_ir_p8d_cdc_ratios_snapshot",
          "finished_utc": "2026-07-29T12:25:55.082322Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8d_cdc_ratios/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:53.301290Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_p8d_cdc_ratios_snapshot -runall",
          "finished_utc": "2026-07-29T12:25:57.759416Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_p8d_cdc_ratios/run.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:55.082985Z",
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
      "log_directory": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_rx",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_rx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_selective_repeat_rx.sv",
          "finished_utc": "2026-07-29T12:25:11.123919Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_rx/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:10.352446Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_selective_repeat_rx -debug typical -s tb_ir_selective_repeat_rx_snapshot",
          "finished_utc": "2026-07-29T12:25:12.252446Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_rx/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:11.124698Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_selective_repeat_rx_snapshot -runall",
          "finished_utc": "2026-07-29T12:25:14.826430Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_rx/run.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:12.253012Z",
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
      "log_directory": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_tx",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_selective_repeat_tx.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_selective_repeat_tx.sv",
          "finished_utc": "2026-07-29T12:25:06.666923Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_tx/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:05.922172Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_selective_repeat_tx -debug typical -s tb_ir_selective_repeat_tx_snapshot",
          "finished_utc": "2026-07-29T12:25:07.713100Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_tx/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:06.667494Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_selective_repeat_tx_snapshot -runall",
          "finished_utc": "2026-07-29T12:25:10.335197Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_selective_repeat_tx/run.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:07.713678Z",
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
      "log_directory": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_seq_math",
      "phases": {
        "compile": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat --sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_seq_math_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_ir_seq_math.sv",
          "finished_utc": "2026-07-29T12:25:02.425638Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_seq_math/compile.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:01.659265Z",
          "timed_out": false
        },
        "elaborate": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_ir_seq_math -debug typical -s tb_ir_seq_math_snapshot",
          "finished_utc": "2026-07-29T12:25:03.298405Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_seq_math/elaborate.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:02.426206Z",
          "timed_out": false
        },
        "fatal_detected": false,
        "missing_markers": [],
        "run": {
          "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_ir_seq_math_snapshot -runall",
          "finished_utc": "2026-07-29T12:25:05.905217Z",
          "log": "evidence/generated/p9_final_source_p8d_6d88b785/p8d_raw/formal_6d88b7854219/xsim/tb_ir_seq_math/run.log",
          "returncode": 0,
          "started_utc": "2026-07-29T12:25:03.299807Z",
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
  "source_commit": "6d88b7854219c8b514ef36109a456ffbda4972d8",
  "status": "PASS",
  "test_id": "P8D-SELECTIVE-REPEAT-RTL"
}
```
