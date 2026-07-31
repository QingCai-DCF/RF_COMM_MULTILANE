# Vivado Non-Hardware Build Summary

M5_VIVADO_NONHARDWARE_BUILD=FAIL
NO_HARDWARE_ACTIONS_EXECUTED=1
VIVADO_BATCH_TCL=scripts/vivado_nonhardware_build.tcl
VIVADO_REPORT_DIR=evidence/generated/vivado
VIVADO_PATH_ON_PATH=0
XILINX_VIVADO_2023_1_BIN=D:\Xilinx\Vivado\2023.1\bin
XILINX_VIVADO_2023_1_BAT_AVAILABLE=1
VIVADO_EXECUTABLE=D:\Xilinx\Vivado\2023.1\bin\vivado.bat
VIVADO_EXIT_CODE=1
BITSTREAM_GENERATED_NO_HW=1
BITSTREAM_PATH=evidence/generated/vivado/ir_top_new_safe_idle.bit
BITSTREAM_SHA256=79e52fd177acdbdff704730f75ef08da07a18d2e0c56a50b3c6784b0460d569a
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
| safe_idle | `evidence/generated/vivado/ir_top_new_safe_idle.bit` | `79e52fd177acdbdff704730f75ef08da07a18d2e0c56a50b3c6784b0460d569a` | p4_auto_safe_idle_ila | 768 |

## Stage Commands

- `safe_idle` rc=0
- `tfdu_control_idle` rc=1

## Log Tail

```text
inary archive.
Writing XDEF routing.
Writing XDEF routing logical nets.
Writing XDEF routing special nets.
Write XDEF Complete: Time (s): cpu = 00:00:00 ; elapsed = 00:00:00.029 . Memory (MB): peak = 2366.496 ; gain = 0.000
INFO: [Common 17-1381] The checkpoint 'C:/Users/user/Documents/RF_COMM_P10_1_LED_GATE_canonical_p0_p8b_offline_regression_0wjlfx00/evidence/generated/vivado/post_synth_tfdu_control_idle.dcp' has been generated.
# report_drc -file "$out_dir/post_synth_drc_${stage}.rpt"
Command: report_drc -file C:/Users/user/Documents/RF_COMM_P10_1_LED_GATE_canonical_p0_p8b_offline_regression_0wjlfx00/evidence/generated/vivado/post_synth_drc_tfdu_control_idle.rpt
INFO: [IP_Flow 19-234] Refreshing IP repositories
INFO: [IP_Flow 19-1704] No user IP repositories specified
INFO: [IP_Flow 19-2313] Loaded Vivado IP repository 'D:/Xilinx/Vivado/2023.1/data/ip'.
INFO: [DRC 23-27] Running DRC with 2 threads
INFO: [Vivado_Tcl 2-168] The results of DRC are in file C:/Users/user/Documents/RF_COMM_P10_1_LED_GATE_canonical_p0_p8b_offline_regression_0wjlfx00/evidence/generated/vivado/post_synth_drc_tfdu_control_idle.rpt.
report_drc completed successfully
# opt_design
Command: opt_design
Attempting to get a license for feature 'Implementation' and/or device 'xc7z010'
INFO: [Common 17-349] Got license for feature 'Implementation' and/or device 'xc7z010'
Running DRC as a precondition to command opt_design

Starting DRC Task
INFO: [DRC 23-27] Running DRC with 2 threads
INFO: [Project 1-461] DRC finished with 0 Errors
INFO: [Project 1-462] Please refer to the DRC report (report_drc) for more information.

Time (s): cpu = 00:00:01 ; elapsed = 00:00:00.347 . Memory (MB): peak = 2366.496 ; gain = 0.000

Starting Cache Timing Information Task
INFO: [Timing 38-35] Done setting XDC timing constraints.
Ending Cache Timing Information Task | Checksum: 2456ef6f2

Time (s): cpu = 00:00:01 ; elapsed = 00:00:00.938 . Memory (MB): peak = 2597.426 ; gain = 230.930

Starting Logic Optimization Task

Phase 1 Generate And Synthesize Debug Cores
INFO: [Chipscope 16-329] Generating Script for core instance : dbg_hub
INFO: [IP_Flow 19-3806] Processing IP xilinx.com:ip:xsdbm:3.0 for cell dbg_hub_CV.
INFO: [Chipscope 16-329] Generating Script for core instance : p4_auto_tfdu_control_idle_ila
INFO: [IP_Flow 19-3806] Processing IP xilinx.com:ip:ila:6.2 for cell p4_auto_tfdu_control_idle_ila_CV.
The following Error logs belongs to p4_auto_tfdu_control_idle_ila
ERROR: [Common 17-680] Path length exceeds 260-Byte maximum allowed by Windows: c:/Users/user/Documents/RF_COMM_P10_1_LED_GATE_canonical_p0_p8b_offline_regression_0wjlfx00/.Xil/Vivado-22376-DESKTOP-PU0AECA/dc_drv.0/dc/prj_ip.runs/p4_auto_tfdu_control_idle_ila_synth_1/c:/Users/user/Documents/RF_COMM_P10_1_LED_GATE_canonical_p0_p8b_offline_regression_0wjlfx00/.Xil/Vivado-22376-DESKTOP-PU0AECA/dc_drv.0/dc/prj_ip.runs/p4_auto_tfdu_control_idle_ila_synth_1/.Xil/Vivado-42852-DESKTOP-PU0AECA/realtime\p4_auto_tfdu_control_idle_ila.tcl
Phase 1 Generate And Synthesize Debug Cores | Checksum: 2456ef6f2

Time (s): cpu = 00:00:00 ; elapsed = 00:00:49 . Memory (MB): peak = 2937.953 ; gain = 0.000
INFO: [Common 17-83] Releasing license: Implementation
10 Infos, 0 Warnings, 0 Critical Warnings and 5 Errors encountered.
opt_design failed
INFO: [Common 17-206] Exiting Vivado at Fri Jul 31 20:27:54 2026...

===== safe_idle stderr =====

===== tfdu_control_idle stderr =====
ERROR: [Vivado 12-13638] Failed runs(s) : 'p4_auto_tfdu_control_idle_ila_synth_1'
ERROR: [IP_Flow 19-3805] Failed to generate and synthesize debug IPs.
 ERROR: [Common 17-39] 'wait_on_runs' failed due to earlier errors.
ERROR: [Chipscope 16-330] Synthesis of Debug Cores has failed
ERROR: [Chipscope 16-578] Check "c:/Users/user/Documents/RF_COMM_P10_1_LED_GATE_canonical_p0_p8b_offline_regression_0wjlfx00/.Xil/Vivado-22376-DESKTOP-PU0AECA/dc_drv.0/vivado.log" file for more details.
ERROR: [Chipscope 16-338] Implementing debug Cores failed due to earlier errors
```
