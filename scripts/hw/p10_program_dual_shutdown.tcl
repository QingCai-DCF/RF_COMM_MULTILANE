# Program the two frozen P10 AX7020 shutdown images on the two explicitly
# bound JTAG cables.  This script never downloads an ELF, resets a processor,
# writes AXI/DDR, or starts a TFDU transmission.  The outer fail-closed Python
# wrapper validates the immutable authorization and artifact SHA256 values
# before invoking this script; this script independently requires the current-
# run environment marker and exact live target topology.
# require-user-hw-authorization: reached only through the committed P10
# FastTrack current-run authorization and fail-closed outer wrapper.

proc p10_normal_idcode {value} {
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

proc p10_safe_marker {value} {
  return [string map [list "\r" " " "\n" " " "=" "_" "|" "_"] $value]
}

proc p10_program_one_shutdown {role expected_target expected_serial bit_file} {
  global p10_selected_target p10_target_open p10_result_lines

  set matches {}
  foreach candidate [get_hw_targets -quiet *] {
    if {[string equal -nocase [string trim "$candidate"] $expected_target]} {
      lappend matches $candidate
    }
  }
  if {[llength $matches] != 1} {
    error "P10 $role requires exactly one exact Hardware Manager target; found [llength $matches]"
  }

  set p10_selected_target [lindex $matches 0]
  if {[string first [string tolower $expected_serial] \
                    [string tolower $p10_selected_target]] < 0} {
    error "P10 $role target does not contain its authorized JTAG serial"
  }
  current_hw_target $p10_selected_target
  open_hw_target $p10_selected_target
  set p10_target_open 1

  set all_devices [get_hw_devices -quiet *]
  set exact_devices {}
  set auxiliary_devices {}
  set unexpected_devices {}
  set record_index 0
  foreach candidate $all_devices {
    set part ""; set name ""; set idcode ""
    catch {set part [get_property PART $candidate]}
    catch {set name [get_property NAME $candidate]}
    catch {set idcode [get_property IDCODE $candidate]}
    set normalized [p10_normal_idcode $idcode]
    lappend p10_result_lines "P10_SHUTDOWN_${role}_ENUM_DEVICE_${record_index}=$candidate|PART=$part|NAME=$name|IDCODE=$idcode|NORMALIZED=$normalized"
    incr record_index
    # Hardware Manager appends a process-local numeric suffix when the same
    # canonical device name is instantiated under a second open target (for
    # example xc7z020_1_1).  The exact target is already bound to one JTAG
    # serial above, so accept only that canonical generated-name family while
    # retaining the exact part and IDCODE checks.
    if {[string equal -nocase $part "xc7z020"] &&
        [regexp -nocase {^xc7z020_1(_[0-9]+)?$} $name] &&
        $normalized eq "23727093"} {
      lappend exact_devices $candidate
    } elseif {[string equal -nocase $part "arm_dap"] &&
              [regexp -nocase {^arm_dap_0(_[0-9]+)?$} $name] &&
              $normalized eq "4BA00477"} {
      lappend auxiliary_devices $candidate
    } else {
      lappend unexpected_devices $candidate
    }
  }
  if {[llength $exact_devices] != 1} {
    error "P10 $role expected exactly one canonical live Zynq-7020; found [llength $exact_devices]"
  }
  if {[llength $auxiliary_devices] > 1} {
    error "P10 $role expected at most one ARM DAP; found [llength $auxiliary_devices]"
  }
  if {[llength $unexpected_devices] != 0} {
    error "P10 $role found unexpected Hardware Manager devices: [llength $unexpected_devices]"
  }

  set device [lindex $exact_devices 0]
  current_hw_device $device
  refresh_hw_device -update_hw_probes false $device
  set_property PROGRAM.FILE $bit_file $device
  program_hw_devices $device

  lappend p10_result_lines "P10_SHUTDOWN_${role}_TARGET=$p10_selected_target"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_SERIAL=$expected_serial"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_HW_OBJECT_COUNT=[llength $all_devices]"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_EXACT_FPGA_MATCH_COUNT=[llength $exact_devices]"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_AUXILIARY_DAP_COUNT=[llength $auxiliary_devices]"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_UNEXPECTED_HW_OBJECT_COUNT=[llength $unexpected_devices]"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_TXD_OUTPUT_INTENT=0"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_SD_REQUEST_ACTIVE=1"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_MODE_HIGH=1"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_ENDPOINT_ARMED=0"
  lappend p10_result_lines "P10_SHUTDOWN_${role}_ACTIVE_TX_MASK=0"
  lappend p10_result_lines "P10_SHUTDOWN_${role}=PASS"

  close_hw_target $p10_selected_target
  set p10_target_open 0
  set p10_selected_target ""
}

if {[llength $argv] != 10} {
  error "usage: p10_program_dual_shutdown.tcl <server-url> <fixed-target> <rotating-target> <fixed-serial> <rotating-serial> <part> <authorization> <fixed-bit> <rotating-bit> <result>"
}
set server_url [lindex $argv 0]
set fixed_target [lindex $argv 1]
set rotating_target [lindex $argv 2]
set fixed_serial [lindex $argv 3]
set rotating_serial [lindex $argv 4]
set expected_part [lindex $argv 5]
set authorization_file [file normalize [lindex $argv 6]]
set fixed_bit [file normalize [lindex $argv 7]]
set rotating_bit [file normalize [lindex $argv 8]]
set result_file [file normalize [lindex $argv 9]]

set p10_manager_open 0
set p10_server_connected 0
set p10_target_open 0
set p10_selected_target ""
set p10_result_lines {}
set p10_fixed_status FAIL
set p10_rotating_status FAIL

set rc [catch {
  if {![info exists ::env(RF_COMM_P10_HW_AUTH)] ||
      $::env(RF_COMM_P10_HW_AUTH) ni {
        P10_FASTTRACK_IMMUTABLE_AUTHORIZED P10_3F_IMMUTABLE_AUTHORIZED
        P10_4_IMMUTABLE_AUTHORIZED P10_5_IMMUTABLE_AUTHORIZED}} {
    error "P10 immutable current-run environment marker required"
  }
  foreach required [list $authorization_file $fixed_bit $rotating_bit] {
    if {![file isfile $required]} { error "missing immutable P10 shutdown input: $required" }
  }
  if {![string equal -nocase $expected_part "xc7z020clg400-2"]} {
    error "P10 shutdown part contract mismatch"
  }
  if {$fixed_serial eq $rotating_serial ||
      ![regexp {^[0-9]+$} $fixed_serial] ||
      ![regexp {^[0-9]+$} $rotating_serial]} {
    error "P10 shutdown serial binding is invalid or ambiguous"
  }

  open_hw_manager
  set p10_manager_open 1
  connect_hw_server -url $server_url
  set p10_server_connected 1

  p10_program_one_shutdown FIXED $fixed_target $fixed_serial $fixed_bit
  set p10_fixed_status PASS
  p10_program_one_shutdown ROTATING $rotating_target $rotating_serial $rotating_bit
  set p10_rotating_status PASS
} error_text error_options]

if {$p10_target_open} { catch {close_hw_target $p10_selected_target} }
if {$p10_server_connected} { catch {disconnect_hw_server} }
if {$p10_manager_open} { catch {close_hw_manager} }

file mkdir [file dirname $result_file]
set out [open $result_file w]
foreach line $p10_result_lines {
  puts $out $line
  puts $line
}
puts $out "SHUTDOWN_FIXED=$p10_fixed_status"
puts $out "SHUTDOWN_ROTATING=$p10_rotating_status"
puts "SHUTDOWN_FIXED=$p10_fixed_status"
puts "SHUTDOWN_ROTATING=$p10_rotating_status"
if {$rc == 0 && $p10_fixed_status eq "PASS" && $p10_rotating_status eq "PASS"} {
  puts $out "TFDU_SHUTDOWN_PROGRAMMED=1"
  puts $out "SHUTDOWN_EXIT=0"
  puts $out "P10_DUAL_SHUTDOWN_RESULT=PASS"
  puts "TFDU_SHUTDOWN_PROGRAMMED=1"
  puts "SHUTDOWN_EXIT=0"
  puts "P10_DUAL_SHUTDOWN_RESULT=PASS"
} else {
  puts $out "TFDU_SHUTDOWN_PROGRAMMED=0"
  puts $out "SHUTDOWN_EXIT=1"
  puts $out "P10_DUAL_SHUTDOWN_RESULT=FAIL"
  puts $out "P10_DUAL_SHUTDOWN_ERROR=[p10_safe_marker $error_text]"
  puts stderr "P10_DUAL_SHUTDOWN_RESULT=FAIL"
  puts stderr $error_text
}
close $out

if {$rc != 0 || $p10_fixed_status ne "PASS" || $p10_rotating_status ne "PASS"} {
  exit 31
}
exit 0
