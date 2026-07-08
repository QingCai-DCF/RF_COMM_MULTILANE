set repo_root [file normalize [file join [file dirname [info script]] ".."]]
set hw_url localhost:3121
set jtag_frequency_hz 1000000
source [file join $repo_root tools hw_connect_utils.tcl]

if {[llength $argv] >= 1 && [lindex $argv 0] ne ""} {
  set hw_url [lindex $argv 0]
}
if {[llength $argv] >= 2 && [lindex $argv 1] ne ""} {
  set jtag_frequency_hz [lindex $argv 1]
}

puts "HW_PREFLIGHT_BEGIN [clock format [clock seconds] -format {%Y-%m-%dT%H:%M:%S%z}]"
puts "HW_PREFLIGHT_URL $hw_url"
puts "HW_PREFLIGHT_JTAG_FREQUENCY_HZ $jtag_frequency_hz"

set exit_code 0
if {[catch {
  open_hw_manager
  rf_hw_disconnect_stale
  after 500

  connect_hw_server -url $hw_url
  set targets [get_hw_targets -quiet *]
  puts "HW_PREFLIGHT_TARGET_COUNT [llength $targets]"
  foreach target $targets {
    puts "HW_PREFLIGHT_TARGET $target"
  }

  if {[llength $targets] == 0} {
    set exit_code 2
    puts "HW_PREFLIGHT_RESULT FAIL_NO_TARGET"
  } else {
    set target [lindex $targets 0]
    current_hw_target $target
    if {$jtag_frequency_hz > 0} {
      if {[catch {set_property PARAM.FREQUENCY $jtag_frequency_hz $target} freq_err]} {
        puts "HW_PREFLIGHT_FREQ_WARN $freq_err"
      } else {
        puts "HW_PREFLIGHT_FREQ_SET $jtag_frequency_hz"
      }
    }

    if {[catch {open_hw_target $target} open_err]} {
      set exit_code 3
      puts "HW_PREFLIGHT_RESULT FAIL_OPEN_TARGET $open_err"
    } else {
      set devices [get_hw_devices -quiet *]
      puts "HW_PREFLIGHT_DEVICE_COUNT [llength $devices]"
      foreach dev $devices {
        set name [get_property NAME $dev]
        puts "HW_PREFLIGHT_DEVICE $dev NAME=$name"
      }

      set zynq [rf_hw_find_zynq_device]
      if {$zynq eq ""} {
        set exit_code 4
        puts "HW_PREFLIGHT_RESULT FAIL_NO_ZYNQ"
      } else {
        current_hw_device $zynq
        puts "HW_PREFLIGHT_ZYNQ $zynq"
        puts "HW_PREFLIGHT_RESULT PASS"
      }
    }
  }
} err]} {
  set exit_code 5
  puts "HW_PREFLIGHT_EXCEPTION $err"
}

catch {close_hw_manager}
puts "HW_PREFLIGHT_END [clock format [clock seconds] -format {%Y-%m-%dT%H:%M:%S%z}]"
exit $exit_code
