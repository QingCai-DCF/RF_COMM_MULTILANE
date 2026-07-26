if {$argc < 2} {
  error "usage: report_p9_checkpoint_utilization.tcl <checkpoint.dcp> <report.rpt>"
}

set checkpoint_path [file normalize [lindex $argv 0]]
set report_path [file normalize [lindex $argv 1]]
file mkdir [file dirname $report_path]

open_checkpoint $checkpoint_path
report_utilization -hierarchical -hierarchical_depth 6 -file $report_path
close_design
puts "P9_HIERARCHICAL_UTILIZATION_REPORT=$report_path"
