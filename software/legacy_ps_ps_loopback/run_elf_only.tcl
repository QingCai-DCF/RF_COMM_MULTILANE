# XSCT script: start the RF_COMM PS-PS loopback ELF without programming FPGA.
# Use after program_fpga_init_ps7.tcl and after Vivado ILA has been armed.
#
# Usage from the repository root:
#   & 'D:\Xilinx\Vitis\2023.1\bin\xsct.bat' '.\software\ps_ps_loopback\run_elf_only.tcl'

set script_dir [file dirname [file normalize [info script]]]
set repo_root  [file normalize [file join $script_dir ".." ".."]]

set elf_file  [file join $repo_root "software" "_vitis_ws_ps_ps_loopback" "rf_comm_ps_ps_loopback" "Debug" "rf_comm_ps_ps_loopback.elf"]

if {![file exists $elf_file]} {
    error "Required file is missing: $elf_file"
}

puts "RF_COMM start PS-PS loopback ELF only"
puts "  elf:  $elf_file"

if {[llength $argv] > 0} {
    set hw_url [lindex $argv 0]
    puts "Connecting to hw_server: $hw_url"
    connect -url $hw_url
} else {
    puts "Connecting to default hw_server"
    connect
}

after 1000

puts "Downloading and starting PS-PS loopback ELF"
targets -set -filter {name =~ "*Cortex-A9*#0"}
rst -processor
after 1000
dow $elf_file
con

puts "PS_ELF_STARTED_NO_FPGA"

