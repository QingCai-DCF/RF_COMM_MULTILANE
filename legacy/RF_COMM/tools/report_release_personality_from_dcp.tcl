set repo_root [file normalize [file join [file dirname [info script]] ..]]

if {[info exists ::env(RELEASE_PERSONALITY_OUT_DIR)] && $::env(RELEASE_PERSONALITY_OUT_DIR) ne ""} {
  set out_dir [file normalize $::env(RELEASE_PERSONALITY_OUT_DIR)]
} else {
  set out_dir [file join $repo_root reports release_personality_dcp_current]
}
file mkdir $out_dir

if {[info exists ::env(RELEASE_PERSONALITY_DCP)] && $::env(RELEASE_PERSONALITY_DCP) ne ""} {
  set dcp_path [file normalize $::env(RELEASE_PERSONALITY_DCP)]
} else {
  set dcp_path ""
  set newest_mtime -1
  foreach candidate [glob -nocomplain [file join $repo_root reports build_external_reduced_8lane_frag16_route_20260627_* design_shiboqi_wrapper_post_route.dcp]] {
    set candidate_mtime [file mtime $candidate]
    if {$candidate_mtime > $newest_mtime} {
      set dcp_path $candidate
      set newest_mtime $candidate_mtime
    }
  }
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}
set_param general.maxThreads $max_threads

if {![file exists $dcp_path]} {
  error "Missing release-personality DCP: $dcp_path"
}

puts "RELEASE_PERSONALITY_DCP=$dcp_path"
puts "RELEASE_PERSONALITY_OUT_DIR=$out_dir"

open_checkpoint $dcp_path

report_timing_summary -file [file join $out_dir timing_summary_post_route.rpt]
report_utilization -file [file join $out_dir utilization_post_route.rpt]
report_route_status -file [file join $out_dir route_status_post_route.rpt]
report_drc -file [file join $out_dir drc_post_route.rpt]
report_methodology -file [file join $out_dir methodology_post_route.rpt]
report_control_sets -verbose -file [file join $out_dir control_sets_post_route.rpt]
report_clocks -file [file join $out_dir clocks_post_route.rpt]

puts "RELEASE_PERSONALITY_REPORTS_DONE"
puts "RELEASE_PERSONALITY_NO_HARDWARE_PROGRAMMING=1"
puts "RELEASE_PERSONALITY_NO_UART_WRITE=1"
puts "RELEASE_PERSONALITY_NO_TFDU_DRIVE=1"
puts "RELEASE_PERSONALITY_NO_SYNTHESIS=1"
puts "RELEASE_PERSONALITY_NO_IMPLEMENTATION=1"
puts "RELEASE_PERSONALITY_NO_BITSTREAM=1"
