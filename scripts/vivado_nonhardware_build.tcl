set root_dir [file normalize [lindex $argv 0]]
set out_dir [file normalize "$root_dir/evidence/generated/vivado"]
file mkdir $out_dir

set part_name "xc7z010clg400-1"
set log_file [open "$out_dir/nonhardware_build_markers.txt" "w"]
puts $log_file "VIVADO_NONHARDWARE_BUILD_STARTED=1"
puts $log_file "NO_HARDWARE_ACTIONS_EXECUTED=1"
close $log_file

create_project rf_comm_nonhardware "$out_dir/project" -part $part_name -force
set rtl_files [glob -nocomplain "$root_dir/rtl/*.sv"]
add_files -fileset sources_1 $rtl_files
set_property top ir_top_new [current_fileset]
read_xdc "$root_dir/constraints/active/PORT1.generated.xdc"
update_compile_order -fileset sources_1

synth_design -top ir_top_new -part $part_name
write_checkpoint -force "$out_dir/post_synth.dcp"
report_drc -file "$out_dir/post_synth_drc.rpt"

opt_design
place_design
route_design
write_checkpoint -force "$out_dir/post_route.dcp"
report_drc -file "$out_dir/post_route_drc.rpt"
report_timing_summary -file "$out_dir/post_route_timing_summary.rpt"
report_utilization -file "$out_dir/post_route_utilization.rpt"

set log_file [open "$out_dir/nonhardware_build_markers.txt" "a"]
puts $log_file "VIVADO_NONHARDWARE_BUILD_DONE=1"
puts $log_file "VIVADO_REPORT_DIR=$out_dir"
close $log_file
