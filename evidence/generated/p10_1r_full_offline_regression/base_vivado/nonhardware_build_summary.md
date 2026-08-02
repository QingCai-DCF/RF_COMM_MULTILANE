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
BITSTREAM_SHA256=7668cf0122d29ccf426570c7822d723f2e06cdc5c2ad01d05485841a373bc1bb
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
| safe_idle | `evidence/generated/vivado/ir_top_new_safe_idle.bit` | `7668cf0122d29ccf426570c7822d723f2e06cdc5c2ad01d05485841a373bc1bb` | p4_auto_safe_idle_ila | 768 |
| tfdu_control_idle | `evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit` | `74bb364d9d828cd3bc5565bf32043ea4b66eaaf2cdbb70a1d8b1bf2fe52edcde` | p4_auto_tfdu_control_idle_ila | 768 |
| raw_pulse | `evidence/generated/vivado/ir_top_new_raw_pulse.bit` | `1e939612f3dec9a673a39bf7e4f7c04a255d3204289c528487b85585a3973b48` | p4_auto_raw_pulse_ila | 768 |
| raw_lane_matrix | `evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit` | `9bc8c5b01755748b46db5d2ab2f5990a75d790f8708f5d412f8eec2709e23834` | p4_auto_raw_lane_matrix_ila | 768 |
| protocol_lane0 | `evidence/generated/vivado/ir_top_new_protocol_lane0.bit` | `4d3490927659ef9e3e1bcfe3a33bec3b0614657b13076f372d027d488b8cb833` | p4_auto_protocol_lane0_ila | 768 |
| protocol_lane0_ack | `evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit` | `4860b64fa899715d53e315a3298ea4baa878c6aa3f5b3103ee5a0e5e4383bee9` | p4_auto_protocol_lane0_ack_ila | 768 |
| protocol_lane1 | `evidence/generated/vivado/ir_top_new_protocol_lane1.bit` | `656e1fe5b39ef7e19ab0de8f9c6402149481a61c346f77ea2cee03545126698d` | p4_auto_protocol_lane1_ila | 768 |
| protocol_lane1_ack | `evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit` | `5c3d8bdfafbe681adbf5b0e3a77ff70cbf9e8ba3c261de5e8830054c6cf421e9` | p4_auto_protocol_lane1_ack_ila | 768 |
| protocol_two_lane_minimal | `evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit` | `28423af226c0ca1451d1021176b2b80604645ed399e9fd379a532c36461e4d87` | p4_auto_protocol_two_lane_minimal_ila | 768 |
| protocol_lane0_soak | `evidence/generated/vivado/ir_top_new_protocol_lane0_soak.bit` | `eccb9c6c33d74add150cfab287ee9051c9ba27ef66e0b783f64dca091dda586d` | p4_auto_protocol_lane0_soak_ila | 768 |
| protocol_two_lane_soak | `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit` | `d9dfe040e6d3b6ed3fa291d6bb4422764f78993b6c2e53dfac64c7fe9d6ab408` | p4_auto_protocol_two_lane_soak_ila | 768 |
| p6_local_transport | `evidence/generated/vivado/ir_top_new_p6_local_transport.bit` | `3e873b3fccca19daa0aa03ec7bb1ed4b9111b57578d77366c041faa239b67f46` | p4_auto_p6_local_transport_ila | 768 |

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
NID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD1/ctl_reg_en_2[1], dbg_hub/inst/BSCANID.u_xsdbm_id/SWITCH_N_EXT_BSCAN.bscan_switch/m_bscan_capture[0], dbg_hub/inst/BSCANID.u_xsdbm_id/SWITCH_N_EXT_BSCAN.bscan_switch/m_bscan_drck[0], dbg_hub/inst/BSCANID.u_xsdbm_id/SWITCH_N_EXT_BSCAN.bscan_switch/m_bscan_runtest[0], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_WR/U_WR_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_wrfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/rstblk/ngwrdrst.grst.rd_rst_reg[0], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_RD/U_RD_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_rdfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/rstblk/ngwrdrst.grst.wr_rst_reg[2], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_WR/U_WR_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_wrfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/rstblk/ngwrdrst.grst.wr_rst_reg[2], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_RD/U_RD_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_rdfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.wr/gwhf.whf/overflow, dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_WR/U_WR_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_wrfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.wr/gwhf.whf/overflow, dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_RD/U_RD_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_rdfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.rd/gras.rsts/ram_empty_i... and (the first 15 of 26 listed).
WARNING: [DRC ZPS7-1] PS7 block required: The PS7 cell must be used in this Zynq design in order to enable correct default configuration.
INFO: [Vivado 12-3199] DRC finished with 0 Errors, 5 Warnings
INFO: [Vivado 12-3200] Please refer to the DRC report (report_drc) for more information.
INFO: [Designutils 20-2272] Running write_bitstream with 2 threads.
Loading data files...
Loading site data...
Loading route data...
Processing options...
Creating bitmap...
Creating bitstream...
Writing bitstream C:/Users/user/Documents/RF_COMM_MULTILANE_P10_1R/evidence/generated/vivado/ir_top_new_p6_local_transport.bit...
INFO: [Vivado 12-1842] Bitgen Completed Successfully.
INFO: [Project 1-1876] WebTalk data collection is mandatory when using a ULT device. To see the specific WebTalk data collected for your design, open the usage_statistics_webtalk.html or usage_statistics_webtalk.xml file in the implementation directory.
INFO: [Common 17-83] Releasing license: Implementation
9 Infos, 5 Warnings, 0 Critical Warnings and 0 Errors encountered.
write_bitstream completed successfully
write_bitstream: Time (s): cpu = 00:00:12 ; elapsed = 00:00:09 . Memory (MB): peak = 3740.949 ; gain = 225.055
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
INFO: [Common 17-206] Exiting Vivado at Sun Aug  2 12:40:45 2026...

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

===== protocol_two_lane_soak stderr =====

===== p6_local_transport stderr =====
```
