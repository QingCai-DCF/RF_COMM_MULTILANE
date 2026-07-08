set repo_root [file normalize [file join [file dirname [info script]] ".."]]
source [file join $repo_root tools hw_connect_utils.tcl]
set bit_file [file join $repo_root "shutdown_bitstream" "tfdu_shutdown_j10_j11.bit"]
set jtag_frequency_hz 1000000
if {![file exists $bit_file]} {
  error "Missing shutdown bitstream: $bit_file. Run tools/build_tfdu_shutdown.tcl first."
}

set dev [rf_hw_open_zynq_device localhost:3121 $jtag_frequency_hz]
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bit_file $dev
program_hw_devices $dev
puts "TFDU_SHUTDOWN_PROGRAMMED $bit_file"
