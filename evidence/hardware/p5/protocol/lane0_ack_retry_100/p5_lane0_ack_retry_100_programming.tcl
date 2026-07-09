set log_file {C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/hardware/p5/protocol/lane0_ack_retry_100/p5_lane0_ack_retry_100_programming.log}
set ila_dir {C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/hardware/p5/ila/lane0_ack_retry_100}
file mkdir $ila_dir
set fh [open $log_file "w"]
proc say {line} {
  global fh
  puts $line
  puts $fh $line
  flush $fh
}
say "P5_LANE0_ACK_RETRY_100_PROGRAM_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set bit_file {C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/vivado/ir_top_new_protocol_lane0_ack.bit}
if {![file exists $bit_file]} {
  say "P5_LANE0_ACK_RETRY_100_BITSTREAM_MISSING=$bit_file"
  close $fh
  exit 20
}
set ltx_file {C:/Users/user/Documents/RF_COMM_MULTILANE/evidence/generated/vivado/p4_auto_protocol_lane0_ack_debug.ltx}
set rc [catch {
  open_hw_manager
  connect_hw_server -url {localhost:3121}
  set targets [get_hw_targets -quiet *]
  say "P5_HW_TARGET_COUNT=[llength $targets]"
  if {[llength $targets] == 0} {
    error "No JTAG hw_target found."
  }
  set dev ""
  foreach target $targets {
    say "P5_HW_TARGET=$target"
    if {[catch {current_hw_target $target} target_err]} {
      say "P5_CURRENT_HW_TARGET_ERROR=$target_err"
      continue
    }
    if {[catch {set_property PARAM.FREQUENCY 1000000 $target} freq_err]} {
      say "P5_HW_JTAG_FREQUENCY_WARN=$freq_err"
    } else {
      say "P5_HW_JTAG_FREQUENCY_HZ=1000000"
    }
    if {[catch {open_hw_target $target} open_err]} {
      say "P5_OPEN_HW_TARGET_ERROR=$open_err"
      continue
    }
    foreach candidate [get_hw_devices -quiet *] {
      set part ""
      catch {set part [get_property PART $candidate]}
      say "P5_HW_DEVICE=$candidate PART=$part"
      if {[string match -nocase *xc7z010* $part] || [string match -nocase *7z010* $part]} {
        set dev $candidate
        break
      }
      if {$dev eq ""} {
        set dev $candidate
      }
    }
    if {$dev ne ""} {
      break
    }
    catch {close_hw_target $target}
  }
  if {$dev eq ""} {
    error "No programmable hw_device found."
  }
  current_hw_device $dev
  refresh_hw_device -update_hw_probes false $dev
  foreach prop {NAME PART IDCODE IS_PROGRAMMED PROGRAM.FILE} {
    if {[catch {set value [get_property $prop $dev]} prop_err]} {
      say "P5_LANE0_ACK_RETRY_100_DEVICE_PROP $prop ERROR=$prop_err"
    } else {
      say "P5_LANE0_ACK_RETRY_100_DEVICE_PROP $prop=$value"
    }
  }
  set_property PROGRAM.FILE $bit_file $dev
  if {$ltx_file ne "" && [file exists $ltx_file]} {
    set_property PROBES.FILE $ltx_file $dev
    say "P5_LANE0_ACK_RETRY_100_PROBES_FILE=$ltx_file"
  } else {
    say "P5_LANE0_ACK_RETRY_100_PROBES_FILE=MISSING"
  }
  program_hw_devices $dev
  if {3000 > 0} {
    after 3000
  }
  refresh_hw_device -update_hw_probes true $dev
  say "P5_LANE0_ACK_RETRY_100_BITSTREAM_PROGRAMMED=$bit_file"
  set ilas [get_hw_ilas -quiet *]
  set probes [get_hw_probes -quiet *]
  say "P5_HW_ILA_COUNT=[llength $ilas]"
  say "P5_HW_PROBE_COUNT=[llength $probes]"
  set capture_pass 0
  set capture_idx 0
  foreach ila $ilas {
    set wdb_file [file join $ila_dir "lane0_ack_retry_100_${capture_idx}.wdb"]
    set csv_file [file join $ila_dir "lane0_ack_retry_100_${capture_idx}.csv"]
    set ila_rc [catch {
      current_hw_ila $ila
      catch {set_property CONTROL.TRIGGER_POSITION 0 $ila}
      if {[catch {run_hw_ila -trigger_now $ila} trigger_err]} {
        say "P5_ILA_TRIGGER_NOW_WARN_${capture_idx}=$trigger_err"
        run_hw_ila $ila
      }
      wait_on_hw_ila $ila
      set data [upload_hw_ila_data $ila]
      write_hw_ila_data -force $wdb_file $data
      if {[catch {write_hw_ila_data -force -csv_file $csv_file $data} csv_err]} {
        say "P5_ILA_CSV_EXPORT_WARN_${capture_idx}=$csv_err"
      }
    } ila_err]
    if {$ila_rc == 0} {
      say "P5_ILA_CAPTURE_${capture_idx}=PASS"
      say "P5_ILA_CAPTURE_${capture_idx}_WDB=$wdb_file"
      if {[file exists $csv_file]} {
        say "P5_ILA_CAPTURE_${capture_idx}_CSV=$csv_file"
      }
      set capture_pass 1
    } else {
      say "P5_ILA_CAPTURE_${capture_idx}=FAIL"
      say "P5_ILA_CAPTURE_${capture_idx}_ERROR=$ila_err"
    }
    incr capture_idx
  }
  if {$capture_pass} {
    say "P5_ILA_CAPTURE=PASS"
  } elseif {[llength $ilas] == 0} {
    say "P5_ILA_CAPTURE=SKIP_NO_ILA"
  } else {
    say "P5_ILA_CAPTURE=FAIL"
  }
  say "P5_LANE0_ACK_RETRY_100_PROGRAM=PASS"
  catch {close_hw_target}
  catch {disconnect_hw_server}
  catch {close_hw_manager}
} err opts]
if {$rc != 0} {
  say "P5_LANE0_ACK_RETRY_100_PROGRAM=FAIL"
  say "P5_LANE0_ACK_RETRY_100_PROGRAM_ERROR=$err"
  catch {close_hw_target}
  catch {disconnect_hw_server}
  catch {close_hw_manager}
  close $fh
  exit 21
}
close $fh
exit 0
