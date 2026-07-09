# Vivado Non-Hardware Build Summary

M5_VIVADO_NONHARDWARE_BUILD=FAIL
NO_HARDWARE_ACTIONS_EXECUTED=1
VIVADO_BATCH_TCL=scripts/vivado_nonhardware_build.tcl
VIVADO_REPORT_DIR=evidence/generated/vivado
VIVADO_PATH_ON_PATH=0
XILINX_VIVADO_2023_1_BIN=D:\Xilinx\Vivado\2023.1\bin
XILINX_VIVADO_2023_1_BAT_AVAILABLE=1
VIVADO_EXECUTABLE=D:\Xilinx\Vivado\2023.1\bin\vivado.bat
VIVADO_EXIT_CODE=4294967295
BITSTREAM_GENERATED_NO_HW=1
BITSTREAM_PATH=evidence/generated/vivado/ir_top_new_safe_idle.bit
BITSTREAM_SHA256=dafb203e199f49b4da5fb8f8b096051896136871cdd257bfd43d715394a2f16d
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
| safe_idle | `evidence/generated/vivado/ir_top_new_safe_idle.bit` | `dafb203e199f49b4da5fb8f8b096051896136871cdd257bfd43d715394a2f16d` | p4_auto_safe_idle_ila | 768 |
| tfdu_control_idle | `evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit` | `bdaa288a8b3d647bb0ea50408589bd9f7261d34bf8bbc8821200004d844479d6` | p4_auto_tfdu_control_idle_ila | 768 |
| raw_pulse | `evidence/generated/vivado/ir_top_new_raw_pulse.bit` | `aefef053458b875179fdc803c88c31e485fd5d92261e59e15036acfa4a6e0d09` | p4_auto_raw_pulse_ila | 768 |
| raw_lane_matrix | `evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit` | `ce09c11c93a33f88160c94642ba40b0dfe99f343635f1b7b13f7fb5158bdd3ae` | p4_auto_raw_lane_matrix_ila | 768 |
| protocol_lane0 | `evidence/generated/vivado/ir_top_new_protocol_lane0.bit` | `4d6d42b9b0993cbadc3c9270c0d2e30de368dc9a8b9c8538283c555f25fbbdf3` | p4_auto_protocol_lane0_ila | 768 |
| protocol_lane0_ack | `evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit` | `d002c3c9fce05e0a9b1df3e5984a714c97b60a43e086c02e3159d78fec8d8620` | p4_auto_protocol_lane0_ack_ila | 768 |
| protocol_lane1 | `evidence/generated/vivado/ir_top_new_protocol_lane1.bit` | `74b6f4d41bb90e9ae4e937aa55245d0dc2a442a43a777ccf36d491f14019cd71` | p4_auto_protocol_lane1_ila | 768 |
| protocol_lane1_ack | `evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit` | `5b6c8174499245cc56914b8c44c6b42330110e197e13a7f4534ef1313993a4ee` | p4_auto_protocol_lane1_ack_ila | 768 |
| protocol_two_lane_minimal | `evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit` | `5af431efe617323cd6851a8493db4d50191c0f799693d66b6e4c4c950033b723` | p4_auto_protocol_two_lane_minimal_ila | 768 |
| protocol_lane0_soak | `evidence/generated/vivado/ir_top_new_protocol_lane0_soak.bit` | `4e159f20a37c277f32a4cfe0ec0c2f42155d92012d2c9b9a99071f8428eb9e89` | p4_auto_protocol_lane0_soak_ila | 768 |
| protocol_two_lane_soak | `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit` | `32de20cf3c054f0e7ba909085e4f81c97f3bc74bac545b747583b8a0d33f2372` | p4_auto_protocol_two_lane_soak_ila | 768 |
| p6_local_transport | `evidence/generated/vivado/ir_top_new_p6_local_transport.bit` | `0117d41a2fc56e1d5d4c002e8d5e4ba573ad040ae1e7bdf6275869d21fbbbfc5` | p4_auto_p6_local_transport_ila | 768 |

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
- `protocol_lane0_soak` rc=4294967295

## Log Tail

```text
8 Bit    Registers := 2
	                7 Bit    Registers := 2
	                6 Bit    Registers := 1
	                5 Bit    Registers := 4
	                4 Bit    Registers := 15
	                2 Bit    Registers := 8
	                1 Bit    Registers := 47
+---Muxes :
	   2 Input  512 Bit        Muxes := 4
	   8 Input  512 Bit        Muxes := 2
	   2 Input  256 Bit        Muxes := 1
	   2 Input   56 Bit        Muxes := 3
	   2 Input   32 Bit        Muxes := 615
	   8 Input   32 Bit        Muxes := 2
	   2 Input   16 Bit        Muxes := 171
	   4 Input   16 Bit        Muxes := 2
	   8 Input   16 Bit        Muxes := 3
	   2 Input   14 Bit        Muxes := 1
	   2 Input    9 Bit        Muxes := 2
	   8 Input    9 Bit        Muxes := 2
	   2 Input    8 Bit        Muxes := 18
	  13 Input    8 Bit        Muxes := 1
	  24 Input    8 Bit        Muxes := 1
	   8 Input    8 Bit        Muxes := 2
	   2 Input    7 Bit        Muxes := 4
	   8 Input    7 Bit        Muxes := 2
	   2 Input    6 Bit        Muxes := 2
	   8 Input    6 Bit        Muxes := 1
	   2 Input    5 Bit        Muxes := 18
	   7 Input    4 Bit        Muxes := 2
	   2 Input    4 Bit        Muxes := 14
	   8 Input    4 Bit        Muxes := 1
	   5 Input    3 Bit        Muxes := 2
	   2 Input    3 Bit        Muxes := 4
	   8 Input    3 Bit        Muxes := 1
	   2 Input    2 Bit        Muxes := 19
	   8 Input    2 Bit        Muxes := 1
	   2 Input    1 Bit        Muxes := 221
	   4 Input    1 Bit        Muxes := 2
	   3 Input    1 Bit        Muxes := 2
	   8 Input    1 Bit        Muxes := 22
	  16 Input    1 Bit        Muxes := 1
---------------------------------------------------------------------------------
Finished RTL Component Statistics
---------------------------------------------------------------------------------
---------------------------------------------------------------------------------
Start Part Resource Summary
---------------------------------------------------------------------------------
Part Resources:
DSPs: 80 (col length:40)
BRAMs: 120 (col length: RAMB18 40 RAMB36 20)
---------------------------------------------------------------------------------
Finished Part Resource Summary
---------------------------------------------------------------------------------
---------------------------------------------------------------------------------
Start Cross Boundary and Area Optimization
---------------------------------------------------------------------------------
WARNING: [Synth 8-7080] Parallel synthesis criteria is not met
WARNING: [Synth 8-3917] design ir_top_new has port ir_mode_out_0[1] driven by constant 1
WARNING: [Synth 8-3917] design ir_top_new has port ir_mode_out_0[0] driven by constant 1
WARNING: [Synth 8-3917] design ir_top_new has port ir_sd_0[1] driven by constant 1
WARNING: [Synth 8-3917] design ir_top_new has port ir_sd_0[0] driven by constant 0
WARNING: [Synth 8-3917] design ir_top_new has port ir_tx_out_0[1] driven by constant 0
WARNING: [Synth 8-3917] design ir_top_new has port loop_mode_b0[1] driven by constant 1
WARNING: [Synth 8-3917] design ir_top_new has port loop_mode_b0[0] driven by constant 1
WARNING: [Synth 8-3917] design ir_top_new has port loop_sd_b0[1] driven by constant 1
WARNING: [Synth 8-3917] design ir_top_new has port loop_sd_b0[0] driven by constant 0
WARNING: [Synth 8-3917] design ir_top_new has port loop_tx_b0[1] driven by constant 0

===== safe_idle stderr =====

===== tfdu_control_idle stderr =====

===== raw_pulse stderr =====

===== raw_lane_matrix stderr =====

===== protocol_lane0 stderr =====

===== protocol_lane0_ack stderr =====

===== protocol_lane1 stderr =====

===== protocol_lane1_ack stderr =====

===== protocol_two_lane_minimal stderr =====

===== protocol_lane0_soak stderr =====
```
