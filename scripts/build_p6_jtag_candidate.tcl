set root_dir [file normalize [lindex $argv 0]]
set build_dir [file normalize "$root_dir/build/p6_jtag_candidate"]
set out_dir [file normalize "$root_dir/evidence/generated/vivado/p6_jtag_candidate"]
file mkdir $build_dir
file mkdir $out_dir

create_project p6_jtag_candidate $build_dir/project -part xc7z010clg400-1 -force
set source_files [list \
  "$root_dir/rtl/tfdu_lane_phy.sv" \
  "$root_dir/rtl/ir_4ppm_codec.sv" \
  "$root_dir/rtl/p6_dynamic_transport_engine.sv" \
  "$root_dir/rtl/p6_local_transport_regs.sv" \
  "$root_dir/rtl/p6_axi_lite_bridge.sv" \
  "$root_dir/rtl/p6_axi_peripheral.sv" \
  "$root_dir/rtl/p6_jtag_top.sv" \
]
add_files -fileset sources_1 $source_files
set_property top p6_jtag_top [current_fileset]

create_ip -name jtag_axi -vendor xilinx.com -library ip -module_name p6_jtag_axi_master
set_property -dict [list \
  CONFIG.PROTOCOL {2} \
  CONFIG.M_AXI_ADDR_WIDTH {32} \
  CONFIG.M_AXI_DATA_WIDTH {32} \
  CONFIG.SIGNAL_CLOCK.FREQ_HZ {64000000} \
] [get_ips p6_jtag_axi_master]
set_property GENERATE_SYNTH_CHECKPOINT false [get_files p6_jtag_axi_master.xci]
generate_target all [get_ips p6_jtag_axi_master]

read_xdc "$root_dir/constraints/active/PORT1.generated.xdc"
update_compile_order -fileset sources_1
synth_design -top p6_jtag_top -part xc7z010clg400-1

set cfgclk_pin [get_pins -hier -quiet *u_startupe2/CFGMCLK]
if {[llength $cfgclk_pin] > 0} {
  create_clock -name p6_cfgmclk -period 15.625 [lindex $cfgclk_pin 0]
}

set debug_clock_nets [get_nets -hier -quiet *cfgmclk*]
set debug_nets [lsort -unique -dictionary [concat \
  [get_nets -hier -quiet *engine_debug_status*] \
  [get_nets -hier -quiet *regs_debug_status*] \
  [get_nets -hier -quiet *engine_error_code*] \
  [get_nets -hier -quiet *engine_rx_good_mask*] \
]]
if {[llength $debug_clock_nets] > 0 && [llength $debug_nets] > 0} {
  create_debug_core p6_local_transport_ila ila
  set_property C_DATA_DEPTH 1024 [get_debug_cores p6_local_transport_ila]
  set_property C_TRIGIN_EN false [get_debug_cores p6_local_transport_ila]
  set_property C_TRIGOUT_EN false [get_debug_cores p6_local_transport_ila]
  set_property C_ADV_TRIGGER false [get_debug_cores p6_local_transport_ila]
  connect_debug_port p6_local_transport_ila/clk [lindex $debug_clock_nets 0]
  set_property port_width [llength $debug_nets] [get_debug_ports p6_local_transport_ila/probe0]
  connect_debug_port p6_local_transport_ila/probe0 $debug_nets
}

write_checkpoint -force "$out_dir/post_synth_p6_jtag_candidate.dcp"
report_drc -file "$out_dir/post_synth_drc_p6_jtag_candidate.rpt"
opt_design
place_design
route_design
phys_opt_design -directive AggressiveExplore
write_checkpoint -force "$out_dir/post_route_p6_jtag_candidate.dcp"
report_drc -file "$out_dir/post_route_drc_p6_jtag_candidate.rpt"
report_timing_summary -file "$out_dir/post_route_timing_summary_p6_jtag_candidate.rpt"
report_timing -max_paths 50 -sort_by group -file "$out_dir/post_route_timing_paths_p6_jtag_candidate.rpt"
report_utilization -file "$out_dir/post_route_utilization_p6_jtag_candidate.rpt"
if {[llength [get_debug_cores -quiet p6_local_transport_ila]] > 0} {
  write_debug_probes -force "$out_dir/p6_jtag_candidate.ltx"
}
write_bitstream -force "$out_dir/p6_jtag_candidate.bit"

set markers [open "$out_dir/p6_jtag_candidate_build_markers.txt" w]
puts $markers "P6_JTAG_CANDIDATE_BUILD=PASS"
puts $markers "P6_JTAG_AXI_LIVE_INGRESS=1"
puts $markers "P6_DYNAMIC_PAYLOAD_PHYSICAL_ENGINE=1"
puts $markers "P6_MAX_LANE_MASK=0x3"
puts $markers "P6_ETHERNET_USED=0"
puts $markers "P6_MOTION_USED=0"
puts $markers "P6_BITSTREAM=$out_dir/p6_jtag_candidate.bit"
puts $markers "P6_LTX=$out_dir/p6_jtag_candidate.ltx"
puts $markers "P6_DEBUG_NET_COUNT=[llength $debug_nets]"
close $markers
puts "P6_JTAG_CANDIDATE_BUILD=PASS"
puts "P6_BITSTREAM=$out_dir/p6_jtag_candidate.bit"
puts "P6_LTX=$out_dir/p6_jtag_candidate.ltx"
