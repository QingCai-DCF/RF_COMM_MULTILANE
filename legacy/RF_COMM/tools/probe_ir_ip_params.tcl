set repo_root [file normalize [file join [file dirname [info script]] ..]]
set ip_repo [file join $repo_root IPs ip_ir_array]
set probe_dir [file join $repo_root .vivado_ip_probe]

file mkdir $probe_dir
create_project -force ir_ip_probe $probe_dir -part xc7z010clg400-1
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild

create_bd_design probe_bd
set defs [get_ipdefs -all -filter {VLNV =~ xilinx.com:user:ir_array_top_axi:*}]
if {[llength $defs] == 0} {
  error "Missing ir_array_top_axi IP definition"
}
set vlnv [get_property VLNV [lindex $defs end]]
set c [create_bd_cell -type ip -vlnv $vlnv ir_probe]
set props [list_property $c]
puts "IR_IP_PROBE_VLNV=[get_property VLNV $c]"
puts "IR_IP_PROBE_HAS_STREAM_PHY_DBG_SELECT=[expr {[lsearch -exact $props CONFIG.STREAM_PHY_DBG_SELECT] >= 0}]"
puts "IR_IP_PROBE_HAS_STREAM_FULL_MODE=[expr {[lsearch -exact $props CONFIG.STREAM_FULL_MODE] >= 0}]"
puts "IR_IP_PROBE_HAS_STREAM_NODE_ID=[expr {[lsearch -exact $props CONFIG.STREAM_NODE_ID] >= 0}]"
if {[lsearch -exact $props CONFIG.STREAM_PHY_DBG_SELECT] >= 0} {
  set_property CONFIG.STREAM_PHY_DBG_SELECT 1 $c
  puts "IR_IP_PROBE_SET_STREAM_PHY_DBG_SELECT=[get_property CONFIG.STREAM_PHY_DBG_SELECT $c]"
}

close_project
puts "IR_IP_PROBE_DONE"
