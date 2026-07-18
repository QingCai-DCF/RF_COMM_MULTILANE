set root_dir [file normalize [lindex $argv 0]]
set part_name [lindex $argv 1]
set lane_count [lindex $argv 2]
set window_size [lindex $argv 3]
set sack_bits [lindex $argv 4]
set data_width [lindex $argv 5]
set physical_module_count [lindex $argv 6]
set out_dir [file normalize [lindex $argv 7]]
file mkdir $out_dir

create_project p8d_resource_audit "$out_dir/project" -part $part_name -force
set_property target_language Verilog [current_project]
set_property include_dirs [list "$root_dir/rtl"] [current_fileset]
read_verilog -sv [list \
  "$root_dir/rtl/generated/tfdu_safety_pkg.sv" \
  "$root_dir/rtl/ir_tfdu_exact_duty_accountant.sv" \
  "$root_dir/rtl/ir_tfdu_physical_module_safety.sv" \
  "$root_dir/rtl/ir_tfdu_safety_endpoint.sv" \
  "$root_dir/rtl/ir_p8c_resource_tops.sv" \
  "$root_dir/rtl/ir_seq_math_pkg.sv" \
  "$root_dir/rtl/ir_ack_aggregator.sv" \
  "$root_dir/rtl/ir_health_weighted_scheduler.sv" \
  "$root_dir/rtl/ir_selective_repeat_tx.sv" \
  "$root_dir/rtl/ir_selective_repeat_rx.sv" \
  "$root_dir/rtl/ir_axis_tx_frontend.sv" \
  "$root_dir/rtl/ir_dma_descriptor_model.sv" \
  "$root_dir/rtl/ir_shared_payload_store.sv" \
  "$root_dir/rtl/ir_data_plane_top.sv" \
  "$root_dir/rtl/ir_p8d_resource_tops.sv" \
]
set generics [list LANE_COUNT=$lane_count WINDOW_SIZE=$window_size SACK_BITS=$sack_bits \
  DATA_WIDTH=$data_width PHYSICAL_MODULE_COUNT=$physical_module_count]
synth_design -mode out_of_context -top ir_p8d_resource_top -part $part_name -generic $generics
create_clock -name p8d_clk -period 15.625 [get_ports clk]

report_utilization -hierarchical -file "$out_dir/utilization.rpt"
report_utilization -cells [get_cells -hierarchical *data_plane*] -file "$out_dir/data_plane_utilization.rpt"
report_utilization -cells [get_cells -hierarchical *payload_store*] -file "$out_dir/payload_store_utilization.rpt"
report_utilization -cells [get_cells -hierarchical *scheduler*] -file "$out_dir/scheduler_utilization.rpt"
report_utilization -cells [get_cells -hierarchical *ring*] -file "$out_dir/descriptor_ring_utilization.rpt"
report_timing_summary -delay_type max -max_paths 20 -file "$out_dir/timing_summary.rpt"
report_drc -file "$out_dir/drc.rpt"
check_timing -verbose -file "$out_dir/check_timing.rpt"

set lut_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == LUT}]]
set ff_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == FLOP_LATCH}]]
set bram36_count [llength [get_cells -hierarchical -filter {REF_NAME =~ RAMB36*}]]
set bram18_count [llength [get_cells -hierarchical -filter {REF_NAME =~ RAMB18*}]]
set dsp_count [llength [get_cells -hierarchical -filter {REF_NAME =~ DSP48*}]]
set marker [open "$out_dir/resource_markers.txt" w]
puts $marker "P8D_RESOURCE_TOP=ir_p8d_resource_top"
puts $marker "P8D_RESOURCE_PART=$part_name"
puts $marker "P8D_LANE_COUNT=$lane_count"
puts $marker "P8D_WINDOW_SIZE=$window_size"
puts $marker "P8D_SACK_BITS=$sack_bits"
puts $marker "P8D_AXIS_DATA_WIDTH=$data_width"
puts $marker "P8D_PHYSICAL_MODULE_COUNT=$physical_module_count"
puts $marker "P8D_LUT=$lut_count"
puts $marker "P8D_FF=$ff_count"
puts $marker "P8D_BRAM36=$bram36_count"
puts $marker "P8D_BRAM18=$bram18_count"
puts $marker "P8D_DSP=$dsp_count"
puts $marker "P8D_OOC_SYNTHESIS_PASS=1"
close $marker
write_checkpoint -force "$out_dir/post_synth.dcp"
close_project
