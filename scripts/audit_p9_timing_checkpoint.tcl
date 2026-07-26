if {$argc < 2} {
  error "usage: audit_p9_timing_checkpoint.tcl <checkpoint.dcp> <output-dir>"
}

set checkpoint_path [file normalize [lindex $argv 0]]
set output_dir [file normalize [lindex $argv 1]]
file mkdir $output_dir
open_checkpoint $checkpoint_path

# Keep the human timing summary compact.  The following check_timing report is
# the authoritative exhaustive audit for no_clock and
# unconstrained_internal_endpoints; listing every external unconstrained I/O
# path here only duplicates tens of megabytes without adding gate coverage.
report_timing_summary -max_paths 10 \
  -file "$output_dir/unconstrained_paths.rpt"
check_timing -verbose -file "$output_dir/check_timing_verbose.rpt"
close_design
puts "P9_TIMING_AUDIT_COMPLETE=$output_dir"
