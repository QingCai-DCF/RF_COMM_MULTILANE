set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
open_project $project_file
foreach r [get_runs] {
  puts "RUN_STATUS name=$r status=[get_property STATUS $r] progress=[get_property PROGRESS $r] dir=[get_property DIRECTORY $r]"
}
close_project
