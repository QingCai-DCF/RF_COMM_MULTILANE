# P8E non-hardware synth/place/route/report flow.
# argv0 is a generated Tcl configuration containing exact source/constraint lists.
set cfg_path [file normalize [lindex $argv 0]]
source $cfg_path
file mkdir $p8e_out_dir

create_project p8e_impl "$p8e_out_dir/project" -part $p8e_part -force
set_property target_language Verilog [current_project]
set_property include_dirs $p8e_include_dirs [current_fileset]
read_verilog -sv $p8e_sources
foreach xdc $p8e_constraints { read_xdc $xdc }

# Vivado implementation directives are the supported robustness dimension.
# Record whether this tool build accepts an additional deterministic placer
# seed; a rejected internal parameter never weakens the two-strategy gate.
set p8e_seed_applied 0
if {![catch {set_param place.seed $p8e_seed}]} { set p8e_seed_applied 1 }

if {$p8e_synth_directive eq "Default"} {
  synth_design -mode out_of_context -top $p8e_top -part $p8e_part
} else {
  synth_design -mode out_of_context -top $p8e_top -part $p8e_part \
    -directive $p8e_synth_directive
}
write_checkpoint -force "$p8e_out_dir/post_synth.dcp"
write_verilog -force -mode funcsim "$p8e_out_dir/post_synth_funcsim.v"
report_utilization -hierarchical -file "$p8e_out_dir/post_synth_utilization.rpt"
report_timing_summary -delay_type min_max -max_paths 20 \
  -file "$p8e_out_dir/post_synth_timing_summary.rpt"
report_drc -file "$p8e_out_dir/post_synth_drc.rpt"

opt_design
if {$p8e_place_directive eq "Default"} {
  place_design
} else {
  place_design -directive $p8e_place_directive
}
if {$p8e_phys_opt_directive eq "Default"} {
  phys_opt_design
} else {
  phys_opt_design -directive $p8e_phys_opt_directive
}
write_checkpoint -force "$p8e_out_dir/post_place.dcp"
if {$p8e_route_directive eq "Default"} {
  route_design
} else {
  route_design -directive $p8e_route_directive
}
write_checkpoint -force "$p8e_out_dir/post_route.dcp"

report_utilization -hierarchical -file "$p8e_out_dir/post_route_utilization.rpt"
report_timing_summary -delay_type min_max -max_paths 100 \
  -file "$p8e_out_dir/post_route_timing_summary.rpt"
report_timing -delay_type max -max_paths 100 -path_type full_clock_expanded \
  -file "$p8e_out_dir/post_route_setup_paths.rpt"
report_timing -delay_type min -max_paths 100 -path_type full_clock_expanded \
  -file "$p8e_out_dir/post_route_hold_paths.rpt"
report_cdc -details -file "$p8e_out_dir/post_route_cdc.rpt"
report_clock_interaction -file "$p8e_out_dir/post_route_clock_interaction.rpt"
check_timing -verbose -file "$p8e_out_dir/post_route_check_timing.rpt"
report_exceptions -file "$p8e_out_dir/post_route_exceptions.rpt"
report_drc -file "$p8e_out_dir/post_route_drc.rpt"
report_methodology -file "$p8e_out_dir/post_route_methodology.rpt"
report_power -file "$p8e_out_dir/post_route_power.rpt"
report_pulse_width -file "$p8e_out_dir/post_route_pulse_width.rpt"

set setup_paths [get_timing_paths -delay_type max -max_paths 1]
set hold_paths [get_timing_paths -delay_type min -max_paths 1]
set setup_wns "NA"
set hold_whs "NA"
if {[llength $setup_paths]} { set setup_wns [get_property SLACK [lindex $setup_paths 0]] }
if {[llength $hold_paths]} { set hold_whs [get_property SLACK [lindex $hold_paths 0]] }
set tns 0.0
foreach path [get_timing_paths -delay_type max -slack_lesser_than 0 -max_paths 100000] {
  set slack [get_property SLACK $path]
  if {$slack < 0} { set tns [expr {$tns + $slack}] }
}
set lut_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == LUT}]]
set ff_count [llength [get_cells -hierarchical -filter {PRIMITIVE_GROUP == FLOP_LATCH}]]
set bram36_count [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ RAMB36*}]]
set bram18_count [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ RAMB18*}]]
set dsp_count [llength [get_cells -quiet -hierarchical -filter {REF_NAME =~ DSP48*}]]
set reqp1839_count [llength [get_drc_violations -quiet REQP-1839*]]
set drc_critical 0
set drc_error 0
foreach violation [get_drc_violations -quiet] {
  set severity [get_property SEVERITY $violation]
  if {$severity eq "Critical Warning"} { incr drc_critical }
  if {$severity eq "Error"} { incr drc_error }
}
set cdc_critical 0
set cdc_warning 0
if {[llength [info commands get_cdc_violations]]} {
  foreach violation [get_cdc_violations -quiet] {
    set severity [get_property SEVERITY $violation]
    if {$severity eq "Critical" || $severity eq "Critical Warning"} { incr cdc_critical }
    if {$severity eq "Warning"} { incr cdc_warning }
  }
}
set marker [open "$p8e_out_dir/build_markers.txt" w]
puts $marker "P8E_PROFILE=$p8e_profile_id"
puts $marker "P8E_STRATEGY=$p8e_strategy_id"
puts $marker "P8E_DOCUMENTED_SEED=$p8e_seed"
puts $marker "P8E_SEED_APPLIED=$p8e_seed_applied"
puts $marker "P8E_PART=$p8e_part"
puts $marker "P8E_TOP=$p8e_top"
puts $marker "P8E_SETUP_WNS_NS=$setup_wns"
puts $marker "P8E_HOLD_WHS_NS=$hold_whs"
puts $marker "P8E_TNS_NS=$tns"
puts $marker "P8E_LUT=$lut_count"
puts $marker "P8E_FF=$ff_count"
puts $marker "P8E_BRAM36=$bram36_count"
puts $marker "P8E_BRAM18=$bram18_count"
puts $marker "P8E_DSP=$dsp_count"
puts $marker "P8E_REQP_1839=$reqp1839_count"
puts $marker "P8E_DRC_CRITICAL=$drc_critical"
puts $marker "P8E_DRC_ERROR=$drc_error"
puts $marker "P8E_CDC_CRITICAL=$cdc_critical"
puts $marker "P8E_CDC_WARNING=$cdc_warning"
puts $marker "P8E_ROUTE_STATUS=[get_property ROUTE_STATUS [current_design]]"
puts $marker "P8E_IMPLEMENTATION_COMPLETE=1"
close $marker
close_project
