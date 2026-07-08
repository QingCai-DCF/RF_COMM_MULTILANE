# XSCT board bring-up script for the RF_COMM PS bridge.
#
# Usage from the repository root:
#   & 'D:\Xilinx\Vitis\2023.1\bin\xsct.bat' '.\software\ps_lwip_bridge\run_on_hw.tcl'
#
# Optional hw_server URL:
#   & 'D:\Xilinx\Vitis\2023.1\bin\xsct.bat' '.\software\ps_lwip_bridge\run_on_hw.tcl' TCP:localhost:3121

set script_dir [file dirname [file normalize [info script]]]
set repo_root  [file normalize [file join $script_dir ".." ".."]]

set bit_file  [file join $repo_root "TFDU_VFIR_Client_Array" "TFDU_VFIR_Client.runs" "impl_1" "design_shiboqi_wrapper.bit"]
set bit_fallback [file join $repo_root "TFDU_VFIR_Client_Array" "design_shiboqi_wrapper.bit"]
set elf_file  [file join $repo_root "software" "_vitis_ws" "rf_comm_ps_bridge" "Debug" "rf_comm_ps_bridge.elf"]
set init_file [file join $repo_root "software" "_vitis_ws" "design_shiboqi_wrapper" "hw" "ps7_init.tcl"]

if {![file exists $bit_file] && [file exists $bit_fallback]} {
    set bit_file $bit_fallback
}

foreach f [list $bit_file $elf_file $init_file] {
    if {![file exists $f]} {
        error "Required file is missing: $f"
    }
}

puts "RF_COMM hardware run"
puts "  bit:  $bit_file"
puts "  elf:  $elf_file"
puts "  init: $init_file"

if {[llength $argv] > 0} {
    set hw_url [lindex $argv 0]
    puts "Connecting to hw_server: $hw_url"
    connect -url $hw_url
} else {
    puts "Connecting to default hw_server"
    connect
}

after 1000

puts "Resetting PS system"
targets -set -filter {name =~ "APU*"}
rst -system
after 3000

puts "Programming FPGA"
targets -set -filter {name =~ "xc7z*"}
fpga -file $bit_file
after 1000

puts "Running PS7 init"
targets -set -filter {name =~ "APU*"}
source $init_file
ps7_init
ps7_post_config

puts "Downloading and starting PS bridge ELF"
targets -set -filter {name =~ "*Cortex-A9*#0"}
rst -processor
after 1000
dow $elf_file
con

puts "PS bridge started. Check UART for IP address, then connect TCP port 5001."
