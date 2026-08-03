# Offline-only P10 AX7020 shutdown implementation.
# argv: <repository-root> <fixed|rotating> <output-directory>
set root_dir [file normalize [lindex $argv 0]]
set endpoint_role [string tolower [lindex $argv 1]]
set out_dir [file normalize [lindex $argv 2]]

if {$endpoint_role ni {fixed rotating}} {
  error "P10 shutdown role must be fixed or rotating"
}

if {$endpoint_role eq "fixed"} {
  set profile_id P10_AX7020_FIXED_2LANE
  set xdc_path "$root_dir/board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc"
  set bit_name p10_ax7020_fixed_shutdown.bit
} else {
  set profile_id P10_AX7020_ROTATING_2LANE
  set xdc_path "$root_dir/board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc"
  set bit_name p10_ax7020_rotating_shutdown.bit
}

file mkdir $out_dir
create_project -in_memory -part xc7z020clg400-2
set_property target_language Verilog [current_project]
read_verilog "$root_dir/rtl/p10_ax7020_shutdown_top.v"
read_xdc $xdc_path

synth_design -top p10_ax7020_shutdown_top -part xc7z020clg400-2

set shutdown_led_ports [get_ports -quiet {pl_activity_led_n_o[*]}]
if {[llength $shutdown_led_ports] != 4} {
  error "P10 shutdown image must expose exactly four active-low PL LED outputs"
}
write_checkpoint -force "$out_dir/post_synth_shutdown.dcp"
report_utilization -hierarchical -file "$out_dir/post_synth_utilization.rpt"
report_drc -file "$out_dir/post_synth_drc.rpt"

opt_design
place_design
route_design
write_checkpoint -force "$out_dir/post_route_shutdown.dcp"
report_utilization -hierarchical -file "$out_dir/post_route_utilization.rpt"
report_timing_summary -delay_type min_max -report_unconstrained \
  -check_timing_verbose -file "$out_dir/post_route_timing_summary.rpt"
report_drc -file "$out_dir/post_route_drc.rpt"
report_methodology -file "$out_dir/post_route_methodology.rpt"
report_cdc -details -file "$out_dir/post_route_cdc.rpt"

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
  error "P10 shutdown signoff failed: DRC_CRITICAL=$drc_critical DRC_ERROR=$drc_error REQP_1839=$reqp_1839 METHODOLOGY_CRITICAL=$methodology_critical CDC_CRITICAL=$cdc_critical"
}

set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
write_bitstream -force "$out_dir/$bit_name"

set marker [open "$out_dir/p10_shutdown_build_markers.txt" w]
puts $marker "P10_SHUTDOWN_BUILD=PASS"
puts $marker "P10_ENDPOINT_ROLE=$endpoint_role"
puts $marker "P10_PROFILE_ID=$profile_id"
puts $marker "P10_PART=[get_property PART [current_project]]"
puts $marker "P10_TOP=p10_ax7020_shutdown_top"
puts $marker "P10_XDC=$xdc_path"
puts $marker "P10_SHUTDOWN_MODE_INTENT=0x3"
puts $marker "P10_SHUTDOWN_SD_INTENT=0x3"
puts $marker "P10_SHUTDOWN_TXD_INTENT=0x0"
puts $marker "P10_SHUTDOWN_LED_N_INTENT=0xF"
puts $marker "P10_SHUTDOWN_LED_ACTIVE_LOW=true"
puts $marker "P10_SHUTDOWN_LED_PORT_COUNT=[llength $shutdown_led_ports]"
puts $marker "P10_DRC_CRITICAL_COUNT=$drc_critical"
puts $marker "P10_DRC_ERROR_COUNT=$drc_error"
puts $marker "P10_REQP_1839_COUNT=$reqp_1839"
puts $marker "P10_METHODOLOGY_CRITICAL_COUNT=$methodology_critical"
puts $marker "P10_CDC_CRITICAL_COUNT=$cdc_critical"
close $marker

puts "P10_SHUTDOWN_BUILD=PASS"
puts "P10_ENDPOINT_ROLE=$endpoint_role"
puts "P10_SHUTDOWN_BITSTREAM=$out_dir/$bit_name"
