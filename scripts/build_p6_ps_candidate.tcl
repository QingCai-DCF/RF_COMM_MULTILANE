set root_dir [file normalize [lindex $argv 0]]
set build_dir [file normalize "$root_dir/build/p6_ps_candidate"]
set out_dir [file normalize "$root_dir/evidence/generated/vivado/p6_ps_candidate"]
file mkdir $build_dir
file mkdir $out_dir

create_project p6_ps_candidate "$build_dir/project" -part xc7z010clg400-1 -force
add_files -fileset sources_1 [list \
  "$root_dir/rtl/tfdu_lane_phy.sv" \
  "$root_dir/rtl/ir_4ppm_codec.sv" \
  "$root_dir/rtl/p6_dynamic_transport_engine.sv" \
  "$root_dir/rtl/p6_local_transport_regs.sv" \
  "$root_dir/rtl/p6_axi_lite_bridge.sv" \
  "$root_dir/rtl/p6_axi_peripheral.sv" \
  "$root_dir/rtl/p6_axi_peripheral_bd.v" \
]
read_xdc "$root_dir/constraints/active/PORT1.generated.xdc"

create_bd_design p6_ps_system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0]
set_property -dict [list \
  CONFIG.PCW_USE_M_AXI_GP0 {1} \
  CONFIG.PCW_EN_CLK0_PORT {1} \
  CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {64.000000} \
] $ps
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {make_external "FIXED_IO, DDR" apply_board_preset "0" Master "Disable" Slave "Disable"} $ps

update_compile_order -fileset sources_1
set p6 [create_bd_cell -type module -reference p6_axi_peripheral_bd p6_peripheral_0]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config [list \
  Clk_master {/processing_system7_0/FCLK_CLK0 (64 MHz)} \
  Clk_slave {/processing_system7_0/FCLK_CLK0 (64 MHz)} \
  Clk_xbar {/processing_system7_0/FCLK_CLK0 (64 MHz)} \
  Master {/processing_system7_0/M_AXI_GP0} \
  Slave {/p6_peripheral_0/s_axi} \
  ddr_seg {Auto} \
  intc_ip {Auto} \
  master_apm {0} \
] [get_bd_intf_pins p6_peripheral_0/s_axi]
assign_bd_address -offset 0x43C00000 -range 4K -target_address_space [get_bd_addr_spaces processing_system7_0/Data] [get_bd_addr_segs p6_peripheral_0/s_axi/reg0] -force

foreach pin_name [list ir_mode_out_0 ir_rx_in_0 ir_sd_0 ir_tx_out_0 loop_mode_b0 loop_rx_b0 loop_sd_b0 loop_tx_b0] {
  set pin [get_bd_pins "p6_peripheral_0/$pin_name"]
  make_bd_pins_external $pin
  set generated [get_bd_ports "${pin_name}_0"]
  if {[llength $generated] == 1} { set_property name $pin_name $generated }
}

validate_bd_design
save_bd_design
generate_target all [get_files p6_ps_system.bd]
make_wrapper -files [get_files p6_ps_system.bd] -top
add_files -norecurse "$build_dir/project/p6_ps_candidate.gen/sources_1/bd/p6_ps_system/hdl/p6_ps_system_wrapper.v"
set_property top p6_ps_system_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
open_run impl_1
phys_opt_design -directive AggressiveExplore
route_design
report_drc -file "$out_dir/post_route_drc_p6_ps_candidate.rpt"
report_timing_summary -file "$out_dir/post_route_timing_summary_p6_ps_candidate.rpt"
report_utilization -file "$out_dir/post_route_utilization_p6_ps_candidate.rpt"
write_bitstream -force "$out_dir/p6_ps_candidate.bit"
write_hw_platform -fixed -include_bit -force -file "$out_dir/p6_ps_candidate.xsa"

set markers [open "$out_dir/p6_ps_candidate_build_markers.txt" w]
puts $markers "P6_PS_CANDIDATE_BUILD=PASS"
puts $markers "P6_PS_AXI_BASE=0x43C00000"
puts $markers "P6_PS_XSA=$out_dir/p6_ps_candidate.xsa"
puts $markers "P6_PS_BITSTREAM=$out_dir/p6_ps_candidate.bit"
puts $markers "P6_ETHERNET_USED=0"
puts $markers "P6_MOTION_USED=0"
close $markers
puts "P6_PS_CANDIDATE_BUILD=PASS"
