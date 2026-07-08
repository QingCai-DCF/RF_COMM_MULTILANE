set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}

set_param general.maxThreads $max_threads
open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]

if {[info exists ::env(VIVADO_DISABLE_IP_CACHE)] && $::env(VIVADO_DISABLE_IP_CACHE) ne "" && $::env(VIVADO_DISABLE_IP_CACHE) ne "0"} {
  config_ip_cache -disable_cache
}

update_ip_catalog -rebuild

set ir_array_ips [get_ips -quiet *ir_array_top_axi*]
if {[llength $ir_array_ips] > 0} {
  set upgradable [list]
  foreach ip $ir_array_ips {
    if {[llength [get_property UPGRADE_VERSIONS $ip]] > 0} {
      lappend upgradable $ip
    }
  }
  if {[llength $upgradable] > 0} {
    puts "SYNTH_ONLY: upgrade IR array IP instances: $upgradable"
    upgrade_ip $upgradable
  }
}

set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
if {$bd_file eq ""} {
  error "Missing design_shiboqi.bd in project"
}

generate_target all $bd_file
export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
update_compile_order -fileset sources_1

reset_run synth_1
launch_runs synth_1 -jobs $max_threads
wait_on_run synth_1

set synth_status [get_property STATUS [get_runs synth_1]]
puts "SYNTH_STATUS=$synth_status"
if {![string match "*Complete*" $synth_status]} {
  error "Synthesis did not complete: $synth_status"
}

open_run synth_1
set run_dir [get_property DIRECTORY [get_runs synth_1]]
report_utilization -file [file join $run_dir utilization_synth.rpt]

puts "SYNTH_ONLY_DONE"
puts "SYNTH_RUN_DIR=$run_dir"
close_project
