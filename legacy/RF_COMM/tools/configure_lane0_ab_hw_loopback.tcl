set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]

set cnt_chip_max 7
if {[info exists ::env(IR_CNT_CHIP_MAX)] && $::env(IR_CNT_CHIP_MAX) ne ""} {
  set cnt_chip_max $::env(IR_CNT_CHIP_MAX)
}
puts "HWLOOP: CNT_CHIP_MAX=$cnt_chip_max"

set cnt_preamble 64
if {[info exists ::env(IR_CNT_PREAMBLE)] && $::env(IR_CNT_PREAMBLE) ne ""} {
  set cnt_preamble $::env(IR_CNT_PREAMBLE)
}
puts "HWLOOP: CNT_PREAMBLE=$cnt_preamble"

set rx_data_phase_delay_cycles 0
if {[info exists ::env(IR_RX_DATA_PHASE_DELAY_CYCLES)] && $::env(IR_RX_DATA_PHASE_DELAY_CYCLES) ne ""} {
  set rx_data_phase_delay_cycles $::env(IR_RX_DATA_PHASE_DELAY_CYCLES)
}
puts "HWLOOP: RX_DATA_PHASE_DELAY_CYCLES=$rx_data_phase_delay_cycles"

set rx_detect_start_cycles [expr {$cnt_chip_max >= 15 ? 0 : ($cnt_chip_max >= 7 ? 3 : 0)}]
if {[info exists ::env(IR_RX_DETECT_START_CYCLES)] && $::env(IR_RX_DETECT_START_CYCLES) ne ""} {
  set rx_detect_start_cycles $::env(IR_RX_DETECT_START_CYCLES)
}
set rx_detect_end_cycles [expr {$cnt_chip_max >= 15 ? 10 : $cnt_chip_max}]
if {[info exists ::env(IR_RX_DETECT_END_CYCLES)] && $::env(IR_RX_DETECT_END_CYCLES) ne ""} {
  set rx_detect_end_cycles $::env(IR_RX_DETECT_END_CYCLES)
}
puts "HWLOOP: RX_DETECT_WINDOW=$rx_detect_start_cycles..$rx_detect_end_cycles"

set rx_preamble_realign_edge 1
if {[info exists ::env(IR_RX_PREAMBLE_REALIGN_EDGE)] && $::env(IR_RX_PREAMBLE_REALIGN_EDGE) ne ""} {
  set rx_preamble_realign_edge $::env(IR_RX_PREAMBLE_REALIGN_EDGE)
}
puts "HWLOOP: RX_PREAMBLE_REALIGN_EDGE=$rx_preamble_realign_edge"

set b_rx_detect_start_cycles $rx_detect_start_cycles
if {[info exists ::env(IR_B_RX_DETECT_START_CYCLES)] && $::env(IR_B_RX_DETECT_START_CYCLES) ne ""} {
  set b_rx_detect_start_cycles $::env(IR_B_RX_DETECT_START_CYCLES)
}
set b_rx_detect_end_cycles $rx_detect_end_cycles
if {[info exists ::env(IR_B_RX_DETECT_END_CYCLES)] && $::env(IR_B_RX_DETECT_END_CYCLES) ne ""} {
  set b_rx_detect_end_cycles $::env(IR_B_RX_DETECT_END_CYCLES)
}
set b_rx_preamble_realign_edge $rx_preamble_realign_edge
if {[info exists ::env(IR_B_RX_PREAMBLE_REALIGN_EDGE)] && $::env(IR_B_RX_PREAMBLE_REALIGN_EDGE) ne ""} {
  set b_rx_preamble_realign_edge $::env(IR_B_RX_PREAMBLE_REALIGN_EDGE)
}
puts "HWLOOP: B_RX_DETECT_WINDOW=$b_rx_detect_start_cycles..$b_rx_detect_end_cycles"
puts "HWLOOP: B_RX_PREAMBLE_REALIGN_EDGE=$b_rx_preamble_realign_edge"

set b_mode loopback
if {[info exists ::env(IR_B_MODE)] && $::env(IR_B_MODE) ne ""} {
  set b_mode $::env(IR_B_MODE)
}

set max_hw_lane_count 8
set lane_count 1
if {[info exists ::env(IR_LANE_COUNT)] && $::env(IR_LANE_COUNT) ne ""} {
  set lane_count $::env(IR_LANE_COUNT)
}
if {$lane_count < 1 || $lane_count > $max_hw_lane_count} {
  error "IR_LANE_COUNT must be in 1..$max_hw_lane_count, got $lane_count"
}
puts "HWLOOP: IR_LANE_COUNT=$lane_count"

set parallel_2lane_mode 0
if {[info exists ::env(IR_PARALLEL_2LANE_MODE)] && $::env(IR_PARALLEL_2LANE_MODE) ne ""} {
  set parallel_2lane_mode $::env(IR_PARALLEL_2LANE_MODE)
}
if {$parallel_2lane_mode != 0} {
  if {$lane_count != 2} {
    error "IR_PARALLEL_2LANE_MODE requires IR_LANE_COUNT=2"
  }
  set b_mode stream_bidir
}
puts "HWLOOP: IR_B_MODE=$b_mode"
puts "HWLOOP: IR_PARALLEL_2LANE_MODE=$parallel_2lane_mode"
set lane_mask_all [expr {(1 << $lane_count) - 1}]
set b_ack_lane_mask $lane_mask_all
if {[info exists ::env(IR_B_ACK_LANE_MASK)] && $::env(IR_B_ACK_LANE_MASK) ne ""} {
  set b_ack_lane_mask [expr {$::env(IR_B_ACK_LANE_MASK)}]
}
puts "HWLOOP: IR_B_ACK_LANE_MASK=$b_ack_lane_mask"
set b_tx_lane_mask $lane_mask_all
if {[info exists ::env(IR_B_TX_LANE_MASK)] && $::env(IR_B_TX_LANE_MASK) ne ""} {
  set b_tx_lane_mask [expr {$::env(IR_B_TX_LANE_MASK)}]
}
set b_rx_lane_mask $lane_mask_all
if {[info exists ::env(IR_B_RX_LANE_MASK)] && $::env(IR_B_RX_LANE_MASK) ne ""} {
  set b_rx_lane_mask [expr {$::env(IR_B_RX_LANE_MASK)}]
}
set b_expected_a_lane_mask $lane_mask_all
if {[info exists ::env(IR_B_EXPECTED_A_LANE_MASK)] && $::env(IR_B_EXPECTED_A_LANE_MASK) ne ""} {
  set b_expected_a_lane_mask [expr {$::env(IR_B_EXPECTED_A_LANE_MASK)}]
}
puts "HWLOOP: IR_B_TX_LANE_MASK=$b_tx_lane_mask IR_B_RX_LANE_MASK=$b_rx_lane_mask IR_B_EXPECTED_A_LANE_MASK=$b_expected_a_lane_mask"
set b_session_id [format "0x%04X" [expr {0x2200 + $lane_mask_all}]]
if {[info exists ::env(IR_B_SESSION_ID)] && $::env(IR_B_SESSION_ID) ne ""} {
  set b_session_id $::env(IR_B_SESSION_ID)
}
puts "HWLOOP: B_SESSION_ID=$b_session_id"

set stream_full_mode 0
if {[info exists ::env(IR_STREAM_FULL_MODE)] && $::env(IR_STREAM_FULL_MODE) ne ""} {
  set stream_full_mode $::env(IR_STREAM_FULL_MODE)
}
set stream_tx_require_ack 1
if {[info exists ::env(IR_STREAM_TX_REQUIRE_ACK)] && $::env(IR_STREAM_TX_REQUIRE_ACK) ne ""} {
  set stream_tx_require_ack $::env(IR_STREAM_TX_REQUIRE_ACK)
}
set stream_node_id 0
if {[info exists ::env(IR_STREAM_NODE_ID)] && $::env(IR_STREAM_NODE_ID) ne ""} {
  set stream_node_id $::env(IR_STREAM_NODE_ID)
}
set stream_phy_dbg_select 0
if {[info exists ::env(IR_STREAM_PHY_DBG_SELECT)] && $::env(IR_STREAM_PHY_DBG_SELECT) ne ""} {
  set stream_phy_dbg_select $::env(IR_STREAM_PHY_DBG_SELECT)
}
set force_sd_shutdown 0
if {[info exists ::env(IR_FORCE_SD_SHUTDOWN)] && $::env(IR_FORCE_SD_SHUTDOWN) ne ""} {
  set force_sd_shutdown $::env(IR_FORCE_SD_SHUTDOWN)
}
if {$b_mode eq "stream_bidir"} {
  set stream_full_mode 1
  set stream_node_id 0
}
if {$stream_node_id < 0 || $stream_node_id > 1} {
  error "IR_STREAM_NODE_ID must be 0 or 1, got $stream_node_id"
}
if {$stream_tx_require_ack < 0 || $stream_tx_require_ack > 1} {
  error "IR_STREAM_TX_REQUIRE_ACK must be 0 or 1, got $stream_tx_require_ack"
}
if {$stream_tx_require_ack == 0 && $parallel_2lane_mode != 0} {
  error "IR_STREAM_TX_REQUIRE_ACK=0 is supported only by the legacy stream path; set IR_PARALLEL_2LANE_MODE=0"
}
if {$stream_phy_dbg_select < 0 || $stream_phy_dbg_select > 6} {
  error "IR_STREAM_PHY_DBG_SELECT must be 0..6, got $stream_phy_dbg_select"
}
if {$force_sd_shutdown < 0 || $force_sd_shutdown > 1} {
  error "IR_FORCE_SD_SHUTDOWN must be 0 or 1, got $force_sd_shutdown"
}
puts "HWLOOP: STREAM_FULL_MODE=$stream_full_mode STREAM_TX_REQUIRE_ACK=$stream_tx_require_ack STREAM_NODE_ID=$stream_node_id STREAM_PHY_DBG_SELECT=$stream_phy_dbg_select FORCE_SD_SHUTDOWN=$force_sd_shutdown"

set fragment_bytes 16
if {$b_mode eq "sink"} {
  set fragment_bytes 255
} elseif {$b_mode eq "stream_bidir"} {
  set fragment_bytes 255
} elseif {$stream_full_mode != 0} {
  set fragment_bytes 64
}
if {[info exists ::env(IR_FRAGMENT_BYTES)] && $::env(IR_FRAGMENT_BYTES) ne ""} {
  set fragment_bytes $::env(IR_FRAGMENT_BYTES)
}
set max_packet_bytes 256
if {$b_mode eq "sink" || $b_mode eq "stream_bidir"} {
  set max_packet_bytes 255
}
if {[info exists ::env(IR_MAX_PACKET_BYTES)] && $::env(IR_MAX_PACKET_BYTES) ne ""} {
  set max_packet_bytes $::env(IR_MAX_PACKET_BYTES)
}
set max_frags [expr {int(ceil(double($max_packet_bytes) / double($fragment_bytes)))}]
set max_frame_bytes [expr {14 + $fragment_bytes}]
set max_retry [expr {$lane_count > 4 ? ($lane_count * $max_frags) : 4}]
if {[info exists ::env(IR_MAX_RETRY)] && $::env(IR_MAX_RETRY) ne ""} {
  set max_retry $::env(IR_MAX_RETRY)
}
set tx_async_fifo_depth 1024
if {[info exists ::env(IR_TX_ASYNC_FIFO_DEPTH)] && $::env(IR_TX_ASYNC_FIFO_DEPTH) ne ""} {
  set tx_async_fifo_depth $::env(IR_TX_ASYNC_FIFO_DEPTH)
}
set rx_async_fifo_depth 1024
if {[info exists ::env(IR_RX_ASYNC_FIFO_DEPTH)] && $::env(IR_RX_ASYNC_FIFO_DEPTH) ne ""} {
  set rx_async_fifo_depth $::env(IR_RX_ASYNC_FIFO_DEPTH)
}
set frag_timeout_cycles 50000
if {[info exists ::env(IR_FRAG_TIMEOUT_CYCLES)] && $::env(IR_FRAG_TIMEOUT_CYCLES) ne ""} {
  set frag_timeout_cycles $::env(IR_FRAG_TIMEOUT_CYCLES)
}
set guard_cycles 8192
if {$b_mode eq "sink"} {
  set guard_cycles 4096
} elseif {$b_mode eq "stream_bidir"} {
  set guard_cycles 4096
}
if {[info exists ::env(IR_GUARD_CYCLES)] && $::env(IR_GUARD_CYCLES) ne ""} {
  set guard_cycles $::env(IR_GUARD_CYCLES)
}
set b_backoff_slot_cycles 1024
if {$b_mode eq "stream_bidir"} {
  set b_backoff_slot_cycles 100000
}
if {[info exists ::env(IR_B_BACKOFF_SLOT_CYCLES)] && $::env(IR_B_BACKOFF_SLOT_CYCLES) ne ""} {
  set b_backoff_slot_cycles $::env(IR_B_BACKOFF_SLOT_CYCLES)
}
set b2a_enable 1
if {[info exists ::env(IR_B2A_ENABLE)] && $::env(IR_B2A_ENABLE) ne ""} {
  set b2a_enable $::env(IR_B2A_ENABLE)
}
set b2a_free_run 0
if {[info exists ::env(IR_B2A_FREE_RUN)] && $::env(IR_B2A_FREE_RUN) ne ""} {
  set b2a_free_run $::env(IR_B2A_FREE_RUN)
}
set b2a_echo_enable 0
if {[info exists ::env(IR_B2A_ECHO_ENABLE)] && $::env(IR_B2A_ECHO_ENABLE) ne ""} {
  set b2a_echo_enable $::env(IR_B2A_ECHO_ENABLE)
}
set b_start_idle_cycles 100000
if {[info exists ::env(IR_B_START_IDLE_CYCLES)] && $::env(IR_B_START_IDLE_CYCLES) ne ""} {
  set b_start_idle_cycles $::env(IR_B_START_IDLE_CYCLES)
}
set b_recovery_reset_cycles 2048
if {[info exists ::env(IR_B_RECOVERY_RESET_CYCLES)] && $::env(IR_B_RECOVERY_RESET_CYCLES) ne ""} {
  set b_recovery_reset_cycles $::env(IR_B_RECOVERY_RESET_CYCLES)
}
set b_debug_select_rx_status 0
if {[info exists ::env(IR_B_DEBUG_SELECT_RX_STATUS)] && $::env(IR_B_DEBUG_SELECT_RX_STATUS) ne ""} {
  set b_debug_select_rx_status $::env(IR_B_DEBUG_SELECT_RX_STATUS)
}
set b_tx_gap_cycles 0
if {[info exists ::env(IR_B_TX_GAP_CYCLES)] && $::env(IR_B_TX_GAP_CYCLES) ne ""} {
  set b_tx_gap_cycles $::env(IR_B_TX_GAP_CYCLES)
}
set tx_only_ack_mode 0
if {$b_mode eq "sink"} {
  set tx_only_ack_mode 1
}
if {[info exists ::env(IR_TX_ONLY_ACK_MODE)] && $::env(IR_TX_ONLY_ACK_MODE) ne ""} {
  set tx_only_ack_mode $::env(IR_TX_ONLY_ACK_MODE)
}
if {$tx_only_ack_mode != 0 && $stream_full_mode != 0} {
  error "TX_ONLY_ACK_MODE and STREAM_FULL_MODE are mutually exclusive"
}
if {$stream_full_mode != 0 && $b_mode ne "external" && $b_mode ne "stream_bidir"} {
  error "STREAM_FULL_MODE requires IR_B_MODE=external or IR_B_MODE=stream_bidir"
}
if {$b_mode ne "external" && $b_mode ne "stream_bidir" && $b_mode ne "fdx_partition" && $lane_count != 1} {
  error "Internal loopback/sink B endpoint supports only IR_LANE_COUNT=1"
}
if {$b_mode eq "fdx_partition" && $lane_count != 2} {
  error "IR_B_MODE=fdx_partition requires IR_LANE_COUNT=2"
}
puts "HWLOOP: MAX_PACKET_BYTES=$max_packet_bytes FRAGMENT_BYTES=$fragment_bytes MAX_FRAGS=$max_frags MAX_FRAME_BYTES=$max_frame_bytes GUARD_CYCLES=$guard_cycles B_BACKOFF_SLOT_CYCLES=$b_backoff_slot_cycles B2A_ENABLE=$b2a_enable B2A_FREE_RUN=$b2a_free_run B2A_ECHO_ENABLE=$b2a_echo_enable B_START_IDLE_CYCLES=$b_start_idle_cycles B_RECOVERY_RESET_CYCLES=$b_recovery_reset_cycles B_DEBUG_SELECT_RX_STATUS=$b_debug_select_rx_status B_TX_GAP_CYCLES=$b_tx_gap_cycles TX_ONLY_ACK_MODE=$tx_only_ack_mode STREAM_FULL_MODE=$stream_full_mode STREAM_TX_REQUIRE_ACK=$stream_tx_require_ack PARALLEL_2LANE_MODE=$parallel_2lane_mode"
puts "HWLOOP: MAX_RETRY=$max_retry FRAG_TIMEOUT_CYCLES=$frag_timeout_cycles TX_ASYNC_FIFO_DEPTH=$tx_async_fifo_depth RX_ASYNC_FIFO_DEPTH=$rx_async_fifo_depth"

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

set bd_mref_dir [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.gen sources_1 bd mref]
foreach ref_name {ir_stream_bidir_b0_bd ir_stream_bidir_vec_bd ir_fdx_partition_b_bd} {
  set ref_cache [file join $bd_mref_dir $ref_name]
  if {[file exists $ref_cache]} {
    puts "HWLOOP: clear stale module_ref cache $ref_cache"
    file delete -force $ref_cache
  }
}

set max_threads 16
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}
set_param general.maxThreads $max_threads
open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild
set ir_array_ips [get_ips -quiet *ir_array_top_axi*]
if {[llength $ir_array_ips] > 0} {
  puts "HWLOOP: upgrade IR array IP instances: $ir_array_ips"
  upgrade_ip $ir_array_ips
}

set rtl_dir [file join $ip_repo src]
foreach f [list [file join $rtl_dir ir_stream_bidir_vec_bd.sv]] {
  set old_refs [get_files -quiet $f]
  if {[llength $old_refs] > 0} {
    puts "HWLOOP: remove obsolete RTL source $f"
    remove_files $old_refs
  }
}
set rtl_files [list \
  [file join $rtl_dir ir_protocol_pkg.sv] \
  [file join $rtl_dir crc32_gen.sv] \
  [file join $rtl_dir ir_tx_4ppm_frame.sv] \
  [file join $rtl_dir ir_rx_4ppm_frame.sv] \
  [file join $rtl_dir ir_lane_frame_source.sv] \
  [file join $rtl_dir ir_lane_frame_sink.sv] \
  [file join $rtl_dir ir_comm_lane.sv] \
  [file join $rtl_dir ir_array_tx_mgr.sv] \
  [file join $rtl_dir ir_array_rx_mgr.sv] \
  [file join $rtl_dir ir_array_top.sv] \
  [file join $rtl_dir ir_txonly_ack_axi.sv] \
  [file join $rtl_dir ir_stream_array_top.sv] \
  [file join $rtl_dir ir_stream_parallel_2lane_top.sv] \
  [file join $rtl_dir ir_stream_array_top_axi.sv] \
  [file join $rtl_dir ir_stream_bidir_b0_bd.sv] \
  [file join $rtl_dir ir_stream_bidir_b0_bd.v] \
  [file join $rtl_dir ir_stream_bidir_vec_bd.v] \
  [file join $rtl_dir ir_fdx_partition_b_bd.sv] \
  [file join $rtl_dir ir_fdx_partition_b_bd.v] \
  [file join $rtl_dir ir_sink_b0_bd.v] \
  [file join $rtl_dir ir_loopback_b0_bd.v] \
  [file join $rtl_dir ir_loopback_b0_dbg_bd.v] \
  [file join $rtl_dir ir_loopback_b0_rxdbg_bd.v] \
  [file join $rtl_dir ir_loopback_b0_rxfix_bd.v] \
  [file join $rtl_dir ir_loopback_b0_cntdbg_bd.v] \
  [file join $rtl_dir ir_loopback_b0_guard_bd.v] \
  [file join $rtl_dir ir_loopback_b0_txguard_bd.v] \
  [file join $rtl_dir ir_loopback_b0_completeack_bd.v] \
]

foreach f $rtl_files {
  if {![file exists $f]} {
    error "Missing loopback RTL source: $f"
  }
  if {[llength [get_files -quiet $f]] == 0} {
    puts "HWLOOP: add RTL source $f"
    add_files -norecurse -fileset sources_1 $f
  }
}
update_compile_order -fileset sources_1

set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
if {$bd_file eq ""} {
  error "Missing design_shiboqi.bd in project"
}

set vivado_ipi_dir ""
set vivado_exec_dir [file dirname [file normalize [info nameofexecutable]]]
foreach vivado_root_candidate [list \
  [file normalize [file join $vivado_exec_dir ..]] \
  [file normalize [file join $vivado_exec_dir .. ..]] \
  [file normalize [file join $vivado_exec_dir .. .. ..]] \
] {
  set candidate_ipi_dir [file join $vivado_root_candidate scripts ipintegrator]
  if {[file exists [file join $candidate_ipi_dir utils.tcl]]} {
    set vivado_ipi_dir $candidate_ipi_dir
    break
  }
}
set bd_open_cwd [pwd]
if {$vivado_ipi_dir ne ""} {
  puts "HWLOOP: open_bd_design cwd workaround $vivado_ipi_dir"
  cd $vivado_ipi_dir
  if {[file exists [file join $vivado_ipi_dir init.tcl]]} {
    if {[catch {source -notrace [file join $vivado_ipi_dir init.tcl]} init_err]} {
      puts "HWLOOP: ipintegrator init pre-source warning: $init_err"
    }
  }
}
set bd_open_rc [catch {open_bd_design $bd_file} bd_open_err bd_open_opts]
cd $bd_open_cwd
if {$bd_open_rc != 0 && $vivado_ipi_dir ne ""} {
  puts "HWLOOP: open_bd_design retry after init error: $bd_open_err"
  cd $vivado_ipi_dir
  set bd_open_rc [catch {open_bd_design $bd_file} bd_open_err bd_open_opts]
  cd $bd_open_cwd
}
if {$bd_open_rc != 0} {
  return -options $bd_open_opts $bd_open_err
}

proc recreate_tfdu_vector_port {name dir pin lane_count} {
  set old_port [get_bd_ports -quiet $name]
  if {[llength $old_port] > 0} {
    puts "HWLOOP: delete old BD port $name"
    delete_bd_objs $old_port
  }

  set pin_obj [get_bd_pins -quiet $pin]
  set old_nets [get_bd_nets -quiet -of_objects $pin_obj]
  foreach old_net $old_nets {
    puts "HWLOOP: delete old BD net [get_property NAME $old_net] from $pin"
    delete_bd_objs $old_net
  }

  set hi [expr {$lane_count - 1}]
  puts "HWLOOP: create TFDU BD port $name $dir \[$hi:0\]"
  set new_port [create_bd_port -dir $dir -from $hi -to 0 $name]
  connect_bd_net $new_port [get_bd_pins $pin]
}

set a [get_bd_cells -quiet ir_array_top_axi_0]
if {[llength $a] == 0} {
  error "Missing BD cell ir_array_top_axi_0"
}

puts "HWLOOP: set PS-controlled A endpoint LANE_COUNT=$lane_count CNT_CHIP_MAX=$cnt_chip_max CNT_PREAMBLE=$cnt_preamble"
set a_cfg [list \
  CONFIG.LANE_COUNT $lane_count \
  CONFIG.MAX_PACKET_BYTES $max_packet_bytes \
  CONFIG.MAX_RETRY $max_retry \
  CONFIG.CNT_CHIP_MAX $cnt_chip_max \
  CONFIG.CNT_PREAMBLE $cnt_preamble \
  CONFIG.FRAGMENT_BYTES $fragment_bytes \
  CONFIG.FRAG_TIMEOUT_CYCLES $frag_timeout_cycles \
  CONFIG.MAX_FRAGS $max_frags \
  CONFIG.MAX_FRAME_BYTES $max_frame_bytes \
  CONFIG.TX_POST_ACK_GUARD_CYCLES $guard_cycles \
  CONFIG.RX_TO_TX_GUARD_CYCLES $guard_cycles \
  CONFIG.TX_ONLY_ACK_MODE $tx_only_ack_mode \
  CONFIG.STREAM_FULL_MODE $stream_full_mode \
  CONFIG.STREAM_NODE_ID $stream_node_id \
]
set a_props [list_property $a]
if {[lsearch -exact $a_props CONFIG.RX_DATA_PHASE_DELAY_CYCLES] >= 0} {
  lappend a_cfg CONFIG.RX_DATA_PHASE_DELAY_CYCLES $rx_data_phase_delay_cycles
}
if {[lsearch -exact $a_props CONFIG.RX_DETECT_START_CYCLES] >= 0} {
  lappend a_cfg CONFIG.RX_DETECT_START_CYCLES $rx_detect_start_cycles
}
if {[lsearch -exact $a_props CONFIG.RX_DETECT_END_CYCLES] >= 0} {
  lappend a_cfg CONFIG.RX_DETECT_END_CYCLES $rx_detect_end_cycles
}
if {[lsearch -exact $a_props CONFIG.RX_PREAMBLE_REALIGN_EDGE] >= 0} {
  lappend a_cfg CONFIG.RX_PREAMBLE_REALIGN_EDGE $rx_preamble_realign_edge
}
if {[lsearch -exact $a_props CONFIG.PARALLEL_2LANE_MODE] >= 0} {
  lappend a_cfg CONFIG.PARALLEL_2LANE_MODE $parallel_2lane_mode
}
if {[lsearch -exact $a_props CONFIG.STREAM_TX_REQUIRE_ACK] >= 0} {
  lappend a_cfg CONFIG.STREAM_TX_REQUIRE_ACK $stream_tx_require_ack
} elseif {$stream_tx_require_ack != 1} {
  error "A endpoint IP does not expose CONFIG.STREAM_TX_REQUIRE_ACK; refresh/repackage ir_array_top_axi before A2B RX-only build"
}
if {[lsearch -exact $a_props CONFIG.STREAM_PHY_DBG_SELECT] >= 0} {
  lappend a_cfg CONFIG.STREAM_PHY_DBG_SELECT $stream_phy_dbg_select
} elseif {$stream_phy_dbg_select != 0} {
  error "A endpoint IP does not expose CONFIG.STREAM_PHY_DBG_SELECT; refresh/repackage ir_array_top_axi before diagnostic build"
}
if {[lsearch -exact $a_props CONFIG.FORCE_SD_SHUTDOWN] >= 0} {
  lappend a_cfg CONFIG.FORCE_SD_SHUTDOWN $force_sd_shutdown
} elseif {$force_sd_shutdown != 0} {
  error "A endpoint IP does not expose CONFIG.FORCE_SD_SHUTDOWN; refresh/repackage ir_array_top_axi before P7A-04 build"
}
if {[lsearch -exact $a_props CONFIG.TX_ASYNC_FIFO_DEPTH] >= 0} {
  lappend a_cfg CONFIG.TX_ASYNC_FIFO_DEPTH $tx_async_fifo_depth
}
if {[lsearch -exact $a_props CONFIG.RX_ASYNC_FIFO_DEPTH] >= 0} {
  lappend a_cfg CONFIG.RX_ASYNC_FIFO_DEPTH $rx_async_fifo_depth
}
set a_cfg_rc [catch {set_property -dict $a_cfg $a} a_cfg_err a_cfg_opts]
if {$a_cfg_rc != 0} {
  puts "HWLOOP: A endpoint set_property retry after error: $a_cfg_err"
  update_ip_catalog -rebuild
  set a [get_bd_cells -quiet ir_array_top_axi_0]
  set a_cfg_rc [catch {set_property -dict $a_cfg $a} a_cfg_err a_cfg_opts]
}
if {$a_cfg_rc != 0} {
  return -options $a_cfg_opts $a_cfg_err
}
puts "HWLOOP: A endpoint applied config entries=$a_cfg"
recreate_tfdu_vector_port ir_rx_in_0 I ir_array_top_axi_0/ir_rx_in $lane_count
recreate_tfdu_vector_port ir_sd_0 O ir_array_top_axi_0/ir_sd $lane_count
recreate_tfdu_vector_port ir_mode_out_0 O ir_array_top_axi_0/ir_mode_out $lane_count
recreate_tfdu_vector_port ir_tx_out_0 O ir_array_top_axi_0/ir_tx_out $lane_count

proc delete_bd_cell_if_exists {name} {
  set obj [get_bd_cells -quiet $name]
  if {[llength $obj] > 0} {
    puts "HWLOOP: delete old BD cell $name"
    delete_bd_objs $obj
  }
}

proc delete_bd_port_if_exists {name} {
  set obj [get_bd_ports -quiet $name]
  if {[llength $obj] > 0} {
    puts "HWLOOP: delete old BD port $name"
    delete_bd_objs $obj
  }
}

proc delete_bd_net_if_exists {name} {
  set obj [get_bd_nets -quiet $name]
  if {[llength $obj] > 0} {
    puts "HWLOOP: delete stale BD net $name"
    delete_bd_objs $obj
  }
}

delete_bd_cell_if_exists system_ila_0
delete_bd_cell_if_exists ila_lane0_phy
delete_bd_cell_if_exists ila_2lane_phy

foreach name {
  ir_loopback_b0
  not_a_to_b
  not_b_to_a
  const_loop_enable_b0
  const_loop_session_b0
  const_loop_lane_mask_b0
  const_ext_phy_dbg0
} {
  delete_bd_cell_if_exists $name
}

foreach name {
  loop_tx_b0
  loop_rx_b0
  loop_sd_b0
  loop_mode_b0
} {
  delete_bd_port_if_exists $name
}

foreach name {
  ir_loopback_b0_ir_mode_out
  ir_loopback_b0_ir_mode_out1
  ir_loopback_b0_ir_sd
  ir_loopback_b0_ir_sd1
  ir_loopback_b0_ir_tx_out
  ir_loopback_b0_ir_tx_out1
  loop_rx_b0_1
  loop_rx_b0_2
} {
  delete_bd_net_if_exists $name
}

proc delete_nets_on_pin_if_exists {pin_name} {
  set pin_obj [get_bd_pins -quiet $pin_name]
  if {[llength $pin_obj] == 0} {
    return
  }
  foreach old_net [get_bd_nets -quiet -of_objects $pin_obj] {
    puts "HWLOOP: delete old BD net [get_property NAME $old_net] from $pin_name"
    delete_bd_objs $old_net
  }
}

proc sync_imported_wrapper {repo_root} {
  set generated_wrapper [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.gen sources_1 bd design_shiboqi hdl design_shiboqi_wrapper.v]
  set imported_wrapper [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.srcs sources_1 imports hdl design_shiboqi_wrapper.v]
  if {[file exists $generated_wrapper] && [file exists $imported_wrapper]} {
    puts "HWLOOP: sync generated wrapper to imported top wrapper"
    file copy -force $generated_wrapper $imported_wrapper
  }
}

proc force_xci_model_parameter {bd_file ip_name param_name param_value} {
  set bd_dir [file dirname $bd_file]
  set xci_file [file join $bd_dir ip $ip_name ${ip_name}.xci]
  if {![file exists $xci_file]} {
    puts "HWLOOP: XCI model parameter patch skipped; missing $xci_file"
    return
  }

  set fh [open $xci_file r]
  set text [read $fh]
  close $fh

  set pattern [format {("%s": \[ \{ "value": ")[^"]+(", "resolve_type": "generated")} $param_name]
  set replacement "\\1$param_value\\2"
  set changed [regsub -all $pattern $text $replacement new_text]
  if {$changed == 0} {
    puts "HWLOOP: XCI model parameter patch warning; $param_name generated entry not found in $xci_file"
    return
  }

  set fh [open $xci_file w]
  puts -nonewline $fh $new_text
  close $fh
  puts "HWLOOP: XCI model parameter patched $param_name=$param_value in $xci_file"
}

delete_nets_on_pin_if_exists ir_array_top_axi_0/ext_phy_dbg

if {$b_mode eq "external"} {
  puts "HWLOOP: external endpoint mode; skip internal B endpoint and tie ext_phy_dbg to zero"
  set const_dbg [create_bd_cell -type ip -vlnv xilinx.com:ip:xlconstant:* const_ext_phy_dbg0]
  set_property -dict [list CONFIG.CONST_WIDTH 32 CONFIG.CONST_VAL 0] $const_dbg
  connect_bd_net [get_bd_pins const_ext_phy_dbg0/dout] [get_bd_pins ir_array_top_axi_0/ext_phy_dbg]
  validate_bd_design
  save_bd_design
  force_xci_model_parameter $bd_file design_shiboqi_ir_array_top_axi_0_0 STREAM_PHY_DBG_SELECT $stream_phy_dbg_select
  force_xci_model_parameter $bd_file design_shiboqi_ir_array_top_axi_0_0 FORCE_SD_SHUTDOWN $force_sd_shutdown
  reset_target all $bd_file
  generate_target all $bd_file
  export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
  update_compile_order -fileset sources_1

  set wrapper_files [make_wrapper -files $bd_file -top -force]
  if {[llength $wrapper_files] > 0} {
    foreach wrapper_file $wrapper_files {
      if {[llength [get_files -quiet $wrapper_file]] == 0} {
        add_files -norecurse $wrapper_file
      }
    }
  }

  set_property top design_shiboqi_wrapper [current_fileset]
  sync_imported_wrapper $repo_root
  update_compile_order -fileset sources_1
  close_project
  puts "CONFIGURE_IR_EXTERNAL_ENDPOINT_DONE"
  return
}

if {$b_mode eq "sink"} {
  set b_ref ir_sink_b0_bd
  puts "HWLOOP: create lane0-B sink-only half-duplex partner endpoint"
} elseif {$b_mode eq "stream_bidir"} {
  if {$lane_count == 1} {
    set b_ref ir_stream_bidir_b0_bd
    puts "HWLOOP: create lane0-B non-degenerate stream bidirectional partner endpoint"
  } else {
    set b_ref ir_stream_bidir_vec_bd
    puts "HWLOOP: create vector B non-degenerate stream bidirectional partner endpoint"
  }
} elseif {$b_mode eq "fdx_partition"} {
  set b_ref ir_fdx_partition_b_bd
  puts "HWLOOP: create 1+1 lane full-duplex partition B partner endpoint"
} elseif {$b_mode eq "loopback"} {
  set b_ref ir_loopback_b0_completeack_bd
  puts "HWLOOP: create lane0-B loopback partner endpoint"
} else {
  error "Unsupported IR_B_MODE=$b_mode (expected loopback, sink, stream_bidir, fdx_partition, or external)"
}

set b [create_bd_cell -type module -reference $b_ref ir_loopback_b0]
if {[llength [info commands update_module_reference]] > 0} {
  if {[catch {update_module_reference $b} update_err]} {
    puts "HWLOOP: update_module_reference warning before B config: $update_err"
  }
}
if {$b_mode eq "sink" || $b_mode eq "stream_bidir" || $b_mode eq "fdx_partition"} {
  puts "HWLOOP: set B endpoint SESSION_ID=$b_session_id CNT_PREAMBLE=$cnt_preamble GUARD_CYCLES=$guard_cycles"
  set b_props [list_property $b]
  set b_cfg [list]
  if {[lsearch -exact $b_props CONFIG.LANE_COUNT] >= 0} {
    lappend b_cfg CONFIG.LANE_COUNT $lane_count
  }
  if {[lsearch -exact $b_props CONFIG.B_SESSION_ID] >= 0} {
    lappend b_cfg CONFIG.B_SESSION_ID $b_session_id
  }
  if {[lsearch -exact $b_props CONFIG.B_CNT_CHIP_MAX] >= 0} {
    lappend b_cfg CONFIG.B_CNT_CHIP_MAX $cnt_chip_max
  }
  if {[lsearch -exact $b_props CONFIG.B_CNT_PREAMBLE] >= 0} {
    lappend b_cfg CONFIG.B_CNT_PREAMBLE $cnt_preamble
  }
  if {[lsearch -exact $b_props CONFIG.B_RX_DATA_PHASE_DELAY_CYCLES] >= 0} {
    lappend b_cfg CONFIG.B_RX_DATA_PHASE_DELAY_CYCLES $rx_data_phase_delay_cycles
  }
  if {[lsearch -exact $b_props CONFIG.B_RX_DETECT_START_CYCLES] >= 0} {
    lappend b_cfg CONFIG.B_RX_DETECT_START_CYCLES $b_rx_detect_start_cycles
  }
  if {[lsearch -exact $b_props CONFIG.B_RX_DETECT_END_CYCLES] >= 0} {
    lappend b_cfg CONFIG.B_RX_DETECT_END_CYCLES $b_rx_detect_end_cycles
  }
  if {[lsearch -exact $b_props CONFIG.B_RX_PREAMBLE_REALIGN_EDGE] >= 0} {
    lappend b_cfg CONFIG.B_RX_PREAMBLE_REALIGN_EDGE $b_rx_preamble_realign_edge
  }
  if {[lsearch -exact $b_props CONFIG.B_GUARD_CYCLES] >= 0} {
    lappend b_cfg CONFIG.B_GUARD_CYCLES $guard_cycles
  }
  if {[lsearch -exact $b_props CONFIG.B_BACKOFF_SLOT_CYCLES] >= 0} {
    lappend b_cfg CONFIG.B_BACKOFF_SLOT_CYCLES $b_backoff_slot_cycles
  }
  if {[lsearch -exact $b_props CONFIG.B_START_IDLE_CYCLES] >= 0} {
    lappend b_cfg CONFIG.B_START_IDLE_CYCLES $b_start_idle_cycles
  }
  if {[lsearch -exact $b_props CONFIG.B_RECOVERY_RESET_CYCLES] >= 0} {
    lappend b_cfg CONFIG.B_RECOVERY_RESET_CYCLES $b_recovery_reset_cycles
  }
  if {[lsearch -exact $b_props CONFIG.B_PARALLEL_2LANE_MODE] >= 0} {
    lappend b_cfg CONFIG.B_PARALLEL_2LANE_MODE $parallel_2lane_mode
  }
  if {[lsearch -exact $b_props CONFIG.B_DEBUG_SELECT_RX_STATUS] >= 0} {
    lappend b_cfg CONFIG.B_DEBUG_SELECT_RX_STATUS $b_debug_select_rx_status
  }
  if {[lsearch -exact $b_props CONFIG.B_ACK_LANE_MASK] >= 0} {
    lappend b_cfg CONFIG.B_ACK_LANE_MASK $b_ack_lane_mask
  }
  if {[lsearch -exact $b_props CONFIG.B_TX_LANE_MASK] >= 0} {
    lappend b_cfg CONFIG.B_TX_LANE_MASK $b_tx_lane_mask
  }
  if {[lsearch -exact $b_props CONFIG.B_RX_LANE_MASK] >= 0} {
    lappend b_cfg CONFIG.B_RX_LANE_MASK $b_rx_lane_mask
  }
  if {[lsearch -exact $b_props CONFIG.B_EXPECTED_A_LANE_MASK] >= 0} {
    lappend b_cfg CONFIG.B_EXPECTED_A_LANE_MASK $b_expected_a_lane_mask
  }
  if {[lsearch -exact $b_props CONFIG.RAW_PACKET_BYTES] >= 0} {
    lappend b_cfg CONFIG.RAW_PACKET_BYTES $max_packet_bytes
  }
  if {[lsearch -exact $b_props CONFIG.FRAGMENT_BYTES] >= 0} {
    lappend b_cfg CONFIG.FRAGMENT_BYTES $fragment_bytes
  }
  if {[lsearch -exact $b_props CONFIG.APP_PAYLOAD_BYTES] >= 0} {
    lappend b_cfg CONFIG.APP_PAYLOAD_BYTES [expr {$max_packet_bytes - 8}]
  }
  if {[lsearch -exact $b_props CONFIG.B2A_ENABLE] >= 0} {
    lappend b_cfg CONFIG.B2A_ENABLE $b2a_enable
  }
  if {[lsearch -exact $b_props CONFIG.B2A_FREE_RUN] >= 0} {
    lappend b_cfg CONFIG.B2A_FREE_RUN $b2a_free_run
  }
  if {[lsearch -exact $b_props CONFIG.B2A_ECHO_ENABLE] >= 0} {
    lappend b_cfg CONFIG.B2A_ECHO_ENABLE $b2a_echo_enable
  }
  if {[lsearch -exact $b_props CONFIG.FORCE_SD_SHUTDOWN] >= 0} {
    lappend b_cfg CONFIG.FORCE_SD_SHUTDOWN $force_sd_shutdown
  } elseif {$force_sd_shutdown != 0} {
    error "B endpoint does not expose CONFIG.FORCE_SD_SHUTDOWN; refresh module reference before P7A-04 build"
  }
  if {[lsearch -exact $b_props CONFIG.TX_GAP_CYCLES] >= 0} {
    lappend b_cfg CONFIG.TX_GAP_CYCLES $b_tx_gap_cycles
  }
  if {[llength $b_cfg] > 0} {
    set_property -dict $b_cfg $b
    puts "HWLOOP: B endpoint applied config entries=$b_cfg"
  } else {
    puts "HWLOOP: B sink module parameters unavailable in BD; using RTL defaults"
  }
}
if {[llength [info commands update_module_reference]] > 0} {
  if {[catch {update_module_reference $b} update_err]} {
    puts "HWLOOP: update_module_reference warning after B config: $update_err"
  }
}

connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins ir_loopback_b0/clk_phy]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] [get_bd_pins ir_loopback_b0/rst_n]

recreate_tfdu_vector_port loop_rx_b0 I ir_loopback_b0/ir_rx_in $lane_count
recreate_tfdu_vector_port loop_sd_b0 O ir_loopback_b0/ir_sd $lane_count
recreate_tfdu_vector_port loop_mode_b0 O ir_loopback_b0/ir_mode_out $lane_count
recreate_tfdu_vector_port loop_tx_b0 O ir_loopback_b0/ir_tx_out $lane_count
set b_debug_pin [get_bd_pins -quiet ir_loopback_b0/debug_status]
if {[llength $b_debug_pin] == 0} {
  error "B-side debug_status pin was not created on ir_loopback_b0"
}
connect_bd_net $b_debug_pin [get_bd_pins ir_array_top_axi_0/ext_phy_dbg]

validate_bd_design
save_bd_design
force_xci_model_parameter $bd_file design_shiboqi_ir_array_top_axi_0_0 STREAM_PHY_DBG_SELECT $stream_phy_dbg_select
force_xci_model_parameter $bd_file design_shiboqi_ir_array_top_axi_0_0 FORCE_SD_SHUTDOWN $force_sd_shutdown
reset_target all $bd_file
generate_target all $bd_file
export_ip_user_files -of_objects $bd_file -no_script -sync -force -quiet
update_compile_order -fileset sources_1

set wrapper_files [make_wrapper -files $bd_file -top -force]
if {[llength $wrapper_files] > 0} {
  foreach wrapper_file $wrapper_files {
    if {[llength [get_files -quiet $wrapper_file]] == 0} {
      add_files -norecurse $wrapper_file
    }
  }
}

set_property top design_shiboqi_wrapper [current_fileset]
sync_imported_wrapper $repo_root
update_compile_order -fileset sources_1
close_project

puts "CONFIGURE_LANE0_AB_HW_LOOPBACK_DONE"
