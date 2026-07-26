# P9 authorization-bound, read-only target identity probe.
# require-user-hw-authorization: the immutable phase-2 wrapper and the
# RF_COMM_P9_HW_AUTH marker are both checked before any hardware API call.
# The Python wrapper validates the phase-2 authorization and every immutable
# SHA-256 before this script may be launched.

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

if {[llength $argv] != 6} {
  error "usage: p9_hw_preflight.tcl <server-url> <target> <board-id> <part> <phase2-auth> <result>"
}

set server_url [lindex $argv 0]
set expected_target [lindex $argv 1]
set expected_board [lindex $argv 2]
set expected_part [lindex $argv 3]
set authorization_file [file normalize [lindex $argv 4]]
set result_file [file normalize [lindex $argv 5]]
set expected_live_part "xc7z010"
set expected_live_device "xc7z010_1"
set expected_idcode "13722093"
set expected_aux_part "arm_dap"
set expected_aux_device "arm_dap_0"
set expected_aux_idcode "4BA00477"
set manager_open 0
set server_connected 0
set target_open 0
set selected_target ""
set all_device_count 0
set exact_device_count 0
set auxiliary_device_count 0
set unexpected_device_count 0
set device_records {}

set rc [catch {
  if {![info exists ::env(RF_COMM_P9_HW_AUTH)] ||
      $::env(RF_COMM_P9_HW_AUTH) ne "P9_PHASE2_IMMUTABLE_AUTHORIZED"} {
    error "RF_COMM_P9_HW_AUTH=P9_PHASE2_IMMUTABLE_AUTHORIZED required"
  }
  if {![file isfile $authorization_file]} { error "phase-2 authorization missing" }
  if {![string equal -nocase $expected_part "xc7z010clg400-1"]} {
    error "P9 preflight supports only xc7z010clg400-1"
  }
  if {[string first [string tolower $expected_board] [string tolower $expected_target]] < 0} {
    error "target does not contain the authorized board serial"
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
    error "expected exactly one authorized hw target; found [llength $matches]"
  }
  set selected_target [lindex $matches 0]
  current_hw_target $selected_target
  open_hw_target $selected_target
  set target_open 1

  set all_devices [get_hw_devices -quiet *]
  set device_matches {}
  set auxiliary_devices {}
  set unexpected_devices {}
  set all_device_count [llength $all_devices]
  foreach candidate $all_devices {
    set part ""; set name ""; set idcode ""
    catch {set part [get_property PART $candidate]}
    catch {set name [get_property NAME $candidate]}
    catch {set idcode [get_property IDCODE $candidate]}
    set normalized_idcode [p9_normal_idcode $idcode]
    lappend device_records [list "$candidate" $part $name $idcode $normalized_idcode]
    if {[string equal -nocase $part $expected_live_part] &&
        [string equal -nocase $name $expected_live_device] &&
        $normalized_idcode eq $expected_idcode} {
      lappend device_matches $candidate
    } elseif {[string equal -nocase $part $expected_aux_part] &&
              [string equal -nocase $name $expected_aux_device] &&
              $normalized_idcode eq $expected_aux_idcode} {
      lappend auxiliary_devices $candidate
    } else {
      lappend unexpected_devices $candidate
    }
  }
  set exact_device_count [llength $device_matches]
  set auxiliary_device_count [llength $auxiliary_devices]
  set unexpected_device_count [llength $unexpected_devices]
  if {$exact_device_count != 1} {
    error "expected exactly one canonical live Zynq-7010 match; found $exact_device_count"
  }
  if {$auxiliary_device_count > 1} {
    error "expected at most one canonical ARM DAP object; found $auxiliary_device_count"
  }
  if {$unexpected_device_count != 0} {
    error "unexpected hardware-manager objects found: $unexpected_device_count"
  }
  set device [lindex $device_matches 0]
  current_hw_device $device
  set live_part [get_property PART $device]
  set live_name [get_property NAME $device]
  set live_idcode [get_property IDCODE $device]

  file mkdir [file dirname $result_file]
  set out [open $result_file w]
  foreach line [list \
      "P9_TARGET_IDENTITY_RESULT=PASS" \
      "P9_TARGET_IDENTITY_READ_ONLY=1" \
      "P9_TARGET_IDENTITY_SINGLE_TARGET=1" \
      "P9_TARGET_IDENTITY_HW_OBJECT_COUNT=$all_device_count" \
      "P9_TARGET_IDENTITY_EXACT_FPGA_MATCH_COUNT=$exact_device_count" \
      "P9_TARGET_IDENTITY_AUXILIARY_DAP_COUNT=$auxiliary_device_count" \
      "P9_TARGET_IDENTITY_UNEXPECTED_HW_OBJECT_COUNT=$unexpected_device_count" \
      "P9_TARGET_IDENTITY_TARGET=$selected_target" \
      "P9_TARGET_IDENTITY_BOARD_ID=$expected_board" \
      "P9_TARGET_IDENTITY_CANONICAL_PART=$expected_part" \
      "P9_TARGET_IDENTITY_LIVE_PART=$live_part" \
      "P9_TARGET_IDENTITY_LIVE_DEVICE=$live_name" \
      "P9_TARGET_IDENTITY_LIVE_IDCODE=$live_idcode" \
      "P9_TARGET_IDENTITY_LIVE_IDCODE_NORMALIZED=[p9_normal_idcode $live_idcode]"] {
    puts $out $line
    puts $line
  }
  set record_index 0
  foreach record $device_records {
    lassign $record object part name idcode normalized
    set line "P9_TARGET_IDENTITY_ENUM_DEVICE_$record_index=$object|PART=$part|NAME=$name|IDCODE=$idcode|NORMALIZED=$normalized"
    puts $out $line
    puts $line
    incr record_index
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
    puts $out "P9_TARGET_IDENTITY_RESULT=FAIL"
    puts $out "P9_TARGET_IDENTITY_READ_ONLY=1"
    puts $out "P9_TARGET_IDENTITY_HW_OBJECT_COUNT=$all_device_count"
    puts $out "P9_TARGET_IDENTITY_EXACT_FPGA_MATCH_COUNT=$exact_device_count"
    puts $out "P9_TARGET_IDENTITY_AUXILIARY_DAP_COUNT=$auxiliary_device_count"
    puts $out "P9_TARGET_IDENTITY_UNEXPECTED_HW_OBJECT_COUNT=$unexpected_device_count"
    puts $out "P9_TARGET_IDENTITY_ERROR=[string map [list \"\\r\" \" \" \"\\n\" \" \" \"=\" \"_\"] $error_text]"
    set record_index 0
    foreach record $device_records {
      lassign $record object part name idcode normalized
      puts $out "P9_TARGET_IDENTITY_ENUM_DEVICE_$record_index=$object|PART=$part|NAME=$name|IDCODE=$idcode|NORMALIZED=$normalized"
      incr record_index
    }
    close $out
  }
  puts stderr "P9_TARGET_IDENTITY_RESULT=FAIL"
  puts stderr $error_text
  exit 21
}
exit 0
