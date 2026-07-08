set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root reports pin_static_diag pin_static_diag.xpr]

open_project $project_file
open_run impl_1

puts "PIN_STATIC_DIAG_IO_BEGIN"
foreach port {a_mode a_sd a_tx a_rx b_mode b_sd b_tx b_rx} {
  set p [get_ports -quiet $port]
  if {[llength $p] == 0} {
    puts "$port MISSING"
  } else {
    puts [format "%s PACKAGE_PIN=%s IOSTANDARD=%s DIRECTION=%s" \
      $port \
      [get_property PACKAGE_PIN $p] \
      [get_property IOSTANDARD $p] \
      [get_property DIRECTION $p]]
  }
}
puts "PIN_STATIC_DIAG_IO_END"

close_project
