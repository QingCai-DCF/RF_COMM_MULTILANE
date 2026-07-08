set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
open_project $project_file
set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
open_bd_design $bd_file
foreach p [lsort [get_bd_pins -quiet ir_loopback_b0/*]] {
  puts "PIN name=$p dir=[get_property DIR $p] type=[get_property TYPE $p] left=[get_property LEFT $p] right=[get_property RIGHT $p]"
}
close_project
