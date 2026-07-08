set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set ip_cache_dir [file join $repo_root .vivado_ip_cache]
set scan_xdc_dir [file join $repo_root reports external_lane_scan_xdcs]
set port1_xdc [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new PORT1.xdc]

if {[info exists ::env(REDUCED_ROUTE_OUT_DIR)] && $::env(REDUCED_ROUTE_OUT_DIR) ne ""} {
  set out_dir [file normalize $::env(REDUCED_ROUTE_OUT_DIR)]
} else {
  set out_dir [file join $repo_root reports build_external_reduced_2lane_route_current]
}
file mkdir $out_dir

set lane_count 2
if {[info exists ::env(REDUCED_ROUTE_LANE_COUNT)] && $::env(REDUCED_ROUTE_LANE_COUNT) ne ""} {
  set lane_count $::env(REDUCED_ROUTE_LANE_COUNT)
}
set fragment_bytes 64
if {[info exists ::env(REDUCED_ROUTE_FRAGMENT_BYTES)] && $::env(REDUCED_ROUTE_FRAGMENT_BYTES) ne ""} {
  set fragment_bytes $::env(REDUCED_ROUTE_FRAGMENT_BYTES)
}
set max_packet_bytes 255
if {[info exists ::env(REDUCED_ROUTE_MAX_PACKET_BYTES)] && $::env(REDUCED_ROUTE_MAX_PACKET_BYTES) ne ""} {
  set max_packet_bytes $::env(REDUCED_ROUTE_MAX_PACKET_BYTES)
}
set tx_async_fifo_depth 128
if {[info exists ::env(REDUCED_ROUTE_TX_ASYNC_FIFO_DEPTH)] && $::env(REDUCED_ROUTE_TX_ASYNC_FIFO_DEPTH) ne ""} {
  set tx_async_fifo_depth $::env(REDUCED_ROUTE_TX_ASYNC_FIFO_DEPTH)
}
set rx_async_fifo_depth 128
if {[info exists ::env(REDUCED_ROUTE_RX_ASYNC_FIFO_DEPTH)] && $::env(REDUCED_ROUTE_RX_ASYNC_FIFO_DEPTH) ne ""} {
  set rx_async_fifo_depth $::env(REDUCED_ROUTE_RX_ASYNC_FIFO_DEPTH)
}
set stream_phy_dbg_select 0
if {[info exists ::env(REDUCED_ROUTE_STREAM_PHY_DBG_SELECT)] && $::env(REDUCED_ROUTE_STREAM_PHY_DBG_SELECT) ne ""} {
  set stream_phy_dbg_select $::env(REDUCED_ROUTE_STREAM_PHY_DBG_SELECT)
}
set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}
set control_set_opt_threshold ""
if {[info exists ::env(REDUCED_ROUTE_CONTROL_SET_OPT_THRESHOLD)] && $::env(REDUCED_ROUTE_CONTROL_SET_OPT_THRESHOLD) ne ""} {
  set control_set_opt_threshold $::env(REDUCED_ROUTE_CONTROL_SET_OPT_THRESHOLD)
}
set opt_design_more_options ""
if {[info exists ::env(REDUCED_ROUTE_OPT_DESIGN_MORE_OPTIONS)] && $::env(REDUCED_ROUTE_OPT_DESIGN_MORE_OPTIONS) ne ""} {
  set opt_design_more_options $::env(REDUCED_ROUTE_OPT_DESIGN_MORE_OPTIONS)
}
set post_opt_control_set_merge 0
if {[info exists ::env(REDUCED_ROUTE_POST_OPT_CONTROL_SET_MERGE)] && $::env(REDUCED_ROUTE_POST_OPT_CONTROL_SET_MERGE) ne "" && $::env(REDUCED_ROUTE_POST_OPT_CONTROL_SET_MERGE) ne "0"} {
  set post_opt_control_set_merge 1
}
set remap_sink_frame_data_enable 0
if {[info exists ::env(REDUCED_ROUTE_REMAP_SINK_FRAME_DATA_ENABLE)] && $::env(REDUCED_ROUTE_REMAP_SINK_FRAME_DATA_ENABLE) ne "" && $::env(REDUCED_ROUTE_REMAP_SINK_FRAME_DATA_ENABLE) ne "0"} {
  set remap_sink_frame_data_enable 1
}
set disable_ip_cache 0
if {[info exists ::env(REDUCED_ROUTE_DISABLE_IP_CACHE)] && $::env(REDUCED_ROUTE_DISABLE_IP_CACHE) ne "" && $::env(REDUCED_ROUTE_DISABLE_IP_CACHE) ne "0"} {
  set disable_ip_cache 1
}
set_param general.maxThreads $max_threads

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
    puts "EXTERNAL_REDUCED_ROUTE_PATCHED_OOC_RUNDEF=$rundef"
  }
}

proc safe_get_prop {prop obj default_value} {
  if {[llength $obj] == 0} {
    return $default_value
  }
  set props [list_property $obj]
  if {[lsearch -exact $props $prop] < 0} {
    return $default_value
  }
  if {[catch {get_property $prop $obj} value]} {
    return $default_value
  }
  return $value
}

proc safe_set_prop {prop value obj} {
  if {[llength $obj] == 0} {
    return 0
  }
  set props [list_property $obj]
  if {[lsearch -exact $props $prop] < 0} {
    return 0
  }
  if {[catch {set_property $prop $value $obj} err]} {
    puts "EXTERNAL_REDUCED_ROUTE_PROP_SET_WARNING $prop $err"
    return 0
  }
  return 1
}

proc copy_if_exists {src dst} {
  if {[file exists $src]} {
    file copy -force $src $dst
  }
}

proc configure_external_reduced {repo_root lane_count fragment_bytes max_packet_bytes tx_async_fifo_depth rx_async_fifo_depth stream_phy_dbg_select max_threads} {
  set ::env(IR_LANE_COUNT) $lane_count
  set ::env(IR_B_MODE) external
  set ::env(IR_FRAGMENT_BYTES) $fragment_bytes
  set ::env(IR_MAX_PACKET_BYTES) $max_packet_bytes
  set ::env(IR_MAX_RETRY) [expr {$lane_count > 4 ? 16 : 8}]
  set ::env(IR_TX_ASYNC_FIFO_DEPTH) $tx_async_fifo_depth
  set ::env(IR_RX_ASYNC_FIFO_DEPTH) $rx_async_fifo_depth
  set ::env(IR_STREAM_PHY_DBG_SELECT) $stream_phy_dbg_select
  set ::env(VIVADO_MAX_THREADS) $max_threads
  puts "EXTERNAL_REDUCED_ROUTE_CONFIGURE lane=$lane_count mode=external fragment_bytes=$fragment_bytes max_packet_bytes=$max_packet_bytes tx_fifo=$tx_async_fifo_depth rx_fifo=$rx_async_fifo_depth stream_phy_dbg_select=$stream_phy_dbg_select"
  source [file join $repo_root tools configure_lane0_ab_hw_loopback.tcl]
}

proc restore_active_2lane {repo_root max_threads} {
  set ::env(IR_LANE_COUNT) 2
  set ::env(IR_B_MODE) stream_bidir
  set ::env(IR_FRAGMENT_BYTES) 255
  set ::env(IR_MAX_PACKET_BYTES) 255
  set ::env(IR_TX_ASYNC_FIFO_DEPTH) 1024
  set ::env(IR_RX_ASYNC_FIFO_DEPTH) 1024
  set ::env(IR_STREAM_PHY_DBG_SELECT) 0
  set ::env(IR_B_ACK_LANE_MASK) 0x3
  set ::env(IR_B_TX_LANE_MASK) 0x3
  set ::env(IR_B_RX_LANE_MASK) 0x3
  set ::env(IR_B_EXPECTED_A_LANE_MASK) 0x3
  set ::env(VIVADO_MAX_THREADS) $max_threads
  puts "EXTERNAL_REDUCED_ROUTE_RESTORE_2LANE_START"
  source [file join $repo_root tools configure_lane0_ab_hw_loopback.tcl]
  puts "EXTERNAL_REDUCED_ROUTE_RESTORE_2LANE_DONE"
}

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
if {![file exists $port1_xdc]} {
  error "Missing PORT1 XDC: $port1_xdc"
}
set scan_xdc [file join $scan_xdc_dir [format "target_ir_array_external_%dlane_scan.xdc" $lane_count]]
if {![file exists $scan_xdc]} {
  error "Missing external scan XDC: $scan_xdc"
}

set build_rc [catch {
  configure_external_reduced $repo_root $lane_count $fragment_bytes $max_packet_bytes $tx_async_fifo_depth $rx_async_fifo_depth $stream_phy_dbg_select $max_threads

  open_project $project_file
  set_property ip_repo_paths $ip_repo [current_project]
  file mkdir $ip_cache_dir
  if {$disable_ip_cache} {
    puts "EXTERNAL_REDUCED_ROUTE_IP_CACHE=disabled"
    config_ip_cache -disable_cache
  } else {
    puts "EXTERNAL_REDUCED_ROUTE_IP_CACHE=use_cache_location $ip_cache_dir"
    config_ip_cache -use_cache_location $ip_cache_dir
  }
  update_ip_catalog -rebuild

  set stale_stub_refs [get_files -quiet */direct_build*/auto_blackbox_stubs.v]
  if {[llength $stale_stub_refs] > 0} {
    puts "EXTERNAL_REDUCED_ROUTE_REMOVE_STALE_DIRECT_STUBS=$stale_stub_refs"
    remove_files $stale_stub_refs
  }

  set port1_obj [get_files -quiet $port1_xdc]
  if {[llength $port1_obj] == 0} {
    error "PORT1.xdc is not present in constrs_1"
  }
  set port1_used_in [safe_get_prop USED_IN $port1_obj {synthesis implementation}]
  set port1_is_enabled [safe_get_prop IS_ENABLED $port1_obj "__NO_PROPERTY__"]
  set synth_run [get_runs synth_1]
  set impl_run [get_runs impl_1]
  set old_control_set_opt_threshold [safe_get_prop STEPS.SYNTH_DESIGN.ARGS.CONTROL_SET_OPT_THRESHOLD $synth_run "__NO_PROPERTY__"]
  if {$control_set_opt_threshold ne ""} {
    safe_set_prop STEPS.SYNTH_DESIGN.ARGS.CONTROL_SET_OPT_THRESHOLD $control_set_opt_threshold $synth_run
    puts "EXTERNAL_REDUCED_ROUTE_CONTROL_SET_OPT_THRESHOLD_SET=$control_set_opt_threshold old=$old_control_set_opt_threshold"
  }
  set old_opt_design_more_options [safe_get_prop {STEPS.OPT_DESIGN.ARGS.MORE OPTIONS} $impl_run "__NO_PROPERTY__"]
  if {$opt_design_more_options ne ""} {
    safe_set_prop {STEPS.OPT_DESIGN.ARGS.MORE OPTIONS} $opt_design_more_options $impl_run
    puts "EXTERNAL_REDUCED_ROUTE_OPT_DESIGN_MORE_OPTIONS_SET=$opt_design_more_options old=$old_opt_design_more_options"
  }
  set old_opt_design_tcl_pre [safe_get_prop STEPS.OPT_DESIGN.TCL.PRE $impl_run "__NO_PROPERTY__"]
  set pre_opt_hook ""
  if {$remap_sink_frame_data_enable} {
    set pre_opt_hook [file join $out_dir pre_opt_sink_frame_data_control_set_remap.tcl]
    set hook_fh [open $pre_opt_hook w]
    puts $hook_fh "puts \"EXTERNAL_REDUCED_ROUTE_REMAP_SINK_FRAME_DATA_ENABLE_START\""
    if {$old_opt_design_tcl_pre ne "" && $old_opt_design_tcl_pre ne "__NO_PROPERTY__"} {
      puts $hook_fh "source [list $old_opt_design_tcl_pre]"
    }
    puts $hook_fh {set sink_frame_regs [get_cells -hier -regexp {.*u_sink/frame_data_reg\[.*\]}]}
    puts $hook_fh {set sink_frame_count [llength $sink_frame_regs]}
    puts $hook_fh {puts "EXTERNAL_REDUCED_ROUTE_REMAP_SINK_FRAME_DATA_REGS=$sink_frame_count"}
    puts $hook_fh {if {$sink_frame_count == 0} { error "No u_sink/frame_data registers matched for CONTROL_SET_REMAP" }}
    puts $hook_fh {set_property CONTROL_SET_REMAP ENABLE $sink_frame_regs}
    puts $hook_fh {set sample_file [file join [file dirname [info script]] sink_frame_data_control_set_remap_properties.rpt]}
    puts $hook_fh {set sample_fh [open $sample_file w]}
    puts $hook_fh {puts $sample_fh "sink_frame_count=$sink_frame_count"}
    puts $hook_fh {set sample_idx 0}
    puts $hook_fh {foreach reg [lrange $sink_frame_regs 0 15] {
  puts $sample_fh "$sample_idx $reg CONTROL_SET_REMAP=[get_property CONTROL_SET_REMAP $reg]"
  incr sample_idx
}}
    puts $hook_fh {close $sample_fh}
    puts $hook_fh "puts \"EXTERNAL_REDUCED_ROUTE_REMAP_SINK_FRAME_DATA_ENABLE_DONE\""
    close $hook_fh
    safe_set_prop STEPS.OPT_DESIGN.TCL.PRE $pre_opt_hook $impl_run
    puts "EXTERNAL_REDUCED_ROUTE_OPT_DESIGN_TCL_PRE_SET=$pre_opt_hook old=$old_opt_design_tcl_pre"
  }
  set old_opt_design_tcl_post [safe_get_prop STEPS.OPT_DESIGN.TCL.POST $impl_run "__NO_PROPERTY__"]
  set post_opt_hook ""
  if {$post_opt_control_set_merge} {
    set post_opt_hook [file join $out_dir post_opt_control_set_merge.tcl]
    set hook_fh [open $post_opt_hook w]
    puts $hook_fh "puts \"EXTERNAL_REDUCED_ROUTE_POST_OPT_CONTROL_SET_MERGE_START\""
    puts $hook_fh "opt_design -control_set_merge -merge_equivalent_drivers"
    puts $hook_fh "report_control_sets -verbose -file [list [file join $out_dir control_sets_post_extra_opt.rpt]]"
    puts $hook_fh "puts \"EXTERNAL_REDUCED_ROUTE_POST_OPT_CONTROL_SET_MERGE_DONE\""
    close $hook_fh
    safe_set_prop STEPS.OPT_DESIGN.TCL.POST $post_opt_hook $impl_run
    puts "EXTERNAL_REDUCED_ROUTE_OPT_DESIGN_TCL_POST_SET=$post_opt_hook old=$old_opt_design_tcl_post"
  }
  set constrs_set [current_fileset -constrset]
  set target_prop ""
  foreach prop_name {TARGET_CONSTRS_FILE target_constrs_file TargetConstrsFile} {
    if {[lsearch -exact [list_property $constrs_set] $prop_name] >= 0} {
      set target_prop $prop_name
      break
    }
  }
  set port1_target_constrs ""
  if {$target_prop ne ""} {
    set port1_target_constrs [safe_get_prop $target_prop $constrs_set ""]
  }

  set scan_added 0
  if {[llength [get_files -quiet $scan_xdc]] == 0} {
    add_files -fileset constrs_1 -norecurse $scan_xdc
    set scan_added 1
    puts "EXTERNAL_REDUCED_ROUTE_XDC_ADDED=$scan_xdc"
  }
  set scan_obj [get_files -quiet $scan_xdc]
  set_property USED_IN {synthesis implementation} $scan_obj

  safe_set_prop USED_IN {} $port1_obj
  if {$port1_is_enabled ne "__NO_PROPERTY__"} {
    safe_set_prop IS_ENABLED false $port1_obj
  }
  if {$target_prop ne ""} {
    safe_set_prop $target_prop $scan_xdc $constrs_set
  }

  set route_rc [catch {
    set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
    if {$bd_file eq ""} {
      error "Missing design_shiboqi.bd"
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
    puts "EXTERNAL_REDUCED_ROUTE_SYNTH_STATUS=$synth_status"
    copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs synth_1 runme.log] [file join $out_dir synth_1_runme.log]
    copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs synth_1 design_shiboqi_wrapper.dcp] [file join $out_dir design_shiboqi_wrapper_synth.dcp]
    if {![string match "*Complete*" $synth_status]} {
      error "Synthesis did not complete: $synth_status"
    }

    launch_runs impl_1 -to_step route_design -jobs $max_threads
    wait_on_run impl_1

    set impl_status [get_property STATUS [get_runs impl_1]]
    puts "EXTERNAL_REDUCED_ROUTE_IMPL_STATUS=$impl_status"
    copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1 runme.log] [file join $out_dir impl_1_runme.log]
    copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1 design_shiboqi_wrapper_drc_opted.rpt] [file join $out_dir drc_opted.rpt]
    copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1 design_shiboqi_wrapper_placed.dcp] [file join $out_dir design_shiboqi_wrapper_placed.dcp]
    copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1 design_shiboqi_wrapper_routed.dcp] [file join $out_dir design_shiboqi_wrapper_routed.dcp]
    if {![string match "*Complete*" $impl_status]} {
      error "Implementation route did not complete: $impl_status"
    }

    open_run impl_1
    report_timing_summary -file [file join $out_dir timing_summary_post_route.rpt]
    report_utilization -file [file join $out_dir utilization_post_route.rpt]
    report_route_status -file [file join $out_dir route_status_post_route.rpt]
    report_drc -file [file join $out_dir drc_post_route.rpt]
    report_io -file [file join $out_dir io_post_route.rpt]
    write_checkpoint -force [file join $out_dir design_shiboqi_wrapper_post_route.dcp]
    puts "EXTERNAL_REDUCED_ROUTE_BUILD_DONE"
  } route_err route_opts]

  set port1_obj [get_files -quiet $port1_xdc]
  if {[llength $port1_obj] > 0} {
    safe_set_prop USED_IN $port1_used_in $port1_obj
    if {$port1_is_enabled ne "__NO_PROPERTY__"} {
      safe_set_prop IS_ENABLED $port1_is_enabled $port1_obj
    }
    puts "EXTERNAL_REDUCED_ROUTE_PORT1_RESTORED=$port1_xdc USED_IN=$port1_used_in IS_ENABLED=$port1_is_enabled"
  }
  if {$port1_target_constrs ne ""} {
    safe_set_prop $target_prop $port1_target_constrs [current_fileset -constrset]
    puts "EXTERNAL_REDUCED_ROUTE_TARGET_CONSTRS_RESTORED=$port1_target_constrs"
  }
  if {$scan_added && [llength [get_files -quiet $scan_xdc]] > 0} {
    remove_files [get_files -quiet $scan_xdc]
    puts "EXTERNAL_REDUCED_ROUTE_XDC_REMOVED_AFTER_BUILD=$scan_xdc"
  }
  if {$control_set_opt_threshold ne "" && $old_control_set_opt_threshold ne "__NO_PROPERTY__"} {
    safe_set_prop STEPS.SYNTH_DESIGN.ARGS.CONTROL_SET_OPT_THRESHOLD $old_control_set_opt_threshold [get_runs synth_1]
    puts "EXTERNAL_REDUCED_ROUTE_CONTROL_SET_OPT_THRESHOLD_RESTORED=$old_control_set_opt_threshold"
  }
  if {$opt_design_more_options ne "" && $old_opt_design_more_options ne "__NO_PROPERTY__"} {
    safe_set_prop {STEPS.OPT_DESIGN.ARGS.MORE OPTIONS} $old_opt_design_more_options [get_runs impl_1]
    puts "EXTERNAL_REDUCED_ROUTE_OPT_DESIGN_MORE_OPTIONS_RESTORED=$old_opt_design_more_options"
  }
  if {$remap_sink_frame_data_enable && $old_opt_design_tcl_pre ne "__NO_PROPERTY__"} {
    safe_set_prop STEPS.OPT_DESIGN.TCL.PRE $old_opt_design_tcl_pre [get_runs impl_1]
    puts "EXTERNAL_REDUCED_ROUTE_OPT_DESIGN_TCL_PRE_RESTORED=$old_opt_design_tcl_pre"
  }
  if {$post_opt_control_set_merge && $old_opt_design_tcl_post ne "__NO_PROPERTY__"} {
    safe_set_prop STEPS.OPT_DESIGN.TCL.POST $old_opt_design_tcl_post [get_runs impl_1]
    puts "EXTERNAL_REDUCED_ROUTE_OPT_DESIGN_TCL_POST_RESTORED=$old_opt_design_tcl_post"
  }
  close_project

  if {$route_rc != 0} {
    return -options $route_opts $route_err
  }
} build_err build_opts]

if {$build_rc != 0} {
  puts "EXTERNAL_REDUCED_ROUTE_BUILD_ERROR=$build_err"
  if {[catch {close_project} close_err]} {
    puts "EXTERNAL_REDUCED_ROUTE_CLOSE_AFTER_ERROR_WARNING=$close_err"
  }
}

set restore_rc [catch {restore_active_2lane $repo_root $max_threads} restore_err restore_opts]
if {$restore_rc != 0} {
  puts "EXTERNAL_REDUCED_ROUTE_RESTORE_2LANE_ERROR=$restore_err"
}

puts "EXTERNAL_REDUCED_ROUTE_NO_HARDWARE_PROGRAMMING=1"
puts "EXTERNAL_REDUCED_ROUTE_NO_UART_WRITE=1"
puts "EXTERNAL_REDUCED_ROUTE_NO_TFDU_DRIVE=1"
puts "EXTERNAL_REDUCED_ROUTE_ETHERNET_DEFERRED=1"

if {$build_rc != 0} {
  error $build_err
}
if {$restore_rc != 0} {
  error $restore_err
}
puts "EXTERNAL_REDUCED_ROUTE_DONE out_dir=$out_dir"
