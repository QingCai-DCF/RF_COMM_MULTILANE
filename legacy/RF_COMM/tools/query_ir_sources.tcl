set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]

open_project $project_file
puts "TOP=[get_property top [current_fileset]]"
foreach f [get_files -quiet -all *ir_array_top.sv] {
  puts "IR_SRC=$f USED_IN=[get_property USED_IN $f]"
}
foreach f [get_files -quiet -all *ir_comm_lane.sv] {
  puts "LANE_SRC=$f USED_IN=[get_property USED_IN $f]"
}
set refs [get_property SOURCE_MGMT_MODE [current_project]]
puts "SOURCE_MGMT_MODE=$refs"
close_project
