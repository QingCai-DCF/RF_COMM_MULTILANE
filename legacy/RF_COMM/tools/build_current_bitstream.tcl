set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set ip_cache_dir [file join $repo_root .vivado_ip_cache]
set xsa_file [file join $repo_root TFDU_VFIR_Client_Array design_shiboqi_wrapper.xsa]
set bit_copy [file join $repo_root TFDU_VFIR_Client_Array design_shiboqi_wrapper.bit]

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
    puts "PATCHED_OOC_RUNDEF=$rundef"
  }
}

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}

set_param general.maxThreads $max_threads
open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
file mkdir $ip_cache_dir
if {[info exists ::env(VIVADO_DISABLE_IP_CACHE)] && $::env(VIVADO_DISABLE_IP_CACHE) ne "" && $::env(VIVADO_DISABLE_IP_CACHE) ne "0"} {
  puts "IP_CACHE=disabled"
  config_ip_cache -disable_cache
} else {
  config_ip_cache -use_cache_location $ip_cache_dir
}
update_ip_catalog -rebuild

set ir_ip [get_ips -quiet design_shiboqi_ir_array_top_axi_0_0]
if {$ir_ip ne ""} {
  set ip_status_file [file join $repo_root reports build_current_bitstream_ip_status.rpt]
  file mkdir [file dirname $ip_status_file]
  report_ip_status -file $ip_status_file
  if {[catch {upgrade_ip $ir_ip} upgrade_err]} {
    puts "IP_UPGRADE_SKIPPED=$upgrade_err"
  } else {
    puts "IP_UPGRADED=$ir_ip"
  }
}

set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
if {$bd_file eq ""} {
  error "Missing design_shiboqi.bd in project"
}

set skip_bd_generate 0
if {[info exists ::env(VIVADO_SKIP_BD_GENERATE)] && $::env(VIVADO_SKIP_BD_GENERATE) ne "" && $::env(VIVADO_SKIP_BD_GENERATE) ne "0"} {
  set skip_bd_generate 1
  puts "BD_GENERATE=skipped_existing_outputs"
}

if {!$skip_bd_generate} {
  if {[info exists ::env(VIVADO_DISABLE_IP_CACHE)] && $::env(VIVADO_DISABLE_IP_CACHE) ne "" && $::env(VIVADO_DISABLE_IP_CACHE) ne "0"} {
    reset_target all $bd_file
  }
  generate_target all $bd_file
  export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
} else {
  puts "BD_GENERATE_SKIP_REASON=VIVADO_SKIP_BD_GENERATE"
}

set skip_compile_order 0
if {[info exists ::env(VIVADO_SKIP_COMPILE_ORDER)] && $::env(VIVADO_SKIP_COMPILE_ORDER) ne "" && $::env(VIVADO_SKIP_COMPILE_ORDER) ne "0"} {
  set skip_compile_order 1
  puts "COMPILE_ORDER_UPDATE=skipped_existing_order"
}

if {!$skip_compile_order} {
  update_compile_order -fileset sources_1
} else {
  puts "COMPILE_ORDER_SKIP_REASON=VIVADO_SKIP_COMPILE_ORDER"
}

reset_run synth_1
reset_run impl_1
patch_ooc_rundef_scripts $repo_root
launch_runs synth_1 -jobs $max_threads
wait_on_run synth_1

set synth_status [get_property STATUS [get_runs synth_1]]
puts "SYNTH_STATUS=$synth_status"
if {![string match "*Complete*" $synth_status]} {
  error "Synthesis did not complete: $synth_status"
}

launch_runs impl_1 -to_step write_bitstream -jobs $max_threads
wait_on_run impl_1

set impl_status [get_property STATUS [get_runs impl_1]]
puts "IMPL_STATUS=$impl_status"
if {![string match "*Complete*" $impl_status]} {
  error "Implementation did not complete: $impl_status"
}

open_run impl_1
set run_dir [get_property DIRECTORY [current_run]]
report_timing_summary -file [file join $run_dir timing_summary_post_route.rpt]
report_utilization -file [file join $run_dir utilization_post_route.rpt]
report_route_status -file [file join $run_dir route_status_post_route.rpt]
if {[catch {
  set ltx_file [file join $run_dir design_shiboqi_wrapper.ltx]
  write_debug_probes -force $ltx_file
  puts "DEBUG_PROBES_FILE=$ltx_file"
} ltx_err]} {
  puts "DEBUG_PROBES_FILE_SKIPPED=$ltx_err"
}
write_hw_platform -fixed -include_bit -force -file $xsa_file

set run_bit [file join $run_dir design_shiboqi_wrapper.bit]
if {[file exists $run_bit]} {
  file copy -force $run_bit $bit_copy
  puts "BITSTREAM_FILE=$run_bit"
  puts "BITSTREAM_COPY=$bit_copy"
} else {
  error "Missing generated bitstream: $run_bit"
}

puts "BUILD_CURRENT_BITSTREAM_DONE"
close_project
