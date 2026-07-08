set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]

open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild

set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
if {$bd_file eq ""} {
  error "Missing design_shiboqi.bd"
}
open_bd_design $bd_file
set a [get_bd_cells -quiet ir_array_top_axi_0]
if {[llength $a] == 0} {
  error "Missing ir_array_top_axi_0"
}

set props_before [list_property $a]
puts "IR_CELL_PROBE_BEFORE_HAS_STREAM_PHY_DBG_SELECT=[expr {[lsearch -exact $props_before CONFIG.STREAM_PHY_DBG_SELECT] >= 0}]"
puts "IR_CELL_PROBE_HAS_UPGRADE_BD_CELLS=[expr {[llength [info commands upgrade_bd_cells]] > 0}]"

if {[llength [info commands upgrade_bd_cells]] > 0} {
  if {[catch {upgrade_bd_cells $a} upgrade_err]} {
    puts "IR_CELL_PROBE_UPGRADE_BD_CELLS_ERROR=$upgrade_err"
  } else {
    puts "IR_CELL_PROBE_UPGRADE_BD_CELLS_OK=1"
  }
}

set props_after [list_property $a]
puts "IR_CELL_PROBE_AFTER_HAS_STREAM_PHY_DBG_SELECT=[expr {[lsearch -exact $props_after CONFIG.STREAM_PHY_DBG_SELECT] >= 0}]"
if {[lsearch -exact $props_after CONFIG.STREAM_PHY_DBG_SELECT] >= 0} {
  set_property CONFIG.STREAM_PHY_DBG_SELECT 1 $a
  puts "IR_CELL_PROBE_SET_STREAM_PHY_DBG_SELECT=[get_property CONFIG.STREAM_PHY_DBG_SELECT $a]"
}

close_project
puts "IR_CELL_PROBE_DONE"
