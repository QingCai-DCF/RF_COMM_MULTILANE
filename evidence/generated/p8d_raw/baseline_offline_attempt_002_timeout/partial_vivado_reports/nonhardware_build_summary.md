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
BITSTREAM_SHA256=e54d8c97a76f631a0a43cb608acd9e0b8d7c71428e7bf3437bf802efec009467
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
| safe_idle | `evidence/generated/vivado/ir_top_new_safe_idle.bit` | `e54d8c97a76f631a0a43cb608acd9e0b8d7c71428e7bf3437bf802efec009467` | p4_auto_safe_idle_ila | 768 |
| tfdu_control_idle | `evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit` | `654ef3ec5e9559310f7701d375b77addd7cfd4b835cd2f740a4eb84931461b3a` | p4_auto_tfdu_control_idle_ila | 768 |
| raw_pulse | `evidence/generated/vivado/ir_top_new_raw_pulse.bit` | `d6d9d93587b184215e5acec2fb6301b67eb4aca4ae85efce74b7cd233788096e` | p4_auto_raw_pulse_ila | 768 |
| raw_lane_matrix | `evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit` | `b1147e74eff01cbc1b5ffd420a4916487fa26b22478acabdf6e370dba3083e37` | p4_auto_raw_lane_matrix_ila | 768 |
| protocol_lane0 | `evidence/generated/vivado/ir_top_new_protocol_lane0.bit` | `e3d6ae82d3a70717634a879bde02dadfd3684955ced1f15dcb4797c8411e92d5` | p4_auto_protocol_lane0_ila | 768 |
| protocol_lane0_ack | `evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit` | `acc3525a80b0ef9998e913d45f5d2290c3637906abf1144a5eea4a1dfcb7c4d4` | p4_auto_protocol_lane0_ack_ila | 768 |
| protocol_lane1 | `evidence/generated/vivado/ir_top_new_protocol_lane1.bit` | `86e44d5eacbcb7556e6a57d54a7af47de7b39587ff466c798859a67531680c2b` | p4_auto_protocol_lane1_ila | 768 |
| protocol_lane1_ack | `evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit` | `e3f47fc5161feaeed5f354a3d961a136ce71019c9f9520e37c27b7b6a2862595` | p4_auto_protocol_lane1_ack_ila | 768 |
| protocol_two_lane_minimal | `evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit` | `280b37f7065af34b53bf2ada660464b95dccb0fea6a76121a9e240e846f9c4ee` | p4_auto_protocol_two_lane_minimal_ila | 768 |
| protocol_lane0_soak | `evidence/generated/vivado/ir_top_new_protocol_lane0_soak.bit` | `7b15de61b59ce9887d38034c968b24ee0030536ddf0dd1bfc657ca65654fccc7` | p4_auto_protocol_lane0_soak_ila | 768 |
| protocol_two_lane_soak | `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit` | `b90da8ba60830c245062bebd05e29c8b31159a350fcbc059db1deaffa617b6a6` | p4_auto_protocol_two_lane_soak_ila | 768 |
| p6_local_transport | `evidence/generated/vivado/ir_top_new_p6_local_transport.bit` | `5a15a047d5916cf2b574277ba28eb13ba5940f3e0df4f6c0612d704cc5ef7f13` | p4_auto_p6_local_transport_ila | 768 |

## Stage Commands

- `safe_idle` rc=0
- `tfdu_control_idle` rc=0
- `raw_pulse` rc=0
- `raw_lane_matrix` rc=0
- `protocol_lane0` rc=4294967295

## Log Tail

```text
bug_status_nets] > 0} {
#   create_debug_core $ila_name ila
#   set_property C_DATA_DEPTH 1024 [get_debug_cores $ila_name]
#   set_property C_TRIGIN_EN false [get_debug_cores $ila_name]
#   set_property C_TRIGOUT_EN false [get_debug_cores $ila_name]
#   set_property C_ADV_TRIGGER false [get_debug_cores $ila_name]
#   connect_debug_port ${ila_name}/clk [lindex $debug_clock_nets 0]
#   if {[llength [get_debug_cores -quiet dbg_hub]] > 0} {
#     connect_debug_port dbg_hub/clk [lindex $debug_clock_nets 0]
#     set_property C_CLK_INPUT_FREQ_HZ 64000000 [get_debug_cores dbg_hub]
#     puts $dbg_log "P4_AUTO_DBG_HUB_CLOCK=PASS"
#     puts $dbg_log "P4_AUTO_DBG_HUB_CLK_INPUT_FREQ_HZ=64000000"
#   } else {
#     puts $dbg_log "P4_AUTO_DBG_HUB_CLOCK=SKIP_WITH_REASON"
#   }
#   set_property port_width [llength $debug_status_nets] [get_debug_ports ${ila_name}/probe0]
#   connect_debug_port ${ila_name}/probe0 $debug_status_nets
#   puts $dbg_log "P4_AUTO_ILA_CORE_INSERTION=PASS"
#   puts $dbg_log "P4_AUTO_ILA_CORE_NAME=$ila_name"
#   puts $dbg_log "P4_AUTO_ILA_PROBE0_WIDTH=[llength $debug_status_nets]"
# } else {
#   puts $dbg_log "P4_AUTO_ILA_CORE_INSERTION=SKIP_WITH_REASON"
#   puts $dbg_log "P4_AUTO_ILA_SKIP_REASON=missing debug clock or status nets"
# }
# close $dbg_log
# if {$stage eq "safe_idle"} {
#   file copy -force $dbg_log_file "$out_dir/p4_auto_debug_instrumentation.txt"
# }
# write_checkpoint -force "$out_dir/post_synth_${stage}.dcp"
INFO: [Timing 38-480] Writing timing data to binary archive.
Writing XDEF routing.
Writing XDEF routing logical nets.
Writing XDEF routing special nets.
Write XDEF Complete: Time (s): cpu = 00:00:00 ; elapsed = 00:00:00.035 . Memory (MB): peak = 3204.027 ; gain = 0.000
INFO: [Common 17-1381] The checkpoint 'C:/Users/user/.codex/worktrees/3765/RF_COMM_MULTILANE/evidence/generated/vivado/post_synth_protocol_lane0.dcp' has been generated.
# report_drc -file "$out_dir/post_synth_drc_${stage}.rpt"
Command: report_drc -file C:/Users/user/.codex/worktrees/3765/RF_COMM_MULTILANE/evidence/generated/vivado/post_synth_drc_protocol_lane0.rpt
INFO: [IP_Flow 19-234] Refreshing IP repositories
INFO: [IP_Flow 19-1704] No user IP repositories specified
INFO: [IP_Flow 19-2313] Loaded Vivado IP repository 'D:/Xilinx/Vivado/2023.1/data/ip'.
INFO: [DRC 23-27] Running DRC with 2 threads
INFO: [Vivado_Tcl 2-168] The results of DRC are in file C:/Users/user/.codex/worktrees/3765/RF_COMM_MULTILANE/evidence/generated/vivado/post_synth_drc_protocol_lane0.rpt.
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

Time (s): cpu = 00:00:00 ; elapsed = 00:00:00.432 . Memory (MB): peak = 3204.027 ; gain = 0.000

Starting Cache Timing Information Task
INFO: [Timing 38-35] Done setting XDC timing constraints.
Ending Cache Timing Information Task | Checksum: 2542fc9a6

Time (s): cpu = 00:00:02 ; elapsed = 00:00:01 . Memory (MB): peak = 3204.027 ; gain = 0.000

Starting Logic Optimization Task

Phase 1 Generate And Synthesize Debug Cores
INFO: [Chipscope 16-329] Generating Script for core instance : dbg_hub
INFO: [IP_Flow 19-3806] Processing IP xilinx.com:ip:xsdbm:3.0 for cell dbg_hub_CV.
INFO: [Chipscope 16-329] Generating Script for core instance : p4_auto_protocol_lane0_ila
INFO: [IP_Flow 19-3806] Processing IP xilinx.com:ip:ila:6.2 for cell p4_auto_protocol_lane0_ila_CV.

===== safe_idle stderr =====

===== tfdu_control_idle stderr =====

===== raw_pulse stderr =====

===== raw_lane_matrix stderr =====

===== protocol_lane0 stderr =====
ERROR: [Common 17-180] Spawn failed: No such file or directory
```
