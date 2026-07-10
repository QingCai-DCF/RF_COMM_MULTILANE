set root_dir [file normalize [lindex $argv 0]]
set out_dir [file normalize "$root_dir/evidence/generated/vivado/p6_jtag_candidate"]
open_checkpoint "$out_dir/post_route_p6_jtag_candidate.dcp"
phys_opt_design -directive AggressiveExplore
write_checkpoint -force "$out_dir/post_route_physopt_p6_jtag_candidate.dcp"
report_drc -file "$out_dir/post_route_drc_p6_jtag_candidate.rpt"
report_timing_summary -file "$out_dir/post_route_timing_summary_p6_jtag_candidate.rpt"
report_timing -max_paths 50 -sort_by group -file "$out_dir/post_route_timing_paths_p6_jtag_candidate.rpt"
report_utilization -file "$out_dir/post_route_utilization_p6_jtag_candidate.rpt"
if {[llength [get_debug_cores -quiet p6_local_transport_ila]] > 0} {
  write_debug_probes -force "$out_dir/p6_jtag_candidate.ltx"
}
write_bitstream -force "$out_dir/p6_jtag_candidate.bit"
puts "P6_JTAG_CANDIDATE_PHYSOPT=PASS"
