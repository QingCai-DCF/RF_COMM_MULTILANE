set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]

open_project $project_file
set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
open_bd_design $bd_file

set cell [get_bd_cells -quiet ir_loopback_b0]
if {[llength $cell] == 0} {
  puts "LOOPBACK_CELL_MISSING"
} else {
  puts "LOOPBACK_CELL=$cell"
  foreach pin [lsort [get_bd_pins -of_objects $cell]] {
    puts "PIN $pin DIR=[get_property DIR $pin] LEFT=[get_property LEFT $pin] RIGHT=[get_property RIGHT $pin]"
  }
}

set a [get_bd_cells -quiet ir_array_top_axi_0]
if {[llength $a] == 0} {
  puts "A_CELL_MISSING"
} else {
  foreach pin [lsort [get_bd_pins -of_objects $a]] {
    if {[string match *ext_phy* $pin]} {
      puts "A_PIN $pin DIR=[get_property DIR $pin] LEFT=[get_property LEFT $pin] RIGHT=[get_property RIGHT $pin]"
    }
  }
}

close_project
exit 0
