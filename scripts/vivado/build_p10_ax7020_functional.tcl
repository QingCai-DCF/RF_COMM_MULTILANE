set root_dir [file normalize [lindex $argv 0]]
set endpoint_role_name [string tolower [lindex $argv 1]]
set out_dir [file normalize [lindex $argv 2]]
set lane_count 2
if {[llength $argv] > 3} { set lane_count [lindex $argv 3] }
set campaign p10
if {[llength $argv] > 4} { set campaign [string tolower [lindex $argv 4]] }
if {$lane_count != 2 && $lane_count != 4} {
  error "P10 AX7020 build lane_count must be 2 or 4"
}

if {$endpoint_role_name eq "fixed"} {
  set endpoint_role 1
  if {$lane_count == 4} {
    set profile_id P10_2_AX7020_FIXED_4LANE
    set xdc_file "$root_dir/board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc"
  } else {
    set profile_id P10_AX7020_FIXED_2LANE
    set xdc_file "$root_dir/board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc"
  }
} elseif {$endpoint_role_name eq "rotating"} {
  set endpoint_role 2
  if {$lane_count == 4} {
    set profile_id P10_2_AX7020_ROTATING_4LANE
    set xdc_file "$root_dir/board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc"
  } else {
    set profile_id P10_AX7020_ROTATING_2LANE
    set xdc_file "$root_dir/board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc"
  }
} else {
  error "P10 endpoint role must be fixed or rotating"
}

# Vivado 2023.1 still enforces a 260-byte path limit for generated OOC files on
# Windows.  Keep the disposable project path deliberately short; all retained
# reports and artifacts are written to out_dir in the worktree.
set build_dir [file normalize "C:/p10_vivado/${campaign}_${endpoint_role_name}_${lane_count}lane"]
file mkdir $build_dir
file mkdir $out_dir
set project_name "p10_ax7020_${endpoint_role_name}_${lane_count}lane_functional"
create_project $project_name "$build_dir/project" \
  -part xc7z020clg400-2 -force

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
  "$root_dir/rtl/p10_lane_activity_leds.sv" \
  "$root_dir/rtl/p10_2_lane_activity_leds.sv" \
  "$root_dir/rtl/p10_axi_dma_endpoint_peripheral_bd.v" \
]
add_files -fileset sources_1 $rtl_sources
set_property include_dirs [list "$root_dir/rtl"] [get_filesets sources_1]
read_xdc $xdc_file

create_bd_design p10_ps_system
set ps [create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
  -config {make_external "FIXED_IO, DDR" apply_board_preset "0" Master "Disable" Slave "Disable"} $ps
source "$root_dir/board_profiles/ax7020_common/p10_ps7_config.tcl"
p10_apply_ax7020_ps7_config $ps [expr {$campaign in {p10_3 p10_3f p10_4}}]

set dma [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0]
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
set endpoint [create_bd_cell -type module -reference p10_axi_dma_endpoint_peripheral_bd p10_endpoint_0]
set_property CONFIG.ENDPOINT_ROLE $endpoint_role $endpoint
set_property CONFIG.LANE_COUNT $lane_count $endpoint
if {$campaign eq "p10_3"} {
  set_property CONFIG.BUILD_ID_OVERRIDE \
      [expr {$endpoint_role == 1 ? 0x50333446 : 0x50333452}] $endpoint
} elseif {$campaign eq "p10_3f"} {
  set_property CONFIG.BUILD_ID_OVERRIDE \
      [expr {$endpoint_role == 1 ? 0x50334646 : 0x50334652}] $endpoint
} elseif {$campaign eq "p10_4"} {
  set_property CONFIG.BUILD_ID_OVERRIDE \
      [expr {$endpoint_role == 1 ? 0x50343446 : 0x50343452}] $endpoint
}

set rst64 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_protocol_64]
set rst100 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_dma_100]
set rst50 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_axil_50]
set stream_rst64 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_stream_protocol_64]
set stream_rst100 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_stream_dma_100]
set stream_rst50 [create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_stream_dma_50]
foreach stream_reset [list $stream_rst64 $stream_rst100 $stream_rst50] {
  set_property CONFIG.C_AUX_RESET_HIGH {1} $stream_reset
}

connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] \
  [get_bd_pins rst_protocol_64/slowest_sync_clk] \
  [get_bd_pins rst_stream_protocol_64/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK1] \
  [get_bd_pins rst_dma_100/slowest_sync_clk] \
  [get_bd_pins rst_stream_dma_100/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK2] \
  [get_bd_pins rst_axil_50/slowest_sync_clk] \
  [get_bd_pins rst_stream_dma_50/slowest_sync_clk]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] \
  [get_bd_pins rst_protocol_64/ext_reset_in] \
  [get_bd_pins rst_dma_100/ext_reset_in] \
  [get_bd_pins rst_axil_50/ext_reset_in] \
  [get_bd_pins rst_stream_protocol_64/ext_reset_in] \
  [get_bd_pins rst_stream_dma_100/ext_reset_in] \
  [get_bd_pins rst_stream_dma_50/ext_reset_in]
connect_bd_net [get_bd_pins p10_endpoint_0/stream_reset_request_o] \
  [get_bd_pins rst_stream_protocol_64/aux_reset_in] \
  [get_bd_pins rst_stream_dma_100/aux_reset_in] \
  [get_bd_pins rst_stream_dma_50/aux_reset_in]

set gp_xbar [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_interconnect:2.1 gp0_interconnect]
set_property -dict [list CONFIG.NUM_SI {1} CONFIG.NUM_MI {2}] $gp_xbar
set axil_cc [create_bd_cell -type ip -vlnv xilinx.com:ip:axi_clock_converter:2.1 p10_axil_clock_converter]
set_property CONFIG.PROTOCOL {AXI4LITE} $axil_cc
connect_bd_intf_net [get_bd_intf_pins processing_system7_0/M_AXI_GP0] [get_bd_intf_pins gp0_interconnect/S00_AXI]
connect_bd_intf_net [get_bd_intf_pins gp0_interconnect/M00_AXI] [get_bd_intf_pins axi_dma_0/S_AXI_LITE]
connect_bd_intf_net [get_bd_intf_pins gp0_interconnect/M01_AXI] [get_bd_intf_pins p10_axil_clock_converter/S_AXI]
connect_bd_intf_net [get_bd_intf_pins p10_axil_clock_converter/M_AXI] [get_bd_intf_pins p10_endpoint_0/s_axi]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK2] \
  [get_bd_pins processing_system7_0/M_AXI_GP0_ACLK] \
  [get_bd_pins gp0_interconnect/ACLK] [get_bd_pins gp0_interconnect/S00_ACLK] \
  [get_bd_pins gp0_interconnect/M00_ACLK] [get_bd_pins gp0_interconnect/M01_ACLK] \
  [get_bd_pins p10_axil_clock_converter/s_axi_aclk] [get_bd_pins axi_dma_0/s_axi_lite_aclk]
connect_bd_net [get_bd_pins rst_axil_50/interconnect_aresetn] \
  [get_bd_pins gp0_interconnect/ARESETN] [get_bd_pins gp0_interconnect/S00_ARESETN] \
  [get_bd_pins gp0_interconnect/M00_ARESETN] [get_bd_pins gp0_interconnect/M01_ARESETN]
connect_bd_net [get_bd_pins rst_axil_50/peripheral_aresetn] [get_bd_pins p10_axil_clock_converter/s_axi_aresetn]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] \
  [get_bd_pins p10_axil_clock_converter/m_axi_aclk] [get_bd_pins p10_endpoint_0/s_axi_aclk]
connect_bd_net [get_bd_pins rst_protocol_64/peripheral_aresetn] \
  [get_bd_pins p10_axil_clock_converter/m_axi_aresetn] [get_bd_pins p10_endpoint_0/s_axi_aresetn]

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
connect_bd_intf_net [get_bd_intf_pins mm2s_axis_clock_converter/M_AXIS] [get_bd_intf_pins p10_endpoint_0/s_axis]
connect_bd_intf_net [get_bd_intf_pins p10_endpoint_0/m_axis] [get_bd_intf_pins s2mm_axis_clock_converter/S_AXIS]
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

foreach pin_name [list tfdu_mode_o tfdu_rxd_i tfdu_sd_o tfdu_txd_o pl_activity_led_n_o] {
  set pin [get_bd_pins "p10_endpoint_0/$pin_name"]
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
  [get_bd_addr_segs p10_endpoint_0/s_axi/reg0] -force

validate_bd_design
save_bd_design
generate_target all [get_files p10_ps_system.bd]
make_wrapper -files [get_files p10_ps_system.bd] -top
add_files -norecurse "$build_dir/project/${project_name}.gen/sources_1/bd/p10_ps_system/hdl/p10_ps_system_wrapper.v"
set_property top p10_ps_system_wrapper [current_fileset]
update_compile_order -fileset sources_1

set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
launch_runs impl_1 -to_step write_bitstream -jobs 8
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%" ||
    ![string match "*Complete*" [get_property STATUS [get_runs impl_1]]]} {
  error "P10 implementation did not complete: [get_property STATUS [get_runs impl_1]]"
}

open_run impl_1
report_drc -file "$out_dir/post_route_drc.rpt"
report_methodology -file "$out_dir/post_route_methodology.rpt"
report_timing_summary -report_unconstrained -check_timing_verbose \
  -file "$out_dir/post_route_timing_summary.rpt"
check_timing -verbose -file "$out_dir/post_route_check_timing.rpt"
report_utilization -hierarchical -file "$out_dir/post_route_utilization.rpt"
report_cdc -details -file "$out_dir/post_route_cdc.rpt"
report_clock_interaction -file "$out_dir/post_route_clock_interaction.rpt"

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
set check_handle [open "$out_dir/post_route_check_timing.rpt" r]
set check_text [read $check_handle]
close $check_handle
set unconstrained_internal_endpoints -1
set no_clock_count -1
regexp {checking unconstrained_internal_endpoints \(([0-9]+)\)} \
  $check_text -> unconstrained_internal_endpoints
regexp {checking no_clock \(([0-9]+)\)} $check_text -> no_clock_count
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
set wns [expr {[llength $setup_path] ? [get_property SLACK $setup_path] : 0.0}]
set whs [expr {[llength $hold_path] ? [get_property SLACK $hold_path] : 0.0}]
set tns 0.0
foreach path [get_timing_paths -quiet -delay_type max -slack_lesser_than 0.0 -max_paths 100000] {
  set tns [expr {$tns + [get_property SLACK $path]}]
}
set lut_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == LUT}]]
set ff_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == FLOP_LATCH}]]
set bram36_count [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ RAMB36*}]]
set bram18_count [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ RAMB18*}]]
set dsp_count [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ DSP48*}]]
set forensic_bram_count 0
foreach cell [concat \
    [get_cells -quiet -hierarchical -filter {REF_NAME =~ RAMB36*}] \
    [get_cells -quiet -hierarchical -filter {REF_NAME =~ RAMB18*}]] {
  if {[string first "u_fault_forensics" [get_property NAME $cell]] >= 0} {
    incr forensic_bram_count
  }
}
set forensic_bram_inferred [expr {$forensic_bram_count > 0}]
set bram36_equivalent [expr {$bram36_count + $bram18_count / 2.0}]
set lut_percent [expr {100.0 * $lut_count / 53200.0}]
set ff_percent [expr {100.0 * $ff_count / 106400.0}]
set bram_percent [expr {100.0 * $bram36_equivalent / 140.0}]
set dsp_percent [expr {100.0 * $dsp_count / 220.0}]
set resource_limits_pass [expr {$lut_percent <= 70.0 && $ff_percent <= 70.0 &&
    $bram_percent <= 75.0 && $dsp_percent <= 50.0}]
if {$wns < 0.0 || $whs < 0.0 || $tns < 0.0 || $drc_critical != 0 ||
    $drc_error != 0 || $reqp_1839 != 0 || $methodology_critical != 0 ||
    $cdc_critical != 0 || $unconstrained_internal_endpoints != 0 ||
    $no_clock_count != 0 || !$resource_limits_pass ||
    ($campaign in {p10_3f p10_4} && !$forensic_bram_inferred)} {
  error "P10 signoff gate failed: WNS=$wns WHS=$whs TNS=$tns DRC_CRITICAL=$drc_critical DRC_ERROR=$drc_error REQP_1839=$reqp_1839 METHODOLOGY_CRITICAL=$methodology_critical CDC_CRITICAL=$cdc_critical UNCONSTRAINED_INTERNAL=$unconstrained_internal_endpoints NO_CLOCK=$no_clock_count RESOURCE_LIMITS=$resource_limits_pass"
}

write_checkpoint -force "$out_dir/p10_ax7020_${endpoint_role_name}_post_route.dcp"
write_bitstream -force "$out_dir/p10_ax7020_${endpoint_role_name}_functional.bit"
write_hw_platform -fixed -include_bit -force \
  -file "$out_dir/p10_ax7020_${endpoint_role_name}_functional.xsa"

set marker [open "$out_dir/p10_functional_build_markers.txt" w]
puts $marker "P10_FUNCTIONAL_BUILD=PASS"
puts $marker "P10_ENDPOINT_ROLE=$endpoint_role_name"
puts $marker "P10_ENDPOINT_ROLE_VALUE=$endpoint_role"
puts $marker "P10_PROFILE_ID=$profile_id"
puts $marker "P10_LANE_COUNT=$lane_count"
puts $marker "P10_CAMPAIGN=$campaign"
set marker_build_id [expr {$campaign eq "p10_4" ?
    ($endpoint_role == 1 ? 0x50343446 : 0x50343452) :
    ($campaign eq "p10_3f" ?
    ($endpoint_role == 1 ? 0x50334646 : 0x50334652) :
    ($campaign eq "p10_3" ?
      ($endpoint_role == 1 ? 0x50333446 : 0x50333452) :
      ($lane_count == 4 ?
        ($endpoint_role == 1 ? 0x50323446 : 0x50323452) :
        ($endpoint_role == 1 ? 0x50325346 : 0x50325352))))}]
puts $marker [format "P10_PL_BUILD_ID=0x%08X" $marker_build_id]
puts $marker "P10_PART=[get_property PART [current_project]]"
puts $marker "P10_TOP=p10_ps_system_wrapper"
puts $marker "P10_AXI_BASE=0x43C00000"
puts $marker "P10_DMA_AXI_BASE=0x40400000"
puts $marker "P10_DMA_MODE=SCATTER_GATHER"
puts $marker "P10_DMA_SG_STSCNTRL_STREAM=DISABLED"
puts $marker "P10_DMA_HP_PORT=S_AXI_HP0"
puts $marker "P10_PROTOCOL_CLOCK_HZ=64000000"
puts $marker "P10_DMA_CLOCK_HZ=100000000"
puts $marker "P10_AXIL_CLOCK_HZ=50000000"
puts $marker "P10_NETWORK_USED=false"
puts $marker "P10_ETHERNET_ENABLED=false"
if {$campaign in {p10_3 p10_3f p10_4}} {
  puts $marker "P10_PS_GPIO_ENABLED=true"
  puts $marker "P10_PS_ACTIVITY_LED_MAPPING=PS_LED1_MIO0_MM2S_INFLIGHT_PS_LED2_MIO13_S2MM_INFLIGHT"
  puts $marker "P10_PS_ACTIVITY_LED_ACTIVE_LOW=true"
  puts $marker "P10_PS_ACTIVITY_LED_SAFETY_ROLE=MONITOR_ONLY"
} else {
  puts $marker "P10_PS_GPIO_ENABLED=false"
  puts $marker "P10_PS_ACTIVITY_LED_MAPPING=DISABLED"
}
if {$campaign in {p10_3f p10_4}} {
  set forensic_bram_marker [expr {$forensic_bram_inferred ? "true" : "false"}]
  puts $marker "P10_FIRST_FAULT_FORENSICS=true"
  puts $marker "P10_FORENSIC_SNAPSHOT_WORDS=64"
  puts $marker "P10_FORENSIC_EVENT_DEPTH=256"
  puts $marker "P10_FORENSIC_EVENT_WORDS=8"
  puts $marker "P10_FORENSIC_RESET_POLICY=NO_FUNCTIONAL_RESET"
  puts $marker "P10_FORENSIC_BRAM_INFERRED=$forensic_bram_marker"
  puts $marker "P10_FORENSIC_BRAM_PRIMITIVES=$forensic_bram_count"
}
if {$lane_count == 4} {
  puts $marker "P10_PL_ACTIVITY_LED_MAPPING=LED1_LANE0_ACTIVITY_LED2_LANE1_ACTIVITY_LED3_LANE2_ACTIVITY_LED4_LANE3_ACTIVITY"
} else {
  puts $marker "P10_PL_ACTIVITY_LED_MAPPING=LED1_LANE0_TX_LED2_LANE0_RX_LED3_LANE1_TX_LED4_LANE1_RX"
}
puts $marker "P10_PL_ACTIVITY_LED_ACTIVE_LOW=true"
puts $marker "P10_PL_ACTIVITY_LED_HOLD_MS=200"
puts $marker "P10_PL_ACTIVITY_LED_SAFETY_ROLE=MONITOR_ONLY"
puts $marker "P10_CANONICAL_XDC=[file normalize $xdc_file]"
puts $marker "P10_WNS_NS=$wns"
puts $marker "P10_WHS_NS=$whs"
puts $marker "P10_TNS_NS=$tns"
puts $marker "P10_DRC_CRITICAL_COUNT=$drc_critical"
puts $marker "P10_DRC_ERROR_COUNT=$drc_error"
puts $marker "P10_REQP_1839_COUNT=$reqp_1839"
puts $marker "P10_METHODOLOGY_CRITICAL_COUNT=$methodology_critical"
puts $marker "P10_CDC_CRITICAL_COUNT=$cdc_critical"
puts $marker "P10_UNCONSTRAINED_INTERNAL_ENDPOINTS=$unconstrained_internal_endpoints"
puts $marker "P10_NO_CLOCK_COUNT=$no_clock_count"
puts $marker "P10_LUT=$lut_count"
puts $marker "P10_FF=$ff_count"
puts $marker "P10_BRAM36=$bram36_count"
puts $marker "P10_BRAM18=$bram18_count"
puts $marker "P10_BRAM36_EQUIVALENT=$bram36_equivalent"
puts $marker "P10_DSP=$dsp_count"
puts $marker "P10_LUT_PERCENT=$lut_percent"
puts $marker "P10_FF_PERCENT=$ff_percent"
puts $marker "P10_BRAM_PERCENT=$bram_percent"
puts $marker "P10_DSP_PERCENT=$dsp_percent"
puts $marker "P10_RESOURCE_LIMITS_PASS=$resource_limits_pass"
puts $marker "P10_HARDWARE_ADMISSION=false"
puts $marker "P10_BLOCKING_CONDITION=P10-SAFETY-POWERUP-001"
close $marker
puts "P10_AX7020_${endpoint_role_name}_FUNCTIONAL_BUILD=PASS"
