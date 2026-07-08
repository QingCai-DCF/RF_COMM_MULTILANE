set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set ip_cache_dir [file join $repo_root .vivado_ip_cache]
set out_dir [file join $repo_root TFDU_VFIR_Client_Array project_build_8lane_external]
set candidate_xdc [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new target_ir_array_8lane_a_only_candidate.xdc]
set port1_xdc [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new PORT1.xdc]

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
    puts "PROJECT_8LANE_EXTERNAL_PATCHED_OOC_RUNDEF=$rundef"
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
    puts "PROJECT_8LANE_EXTERNAL_PROP_SET_WARNING $prop $err"
    return 0
  }
  return 1
}

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
if {![file exists $candidate_xdc]} {
  error "Missing 8-lane A-only candidate XDC: $candidate_xdc"
}
if {![file exists $port1_xdc]} {
  error "Missing active PORT1 XDC: $port1_xdc"
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}

set_param general.maxThreads $max_threads
set ::env(IR_LANE_COUNT) 8
set ::env(IR_B_MODE) external
set ::env(IR_FRAGMENT_BYTES) 255
set ::env(IR_MAX_PACKET_BYTES) 255
set ::env(IR_MAX_RETRY) 16
set ::env(VIVADO_MAX_THREADS) $max_threads

puts "PROJECT_8LANE_EXTERNAL: configure BD for IR_LANE_COUNT=$::env(IR_LANE_COUNT) IR_B_MODE=$::env(IR_B_MODE)"
source [file join $repo_root tools configure_lane0_ab_hw_loopback.tcl]

file mkdir $out_dir
open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
file mkdir $ip_cache_dir
config_ip_cache -use_cache_location $ip_cache_dir
update_ip_catalog -rebuild

set stale_stub_refs [get_files -quiet */direct_build*/auto_blackbox_stubs.v]
if {[llength $stale_stub_refs] > 0} {
  puts "PROJECT_8LANE_EXTERNAL_REMOVE_STALE_DIRECT_STUBS=$stale_stub_refs"
  remove_files $stale_stub_refs
}

set port1_obj [get_files -quiet $port1_xdc]
if {[llength $port1_obj] == 0} {
  error "PORT1.xdc is not present in constrs_1: $port1_xdc"
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

set candidate_added 0
set candidate_obj [get_files -quiet $candidate_xdc]
if {[llength $candidate_obj] == 0} {
  add_files -fileset constrs_1 -norecurse $candidate_xdc
  set candidate_obj [get_files -quiet $candidate_xdc]
  set candidate_added 1
  puts "PROJECT_8LANE_EXTERNAL_XDC_ADDED=$candidate_xdc"
} else {
  puts "PROJECT_8LANE_EXTERNAL_XDC_ALREADY_PRESENT=$candidate_xdc"
}
if {[llength $candidate_obj] > 0} {
  set_property USED_IN {synthesis implementation} $candidate_obj
}

puts "PROJECT_8LANE_EXTERNAL_DISABLE_PORT1_FOR_BUILD=$port1_xdc USED_IN=$port1_used_in IS_ENABLED=$port1_is_enabled"
safe_set_prop USED_IN {} $port1_obj
if {$port1_is_enabled ne "__NO_PROPERTY__"} {
  safe_set_prop IS_ENABLED false $port1_obj
}
if {$target_prop ne ""} {
  safe_set_prop $target_prop $candidate_xdc $constrs_set
}

set build_rc [catch {
  set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
  if {$bd_file eq ""} {
    error "Missing design_shiboqi.bd in project"
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
  puts "PROJECT_8LANE_EXTERNAL_SYNTH_STATUS=$synth_status"
  if {![string match "*Complete*" $synth_status]} {
    error "Synthesis did not complete: $synth_status"
  }

  launch_runs impl_1 -to_step write_bitstream -jobs $max_threads
  wait_on_run impl_1

  set impl_status [get_property STATUS [get_runs impl_1]]
  puts "PROJECT_8LANE_EXTERNAL_IMPL_STATUS=$impl_status"
  if {![string match "*Complete*" $impl_status]} {
    error "Implementation did not complete: $impl_status"
  }

  open_run impl_1
  set run_dir [get_property DIRECTORY [current_run]]
  report_timing_summary -file [file join $out_dir timing_summary_post_route.rpt]
  report_utilization -file [file join $out_dir utilization_post_route.rpt]
  report_route_status -file [file join $out_dir route_status_post_route.rpt]
  report_drc -file [file join $out_dir drc_post_route.rpt]
  report_io -file [file join $out_dir io_post_route.rpt]
  if {[catch {write_debug_probes -force [file join $out_dir design_shiboqi_wrapper_8lane_external.ltx]} ltx_err]} {
    puts "PROJECT_8LANE_EXTERNAL_DEBUG_PROBES_SKIPPED=$ltx_err"
  }

  set run_bit [file join $run_dir design_shiboqi_wrapper.bit]
  if {![file exists $run_bit]} {
    error "Missing generated bitstream: $run_bit"
  }
  set bit_copy [file join $out_dir design_shiboqi_wrapper_8lane_external.bit]
  file copy -force $run_bit $bit_copy
  puts "PROJECT_8LANE_EXTERNAL_RUN_BITSTREAM=$run_bit"
  puts "PROJECT_8LANE_EXTERNAL_BITSTREAM_COPY=$bit_copy"
  puts "PROJECT_8LANE_EXTERNAL_BUILD_DONE"
} build_err build_opts]

if {[llength [get_files -quiet $port1_xdc]] > 0} {
  set port1_obj [get_files -quiet $port1_xdc]
  safe_set_prop USED_IN $port1_used_in $port1_obj
  if {$port1_is_enabled ne "__NO_PROPERTY__"} {
    safe_set_prop IS_ENABLED $port1_is_enabled $port1_obj
  }
  puts "PROJECT_8LANE_EXTERNAL_PORT1_RESTORED=$port1_xdc USED_IN=$port1_used_in IS_ENABLED=$port1_is_enabled"
}
if {$port1_target_constrs ne ""} {
  safe_set_prop $target_prop $port1_target_constrs [current_fileset -constrset]
  puts "PROJECT_8LANE_EXTERNAL_TARGET_CONSTRS_RESTORED=$port1_target_constrs"
}
if {$candidate_added && [llength [get_files -quiet $candidate_xdc]] > 0} {
  remove_files [get_files -quiet $candidate_xdc]
  puts "PROJECT_8LANE_EXTERNAL_XDC_REMOVED_AFTER_BUILD=$candidate_xdc"
}
close_project

if {$build_rc != 0} {
  return -options $build_opts $build_err
}
