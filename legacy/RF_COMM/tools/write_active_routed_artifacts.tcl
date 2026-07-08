set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set bd_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs sources_1 bd design_shiboqi design_shiboqi.bd]
set xdc_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new PORT1.xdc]
set run_dir [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1]
set routed_dcp [file join $run_dir design_shiboqi_wrapper_routed.dcp]
set xsa_file [file join $repo_root TFDU_VFIR_Client_Array design_shiboqi_wrapper.xsa]
set bit_copy [file join $repo_root TFDU_VFIR_Client_Array design_shiboqi_wrapper.bit]

proc read_file_text {path} {
  set fh [open $path r]
  set text [read $fh]
  close $fh
  return $text
}

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
if {![file exists $bd_file]} {
  error "Missing block design: $bd_file"
}
if {![file exists $xdc_file]} {
  error "Missing active PORT1 XDC: $xdc_file"
}
if {![file exists $routed_dcp]} {
  error "Missing routed checkpoint: $routed_dcp"
}

set xdc_text [read_file_text $xdc_file]
if {[string first {ir_rx_in_0[1]} $xdc_text] < 0 || [string first {loop_rx_b0[1]} $xdc_text] < 0} {
  error "PORT1 XDC does not expose the current 2-lane A/B TFDU ports"
}
if {[string first {PACKAGE_PIN G15 [get_ports {loop_rx_b0[1]}]} $xdc_text] < 0} {
  error "PORT1 XDC is not the current B_RX1-to-G15 mapping"
}

set bd_text [read_file_text $bd_file]
if {[string first {ir_stream_bidir_vec_bd} $bd_text] < 0} {
  error "Block design is not using ir_stream_bidir_vec_bd"
}
if {[string first {"value": "2"} $bd_text] < 0} {
  error "Block design does not appear to contain a 2-lane parameter value"
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}
set_param general.maxThreads $max_threads

open_project $project_file
set target_xdc [get_property TARGET_CONSTRS_FILE [current_fileset -constrset]]
puts "TARGET_CONSTRAINT_FILE=$target_xdc"
if {![string match "*PORT1.xdc" $target_xdc]} {
  error "Active target constraints are not PORT1.xdc: $target_xdc"
}

set impl_status [get_property STATUS [get_runs impl_1]]
puts "IMPL_STATUS=$impl_status"
if {![string match "*route_design Complete*" $impl_status] && ![string match "*write_bitstream Complete*" $impl_status] && ![string match "*Complete*" $impl_status]} {
  error "impl_1 is not routed enough to write artifacts: $impl_status"
}

open_run impl_1
set current_run_dir [get_property DIRECTORY [current_run]]
if {[file normalize $current_run_dir] ne [file normalize $run_dir]} {
  puts "RUN_DIR_WARNING expected=$run_dir actual=$current_run_dir"
}

set bit_file [file join $run_dir design_shiboqi_wrapper.bit]
set ltx_file [file join $run_dir design_shiboqi_wrapper.ltx]

write_bitstream -force $bit_file
write_debug_probes -force $ltx_file
write_hw_platform -fixed -include_bit -force -file $xsa_file
file copy -force $bit_file $bit_copy

puts "ACTIVE_BIT=$bit_file"
puts "ACTIVE_LTX=$ltx_file"
puts "ACTIVE_XSA=$xsa_file"
puts "ACTIVE_BIT_COPY=$bit_copy"
puts "NO_HARDWARE_PROGRAMMING=1"
puts "NO_UART_WRITE=1"
puts "NO_TFDU_DRIVE=1"
puts "WRITE_ACTIVE_ROUTED_ARTIFACTS_DONE"
close_project
