set root_dir [file normalize [lindex $argv 0]]
set top_name [lindex $argv 1]
set part_name [lindex $argv 2]
set out_dir [file normalize [lindex $argv 3]]
file mkdir $out_dir

create_project p8c_resource_audit "$out_dir/project" -part $part_name -force
set_property target_language Verilog [current_project]
set_property include_dirs [list "$root_dir/rtl"] [current_fileset]
read_verilog -sv [list \
  "$root_dir/rtl/generated/tfdu_safety_pkg.sv" \
  "$root_dir/rtl/ir_tfdu_exact_duty_accountant.sv" \
  "$root_dir/rtl/ir_tfdu_physical_module_safety.sv" \
  "$root_dir/rtl/ir_tfdu_safety_endpoint.sv" \
  "$root_dir/rtl/ir_p8c_resource_tops.sv" \
]
synth_design -mode out_of_context -top $top_name -part $part_name
create_clock -name p8c_clk -period 15.625 [get_ports clk]

report_utilization -hierarchical -file "$out_dir/utilization.rpt"
report_timing_summary -delay_type max -max_paths 20 -file "$out_dir/timing_summary.rpt"
report_drc -file "$out_dir/drc.rpt"
check_timing -verbose -file "$out_dir/check_timing.rpt"

set lut_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == LUT}]]
set ff_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == FLOP_LATCH}]]
set bram36_count [llength [get_cells -hierarchical -filter {REF_NAME =~ RAMB36*}]]
set bram18_count [llength [get_cells -hierarchical -filter {REF_NAME =~ RAMB18*}]]
set srl_count [llength [get_cells -hierarchical -filter {REF_NAME =~ SRL*}]]
set marker [open "$out_dir/resource_markers.txt" w]
puts $marker "P8C_RESOURCE_TOP=$top_name"
puts $marker "P8C_RESOURCE_PART=$part_name"
puts $marker "P8C_LUT=$lut_count"
puts $marker "P8C_FF=$ff_count"
puts $marker "P8C_BRAM36=$bram36_count"
puts $marker "P8C_BRAM18=$bram18_count"
puts $marker "P8C_SRL=$srl_count"
puts $marker "P8C_MAX_INFERRED_RAM_DEPTH=64000"
puts $marker "P8C_OOC_SYNTHESIS_PASS=1"
close $marker
write_checkpoint -force "$out_dir/post_synth.dcp"
close_project
