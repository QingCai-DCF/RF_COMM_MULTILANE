set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set ip_cache_dir [file join $repo_root .vivado_ip_cache]
set scan_xdc_dir [file join $repo_root reports external_lane_scan_xdcs]
set port1_xdc [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new PORT1.xdc]

if {[info exists ::env(SCAN_OUT_DIR)] && $::env(SCAN_OUT_DIR) ne ""} {
  set out_dir [file normalize $::env(SCAN_OUT_DIR)]
} else {
  set out_dir [file join $repo_root reports external_lane_resource_scan_current]
}
file mkdir $out_dir

set scan_lanes {1 2 3 4 5 6 7 8}
if {[info exists ::env(SCAN_LANES)] && $::env(SCAN_LANES) ne ""} {
  set scan_lanes {}
  foreach lane [split $::env(SCAN_LANES) ", "] {
    if {$lane ne ""} {
      lappend scan_lanes $lane
    }
  }
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}
set_param general.maxThreads $max_threads

set scan_fragment_bytes 255
if {[info exists ::env(SCAN_FRAGMENT_BYTES)] && $::env(SCAN_FRAGMENT_BYTES) ne ""} {
  set scan_fragment_bytes $::env(SCAN_FRAGMENT_BYTES)
}
set scan_max_packet_bytes 255
if {[info exists ::env(SCAN_MAX_PACKET_BYTES)] && $::env(SCAN_MAX_PACKET_BYTES) ne ""} {
  set scan_max_packet_bytes $::env(SCAN_MAX_PACKET_BYTES)
}
set scan_max_retry ""
if {[info exists ::env(SCAN_MAX_RETRY)] && $::env(SCAN_MAX_RETRY) ne ""} {
  set scan_max_retry $::env(SCAN_MAX_RETRY)
}
set scan_tx_async_fifo_depth 1024
if {[info exists ::env(SCAN_TX_ASYNC_FIFO_DEPTH)] && $::env(SCAN_TX_ASYNC_FIFO_DEPTH) ne ""} {
  set scan_tx_async_fifo_depth $::env(SCAN_TX_ASYNC_FIFO_DEPTH)
}
set scan_rx_async_fifo_depth 1024
if {[info exists ::env(SCAN_RX_ASYNC_FIFO_DEPTH)] && $::env(SCAN_RX_ASYNC_FIFO_DEPTH) ne ""} {
  set scan_rx_async_fifo_depth $::env(SCAN_RX_ASYNC_FIFO_DEPTH)
}
set scan_stream_phy_dbg_select 0
if {[info exists ::env(SCAN_STREAM_PHY_DBG_SELECT)] && $::env(SCAN_STREAM_PHY_DBG_SELECT) ne ""} {
  set scan_stream_phy_dbg_select $::env(SCAN_STREAM_PHY_DBG_SELECT)
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
    puts "EXTERNAL_RESOURCE_SCAN_PATCHED_OOC_RUNDEF=$rundef"
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
    puts "EXTERNAL_RESOURCE_SCAN_PROP_SET_WARNING $prop $err"
    return 0
  }
  return 1
}

proc copy_if_exists {src dst} {
  if {[file exists $src]} {
    file copy -force $src $dst
  }
}

proc configure_external_lane {repo_root lane_count max_threads} {
  global scan_fragment_bytes scan_max_packet_bytes scan_max_retry scan_tx_async_fifo_depth scan_rx_async_fifo_depth scan_stream_phy_dbg_select
  set ::env(IR_LANE_COUNT) $lane_count
  set ::env(IR_B_MODE) external
  set ::env(IR_FRAGMENT_BYTES) $scan_fragment_bytes
  set ::env(IR_MAX_PACKET_BYTES) $scan_max_packet_bytes
  if {$scan_max_retry ne ""} {
    set ::env(IR_MAX_RETRY) $scan_max_retry
  } else {
    set ::env(IR_MAX_RETRY) [expr {$lane_count > 4 ? 16 : 8}]
  }
  set ::env(IR_TX_ASYNC_FIFO_DEPTH) $scan_tx_async_fifo_depth
  set ::env(IR_RX_ASYNC_FIFO_DEPTH) $scan_rx_async_fifo_depth
  set ::env(IR_STREAM_PHY_DBG_SELECT) $scan_stream_phy_dbg_select
  set ::env(VIVADO_MAX_THREADS) $max_threads
  puts "EXTERNAL_RESOURCE_SCAN_CONFIGURE lane=$lane_count mode=external fragment_bytes=$scan_fragment_bytes max_packet_bytes=$scan_max_packet_bytes tx_fifo=$scan_tx_async_fifo_depth rx_fifo=$scan_rx_async_fifo_depth stream_phy_dbg_select=$scan_stream_phy_dbg_select"
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
  puts "EXTERNAL_RESOURCE_SCAN_RESTORE_2LANE_START"
  source [file join $repo_root tools configure_lane0_ab_hw_loopback.tcl]
  puts "EXTERNAL_RESOURCE_SCAN_RESTORE_2LANE_DONE"
}

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
if {![file exists $port1_xdc]} {
  error "Missing PORT1 XDC: $port1_xdc"
}

set scan_rc [catch {
  foreach lane_count $scan_lanes {
    set lane_rc [catch {
      set lane_dir [file join $out_dir [format "lane_%02d" $lane_count]]
      file mkdir $lane_dir
      set scan_xdc [file join $scan_xdc_dir [format "target_ir_array_external_%dlane_scan.xdc" $lane_count]]
      if {![file exists $scan_xdc]} {
        error "Missing scan XDC for lane $lane_count: $scan_xdc"
      }

      puts "EXTERNAL_RESOURCE_SCAN_LANE_START=$lane_count"
      configure_external_lane $repo_root $lane_count $max_threads

      open_project $project_file
      set_property ip_repo_paths $ip_repo [current_project]
      file mkdir $ip_cache_dir
      config_ip_cache -use_cache_location $ip_cache_dir
      update_ip_catalog -rebuild

      set stale_stub_refs [get_files -quiet */direct_build*/auto_blackbox_stubs.v]
      if {[llength $stale_stub_refs] > 0} {
        puts "EXTERNAL_RESOURCE_SCAN_REMOVE_STALE_DIRECT_STUBS=$stale_stub_refs"
        remove_files $stale_stub_refs
      }

      set port1_obj [get_files -quiet $port1_xdc]
      if {[llength $port1_obj] == 0} {
        error "PORT1.xdc is not present in constrs_1"
      }
      set port1_used_in [safe_get_prop USED_IN $port1_obj {synthesis implementation}]
      set port1_is_enabled [safe_get_prop IS_ENABLED $port1_obj "__NO_PROPERTY__"]
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
      set synth_wait_rc [catch {wait_on_run synth_1} synth_wait_err synth_wait_opts]
      set synth_status [get_property STATUS [get_runs synth_1]]
      puts "EXTERNAL_RESOURCE_SCAN_SYNTH_STATUS lane=$lane_count status=$synth_status"
      copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs synth_1 runme.log] [file join $lane_dir synth_1_runme.log]
      copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs synth_1 design_shiboqi_wrapper_utilization_synth.rpt] [file join $lane_dir utilization_synth.rpt]
      if {$synth_wait_rc != 0 || ![string match "*Complete*" $synth_status]} {
        puts "EXTERNAL_RESOURCE_SCAN_LANE_SYNTH_FAIL=$lane_count"
      } else {
        launch_runs impl_1 -to_step place_design -jobs $max_threads
        set impl_wait_rc [catch {wait_on_run impl_1} impl_wait_err impl_wait_opts]
        set impl_status [get_property STATUS [get_runs impl_1]]
        puts "EXTERNAL_RESOURCE_SCAN_IMPL_STATUS lane=$lane_count status=$impl_status"
        copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1 runme.log] [file join $lane_dir impl_1_runme.log]
        copy_if_exists [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.runs impl_1 design_shiboqi_wrapper_drc_opted.rpt] [file join $lane_dir drc_opted.rpt]
        if {[catch {open_run impl_1} open_err]} {
          puts "EXTERNAL_RESOURCE_SCAN_OPEN_RUN_WARNING lane=$lane_count $open_err"
        } else {
          if {[catch {report_utilization -file [file join $lane_dir utilization_open_run.rpt]} util_err]} {
            puts "EXTERNAL_RESOURCE_SCAN_UTIL_WARNING lane=$lane_count $util_err"
          }
          if {[catch {report_drc -file [file join $lane_dir drc_open_run.rpt]} drc_err]} {
            puts "EXTERNAL_RESOURCE_SCAN_DRC_WARNING lane=$lane_count $drc_err"
          }
        }
        if {$impl_wait_rc != 0} {
          puts "EXTERNAL_RESOURCE_SCAN_IMPL_WAIT_ERROR lane=$lane_count $impl_wait_err"
        }
      }

      set port1_obj [get_files -quiet $port1_xdc]
      if {[llength $port1_obj] > 0} {
        safe_set_prop USED_IN $port1_used_in $port1_obj
        if {$port1_is_enabled ne "__NO_PROPERTY__"} {
          safe_set_prop IS_ENABLED $port1_is_enabled $port1_obj
        }
      }
      if {$port1_target_constrs ne ""} {
        safe_set_prop $target_prop $port1_target_constrs [current_fileset -constrset]
      }
      if {$scan_added && [llength [get_files -quiet $scan_xdc]] > 0} {
        remove_files [get_files -quiet $scan_xdc]
      }
      close_project
      puts "EXTERNAL_RESOURCE_SCAN_LANE_DONE=$lane_count"
    } lane_err lane_opts]

    if {$lane_rc != 0} {
      puts "EXTERNAL_RESOURCE_SCAN_LANE_ERROR lane=$lane_count error=$lane_err"
      if {[catch {close_project} close_err]} {
        puts "EXTERNAL_RESOURCE_SCAN_CLOSE_AFTER_ERROR_WARNING=$close_err"
      }
    }
  }
} scan_err scan_opts]

set restore_rc [catch {restore_active_2lane $repo_root $max_threads} restore_err restore_opts]
if {$restore_rc != 0} {
  puts "EXTERNAL_RESOURCE_SCAN_RESTORE_2LANE_ERROR=$restore_err"
}

if {$scan_rc != 0} {
  return -options $scan_opts $scan_err
}
if {$restore_rc != 0} {
  return -options $restore_opts $restore_err
}
puts "EXTERNAL_RESOURCE_SCAN_DONE lanes=$scan_lanes out_dir=$out_dir"
