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
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat -sv -i C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_path_mapping_pkg.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_path_mapping_engine.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_bank_lane_crossbar.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_path_epoch_commit.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\sim\\tb\\tb_p8b_mapping_unit.sv",
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
    "log_path": "evidence/generated/p8b_xsim/mapping_unit.log",
    "log_sha256": "8c3440dfdfccf863511c9c2edf9d515a395eaeae99ed370135e9323c01d6ca8f",
    "marker": "TB_P8B_MAPPING_UNIT_PASS=1",
    "marker_seen": true,
    "name": "mapping_unit",
    "returncode": 0,
    "status": "PASS"
  },
  "phase_trajectory": {
    "commands": [
      {
        "command": "D:\\Xilinx\\Vivado\\2023.1\\bin\\xvlog.bat -sv -i C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_path_mapping_pkg.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_phase_validity_guard.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\rtl\\ir_handover_metrics.sv C:\\Users\\user\\.codex\\worktrees\\3765\\RF_COMM_MULTILANE\\sim\\tb\\tb_p8b_phase_trajectory.sv",
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
    "log_path": "evidence/generated/p8b_xsim/phase_trajectory.log",
    "log_sha256": "d579bf8002907e5e103a6c55aed4d8b321d5ba956f1d977dcde4ef32d093287b",
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
