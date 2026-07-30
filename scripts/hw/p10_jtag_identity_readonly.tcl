# P10 read-only dual-AX7020 JTAG identity inventory.
# require-user-hw-authorization --allow-hardware
#
# The only target-side operations in this script are the read-only inventory
# commands
#   jtag targets -target-properties
#   targets -target-properties
# after a local hw_server connection.  It never selects a debug target,
# changes reset state, configures PL, accesses memory, starts an ELF, or writes
# UART/TFDU state.

proc p10_clean {value} {
  return [string map [list "\r" " " "\n" " " "=" ":"] [string trim $value]]
}

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

proc p10_emit {key value} {
  global p10_result_handle
  set line "${key}=[p10_clean $value]"
  puts $p10_result_handle $line
  flush $p10_result_handle
  puts $line
}

if {$argc != 2} {
  puts stderr "usage: p10_jtag_identity_readonly.tcl <xsdb-url> <result-path>"
  exit 2
}

set p10_xsdb_url [lindex $argv 0]
set p10_result_path [file normalize [lindex $argv 1]]
file mkdir [file dirname $p10_result_path]
set p10_result_handle [open $p10_result_path w]
fconfigure $p10_result_handle -encoding utf-8 -translation lf

p10_emit P10_JTAG_IDENTITY_SCHEMA 1
p10_emit P10_JTAG_IDENTITY_READ_ONLY 1
p10_emit P10_JTAG_MUTATING_COMMANDS_EXECUTED 0
p10_emit P10_JTAG_XSDB_URL $p10_xsdb_url

set p10_connected 0
set p10_status INCOMPLETE
set p10_error ""
set p10_records {}
set p10_debug_records {}

set p10_catch_code [catch {
  connect -url $p10_xsdb_url
  set p10_connected 1
  set p10_records [jtag targets -target-properties]
  set p10_debug_records [targets -target-properties]
} p10_error p10_options]

if {$p10_catch_code != 0} {
  p10_emit P10_JTAG_IDENTITY_RESULT FAIL
  p10_emit P10_JTAG_IDENTITY_ERROR $p10_error
  if {$p10_connected} { catch {disconnect} }
  p10_emit P10_JTAG_DISCONNECTED 1
  close $p10_result_handle
  exit 1
}

set p10_cable_serials {}
set p10_current_serial ""
set p10_device_count 0
set p10_record_count 0
array set p10_zynq_counts {}
array set p10_dap_counts {}
array set p10_other_counts {}

foreach p10_props $p10_records {
  incr p10_record_count
  p10_emit P10_JTAG_RECORD_${p10_record_count} $p10_props

  set p10_level ""
  if {[dict exists $p10_props level]} {
    set p10_level [dict get $p10_props level]
  }
  if {$p10_level ne "" && $p10_level == 0 &&
      [dict exists $p10_props jtag_cable_serial]} {
    set p10_current_serial [dict get $p10_props jtag_cable_serial]
    lappend p10_cable_serials $p10_current_serial
    set p10_zynq_counts($p10_current_serial) 0
    set p10_dap_counts($p10_current_serial) 0
    set p10_other_counts($p10_current_serial) 0
    set p10_index [llength $p10_cable_serials]
    p10_emit P10_JTAG_CABLE_${p10_index}_SERIAL $p10_current_serial
    continue
  }

  if {![dict exists $p10_props name] || ![dict exists $p10_props idcode]} {
    continue
  }
  incr p10_device_count
  set p10_name [dict get $p10_props name]
  set p10_idcode [p10_normal_idcode [dict get $p10_props idcode]]
  set p10_device_serial $p10_current_serial
  if {[dict exists $p10_props jtag_cable_serial]} {
    set p10_device_serial [dict get $p10_props jtag_cable_serial]
  }
  p10_emit P10_JTAG_DEVICE_${p10_device_count}_CABLE_SERIAL $p10_device_serial
  p10_emit P10_JTAG_DEVICE_${p10_device_count}_NAME $p10_name
  p10_emit P10_JTAG_DEVICE_${p10_device_count}_IDCODE $p10_idcode
  if {[dict exists $p10_props node_id]} {
    p10_emit P10_JTAG_DEVICE_${p10_device_count}_NODE_ID [dict get $p10_props node_id]
  }

  if {$p10_device_serial eq "" || ![info exists p10_zynq_counts($p10_device_serial)]} {
    continue
  }
  if {[string equal -nocase $p10_name xc7z020] && $p10_idcode eq "23727093"} {
    incr p10_zynq_counts($p10_device_serial)
  } elseif {[string equal -nocase $p10_name arm_dap] && $p10_idcode eq "4BA00477"} {
    incr p10_dap_counts($p10_device_serial)
  } else {
    incr p10_other_counts($p10_device_serial)
  }
}

set p10_cable_count [llength $p10_cable_serials]
set p10_distinct_serials [lsort -unique $p10_cable_serials]
set p10_topology_ok [expr {$p10_cable_count == 2 &&
    [llength $p10_distinct_serials] == 2}]

p10_emit P10_JTAG_RECORD_COUNT $p10_record_count
p10_emit P10_JTAG_CABLE_COUNT $p10_cable_count
p10_emit P10_JTAG_DISTINCT_CABLE_COUNT [llength $p10_distinct_serials]
p10_emit P10_JTAG_DEVICE_COUNT $p10_device_count

set p10_debug_record_count 0
foreach p10_props $p10_debug_records {
  incr p10_debug_record_count
  p10_emit P10_JTAG_DEBUG_RECORD_${p10_debug_record_count} $p10_props
}
p10_emit P10_JTAG_DEBUG_RECORD_COUNT $p10_debug_record_count

foreach p10_serial $p10_distinct_serials {
  if {![info exists p10_zynq_counts($p10_serial)]} {
    set p10_topology_ok 0
    continue
  }
  p10_emit P10_JTAG_CABLE_${p10_serial}_XC7Z020_COUNT $p10_zynq_counts($p10_serial)
  p10_emit P10_JTAG_CABLE_${p10_serial}_ARM_DAP_COUNT $p10_dap_counts($p10_serial)
  p10_emit P10_JTAG_CABLE_${p10_serial}_OTHER_DEVICE_COUNT $p10_other_counts($p10_serial)
  if {$p10_zynq_counts($p10_serial) != 1 ||
      $p10_dap_counts($p10_serial) != 1 ||
      $p10_other_counts($p10_serial) != 0} {
    set p10_topology_ok 0
  }
}

if {$p10_topology_ok} {
  set p10_status PASS
}
p10_emit P10_JTAG_IDENTITY_RESULT $p10_status

if {$p10_connected} { catch {disconnect} }
p10_emit P10_JTAG_DISCONNECTED 1
close $p10_result_handle

if {$p10_status eq "PASS"} {
  exit 0
}
exit 3
