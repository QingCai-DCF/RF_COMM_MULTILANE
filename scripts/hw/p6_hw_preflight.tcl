set root_dir [file normalize [lindex $argv 0]]
set hw_server_url [lindex $argv 1]
set jtag_frequency_hz [lindex $argv 2]
set result_file [file normalize [lindex $argv 3]]
source [file join $root_dir legacy RF_COMM tools hw_connect_utils.tcl]
set dev [rf_hw_open_zynq_device $hw_server_url $jtag_frequency_hz]
puts "P6_HW_PREFLIGHT_DEVICE=[get_property NAME $dev]"
puts "P6_HW_PREFLIGHT_PART=[get_property PART $dev]"
puts "P6_HW_PREFLIGHT_PROGRAM_FILE=[get_property PROGRAM.FILE $dev]"
puts "P6_HW_PREFLIGHT_ZYNQ=1"
puts "P6_HW_PREFLIGHT_RESULT=PASS"
set out [open $result_file w]
puts $out "P6_HW_PREFLIGHT_DEVICE=[get_property NAME $dev]"
puts $out "P6_HW_PREFLIGHT_PART=[get_property PART $dev]"
puts $out "P6_HW_PREFLIGHT_ZYNQ=1"
puts $out "P6_HW_PREFLIGHT_RESULT=PASS"
close $out
