# P8D repository intake

- Status: `PASS`
- Decision: `PROCEED_WITH_P8D_IMPLEMENTATION`
- Start timestamp (UTC): `2026-07-18T05:07:07.9868581Z`
- Hardware actions executed: `false`

## Baseline

| Field | Observed |
| --- | --- |
| Worktree | `C:/Users/user/.codex/worktrees/3765/RF_COMM_MULTILANE` |
| Branch | `p8/integration` |
| Clean HEAD before P8D source changes | `f76b477cba165270dde59e9db2a8cd8bb1a83ccc` |
| `p8c-pass^{}` | `c44b0d45133bf75c9c71f53dde77f3dc186ad131` |
| P8C source | `e8be6ffddd1b59b13b6bf3e0c32c02c6a66b6134` |
| `NO_HARDWARE` | `1` |
| `CURRENT_RUN_HARDWARE_AUTHORIZATION` | `false` |

The previously untracked P8C completion summary was committed only after
explicit user confirmation. All failed intake and interrupted-regression
artifacts remain preserved under `evidence/generated/p8d_raw`.

## Required checks

| Check | Result |
| --- | --- |
| Branch is `p8/integration` | `PASS` |
| `p8c-pass` exists and resolves to the expected checkpoint | `PASS` |
| HEAD is a known clean descendant | `PASS` |
| Worktree clean before P8D source changes | `PASS` |
| Project constraints SHA256 matches | `PASS` |
| P8C `--verify-existing` | `PASS` |
| Complete P0–P8C offline regression | `PASS` |

The full regression ran 33 checks in 3,600.4 seconds with zero failures and
zero pending tools. P8B and P8C were both included. Its immutable P8D baseline
copy is under `evidence/generated/p8d_raw/baseline_offline_attempt_003_pass`.

## Canonical hashes

| Artifact | SHA256 |
| --- | --- |
| `PROJECT_CONSTRAINTS.txt` | `9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758` |
| `AGENTS.md` | `6677e4589355aa96dd434f8eb5ab9567c97efcb87ca5b3aae137efbd6776aebb` |
| `config/project_state.json` | `e52f7e46a9f4ada89b083e9c318748a25c694069227f47a6ccf4a00e42eab175` |
| `config/project_requirements.yaml` | `d7c19fe0a67fa6807a456d132e8a538bc0f7800ceb7e5ba16fc2445bd13dfd95` |
| `config/tfdu_safety.yaml` | `e9069e49c1fd835ac7d1aee7e75b8e5b5cb13533fd703ddddf2ac3d8da61fb06` |
| `config/register_map/ir_axi_regs.yaml` | `9993ae99c883a921f61bf1af8f1aca54b8a89fa7cd53452f435a6ed992c7fd2d` |
| `evidence/generated/p8c_final_summary.json` | `161d89e30eb6bcc607cbb1732fcccd739519e5d92e014e3530199d8b92dc819e` |
| `evidence/generated/p8c_final_summary.md` | `41f104ffda9512dd844872c211b9ee3dd7826bf9422d0c37d87192f620921b88` |

## Tool inventory

| Tool | Version/status |
| --- | --- |
| Python | `3.14.3` |
| Git | `2.54.0.windows.1` |
| Vivado | `2023.1 build 3865809` |
| XSIM | `D:/Xilinx/Vivado/2023.1/bin/xsim.bat` |
| Vitis ARM GCC | `arm-xilinx-eabi-gcc 12.2.0` |

## Existing implementation mapping

| Responsibility | Current path |
| --- | --- |
| Legacy stop-and-wait L2 | `rtl/ir_arq_l2.sv` |
| Scheduler | `rtl/ir_multilane_scheduler.sv` |
| L1 / 4PPM / TFDU | `rtl/ir_frame_l1.sv`, `rtl/ir_4ppm_codec.sv`, `rtl/tfdu_lane_phy.sv` |
| P8B mapping/crossbar/epoch | `rtl/ir_bank_lane_crossbar.sv`, `rtl/ir_path_epoch_commit.sv`, `rtl/ir_path_mapping_engine.sv` |
| P8C safety integration | `rtl/ir_p8c_mapping_safety_adapter.sv`, `rtl/ir_tfdu_*` |
| RFAP v1 | `config/p7_app_protocol.yaml`, `tools/p7_app_protocol.py`, `software/ps_driver/p7_app_service.*` |
| AXI-Lite registers | `rtl/ir_axi_regs_new.sv`, `config/register_map/ir_axi_regs.yaml` |
| PS driver | `software/ps_driver/ir_driver.*`, `software/ps_driver/ir_profile.*` |
| Host tools | `software/host_client`, `software/legacy_host_client` |
| Reference models | `tools/p8b_*`, `tools/p8c_tfdu_safety_reference.py`, `sim/models/tfdu6102_reference.py` |
| XSIM benches | `sim/tb` |
| Offline gates | `scripts/run_offline_gates.py`, `scripts/run_p8b_geometry_gate.py`, `scripts/run_p8c_safety_gate.py` |
