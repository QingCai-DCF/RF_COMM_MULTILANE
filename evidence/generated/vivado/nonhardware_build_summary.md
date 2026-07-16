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
BITSTREAM_SHA256=70a78590081b00e1ebfa9650ff2b7c476bfbaa8bba93a855d003cfa1a4f70788
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
| safe_idle | `evidence/generated/vivado/ir_top_new_safe_idle.bit` | `70a78590081b00e1ebfa9650ff2b7c476bfbaa8bba93a855d003cfa1a4f70788` | p4_auto_safe_idle_ila | 768 |
| tfdu_control_idle | `evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit` | `ee79253175043a7bd4e90da89da4db100db67a6b5447657dccc8d8613ecd0c0e` | p4_auto_tfdu_control_idle_ila | 768 |
| raw_pulse | `evidence/generated/vivado/ir_top_new_raw_pulse.bit` | `fe4bade0a35d89c82154834e840e92445a5abd99e96f4d3e5bf9fa9061b95262` | p4_auto_raw_pulse_ila | 768 |
| raw_lane_matrix | `evidence/generated/vivado/ir_top_new_raw_lane_matrix.bit` | `027fc0bfd6a6705ba187e33dc17cdda988476e98cb4317a6ac92d1446e90171b` | p4_auto_raw_lane_matrix_ila | 768 |
| protocol_lane0 | `evidence/generated/vivado/ir_top_new_protocol_lane0.bit` | `1f59a35e8f377fe42821b6b81d2bfe788c7ce6e96fda14b67a7614803c75a361` | p4_auto_protocol_lane0_ila | 768 |
| protocol_lane0_ack | `evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit` | `384fe17b2b708f1a28a7c3fadd5f2943c01656f7d44302759132e5f0c32bb8ce` | p4_auto_protocol_lane0_ack_ila | 768 |
| protocol_lane1 | `evidence/generated/vivado/ir_top_new_protocol_lane1.bit` | `4dd73f2978c8b1bcd3aecb45be5a72180a1ed4c90b0bef796180bfef35777097` | p4_auto_protocol_lane1_ila | 768 |
| protocol_lane1_ack | `evidence/generated/vivado/ir_top_new_protocol_lane1_ack.bit` | `0557834d54afc22c64aa152e36195878773442cc21d4c0f033cf4e435cd4d90b` | p4_auto_protocol_lane1_ack_ila | 768 |
| protocol_two_lane_minimal | `evidence/generated/vivado/ir_top_new_protocol_two_lane_minimal.bit` | `dc8325df7ffc1fe447ac56fb1e98c29c65e98210b6e89ce868d01416454e0c2d` | p4_auto_protocol_two_lane_minimal_ila | 768 |
| protocol_lane0_soak | `evidence/generated/vivado/ir_top_new_protocol_lane0_soak.bit` | `79ef8b0847c2c18ff037c56177a0c2cd48527fe58cae2c03c90442ed5d11001f` | p4_auto_protocol_lane0_soak_ila | 768 |
| protocol_two_lane_soak | `evidence/generated/vivado/ir_top_new_protocol_two_lane_soak.bit` | `e52e2121c9d676df4bccb7572e214e66914b9cee64bdd7a4762be79967c6f529` | p4_auto_protocol_two_lane_soak_ila | 768 |
| p6_local_transport | `evidence/generated/vivado/ir_top_new_p6_local_transport.bit` | `1924ab076b354a40ca197167603353cef664123e8c9eb67c0eea1e2f58571e4d` | p4_auto_p6_local_transport_ila | 768 |

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
u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD1/ctl_reg_en_2[1], dbg_hub/inst/BSCANID.u_xsdbm_id/SWITCH_N_EXT_BSCAN.bscan_switch/m_bscan_capture[0], dbg_hub/inst/BSCANID.u_xsdbm_id/SWITCH_N_EXT_BSCAN.bscan_switch/m_bscan_drck[0], dbg_hub/inst/BSCANID.u_xsdbm_id/SWITCH_N_EXT_BSCAN.bscan_switch/m_bscan_runtest[0], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_WR/U_WR_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_wrfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/rstblk/ngwrdrst.grst.rd_rst_reg[0], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_RD/U_RD_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_rdfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/rstblk/ngwrdrst.grst.wr_rst_reg[2], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_WR/U_WR_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_wrfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/rstblk/ngwrdrst.grst.wr_rst_reg[2], dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_RD/U_RD_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_rdfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.wr/gwhf.whf/overflow, dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_WR/U_WR_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_wrfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.wr/gwhf.whf/overflow, dbg_hub/inst/BSCANID.u_xsdbm_id/CORE_XSDB.UUT_MASTER/U_ICON_INTERFACE/U_CMD6_RD/U_RD_FIFO/SUBCORE_FIFO.xsdbm_v3_0_0_rdfifo_inst/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.rd/gras.rsts/ram_empty_i... and (the first 15 of 26 listed).
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
Writing bitstream D:/CodexWorktrees/p7formal_d3eb4a6/RF_COMM_MULTILANE/evidence/generated/vivado/ir_top_new_p6_local_transport.bit...
INFO: [Vivado 12-1842] Bitgen Completed Successfully.
INFO: [Project 1-1876] WebTalk data collection is mandatory when using a ULT device. To see the specific WebTalk data collected for your design, open the usage_statistics_webtalk.html or usage_statistics_webtalk.xml file in the implementation directory.
INFO: [Common 17-83] Releasing license: Implementation
9 Infos, 5 Warnings, 0 Critical Warnings and 0 Errors encountered.
write_bitstream completed successfully
write_bitstream: Time (s): cpu = 00:00:11 ; elapsed = 00:00:09 . Memory (MB): peak = 3754.414 ; gain = 217.500
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
INFO: [Common 17-206] Exiting Vivado at Fri Jul 17 04:08:13 2026...

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
