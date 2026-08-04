set root_dir [file normalize [lindex $argv 0]]
set build_dir [file normalize "$root_dir/build/p9_z7010_candidate"]
set out_dir [file normalize "$root_dir/evidence/generated/vivado/p9_z7010_candidate"]
file mkdir $build_dir
file mkdir $out_dir

create_project p9_z7010_candidate "$build_dir/project" -part xc7z010clg400-1 -force
set rtl_sources [list \
  "$root_dir/rtl/generated/tfdu_safety_config.svh" \
  "$root_dir/rtl/generated/ir_register_map_defs.svh" \
  "$root_dir/rtl/ir_seq_math_pkg.sv" \
  "$root_dir/rtl/ir_health_weighted_scheduler.sv" \
  "$root_dir/rtl/ir_selective_repeat_tx.sv" \
  "$root_dir/rtl/ir_selective_repeat_rx.sv" \
  "$root_dir/rtl/ir_ack_aggregator.sv" \
  "$root_dir/rtl/ir_data_plane_top.sv" \
  "$root_dir/rtl/ir_tfdu_exact_duty_accountant.sv" \
  "$root_dir/rtl/ir_tfdu_physical_module_safety.sv" \
  "$root_dir/rtl/tfdu_lane_phy.sv" \
  "$root_dir/rtl/ir_4ppm_codec.sv" \
  "$root_dir/rtl/p9_rate_4ppm_rx.sv" \
  "$root_dir/rtl/p9_4ppm_frame_tx.sv" \
  "$root_dir/rtl/p9_4ppm_frame_rx.sv" \
  "$root_dir/rtl/p10_1r_rx_admission.sv" \
  "$root_dir/rtl/p9_optical_transport_core.sv" \
  "$root_dir/rtl/p6_axi_lite_bridge.sv" \
  "$root_dir/rtl/p10_1_metric_counter.sv" \
  "$root_dir/rtl/p10_1_timer_snapshot.sv" \
  "$root_dir/rtl/p10_1_event_fifo.sv" \
  "$root_dir/rtl/p10_1_perf_monitor.sv" \
  "$root_dir/rtl/p10_fault_forensics.sv" \
  "$root_dir/rtl/p9_axi_dma_peripheral.sv" \
  "$root_dir/rtl/p9_axi_dma_peripheral_bd.v" \
]
add_files -fileset sources_1 $rtl_sources
set_property include_dirs [list "$root_dir/rtl"] [get_filesets sources_1]
read_xdc "$root_dir/constraints/active/PORT1.generated.xdc"

create_bd_design p9_ps_system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0]
set_property -dict [list \
  CONFIG.PCW_USE_M_AXI_GP0 {1} \
  CONFIG.PCW_USE_S_AXI_HP0 {1} \
  CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
  CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
  CONFIG.PCW_IRQ_F2P_INTR {1} \
  CONFIG.PCW_EN_CLK0_PORT {1} \
  CONFIG.PCW_EN_CLK1_PORT {1} \
  CONFIG.PCW_EN_CLK2_PORT {1} \
  CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {64.000000} \
  CONFIG.PCW_FPGA1_PERIPHERAL_FREQMHZ {100.000000} \
  CONFIG.PCW_FPGA2_PERIPHERAL_FREQMHZ {50.000000} \
] $ps
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
  -config {make_external "FIXED_IO, DDR" apply_board_preset "0" Master "Disable" Slave "Disable"} $ps

# Exact AX7010 PS/DDR board contract inherited from the P6/P7 hardware-proven
# platform.  These values are locked after generic PS7 automation.
set_property -dict [list \
  CONFIG.PCW_CRYSTAL_PERIPHERAL_FREQMHZ {33.333333} \
  CONFIG.PCW_APU_PERIPHERAL_FREQMHZ {666.666666} \
  CONFIG.PCW_PRESET_BANK0_VOLTAGE {LVCMOS 3.3V} \
  CONFIG.PCW_PRESET_BANK1_VOLTAGE {LVCMOS 1.8V} \
  CONFIG.PCW_UIPARAM_DDR_PARTNO {MT41J128M16 HA-125} \
  CONFIG.PCW_UIPARAM_DDR_DRAM_WIDTH {16 Bits} \
  CONFIG.PCW_UIPARAM_DDR_DEVICE_CAPACITY {2048 MBits} \
  CONFIG.PCW_UIPARAM_DDR_BUS_WIDTH {32 Bit} \
  CONFIG.PCW_UIPARAM_DDR_FREQ_MHZ {533.333333} \
  CONFIG.PCW_UIPARAM_DDR_T_FAW {40.0} \
  CONFIG.PCW_UIPARAM_DDR_ECC {Disabled} \
  CONFIG.PCW_UIPARAM_DDR_TRAIN_READ_GATE {1} \
  CONFIG.PCW_UIPARAM_DDR_TRAIN_DATA_EYE {1} \
  CONFIG.PCW_UIPARAM_DDR_TRAIN_WRITE_LEVEL {1} \
] $ps

set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0]
# P9 uses only the primary MM2S/S2MM payload streams.  Leaving the optional
# SG control/status stream enabled makes S2MM wait forever for an unconnected
# S_AXIS_STS packet after it has already written the payload to DDR.
set_property -dict [list \
  CONFIG.c_include_sg {1} \
  CONFIG.c_sg_include_stscntrl_strm {0} \
  CONFIG.c_sg_length_width {26} \
  CONFIG.c_addr_width {32} \
  CONFIG.c_include_mm2s {1} \
  CONFIG.c_include_s2mm {1} \
  CONFIG.c_include_mm2s_dre {1} \
  CONFIG.c_include_s2mm_dre {1} \
  CONFIG.c_m_axi_mm2s_data_width {32} \
  CONFIG.c_m_axis_mm2s_tdata_width {32} \
  CONFIG.c_m_axi_s2mm_data_width {32} \
  CONFIG.c_s_axis_s2mm_tdata_width {32} \
  CONFIG.c_mm2s_burst_size {16} \
  CONFIG.c_s2mm_burst_size {16} \
] $dma

update_compile_order -fileset sources_1
set p9 [create_bd_cell -type module -reference p9_axi_dma_peripheral_bd p9_peripheral_0]

# Three independent clocks: protocol 64 MHz, DMA/HP0 100 MHz, and GP0 AXI-Lite
# 50 MHz.  Every crossing uses a vendor asynchronous clock converter.
set rst64 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_protocol_64]
set rst100 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_dma_100]
set rst50 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_axil_50]
set stream_rst64 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_stream_protocol_64]
set stream_rst100 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_stream_dma_100]
set stream_rst50 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_stream_dma_50]
# stream_reset_request_o is an active-high pulse which is low while the data
# path is allowed to run.  proc_sys_reset defaults aux_reset_in to active-low;
# override that default so the idle request cannot hold DMA/AXIS in reset.
foreach stream_reset [list $stream_rst64 $stream_rst100 $stream_rst50] {
  set_property CONFIG.C_AUX_RESET_HIGH {1} $stream_reset
}
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins rst_protocol_64/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] [get_bd_pins rst_dma_100/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK2] [get_bd_pins rst_axil_50/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins rst_stream_protocol_64/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] [get_bd_pins rst_stream_dma_100/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK2] [get_bd_pins rst_stream_dma_50/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins rst_protocol_64/ext_reset_in]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins rst_dma_100/ext_reset_in]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] [get_bd_pins rst_axil_50/ext_reset_in]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] \
  [get_bd_pins rst_stream_protocol_64/ext_reset_in] \
  [get_bd_pins rst_stream_dma_100/ext_reset_in] [get_bd_pins rst_stream_dma_50/ext_reset_in]
connect_bd_net [get_bd_pins p9_peripheral_0/stream_reset_request_o] \
  [get_bd_pins rst_stream_protocol_64/aux_reset_in] \
  [get_bd_pins rst_stream_dma_100/aux_reset_in] [get_bd_pins rst_stream_dma_50/aux_reset_in]

# GP0 control fabric: DMA registers stay at 50 MHz; the P9 register peripheral
# crosses once into the 64 MHz protocol domain.
set gp_xbar [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 gp0_interconnect]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {2}] $gp_xbar
set axil_cc [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 p9_axil_clock_converter]
set_property CONFIG.PROTOCOL {AXI4LITE} $axil_cc
connect_bd_intf_net [get_bd_intf_pins processing_system7_0/M_AXI_GP0] [get_bd_intf_pins gp0_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins gp0_interconnect/M00_AXI] [get_bd_intf_pins axi_dma_0/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins gp0_interconnect/M01_AXI] [get_bd_intf_pins p9_axil_clock_converter/S_AXI]
connect_bd_intf_net [get_bd_intf_pins p9_axil_clock_converter/M_AXI] [get_bd_intf_pins p9_peripheral_0/s_axi]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK2] \
  [get_bd_pins processing_system7_0/M_AXI_GP0_ACLK] \
  [get_bd_pins gp0_interconnect/ACLK] [get_bd_pins gp0_interconnect/S00_ACLK] \
  [get_bd_pins gp0_interconnect/M00_ACLK] [get_bd_pins gp0_interconnect/M01_ACLK] \
  [get_bd_pins p9_axil_clock_converter/s_axi_aclk] [get_bd_pins axi_dma_0/s_axi_lite_aclk]
connect_bd_net [get_bd_pins rst_axil_50/interconnect_aresetn] \
  [get_bd_pins gp0_interconnect/ARESETN] [get_bd_pins gp0_interconnect/S00_ARESETN] \
  [get_bd_pins gp0_interconnect/M00_ARESETN] [get_bd_pins gp0_interconnect/M01_ARESETN]
connect_bd_net [get_bd_pins rst_axil_50/peripheral_aresetn] [get_bd_pins p9_axil_clock_converter/s_axi_aresetn]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] \
  [get_bd_pins p9_axil_clock_converter/m_axi_aclk] [get_bd_pins p9_peripheral_0/s_axi_aclk]
connect_bd_net [get_bd_pins rst_protocol_64/peripheral_aresetn] \
  [get_bd_pins p9_axil_clock_converter/m_axi_aresetn] [get_bd_pins p9_peripheral_0/s_axi_aresetn]

# Real SG AXI DMA masters share the 100 MHz PS HP0 port through the 7-series
# AXI Interconnect.  Unlike SmartConnect, this topology does not insert deep
# distributed-RAM packet buffers that consume a material fraction of Z7010.
set hp_xbar [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 hp0_interconnect]
set_property -dict [list CONFIG.NUM_SI {3} CONFIG.NUM_MI {1}] $hp_xbar
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXI_MM2S] [get_bd_intf_pins hp0_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXI_S2MM] [get_bd_intf_pins hp0_interconnect/S01_AXI]
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXI_SG] [get_bd_intf_pins hp0_interconnect/S02_AXI]
connect_bd_intf_net [get_bd_intf_pins hp0_interconnect/M00_AXI] [get_bd_intf_pins processing_system7_0/S_AXI_HP0]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] \
  [get_bd_pins processing_system7_0/S_AXI_HP0_ACLK] \
  [get_bd_pins hp0_interconnect/ACLK] \
  [get_bd_pins hp0_interconnect/S00_ACLK] [get_bd_pins hp0_interconnect/S01_ACLK] \
  [get_bd_pins hp0_interconnect/S02_ACLK] [get_bd_pins hp0_interconnect/M00_ACLK] \
  [get_bd_pins axi_dma_0/m_axi_sg_aclk] \
  [get_bd_pins axi_dma_0/m_axi_mm2s_aclk] [get_bd_pins axi_dma_0/m_axi_s2mm_aclk]
connect_bd_net [get_bd_pins rst_dma_100/interconnect_aresetn] \
  [get_bd_pins hp0_interconnect/ARESETN] \
  [get_bd_pins hp0_interconnect/S00_ARESETN] [get_bd_pins hp0_interconnect/S01_ARESETN] \
  [get_bd_pins hp0_interconnect/S02_ARESETN] [get_bd_pins hp0_interconnect/M00_ARESETN]
connect_bd_net [get_bd_pins rst_stream_dma_50/peripheral_aresetn] [get_bd_pins axi_dma_0/axi_resetn]

set mm2s_cc [create_bd_cell -type ip -vlnv xilinx.com:ip:axis_clock_converter:1.1 mm2s_axis_clock_converter]
set s2mm_cc [create_bd_cell -type ip -vlnv xilinx.com:ip:axis_clock_converter:1.1 s2mm_axis_clock_converter]
foreach cc [list $mm2s_cc $s2mm_cc] {
  set_property -dict [list CONFIG.TDATA_NUM_BYTES {4} CONFIG.HAS_TKEEP {1} CONFIG.HAS_TLAST {1}] $cc
}
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXIS_MM2S] [get_bd_intf_pins mm2s_axis_clock_converter/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins mm2s_axis_clock_converter/M_AXIS] [get_bd_intf_pins p9_peripheral_0/s_axis]
connect_bd_intf_net [get_bd_intf_pins p9_peripheral_0/m_axis] [get_bd_intf_pins s2mm_axis_clock_converter/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins s2mm_axis_clock_converter/M_AXIS] [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] \
  [get_bd_pins mm2s_axis_clock_converter/s_axis_aclk] [get_bd_pins s2mm_axis_clock_converter/m_axis_aclk]
connect_bd_net [get_bd_pins rst_stream_dma_100/peripheral_aresetn] \
  [get_bd_pins mm2s_axis_clock_converter/s_axis_aresetn] [get_bd_pins s2mm_axis_clock_converter/m_axis_aresetn]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] \
  [get_bd_pins mm2s_axis_clock_converter/m_axis_aclk] [get_bd_pins s2mm_axis_clock_converter/s_axis_aclk]
connect_bd_net [get_bd_pins rst_stream_protocol_64/peripheral_aresetn] \
  [get_bd_pins mm2s_axis_clock_converter/m_axis_aresetn] [get_bd_pins s2mm_axis_clock_converter/s_axis_aresetn]

set irq_concat [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 dma_irq_concat]
set_property CONFIG.NUM_PORTS {2} $irq_concat
connect_bd_net [get_bd_pins axi_dma_0/mm2s_introut] [get_bd_pins dma_irq_concat/In0]
connect_bd_net [get_bd_pins axi_dma_0/s2mm_introut] [get_bd_pins dma_irq_concat/In1]
connect_bd_net [get_bd_pins dma_irq_concat/dout] [get_bd_pins processing_system7_0/IRQ_F2P]

foreach pin_name [list ir_mode_out_0 ir_rx_in_0 ir_sd_0 ir_tx_out_0 loop_mode_b0 loop_rx_b0 loop_sd_b0 loop_tx_b0] {
  set pin [get_bd_pins "p9_peripheral_0/$pin_name"]
  make_bd_pins_external $pin
  set generated [get_bd_ports "${pin_name}_0"]
  if {[llength $generated] == 1} { set_property name $pin_name $generated }
}

assign_bd_address
assign_bd_address -offset 0x40400000 -range 64K \
  -target_address_space [get_bd_addr_spaces processing_system7_0/Data] \
  [get_bd_addr_segs axi_dma_0/S_AXI_LITE/Reg] -force
assign_bd_address -offset 0x43C00000 -range 4K \
  -target_address_space [get_bd_addr_spaces processing_system7_0/Data] \
  [get_bd_addr_segs p9_peripheral_0/s_axi/reg0] -force

validate_bd_design
save_bd_design
generate_target all [get_files p9_ps_system.bd]
make_wrapper -files [get_files p9_ps_system.bd] -top
add_files -norecurse "$build_dir/project/p9_z7010_candidate.gen/sources_1/bd/p9_ps_system/hdl/p9_ps_system_wrapper.v"
set_property top p9_ps_system_wrapper [current_fileset]
update_compile_order -fileset sources_1

set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%" ||
    ![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {
  error "P9 implementation did not complete: [get_property STATUS [get_runs impl_1]]"
}
open_run impl_1
report_drc -file "$out_dir/post_route_drc_p9_candidate.rpt"
report_methodology -file "$out_dir/post_route_methodology_p9_candidate.rpt"
report_timing_summary -report_unconstrained -check_timing_verbose \
  -file "$out_dir/post_route_timing_summary_p9_candidate.rpt"
report_utilization -hierarchical -file "$out_dir/post_route_utilization_p9_candidate.rpt"
report_cdc -details -file "$out_dir/post_route_cdc_p9_candidate.rpt"
report_clock_interaction -file "$out_dir/post_route_clock_interaction_p9_candidate.rpt"

set drc_critical 0
set drc_error 0
foreach violation [get_drc_violations -quiet] {
  set severity [get_property SEVERITY $violation]
  if {[string match -nocase "*critical*" $severity]} { incr drc_critical }
  if {[string equal -nocase $severity "error"]} { incr drc_error }
}
set reqp_1839 [llength [get_drc_violations -quiet REQP-1839*]]
set methodology_critical 0
foreach violation [get_methodology_violations -quiet] {
  if {[string match -nocase "*critical*" [get_property SEVERITY $violation]]} {
    incr methodology_critical
  }
}
set cdc_critical 0
if {![catch {set cdc_violations [get_cdc_violations -quiet]}]} {
  foreach violation $cdc_violations {
    if {[string match -nocase "*critical*" [get_property SEVERITY $violation]]} {
      incr cdc_critical
    }
  }
}
if {$drc_critical != 0 || $drc_error != 0 || $reqp_1839 != 0 ||
    $methodology_critical != 0 || $cdc_critical != 0} {
  error "P9 signoff severity gate failed: DRC_CRITICAL=$drc_critical DRC_ERROR=$drc_error REQP_1839=$reqp_1839 METHODOLOGY_CRITICAL=$methodology_critical CDC_CRITICAL=$cdc_critical"
}
write_checkpoint -force "$out_dir/post_route_p9_candidate.dcp"
write_bitstream -force "$out_dir/ir_p9_z7010_2lane_candidate.bit"
write_hw_platform -fixed -include_bit -force -file "$out_dir/ir_p9_z7010_2lane.xsa"

set marker [open "$out_dir/p9_candidate_build_markers.txt" w]
puts $marker "P9_CANDIDATE_BUILD=PASS"
puts $marker "P9_PART=[get_property PART [current_project]]"
puts $marker "P9_TOP=p9_ps_system_wrapper"
puts $marker "P9_P9_AXI_BASE=0x43C00000"
puts $marker "P9_DMA_AXI_BASE=0x40400000"
puts $marker "P9_DMA_MODE=SCATTER_GATHER"
puts $marker "P9_DMA_SG_STSCNTRL_STREAM=DISABLED"
puts $marker "P9_DMA_HP_PORT=S_AXI_HP0"
puts $marker "P9_DMA_DATA_WIDTH=32"
puts $marker "P9_PROTOCOL_CLOCK_HZ=64000000"
puts $marker "P9_DMA_CLOCK_HZ=100000000"
puts $marker "P9_AXIL_CLOCK_HZ=50000000"
puts $marker "P9_STREAM_RESET_DOMAINS=PROTOCOL64_DMA100_AXIL50"
puts $marker "P9_STREAM_AUX_RESET_ACTIVE_HIGH=1"
puts $marker "P9_CANONICAL_XDC=constraints/active/PORT1.generated.xdc"
puts $marker "P9_DRC_CRITICAL_COUNT=$drc_critical"
puts $marker "P9_DRC_ERROR_COUNT=$drc_error"
puts $marker "P9_REQP_1839_COUNT=$reqp_1839"
puts $marker "P9_METHODOLOGY_CRITICAL_COUNT=$methodology_critical"
puts $marker "P9_CDC_CRITICAL_COUNT=$cdc_critical"
close $marker
puts "P9_CANDIDATE_BUILD=PASS"
