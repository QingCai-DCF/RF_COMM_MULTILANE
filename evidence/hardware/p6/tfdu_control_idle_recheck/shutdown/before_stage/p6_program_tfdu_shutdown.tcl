set log_file {C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/hardware/p6/tfdu_control_idle_recheck/shutdown/before_stage/p6_program_tfdu_shutdown.log}
set fh [open $log_file "w"]
proc say {line} {
  global fh
  puts $line
  puts $fh $line
  flush $fh
}
say "P6_TFDU_SHUTDOWN_WRAPPER_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set rc [catch {
  source {C:/Users/user/Documents/RF_COMM_MULTILANE/scripts/legacy_safe_tools/program_tfdu_shutdown.tcl}
} err opts]
if {$rc != 0} {
  say "P6_TFDU_SHUTDOWN_WRAPPER=FAIL"
  say "P6_TFDU_SHUTDOWN_WRAPPER_ERROR=$err"
  close $fh
  exit 31
}
say "TFDU_SHUTDOWN_PROGRAMMED {C:/Users/user/Documents/RF_COMM_MULTILANE/shutdown_bitstream/tfdu_shutdown_j10_j11.bit}"
say "P6_TFDU_SHUTDOWN_WRAPPER=PASS"
close $fh
exit 0
