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
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat -sv -i <REPO_ROOT>\\rtl <REPO_ROOT>\\rtl\\ir_path_mapping_pkg.sv <REPO_ROOT>\\rtl\\ir_path_mapping_engine.sv <REPO_ROOT>\\rtl\\ir_bank_lane_crossbar.sv <REPO_ROOT>\\rtl\\ir_path_epoch_commit.sv <REPO_ROOT>\\sim\\tb\\tb_p8b_mapping_unit.sv",
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
    "log_path": "evidence/generated/p10_1r_replay_39df1715/p8d_retry_bindings/p8d_raw/formal_39df17155ce8/regression/p8b/p8b_xsim/mapping_unit.log",
    "log_sha256": "49db8751192d8513119305393dfc4cf51817a6c23217e01835042ad3a868cace",
    "marker": "TB_P8B_MAPPING_UNIT_PASS=1",
    "marker_seen": true,
    "name": "mapping_unit",
    "returncode": 0,
    "status": "PASS"
  },
  "phase_trajectory": {
    "commands": [
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat -sv -i <REPO_ROOT>\\rtl <REPO_ROOT>\\rtl\\ir_path_mapping_pkg.sv <REPO_ROOT>\\rtl\\ir_phase_validity_guard.sv <REPO_ROOT>\\rtl\\ir_handover_metrics.sv <REPO_ROOT>\\sim\\tb\\tb_p8b_phase_trajectory.sv",
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
    "log_path": "evidence/generated/p10_1r_replay_39df1715/p8d_retry_bindings/p8d_raw/formal_39df17155ce8/regression/p8b/p8b_xsim/phase_trajectory.log",
    "log_sha256": "22495b96fa0eb71a11df4d2dfa24194fd96347f31c3a84bb807e728e1c625907",
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
