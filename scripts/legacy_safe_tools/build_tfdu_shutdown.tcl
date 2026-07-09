set script_dir [file normalize [file dirname [info script]]]
set repo_root [file normalize [file join $script_dir ".." ".."]]
set out_dir [file join $repo_root "shutdown_bitstream"]
file mkdir $out_dir

read_verilog [file join $script_dir "tfdu_shutdown_top.v"]
read_xdc [file join $script_dir "tfdu_shutdown_j10_j11.xdc"]

synth_design -top tfdu_shutdown_top -part xc7z010clg400-1
opt_design
place_design
route_design
write_bitstream -force [file join $out_dir "tfdu_shutdown_j10_j11.bit"]
puts "TFDU_SHUTDOWN_BITSTREAM_READY [file join $out_dir tfdu_shutdown_j10_j11.bit]"
