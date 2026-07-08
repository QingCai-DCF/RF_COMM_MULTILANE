# Active Constraint Freeze

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

active XDC path: `constraints/active/PORT1.generated.xdc`
active XDC SHA256: `cf23a0d34a2fa76521faf4c91f3858cff2117fa6020d302d1a6109f10254f990`
pinmap path: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
pinmap SHA256: `4c7d5f0836a2ab48df7672e00f99455e582fbf477b04ed2b3b44ef38506a8a6a`
lane_count: 2
active profile lane_count_target: 2
primary active XDC count: 1
auxiliary active XDC files: constraints/active/async_clock_groups_impl.xdc
conflict check result: PASS
old single-lane wrapper status: not in active top
current top wrapper status: PASS width matches ACTIVE_PROFILE

## Logical Signal List

- `ir_mode_out_0[0]`
- `ir_mode_out_0[1]`
- `ir_rx_in_0[0]`
- `ir_rx_in_0[1]`
- `ir_sd_0[0]`
- `ir_sd_0[1]`
- `ir_tx_out_0[0]`
- `ir_tx_out_0[1]`
- `loop_mode_b0[0]`
- `loop_mode_b0[1]`
- `loop_rx_b0[0]`
- `loop_rx_b0[1]`
- `loop_sd_b0[0]`
- `loop_sd_b0[1]`
- `loop_tx_b0[0]`
- `loop_tx_b0[1]`

## Package Pin Mapping

| Lane | Side | Signal | Port | Package pin | IOSTANDARD | Connector |
| --- | --- | --- | --- | --- | --- | --- |
| 0 | A | Mode | `ir_mode_out_0[0]` | T12 | LVCMOS33 | J10 |
| 1 | A | Mode | `ir_mode_out_0[1]` | G17 | LVCMOS33 | J11 |
| 0 | A | Rxd | `ir_rx_in_0[0]` | B19 | LVCMOS33 | J10 |
| 1 | A | Rxd | `ir_rx_in_0[1]` | H15 | LVCMOS33 | J11 |
| 0 | A | SD | `ir_sd_0[0]` | T11 | LVCMOS33 | J10 |
| 1 | A | SD | `ir_sd_0[1]` | H16 | LVCMOS33 | J11 |
| 0 | A | Txd | `ir_tx_out_0[0]` | C20 | LVCMOS33 | J10 |
| 1 | A | Txd | `ir_tx_out_0[1]` | K14 | LVCMOS33 | J11 |
| 0 | B | Mode | `loop_mode_b0[0]` | V17 | LVCMOS33 | J10 |
| 1 | B | Mode | `loop_mode_b0[1]` | L16 | LVCMOS33 | J11 |
| 0 | B | Rxd | `loop_rx_b0[0]` | U13 | LVCMOS33 | J10 |
| 1 | B | Rxd | `loop_rx_b0[1]` | G15 | LVCMOS33 | J11 |
| 0 | B | SD | `loop_sd_b0[0]` | T14 | LVCMOS33 | J10 |
| 1 | B | SD | `loop_sd_b0[1]` | M17 | LVCMOS33 | J11 |
| 0 | B | Txd | `loop_tx_b0[0]` | V12 | LVCMOS33 | J10 |
| 1 | B | Txd | `loop_tx_b0[1]` | E18 | LVCMOS33 | J11 |

## Archived / Reference XDC List

- `constraints/legacy_conflicts/PORT1.ip_legacy_conflict.original.xdc`
- `constraints/legacy_conflicts/PORT1.top_active.original.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/PORT1.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/async_clock_groups_impl.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/bd_f066_ila_lib_0_ooc.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/bd_f066_ooc.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/design_shiboqi_ooc.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/design_shiboqi_system_ila_0_0_ooc.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/ila.xdc`
- `legacy/RF_COMM/IPs/ip_ir_array/src/ila_impl.xdc`
- `legacy/RF_COMM/TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/PORT1.xdc`
- `legacy/RF_COMM/TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/async_clock_groups_impl.xdc`
- `legacy/RF_COMM/TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/target_ir_array_8lane_a_only_candidate.xdc`
- `legacy/RF_COMM/TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/target_ir_array_8lane_candidate.xdc`
- `legacy/RF_COMM/TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/target_ir_array_draft.xdc`
- `legacy/RF_COMM/tools/pin_static_diag.xdc`
- `legacy/RF_COMM/tools/tfdu_shutdown_8lane_candidate.xdc`
- `legacy/RF_COMM/tools/tfdu_shutdown_j10_j11.xdc`
