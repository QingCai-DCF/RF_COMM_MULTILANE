set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set xsa_file [file join $repo_root TFDU_VFIR_Client_Array design_shiboqi_wrapper.xsa]

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

open_project $project_file
set_param general.maxThreads 16
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild

set ir_ip [get_ips design_shiboqi_ir_array_top_axi_0_0]
if {[llength [get_property UPGRADE_VERSIONS $ir_ip]] > 0} {
  upgrade_ip $ir_ip
}

set bd_file [get_files */design_shiboqi.bd]
generate_target all $bd_file
export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
update_compile_order -fileset sources_1

reset_run synth_1
reset_run impl_1
launch_runs impl_1 -to_step write_bitstream -jobs 16
wait_on_run impl_1

open_run impl_1
report_timing_summary -file [file join [get_property DIRECTORY [current_run]] timing_summary_post_route.rpt]
report_utilization -file [file join [get_property DIRECTORY [current_run]] utilization_post_route.rpt]
write_hw_platform -fixed -include_bit -force -file $xsa_file

puts "BUILD_MAIN_PROJECT_DONE"
puts "XSA_FILE=$xsa_file"
close_project
