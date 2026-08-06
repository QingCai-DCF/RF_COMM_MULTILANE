# Vivado Non-Hardware Build Summary

M5_VIVADO_NONHARDWARE_BUILD=PASS
NO_HARDWARE_ACTIONS_EXECUTED=1
VIVADO_BATCH_TCL=scripts/vivado_nonhardware_build.tcl
VIVADO_REPORT_DIR=evidence/generated/vivado
VIVADO_PATH_ON_PATH=0
XILINX_VIVADO_2023_1_BIN=D:\Xilinx\Vivado\2023.1\bin
XILINX_VIVADO_2023_1_BAT_AVAILABLE=1
VIVADO_EXECUTABLE=D:\Xilinx\Vivado\2023.1\bin\vivado.bat
VIVADO_EXIT_CODE=0
BITSTREAM_GENERATED_NO_HW=1
BITSTREAM_PATH=evidence/generated/vivado/ir_top_new_safe_idle.bit
BITSTREAM_SHA256=8e16c093e943e6ee65c8d2f6465bcf0a438549e346e0f263954b5dd7f919fc2e
P4_AUTO_DEBUG_INSTRUMENTATION_LOG=evidence/generated/vivado/p4_auto_debug_instrumentation.txt
P4_AUTO_DEBUG_CLOCK_NET_COUNT=1
P4_AUTO_DEBUG_STATUS_NET_COUNT=768
P4_AUTO_ILA_CORE_INSERTION=PASS
P4_AUTO_ILA_CORE_NAME=p4_auto_safe_idle_ila
P4_AUTO_ILA_PROBE0_WIDTH=768
P4_AUTO_DEBUG_PROBES=evidence/generated/vivado/p4_auto_safe_idle_debug.ltx
P4_AUTO_DEBUG_PROBES_SHA256=1f5258d51a906547942b5f7260a691fd45ad31cd88734b9aeb26f2d626fce561

## P4_AUTO Stage Bitstreams

| Stage | Bitstream | SHA256 | ILA Core | Probe Width |
| --- | --- | --- | --- | --- |
| safe_idle | `evidence/generated/vivado/ir_top_new_safe_idle.bit` | `8e16c093e943e6ee65c8d2f6465bcf0a438549e346e0f263954b5dd7f919fc2e` | p4_auto_safe_idle_ila | 768 |
| tfdu_control_idle | `evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit` | `14b8bc75d79d4cde9b796ed0909d247f50f300f168b657170e858a75b9c33a92` | p4_auto_tfdu_control_idle_ila | 768 |
| raw_pulse | `evidence/generated/vivado/ir_top_new_raw_pulse.bit` | `d76efce16357e0b06e5fa078941390df9e1685291ef2e77609f084939ccaee64` | p4_auto_raw_pulse_ila | 768 |
| raw_lane_matrix | `evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit` | `1be61d4f9c039cf94fc2a56bf197b1f38e5f6c1b019e8a41205d458afdf836bb` | p4_auto_raw_lane_matrix_ila | 768 |
| protocol_lane0 | `evidence/generated/vivado/ir_top_new_protocol_lane0.bit` | `f25f1c4e3014d6bd33738034172001b9656fdb235ea5ee08ac32e1b16ac9e183` | p4_auto_protocol_lane0_ila | 768 |
| protocol_lane0_ack | `evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit` | `c70ecc85ec8592441a125bb71e1d30e286cd91261017de21efcc234901515cc5` | p4_auto_protocol_lane0_ack_ila | 768 |
| protocol_lane1 | `evidence/generated/vivado/ir_top_new_protocol_lane1.bit` | `d4b7618c2fac2517fbc379cd49d9ed66f296a9027f495d184e10ce7549e62b26` | p4_auto_protocol_lane1_ila | 768 |
| protocol_lane1_ack | `evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit` | `b1a26493d7bd48905695cede104d1f6952ac89f7351a1c9467c098cc4505c6a7` | p4_auto_protocol_lane1_ack_ila | 768 |
| protocol_two_lane_minimal | `evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit` | `6e725f5ffbb87f866be556418be4206597d61cbb734c46c1435f0b9cc5457dc3` | p4_auto_protocol_two_lane_minimal_ila | 768 |
| protocol_lane0_soak | `evidence/generated/vivado/ir_top_new_protocol_lane0_soak.bit` | `10d905482d321b3198981de27bc4abdb15894b4429e6cfa065933499017c6df2` | p4_auto_protocol_lane0_soak_ila | 768 |
| protocol_two_lane_soak | `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit` | `a9e26b52205546722b896254c8c0306cb135a00ee9e839de2d85c4e2745922ad` | p4_auto_protocol_two_lane_soak_ila | 768 |
| p6_local_transport | `evidence/generated/vivado/ir_top_new_p6_local_transport.bit` | `0047be442017192b574de94068c60b8470122993fda6bea3ac9ca9c7f88c10da` | p4_auto_p6_local_transport_ila | 768 |

## Stage Commands

- `safe_idle` rc=0
- `tfdu_control_idle` rc=0
- `raw_pulse` rc=0
- `raw_lane_matrix` rc=0
- `protocol_lane0` rc=0
- `protocol_lane0_ack` rc=0
- `protocol_lane1` rc=0
- `protocol_lane1_ack` rc=0
- `protocol_two_lane_minimal` rc=0
- `protocol_lane0_soak` rc=0
- `protocol_two_lane_soak` rc=0
- `p6_local_transport` rc=0

## Log Tail

```text
VIVADO_VERIFY_EXISTING=1
NO_HARDWARE_ACTIONS_EXECUTED=1
```
