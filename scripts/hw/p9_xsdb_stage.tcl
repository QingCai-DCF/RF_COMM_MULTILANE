# P9 Z7010 one-stage XSDB executor.
#
# Every invocation programs the immutable candidate, boots the immutable PS
# ELF, executes exactly one fixed-plan P9 stage, submits an endpoint shutdown
# command, and exits.  The outer Python wrapper independently programs the
# immutable shutdown bitstream before and after this process and on every
# exception/timeout/Ctrl+C path.
# require-user-hw-authorization: this file is reachable only after phase-2
# immutable authorization validation and checks RF_COMM_P9_HW_AUTH itself.

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

proc p9_select_jtag_identity {records board_id} {
  set cable_roots {}
  set cable_matches {}
  set device_nodes {}
  set device_matches {}
  set dap_matches {}
  foreach props $records {
    if {[dict exists $props jtag_cable_serial] &&
        [dict exists $props level] && [dict get $props level] == 0} {
      lappend cable_roots $props
      if {[string equal -nocase [dict get $props jtag_cable_serial] $board_id]} {
        lappend cable_matches $props
      }
    }
    if {![dict exists $props idcode] || ![dict exists $props name]} { continue }
    lappend device_nodes $props
    if {[string equal -nocase [dict get $props name] xc7z010] &&
        [p9_normal_idcode [dict get $props idcode]] eq "13722093" &&
        [dict exists $props node_id]} {
      lappend device_matches $props
    }
    if {[string equal -nocase [dict get $props name] arm_dap] &&
        [p9_normal_idcode [dict get $props idcode]] eq "4BA00477" &&
        [dict exists $props node_id]} {
      lappend dap_matches $props
    }
  }
  if {[llength $cable_roots] != 1 || [llength $cable_matches] != 1} {
    error "P9 XSDB requires exactly one authorized cable root"
  }
  if {[llength $device_nodes] != 2 || [llength $device_matches] != 1 ||
      [llength $dap_matches] != 1} {
    error "P9 XSDB requires exactly one canonical ARM-DAP plus Zynq-7010 JTAG chain"
  }
  return [dict create cable [lindex $cable_matches 0] \
      device [lindex $device_matches 0] cable_roots $cable_roots \
      cable_matches $cable_matches device_nodes $device_nodes \
      exact_device_matches $device_matches exact_dap_matches $dap_matches]
}

proc p9_jtag_topology_counts {records board_id} {
  set cable_roots 0; set cable_matches 0; set device_nodes 0
  set device_matches 0; set dap_matches 0
  foreach props $records {
    if {[dict exists $props jtag_cable_serial] &&
        [dict exists $props level] && [dict get $props level] == 0} {
      incr cable_roots
      if {[string equal -nocase [dict get $props jtag_cable_serial] $board_id]} {
        incr cable_matches
      }
    }
    if {![dict exists $props idcode] || ![dict exists $props name]} { continue }
    incr device_nodes
    if {[string equal -nocase [dict get $props name] xc7z010] &&
        [p9_normal_idcode [dict get $props idcode]] eq "13722093" &&
        [dict exists $props node_id]} {
      incr device_matches
    }
    if {[string equal -nocase [dict get $props name] arm_dap] &&
        [p9_normal_idcode [dict get $props idcode]] eq "4BA00477" &&
        [dict exists $props node_id]} {
      incr dap_matches
    }
  }
  return [dict create cable_roots $cable_roots cable_matches $cable_matches \
      device_nodes $device_nodes device_matches $device_matches dap_matches $dap_matches]
}

proc p9_wait_jtag_identity {board_id {max_attempts 51} {delay_ms 100}} {
  if {![string is integer -strict $max_attempts] || $max_attempts < 1 ||
      ![string is integer -strict $delay_ms] || $delay_ms < 0} {
    error "invalid P9 JTAG discovery bound"
  }
  set started_ms [clock milliseconds]
  set last_counts [dict create cable_roots 0 cable_matches 0 device_nodes 0 \
      device_matches 0 dap_matches 0]
  for {set attempt 1} {$attempt <= $max_attempts} {incr attempt} {
    set records [jtag targets -target-properties]
    set last_counts [p9_jtag_topology_counts $records $board_id]
    set roots [dict get $last_counts cable_roots]
    set root_matches [dict get $last_counts cable_matches]
    set devices [dict get $last_counts device_nodes]
    set zynq_matches [dict get $last_counts device_matches]
    set dap_matches [dict get $last_counts dap_matches]

    # A second/wrong cable or an ambiguous/extra JTAG device is a hard
    # authorization failure, never a discovery condition to wait through.
    if {$roots > 1 || ($roots == 1 && $root_matches != 1) ||
        $devices > 2 || $zynq_matches > 1 || $dap_matches > 1 ||
        ($devices == 2 && ($zynq_matches != 1 || $dap_matches != 1))} {
      error "P9 XSDB unauthorized or ambiguous JTAG topology: $last_counts"
    }
    if {![catch {p9_select_jtag_identity $records $board_id} identity]} {
      dict set identity discovery_attempts $attempt
      dict set identity discovery_elapsed_ms [expr {[clock milliseconds] - $started_ms}]
      return $identity
    }
    if {$attempt < $max_attempts && $delay_ms > 0} { after $delay_ms }
  }
  error "P9 XSDB JTAG discovery timeout after $max_attempts attempts: $last_counts"
}

proc p9_unique_targets_by_id {records} {
  set result {}; set seen [dict create]
  foreach props $records {
    if {![dict exists $props target_id]} { error "debug target lacks target_id" }
    set id [dict get $props target_id]
    if {![string is integer -strict $id] || $id < 0} { error "invalid debug target_id" }
    if {[dict exists $seen $id]} { continue }
    dict set seen $id 1
    lappend result $props
  }
  return $result
}

proc p9_classify_targets {records device_id board_id} {
  set dap {}; set apu {}; set fpga {}; set cpu0 {}
  foreach props $records {
    if {![dict exists $props name] || ![dict exists $props target_id]} { continue }
    set name [dict get $props name]
    if {[string match -nocase "*DAP*" $name]} { lappend dap $props }
    if {[string equal -nocase $name APU]} { lappend apu $props }
    if {[string equal -nocase $name xc7z010] &&
        [dict exists $props jtag_device_id] && [dict get $props jtag_device_id] == $device_id &&
        [dict exists $props jtag_cable_serial] &&
        [string equal -nocase [dict get $props jtag_cable_serial] $board_id]} {
      lappend fpga $props
    }
    if {[string match -nocase "*Cortex-A9*#0" $name]} { lappend cpu0 $props }
  }
  return [dict create dap [p9_unique_targets_by_id $dap] \
      apu [p9_unique_targets_by_id $apu] fpga [p9_unique_targets_by_id $fpga] \
      cpu0 [p9_unique_targets_by_id $cpu0]]
}

proc p9_wait_debug_targets {device_id board_id {max_attempts 51} {delay_ms 100}} {
  if {![string is integer -strict $max_attempts] || $max_attempts < 1 ||
      ![string is integer -strict $delay_ms] || $delay_ms < 0} {
    error "invalid P9 debug-target discovery bound"
  }
  set started_ms [clock milliseconds]
  set last_counts [dict create dap 0 apu 0 fpga 0 cpu0 0]
  for {set attempt 1} {$attempt <= $max_attempts} {incr attempt} {
    set debug [p9_classify_targets [targets -target-properties] $device_id $board_id]
    set dap_count [llength [dict get $debug dap]]
    set apu_count [llength [dict get $debug apu]]
    set fpga_count [llength [dict get $debug fpga]]
    set cpu_count [llength [dict get $debug cpu0]]
    set last_counts [dict create dap $dap_count apu $apu_count \
        fpga $fpga_count cpu0 $cpu_count]

    # Missing descendants are a bounded discovery condition immediately after
    # hw_server connect.  Any duplicate authorized FPGA/CPU/reset target is an
    # ambiguity and must fail closed without waiting for it to disappear.
    if {$dap_count > 1 || $apu_count > 1 || $fpga_count > 1 || $cpu_count > 1} {
      error "P9 XSDB ambiguous debug-target topology: $last_counts"
    }
    set reset_unique [expr {$dap_count == 1 || ($dap_count == 0 && $apu_count == 1)}]
    if {$fpga_count == 1 && $cpu_count == 1 && $reset_unique} {
      dict set debug discovery_attempts $attempt
      dict set debug discovery_elapsed_ms [expr {[clock milliseconds] - $started_ms}]
      return $debug
    }
    if {$attempt < $max_attempts && $delay_ms > 0} { after $delay_ms }
  }
  error "P9 XSDB debug-target discovery timeout after $max_attempts attempts: $last_counts"
}

proc p9_read32 {address} {
  return [expr {[mrd -value $address] & 0xFFFFFFFF}]
}

proc p9_read32_force {address} {
  return [expr {[mrd -force -value $address] & 0xFFFFFFFF}]
}

proc p9_check_abort {} {
  global abort_file
  if {[file exists $abort_file]} {
    catch {mwr 0x43C00718 0x0000001A}
    error "P9 abort sentinel observed"
  }
}

proc p9_say {line} {
  global result_handle
  puts $result_handle $line
  flush $result_handle
  puts $line
  flush stdout
}

proc p9_dump_mailbox {label} {
  global dump_dir
  if {![regexp {^[A-Za-z0-9_.-]+$} $label]} { error "unsafe P9 case label" }
  set final [file join $dump_dir "${label}.bin"]
  set partial "${final}.partial"
  catch {file delete -force $partial}
  catch {stop}
  mrd -size b -bin -file $partial 0x00020000 1024
  if {![file isfile $partial] || [file size $partial] != 1024} {
    error "P9 mailbox dump is not exactly 1024 bytes for $label"
  }
  file rename -force $partial $final
  return $final
}

proc p9_record_observation {d window started finished dump_path observed_status observed_state sequence} {
  global observation_handle
  set values [list [dict get $d label] [dict get $d command] [dict get $d expected_status] \
      [dict get $d flags] [dict get $d lane] [dict get $d direction] [dict get $d rate] [dict get $d weights] \
      [dict get $d size] [dict get $d ring] [dict get $d cache] [dict get $d txoff] \
      [dict get $d rxoff] [dict get $d timeout] [dict get $d session] [dict get $d path] \
      [dict get $d object] [dict get $d dropdata] [dict get $d dropack] \
      [dict get $d unavailable] [dict get $d rawtarget] [dict get $d spacing] \
      [dict get $d stale] [dict get $d initialseq] [dict get $d faultflags] \
      [dict get $d idle] [dict get $d injectmask] [dict get $d injectdelay] $window \
      $started $finished $observed_status $observed_state $sequence $dump_path]
  puts $observation_handle [join $values "|"]
  flush $observation_handle
}

# Diagnostic-only, read-only snapshots of the live AXI DMA channels and their
# first TX/RX descriptors.  The frozen diagnostic wrapper is the only caller
# that may enable this path.  It neither stops the CPU nor writes a PL, DMA, or
# descriptor address, so the captured state precedes the PS timeout cleanup.
proc p9_dma_diagnostic_snapshot {label sequence elapsed_ms ordinal} {
  global dump_dir
  if {![regexp {^[A-Za-z0-9_.-]+$} $label]} { error "unsafe DMA snapshot label" }
  set final [file join $dump_dir [format "%s.dma_snapshot_%02d.psv" $label $ordinal]]
  set partial "${final}.partial"
  catch {file delete -force $partial}
  set handle [open $partial w]
  puts $handle "schema_version|1"
  puts $handle "label|$label"
  puts $handle "sequence|$sequence"
  puts $handle "elapsed_ms|$elapsed_ms"
  foreach spec {
    {mm2s_dmacr 0x40400000} {mm2s_dmasr 0x40400004}
    {mm2s_curdesc 0x40400008} {mm2s_taildesc 0x40400010}
    {s2mm_dmacr 0x40400030} {s2mm_dmasr 0x40400034}
    {s2mm_curdesc 0x40400038} {s2mm_taildesc 0x40400040}
    {pl_status 0x43C0071C} {pl_object_error 0x43C00724}
    {pl_input_byte_count 0x43C00750} {pl_output_byte_count 0x43C00754}
  } {
    set name [lindex $spec 0]
    set value [p9_read32_force [lindex $spec 1]]
    puts $handle "$name|[format 0x%08X $value]"
  }
  foreach ring_spec {{tx 0x01000000} {rx 0x01001000}} {
    set ring [lindex $ring_spec 0]
    set base [lindex $ring_spec 1]
    for {set offset 0} {$offset < 64} {incr offset 4} {
      set value [p9_read32_force [expr {$base + $offset}]]
      puts $handle [format "%s_bd_%02X|0x%08X" $ring $offset $value]
    }
  }
  # Capture the descriptors that the DMA hardware names in CURDESC/TAILDESC,
  # not only descriptor zero.  Long-running diagnostic cases advance around
  # the SG ring, so descriptor zero can be stale evidence from an earlier
  # command.  Bounds and alignment are checked before every read so a corrupt
  # DMA pointer cannot turn this read-only diagnostic into an arbitrary AXI
  # memory walk.
  foreach current_spec {
    {tx_current 0x40400008 0x01000000 0x01000800}
    {tx_tail    0x40400010 0x01000000 0x01000800}
    {rx_current 0x40400038 0x01001000 0x01001800}
    {rx_tail    0x40400040 0x01001000 0x01001800}
  } {
    set name [lindex $current_spec 0]
    set pointer [expr {[p9_read32_force [lindex $current_spec 1]] & 0xFFFFFFC0}]
    set lower [lindex $current_spec 2]
    set upper [lindex $current_spec 3]
    if {$pointer < $lower || $pointer >= $upper || ($pointer & 0x3F) != 0} {
      puts $handle [format "%s_pointer_invalid|0x%08X" $name $pointer]
      continue
    }
    puts $handle [format "%s_pointer|0x%08X" $name $pointer]
    for {set offset 0} {$offset < 64} {incr offset 4} {
      set value [p9_read32_force [expr {$pointer + $offset}]]
      puts $handle [format "%s_%02X|0x%08X" $name $offset $value]
    }
  }
  foreach buffer_spec {{tx_buffer 0x02000000} {rx_buffer 0x06000000}} {
    set name [lindex $buffer_spec 0]
    set base [lindex $buffer_spec 1]
    for {set offset 0} {$offset < 64} {incr offset 4} {
      set value [p9_read32_force [expr {$base + $offset}]]
      puts $handle [format "%s_%02X|0x%08X" $name $offset $value]
    }
  }
  close $handle
  file rename -force $partial $final
  p9_say "P9_DMA_DIAGNOSTIC_SNAPSHOT=[file normalize $final]"
}

proc p9_case_dict {fields} {
  if {[llength $fields] != 29 || [lindex $fields 0] ne "CASE"} {
    error "P9 CASE requires exactly 29 fields"
  }
  set names {kind label command expected_status flags lane direction rate weights size ring cache txoff rxoff timeout session path object dropdata dropack unavailable rawtarget spacing stale initialseq faultflags idle injectmask injectdelay}
  set d [dict create]
  for {set i 0} {$i < [llength $names]} {incr i} {
    set name [lindex $names $i]; set value [lindex $fields $i]
    if {$name eq "kind" || $name eq "label"} {
      dict set d $name $value
    } else {
      if {![string is integer -strict $value]} { error "P9 CASE $name is not an integer" }
      dict set d $name $value
    }
  }
  if {![regexp {^[A-Za-z0-9_.-]+$} [dict get $d label]]} { error "invalid P9 CASE label" }
  if {[dict get $d lane] < 0 || [dict get $d lane] > 3} { error "lane mask outside 0x0..0x3" }
  if {[dict get $d timeout] < 1 || [dict get $d timeout] > 1800000} { error "case timeout outside authorization" }
  if {[dict get $d injectmask] < 0 || [dict get $d injectmask] > 3} { error "injected lane mask outside 0x0..0x3" }
  return $d
}

proc p9_wait_ready {label} {
  set deadline [expr {[clock milliseconds] + 15000}]
  while {[clock milliseconds] < $deadline} {
    p9_check_abort
    set magic [p9_read32 0x00020000]
    set state [p9_read32 0x0002000C]
    set status [p9_read32 0x00020020]
    if {$magic == 0x424D3950 && $state == 1 && $status == 0} {
      p9_say "P9_SERVICE_READY_LABEL=$label"
      return
    }
    if {$state == 5} { error "P9 service entered FAULT during $label startup status=$status" }
    after 10
  }
  error "P9 service ready timeout for $label"
}

proc p9_execute_case {d {window "NA"}} {
  global command_sequence observation_handle
  p9_check_abort
  incr command_sequence
  set sequence $command_sequence
  set started [clock milliseconds]

  # SUBMITTED is written while sequence still equals the prior response.  All
  # arguments follow, and command_sequence is the final atomic publish write.
  mwr 0x0002000C 2
  mwr 0x00020014 [dict get $d command]
  mwr 0x00020024 [dict get $d flags]
  mwr 0x00020028 [dict get $d lane]
  mwr 0x0002002C [dict get $d direction]
  mwr 0x00020030 [dict get $d rate]
  mwr 0x00020034 [dict get $d weights]
  mwr 0x00020038 [dict get $d size]
  mwr 0x0002003C [dict get $d ring]
  mwr 0x00020040 [dict get $d cache]
  mwr 0x00020044 [dict get $d txoff]
  mwr 0x00020048 [dict get $d rxoff]
  mwr 0x0002004C [dict get $d timeout]
  mwr 0x00020050 [dict get $d session]
  mwr 0x00020054 [dict get $d path]
  mwr 0x00020058 [dict get $d object]
  mwr 0x0002005C [dict get $d dropdata]
  mwr 0x00020060 [dict get $d dropack]
  mwr 0x00020064 [dict get $d unavailable]
  mwr 0x00020068 [dict get $d rawtarget]
  mwr 0x0002006C [dict get $d spacing]
  mwr 0x00020070 [dict get $d stale]
  mwr 0x00020074 [dict get $d initialseq]
  mwr 0x00020078 [dict get $d faultflags]
  mwr 0x0002007C [dict get $d idle]
  mwr 0x00020018 $sequence

  if {[dict get $d injectmask] != 0} {
    set running_deadline [expr {[clock milliseconds] + 5000}]
    while {[clock milliseconds] < $running_deadline} {
      p9_check_abort
      if {[p9_read32 0x0002000C] == 3} { break }
      after 1
    }
    if {[p9_read32 0x0002000C] != 3} { error "case completed before requested asynchronous injection" }
    after [dict get $d injectdelay]
    set injected [expr {([dict get $d dropdata] & 0xFF) | (([dict get $d dropack] & 0xFF) << 8) | (([dict get $d injectmask] & 3) << 16)}]
    mwr 0x43C0073C $injected
    p9_say "P9_ASYNC_LANE_INJECTION=[dict get $d label]:[dict get $d injectmask]"
  }

  set deadline [expr {$started + [dict get $d timeout] + 5000}]
  set terminal 0
  set diagnostic_dma 0
  if {[info exists ::env(RF_COMM_P9_DIAGNOSTIC_DMA_SNAPSHOT)] &&
      $::env(RF_COMM_P9_DIAGNOSTIC_DMA_SNAPSHOT) eq "1" &&
      [dict get $d command] == 3} {
    set diagnostic_dma 1
  }
  set diagnostic_schedule {100 500 2000}
  set diagnostic_ordinal 0
  while {[clock milliseconds] < $deadline} {
    p9_check_abort
    set response [p9_read32 0x0002001C]
    set state [p9_read32 0x0002000C]
    if {$response == $sequence && $state in {4 5 6}} { set terminal 1; break }
    if {$diagnostic_dma && $diagnostic_ordinal < [llength $diagnostic_schedule]} {
      set elapsed [expr {[clock milliseconds] - $started}]
      if {$elapsed >= [lindex $diagnostic_schedule $diagnostic_ordinal]} {
        p9_dma_diagnostic_snapshot [dict get $d label] $sequence $elapsed $diagnostic_ordinal
        incr diagnostic_ordinal
      }
    }
    after 5
  }
  if {!$terminal} { error "P9 command timeout label=[dict get $d label]" }
  set observed_status [p9_read32 0x00020020]
  set observed_state [p9_read32 0x0002000C]
  # Preserve the terminal mailbox before interpreting its status.  A failed
  # command is primary hardware evidence too; previously the status check
  # raised first and discarded the PL error code, DMA state, and counters
  # needed to diagnose the failure.
  set dump_path [p9_dump_mailbox [dict get $d label]]
  set finished [clock milliseconds]
  p9_record_observation $d $window $started $finished $dump_path $observed_status $observed_state $sequence
  if {$observed_status != [dict get $d expected_status]} {
    error "P9 command status mismatch label=[dict get $d label] expected=[dict get $d expected_status] observed=$observed_status"
  }
  if {[dict get $d command] == 10} {
    if {$observed_state != 6} { error "shutdown command did not reach SHUTDOWN state" }
  } elseif {$observed_status == 0} {
    if {$observed_state != 4} { error "successful command did not reach COMPLETE state" }
  } elseif {$observed_state != 5} {
    error "expected failing command did not reach FAULT state"
  }
  p9_say "P9_CASE_PASS=[dict get $d label]"
  if {[dict get $d command] != 10} { con }
}

proc p9_default_case {label object_id size direction weights timeout} {
  # The formal soak carries an actual RFAP vNext stream in every DMA object.
  return [dict create kind CASE label $label command 3 expected_status 0 flags 10 lane 3 \
      direction $direction rate 2 weights $weights size $size ring 32 cache 1 txoff 0 rxoff 0 \
      timeout $timeout session 0x90090001 path 9 object $object_id dropdata 0 dropack 0 \
      unavailable 0 rawtarget 0 spacing 1024 stale 0 initialseq 0 faultflags 0 idle 0 \
      injectmask 0 injectdelay 0]
}

proc p9_run_soak {label duration_sec} {
  if {$duration_sec != 1800} { error "formal P9 soak must be exactly 1800 seconds" }
  set start [clock milliseconds]
  set deadline [expr {$start + 1800000}]
  set warmup_end [expr {$start + 300000}]
  set index 0
  set boundary_announced 0
  p9_say "P9_SOAK_ACTIVE_START_MS=$start"
  while {[clock milliseconds] < $deadline} {
    p9_check_abort
    set now [clock milliseconds]
    set remaining [expr {$deadline - $now}]
    set warmup_remaining [expr {$warmup_end - $now}]
    # Do not let a warm-up object cross the frozen 300 s boundary.  Waiting
    # here is still part of the bounded stationary active window, and makes
    # the subsequent clean acceptance interval exactly 1500 s.
    if {$warmup_remaining > 0 && $warmup_remaining <= 8000} {
      after $warmup_remaining
      p9_say "P9_SOAK_WARMUP_END_MS=[clock milliseconds]"
      p9_say "P9_SOAK_ACCEPTANCE_SECONDS=1500"
      set boundary_announced 1
      continue
    }
    if {!$boundary_announced && $now >= $warmup_end} {
      p9_say "P9_SOAK_WARMUP_END_MS=$now"
      p9_say "P9_SOAK_ACCEPTANCE_SECONDS=1500"
      set boundary_announced 1
    }
    # p9_execute_case has a 5 s terminal grace and every case performs an
    # immutable mailbox dump.  Reserve 7 s so no new object can extend the
    # exact authorized active window.
    if {$remaining <= 8000} { after $remaining; break }
    set window [expr {$now < $warmup_end ? "WARMUP" : "ACCEPTANCE"}]
    set choice [expr {$index % 3}]
    set case_budget [expr {$now < $warmup_end ? $warmup_remaining : $remaining}]
    if {$case_budget > 130000 && $choice == 2} {
      set size 1048576
    } elseif {$case_budget > 20000 && $choice != 0} {
      set size 65536
    } else {
      set size 4096
    }
    set direction [expr {$index & 1}]
    set weights [lindex {0x0101 0x0301 0x0103} $choice]
    set timeout [expr {min(120000, max(250, $case_budget - 7000))}]
    set case_label [format "soak_%05d_%s_%d_d%d" $index [string tolower $window] $size $direction]
    set d [p9_default_case $case_label [expr {0x39000000 + $index}] $size $direction $weights $timeout]
    # A single bounded digital loss is confined to warm-up.  Every case after
    # the 300 s boundary is clean.
    if {$index == 0} { dict set d dropdata 1 }
    p9_execute_case $d $window
    incr index
  }
  set finished [clock milliseconds]
  set elapsed [expr {$finished - $start}]
  p9_say "P9_SOAK_CASE_COUNT=$index"
  p9_say "P9_SOAK_ACTIVE_END_MS=$finished"
  p9_say "P9_SOAK_ACTIVE_ELAPSED_MS=$elapsed"
  if {$elapsed < 1800000 || $elapsed > 1800500} {
    error "P9 soak active window was not bounded to 1800 seconds: $elapsed ms"
  }
}

if {[llength $argv] != 12} {
  error "usage: p9_xsdb_stage.tcl <xsdb-url> <board-id> <candidate-bit> <elf> <ps7-init> <plan> <dump-dir> <abort-file> <result> <stage> <phase2-auth> <run-id>"
}
set xsdb_url [lindex $argv 0]
set expected_board [lindex $argv 1]
set candidate_bit [file normalize [lindex $argv 2]]
set elf_file [file normalize [lindex $argv 3]]
set ps7_init_file [file normalize [lindex $argv 4]]
set plan_file [file normalize [lindex $argv 5]]
set dump_dir [file normalize [lindex $argv 6]]
set abort_file [file normalize [lindex $argv 7]]
set result_file [file normalize [lindex $argv 8]]
set stage [lindex $argv 9]
set authorization_file [file normalize [lindex $argv 10]]
set run_id [lindex $argv 11]
set connected 0; set candidate_programmed 0; set cpu_selected 0
set command_sequence 1000
file mkdir $dump_dir
file mkdir [file dirname $result_file]
set result_handle [open $result_file w]
set observation_file [file join $dump_dir observations.psv]
set observation_handle [open $observation_file w]
puts $observation_handle "label|command|expected_status|flags|lane|direction|rate|weights|size|ring|cache|txoff|rxoff|timeout|session|path|object|dropdata|dropack|unavailable|rawtarget|spacing|stale|initialseq|faultflags|idle|injectmask|injectdelay|window|started_ms|finished_ms|observed_status|observed_state|sequence|dump_path"
flush $observation_handle

set rc [catch {
  if {![info exists ::env(RF_COMM_P9_HW_AUTH)] ||
      $::env(RF_COMM_P9_HW_AUTH) ne "P9_PHASE2_IMMUTABLE_AUTHORIZED"} {
    error "P9 phase-2 environment marker required"
  }
  if {![regexp {^P9-(0[6-9]|1[0-9]|2[0-5])$} $stage]} { error "unsupported P9 XSDB stage" }
  if {![regexp {^p9_[A-Za-z0-9_.-]+$} $run_id]} { error "unsafe P9 run id" }
  foreach required [list $candidate_bit $elf_file $ps7_init_file $plan_file $authorization_file] {
    if {![file isfile $required]} { error "missing immutable P9 input: $required" }
  }
  if {[file exists $abort_file]} { error "P9 abort sentinel exists before launch" }

  # Parse and validate the complete plan before connecting to hardware.
  set plan_handle [open $plan_file r]
  set plan_text [read $plan_handle]
  close $plan_handle
  set parsed_plan {}
  foreach raw_line [split $plan_text "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string match "#*" $line]} { continue }
    if {![regexp {^[ -~]+$} $line]} { error "non-ASCII P9 plan line" }
    set fields [split $line]
    set kind [lindex $fields 0]
    if {$kind eq "CASE"} {
      lappend parsed_plan [list CASE [p9_case_dict $fields]]
    } elseif {$kind eq "REBOOT"} {
      if {[llength $fields] != 2 || ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]]} {
        error "invalid P9 REBOOT line"
      }
      lappend parsed_plan [list REBOOT [lindex $fields 1]]
    } elseif {$kind eq "SOAK"} {
      if {[llength $fields] != 3 || ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]] ||
          ![string is integer -strict [lindex $fields 2]] || [lindex $fields 2] != 1800} {
        error "invalid P9 SOAK line"
      }
      lappend parsed_plan [list SOAK [lindex $fields 1] [lindex $fields 2]]
    } else {
      error "unknown P9 plan record: $kind"
    }
  }
  if {[llength $parsed_plan] == 0} { error "empty P9 stage plan" }

  connect -url $xsdb_url
  set connected 1
  set jtag_identity [p9_wait_jtag_identity $expected_board]
  set device [dict get $jtag_identity device]
  set device_nodes [dict get $jtag_identity device_nodes]
  p9_say "P9_XSDB_JTAG_DISCOVERY_ATTEMPTS=[dict get $jtag_identity discovery_attempts]"
  p9_say "P9_XSDB_JTAG_DISCOVERY_ELAPSED_MS=[dict get $jtag_identity discovery_elapsed_ms]"
  p9_say "P9_XSDB_CABLE_ROOT_COUNT=[llength [dict get $jtag_identity cable_roots]]"
  p9_say "P9_XSDB_JTAG_DEVICE_COUNT=[llength $device_nodes]"
  p9_say "P9_XSDB_EXACT_FPGA_MATCH_COUNT=[llength [dict get $jtag_identity exact_device_matches]]"
  set jtag_index 0
  foreach props $device_nodes {
    set name [dict get $props name]
    set idcode [dict get $props idcode]
    set node_id "UNKNOWN"
    if {[dict exists $props node_id]} { set node_id [dict get $props node_id] }
    set safe_name [string map [list "=" "_" "|" "_" "\r" "" "\n" ""] $name]
    p9_say "P9_XSDB_ENUM_DEVICE_$jtag_index=$safe_name|NODE_ID=$node_id|IDCODE=$idcode|NORMALIZED=[p9_normal_idcode $idcode]"
    incr jtag_index
  }
  set debug [p9_wait_debug_targets [dict get $device node_id] $expected_board]
  set dap [dict get $debug dap]; set apu [dict get $debug apu]
  set fpga_targets [dict get $debug fpga]; set cpu_targets [dict get $debug cpu0]
  p9_say "P9_XSDB_DEBUG_DISCOVERY_ATTEMPTS=[dict get $debug discovery_attempts]"
  p9_say "P9_XSDB_DEBUG_DISCOVERY_ELAPSED_MS=[dict get $debug discovery_elapsed_ms]"
  if {[llength $dap] == 1} { set reset_target [lindex $dap 0] \
  } elseif {[llength $dap] == 0 && [llength $apu] == 1} { set reset_target [lindex $apu 0] \
  } else { error "P9 XSDB reset target is not unique" }
  set fpga_target [lindex $fpga_targets 0]
  set cpu_target [lindex $cpu_targets 0]
  p9_say "P9_XSDB_IDENTITY=PASS"
  p9_say "P9_XSDB_BOARD_ID=$expected_board"
  p9_say "P9_XSDB_IDCODE=13722093"
  p9_say "P9_XSDB_STAGE=$stage"
  p9_say "P9_XSDB_RUN_ID=$run_id"

  targets [dict get $reset_target target_id]
  rst -system
  after 1000
  targets [dict get $fpga_target target_id]
  fpga -file $candidate_bit
  set candidate_programmed 1
  p9_say "P9_CANDIDATE_PROGRAMMED=1"
  after 1000
  targets [dict get $cpu_target target_id]
  set cpu_selected 1
  source $ps7_init_file
  ps7_init
  ps7_post_config
  rst -processor
  dow $elf_file
  p9_say "P9_PS_ELF_DOWNLOADED=1"
  con
  p9_wait_ready initial_boot
  set ready_dump [p9_dump_mailbox "${stage}_ready"]
  p9_say "P9_INITIAL_READY_DUMP=$ready_dump"
  con

  foreach record $parsed_plan {
    set kind [lindex $record 0]
    if {$kind eq "CASE"} {
      p9_execute_case [lindex $record 1]
    } elseif {$kind eq "REBOOT"} {
      set label [lindex $record 1]
      catch {stop}
      rst -processor
      dow $elf_file
      con
      p9_wait_ready $label
      set dump_path [p9_dump_mailbox $label]
      p9_say "P9_REBOOT_PASS=$label"
      con
    } elseif {$kind eq "SOAK"} {
      p9_run_soak [lindex $record 1] [lindex $record 2]
    }
  }

  if {$stage eq "P9-19"} {
    catch {stop}
    foreach spec [list [list tx_bd_ring 0x01000000] [list rx_bd_ring 0x01001000]] {
      set name [lindex $spec 0]
      set address [lindex $spec 1]
      set final [file join $dump_dir "${name}.bin"]
      set partial "${final}.partial"
      catch {file delete -force $partial}
      mrd -size b -bin -file $partial $address 4096
      if {![file isfile $partial] || [file size $partial] != 4096} {
        error "P9 DMA descriptor ring dump failed: $name"
      }
      file rename -force $partial $final
      p9_say "P9_DMA_DESCRIPTOR_DUMP_${name}=$final"
    }
    con
  }

  set shutdown_case [dict create kind CASE label "${stage}_endpoint_shutdown" command 10 \
      expected_status 0 flags 0 lane 0 direction 0 rate 0 weights 0 size 0 ring 8 cache 0 \
      txoff 0 rxoff 0 timeout 10000 session 0 path 0 object 0 dropdata 0 dropack 0 \
      unavailable 0 rawtarget 0 spacing 1024 stale 0 initialseq 0 faultflags 0 idle 0 \
      injectmask 0 injectdelay 0]
  p9_execute_case $shutdown_case
  p9_say "P9_ENDPOINT_SHUTDOWN=PASS"
  p9_say "P9_XSDB_STAGE_RESULT=PASS"
} error_text error_options]

if {$rc != 0} {
  if {$cpu_selected} {
    catch {mwr 0x43C00718 0x0000001A}
    catch {after 10}
  }
  p9_say "P9_ENDPOINT_SHUTDOWN_REQUESTED_ON_ERROR=1"
  p9_say "P9_XSDB_STAGE_RESULT=FAIL"
  p9_say "P9_XSDB_STAGE_ERROR=[string map [list \"\\r\" \" \" \"\\n\" \" \" \"=\" \"_\" \"|\" \"_\"] $error_text]"
}
catch {close $observation_handle}
catch {close $result_handle}
if {$connected} { catch {disconnect} }
if {$rc != 0} { puts stderr $error_text; exit 41 }
exit 0
