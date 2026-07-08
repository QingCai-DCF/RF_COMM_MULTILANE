set repo_root [file normalize [file join [file dirname [info script]] ".."]]
set src_dir [file join $repo_root "IPs" "ip_ir_array" "src"]
set report_dir [file join $repo_root "reports"]
file mkdir $report_dir

read_verilog -sv [file join $src_dir "ir_protocol_pkg.sv"]
read_verilog -sv [file join $src_dir "crc32_gen.sv"]
read_verilog -sv [file join $src_dir "ir_tx_4ppm_frame.sv"]
read_verilog -sv [file join $src_dir "ir_rx_4ppm_frame.sv"]
read_verilog -sv [file join $src_dir "ir_stream_array_top.sv"]

synth_design -top ir_stream_array_top -part xc7z010clg400-1 \
  -generic LANE_COUNT=4 \
  -generic NODE_ID=0 \
  -generic MAX_PACKET_BYTES=256 \
  -generic FRAGMENT_BYTES=64 \
  -generic MAX_RETRY=4 \
  -generic CNT_CHIP_MAX=7 \
  -generic CNT_PREAMBLE=16 \
  -generic FRAG_TIMEOUT_CYCLES=120000 \
  -generic BACKOFF_SLOT_CYCLES=1024 \
  -generic REASSEMBLY_TIMEOUT_CYCLES=200000

report_utilization -hierarchical -hierarchical_depth 8 \
  -file [file join $report_dir "util_ir_stream_array_top_4lane_ooc_20260605.rpt"]
report_utilization \
  -file [file join $report_dir "util_ir_stream_array_top_4lane_ooc_flat_20260605.rpt"]
puts "IR_STREAM_4LANE_OOC_SYNTH_DONE"
