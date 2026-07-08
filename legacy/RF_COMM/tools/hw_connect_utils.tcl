proc rf_hw_log {line} {
  if {[llength [info commands say]] > 0} {
    say $line
  } else {
    puts $line
  }
}

proc rf_hw_disconnect_stale {} {
  set stale_targets {}
  catch {set stale_targets [get_hw_targets -quiet *]}
  foreach target $stale_targets {
    catch {close_hw_target $target}
  }
  catch {disconnect_hw_server}
}

proc rf_hw_open_target {{hw_url "localhost:3121"} {jtag_frequency_hz 1000000}} {
  open_hw_manager
  rf_hw_disconnect_stale
  after 500

  connect_hw_server -url $hw_url
  set targets [get_hw_targets -quiet *]
  rf_hw_log "HW_TARGET_COUNT [llength $targets]"
  if {[llength $targets] == 0} {
    error "No hw_target found after connect_hw_server."
  }

  set target [lindex $targets 0]
  current_hw_target $target
  rf_hw_log "HW_TARGET $target"

  if {$jtag_frequency_hz > 0} {
    if {[catch {set_property PARAM.FREQUENCY $jtag_frequency_hz $target} freq_err]} {
      rf_hw_log "HW_JTAG_FREQUENCY_WARN $freq_err"
    } else {
      rf_hw_log "HW_JTAG_FREQUENCY_HZ $jtag_frequency_hz"
    }
  }

  if {[catch {open_hw_target $target} open_err]} {
    rf_hw_log "HW_TARGET_OPEN_RETRY $open_err"
    rf_hw_disconnect_stale
    after 1000
    connect_hw_server -url $hw_url
    set targets [get_hw_targets -quiet *]
    rf_hw_log "HW_TARGET_COUNT_RETRY [llength $targets]"
    if {[llength $targets] == 0} {
      error "No hw_target found after reconnect_hw_server."
    }
    set target [lindex $targets 0]
    current_hw_target $target
    if {$jtag_frequency_hz > 0} {
      catch {set_property PARAM.FREQUENCY $jtag_frequency_hz $target}
    }
    open_hw_target $target
  }

  return $target
}

proc rf_hw_find_zynq_device {} {
  foreach dev [get_hw_devices -quiet *] {
    set name [get_property NAME $dev]
    if {[string match -nocase *xc7z* $name] || [string match -nocase *7z* $name]} {
      return $dev
    }
  }
  return ""
}

proc rf_hw_open_zynq_device {{hw_url "localhost:3121"} {jtag_frequency_hz 1000000}} {
  set target [rf_hw_open_target $hw_url $jtag_frequency_hz]
  set dev [rf_hw_find_zynq_device]
  if {$dev eq ""} {
    error "No programmable Zynq/FPGA hw_device found. Devices: [get_hw_devices]"
  }
  current_hw_device $dev
  rf_hw_log "HW_DEVICE $dev"
  return $dev
}
