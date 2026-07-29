# P8B simulation gate summary

- `status`: `PASS`
- `simulator`: `Vivado Simulator 2023.1 xsim`
- `mandatory_tool_available`: `True`
- `python_unit_test_returncode`: `0`
- `python_unit_test_count`: `11`

```json
{
  "mandatory_tool_available": true,
  "mapping_unit": {
    "commands": [
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat -sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_mapping_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_mapping_engine.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_bank_lane_crossbar.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_epoch_commit.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_p8b_mapping_unit.sv",
        "returncode": 0
      },
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_p8b_mapping_unit -debug typical -s tb_p8b_mapping_unit_snapshot",
        "returncode": 0
      },
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_p8b_mapping_unit_snapshot -runall",
        "returncode": 0
      }
    ],
    "log_path": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/regression/p8b/p8b_xsim/mapping_unit.log",
    "log_sha256": "89e96e6b43595ff27d2c6d4f9d8b0c8f758a2eebe55e01cf780188bd7f12aa4d",
    "marker": "TB_P8B_MAPPING_UNIT_PASS=1",
    "marker_seen": true,
    "name": "mapping_unit",
    "returncode": 0,
    "status": "PASS"
  },
  "phase_trajectory": {
    "commands": [
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat -sv -i C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_path_mapping_pkg.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_phase_validity_guard.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\rtl\\ir_handover_metrics.sv C:\\Users\\user\\Documents\\RF_COMM_MULTILANE_P9\\sim\\tb\\tb_p8b_phase_trajectory.sv",
        "returncode": 0
      },
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xelab.bat tb_p8b_phase_trajectory -debug typical -s tb_p8b_phase_trajectory_snapshot",
        "returncode": 0
      },
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xsim.bat tb_p8b_phase_trajectory_snapshot -runall",
        "returncode": 0
      }
    ],
    "log_path": "evidence/generated/p9_final_source_p8d_f57d21d2/p8d_raw/formal_f57d21d23fc0/regression/p8b/p8b_xsim/phase_trajectory.log",
    "log_sha256": "e1abefefb35b8a37a8c86f8a4a382614e495821d3545def7db78eb33b0c21234",
    "marker": "TB_P8B_PHASE_TRAJECTORY_PASS=1",
    "marker_seen": true,
    "name": "phase_trajectory",
    "returncode": 0,
    "status": "PASS"
  },
  "python_unit_test_count": 11,
  "python_unit_test_returncode": 0,
  "simulator": "Vivado Simulator 2023.1 xsim",
  "status": "PASS"
}
```
