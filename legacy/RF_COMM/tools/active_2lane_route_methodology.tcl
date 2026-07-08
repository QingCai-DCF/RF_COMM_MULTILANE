set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set ip_cache_dir [file join $repo_root .vivado_ip_cache]
set port1_xdc [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new PORT1.xdc]
set async_xdc [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new async_clock_groups_impl.xdc]

if {[info exists ::env(ACTIVE_2LANE_ROUTE_OUT_DIR)] && $::env(ACTIVE_2LANE_ROUTE_OUT_DIR) ne ""} {
  set out_dir [file normalize $::env(ACTIVE_2LANE_ROUTE_OUT_DIR)]
} else {
  set out_dir [file join $repo_root reports active_2lane_route_methodology_current]
}
file mkdir $out_dir

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}
set_param general.maxThreads $max_threads

proc read_file_text {path} {
  set fh [open $path r]
  set text [read $fh]
  close $fh
  return $text
}

proc patch_ooc_rundef_scripts {repo_root} {
  set runs_root [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs]
  set broken "ISEStep( \"vivado\",\n         \"-log  -m64 -product Vivado -mode batch -messageDb vivado.pb -notrace -source \" );"

  foreach run_dir [glob -nocomplain -types d [file join $runs_root *_synth_1]] {
    set run_leaf [file tail $run_dir]
    if {![regexp {^(.*)_synth_1$} $run_leaf -> ip_name]} {
      continue
    }
    set rundef [file join $run_dir rundef.js]
    set tcl_files [glob -nocomplain [file join $run_dir *.tcl]]
    if {[llength $tcl_files] == 0} {
      set tcl_files [glob -nocomplain [file join $run_dir ${ip_name}.tcl]]
    }
    if {![file exists $rundef] || [llength $tcl_files] == 0} {
      continue
    }
    set tcl_name [file tail [lindex $tcl_files 0]]
    set log_name [file rootname $tcl_name].vds
    set fh [open $rundef r]
    set text [read $fh]
    close $fh
    regsub -all {\r\n} $text "\n" text
    if {[string first $broken $text] < 0} {
      continue
    }
    set fixed "ISEStep( \"vivado\",\n         \"-log ${log_name} -m64 -product Vivado -mode batch -messageDb vivado.pb -notrace -source ${tcl_name}\" );"
    set text [string map [list $broken $fixed] $text]
    set fh [open $rundef w]
    puts -nonewline $fh $text
    close $fh
    puts "ACTIVE_2LANE_ROUTE_PATCHED_OOC_RUNDEF=$rundef"
  }
}

proc copy_if_exists {src dst} {
  if {[file exists $src]} {
    file copy -force $src $dst
  }
}

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
if {![file exists $port1_xdc]} {
  error "Missing PORT1 XDC: $port1_xdc"
}
if {![file exists $async_xdc]} {
  error "Missing async clock implementation XDC: $async_xdc"
}

set async_text [read_file_text $async_xdc]
if {[string first {set_clock_groups -asynchronous} $async_text] >= 0 && [string first {get_clocks clk_fpga_0} $async_text] >= 0} {
  error "async_clock_groups_impl.xdc still contains broad set_clock_groups"
}

set port1_text [read_file_text $port1_xdc]
if {[string first {PACKAGE_PIN G15 [get_ports {loop_rx_b0[1]}]} $port1_text] < 0} {
  error "PORT1 XDC is not the current B_RX1-to-G15 mapping"
}

set build_rc [catch {
  open_project $project_file
  set_property ip_repo_paths $ip_repo [current_project]
  file mkdir $ip_cache_dir
  config_ip_cache -use_cache_location $ip_cache_dir
  update_ip_catalog -rebuild

  set target_xdc [get_property TARGET_CONSTRS_FILE [current_fileset -constrset]]
  puts "ACTIVE_2LANE_ROUTE_TARGET_CONSTRAINT_FILE=$target_xdc"
  if {![string match "*PORT1.xdc" $target_xdc]} {
    error "Active target constraints are not PORT1.xdc: $target_xdc"
  }

  set async_obj [get_files -quiet $async_xdc]
  if {[llength $async_obj] == 0} {
    error "async_clock_groups_impl.xdc is not present in constrs_1"
  }

  set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
  if {$bd_file eq ""} {
    error "Missing design_shiboqi.bd"
  }
  set bd_text [read_file_text $bd_file]
  if {[string first {ir_stream_bidir_vec_bd} $bd_text] < 0} {
    error "Block design is not using ir_stream_bidir_vec_bd"
  }
  if {[string first {"value": "2"} $bd_text] < 0} {
    error "Block design does not appear to contain a 2-lane parameter value"
  }

  generate_target all $bd_file
  export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
  update_compile_order -fileset sources_1

  reset_run synth_1
  reset_run impl_1
  patch_ooc_rundef_scripts $repo_root
  launch_runs synth_1 -jobs $max_threads
  wait_on_run synth_1

  set synth_status [get_property STATUS [get_runs synth_1]]
  puts "ACTIVE_2LANE_ROUTE_SYNTH_STATUS=$synth_status"
  set synth_run_dir [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs synth_1]
  copy_if_exists [file join $synth_run_dir runme.log] [file join $out_dir synth_1_runme.log]
  if {![string match "*Complete*" $synth_status]} {
    error "Synthesis did not complete: $synth_status"
  }

  launch_runs impl_1 -to_step route_design -jobs $max_threads
  wait_on_run impl_1

  set impl_status [get_property STATUS [get_runs impl_1]]
  puts "ACTIVE_2LANE_ROUTE_IMPL_STATUS=$impl_status"
  set impl_run_dir [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1]
  copy_if_exists [file join $impl_run_dir runme.log] [file join $out_dir impl_1_runme.log]
  if {![string match "*Complete*" $impl_status]} {
    error "Implementation route did not complete: $impl_status"
  }

  open_run impl_1
  report_timing_summary -file [file join $out_dir timing_summary_post_route.rpt]
  report_utilization -file [file join $out_dir utilization_post_route.rpt]
  report_route_status -file [file join $out_dir route_status_post_route.rpt]
  report_drc -file [file join $out_dir drc_post_route.rpt]
  report_methodology -file [file join $out_dir methodology_post_route.rpt]
  report_control_sets -verbose -file [file join $out_dir control_sets_post_route.rpt]
  report_clocks -file [file join $out_dir clocks_post_route.rpt]
  write_checkpoint -force [file join $out_dir design_shiboqi_wrapper_post_route.dcp]
  puts "ACTIVE_2LANE_ROUTE_REPORTS_DONE"
} build_err build_opts]

puts "ACTIVE_2LANE_ROUTE_NO_HARDWARE_PROGRAMMING=1"
puts "ACTIVE_2LANE_ROUTE_NO_UART_WRITE=1"
puts "ACTIVE_2LANE_ROUTE_NO_TFDU_DRIVE=1"
puts "ACTIVE_2LANE_ROUTE_NO_BITSTREAM=1"

if {$build_rc != 0} {
  puts "ACTIVE_2LANE_ROUTE_BUILD_ERROR=$build_err"
  if {[catch {close_project} close_err]} {
    puts "ACTIVE_2LANE_ROUTE_CLOSE_AFTER_ERROR_WARNING=$close_err"
  }
  return -options $build_opts $build_err
}

close_project
puts "ACTIVE_2LANE_ROUTE_DONE out_dir=$out_dir"
