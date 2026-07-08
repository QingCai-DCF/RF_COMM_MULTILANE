puts "RF_COMM_HW_DEBUG_LIST_START"

set script_dir [file dirname [file normalize [info script]]]
set repo_root [file normalize [file join $script_dir ".."]]
source [file join $repo_root tools hw_connect_utils.tcl]

if {[catch {
    rf_hw_open_target localhost:3121 1000000
} err]} {
    puts "HW_DEBUG_CONNECT_ERROR $err"
    exit 0
}

set dev [rf_hw_find_zynq_device]
if {$dev eq ""} {
    puts "HW_DEBUG_CONNECT_ERROR no_zynq_device"
    close_hw_manager
    exit 0
}
refresh_hw_device $dev

set hubs [get_hw_sio_gts -quiet *]
puts "HW_SIO_GT_COUNT [llength $hubs]"

set ilas [get_hw_ilas -quiet *]
puts "HW_ILA_COUNT [llength $ilas]"
foreach ila $ilas {
    puts "HW_ILA $ila"
    foreach probe [get_hw_probes -quiet -of_objects $ila] {
        puts "  PROBE $probe WIDTH=[get_property WIDTH $probe]"
    }
}

close_hw_manager
puts "RF_COMM_HW_DEBUG_LIST_DONE"
exit 0
