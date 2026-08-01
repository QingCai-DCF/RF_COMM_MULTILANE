# P10 AX7020 two-board XSDB stage executor.
#
# Each invocation discovers both boards by their immutable JTAG cable serial,
# resets/programs/boots the two role-specific artifacts, verifies a safe boot,
# executes one immutable paired plan, requests shutdown in both endpoint
# runtimes, and exits.  The outer wrapper independently programs both frozen
# shutdown images before and after this process and on every failure, timeout,
# or Ctrl+C path.
# require-user-hw-authorization: reached only through the committed P10
# FastTrack current-run authorization and fail-closed outer wrapper.

set p10_expected_register_map_version 0x0A000002
set p10_expected_register_map_hash_low 0x6C0301EA

proc p10_sanitize {value} {
  return [string map [list "\r" " " "\n" " " "=" "_" "|" "_"] $value]
}

proc p10_say {line} {
  global p10_result_handle
  puts $p10_result_handle $line
  flush $p10_result_handle
  puts $line
  flush stdout
}

proc p10_select_target {target_id} {
  global p10_active_target_id
  if {![string is integer -strict $target_id] || $target_id < 0} {
    error "invalid P10 debug target id"
  }
  if {$p10_active_target_id != $target_id} {
    targets $target_id
    set p10_active_target_id $target_id
  }
}

proc p10_unique_target_ids {records} {
  set result {}
  set seen [dict create]
  foreach props $records {
    if {![dict exists $props target_id]} { continue }
    set id [dict get $props target_id]
    if {[dict exists $seen $id]} { continue }
    dict set seen $id 1
    lappend result $props
  }
  return $result
}

proc p10_classify_debug_targets {records serial} {
  set apu {}; set cpu0 {}; set fpga {}
  foreach props $records {
    if {![dict exists $props name] ||
        ![dict exists $props target_id] ||
        ![dict exists $props jtag_cable_serial] ||
        ![string equal -nocase [dict get $props jtag_cable_serial] $serial]} {
      continue
    }
    set name [dict get $props name]
    if {[string equal -nocase $name APU]} { lappend apu $props }
    if {[string match -nocase "*Cortex-A9*#0" $name]} { lappend cpu0 $props }
    if {[string equal -nocase $name xc7z020]} { lappend fpga $props }
  }
  return [dict create \
      apu [p10_unique_target_ids $apu] \
      cpu0 [p10_unique_target_ids $cpu0] \
      fpga [p10_unique_target_ids $fpga]]
}

proc p10_wait_debug_targets {{max_attempts 51} {delay_ms 100}} {
  global p10_fixed_serial p10_rotating_serial
  global p10_apu p10_cpu p10_fpga
  set started [clock milliseconds]
  set last "none"
  for {set attempt 1} {$attempt <= $max_attempts} {incr attempt} {
    set records [targets -target-properties]
    set fixed [p10_classify_debug_targets $records $p10_fixed_serial]
    set rotating [p10_classify_debug_targets $records $p10_rotating_serial]
    set counts [list \
        fixed_apu [llength [dict get $fixed apu]] \
        fixed_cpu0 [llength [dict get $fixed cpu0]] \
        fixed_fpga [llength [dict get $fixed fpga]] \
        rotating_apu [llength [dict get $rotating apu]] \
        rotating_cpu0 [llength [dict get $rotating cpu0]] \
        rotating_fpga [llength [dict get $rotating fpga]]]
    set last $counts
    set ambiguous 0
    foreach key {apu cpu0 fpga} {
      if {[llength [dict get $fixed $key]] > 1 ||
          [llength [dict get $rotating $key]] > 1} { set ambiguous 1 }
    }
    set all_fpga {}
    foreach props $records {
      if {[dict exists $props name] &&
          [string equal -nocase [dict get $props name] xc7z020] &&
          [dict exists $props jtag_cable_serial]} {
        lappend all_fpga [dict get $props jtag_cable_serial]
      }
    }
    set unique_fpga_serials [lsort -unique $all_fpga]
    if {$ambiguous || [llength $unique_fpga_serials] > 2} {
      error "P10 ambiguous or unauthorized debug topology: $counts FPGA_SERIALS=$unique_fpga_serials"
    }
    if {[llength [dict get $fixed apu]] == 1 &&
        [llength [dict get $fixed cpu0]] == 1 &&
        [llength [dict get $fixed fpga]] == 1 &&
        [llength [dict get $rotating apu]] == 1 &&
        [llength [dict get $rotating cpu0]] == 1 &&
        [llength [dict get $rotating fpga]] == 1 &&
        $unique_fpga_serials eq [lsort [list $p10_fixed_serial $p10_rotating_serial]]} {
      set p10_apu(fixed) [dict get [lindex [dict get $fixed apu] 0] target_id]
      set p10_cpu(fixed) [dict get [lindex [dict get $fixed cpu0] 0] target_id]
      set p10_fpga(fixed) [dict get [lindex [dict get $fixed fpga] 0] target_id]
      set p10_apu(rotating) [dict get [lindex [dict get $rotating apu] 0] target_id]
      set p10_cpu(rotating) [dict get [lindex [dict get $rotating cpu0] 0] target_id]
      set p10_fpga(rotating) [dict get [lindex [dict get $rotating fpga] 0] target_id]
      p10_say "P10_XSDB_DEBUG_DISCOVERY_ATTEMPTS=$attempt"
      p10_say "P10_XSDB_DEBUG_DISCOVERY_ELAPSED_MS=[expr {[clock milliseconds] - $started}]"
      p10_say "P10_XSDB_FIXED_TARGETS=APU:$p10_apu(fixed),CPU0:$p10_cpu(fixed),FPGA:$p10_fpga(fixed)"
      p10_say "P10_XSDB_ROTATING_TARGETS=APU:$p10_apu(rotating),CPU0:$p10_cpu(rotating),FPGA:$p10_fpga(rotating)"
      return
    }
    if {$attempt < $max_attempts && $delay_ms > 0} { after $delay_ms }
  }
  error "P10 debug target discovery timeout: $last"
}

proc p10_select_apu {role} {
  global p10_apu
  p10_select_target $p10_apu($role)
}

proc p10_select_cpu {role} {
  global p10_cpu
  p10_select_target $p10_cpu($role)
}

proc p10_read32 {role address} {
  p10_select_apu $role
  return [expr {[mrd -address-space AP0 -force -value $address] & 0xFFFFFFFF}]
}

proc p10_write32 {role address value} {
  p10_select_apu $role
  mwr -address-space AP0 -force -bypass-cache-sync $address $value
}

proc p10_check_abort {} {
  global p10_abort_file
  if {[file exists $p10_abort_file]} {
    foreach role {fixed rotating} {
      catch {p10_write32 $role 0x43C00718 0x0000001A}
    }
    error "P10 abort sentinel observed"
  }
}

proc p10_verify_pl_safe {role expected_build expected_profile label} {
  global p10_expected_register_map_version p10_expected_register_map_hash_low
  set identity [p10_read32 $role 0x43C00700]
  set build [p10_read32 $role 0x43C00704]
  set profile [p10_read32 $role 0x43C00708]
  set version [p10_read32 $role 0x43C0070C]
  set hash_low [p10_read32 $role 0x43C00710]
  set capabilities [p10_read32 $role 0x43C00714]
  p10_write32 $role 0x43C00718 0x0000001A
  after 10
  set status [p10_read32 $role 0x43C0071C]
  set phy [p10_read32 $role 0x43C00720]
  set physical_tx {}
  foreach address {0x43C007E4 0x43C007E8 0x43C007EC 0x43C007F0} {
    lappend physical_tx [p10_read32 $role $address]
  }
  if {$identity != 0x5031305A || $build != $expected_build ||
      $profile != $expected_profile ||
      $version != $p10_expected_register_map_version ||
      $hash_low != $p10_expected_register_map_hash_low ||
      $capabilities != 0xF7204221} {
    error [format "P10 %s identity mismatch id=0x%08X build=0x%08X profile=0x%08X version=0x%08X hash=0x%08X caps=0x%08X" \
        $role $identity $build $profile $version $hash_low $capabilities]
  }
  if {($status & 0x00000285) != 0 || ($status & 0x2) == 0} {
    error [format "P10 %s unsafe %s status=0x%08X" $role $label $status]
  }
  if {($phy & 0x00000F00) != 0} {
    error [format "P10 %s sticky PHY safety fault during %s phy=0x%08X" $role $label $phy]
  }
  foreach count $physical_tx {
    if {$count != 0} {
      error "P10 $role autonomous physical TX observed during $label: $physical_tx"
    }
  }
  p10_say [format "P10_SAFE_STATE_%s_%s=id:0x%08X,build:0x%08X,profile:0x%08X,status:0x%08X,phy:0x%08X,physical_tx:%s" \
      [string toupper $role] $label $identity $build $profile $status $phy [join $physical_tx ,]]
}

proc p10_wait_ready {role label} {
  set deadline [expr {[clock milliseconds] + 20000}]
  set magic 0; set state 0; set status 0
  while {[clock milliseconds] < $deadline} {
    p10_check_abort
    set magic [p10_read32 $role 0x00020000]
    set state [p10_read32 $role 0x0002000C]
    set status [p10_read32 $role 0x00020020]
    if {$magic == 0x424D3950 && $state == 1 && $status == 0} {
      p10_say "P10_SERVICE_READY_[string toupper $role]=$label"
      return
    }
    if {$state == 5} {
      error "P10 $role service entered FAULT during $label status=$status"
    }
    after 10
  }
  error [format "P10 %s service ready timeout label=%s magic=0x%08X state=0x%08X status=0x%08X" \
      $role $label $magic $state $status]
}

proc p10_dump_mailbox {role label} {
  global p10_dump_dir
  if {![regexp {^[A-Za-z0-9_.-]+$} $label]} { error "unsafe P10 dump label" }
  set final [file join $p10_dump_dir "${label}.${role}.bin"]
  set partial "${final}.partial"
  catch {file delete -force $partial}
  p10_select_cpu $role
  catch {stop}
  p10_select_apu $role
  mrd -address-space AP0 -force -size b -bin -file $partial 0x00020000 1024
  if {![file isfile $partial] || [file size $partial] != 1024} {
    error "P10 $role mailbox dump is not exactly 1024 bytes for $label"
  }
  file rename -force $partial $final
  return $final
}

proc p10_dump_p10_1_result {role label} {
  global p10_dump_dir
  if {![regexp {^[A-Za-z0-9_.-]+$} $label]} {
    error "unsafe P10.1 result dump label"
  }
  set final [file join $p10_dump_dir "${label}.${role}.p10_1.bin"]
  set partial "${final}.partial"
  catch {file delete -force $partial}
  p10_select_cpu $role
  catch {stop}
  p10_select_apu $role
  mrd -address-space AP0 -force -size b -bin -file $partial 0x00020400 2048
  if {![file isfile $partial] || [file size $partial] != 2048} {
    error "P10.1 $role result dump is not exactly 2048 bytes for $label"
  }
  file rename -force $partial $final
  return $final
}

proc p10_read_p10_1r_snapshot {role} {
  set before [p10_read32 $role 0x43C00A04]
  p10_write32 $role 0x43C00A00 1
  after 1
  set generation [p10_read32 $role 0x43C00A04]
  set caps [p10_read32 $role 0x43C00A08]
  if {$generation <= $before || ($generation & 1) != 0 ||
      $caps != 0x52310101} {
    error [format "P10.1R %s atomic snapshot invalid before=0x%08X generation=0x%08X caps=0x%08X" \
        $role $before $generation $caps]
  }
  set values {}
  for {set address 0x43C00A0C} {$address <= 0x43C00AA8} {incr address 4} {
    lappend values [p10_read32 $role $address]
  }
  if {[lindex $values 35] != 4096 || [lindex $values 36] != 256 ||
      [lindex $values 37] != 131072 || [lindex $values 38] != 4 ||
      [lindex $values 39] != 3} {
    error "P10.1R $role admission timing/config readback mismatch"
  }
  return [linsert $values 0 $generation $caps]
}

proc p10_dump_p10_1r_snapshot {role label} {
  global p10_dump_dir
  if {![regexp {^[A-Za-z0-9_.-]+$} $label]} {
    error "unsafe P10.1R snapshot label"
  }
  set final [file join $p10_dump_dir "${label}.${role}.p10_1r.psv"]
  set values [p10_read_p10_1r_snapshot $role]
  set out [open $final w]
  puts $out [join $values "|"]
  close $out
  return $final
}

proc p10_record_p10_1r_telemetry {sequence label} {
  global p10_telemetry_handle
  set captured [clock milliseconds]
  foreach role {fixed rotating} {
    set values [p10_read_p10_1r_snapshot $role]
    puts $p10_telemetry_handle [join [list $captured $sequence $label $role \
        [join $values ","]] "|"]
  }
  flush $p10_telemetry_handle
}

proc p10_resume {role} {
  p10_select_cpu $role
  con
}

proc p10_case_dict {fields} {
  if {[llength $fields] != 29 || [lindex $fields 0] ne "CASE"} {
    error "P10 CASE requires exactly 29 fields"
  }
  set names {kind label command expected_status flags lane direction rate weights size ring cache txoff rxoff timeout session path object dropdata dropack unavailable rawtarget spacing stale initialseq faultflags idle injectmask injectdelay}
  set d [dict create]
  for {set index 0} {$index < [llength $names]} {incr index} {
    set name [lindex $names $index]
    set value [lindex $fields $index]
    if {$name eq "kind" || $name eq "label"} {
      dict set d $name $value
    } else {
      if {![string is integer -strict $value]} { error "P10 CASE $name is not an integer" }
      dict set d $name $value
    }
  }
  if {![regexp {^[A-Za-z0-9_.-]+$} [dict get $d label]]} { error "invalid P10 CASE label" }
  if {[dict get $d lane] < 0 || [dict get $d lane] > 3 ||
      [dict get $d unavailable] < 0 || [dict get $d unavailable] > 3 ||
      [dict get $d injectmask] < 0 || [dict get $d injectmask] > 3} {
    error "P10 lane mask outside 0x0..0x3"
  }
  if {[dict get $d direction] < 0 || [dict get $d direction] > 1 ||
      [dict get $d rate] < 0 || [dict get $d rate] > 2} {
    error "P10 direction/rate outside authorization"
  }
  if {[dict get $d timeout] < 1 || [dict get $d timeout] > 1800000} {
    error "P10 case timeout outside authorization"
  }
  if {[dict get $d command] in {2 3 12 13} && [dict get $d lane] == 0} {
    error "P10 transmit-capable command has an empty lane mask"
  }
  return $d
}

proc p10_publish_case {role d sequence} {
  p10_write32 $role 0x0002000C 2
  foreach spec {
    {0x00020014 command} {0x00020024 flags} {0x00020028 lane}
    {0x0002002C direction} {0x00020030 rate} {0x00020034 weights}
    {0x00020038 size} {0x0002003C ring} {0x00020040 cache}
    {0x00020044 txoff} {0x00020048 rxoff} {0x0002004C timeout}
    {0x00020050 session} {0x00020054 path} {0x00020058 object}
    {0x0002005C dropdata} {0x00020060 dropack} {0x00020064 unavailable}
    {0x00020068 rawtarget} {0x0002006C spacing} {0x00020070 stale}
    {0x00020074 initialseq} {0x00020078 faultflags} {0x0002007C idle}
  } {
    p10_write32 $role [lindex $spec 0] [dict get $d [lindex $spec 1]]
  }
  p10_write32 $role 0x00020018 $sequence
}

proc p10_sender_role {direction} {
  return [expr {$direction == 0 ? "fixed" : "rotating"}]
}

proc p10_receiver_role {direction} {
  return [expr {$direction == 0 ? "rotating" : "fixed"}]
}

proc p10_wait_receiver_primed {role d} {
  set command [dict get $d command]
  set timeout [dict get $d timeout]
  # Payload generation, zeroing, CRC32, and SHA256 all happen before the
  # receiver publishes RUNNING. Scale this bounded pre-launch wait with the
  # immutable object size so the mandatory 16 MiB RFAP case is not mistaken
  # for a dead endpoint while retaining a finite failure deadline.
  set p10_prime_base_ms 30000
  set p10_prime_per_mib_ms 8000
  set size_mib [expr {([dict get $d size] + 1048575) / 1048576}]
  set prepare_budget [expr {$p10_prime_base_ms +
                            $p10_prime_per_mib_ms * $size_mib}]
  set bounded [expr {$timeout < $prepare_budget ? $timeout : $prepare_budget}]
  set deadline [expr {[clock milliseconds] + $bounded}]
  set last_state 0
  set last_response 0
  set last_pl_status 0
  set last_phy 0
  set last_p10_1_magic 0
  set last_p10_1_state 0
  set last_p10_1_status 0
  set last_p10_1_sequence 0
  while {[clock milliseconds] < $deadline} {
    p10_check_abort
    set state [p10_read32 $role 0x0002000C]
    set response [p10_read32 $role 0x0002001C]
    set pl_status [p10_read32 $role 0x43C0071C]
    set phy [p10_read32 $role 0x43C00720]
    set last_state $state
    set last_response $response
    set last_pl_status $pl_status
    set last_phy $phy
    if {$state == 5 && $command != 13} {
      error "P10 $role receiver faulted before source launch"
    }
    if {($phy & 0x00000F00) != 0} { error "P10 $role receiver safety fault before source launch" }
    if {$command == 3 && $state == 3 && ($pl_status & 0x4) != 0} { return }
    if {$command == 13} {
      set p10_1_magic [p10_read32 $role 0x00020400]
      set p10_1_state [p10_read32 $role 0x00020410]
      set p10_1_status [p10_read32 $role 0x00020414]
      set p10_1_sequence [p10_read32 $role 0x00020418]
      set last_p10_1_magic $p10_1_magic
      set last_p10_1_state $p10_1_state
      set last_p10_1_status $p10_1_status
      set last_p10_1_sequence $p10_1_sequence
      if {$p10_1_magic == 0x31303150 && $p10_1_state == 3 &&
          ($pl_status & 0x4) != 0} {
        return
      }
      if {$state == 5 || $p10_1_state == 8} {
        error [format "P10.1 %s receiver faulted before source launch: main_state=0x%08X response=0x%08X pl_status=0x%08X phy=0x%08X p10_1_magic=0x%08X p10_1_state=0x%08X p10_1_status=0x%08X p10_1_sequence=0x%08X" \
            $role $state $response $pl_status $phy $p10_1_magic \
            $p10_1_state $p10_1_status $p10_1_sequence]
      }
    }
    if {$command == 2 && $state == 3 && ($pl_status & 0x201) == 0x201 &&
        ($pl_status & 0x2) == 0} { return }
    after 1
  }
  error [format "P10 %s receiver did not prime before paired source launch: wait_ms=%d main_state=0x%08X response=0x%08X pl_status=0x%08X phy=0x%08X p10_1_magic=0x%08X p10_1_state=0x%08X p10_1_status=0x%08X p10_1_sequence=0x%08X" \
      $role $bounded $last_state $last_response $last_pl_status $last_phy \
      $last_p10_1_magic $last_p10_1_state $last_p10_1_status \
      $last_p10_1_sequence]
}

proc p10_record_observation {d sequence started finished fixed_dump rotating_dump fixed_p10_1_dump rotating_p10_1_dump fixed_p10_1r_dump rotating_p10_1r_dump fixed_status rotating_status fixed_state rotating_state window} {
  global p10_observation_handle
  set values [list [dict get $d label] [dict get $d command] [dict get $d expected_status] \
      [dict get $d flags] [dict get $d lane] [dict get $d direction] [dict get $d rate] \
      [dict get $d weights] [dict get $d size] [dict get $d ring] [dict get $d cache] \
      [dict get $d txoff] [dict get $d rxoff] [dict get $d timeout] [dict get $d session] \
      [dict get $d path] [dict get $d object] [dict get $d dropdata] [dict get $d dropack] \
      [dict get $d unavailable] [dict get $d rawtarget] [dict get $d spacing] [dict get $d stale] \
      [dict get $d initialseq] [dict get $d faultflags] [dict get $d idle] \
      [dict get $d injectmask] [dict get $d injectdelay] $window $started $finished $sequence \
      $fixed_status $rotating_status $fixed_state $rotating_state $fixed_dump $rotating_dump \
      $fixed_p10_1_dump $rotating_p10_1_dump $fixed_p10_1r_dump $rotating_p10_1r_dump]
  puts $p10_observation_handle [join $values "|"]
  flush $p10_observation_handle
}

proc p10_wait_pair_terminal {sequence timeout_ms} {
  global p10_active_case_label
  set deadline [expr {[clock milliseconds] + $timeout_ms + 5000}]
  set next_telemetry [expr {[clock milliseconds] + 5000}]
  set fixed_done 0; set rotating_done 0
  set fixed_state 0; set rotating_state 0
  while {[clock milliseconds] < $deadline} {
    p10_check_abort
    set now [clock milliseconds]
    if {$now >= $next_telemetry} {
      p10_record_p10_1r_telemetry $sequence $p10_active_case_label
      set next_telemetry [expr {$now + 5000}]
    }
    set fixed_response [p10_read32 fixed 0x0002001C]
    set fixed_state [p10_read32 fixed 0x0002000C]
    set rotating_response [p10_read32 rotating 0x0002001C]
    set rotating_state [p10_read32 rotating 0x0002000C]
    if {$fixed_response == $sequence && $fixed_state in {4 5 6}} { set fixed_done 1 }
    if {$rotating_response == $sequence && $rotating_state in {4 5 6}} { set rotating_done 1 }
    if {$fixed_done && $rotating_done} {
      return [list $fixed_state $rotating_state]
    }
    after 5
  }
  set fixed_p101_state [p10_read32 fixed 0x00020410]
  set fixed_p101_status [p10_read32 fixed 0x00020414]
  set fixed_committed_low [p10_read32 fixed 0x000204B0]
  set rotating_p101_state [p10_read32 rotating 0x00020410]
  set rotating_p101_status [p10_read32 rotating 0x00020414]
  set rotating_committed_low [p10_read32 rotating 0x000204B0]
  error "P10 paired command timeout sequence=$sequence fixed_state=$fixed_state rotating_state=$rotating_state fixed_p101_state=$fixed_p101_state fixed_p101_status=$fixed_p101_status fixed_committed_low=$fixed_committed_low rotating_p101_state=$rotating_p101_state rotating_p101_status=$rotating_p101_status rotating_committed_low=$rotating_committed_low"
}

proc p10_execute_case {d {window "NA"}} {
  global p10_command_sequence p10_active_case_label
  p10_check_abort
  incr p10_command_sequence
  set sequence $p10_command_sequence
  set p10_active_case_label [dict get $d label]
  set started [clock milliseconds]
  set command [dict get $d command]

  foreach role {fixed rotating} {
    p10_write32 $role 0x43C00718 0x00000020
  }
  after 1

  if {$command in {2 3 13}} {
    set receiver [p10_receiver_role [dict get $d direction]]
    set sender [p10_sender_role [dict get $d direction]]
    p10_publish_case $receiver $d $sequence
    p10_wait_receiver_primed $receiver $d
    p10_publish_case $sender $d $sequence
    p10_say "P10_PAIRED_LAUNCH=[dict get $d label]:receiver=$receiver,sender=$sender"
    if {$command == 3 && [dict get $d injectmask] != 0} {
      set injection_deadline [expr {[clock milliseconds] + 10000}]
      set active_seen 0
      while {[clock milliseconds] < $injection_deadline} {
        p10_check_abort
        set injection_state [p10_read32 $sender 0x0002000C]
        set injection_status [p10_read32 $sender 0x43C0071C]
        if {$injection_state in {4 5 6}} {
          error "P10 source completed before requested lane-fault injection"
        }
        if {$injection_state == 3 && ($injection_status & 0x4) != 0} {
          set active_seen 1
          break
        }
        after 1
      }
      if {!$active_seen} { error "P10 source never became active for lane-fault injection" }
      after [dict get $d injectdelay]
      p10_check_abort
      set pre_state [p10_read32 $sender 0x0002000C]
      set pre_status [p10_read32 $sender 0x43C0071C]
      if {$pre_state != 3 || ($pre_status & 0x4) == 0} {
        error "P10 source completed before lane-fault injection write"
      }
      set injected [expr {([dict get $d dropdata] & 0xFF) |
          (([dict get $d dropack] & 0xFF) << 8) |
          (([dict get $d injectmask] & 3) << 16)}]
      p10_write32 $sender 0x43C0073C $injected
      set readback [p10_read32 $sender 0x43C0073C]
      if {($readback & 0x0003FFFF) != $injected} {
        error "P10 asynchronous lane-fault injection readback mismatch"
      }
      p10_say [format "P10_ASYNC_LANE_INJECTION=%s:sender=%s,mask=0x%X,readback=0x%08X" \
          [dict get $d label] $sender [dict get $d injectmask] $readback]
    }
  } else {
    p10_publish_case fixed $d $sequence
    p10_publish_case rotating $d $sequence
  }

  set terminal [p10_wait_pair_terminal $sequence [dict get $d timeout]]
  set fixed_status [p10_read32 fixed 0x00020020]
  set rotating_status [p10_read32 rotating 0x00020020]
  set fixed_state [lindex $terminal 0]
  set rotating_state [lindex $terminal 1]
  set fixed_dump [p10_dump_mailbox fixed [dict get $d label]]
  set rotating_dump [p10_dump_mailbox rotating [dict get $d label]]
  set fixed_p10_1_dump ""
  set rotating_p10_1_dump ""
  if {$command == 13} {
    set fixed_p10_1_dump [p10_dump_p10_1_result fixed [dict get $d label]]
    set rotating_p10_1_dump [p10_dump_p10_1_result rotating [dict get $d label]]
  }
  set fixed_p10_1r_dump [p10_dump_p10_1r_snapshot fixed [dict get $d label]]
  set rotating_p10_1r_dump [p10_dump_p10_1r_snapshot rotating [dict get $d label]]
  set finished [clock milliseconds]
  p10_record_observation $d $sequence $started $finished $fixed_dump $rotating_dump \
      $fixed_p10_1_dump $rotating_p10_1_dump \
      $fixed_p10_1r_dump $rotating_p10_1r_dump \
      $fixed_status $rotating_status $fixed_state $rotating_state $window

  set expected [dict get $d expected_status]
  set expected_state [expr {$command == 10 ? 6 : ($expected == 0 ? 4 : 5)}]
  if {$fixed_status != $expected || $rotating_status != $expected ||
      $fixed_state != $expected_state || $rotating_state != $expected_state} {
    error "P10 paired result mismatch label=[dict get $d label] expected_status=$expected fixed=$fixed_status/$fixed_state rotating=$rotating_status/$rotating_state"
  }
  p10_say "P10_CASE_PASS=[dict get $d label]"
  set reset_recovery_flags [expr {(1 << 18) | (1 << 19) | (1 << 24)}]
  set reset_recovery_case [expr {
      $command == 13 && ([dict get $d flags] & $reset_recovery_flags) != 0}]
  if {$reset_recovery_case} {
    # The result dumps above are the immutable recovery evidence.  Reset-class
    # injection can leave the two independently clocked transport services in
    # different epochs even after both firmware instances report EXPECTED_ABORT.
    # Rebootstrap both PS services before admitting the required clean vector.
    p10_rebootstrap_after_reset_recovery [dict get $d label]
  } elseif {$command != 10} {
    p10_resume fixed
    p10_resume rotating
  }
}

proc p10_p101_case {label object_id size direction lane timeout_ms {flags 0}} {
  # Hardware-selected sustained configuration: buffer=4, ring=32, batch=8,
  # object=256 KiB.  Source run and hashes are frozen in the selected tuning
  # configuration evidence; this helper is used by windows and recovery cases.
  set fields [list CASE $label 13 0 $flags $lane $direction 2 257 $size 32 1 0 0 \
      $timeout_ms 0xA1010001 0x101 $object_id 32 32 0 262144 65536 4 8 0 0 0 0]
  return [p10_case_dict $fields]
}

proc p10_run_p101_window {label duration_sec direction lane maximum_chunk \
                          {absolute_deadline 0}} {
  if {![regexp {^[A-Za-z0-9_.-]+$} $label] ||
      ![string is integer -strict $duration_sec] ||
      $duration_sec < 10 || $duration_sec > 840 ||
      $direction ni {0 1} || $lane ni {1 2 3} ||
      $maximum_chunk ni {1048576 4194304 16777216 67108864} ||
      ![string is integer -strict $absolute_deadline] ||
      $absolute_deadline < 0} {
    error "invalid P10.1 bounded window"
  }
  set started [clock milliseconds]
  set deadline [expr {$absolute_deadline == 0 ?
      $started + $duration_sec * 1000 : $absolute_deadline}]
  if {$deadline <= $started || $deadline > $started + $duration_sec * 1000} {
    error "invalid P10.1 absolute window deadline"
  }
  set index 0
  set last_case_size 0
  set last_case_elapsed_ms 0
  set object_id [expr {0x51000000 ^ (($direction & 1) << 27) ^
      (($lane & 3) << 24) ^ ($duration_sec << 8)}]
  set marker_label [string toupper [string map [list "." "_" "-" "_"] $label]]
  p10_say "P10_1_WINDOW_START_${marker_label}=$started"
  while {[clock milliseconds] < $deadline} {
    p10_check_abort
    set remaining [expr {$deadline - [clock milliseconds]}]
    if {$remaining <= 6000} {
      after $remaining
      break
    }
    set candidate 1048576
    set candidate_budget 5000
    if {$maximum_chunk >= 4194304 && $remaining > 15000} {
      set candidate 4194304
      set candidate_budget 15000
    }
    if {$maximum_chunk >= 16777216 && $remaining > 45000 &&
        ($index % 3) != 0} {
      set candidate 16777216
      set candidate_budget 42000
    }
    if {$maximum_chunk == 67108864 && $remaining > 150000 &&
        ($index % 3) == 2} {
      set candidate 67108864
      set candidate_budget 145000
    }
    # A bounded window may not assume that the endpoint already meets its
    # target throughput.  Scale the most recent completed case wall time to
    # the proposed larger chunk, add 25 percent plus 2 s of margin, and defer
    # the large chunk when it cannot fit.  This keeps a slow measurement a
    # measured performance FAIL instead of turning it into a host timeout.
    if {$candidate > 1048576 && $last_case_size > 0 &&
        $last_case_elapsed_ms > 0} {
      set measured_budget [expr {
          (($last_case_elapsed_ms * $candidate * 5) +
           ($last_case_size * 4 - 1)) / ($last_case_size * 4) + 2000}]
      if {$measured_budget > $candidate_budget} {
        set candidate_budget $measured_budget
      }
    }
    if {$candidate_budget + 3000 >= $remaining} {
      if {$candidate > 1048576} {
        p10_say "P10_1_WINDOW_CHUNK_DEFERRED=$label:candidate=$candidate,budget_ms=$candidate_budget,remaining_ms=$remaining"
      }
      set candidate 1048576
      set candidate_budget 5000
    }
    if {$candidate_budget + 1000 >= $remaining} {
      after $remaining
      break
    }
    set timeout [expr {min(1800000, max(10000, $remaining - 1000))}]
    set case_label [format "%s_%04d_%d" $label $index $candidate]
    set pattern_flags [expr {($index % 5) << 8}]
    set d [p10_p101_case $case_label [expr {$object_id + $index}] \
        $candidate $direction $lane $timeout $pattern_flags]
    set case_started [clock milliseconds]
    p10_execute_case $d $label
    set last_case_elapsed_ms [expr {
        max(1, [clock milliseconds] - $case_started)}]
    set last_case_size $candidate
    if {[clock milliseconds] > $deadline} {
      error "P10.1 window $label exceeded its bounded deadline"
    }
    incr index
  }
  set finished [clock milliseconds]
  set elapsed [expr {$finished - $started}]
  if {$finished < $deadline || $finished > $deadline + 500} {
    error "P10.1 window $label deadline bound failed: elapsed=$elapsed ms"
  }
  if {$index == 0} {
    error "P10.1 window $label completed no autonomous stream"
  }
  p10_say "P10_1_WINDOW_PASS_${marker_label}=cases:$index,elapsed_ms:$elapsed"
}

proc p10_wait_p101_active {sequence timeout_ms} {
  set deadline [expr {[clock milliseconds] + $timeout_ms}]
  while {[clock milliseconds] < $deadline} {
    p10_check_abort
    set ready 1
    foreach role {fixed rotating} {
      set response [p10_read32 $role 0x0002001C]
      set state [p10_read32 $role 0x0002000C]
      set p101_state [p10_read32 $role 0x00020410]
      set pl_status [p10_read32 $role 0x43C0071C]
      if {$response == $sequence || $state == 5 || $p101_state == 8} {
        error "P10.1 service-reset case terminated before reset"
      }
      if {$state != 3 || $p101_state ni {3 4} ||
          ($pl_status & 0x4) == 0} {
        set ready 0
      }
    }
    if {$ready} { return }
    after 1
  }
  error "P10.1 service-reset case never became active"
}

proc p10_execute_ps_service_reset {label reset_role direction lane size object_id} {
  global p10_command_sequence p10_active_case_label
  if {![regexp {^[A-Za-z0-9_.-]+$} $label] ||
      $reset_role ni {fixed rotating} || $direction ni {0 1} ||
      $lane ni {1 2 3} || $size != 67108864} {
    error "invalid P10.1 PS service-reset vector"
  }
  set sender [p10_sender_role $direction]
  set receiver [p10_receiver_role $direction]
  set flag [expr {$reset_role eq $sender ? (1 << 22) : (1 << 23)}]
  set d [p10_p101_case $label $object_id $size $direction $lane 600000 $flag]
  incr p10_command_sequence
  set sequence $p10_command_sequence
  set p10_active_case_label $label
  set started [clock milliseconds]
  p10_publish_case $receiver $d $sequence
  p10_wait_receiver_primed $receiver $d
  p10_publish_case $sender $d $sequence
  p10_wait_p101_active $sequence 30000
  after 100

  set fixed_status [p10_read32 fixed 0x00020020]
  set rotating_status [p10_read32 rotating 0x00020020]
  set fixed_state [p10_read32 fixed 0x0002000C]
  set rotating_state [p10_read32 rotating 0x0002000C]
  foreach role {fixed rotating} {
    if {[p10_read32 $role 0x000204B0] != 0 ||
        [p10_read32 $role 0x000204B4] != 0 ||
        [p10_read32 $role 0x000204D8] != 0 ||
        [p10_read32 $role 0x000204E4] != 0} {
      error "P10.1 service-reset precondition observed a commit"
    }
  }
  set fixed_dump [p10_dump_mailbox fixed $label]
  set rotating_dump [p10_dump_mailbox rotating $label]
  set fixed_p101 [p10_dump_p10_1_result fixed $label]
  set rotating_p101 [p10_dump_p10_1_result rotating $label]
  set fixed_p10_1r [p10_dump_p10_1r_snapshot fixed $label]
  set rotating_p10_1r [p10_dump_p10_1r_snapshot rotating $label]

  p10_select_cpu $reset_role
  rst -processor
  foreach role {fixed rotating} {
    p10_write32 $role 0x43C00718 0x0000001A
  }
  after 10
  p10_reboot_role $reset_role "${label}_selected_reboot"
  set peer [expr {$reset_role eq "fixed" ? "rotating" : "fixed"}]
  p10_reboot_role $peer "${label}_peer_recovery_reboot"
  global p10_expected_build
  p10_verify_pl_safe fixed $p10_expected_build(fixed) 0x702000F0 "${label}_RECOVERED"
  p10_verify_pl_safe rotating $p10_expected_build(rotating) 0x702000A0 "${label}_RECOVERED"
  set finished [clock milliseconds]
  p10_record_observation $d $sequence $started $finished $fixed_dump \
      $rotating_dump $fixed_p101 $rotating_p101 $fixed_p10_1r \
      $rotating_p10_1r $fixed_status $rotating_status $fixed_state \
      $rotating_state PS_SERVICE_RESET
  p10_say "P10_1_PS_SERVICE_RESET_PASS=$label:reset_role=$reset_role"
}

proc p10_run_p101_formal {label duration_sec} {
  if {$duration_sec != 1800} {
    error "formal P10.1 run must be exactly 1800 seconds"
  }
  set started [clock milliseconds]
  p10_say "P10_1_FORMAL_START_MS=$started"
  p10_run_p101_window "${label}_warmup_f2r" 60 0 3 16777216 \
      [expr {$started + 60000}]
  p10_run_p101_window "${label}_warmup_r2f" 60 1 3 16777216 \
      [expr {$started + 120000}]
  p10_run_p101_window "${label}_formal_f2r" 840 0 3 67108864 \
      [expr {$started + 960000}]
  p10_run_p101_window "${label}_formal_r2f" 840 1 3 67108864 \
      [expr {$started + 1800000}]
  set finished [clock milliseconds]
  set elapsed [expr {$finished - $started}]
  if {$elapsed < 1800000 || $elapsed > 1800500} {
    error "P10.1 formal active window was not 1800 seconds: $elapsed ms"
  }
  p10_say "P10_1_FORMAL_END_MS=$finished"
  p10_say "P10_1_FORMAL_ELAPSED_MS=$elapsed"
  p10_say "P10_1_FORMAL_RESULT=PASS"
}

proc p10_run_p101r_timed_case {label duration_sec direction lane size object_id} {
  if {![regexp {^[A-Za-z0-9_.-]+$} $label] ||
      $duration_sec != 30 || $direction ni {0 1} || $lane != 3 ||
      $size != 16777216 || ![string is integer -strict $object_id]} {
    error "invalid P10.1R timed case"
  }
  set started [clock milliseconds]
  set deadline [expr {$started + $duration_sec * 1000}]
  set d [p10_p101_case $label $object_id $size $direction $lane \
      [expr {$duration_sec * 1000}] 0]
  p10_execute_case $d $label
  set completed [clock milliseconds]
  if {$completed > $deadline} {
    error "P10.1R timed case exceeded its 30-second window"
  }
  after [expr {$deadline - $completed}]
  set finished [clock milliseconds]
  set elapsed [expr {$finished - $started}]
  if {$elapsed < 30000 || $elapsed > 30500} {
    error "P10.1R timed case window bound failed: $elapsed ms"
  }
  p10_say "P10_1R_TIMED_CASE_PASS=$label:elapsed_ms=$elapsed,size=$size"
}

proc p10_run_p101r_echo_sweep {label direction lane sample_count spacing} {
  global p10_command_sequence p10_dump_dir p10_active_case_label
  if {![regexp {^[A-Za-z0-9_.-]+$} $label] ||
      $direction ni {0 1} || $lane ni {1 2} ||
      $sample_count != 1000 || $spacing < 1024 || $spacing > 65536} {
    error "invalid P10.1R echo sweep"
  }
  set lane_index [expr {$lane == 1 ? 0 : 1}]
  set sender [p10_sender_role $direction]
  set receiver [p10_receiver_role $direction]
  set output [file join $p10_dump_dir "${label}.echo_tail.psv"]
  set handle [open $output w]
  puts $handle "sample|module|direction|lane_mask|tail_cycles|sender_raw|sender_raw_while_tx|sender_blanked_raw|sender_blanked_frame|sender_blanked_crc_valid|sender_local_source_reject|sender_accepted_remote|receiver_raw|receiver_accepted_remote|sender_last_txd_rise|sender_last_txd_fall|sender_first_rxd_after_tx|sender_last_rxd_after_tx|sender_overlap_violation|sender_admission_violation|sender_non_target_accepted|sender_cross_lane_accepted|receiver_overlap_violation|receiver_admission_violation|receiver_non_target_accepted|receiver_cross_lane_accepted"
  set module [expr {$direction == 0 ? ($lane == 1 ? "F0" : "F1") :
      ($lane == 1 ? "R0" : "R1")}]
  for {set sample 0} {$sample < $sample_count} {incr sample} {
    p10_check_abort
    foreach role {fixed rotating} {
      p10_write32 $role 0x43C00718 0x00000020
    }
    after 1
    set fields [list CASE [format "%s_%04d" $label $sample] 2 0 0 $lane \
        $direction 2 257 0 32 1 0 0 10000 0xA1010001 0x101 \
        [expr {0x61000000 + $sample}] 0 0 0 1 $spacing 0 0 0 0 0 0]
    set d [p10_case_dict $fields]
    incr p10_command_sequence
    set sequence $p10_command_sequence
    set p10_active_case_label [format "%s_%04d" $label $sample]
    p10_publish_case $receiver $d $sequence
    p10_wait_receiver_primed $receiver $d
    p10_publish_case $sender $d $sequence
    set terminal [p10_wait_pair_terminal $sequence 10000]
    set fixed_status [p10_read32 fixed 0x00020020]
    set rotating_status [p10_read32 rotating 0x00020020]
    if {$fixed_status != 0 || $rotating_status != 0 ||
        [lindex $terminal 0] != 4 || [lindex $terminal 1] != 4} {
      close $handle
      error "P10.1R echo sweep command failed $label sample=$sample"
    }
    set fixed_snapshot [p10_read_p10_1r_snapshot fixed]
    set rotating_snapshot [p10_read_p10_1r_snapshot rotating]
    if {$sender eq "fixed"} {
      set sender_values $fixed_snapshot
      set receiver_values $rotating_snapshot
    } else {
      set sender_values $rotating_snapshot
      set receiver_values $fixed_snapshot
    }
    # Snapshot list indices 0/1 are generation/capability.  Register A0C is 2.
    set base 2
    set row [list $sample $module $direction $lane \
        [lindex $sender_values [expr {$base + 19 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 1 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 3 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 5 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 7 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 9 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 11 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 13 + $lane_index}]] \
        [lindex $receiver_values [expr {$base + 1 + $lane_index}]] \
        [lindex $receiver_values [expr {$base + 13 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 23 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 25 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 27 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 29 + $lane_index}]] \
        [lindex $sender_values [expr {$base + 31}]] \
        [lindex $sender_values [expr {$base + 32}]] \
        [lindex $sender_values [expr {$base + 33}]] \
        [lindex $sender_values [expr {$base + 34}]] \
        [lindex $receiver_values [expr {$base + 31}]] \
        [lindex $receiver_values [expr {$base + 32}]] \
        [lindex $receiver_values [expr {$base + 33}]] \
        [lindex $receiver_values [expr {$base + 34}]]]
    puts $handle [join $row "|"]
    flush $handle
    if {(($sample + 1) % 100) == 0} {
      p10_say "P10_1R_ECHO_SWEEP_PROGRESS=$label:[expr {$sample + 1}]/$sample_count"
    }
  }
  close $handle
  p10_say "P10_1R_ECHO_SWEEP_PASS=$label:module=$module,samples=$sample_count,path=$output"
}

proc p10_probe_1plus1 {label} {
  set fixed_config [p10_read32 fixed 0x43C00728]
  set rotating_config [p10_read32 rotating 0x43C00728]
  set fixed_caps [p10_read32 fixed 0x43C00714]
  set rotating_caps [p10_read32 rotating 0x43C00714]
  p10_say [format "P10_1_1PLUS1_CAPABILITY_READBACK=%s:fixed_cfg=0x%08X,rotating_cfg=0x%08X,fixed_caps=0x%08X,rotating_caps=0x%08X" \
      $label $fixed_config $rotating_config $fixed_caps $rotating_caps]
  p10_say "P10_1_1PLUS1_OUTCOME=SKIP_WITH_REASON"
  p10_say "P10_1_1PLUS1_REASON=single_endpoint_direction_bit_no_independent_per_lane_direction"
}

proc p10_reboot_role {role label} {
  global p10_elf
  p10_write32 $role 0x43C00718 0x0000001A
  after 10
  p10_select_cpu $role
  catch {stop}
  rst -processor
  dow $p10_elf($role)
  con
  p10_wait_ready $role $label
  set dump [p10_dump_mailbox $role $label]
  p10_say "P10_REBOOT_PASS_[string toupper $role]=$label:$dump"
  p10_resume $role
}

proc p10_rebootstrap_after_reset_recovery {label} {
  global p10_expected_build
  p10_say "P10_1_RESET_RECOVERY_REBOOT_BEGIN=$label"
  p10_reboot_role fixed "${label}_fixed_reset_recovery_reboot"
  p10_reboot_role rotating "${label}_rotating_reset_recovery_reboot"
  p10_verify_pl_safe fixed $p10_expected_build(fixed) 0x702000F0 "${label}_RESET_RECOVERED"
  p10_verify_pl_safe rotating $p10_expected_build(rotating) 0x702000A0 "${label}_RESET_RECOVERED"
  p10_say "P10_1_RESET_RECOVERY_REBOOT_PASS=$label"
}

proc p10_soak_case {label object_id size direction timeout_ms} {
  set fields [list CASE $label 3 0 2 3 $direction 2 257 $size 32 1 0 0 \
      $timeout_ms 0xA0100001 10 $object_id 0 0 0 0 1024 0 0 0 0 0 0]
  return [p10_case_dict $fields]
}

proc p10_run_soak {label duration_sec} {
  if {$duration_sec != 1800} { error "formal P10 soak must be exactly 1800 seconds" }
  set start [clock milliseconds]
  set deadline [expr {$start + 1800000}]
  set index 0
  p10_say "P10_SOAK_ACTIVE_START_MS=$start"
  while {[clock milliseconds] < $deadline} {
    p10_check_abort
    set now [clock milliseconds]
    set remaining [expr {$deadline - $now}]
    if {$remaining <= 10000} { after $remaining; break }
    set choice [expr {$index % 3}]
    set size [lindex {4096 65536 1048576} $choice]
    set direction [expr {$index & 1}]
    set timeout [expr {min(120000, max(1000, $remaining - 8000))}]
    set case_label [format "soak_%05d_%d_d%d" $index $size $direction]
    set d [p10_soak_case $case_label [expr {0x3A000000 + $index}] $size $direction $timeout]
    p10_execute_case $d ACCEPTANCE
    incr index
  }
  set finished [clock milliseconds]
  set elapsed [expr {$finished - $start}]
  p10_say "P10_SOAK_CASE_COUNT=$index"
  p10_say "P10_SOAK_ACTIVE_END_MS=$finished"
  p10_say "P10_SOAK_ACTIVE_ELAPSED_MS=$elapsed"
  if {$elapsed < 1800000 || $elapsed > 1800500} {
    error "P10 soak active window was not bounded to 1800 seconds: $elapsed ms"
  }
}

if {[llength $argv] ni {16 18}} {
  error "usage: p10_dual_xsdb_stage.tcl <xsdb-url> <fixed-serial> <rotating-serial> <fixed-bit> <rotating-bit> <fixed-elf> <rotating-elf> <fixed-ps7-init> <rotating-ps7-init> <plan> <dump-dir> <abort-file> <result> <stage> <authorization> <run-id> ?<fixed-build-id> <rotating-build-id>?"
}
set p10_xsdb_url [lindex $argv 0]
set p10_fixed_serial [lindex $argv 1]
set p10_rotating_serial [lindex $argv 2]
set p10_bit(fixed) [file normalize [lindex $argv 3]]
set p10_bit(rotating) [file normalize [lindex $argv 4]]
set p10_elf(fixed) [file normalize [lindex $argv 5]]
set p10_elf(rotating) [file normalize [lindex $argv 6]]
set p10_ps7(fixed) [file normalize [lindex $argv 7]]
set p10_ps7(rotating) [file normalize [lindex $argv 8]]
set p10_plan_file [file normalize [lindex $argv 9]]
set p10_dump_dir [file normalize [lindex $argv 10]]
set p10_abort_file [file normalize [lindex $argv 11]]
set p10_result_file [file normalize [lindex $argv 12]]
set p10_stage [lindex $argv 13]
set p10_authorization_file [file normalize [lindex $argv 14]]
set p10_run_id [lindex $argv 15]
set p10_expected_build(fixed) 0x50313046
set p10_expected_build(rotating) 0x50313052
if {[llength $argv] == 18} {
  foreach {role index} {fixed 16 rotating 17} {
    set value [lindex $argv $index]
    if {![regexp {^0x[0-9A-Fa-f]{8}$} $value]} {
      error "invalid P10 expected build ID for $role"
    }
    set p10_expected_build($role) $value
  }
}
set p10_connected 0
set p10_active_target_id -1
set p10_command_sequence 1000
set p10_active_case_label "boot"
file mkdir $p10_dump_dir
file mkdir [file dirname $p10_result_file]
set p10_result_handle [open $p10_result_file w]
set p10_observation_file [file join $p10_dump_dir observations.psv]
set p10_observation_handle [open $p10_observation_file w]
puts $p10_observation_handle "label|command|expected_status|flags|lane|direction|rate|weights|size|ring|cache|txoff|rxoff|timeout|session|path|object|dropdata|dropack|unavailable|rawtarget|spacing|stale|initialseq|faultflags|idle|injectmask|injectdelay|window|started_ms|finished_ms|sequence|fixed_status|rotating_status|fixed_state|rotating_state|fixed_dump_path|rotating_dump_path|fixed_p10_1_dump_path|rotating_p10_1_dump_path|fixed_p10_1r_dump_path|rotating_p10_1r_dump_path"
flush $p10_observation_handle
set p10_telemetry_file [file join $p10_dump_dir p10_1r_telemetry.psv]
set p10_telemetry_handle [open $p10_telemetry_file w]
puts $p10_telemetry_handle "captured_ms|sequence|label|role|snapshot_words_csv"
flush $p10_telemetry_handle

set rc [catch {
  if {![info exists ::env(RF_COMM_P10_HW_AUTH)] ||
      $::env(RF_COMM_P10_HW_AUTH) ne "P10_FASTTRACK_IMMUTABLE_AUTHORIZED"} {
    error "P10 immutable current-run environment marker required"
  }
  if {![regexp {^P10_1R-(PREFLIGHT|ECHO_TAIL|CROSSTALK|PHY_SANITY|ACK_TUNING|PERFORMANCE|STREAMING_64M|FORMAL_30MIN)$} $p10_stage]} { error "unsupported P10.1R XSDB stage" }
  if {![regexp {^p10_1r_[A-Za-z0-9_.-]+$} $p10_run_id]} { error "unsafe P10.1R run id" }
  if {$p10_fixed_serial eq $p10_rotating_serial} { error "ambiguous P10 role serials" }
  foreach required [list $p10_bit(fixed) $p10_bit(rotating) $p10_elf(fixed) \
      $p10_elf(rotating) $p10_ps7(fixed) $p10_ps7(rotating) $p10_plan_file \
      $p10_authorization_file] {
    if {![file isfile $required]} { error "missing immutable P10 input: $required" }
  }
  if {[file exists $p10_abort_file]} { error "P10 abort sentinel exists before launch" }

  set plan_handle [open $p10_plan_file r]
  set plan_text [read $plan_handle]
  close $plan_handle
  set parsed_plan {}
  foreach raw_line [split $plan_text "\n"] {
    set line [string trim $raw_line]
    if {$line eq "" || [string match "#*" $line]} { continue }
    if {![regexp {^[ -~]+$} $line]} { error "non-ASCII P10 plan line" }
    set fields [split $line]
    set kind [lindex $fields 0]
    if {$kind eq "CASE"} {
      lappend parsed_plan [list CASE [p10_case_dict $fields]]
    } elseif {$kind eq "REBOOT"} {
      if {[llength $fields] != 3 || [lindex $fields 1] ni {fixed rotating} ||
          ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 2]]} {
        error "invalid P10 REBOOT record"
      }
      lappend parsed_plan [list REBOOT [lindex $fields 1] [lindex $fields 2]]
    } elseif {$kind eq "SOAK"} {
      if {[llength $fields] != 3 || ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]] ||
          ![string is integer -strict [lindex $fields 2]] || [lindex $fields 2] != 1800} {
        error "invalid P10 SOAK record"
      }
      lappend parsed_plan [list SOAK [lindex $fields 1] [lindex $fields 2]]
    } elseif {$kind eq "P101_WINDOW"} {
      if {[llength $fields] != 6 ||
          ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]] ||
          ![string is integer -strict [lindex $fields 2]] ||
          ![string is integer -strict [lindex $fields 3]] ||
          ![string is integer -strict [lindex $fields 4]] ||
          ![string is integer -strict [lindex $fields 5]]} {
        error "invalid P10.1 WINDOW record"
      }
      lappend parsed_plan $fields
    } elseif {$kind eq "P101_PSRESET"} {
      if {[llength $fields] != 7 ||
          ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]] ||
          [lindex $fields 2] ni {fixed rotating}} {
        error "invalid P10.1 PSRESET record"
      }
      foreach index {3 4 5 6} {
        if {![string is integer -strict [lindex $fields $index]]} {
          error "invalid numeric P10.1 PSRESET field"
        }
      }
      lappend parsed_plan $fields
    } elseif {$kind eq "P101_FORMAL"} {
      if {[llength $fields] != 3 ||
          ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]] ||
          ![string is integer -strict [lindex $fields 2]] ||
          [lindex $fields 2] != 1800} {
        error "invalid P10.1 FORMAL record"
      }
      lappend parsed_plan $fields
    } elseif {$kind eq "P101_1PLUS1_PROBE"} {
      if {[llength $fields] != 2 ||
          ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]]} {
        error "invalid P10.1 1PLUS1 probe record"
      }
      lappend parsed_plan $fields
    } elseif {$kind eq "P101R_ECHO_SWEEP"} {
      if {[llength $fields] != 6 ||
          ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]]} {
        error "invalid P10.1R echo-sweep record"
      }
      foreach index {2 3 4 5} {
        if {![string is integer -strict [lindex $fields $index]]} {
          error "invalid numeric P10.1R echo-sweep field"
        }
      }
      lappend parsed_plan $fields
    } elseif {$kind eq "P101R_TIMED_CASE"} {
      if {[llength $fields] != 7 ||
          ![regexp {^[A-Za-z0-9_.-]+$} [lindex $fields 1]]} {
        error "invalid P10.1R timed-case record"
      }
      foreach index {2 3 4 5 6} {
        if {![string is integer -strict [lindex $fields $index]]} {
          error "invalid numeric P10.1R timed-case field"
        }
      }
      lappend parsed_plan $fields
    } else {
      error "unknown P10 plan record: $kind"
    }
  }
  if {[llength $parsed_plan] == 0} { error "empty P10 stage plan" }

  connect -url $p10_xsdb_url
  set p10_connected 1
  p10_wait_debug_targets
  p10_say "P10_XSDB_IDENTITY=PASS"
  p10_say "P10_XSDB_FIXED_SERIAL=$p10_fixed_serial"
  p10_say "P10_XSDB_ROTATING_SERIAL=$p10_rotating_serial"
  p10_say "P10_XSDB_STAGE=$p10_stage"
  p10_say "P10_XSDB_RUN_ID=$p10_run_id"
  p10_say [format "P10_XSDB_EXPECTED_BUILD_FIXED=0x%08X" $p10_expected_build(fixed)]
  p10_say [format "P10_XSDB_EXPECTED_BUILD_ROTATING=0x%08X" $p10_expected_build(rotating)]

  foreach role {fixed rotating} {
    p10_select_apu $role
    rst -system
    after 1000
    p10_wait_debug_targets
  }

  foreach role {fixed rotating} {
    p10_select_target $p10_fpga($role)
    fpga -file $p10_bit($role)
    p10_say "P10_CANDIDATE_PROGRAMMED_[string toupper $role]=1"
    after 1000
    p10_select_cpu $role
    source $p10_ps7($role)
    configparams force-mem-accesses 1
    set init_rc [catch { ps7_init; ps7_post_config } init_error]
    catch {configparams force-mem-accesses 0}
    if {$init_rc != 0} { error "P10 $role PS7 initialization failed: $init_error" }
    p10_say "P10_PS7_INITIALIZED_[string toupper $role]=1"
  }

  p10_verify_pl_safe fixed $p10_expected_build(fixed) 0x702000F0 PREBOOT
  p10_verify_pl_safe rotating $p10_expected_build(rotating) 0x702000A0 PREBOOT

  foreach role {fixed rotating} {
    p10_select_cpu $role
    rst -processor
    dow $p10_elf($role)
    p10_say "P10_PS_ELF_DOWNLOADED_[string toupper $role]=1"
    con
  }
  p10_wait_ready fixed initial_boot
  p10_wait_ready rotating initial_boot
  set fixed_ready [p10_dump_mailbox fixed "${p10_stage}_ready"]
  set rotating_ready [p10_dump_mailbox rotating "${p10_stage}_ready"]
  p10_say "P10_INITIAL_READY_DUMP_FIXED=$fixed_ready"
  p10_say "P10_INITIAL_READY_DUMP_ROTATING=$rotating_ready"
  p10_resume fixed
  p10_resume rotating
  p10_verify_pl_safe fixed $p10_expected_build(fixed) 0x702000F0 SAFE_BOOT
  p10_verify_pl_safe rotating $p10_expected_build(rotating) 0x702000A0 SAFE_BOOT
  p10_say "P10_SAFE_BOOT=PASS"

  foreach record $parsed_plan {
    set kind [lindex $record 0]
    if {$kind eq "CASE"} {
      p10_execute_case [lindex $record 1]
    } elseif {$kind eq "REBOOT"} {
      p10_reboot_role [lindex $record 1] [lindex $record 2]
    } elseif {$kind eq "SOAK"} {
      p10_run_soak [lindex $record 1] [lindex $record 2]
    } elseif {$kind eq "P101_WINDOW"} {
      p10_run_p101_window [lindex $record 1] [lindex $record 2] \
          [lindex $record 3] [lindex $record 4] [lindex $record 5]
    } elseif {$kind eq "P101_PSRESET"} {
      p10_execute_ps_service_reset [lindex $record 1] [lindex $record 2] \
          [lindex $record 3] [lindex $record 4] [lindex $record 5] \
          [lindex $record 6]
    } elseif {$kind eq "P101_FORMAL"} {
      p10_run_p101_formal [lindex $record 1] [lindex $record 2]
    } elseif {$kind eq "P101_1PLUS1_PROBE"} {
      p10_probe_1plus1 [lindex $record 1]
    } elseif {$kind eq "P101R_ECHO_SWEEP"} {
      p10_run_p101r_echo_sweep [lindex $record 1] [lindex $record 2] \
          [lindex $record 3] [lindex $record 4] [lindex $record 5]
    } elseif {$kind eq "P101R_TIMED_CASE"} {
      p10_run_p101r_timed_case [lindex $record 1] [lindex $record 2] \
          [lindex $record 3] [lindex $record 4] [lindex $record 5] \
          [lindex $record 6]
    }
  }

  set shutdown_fields [list CASE "${p10_stage}_endpoint_shutdown" 10 0 0 0 0 0 0 0 \
      8 0 0 0 10000 0 0 0 0 0 0 0 1024 0 0 0 0 0 0]
  p10_execute_case [p10_case_dict $shutdown_fields]
  p10_say "P10_ENDPOINT_SHUTDOWN_FIXED=PASS"
  p10_say "P10_ENDPOINT_SHUTDOWN_ROTATING=PASS"
  p10_say "P10_XSDB_STAGE_RESULT=PASS"
} error_text error_options]

if {$rc != 0} {
  foreach role {fixed rotating} {
    catch {p10_write32 $role 0x43C00718 0x0000001A}
  }
  p10_say "P10_ENDPOINT_SHUTDOWN_REQUESTED_ON_ERROR=1"
  p10_say "P10_XSDB_STAGE_RESULT=FAIL"
  p10_say "P10_XSDB_STAGE_ERROR=[p10_sanitize $error_text]"
}
catch {close $p10_observation_handle}
catch {close $p10_telemetry_handle}
catch {close $p10_result_handle}
if {$p10_connected} { catch {disconnect} }
if {$rc != 0} {
  puts stderr $error_text
  exit 41
}
exit 0
