if {[llength $argv] == 0} {
  puts stderr "usage: check_tcl_complete.tcl <tcl-file> ?<tcl-file>...?"
  exit 2
}

foreach path $argv {
  if {![file isfile $path]} {
    puts stderr "TCL_FILE_MISSING=$path"
    exit 3
  }
  set handle [open $path r]
  set source [read $handle]
  close $handle
  if {![info complete $source]} {
    puts stderr "TCL_SOURCE_INCOMPLETE=$path"
    exit 4
  }
  puts "TCL_SOURCE_COMPLETE=$path"
}
puts "TCL_COMPLETENESS_GATE=PASS"
exit 0
