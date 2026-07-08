set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
open_project $project_file
set run [get_runs synth_1]
puts "RF_COMM_SYNTH_CONTROL_SET_OPTIONS_BEGIN"
foreach prop [lsort [list_property $run]] {
  set prop_l [string tolower $prop]
  if {[string match "*control*" $prop_l] || [string match "*synth_design.args*" $prop_l]} {
    set value ""
    if {[catch {set value [get_property $prop $run]} err]} {
      set value "__READ_ERROR__:$err"
    }
    puts "$prop=$value"
  }
}
puts "RF_COMM_SYNTH_CONTROL_SET_OPTIONS_END"
close_project
