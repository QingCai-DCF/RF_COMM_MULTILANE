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
BITSTREAM_SHA256=b589918e77bb6bebf9387a4e146754fc7054117e938e3a9caa2a7327df107b99
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
| safe_idle | `evidence/generated/vivado/ir_top_new_safe_idle.bit` | `b589918e77bb6bebf9387a4e146754fc7054117e938e3a9caa2a7327df107b99` | p4_auto_safe_idle_ila | 768 |
| tfdu_control_idle | `evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit` | `df07cecd1ce749642a9fa6841fdc67051205df79876e4849497b8335c689fb87` | p4_auto_tfdu_control_idle_ila | 768 |
| raw_pulse | `evidence/generated/vivado/ir_top_new_raw_pulse.bit` | `66e102f95982610c5d559809e928820909b69e3343c2720305ae4118e34316bd` | p4_auto_raw_pulse_ila | 768 |
| raw_lane_matrix | `evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit` | `537c1b20a6ddf97117f09b961183daeb60c70eab417888e1f5687a73e33c0140` | p4_auto_raw_lane_matrix_ila | 768 |
| protocol_lane0 | `evidence/generated/vivado/ir_top_new_protocol_lane0.bit` | `40e230e08a67bed86a6879e3acd4dfcab181514b0314225db89aaf43c4c0eb1c` | p4_auto_protocol_lane0_ila | 768 |
| protocol_lane0_ack | `evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit` | `dbf685f459fa01d7a781ad12a71cfa519ad4ab138d315458f958eb53c470226e` | p4_auto_protocol_lane0_ack_ila | 768 |
| protocol_lane1 | `evidence/generated/vivado/ir_top_new_protocol_lane1.bit` | `a2d5afbfb9c40ec154d8cd69199193c3cf86243ca8feb4b1559c151e63b99ee4` | p4_auto_protocol_lane1_ila | 768 |
| protocol_lane1_ack | `evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit` | `daf43f501412b8ed2b8ee0ad804ebd394be5e7b25c65d5dd07f283ac677e0846` | p4_auto_protocol_lane1_ack_ila | 768 |
| protocol_two_lane_minimal | `evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit` | `9301189603a8f30fe45ccdf61afb314b1630c691b853fd91794c7fd3c811e628` | p4_auto_protocol_two_lane_minimal_ila | 768 |
| protocol_lane0_soak | `evidence/generated/vivado/ir_top_new_protocol_lane0_soak.bit` | `c48f6bec8814225f500441787c2178f2fcc34f5bdbae7ffc411142ddcc6779ed` | p4_auto_protocol_lane0_soak_ila | 768 |
| protocol_two_lane_soak | `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit` | `d375097e62f6cfd7c5205a17255d68d416d1aeb77487902417fe617439360e3f` | p4_auto_protocol_two_lane_soak_ila | 768 |
| p6_local_transport | `evidence/generated/vivado/ir_top_new_p6_local_transport.bit` | `77928d9ee5c0a12d3666ef1b2840f9ecacc2137d9461c2599a33213375f3c0db` | p4_auto_p6_local_transport_ila | 768 |

## Stage Commands

- `safe_idle` rc=0
- `tfdu_control_idle` rc=0
- `raw_pulse` rc=0
- `raw_lane_matrix` rc=0
- `protocol_lane0` rc=0
- `protocol_lane0_ack` rc=1

## Log Tail

```text
rrors, 5 Warnings
INFO: [Vivado 12-3200] Please refer to the DRC report (report_drc) for more information.
INFO: [Designutils 20-2272] Running write_bitstream with 2 threads.
Loading data files...
Loading site data...
Loading route data...
Processing options...
Creating bitmap...
Creating bitstream...
Writing bitstream C:/Users/user/Documents/RF_COMM_MULTILANE_P9/evidence/generated/vivado/ir_top_new_protocol_lane0.bit...
INFO: [Vivado 12-1842] Bitgen Completed Successfully.
INFO: [Project 1-1876] WebTalk data collection is mandatory when using a ULT device. To see the specific WebTalk data collected for your design, open the usage_statistics_webtalk.html or usage_statistics_webtalk.xml file in the implementation directory.
INFO: [Common 17-83] Releasing license: Implementation
9 Infos, 5 Warnings, 0 Critical Warnings and 0 Errors encountered.
write_bitstream completed successfully
write_bitstream: Time (s): cpu = 00:00:10 ; elapsed = 00:00:08 . Memory (MB): peak = 3547.859 ; gain = 349.516
# set log_file [open "$out_dir/nonhardware_build_markers_${stage}.txt" "a"]
# puts $log_file "VIVADO_NONHARDWARE_BUILD_DONE=1"
# puts $log_file "VIVADO_REPORT_DIR=$out_dir"
# puts $log_file "P4_AUTO_BUILD_STAGE=$stage"
# puts $log_file "P4_AUTO_STAGE_BITSTREAM=$bitstream_file"
# puts $log_file "P4_AUTO_DEBUG_INSTRUMENTATION_LOG=$dbg_log_file"
# if {[file exists $debug_ltx_file]} {
#   puts $log_file "P4_AUTO_DEBUG_PROBES=$debug_ltx_file"
# }
# if {$stage eq "safe_idle"} {
#   puts $log_file "VIVADO_SAFE_IDLE_BITSTREAM=$bitstream_file"
# }
# close $log_file
# if {$stage eq "safe_idle"} {
#   file copy -force "$out_dir/nonhardware_build_markers_${stage}.txt" "$out_dir/nonhardware_build_markers.txt"
# }
INFO: [Common 17-206] Exiting Vivado at Wed Jul 29 23:05:50 2026...

===== protocol_lane0_ack stdout =====

****** Vivado v2023.1 (64-bit)
  **** SW Build 3865809 on Sun May  7 15:05:29 MDT 2023
  **** IP Build 3864474 on Sun May  7 20:36:21 MDT 2023
  **** SharedData Build 3865790 on Sun May 07 13:33:03 MDT 2023
    ** Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
    ** Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.

Sourcing tcl script 'D:/Xilinx/Vivado/2023.1/scripts/Vivado_init.tcl'
vivado-mcp server ready on port 10000
source scripts/vivado_nonhardware_build.tcl
# set root_dir [file normalize [lindex $argv 0]]
# set stage "safe_idle"
# if {[llength $argv] > 1} {
#   set stage [lindex $argv 1]
# }
# if {$stage ni {"safe_idle" "tfdu_control_idle" "raw_pulse" "raw_lane_matrix" "protocol_lane0" "protocol_lane0_ack" "protocol_lane1" "protocol_lane1_ack" "protocol_two_lane_minimal" "protocol_lane0_soak" "protocol_two_lane_soak" "p6_local_transport"}} {
#   error "Unsupported P4_AUTO Vivado build stage: $stage"
# }
# set out_dir [file normalize "$root_dir/evidence/generated/vivado"]
# file mkdir $out_dir
# set bitstream_file "$out_dir/ir_top_new_${stage}.bit"
# set debug_ltx_file "$out_dir/p4_auto_${stage}_debug.ltx"
# set dbg_log_file "$out_dir/p4_auto_${stage}_debug_instrumentation.txt"
# set ila_name "p4_auto_${stage}_ila"
# set part_name "xc7z010clg400-1"
# set log_file [open "$out_dir/nonhardware_build_markers_${stage}.txt" "w"]
# puts $log_file "VIVADO_NONHARDWARE_BUILD_STARTED=1"
# puts $log_file "NO_HARDWARE_ACTIONS_EXECUTED=1"
# puts $log_file "P4_AUTO_BUILD_STAGE=$stage"
# close $log_file
# create_project "rf_comm_nonhardware_${stage}" "$out_dir/project_${stage}" -part $part_name -force
INFO: [Common 17-206] Exiting Vivado at Wed Jul 29 23:05:54 2026...

===== safe_idle stderr =====

===== tfdu_control_idle stderr =====

===== raw_pulse stderr =====

===== raw_lane_matrix stderr =====

===== protocol_lane0 stderr =====

===== protocol_lane0_ack stderr =====
ERROR: [Project 1-161] Failed to remove the directory 'C:/Users/user/Documents/RF_COMM_MULTILANE_P9/evidence/generated/vivado/project_protocol_lane0_ack/rf_comm_nonhardware_protocol_lane0_ack.cache'. The directory might be in use by some other process.
```
