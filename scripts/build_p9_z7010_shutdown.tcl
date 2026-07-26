set root_dir [file normalize [lindex $argv 0]]
set build_dir [file normalize "$root_dir/build/p9_z7010_shutdown"]
set out_dir [file normalize "$root_dir/evidence/generated/vivado/p9_z7010_shutdown"]
file mkdir $build_dir
file mkdir $out_dir

create_project p9_z7010_shutdown "$build_dir/project" -part xc7z010clg400-1 -force
add_files -norecurse "$root_dir/rtl/p9_z7010_shutdown_top.v"
read_xdc "$root_dir/constraints/active/PORT1.generated.xdc"
set_property top p9_z7010_shutdown_top [current_fileset]
update_compile_order -fileset sources_1

launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%" ||
    ![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {
  error "P9 shutdown implementation did not complete: [get_property STATUS [get_runs impl_1]]"
}
open_run impl_1
report_drc -file "$out_dir/post_route_drc_p9_shutdown.rpt"
report_timing_summary -file "$out_dir/post_route_timing_summary_p9_shutdown.rpt"
report_utilization -file "$out_dir/post_route_utilization_p9_shutdown.rpt"
write_checkpoint -force "$out_dir/post_route_p9_shutdown.dcp"
write_bitstream -force "$out_dir/ir_p9_shutdown_z7010.bit"
set marker [open "$out_dir/p9_shutdown_build_markers.txt" w]
puts $marker "P9_SHUTDOWN_BUILD=PASS"
puts $marker "P9_SHUTDOWN_TXD_INTENT=0x0"
puts $marker "P9_SHUTDOWN_SD_INTENT=0xF"
puts $marker "P9_SHUTDOWN_MODE_INTENT=0xF"
puts $marker "P9_SHUTDOWN_PART=xc7z010clg400-1"
close $marker
puts "P9_SHUTDOWN_BUILD=PASS"
