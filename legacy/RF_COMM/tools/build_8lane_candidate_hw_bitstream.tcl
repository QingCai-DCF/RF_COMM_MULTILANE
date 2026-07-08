set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]
set out_dir [file join $repo_root TFDU_VFIR_Client_Array direct_build_8lane_candidate]
set candidate_xdc [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs constrs_1 new target_ir_array_8lane_candidate.xdc]

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}
if {![file exists $candidate_xdc]} {
  error "Missing 8-lane candidate XDC: $candidate_xdc"
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}

set_param general.maxThreads $max_threads
set ::env(IR_LANE_COUNT) 8
set ::env(IR_B_MODE) stream_bidir
set ::env(IR_FRAGMENT_BYTES) 255
set ::env(IR_MAX_PACKET_BYTES) 255
set ::env(IR_B_ACK_LANE_MASK) 0xff
set ::env(IR_B_TX_LANE_MASK) 0xff
set ::env(IR_B_RX_LANE_MASK) 0xff
set ::env(IR_B_EXPECTED_A_LANE_MASK) 0xff
set ::env(VIVADO_MAX_THREADS) $max_threads

puts "BUILD_8LANE_CANDIDATE_HW: configure BD for IR_LANE_COUNT=$::env(IR_LANE_COUNT) IR_B_MODE=$::env(IR_B_MODE)"
source [file join $repo_root tools configure_lane0_ab_hw_loopback.tcl]

open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild

set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
if {$bd_file eq ""} {
  error "Missing design_shiboqi.bd in project"
}

file mkdir $out_dir
generate_target all $bd_file
export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
update_compile_order -fileset sources_1

set bd_gen_dir [file normalize [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.gen sources_1 bd design_shiboqi ip]]
set auto_synth_files [list]
set vhdl_synth_files [list]
if {[file exists $bd_gen_dir]} {
  set auto_synth_files [glob -nocomplain -directory $bd_gen_dir -types f */synth/*.v]
  set vhdl_synth_files [glob -nocomplain -directory $bd_gen_dir -types f */synth/*.vhd]
}

proc write_blackbox_stub_from_synth {out_fh src_file} {
  set in_fh [open $src_file r]
  set text [read $in_fh]
  close $in_fh

  set started 0
  foreach line [split $text "\n"] {
    if {!$started} {
      if {[regexp {^\s*module\s+([A-Za-z0-9_]+)} $line]} {
        puts $out_fh "(* black_box = \"true\" *)"
        puts $out_fh $line
        set started 1
      }
      continue
    }

    if {[regexp {^\s+[A-Za-z][A-Za-z0-9_]*_v[0-9][A-Za-z0-9_]*\s*#\s*\(} $line]} {
      puts $out_fh "endmodule"
      puts $out_fh ""
      return
    }
    puts $out_fh $line
  }

  error "Could not find internal IP instance while generating stub from $src_file"
}

proc write_blackbox_stub_from_vhdl_entity {out_fh src_file} {
  set in_fh [open $src_file r]
  set text [read $in_fh]
  close $in_fh

  regsub -all {\r\n} $text "\n" text
  if {![regexp -nocase {ENTITY[ \t\r\n]+([A-Za-z0-9_]+)[ \t\r\n]+IS} $text -> entity_name]} {
    error "Could not parse VHDL entity name from $src_file"
  }

  set in_port_block 0
  set port_lines [list]
  foreach raw_line [split $text "\n"] {
    set line [string trim $raw_line]
    if {!$in_port_block} {
      if {[regexp -nocase {^PORT[ \t]*\(} $line]} {
        set in_port_block 1
        regsub -nocase {^PORT[ \t]*\(} $line "" line
        if {[string trim $line] ne ""} {
          lappend port_lines $line
        }
      }
      continue
    }
    if {[regexp {^\)[ \t]*;[ \t]*$} $line]} {
      break
    }
    lappend port_lines $line
  }
  if {[llength $port_lines] == 0} {
    error "Could not parse VHDL entity port block from $src_file"
  }

  set ports [list]
  set decls [list]
  foreach raw_line $port_lines {
    set line [string trim $raw_line]
    if {$line eq ""} {
      continue
    }
    regsub -- {--.*$} $line "" line
    set line [string trim $line]
    if {$line eq ""} {
      continue
    }
    regsub {;$} $line "" line
    if {![regexp -nocase {^([A-Za-z0-9_, \t]+)[ \t]*:[ \t]*(IN|OUT|INOUT)[ \t]+STD_LOGIC(_VECTOR)?(\([0-9]+[ \t]+(DOWNTO|TO)[ \t]+[0-9]+\))?} $line -> names direction vector _range range_dir]} {
      continue
    }
    set dir [string tolower $direction]
    if {$dir eq "in"} {
      set verilog_dir "input wire"
    } elseif {$dir eq "out"} {
      set verilog_dir "output wire"
    } else {
      set verilog_dir "inout wire"
    }
    set width ""
    if {$vector ne "" && [regexp -nocase {([0-9]+)[ \t]+(DOWNTO|TO)[ \t]+([0-9]+)} $_range -> left _dir right]} {
      set width "\[$left:$right\] "
    }
    foreach name [split $names ","] {
      set port_name [string trim $name]
      if {$port_name eq ""} {
        continue
      }
      lappend ports $port_name
      lappend decls "$verilog_dir $width$port_name;"
    }
  }

  if {[llength $ports] == 0} {
    error "No VHDL ports parsed from $src_file"
  }

  puts $out_fh "(* black_box = \"true\" *)"
  puts $out_fh "module $entity_name ("
  for {set i 0} {$i < [llength $ports]} {incr i} {
    set suffix [expr {$i == [llength $ports] - 1 ? "" : ","}]
    puts $out_fh "  [lindex $ports $i]$suffix"
  }
  puts $out_fh ");"
  foreach decl $decls {
    puts $out_fh $decl
  }
  puts $out_fh "endmodule"
  puts $out_fh ""
}

set generated_stub_file [file join $out_dir auto_blackbox_stubs.v]
set stub_fh [open $generated_stub_file w]
puts $stub_fh "// Generated by build_8lane_candidate_hw_bitstream.tcl for direct synthesis."
set generated_verilog_stub_count 0
set generated_vhdl_stub_count 0
foreach synth_file [lsort -unique $auto_synth_files] {
  if {[catch {write_blackbox_stub_from_synth $stub_fh $synth_file} stub_err]} {
    puts "DIRECT_8LANE_CANDIDATE_VERILOG_STUB_SKIP file=$synth_file reason=$stub_err"
  } else {
    incr generated_verilog_stub_count
  }
}
foreach synth_file [lsort -unique $vhdl_synth_files] {
  if {[catch {write_blackbox_stub_from_vhdl_entity $stub_fh $synth_file} stub_err]} {
    puts "DIRECT_8LANE_CANDIDATE_VHDL_STUB_SKIP file=$synth_file reason=$stub_err"
  } else {
    incr generated_vhdl_stub_count
  }
}
close $stub_fh
set old_stub_refs [get_files -quiet $generated_stub_file]
if {[llength $old_stub_refs] > 0} {
  puts "DIRECT_8LANE_CANDIDATE_REMOVE_OLD_STUB_REFS=$old_stub_refs"
  remove_files $old_stub_refs
}
if {$generated_verilog_stub_count > 0 || $generated_vhdl_stub_count > 0} {
  read_verilog $generated_stub_file
}
puts "DIRECT_8LANE_CANDIDATE_GENERATED_VERILOG_STUBS=$generated_verilog_stub_count"
puts "DIRECT_8LANE_CANDIDATE_GENERATED_VHDL_STUBS=$generated_vhdl_stub_count"

set part_name [get_property PART [current_project]]
set constrset_name [get_property constrset [current_run -synthesis]]
if {$constrset_name eq ""} {
  set constrset_name constrs_1
}

puts "DIRECT_8LANE_CANDIDATE_SYNTH top=design_shiboqi_wrapper part=$part_name constrset=$constrset_name threads=$max_threads"
synth_design -top design_shiboqi_wrapper -part $part_name -constrset $constrset_name
read_xdc $candidate_xdc
puts "DIRECT_8LANE_CANDIDATE_XDC_READ=$candidate_xdc"

set ip_dcp_files [list]
if {[file exists $bd_gen_dir]} {
  set ip_dcp_files [glob -nocomplain -directory $bd_gen_dir -types f */*.dcp]
}
set bound_dcp_count 0
foreach dcp_file [lsort -unique $ip_dcp_files] {
  set ref_name [file rootname [file tail $dcp_file]]
  foreach cell [get_cells -quiet -hier -filter "REF_NAME == $ref_name"] {
    if {[catch {read_checkpoint -quiet -cell $cell $dcp_file} msg]} {
      puts "DIRECT_8LANE_CANDIDATE_DCP_SKIP cell=$cell ref=$ref_name reason=$msg"
    } else {
      incr bound_dcp_count
      puts "DIRECT_8LANE_CANDIDATE_DCP_BOUND cell=$cell ref=$ref_name"
    }
  }
}
puts "DIRECT_8LANE_CANDIDATE_DCP_BOUND_COUNT=$bound_dcp_count"

write_checkpoint -force [file join $out_dir design_shiboqi_wrapper_synth.dcp]
report_utilization -file [file join $out_dir utilization_synth.rpt]

puts "DIRECT_8LANE_CANDIDATE_IMPL"
opt_design
write_checkpoint -force [file join $out_dir design_shiboqi_wrapper_opt.dcp]
place_design
write_checkpoint -force [file join $out_dir design_shiboqi_wrapper_placed.dcp]
route_design
write_checkpoint -force [file join $out_dir design_shiboqi_wrapper_routed.dcp]

report_drc -file [file join $out_dir drc_routed.rpt]
report_timing_summary -file [file join $out_dir timing_summary_post_route.rpt]
report_utilization -file [file join $out_dir utilization_post_route.rpt]
report_route_status -file [file join $out_dir route_status_post_route.rpt]
report_io -file [file join $out_dir io_post_route.rpt]

set run_bit [file join $out_dir design_shiboqi_wrapper_8lane_candidate.bit]
write_bitstream -force $run_bit
if {[catch {write_debug_probes -force [file join $out_dir design_shiboqi_wrapper_8lane_candidate.ltx]} ltx_err]} {
  puts "DIRECT_8LANE_CANDIDATE_DEBUG_PROBES_SKIPPED=$ltx_err"
}

puts "DIRECT_8LANE_CANDIDATE_BITSTREAM_FILE=$run_bit"
puts "DIRECT_8LANE_CANDIDATE_BUILD_DONE"
close_project
