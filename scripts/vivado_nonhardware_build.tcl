set root_dir [file normalize [lindex $argv 0]]
set stage "safe_idle"
if {[llength $argv] > 1} {
  set stage [lindex $argv 1]
}
if {$stage ni {"safe_idle" "tfdu_control_idle" "raw_pulse" "raw_lane_matrix" "protocol_lane0" "protocol_lane0_ack" "protocol_lane1" "protocol_lane1_ack" "protocol_two_lane_minimal" "protocol_lane0_soak" "protocol_two_lane_soak" "p6_local_transport"}} {
  error "Unsupported P4_AUTO Vivado build stage: $stage"
}
set out_dir [file normalize "$root_dir/evidence/generated/vivado"]
file mkdir $out_dir
set bitstream_file "$out_dir/ir_top_new_${stage}.bit"
set debug_ltx_file "$out_dir/p4_auto_${stage}_debug.ltx"
set dbg_log_file "$out_dir/p4_auto_${stage}_debug_instrumentation.txt"
set ila_name "p4_auto_${stage}_ila"

set part_name "xc7z010clg400-1"
set log_file [open "$out_dir/nonhardware_build_markers_${stage}.txt" "w"]
puts $log_file "VIVADO_NONHARDWARE_BUILD_STARTED=1"
puts $log_file "NO_HARDWARE_ACTIONS_EXECUTED=1"
puts $log_file "P4_AUTO_BUILD_STAGE=$stage"
close $log_file

create_project "rf_comm_nonhardware_${stage}" "$out_dir/project_${stage}" -part $part_name -force
set rtl_files [glob -nocomplain "$root_dir/rtl/*.sv"]
set rtl_debug_files [glob -nocomplain "$root_dir/rtl/debug/*.sv"]
set rtl_files [concat $rtl_files $rtl_debug_files]
add_files -fileset sources_1 $rtl_files
set_property top ir_top_new [current_fileset]
if {$stage eq "tfdu_control_idle"} {
  set_property verilog_define {P4_AUTO_TFDU_CONTROL_IDLE} [current_fileset]
} elseif {$stage eq "raw_pulse"} {
  set_property verilog_define {P4_AUTO_RAW_PULSE_L0} [current_fileset]
} elseif {$stage eq "raw_lane_matrix"} {
  set_property verilog_define {P4_AUTO_RAW_LANE_MATRIX} [current_fileset]
} elseif {$stage eq "protocol_lane0"} {
  set_property verilog_define {P4_AUTO_LANE0_FRAME_CRC} [current_fileset]
} elseif {$stage eq "protocol_lane0_ack"} {
  set_property verilog_define {P4_AUTO_LANE0_ACK_RETRY} [current_fileset]
} elseif {$stage eq "protocol_lane1"} {
  set_property verilog_define {P4_AUTO_LANE1_FRAME_CRC} [current_fileset]
} elseif {$stage eq "protocol_lane1_ack"} {
  set_property verilog_define {P4_AUTO_LANE1_ACK_RETRY} [current_fileset]
} elseif {$stage eq "protocol_two_lane_minimal"} {
  set_property verilog_define {P4_AUTO_TWO_LANE_MINIMAL} [current_fileset]
} elseif {$stage eq "protocol_lane0_soak"} {
  set_property verilog_define {P4_AUTO_LANE0_300S_SOAK} [current_fileset]
} elseif {$stage eq "protocol_two_lane_soak"} {
  set_property verilog_define {P4_AUTO_TWO_LANE_300S_SOAK} [current_fileset]
} elseif {$stage eq "p6_local_transport"} {
  set_property verilog_define {P6_LOCAL_TRANSPORT} [current_fileset]
}
read_xdc "$root_dir/constraints/active/PORT1.generated.xdc"
update_compile_order -fileset sources_1

synth_design -top ir_top_new -part $part_name
set dbg_log [open $dbg_log_file "w"]
puts $dbg_log "P4_AUTO_DEBUG_INSTRUMENTATION_BEGIN=1"
puts $dbg_log "NO_HARDWARE_ACTIONS_EXECUTED=1"
puts $dbg_log "P4_AUTO_BUILD_STAGE=$stage"
set debug_clock_nets [lsort -dictionary [get_nets -hier -quiet *p4_auto_cfgmclk*]]
set debug_status_nets [lsort -dictionary [get_nets -hier -quiet *p4_auto_status_words_flat*]]
puts $dbg_log "P4_AUTO_DEBUG_CLOCK_NET_COUNT=[llength $debug_clock_nets]"
puts $dbg_log "P4_AUTO_DEBUG_STATUS_NET_COUNT=[llength $debug_status_nets]"
if {[llength $debug_clock_nets] > 0 && [llength $debug_status_nets] > 0} {
  create_debug_core $ila_name ila
  set_property C_DATA_DEPTH 1024 [get_debug_cores $ila_name]
  set_property C_TRIGIN_EN false [get_debug_cores $ila_name]
  set_property C_TRIGOUT_EN false [get_debug_cores $ila_name]
  set_property C_ADV_TRIGGER false [get_debug_cores $ila_name]
  connect_debug_port ${ila_name}/clk [lindex $debug_clock_nets 0]
  if {[llength [get_debug_cores -quiet dbg_hub]] > 0} {
    connect_debug_port dbg_hub/clk [lindex $debug_clock_nets 0]
    set_property C_CLK_INPUT_FREQ_HZ 64000000 [get_debug_cores dbg_hub]
    puts $dbg_log "P4_AUTO_DBG_HUB_CLOCK=PASS"
    puts $dbg_log "P4_AUTO_DBG_HUB_CLK_INPUT_FREQ_HZ=64000000"
  } else {
    puts $dbg_log "P4_AUTO_DBG_HUB_CLOCK=SKIP_WITH_REASON"
  }
  set_property port_width [llength $debug_status_nets] [get_debug_ports ${ila_name}/probe0]
  connect_debug_port ${ila_name}/probe0 $debug_status_nets
  puts $dbg_log "P4_AUTO_ILA_CORE_INSERTION=PASS"
  puts $dbg_log "P4_AUTO_ILA_CORE_NAME=$ila_name"
  puts $dbg_log "P4_AUTO_ILA_PROBE0_WIDTH=[llength $debug_status_nets]"
} else {
  puts $dbg_log "P4_AUTO_ILA_CORE_INSERTION=SKIP_WITH_REASON"
  puts $dbg_log "P4_AUTO_ILA_SKIP_REASON=missing debug clock or status nets"
}
close $dbg_log
if {$stage eq "safe_idle"} {
  file copy -force $dbg_log_file "$out_dir/p4_auto_debug_instrumentation.txt"
}
write_checkpoint -force "$out_dir/post_synth_${stage}.dcp"
report_drc -file "$out_dir/post_synth_drc_${stage}.rpt"

opt_design
place_design
route_design
write_checkpoint -force "$out_dir/post_route_${stage}.dcp"
report_drc -file "$out_dir/post_route_drc_${stage}.rpt"
report_timing_summary -file "$out_dir/post_route_timing_summary_${stage}.rpt"
report_utilization -file "$out_dir/post_route_utilization_${stage}.rpt"
if {[llength [get_debug_cores -quiet $ila_name]] > 0} {
  write_debug_probes -force $debug_ltx_file
}
write_bitstream -force $bitstream_file

set log_file [open "$out_dir/nonhardware_build_markers_${stage}.txt" "a"]
puts $log_file "VIVADO_NONHARDWARE_BUILD_DONE=1"
puts $log_file "VIVADO_REPORT_DIR=$out_dir"
puts $log_file "P4_AUTO_BUILD_STAGE=$stage"
puts $log_file "P4_AUTO_STAGE_BITSTREAM=$bitstream_file"
puts $log_file "P4_AUTO_DEBUG_INSTRUMENTATION_LOG=$dbg_log_file"
if {[file exists $debug_ltx_file]} {
  puts $log_file "P4_AUTO_DEBUG_PROBES=$debug_ltx_file"
}
if {$stage eq "safe_idle"} {
  puts $log_file "VIVADO_SAFE_IDLE_BITSTREAM=$bitstream_file"
}
close $log_file
if {$stage eq "safe_idle"} {
  file copy -force "$out_dir/nonhardware_build_markers_${stage}.txt" "$out_dir/nonhardware_build_markers.txt"
}
