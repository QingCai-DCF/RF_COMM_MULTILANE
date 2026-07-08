set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

open_project $project_file
set run [get_runs impl_1]

puts "RF_COMM_IMPL_CONTROL_SET_OPTIONS_BEGIN"
foreach prop [lsort [list_property $run]] {
  set prop_l [string tolower $prop]
  if {[string match "*control*" $prop_l] ||
      [string match "*opt_design.args*" $prop_l] ||
      [string match "*opt_design.tcl*" $prop_l] ||
      [string match "*place_design.args*" $prop_l] ||
      [string match "*phys_opt_design.args*" $prop_l]} {
    set value ""
    if {[catch {set value [get_property $prop $run]} err]} {
      set value "__READ_ERROR__:$err"
    }
    puts "$prop=$value"
  }
}
puts "RF_COMM_IMPL_CONTROL_SET_OPTIONS_END"

puts "RF_COMM_OPT_DESIGN_HELP_BEGIN"
if {[catch {help opt_design} help_text]} {
  puts "__HELP_ERROR__:$help_text"
} else {
  puts $help_text
}
puts "RF_COMM_OPT_DESIGN_HELP_END"

puts "RF_COMM_IMPL_CONTROL_SET_QUERY_NO_HARDWARE_PROGRAMMING=1"
puts "RF_COMM_IMPL_CONTROL_SET_QUERY_NO_UART_WRITE=1"
puts "RF_COMM_IMPL_CONTROL_SET_QUERY_NO_TFDU_DRIVE=1"
close_project
