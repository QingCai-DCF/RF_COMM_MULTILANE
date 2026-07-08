set repo_root [file normalize [file join [file dirname [info script]] ".."]]

if {[info exists ::env(EXT8F16_BIT_ROUTE_DIR)] && $::env(EXT8F16_BIT_ROUTE_DIR) ne ""} {
  set route_dir [file normalize $::env(EXT8F16_BIT_ROUTE_DIR)]
} else {
  error "EXT8F16_BIT_ROUTE_DIR is required"
}
if {[info exists ::env(EXT8F16_BIT_OUT_DIR)] && $::env(EXT8F16_BIT_OUT_DIR) ne ""} {
  set out_dir [file normalize $::env(EXT8F16_BIT_OUT_DIR)]
} else {
  set out_dir [file join $repo_root reports external_reduced_8lane_frag16_bitstream_current]
}
file mkdir $out_dir

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}
set_param general.maxThreads $max_threads

set route_dcp [file join $route_dir design_shiboqi_wrapper_post_route.dcp]
if {![file exists $route_dcp]} {
  error "Missing reduced 8-lane fragment=16 post-route checkpoint: $route_dcp"
}

set bit_file [file join $out_dir external_reduced_8lane_frag16_candidate.bit]
set routed_dcp [file join $out_dir external_reduced_8lane_frag16_candidate_post_route.dcp]
set util_rpt [file join $out_dir external_reduced_8lane_frag16_candidate_utilization.rpt]
set timing_rpt [file join $out_dir external_reduced_8lane_frag16_candidate_timing_summary.rpt]
set route_rpt [file join $out_dir external_reduced_8lane_frag16_candidate_route_status.rpt]
set drc_rpt [file join $out_dir external_reduced_8lane_frag16_candidate_drc.rpt]
set io_rpt [file join $out_dir external_reduced_8lane_frag16_candidate_io.rpt]

puts "EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_OPEN_DCP=$route_dcp"
open_checkpoint $route_dcp
report_timing_summary -file $timing_rpt
report_utilization -file $util_rpt
report_route_status -file $route_rpt
report_drc -file $drc_rpt
report_io -file $io_rpt
write_checkpoint -force $routed_dcp
write_bitstream -force $bit_file
puts "EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_READY $bit_file"
puts "EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_NO_HARDWARE_PROGRAMMING=1"
puts "EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_NO_UART_WRITE=1"
puts "EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_NO_TFDU_DRIVE=1"
puts "EXTERNAL_REDUCED_8LANE_FRAG16_BITSTREAM_ETHERNET_DEFERRED=1"
