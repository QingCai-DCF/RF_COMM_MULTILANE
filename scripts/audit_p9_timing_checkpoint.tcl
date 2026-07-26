if {$argc < 2} {
  error "usage: audit_p9_timing_checkpoint.tcl <checkpoint.dcp> <output-dir>"
}

set checkpoint_path [file normalize [lindex $argv 0]]
set output_dir [file normalize [lindex $argv 1]]
file mkdir $output_dir
open_checkpoint $checkpoint_path

report_timing_summary -report_unconstrained -max_paths 1000 \
  -file "$output_dir/unconstrained_paths.rpt"
check_timing -verbose -file "$output_dir/check_timing_verbose.rpt"
close_design
puts "P9_TIMING_AUDIT_COMPLETE=$output_dir"
