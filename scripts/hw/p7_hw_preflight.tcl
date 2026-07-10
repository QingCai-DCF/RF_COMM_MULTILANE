# P7 authorization-bound, read-only hardware target preflight.
# require-user-hw-authorization: the outer P7 safe wrapper validates it before
# this script is launched or any hardware connection can occur.
# This script only opens the explicitly named target and reads identity fields.

proc p7_auth_value {text key} {
  foreach raw_line [split $text "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string match "#*" $line]} {
      continue
    }
    set separator [string first "=" $line]
    if {$separator < 1} {
      continue
    }
    set observed_key [string trim [string range $line 0 [expr {$separator - 1}]]]
    if {$observed_key eq $key} {
      return [string trim [string range $line [expr {$separator + 1}] end]]
    }
  }
  return ""
}

proc p7_require_auth_value {text key expected} {
  set observed [p7_auth_value $text $key]
  if {![string equal -nocase $observed $expected]} {
    error "P7 authorization mismatch for $key expected=$expected observed=$observed"
  }
}

proc p7_normal_idcode {value} {
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

set p7_canonical_part "xc7z010clg400-1"
set p7_live_part "xc7z010"
set p7_live_device "xc7z010_1"
set p7_live_idcode "13722093"

set result_file ""
set selected_target ""
set manager_open 0
set server_connected 0
set target_open 0

set rc [catch {
  if {[llength $argv] != 7} {
    error "P7 preflight requires root, authorization, board, part, target, server URL, and result path"
  }
  set root_dir [file normalize [lindex $argv 0]]
  set authorization_file [file normalize [lindex $argv 1]]
  set expected_board_id [lindex $argv 2]
  set expected_part [lindex $argv 3]
  set expected_target [lindex $argv 4]
  set hw_server_url [lindex $argv 5]
  set result_file [file normalize [lindex $argv 6]]

  if {![info exists ::env(RF_COMM_HW_AUTH)] ||
      $::env(RF_COMM_HW_AUTH) ne "P7_STATIONARY_APP_LAYER_APPROVED"} {
    error "RF_COMM_HW_AUTH=P7_STATIONARY_APP_LAYER_APPROVED required"
  }
  if {$expected_board_id eq "" || $expected_part eq "" || $expected_target eq ""} {
    error "P7 preflight board, part, and target must be explicit"
  }
  if {![string equal -nocase $expected_part $p7_canonical_part]} {
    error "P7 preflight supports only canonical part $p7_canonical_part"
  }
  if {![file exists $authorization_file] || ![file isfile $authorization_file]} {
    error "P7 authorization file missing: $authorization_file"
  }
  set authorization_root [file normalize [file join $root_dir .hardware_authorization]]
  set auth_slash [string map {\\ /} $authorization_file]
  set auth_root_slash [string trimright [string map {\\ /} $authorization_root] "/"]
  if {![string match -nocase "${auth_root_slash}/*" $auth_slash]} {
    error "P7 authorization file must be under .hardware_authorization"
  }
  set abort_file [file join $authorization_root ABORT_NOW.txt]
  if {[file exists $abort_file]} {
    error "P7 abort file is present"
  }

  set auth_handle [open $authorization_file r]
  set auth_text [read $auth_handle]
  close $auth_handle
  if {[string first "P7_STATIONARY_APP_LAYER_APPROVED" $auth_text] < 0} {
    error "P7 authorization marker missing"
  }
  p7_require_auth_value $auth_text AUTHORIZED_STAGE P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET
  p7_require_auth_value $auth_text USER_HARDWARE_AUTHORIZATION_FOR_P7 GRANTED
  p7_require_auth_value $auth_text BOARD_ID $expected_board_id
  p7_require_auth_value $auth_text EXPECTED_PART $expected_part
  p7_require_auth_value $auth_text EXPECTED_TARGET $expected_target
  p7_require_auth_value $auth_text SHUTDOWN_ON_EXIT required
  p7_require_auth_value $auth_text NO_ETHERNET true
  p7_require_auth_value $auth_text NO_MOTION true
  p7_require_auth_value $auth_text LANE_COUNT 2
  p7_require_auth_value $auth_text MAX_LANE_MASK 0x3
  set authorized_runtime [p7_auth_value $auth_text MAX_RUNTIME_SEC]
  if {![string is integer -strict $authorized_runtime] ||
      $authorized_runtime < 1 || $authorized_runtime > 1800} {
    error "P7 authorization MAX_RUNTIME_SEC must be in 1..1800"
  }

  open_hw_manager
  set manager_open 1
  connect_hw_server -url $hw_server_url
  set server_connected 1

  set target_matches {}
  foreach candidate [get_hw_targets -quiet *] {
    set candidate_text [string trim "$candidate"]
    if {[string equal -nocase $candidate_text $expected_target]} {
      lappend target_matches $candidate
    }
  }
  if {[llength $target_matches] != 1} {
    error "P7 expected exactly one authorized target match; found [llength $target_matches]"
  }
  set selected_target [lindex $target_matches 0]
  if {[string first [string tolower $expected_board_id] [string tolower "$selected_target"]] < 0} {
    error "P7 selected target does not contain authorized board id"
  }
  current_hw_target $selected_target
  open_hw_target $selected_target
  set target_open 1

  set device_matches {}
  foreach candidate [get_hw_devices -quiet *] {
    set candidate_part ""
    set candidate_name ""
    set candidate_idcode ""
    catch {set candidate_part [get_property PART $candidate]}
    catch {set candidate_name [get_property NAME $candidate]}
    catch {set candidate_idcode [get_property IDCODE $candidate]}
    if {[string equal -nocase $candidate_part $p7_live_part] &&
        [string equal -nocase $candidate_name $p7_live_device] &&
        [p7_normal_idcode $candidate_idcode] eq $p7_live_idcode} {
      lappend device_matches $candidate
    }
  }
  if {[llength $device_matches] != 1} {
    error "P7 expected exactly one canonical live part/device/IDCODE match; found [llength $device_matches]"
  }
  set selected_device [lindex $device_matches 0]
  current_hw_device $selected_device
  set selected_part [get_property PART $selected_device]
  set selected_name [get_property NAME $selected_device]
  set selected_idcode "UNKNOWN"
  catch {set selected_idcode [get_property IDCODE $selected_device]}

  set output [open $result_file w]
  foreach line [list \
      "P7_HW_PREFLIGHT_AUTHORIZED=1" \
      "P7_HW_PREFLIGHT_READ_ONLY=1" \
      "P7_HW_PREFLIGHT_BOARD_ID=$expected_board_id" \
      "P7_HW_PREFLIGHT_TARGET=$selected_target" \
      "P7_HW_PREFLIGHT_DEVICE=$selected_name" \
      "P7_HW_PREFLIGHT_PART=$expected_part" \
      "P7_HW_PREFLIGHT_IDCODE=$selected_idcode" \
      "P7_HW_PREFLIGHT_CANONICAL_PART=$expected_part" \
      "P7_HW_PREFLIGHT_LIVE_PART=$selected_part" \
      "P7_HW_PREFLIGHT_LIVE_DEVICE=$selected_name" \
      "P7_HW_PREFLIGHT_LIVE_IDCODE=$selected_idcode" \
      "P7_HW_PREFLIGHT_RESULT=PASS"] {
    puts $output $line
    puts $line
  }
  close $output
} error_text error_options]

if {$target_open} {
  catch {close_hw_target $selected_target}
}
if {$server_connected} {
  catch {disconnect_hw_server}
}
if {$manager_open} {
  catch {close_hw_manager}
}

if {$rc != 0} {
  if {$result_file ne ""} {
    catch {
      set failure_output [open $result_file w]
      puts $failure_output "P7_HW_PREFLIGHT_AUTHORIZED=0"
      puts $failure_output "P7_HW_PREFLIGHT_READ_ONLY=1"
      puts $failure_output "P7_HW_PREFLIGHT_RESULT=FAIL"
      puts $failure_output "P7_HW_PREFLIGHT_ERROR=$error_text"
      close $failure_output
    }
  }
  puts stderr "P7_HW_PREFLIGHT_RESULT=FAIL"
  puts stderr "P7_HW_PREFLIGHT_ERROR=$error_text"
  exit 21
}
exit 0
