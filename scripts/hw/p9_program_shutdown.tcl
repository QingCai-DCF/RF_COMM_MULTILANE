# Program the already-frozen P9 Z7010 shutdown bitstream on exactly one
# authorized target.  No candidate, PS ELF, AXI write, or TFDU transmit is
# performed here.
# require-user-hw-authorization: the immutable phase-2 wrapper and the
# RF_COMM_P9_HW_AUTH marker are both checked before any hardware API call.

proc p9_normal_idcode {value} {
  set clean [string tolower [string map {_ ""} [string trim $value]]]
  if {[regexp {^[01]{32}$} $clean]} {
    set numeric 0
    foreach bit [split $clean ""] { set numeric [expr {($numeric << 1) | ($bit eq "1")}] }
    return [format %08X $numeric]
  }
  if {[regexp {^0x([0-9a-f]{8})$} $clean unused hexadecimal]} { return [string toupper $hexadecimal] }
  if {[regexp {^[0-9a-f]{8}$} $clean]} { return [string toupper $clean] }
  return ""
}

if {[llength $argv] != 7} {
  error "usage: p9_program_shutdown.tcl <server-url> <target> <board-id> <part> <phase2-auth> <shutdown-bit> <result>"
}
set server_url [lindex $argv 0]
set expected_target [lindex $argv 1]
set expected_board [lindex $argv 2]
set expected_part [lindex $argv 3]
set authorization_file [file normalize [lindex $argv 4]]
set bit_file [file normalize [lindex $argv 5]]
set result_file [file normalize [lindex $argv 6]]
set manager_open 0; set server_connected 0; set target_open 0; set selected_target ""

set rc [catch {
  if {![info exists ::env(RF_COMM_P9_HW_AUTH)] ||
      $::env(RF_COMM_P9_HW_AUTH) ne "P9_PHASE2_IMMUTABLE_AUTHORIZED"} {
    error "P9 phase-2 environment marker required"
  }
  if {![file isfile $authorization_file] || ![file isfile $bit_file]} {
    error "authorization or immutable shutdown bitstream missing"
  }
  if {![string equal -nocase $expected_part "xc7z010clg400-1"] ||
      [string first [string tolower $expected_board] [string tolower $expected_target]] < 0} {
    error "P9 shutdown target contract mismatch"
  }
  open_hw_manager
  set manager_open 1
  connect_hw_server -url $server_url
  set server_connected 1
  set matches {}
  foreach candidate [get_hw_targets -quiet *] {
    if {[string equal -nocase [string trim "$candidate"] $expected_target]} { lappend matches $candidate }
  }
  if {[llength $matches] != 1} { error "expected one exact target match" }
  set selected_target [lindex $matches 0]
  current_hw_target $selected_target
  open_hw_target $selected_target
  set target_open 1
  set devices [get_hw_devices -quiet *]
  if {[llength $devices] != 1} { error "expected one live device" }
  set device [lindex $devices 0]
  set live_part [get_property PART $device]
  set live_name [get_property NAME $device]
  set live_idcode [get_property IDCODE $device]
  if {![string equal -nocase $live_part "xc7z010"] ||
      ![string equal -nocase $live_name "xc7z010_1"] ||
      [p9_normal_idcode $live_idcode] ne "13722093"} {
    error "live device identity mismatch"
  }
  current_hw_device $device
  refresh_hw_device -update_hw_probes false $device
  set_property PROGRAM.FILE $bit_file $device
  program_hw_devices $device
  file mkdir [file dirname $result_file]
  set out [open $result_file w]
  foreach line [list \
      "P9_SHUTDOWN_PROGRAM_RESULT=PASS" \
      "TFDU_SHUTDOWN_PROGRAMMED=1" \
      "SHUTDOWN_EXIT=0" \
      "P9_SHUTDOWN_TARGET=$selected_target" \
      "P9_SHUTDOWN_LIVE_DEVICE=$live_name" \
      "P9_SHUTDOWN_LIVE_IDCODE_NORMALIZED=[p9_normal_idcode $live_idcode]" \
      "P9_SHUTDOWN_TXD_OUTPUT_INTENT=0" \
      "P9_SHUTDOWN_SD_REQUEST_ACTIVE=1" \
      "P9_SHUTDOWN_MODE_HIGH=1" \
      "P9_SHUTDOWN_ENDPOINT_ARMED=0" \
      "P9_SHUTDOWN_ACTIVE_TX_MASK=0"] {
    puts $out $line
    puts $line
  }
  close $out
} error_text error_options]

if {$target_open} { catch {close_hw_target $selected_target} }
if {$server_connected} { catch {disconnect_hw_server} }
if {$manager_open} { catch {close_hw_manager} }

if {$rc != 0} {
  catch {
    file mkdir [file dirname $result_file]
    set out [open $result_file w]
    puts $out "P9_SHUTDOWN_PROGRAM_RESULT=FAIL"
    puts $out "TFDU_SHUTDOWN_PROGRAMMED=0"
    puts $out "SHUTDOWN_EXIT=1"
    puts $out "P9_SHUTDOWN_ERROR=[string map [list \"\\r\" \" \" \"\\n\" \" \" \"=\" \"_\"] $error_text]"
    close $out
  }
  puts stderr "P9_SHUTDOWN_PROGRAM_RESULT=FAIL"
  puts stderr $error_text
  exit 31
}
exit 0
