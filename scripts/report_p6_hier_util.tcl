set root_dir [file normalize [lindex $argv 0]]
set dcp "$root_dir/evidence/generated/vivado/p6_jtag_candidate/post_synth_p6_jtag_candidate.dcp"
open_checkpoint $dcp
report_utilization -hierarchical -hierarchical_depth 6 -file "$root_dir/evidence/generated/vivado/p6_jtag_candidate/post_synth_hier_utilization.rpt"
puts "P6_HIER_UTIL_REPORT=PASS"
