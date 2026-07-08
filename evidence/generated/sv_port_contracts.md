# SystemVerilog Port Contracts

SV_PORT_CONTRACT_MODULES_PARSED=1
SV_PORT_CONTRACT_ALL_INSTANCES_NAMED=1
SV_PORT_CONTRACT_NO_UNKNOWN_PORTS=1
SV_PORT_CONTRACT_NO_MISSING_PORTS=1
SV_PORT_CONTRACT_NO_DUPLICATE_PORTS=1
SV_PORT_CONTRACT_TB_COVERAGE=1
SV_PORT_CONTRACT_STATIC=PASS

| Module | Instance count | Declared ports |
|---|---:|---:|
| `tfdu_lane_phy` | 2 | 23 |
| `tfdu6102_behavior_model` | 6 | 8 |
| `ir_4ppm_codec` | 4 | 20 |
| `ir_frame_l1` | 1 | 22 |
| `ir_arq_l2` | 1 | 41 |
| `ir_multilane_scheduler` | 1 | 23 |
| `ir_axi_regs_new` | 1 | 50 |
| `ir_top_new` | 0 | 8 |

This static gate checks named-port instance compatibility. It does not replace simulator or Vivado elaboration; tool discovery and simulator execution are recorded by `scripts/run_offline_gates.py`.
