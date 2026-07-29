# Failed-run emergency recovery only.  This script records every enumerated
# hardware-manager device, selects exactly one authorized Zynq-7010 device,
# and programs the phase-2 frozen shutdown bitstream.  It does not program the
# functional candidate, start a PS ELF, or write any AXI register.

proc p9_normal_idcode {value} {
  set clean [string tolower [string map {_ ""} [string trim $value]]]
  if {[regexp {^[01]{32}$} $clean]} {
    set numeric 0
    foreach bit [split $clean ""] {
      set numeric [expr {($numeric << 1) | ($bit eq "1")}]
    }
    return [format %08X $numeric]
  }
  if {[regexp {^0x([0-9a-f]{8})$} $clean unused hexadecimal]} {
    return [string toupper $hexadecimal]
  }
  if {[regexp {^[0-9a-f]{8}$} $clean]} {
    return [string toupper $clean]
  }
  return ""
}

if {[llength $argv] != 5} {
  error "usage: p9_emergency_shutdown_exact_device.tcl <server-url> <target> <phase2-auth> <shutdown-bit> <result>"
}
set server_url [lindex $argv 0]
set expected_target [lindex $argv 1]
set authorization_file [file normalize [lindex $argv 2]]
set bit_file [file normalize [lindex $argv 3]]
set result_file [file normalize [lindex $argv 4]]
set manager_open 0
set server_connected 0
set target_open 0
set selected_target ""
set device_records {}

set rc [catch {
  if {![info exists ::env(RF_COMM_P9_HW_AUTH)] ||
      $::env(RF_COMM_P9_HW_AUTH) ne "P9_PHASE2_IMMUTABLE_AUTHORIZED"} {
    error "P9 phase-2 environment marker required"
  }
  if {![file isfile $authorization_file] || ![file isfile $bit_file]} {
    error "authorization or immutable shutdown bitstream missing"
  }
  open_hw_manager
  set manager_open 1
  connect_hw_server -url $server_url
  set server_connected 1
  set matches {}
  foreach candidate [get_hw_targets -quiet *] {
    if {[string equal -nocase [string trim "$candidate"] $expected_target]} {
      lappend matches $candidate
    }
  }
  if {[llength $matches] != 1} {
    error "expected one exact authorized target match; found [llength $matches]"
  }
  set selected_target [lindex $matches 0]
  current_hw_target $selected_target
  open_hw_target $selected_target
  set target_open 1

  set exact_devices {}
  foreach candidate [get_hw_devices -quiet *] {
    set part ""; set name ""; set idcode ""
    catch {set part [get_property PART $candidate]}
    catch {set name [get_property NAME $candidate]}
    catch {set idcode [get_property IDCODE $candidate]}
    lappend device_records [list "$candidate" $part $name $idcode [p9_normal_idcode $idcode]]
    if {[string equal -nocase $part "xc7z010"] &&
        [string equal -nocase $name "xc7z010_1"] &&
        [p9_normal_idcode $idcode] eq "13722093"} {
      lappend exact_devices $candidate
    }
  }
  if {[llength $exact_devices] != 1} {
    error "expected exactly one authorized Zynq-7010 device; found [llength $exact_devices]"
  }
  set device [lindex $exact_devices 0]
  current_hw_device $device
  refresh_hw_device -update_hw_probes false $device
  set_property PROGRAM.FILE $bit_file $device
  program_hw_devices $device

  file mkdir [file dirname $result_file]
  set out [open $result_file w]
  puts $out "P9_EMERGENCY_RECOVERY_RESULT=PASS"
  puts $out "TFDU_SHUTDOWN_PROGRAMMED=1"
  puts $out "SHUTDOWN_EXIT=0"
  puts $out "P9_SHUTDOWN_TARGET=$selected_target"
  puts $out "P9_SHUTDOWN_DEVICE=$device"
  puts $out "P9_SHUTDOWN_TXD_OUTPUT_INTENT=0"
  puts $out "P9_SHUTDOWN_SD_REQUEST_ACTIVE=1"
  puts $out "P9_SHUTDOWN_ACTIVE_TX_MASK=0"
  foreach record $device_records {
    lassign $record object part name idcode normalized
    puts $out "P9_ENUM_DEVICE=$object|PART=$part|NAME=$name|IDCODE=$idcode|NORMALIZED=$normalized"
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
    puts $out "P9_EMERGENCY_RECOVERY_RESULT=FAIL"
    puts $out "TFDU_SHUTDOWN_PROGRAMMED=0"
    puts $out "SHUTDOWN_EXIT=1"
    puts $out "P9_SHUTDOWN_ERROR=[string map [list \"\r\" \" \" \"\n\" \" \" \"=\" \"_\"] $error_text]"
    foreach record $device_records {
      lassign $record object part name idcode normalized
      puts $out "P9_ENUM_DEVICE=$object|PART=$part|NAME=$name|IDCODE=$idcode|NORMALIZED=$normalized"
    }
    close $out
  }
  puts stderr "P9_EMERGENCY_RECOVERY_RESULT=FAIL"
  puts stderr $error_text
  exit 41
}
puts "P9_EMERGENCY_RECOVERY_RESULT=PASS"
puts "TFDU_SHUTDOWN_PROGRAMMED=1"
puts "SHUTDOWN_EXIT=0"
exit 0
