set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set reports_dir [file join $repo_root reports]
set bd_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs sources_1 bd design_shiboqi design_shiboqi.bd]

file mkdir $reports_dir

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
if {![file exists $bd_file]} {
  error "Missing block design: $bd_file"
}

open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild

open_bd_design $bd_file
report_ip_status -file [file join $reports_dir P2_PSPL_ip_status_before_upgrade.rpt]

set target_ips [get_ips -quiet design_shiboqi_ir_array_top_axi_0_0]
if {[llength $target_ips] == 0} {
  error "Missing target IP design_shiboqi_ir_array_top_axi_0_0"
}

puts "UPGRADE_TARGET_IPS=$target_ips"
upgrade_ip $target_ips
validate_bd_design
save_bd_design

report_ip_status -file [file join $reports_dir P2_PSPL_ip_status_after_upgrade.rpt]
set bd_obj [get_files -quiet $bd_file]
if {[llength $bd_obj] == 0} {
  error "Vivado file object not found for block design: $bd_file"
}
generate_target all $bd_obj
export_ip_user_files -of_objects $bd_obj -no_script -sync -force -quiet
update_compile_order -fileset sources_1

puts "P2_PSPL_IR_IP_UPGRADE_DONE"
close_project
