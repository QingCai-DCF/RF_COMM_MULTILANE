set root_dir [file normalize [lindex $argv 0]]
set out_dir [file normalize [lindex $argv 1]]
set part xc7z010clg400-1
file mkdir $out_dir

create_project p9_post_synth_core "$out_dir/project" -part $part -force
set_property target_language Verilog [current_project]
set rtl_sources [list \
  "$root_dir/rtl/generated/tfdu_safety_config.svh" \
  "$root_dir/rtl/generated/ir_register_map_defs.svh" \
  "$root_dir/rtl/ir_seq_math_pkg.sv" \
  "$root_dir/rtl/ir_health_weighted_scheduler.sv" \
  "$root_dir/rtl/ir_selective_repeat_tx.sv" \
  "$root_dir/rtl/ir_selective_repeat_rx.sv" \
  "$root_dir/rtl/ir_ack_aggregator.sv" \
  "$root_dir/rtl/ir_data_plane_top.sv" \
  "$root_dir/rtl/ir_tfdu_exact_duty_accountant.sv" \
  "$root_dir/rtl/ir_tfdu_physical_module_safety.sv" \
  "$root_dir/rtl/tfdu_lane_phy.sv" \
  "$root_dir/rtl/ir_4ppm_codec.sv" \
  "$root_dir/rtl/p9_rate_4ppm_rx.sv" \
  "$root_dir/rtl/p9_4ppm_frame_tx.sv" \
  "$root_dir/rtl/p9_4ppm_frame_rx.sv" \
  "$root_dir/rtl/p9_optical_transport_core.sv" \
]
add_files -fileset sources_1 $rtl_sources
set_property include_dirs [list "$root_dir/rtl"] [get_filesets sources_1]
set_property top p9_optical_transport_core [current_fileset]
update_compile_order -fileset sources_1

synth_design -mode out_of_context -top p9_optical_transport_core -part $part \
  -generic CLK_HZ=64000000 -generic WINDOW_SIZE=32 -generic SACK_BITS=32 \
  -generic MAX_PAYLOAD_BYTES=247 -generic STORE_ADDR_WIDTH=13 \
  -generic RTO_CYCLES=100000
create_clock -name protocol_clk -period 15.625 [get_ports clk]
write_checkpoint -force "$out_dir/post_synth_p9_core.dcp"
write_verilog -force -mode funcsim "$out_dir/post_synth_p9_core_funcsim.v"
report_timing_summary -delay_type min_max -report_unconstrained \
  -check_timing_verbose -file "$out_dir/post_synth_timing_summary_p9_core.rpt"
report_utilization -hierarchical -file "$out_dir/post_synth_utilization_p9_core.rpt"
report_drc -file "$out_dir/post_synth_drc_p9_core.rpt"

set drc_critical 0
set drc_error 0
foreach violation [get_drc_violations -quiet] {
  set severity [get_property SEVERITY $violation]
  if {[string match -nocase "*critical*" $severity]} { incr drc_critical }
  if {[string equal -nocase $severity "error"]} { incr drc_error }
}
set reqp_1839 [llength [get_drc_violations -quiet REQP-1839*]]
set marker [open "$out_dir/p9_post_synth_build_markers.txt" w]
puts $marker "P9_POST_SYNTH_BUILD=PASS"
puts $marker "P9_POST_SYNTH_PART=[get_property PART [current_project]]"
puts $marker "P9_POST_SYNTH_TOP=p9_optical_transport_core"
puts $marker "P9_POST_SYNTH_CLOCK_NS=15.625"
puts $marker "P9_POST_SYNTH_DRC_CRITICAL_COUNT=$drc_critical"
puts $marker "P9_POST_SYNTH_DRC_ERROR_COUNT=$drc_error"
puts $marker "P9_POST_SYNTH_REQP_1839_COUNT=$reqp_1839"
close $marker
if {$drc_critical != 0 || $drc_error != 0 || $reqp_1839 != 0} {
  error "P9 post-synth signoff failed: DRC_CRITICAL=$drc_critical DRC_ERROR=$drc_error REQP_1839=$reqp_1839"
}
puts "P9_POST_SYNTH_BUILD=PASS"
