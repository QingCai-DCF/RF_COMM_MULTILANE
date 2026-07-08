set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
open_project $project_file
set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
open_bd_design $bd_file
set ila [get_bd_cells -quiet ila_lane0_phy]
if {[llength $ila] == 0} {
  error "ila_lane0_phy not found"
}
puts "ILA_CELL=$ila"
foreach prop [lsort [list_property $ila]] {
  set val [get_property $prop $ila]
  if {[string match "CONFIG.*" $prop] && ([string match "*PROBE*" $prop] || [string match "*MONITOR*" $prop] || [string match "*SLOT*" $prop] || [string match "*TYPE*" $prop] || [string match "*INTERFACE*" $prop] || [string match "*DATA_DEPTH*" $prop])} {
    puts "$prop=$val"
  }
}
foreach pin [lsort [get_bd_pins -of_objects $ila]] {
  puts "PIN $pin DIR=[get_property DIR $pin] TYPE=[get_property TYPE $pin] LEFT=[get_property LEFT $pin] RIGHT=[get_property RIGHT $pin]"
}
close_project
