puts "RF_COMM_HW_CHECK_START"

set script_dir [file dirname [file normalize [info script]]]
set repo_root [file normalize [file join $script_dir ".."]]
source [file join $repo_root tools hw_connect_utils.tcl]

set hw_status "UNKNOWN"
set targets {}
set devices {}
set jtag_frequency_hz 1000000

if {[catch {
    rf_hw_open_target localhost:3121 $jtag_frequency_hz
} err]} {
    set hw_status "HW_SERVER_CONNECT_ERROR"
    puts "HW_STATUS $hw_status"
    puts "HW_ERROR $err"
    exit 0
}

if {[catch {set targets [get_hw_targets *]} target_err]} {
    set targets {}
    puts "HW_TARGET_COUNT 0"
    puts "HW_TARGET_ERROR $target_err"
} else {
    puts "HW_TARGET_COUNT [llength $targets]"
    foreach target $targets {
        puts "HW_TARGET $target"
    }
}

if {[llength $targets] == 0} {
    puts "HW_DEVICE_COUNT 0"
    puts "HW_STATUS NO_HW_TARGET"
    close_hw_manager
    exit 0
}

if {[catch {set devices [get_hw_devices *]} dev_err]} {
    set devices {}
    puts "HW_DEVICE_COUNT 0"
    puts "HW_DEVICE_ERROR $dev_err"
} else {
    puts "HW_DEVICE_COUNT [llength $devices]"
    foreach dev $devices {
        set part [get_property PART $dev]
        set idcode [get_property IDCODE $dev]
        puts "HW_DEVICE $dev PART=$part IDCODE=$idcode"
    }
}

if {[llength $devices] == 0} {
    set hw_status "NO_HW_DEVICE"
} else {
    set hw_status "HW_DEVICE_FOUND"
}

puts "HW_STATUS $hw_status"
close_hw_manager
exit 0
