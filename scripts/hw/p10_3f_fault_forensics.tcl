# Read/commit/explicitly-clear P10.3F first-fault evidence without reprogramming.
#
# This script never runs an ELF and never issues an FPGA programming command.
# Capture requests functional full shutdown first, then reads the persistent PL
# record.  The outer safe wrapper may program the independent shutdown image
# only after capture and archive commit finish (or after a bounded archive
# failure, because hardware safety takes precedence over evidence retention).

set p10_ff_base 0x43C00000
set p10_ff_register_map_version 0x0A000003
set p10_ff_register_map_hash_low 0x5072E5AE

proc p10ff_say {line} {
  global p10ff_result_handle
  puts $p10ff_result_handle $line
  flush $p10ff_result_handle
  puts $line
  flush stdout
}

proc p10ff_select {target_id} {
  global p10ff_active_target
  if {$p10ff_active_target != $target_id} {
    targets $target_id
    set p10ff_active_target $target_id
  }
}

proc p10ff_read32 {role offset} {
  global p10ff_apu p10_ff_base
  p10ff_select $p10ff_apu($role)
  return [expr {[mrd -address-space AP0 -force -value \
      [expr {$p10_ff_base + $offset}]] & 0xFFFFFFFF}]
}

proc p10ff_write32 {role offset value} {
  global p10ff_apu p10_ff_base
  p10ff_select $p10ff_apu($role)
  mwr -address-space AP0 -force -bypass-cache-sync \
      [expr {$p10_ff_base + $offset}] $value
}

proc p10ff_classify {records serial} {
  set apu {}
  set fpga {}
  foreach props $records {
    if {![dict exists $props name] || ![dict exists $props target_id] ||
        ![dict exists $props jtag_cable_serial] ||
        ![string equal -nocase [dict get $props jtag_cable_serial] $serial]} {
      continue
    }
    set name [dict get $props name]
    if {[string equal -nocase $name APU]} {
      lappend apu [dict get $props target_id]
    }
    if {[string equal -nocase $name xc7z020]} {
      lappend fpga [dict get $props target_id]
    }
  }
  return [list [lsort -unique $apu] [lsort -unique $fpga]]
}

proc p10ff_wait_targets {} {
  global p10ff_fixed_serial p10ff_rotating_serial p10ff_apu p10ff_fpga
  for {set attempt 1} {$attempt <= 51} {incr attempt} {
    set records [targets -target-properties]
    set fixed [p10ff_classify $records $p10ff_fixed_serial]
    set rotating [p10ff_classify $records $p10ff_rotating_serial]
    set all_fpga_serials {}
    foreach props $records {
      if {[dict exists $props name] &&
          [string equal -nocase [dict get $props name] xc7z020] &&
          [dict exists $props jtag_cable_serial]} {
        lappend all_fpga_serials [dict get $props jtag_cable_serial]
      }
    }
    if {[llength [lindex $fixed 0]] == 1 &&
        [llength [lindex $fixed 1]] == 1 &&
        [llength [lindex $rotating 0]] == 1 &&
        [llength [lindex $rotating 1]] == 1 &&
        [lsort -unique $all_fpga_serials] eq
            [lsort [list $p10ff_fixed_serial $p10ff_rotating_serial]]} {
      set p10ff_apu(fixed) [lindex [lindex $fixed 0] 0]
      set p10ff_fpga(fixed) [lindex [lindex $fixed 1] 0]
      set p10ff_apu(rotating) [lindex [lindex $rotating 0] 0]
      set p10ff_fpga(rotating) [lindex [lindex $rotating 1] 0]
      p10ff_say "P10_FF_TARGET_DISCOVERY=PASS"
      return
    }
    after 100
  }
  error "P10.3F exact two-board JTAG binding unavailable"
}

proc p10ff_verify_identity {role expected_build} {
  global p10_ff_register_map_version p10_ff_register_map_hash_low
  set identity [p10ff_read32 $role 0x0700]
  set build [p10ff_read32 $role 0x0704]
  set version [p10ff_read32 $role 0x070C]
  set hash_low [p10ff_read32 $role 0x0710]
  if {$identity != 0x5031305A || $build != $expected_build ||
      $version != $p10_ff_register_map_version ||
      $hash_low != $p10_ff_register_map_hash_low} {
    error [format "P10.3F %s identity mismatch id=0x%08X build=0x%08X map=0x%08X hash=0x%08X" \
        $role $identity $build $version $hash_low]
  }
}

proc p10ff_wait_frozen_tail {role} {
  set deadline [expr {[clock milliseconds] + 1000}]
  set status [p10ff_read32 $role 0x0D14]
  while {($status & 0x1) != 0 && ($status & 0x2) == 0 &&
         [clock milliseconds] < $deadline} {
    after 1
    set status [p10ff_read32 $role 0x0D14]
  }
  if {($status & 0x1) != 0 && ($status & 0x2) == 0} {
    error "P10.3F $role post-fault tail did not complete"
  }
  return $status
}

# On a host/JTAG timeout or wrapper exception the PL may still have an active
# object without having raised its own safety fault.  Before reading any frozen
# snapshot/event word, atomically request the implemented terminal-object abort
# on both endpoints, verify persistent kill/full shutdown, and prove that no
# final physical-TX counter advances for a bounded interval.  An already-frozen
# first fault is never overwritten.
proc p10ff_abort_before_capture {out_dir} {
  set abort_requested {}
  foreach role {fixed rotating} {
    set status [p10ff_read32 $role 0x0D14]
    if {($status & 1) == 0} {
      p10ff_write32 $role 0x0718 0x00000020
      lappend abort_requested $role
    }
  }
  set deadline [expr {[clock milliseconds] + 1000}]
  set ready 0
  while {[clock milliseconds] < $deadline} {
    set ready 1
    foreach role {fixed rotating} {
      set status [p10ff_read32 $role 0x0D14]
      if {($status & 0x000001C3) != 0x000001C3} { set ready 0 }
    }
    if {$ready} { break }
    after 1
  }
  if {!$ready} {
    error "P10.3F emergency abort did not reach frozen kill/full shutdown"
  }
  set before_counts {}
  foreach role {fixed rotating} {
    set values {}
    foreach offset {0x07E4 0x07E8 0x07EC 0x07F0} {
      lappend values [p10ff_read32 $role $offset]
    }
    dict set before_counts $role $values
  }
  after 10
  set direct [file join $out_dir "emergency_abort_before_forensic_read.psv"]
  set handle [open $direct w]
  puts $handle "role|ff_status|fault_cause|effective_tx_enable_mask|physical_tx_counts_before|physical_tx_counts_after"
  foreach role {fixed rotating} {
    set after_counts {}
    foreach offset {0x07E4 0x07E8 0x07EC 0x07F0} {
      lappend after_counts [p10ff_read32 $role $offset]
    }
    set status [p10ff_read32 $role 0x0D14]
    set cause [p10ff_read32 $role 0x0D24]
    set effective [expr {[p10ff_read32 $role 0x0424] & 0xF}]
    set prior [dict get $before_counts $role]
    puts $handle [join [list $role [format "0x%08X" $status] \
        [format "0x%08X" $cause] [format "0x%X" $effective] \
        [join $prior ,] [join $after_counts ,]] "|"]
    # Preserve a pre-existing first fault, whatever its original cause.  Only
    # endpoints that were unfrozen when this procedure began must report the
    # terminal-object-abort cause that we just requested.
    set cause_ok [expr {[lsearch -exact $abort_requested $role] < 0 ||
        ($cause & 0x10) != 0}]
    if {($status & 0x000001C3) != 0x000001C3 || !$cause_ok ||
        $effective != 0 || $after_counts ne $prior} {
      close $handle
      error "P10.3F emergency abort pre-read safety evidence failed for $role"
    }
  }
  close $handle
  p10ff_say "P10_FF_ABORT_BEFORE_CAPTURE=PASS"
  p10ff_say "P10_FF_ABORT_DIRECT_EVIDENCE=$direct"
}

proc p10ff_capture_role {role expected_build out_dir} {
  p10ff_verify_identity $role $expected_build
  # Full shutdown is requested before any evidence read.  Frozen safety state
  # already holds kill/shutdown; this request also safely handles NO_FAULT.
  p10ff_write32 $role 0x0718 0x0000001A
  after 10
  set status [p10ff_wait_frozen_tail $role]
  if {($status & 0x180) != 0x180} {
    error [format "P10.3F %s not in full shutdown/kill status=0x%08X" $role $status]
  }
  set caps [p10ff_read32 $role 0x0D10]
  set snapshot_words [expr {$caps & 0xFF}]
  set event_words [expr {($caps >> 8) & 0xFF}]
  set lane_count [expr {($caps >> 16) & 0xF}]
  set module_count [expr {($caps >> 20) & 0xF}]
  if {($caps >> 24) != 0x46 || $snapshot_words != 64 ||
      $event_words != 8 || $lane_count != 4 || $module_count != 4} {
    error [format "P10.3F %s capability mismatch 0x%08X" $role $caps]
  }
  set frozen [expr {($status & 1) != 0}]
  set sequence [p10ff_read32 $role 0x0D18]
  set timestamp_low [p10ff_read32 $role 0x0D1C]
  set timestamp_high [p10ff_read32 $role 0x0D20]
  set cause [p10ff_read32 $role 0x0D24]
  set pre_count [expr {$frozen ? [p10ff_read32 $role 0x0D2C] : 0}]
  set post_count [expr {$frozen ? [p10ff_read32 $role 0x0D30] : 0}]
  set total_count [expr {$frozen ? [p10ff_read32 $role 0x0D34] : 0}]
  set event_depth [p10ff_read32 $role 0x0D38]
  if {$pre_count + $post_count != $total_count || $total_count > $event_depth} {
    error "P10.3F $role event dimensions are inconsistent"
  }
  set output [file join $out_dir "${role}.p10ff.psv"]
  set handle [open $output w]
  puts $handle "P10_FF_PSV|1|$role"
  foreach {name value} [list \
      capabilities $caps status $status fault_sequence $sequence \
      fault_timestamp_low $timestamp_low fault_timestamp_high $timestamp_high \
      fault_cause $cause snapshot_words $snapshot_words \
      pre_event_count $pre_count post_event_count $post_count \
      total_event_count $total_count event_depth $event_depth \
      event_words $event_words] {
    puts $handle [format "META|%s|0x%08X" $name $value]
  }
  if {$frozen} {
    for {set index 0} {$index < $snapshot_words} {incr index} {
      p10ff_write32 $role 0x0D3C $index
      set value [p10ff_read32 $role 0x0D40]
      puts $handle [format "SNAPSHOT|%d|0x%08X" $index $value]
    }
    for {set entry 0} {$entry < $total_count} {incr entry} {
      p10ff_write32 $role 0x0D44 $entry
      for {set word 0} {$word < $event_words} {incr word} {
        p10ff_write32 $role 0x0D48 $word
        set value [p10ff_read32 $role 0x0D4C]
        puts $handle [format "EVENT|%d|%d|0x%08X" $entry $word $value]
      }
    }
  }
  puts $handle "END|$role"
  close $handle
  set final_status [p10ff_read32 $role 0x0D14]
  if {$frozen && ($final_status & 0x0F) != 0x0F} {
    error [format "P10.3F %s ordered-read interlock incomplete status=0x%08X" \
        $role $final_status]
  }
  set capture_state [expr {$frozen ? "FROZEN" : "NO_FAULT"}]
  p10ff_say "P10_FF_CAPTURE_[string toupper $role]=$capture_state"
  p10ff_say "P10_FF_PSV_[string toupper $role]=$output"
}

proc p10ff_digest_word {digest index} {
  set first [expr {$index * 8}]
  set text [string range $digest $first [expr {$first + 7}]]
  set reversed "[string range $text 6 7][string range $text 4 5][string range $text 2 3][string range $text 0 1]"
  scan $reversed %x value
  # Tcl 8.5 returns an eight-hex-digit %x value as a signed 32-bit integer
  # when bit 31 is set, while forced AXI readback is normalized to an
  # unsigned bignum.  Normalize both sides of the archive-digest contract.
  return [expr {$value & 0xFFFFFFFF}]
}

proc p10ff_sanitize_error {text} {
  return [string map [list "\n" " " "\r" " " "=" "_"] $text]
}

proc p10ff_commit_role {role expected_build digest} {
  if {$digest eq "NONE"} {
    p10ff_verify_identity $role $expected_build
    set status [p10ff_read32 $role 0x0D14]
    if {($status & 1) != 0} {
      error "P10.3F $role is frozen but no archive digest was supplied"
    }
    p10ff_say "P10_FF_ARCHIVE_COMMITTED_[string toupper $role]=NO_FAULT"
    return
  }
  if {![regexp {^[0-9A-Fa-f]{64}$} $digest]} {
    error "P10.3F $role invalid SHA256"
  }
  p10ff_verify_identity $role $expected_build
  set status [p10ff_read32 $role 0x0D14]
  if {($status & 0x1CF) != 0x1CF} {
    error [format "P10.3F %s cannot commit incomplete/unsafe archive status=0x%08X" \
        $role $status]
  }
  for {set index 0} {$index < 8} {incr index} {
    set word [p10ff_digest_word $digest $index]
    p10ff_write32 $role [expr {0x0D50 + 4*$index}] $word
    if {[p10ff_read32 $role [expr {0x0D50 + 4*$index}]] != $word} {
      error "P10.3F $role digest readback mismatch at word $index"
    }
  }
  p10ff_write32 $role 0x0D70 0x41524348
  set status [p10ff_read32 $role 0x0D14]
  if {($status & 0x10) == 0} {
    error [format "P10.3F %s archive commit rejected status=0x%08X" $role $status]
  }
  p10ff_say "P10_FF_ARCHIVE_COMMITTED_[string toupper $role]=1"
}

proc p10ff_clear_role {role expected_build digest} {
  p10ff_commit_role $role $expected_build $digest
  p10ff_write32 $role 0x0D74 0x46524F5A
  p10ff_write32 $role 0x0D74 0x434C5241
  set status [p10ff_read32 $role 0x0D14]
  if {($status & 0x1) != 0 || ($status & 0x180) != 0x180} {
    error [format "P10.3F %s explicit clear failed or left shutdown status=0x%08X" \
        $role $status]
  }
  p10ff_say "P10_FF_EXPLICIT_CLEAR_[string toupper $role]=1"
}

if {[llength $argv] == 1 && [lindex $argv 0] eq "selftest"} {
  set digest 0761622f98b9f890cae1b34637215986cfac0a7a85568a2c171cdabe3d33ab5c
  set expected {
    0x2F626107 0x90F8B998 0x46B3E1CA 0x86592137
    0x7A0AACCF 0x2C8A5685 0xBEDA1C17 0x5CAB333D
  }
  for {set index 0} {$index < 8} {incr index} {
    set actual [p10ff_digest_word $digest $index]
    if {$actual != [lindex $expected $index] || $actual < 0} {
      error [format "digest self-test failed at word %d: 0x%08X" $index $actual]
    }
  }
  if {[p10ff_sanitize_error "line1\nline=2"] ne "line1 line_2"} {
    error "error sanitizer self-test failed"
  }
  puts "P10_FF_TCL_SELFTEST=PASS"
  exit 0
}

if {[llength $argv] < 10 || [llength $argv] > 12} {
  puts stderr "usage: p10_3f_fault_forensics.tcl MODE URL FIXED_SERIAL ROTATING_SERIAL OUT_DIR AUTH RUN_ID FIXED_BUILD ROTATING_BUILD RESULT ?FIXED_SHA ROTATING_SHA?"
  exit 2
}
set p10ff_mode [string tolower [lindex $argv 0]]
set p10ff_url [lindex $argv 1]
set p10ff_fixed_serial [lindex $argv 2]
set p10ff_rotating_serial [lindex $argv 3]
set p10ff_out_dir [file normalize [lindex $argv 4]]
set p10ff_auth [file normalize [lindex $argv 5]]
set p10ff_run_id [lindex $argv 6]
set p10ff_expected_build(fixed) [lindex $argv 7]
set p10ff_expected_build(rotating) [lindex $argv 8]
set p10ff_result [file normalize [lindex $argv 9]]
set p10ff_digest(fixed) ""
set p10ff_digest(rotating) ""
if {[llength $argv] > 10} { set p10ff_digest(fixed) [lindex $argv 10] }
if {[llength $argv] > 11} { set p10ff_digest(rotating) [lindex $argv 11] }
set p10ff_active_target -1
set p10ff_connected 0
file mkdir $p10ff_out_dir
file mkdir [file dirname $p10ff_result]
set p10ff_result_handle [open $p10ff_result w]

set rc [catch {
  if {$p10ff_mode ni {capture abort_capture commit clear}} {
    error "invalid P10.3F forensic mode"
  }
  if {![regexp {^p10_3f_[A-Za-z0-9_.-]+$} $p10ff_run_id]} {
    error "unsafe P10.3F run ID"
  }
  if {![file isfile $p10ff_auth]} { error "P10.3F current-run authorization missing" }
  if {![info exists ::env(RF_COMM_P10_HW_AUTH)] ||
      $::env(RF_COMM_P10_HW_AUTH) ne "P10_3F_IMMUTABLE_AUTHORIZED"} {
    error "P10.3F immutable current-run environment marker required"
  }
  if {$p10ff_fixed_serial eq $p10ff_rotating_serial} {
    error "P10.3F board serials are ambiguous"
  }
  connect -url $p10ff_url
  set p10ff_connected 1
  p10ff_wait_targets
  if {$p10ff_mode eq "abort_capture"} {
    p10ff_abort_before_capture $p10ff_out_dir
    p10ff_capture_role fixed $p10ff_expected_build(fixed) $p10ff_out_dir
    p10ff_capture_role rotating $p10ff_expected_build(rotating) $p10ff_out_dir
  } elseif {$p10ff_mode eq "capture"} {
    p10ff_capture_role fixed $p10ff_expected_build(fixed) $p10ff_out_dir
    p10ff_capture_role rotating $p10ff_expected_build(rotating) $p10ff_out_dir
  } elseif {$p10ff_mode eq "commit"} {
    p10ff_commit_role fixed $p10ff_expected_build(fixed) $p10ff_digest(fixed)
    p10ff_commit_role rotating $p10ff_expected_build(rotating) $p10ff_digest(rotating)
  } else {
    p10ff_clear_role fixed $p10ff_expected_build(fixed) $p10ff_digest(fixed)
    p10ff_clear_role rotating $p10ff_expected_build(rotating) $p10ff_digest(rotating)
  }
  p10ff_say "P10_FF_FORENSIC_RESULT=PASS"
} error_text]

if {$rc != 0} {
  foreach role {fixed rotating} {
    catch {p10ff_write32 $role 0x0718 0x0000001A}
  }
  p10ff_say "P10_FF_FORENSIC_RESULT=FAIL"
  set p10ff_error_sanitized [p10ff_sanitize_error $error_text]
  p10ff_say "P10_FF_FORENSIC_ERROR=$p10ff_error_sanitized"
}
catch {close $p10ff_result_handle}
if {$p10ff_connected} { catch {disconnect} }
if {$rc != 0} {
  puts stderr $error_text
  exit 42
}
exit 0
