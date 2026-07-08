set repo_root [file normalize [file join [file dirname [info script]] ".."]]
set src_dir [file join $repo_root "IPs" "ip_ir_array" "src"]
set report_dir [file join $repo_root "reports"]
file mkdir $report_dir

set_param general.maxThreads 16

foreach src_file [list \
  "ir_protocol_pkg.sv" \
  "crc32_gen.sv" \
  "cdc_sync.sv" \
  "ir_axis_async_fifo.sv" \
  "ir_axi_regs.sv" \
  "ir_tx_4ppm_frame.sv" \
  "ir_rx_4ppm_frame.sv" \
  "ir_lane_frame_source.sv" \
  "ir_lane_frame_sink.sv" \
  "ir_comm_lane.sv" \
  "ir_array_tx_mgr.sv" \
  "ir_array_rx_mgr.sv" \
  "ir_array_top.sv" \
  "ir_txonly_ack_axi.sv" \
  "ir_stream_array_top.sv" \
  "ir_stream_array_top_axi.sv" \
  "ir_array_top_axi.sv" \
] {
  set path [file join $src_dir $src_file]
  if {![file exists $path]} {
    error "Missing source: $path"
  }
  read_verilog -sv $path
}

set stamp [clock format [clock seconds] -format "%Y%m%d_%H%M%S"]

synth_design -top ir_array_top_axi -part xc7z010clg400-1 -mode out_of_context \
  -generic LANE_COUNT=4 \
  -generic STREAM_FULL_MODE=1 \
  -generic STREAM_NODE_ID=0 \
  -generic MAX_PACKET_BYTES=256 \
  -generic FRAGMENT_BYTES=64 \
  -generic MAX_FRAGS=4 \
  -generic MAX_FRAME_BYTES=78 \
  -generic MAX_RETRY=4 \
  -generic CNT_CHIP_MAX=7 \
  -generic CNT_PREAMBLE=16 \
  -generic FRAG_TIMEOUT_CYCLES=120000 \
  -generic TX_POST_ACK_GUARD_CYCLES=1024 \
  -generic RX_TO_TX_GUARD_CYCLES=1024 \
  -generic REASSEMBLY_TIMEOUT_CYCLES=200000

set hier_report [file join $report_dir "util_ir_array_top_axi_stream_4lane_ooc_${stamp}.rpt"]
set flat_report [file join $report_dir "util_ir_array_top_axi_stream_4lane_ooc_flat_${stamp}.rpt"]
set timing_report [file join $report_dir "timing_ir_array_top_axi_stream_4lane_ooc_${stamp}.rpt"]

create_clock -name s_axi_aclk -period 10.000 [get_ports s_axi_aclk]
create_clock -name clk_phy -period 15.625 [get_ports clk_phy]
set_clock_groups -asynchronous -group [get_clocks s_axi_aclk] -group [get_clocks clk_phy]

set cdc_ff1_d_pins [get_pins -quiet \
  -of_objects [get_cells -hierarchical -filter {NAME =~ *sync_ff1_reg*}] \
  -filter {NAME =~ *D}]
if {[llength $cdc_ff1_d_pins] != 0} {
  set_false_path -to $cdc_ff1_d_pins
}

report_utilization -hierarchical -hierarchical_depth 8 -file $hier_report
report_utilization -file $flat_report
report_timing_summary -file $timing_report

puts "IR_ARRAY_TOP_AXI_STREAM_4LANE_OOC_SYNTH_DONE"
puts "HIER_UTIL_REPORT=$hier_report"
puts "FLAT_UTIL_REPORT=$flat_report"
puts "TIMING_REPORT=$timing_report"
