set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

set_param general.maxThreads 16
open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild

set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
if {$bd_file eq ""} {
  error "Missing design_shiboqi.bd in project"
}

open_bd_design $bd_file

set ir_cell [get_bd_cells -quiet ir_array_top_axi_0]
if {[llength $ir_cell] == 0} {
  error "Missing BD cell ir_array_top_axi_0"
}

puts "CONFIG: set ir_array_top_axi_0 LANE_COUNT=2"
set_property -dict [list CONFIG.LANE_COUNT 2] $ir_cell

proc recreate_tfdu_vector_port {name dir pin} {
  set old_port [get_bd_ports -quiet $name]
  if {[llength $old_port] > 0} {
    puts "CONFIG: delete old BD port $name"
    delete_bd_objs $old_port
  }

  puts "CONFIG: create BD port $name $dir \[1:0\]"
  set new_port [create_bd_port -dir $dir -from 1 -to 0 $name]
  connect_bd_net $new_port [get_bd_pins $pin]
}

recreate_tfdu_vector_port ir_rx_in_0 I ir_array_top_axi_0/ir_rx_in
recreate_tfdu_vector_port ir_sd_0 O ir_array_top_axi_0/ir_sd
recreate_tfdu_vector_port ir_mode_out_0 O ir_array_top_axi_0/ir_mode_out
recreate_tfdu_vector_port ir_tx_out_0 O ir_array_top_axi_0/ir_tx_out

validate_bd_design
save_bd_design
generate_target all $bd_file
export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
update_compile_order -fileset sources_1

set wrapper_files [make_wrapper -files $bd_file -top -force]
if {[llength $wrapper_files] > 0} {
  foreach wrapper_file $wrapper_files {
    if {[llength [get_files -quiet $wrapper_file]] == 0} {
      add_files -norecurse $wrapper_file
    }
  }
}

set_property top design_shiboqi_wrapper [current_fileset]
update_compile_order -fileset sources_1
close_project

puts "CONFIGURE_2LANE_TFDU_PORTS_DONE"
