if {$argc < 2} {
  error "usage: synth_p9_peripheral_ooc.tcl <repository-root> <output-dir>"
}

set root_dir [file normalize [lindex $argv 0]]
set out_dir [file normalize [lindex $argv 1]]
file mkdir $out_dir

read_verilog -sv [list \
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
  "$root_dir/rtl/p10_4_connector_ack_rx_quarantine.sv" \
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
set_property include_dirs [list "$root_dir/rtl"] [current_fileset]
synth_design -top p9_axi_dma_peripheral_bd -part xc7z010clg400-1 -mode out_of_context \
  -flatten_hierarchy rebuilt
write_checkpoint -force "$out_dir/p9_peripheral_ooc.dcp"
report_utilization -hierarchical -hierarchical_depth 6 \
  -file "$out_dir/p9_peripheral_ooc_utilization.rpt"
report_timing_summary -file "$out_dir/p9_peripheral_ooc_timing.rpt"
puts "P9_PERIPHERAL_OOC_COMPLETE=$out_dir"
