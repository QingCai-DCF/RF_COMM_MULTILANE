set repo_root [file normalize [file join [file dirname [info script]] ".."]]
set out_csv [file join $repo_root reports ila_2lane_capture.csv]
set out_summary [file join $repo_root reports ila_2lane_capture.summary.txt]
set trigger_mode now
set trigger_position 1024
set hw_url localhost:3121
set jtag_frequency_hz 1000000
source [file join $repo_root tools hw_connect_utils.tcl]

if {[llength $argv] >= 1 && [lindex $argv 0] ne ""} {
  set out_csv [file normalize [lindex $argv 0]]
}
if {[llength $argv] >= 2 && [lindex $argv 1] ne ""} {
  set out_summary [file normalize [lindex $argv 1]]
}
if {[llength $argv] >= 3 && [lindex $argv 2] ne ""} {
  set trigger_mode [lindex $argv 2]
}
if {[llength $argv] >= 4 && [lindex $argv 3] ne ""} {
  set jtag_frequency_hz [lindex $argv 3]
}

set run_dir [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1]
set bit_file [file join $run_dir design_shiboqi_wrapper.bit]
set ltx_file [file join $run_dir design_shiboqi_wrapper.ltx]

file mkdir [file dirname $out_csv]
set sfh [open $out_summary w]
proc say {line} {
  global sfh
  puts $line
  puts $sfh $line
  flush $sfh
}

say "ILA2_CAPTURE_BEGIN [clock format [clock seconds] -format {%Y-%m-%dT%H:%M:%S%z}]"
say "CSV=$out_csv"
say "BIT=$bit_file"
say "LTX=$ltx_file"
say "TRIGGER_MODE=$trigger_mode"
say "HW_URL=$hw_url"
say "JTAG_FREQUENCY_HZ=$jtag_frequency_hz"

if {![file exists $ltx_file]} {
  say "ILA2_CAPTURE_ERROR missing_ltx"
  close $sfh
  exit 2
}

if {[catch {set dev [rf_hw_open_zynq_device $hw_url $jtag_frequency_hz]} open_err]} {
  say "ILA2_CAPTURE_ERROR hw_open_failed $open_err"
  close $sfh
  exit 3
}

set_property PROBES.FILE $ltx_file $dev
if {[catch {refresh_hw_device -update_hw_probes true $dev} refresh_err]} {
  say "ILA2_REFRESH_RETRY $refresh_err"
  if {[catch {
    set dev [rf_hw_open_zynq_device $hw_url $jtag_frequency_hz]
    set_property PROBES.FILE $ltx_file $dev
    refresh_hw_device -update_hw_probes true $dev
  } refresh_retry_err]} {
    say "ILA2_CAPTURE_ERROR refresh_failed $refresh_retry_err"
    close_hw_manager
    close $sfh
    exit 4
  }
}

set ilas [get_hw_ilas -quiet *]
say "HW_ILA_COUNT [llength $ilas]"
foreach ila $ilas {
  say "HW_ILA $ila"
  foreach probe [get_hw_probes -quiet -of_objects $ila] {
    say "  PROBE $probe WIDTH=[get_property WIDTH $probe]"
  }
}

if {[llength $ilas] == 0} {
  say "ILA2_CAPTURE_ERROR no_ila_after_refresh"
  close $sfh
  exit 5
}

set ila [lindex $ilas 0]
if {$trigger_mode eq "b_rx_data_state" || $trigger_mode eq "b_rx_check_state" || $trigger_mode eq "b_rx_flush_state"} {
  set trigger_position 128
}

if {[catch {set_property CONTROL.TRIGGER_POSITION $trigger_position $ila} trig_pos_err]} {
  say "ILA2_TRIGGER_POSITION_WARN $trig_pos_err"
}
say "ILA2_TRIGGER_POSITION=$trigger_position"

if {$trigger_mode eq "a_tx_nonzero" || $trigger_mode eq "a_tx_lane0" || $trigger_mode eq "a_tx_lane1" || $trigger_mode eq "b_tx_nonzero" || $trigger_mode eq "b_tx_lane0" || $trigger_mode eq "b_tx_lane1" || $trigger_mode eq "b2a_rx_nonzero" || $trigger_mode eq "b2a_rx_lane0" || $trigger_mode eq "b2a_rx_lane1" || $trigger_mode eq "b_rx_data_state" || $trigger_mode eq "b_rx_check_state" || $trigger_mode eq "b_rx_flush_state"} {
  set trigger_probe [lindex [get_hw_probes -quiet *ir_array_top_axi_0_ir_tx_out* -of_objects $ila] 0]
  set trigger_value {neq2'h0}
  if {$trigger_mode eq "a_tx_lane0"} {
    set trigger_value {eq2'h1}
  } elseif {$trigger_mode eq "a_tx_lane1"} {
    set trigger_value {eq2'h2}
  } elseif {$trigger_mode eq "b_tx_nonzero"} {
    set trigger_probe [lindex [get_hw_probes -quiet *ir_loopback_b0_ir_tx_out* -of_objects $ila] 0]
    set trigger_value {neq2'h0}
  } elseif {$trigger_mode eq "b_tx_lane0"} {
    set trigger_probe [lindex [get_hw_probes -quiet *ir_loopback_b0_ir_tx_out* -of_objects $ila] 0]
    set trigger_value {eq2'h1}
  } elseif {$trigger_mode eq "b_tx_lane1"} {
    set trigger_probe [lindex [get_hw_probes -quiet *ir_loopback_b0_ir_tx_out* -of_objects $ila] 0]
    set trigger_value {eq2'h2}
  } elseif {$trigger_mode eq "b2a_rx_nonzero"} {
    set trigger_probe [lindex [get_hw_probes -quiet *ir_loopback_b0_ir_tx_out* -of_objects $ila] 0]
    set trigger_value {neq2'h0}
  } elseif {$trigger_mode eq "b2a_rx_lane0"} {
    set trigger_probe [lindex [get_hw_probes -quiet *ir_loopback_b0_ir_tx_out* -of_objects $ila] 0]
    set trigger_value {eq2'h1}
  } elseif {$trigger_mode eq "b2a_rx_lane1"} {
    set trigger_probe [lindex [get_hw_probes -quiet *ir_loopback_b0_ir_tx_out* -of_objects $ila] 0]
    set trigger_value {eq2'h2}
  } elseif {$trigger_mode eq "b_rx_data_state"} {
    set trigger_probe [lindex [get_hw_probes -quiet *loop_rx_b0* -of_objects $ila] 0]
    set trigger_value {neq2'h3}
  } elseif {$trigger_mode eq "b_rx_check_state"} {
    set trigger_probe [lindex [get_hw_probes -quiet *loop_rx_b0* -of_objects $ila] 0]
    set trigger_value {neq2'h3}
  } elseif {$trigger_mode eq "b_rx_flush_state"} {
    set trigger_probe [lindex [get_hw_probes -quiet *loop_rx_b0* -of_objects $ila] 0]
    set trigger_value {neq2'h3}
  }
  if {$trigger_probe eq ""} {
    say "ILA2_TRIGGER_CONFIG_ERROR missing_trigger_probe"
    close_hw_manager
    close $sfh
    exit 7
  }
  say "ILA2_TRIGGER_PROBE=$trigger_probe"
  say "ILA2_TRIGGER_VALUE=$trigger_value"
  if {[catch {set_property TRIGGER_COMPARE_VALUE $trigger_value $trigger_probe} trig_cmp_err]} {
    say "ILA2_TRIGGER_COMPARE_WARN $trig_cmp_err"
    say "ILA2_TRIGGER_COMPARE_RETRY_NE"
    set_property TRIGGER_COMPARE_VALUE {ne2'h0} $trigger_probe
  }
  say "ILA2_RUN_WAIT_$trigger_mode"
  run_hw_ila $ila
} else {
  say "ILA2_RUN_TRIGGER_NOW"
  if {[catch {run_hw_ila -trigger_now $ila} run_err]} {
    say "ILA2_TRIGGER_NOW_WARN $run_err"
    run_hw_ila $ila
  }
}
wait_on_hw_ila $ila
set data [upload_hw_ila_data $ila]
say "ILA2_DATA=$data"

if {[catch {write_hw_ila_data -force -csv_file $out_csv $data} csv_err]} {
  say "ILA2_CSV_WRITE_ERROR $csv_err"
  close_hw_manager
  close $sfh
  exit 6
}

say "ILA2_CSV_WRITTEN $out_csv"
close_hw_manager
say "ILA2_CAPTURE_DONE"
close $sfh
