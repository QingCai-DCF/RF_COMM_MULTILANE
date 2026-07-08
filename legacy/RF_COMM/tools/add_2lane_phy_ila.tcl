# Add a compact passive ILA to the current 2-lane A/B hardware loopback BD.
#
# Probes:
#   0 A_TX[1:0]
#   1 A_RX[1:0]
#   2 A_SD[1:0]
#   3 A_MODE[1:0]
#   4 B_TX[1:0]
#   5 B_RX[1:0]
#   6 B_SD[1:0]
#   7 B_MODE[1:0]
#   8 B_DEBUG_STATUS[31:0]

set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

set max_threads 4
if {[info exists ::env(VIVADO_MAX_THREADS)] && $::env(VIVADO_MAX_THREADS) ne ""} {
  set max_threads $::env(VIVADO_MAX_THREADS)
}

set_param general.maxThreads $max_threads
open_project $project_file
set_property ip_repo_paths $ip_repo [current_project]
update_ip_catalog -rebuild

set bd_file [lindex [get_files -quiet */design_shiboqi.bd] 0]
if {$bd_file eq ""} {
  error "Missing design_shiboqi.bd in project"
}

open_bd_design $bd_file

proc delete_bd_cell_if_exists {name} {
  set obj [get_bd_cells -quiet $name]
  if {[llength $obj] > 0} {
    puts "ILA2: delete old BD cell $name"
    delete_bd_objs $obj
  }
}

foreach name {
  ila_lane0_phy
  ila_2lane_phy
  system_ila_0
} {
  delete_bd_cell_if_exists $name
}

foreach required_pin {
  ir_array_top_axi_0/ir_tx_out
  ir_array_top_axi_0/ir_rx_in
  ir_array_top_axi_0/ir_sd
  ir_array_top_axi_0/ir_mode_out
  ir_loopback_b0/ir_tx_out
  ir_loopback_b0/ir_rx_in
  ir_loopback_b0/ir_sd
  ir_loopback_b0/ir_mode_out
  ir_loopback_b0/debug_status
  clk_wiz_0/clk_out1
} {
  if {[llength [get_bd_pins -quiet $required_pin]] == 0} {
    error "Missing required BD pin for 2-lane ILA: $required_pin"
  }
}

foreach vector_pin {
  ir_array_top_axi_0/ir_tx_out
  ir_array_top_axi_0/ir_rx_in
  ir_array_top_axi_0/ir_sd
  ir_array_top_axi_0/ir_mode_out
  ir_loopback_b0/ir_tx_out
  ir_loopback_b0/ir_rx_in
  ir_loopback_b0/ir_sd
  ir_loopback_b0/ir_mode_out
} {
  set left [get_property LEFT [get_bd_pins $vector_pin]]
  set right [get_property RIGHT [get_bd_pins $vector_pin]]
  if {$left != 1 || $right != 0} {
    error "Expected $vector_pin to be \[1:0\], got LEFT=$left RIGHT=$right"
  }
}

puts "ILA2: create passive 2-lane physical ILA"
create_bd_cell -type ip -vlnv xilinx.com:ip:ila:6.2 ila_2lane_phy
set_property -dict [list \
  CONFIG.C_MONITOR_TYPE {Native} \
  CONFIG.C_NUM_MONITOR_SLOTS {0} \
  CONFIG.C_NUM_OF_PROBES {9} \
  CONFIG.C_PROBE0_WIDTH {2} \
  CONFIG.C_PROBE1_WIDTH {2} \
  CONFIG.C_PROBE2_WIDTH {2} \
  CONFIG.C_PROBE3_WIDTH {2} \
  CONFIG.C_PROBE4_WIDTH {2} \
  CONFIG.C_PROBE5_WIDTH {2} \
  CONFIG.C_PROBE6_WIDTH {2} \
  CONFIG.C_PROBE7_WIDTH {2} \
  CONFIG.C_PROBE8_WIDTH {32} \
  CONFIG.C_DATA_DEPTH {16384} \
  CONFIG.C_INPUT_PIPE_STAGES {0} \
  CONFIG.C_EN_STRG_QUAL {0} \
  CONFIG.C_ADV_TRIGGER {false} \
  CONFIG.C_TRIGIN_EN {false} \
  CONFIG.C_TRIGOUT_EN {false} \
] [get_bd_cells ila_2lane_phy]

connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins ila_2lane_phy/clk]
connect_bd_net [get_bd_pins ir_array_top_axi_0/ir_tx_out] [get_bd_pins ila_2lane_phy/probe0]
connect_bd_net [get_bd_pins ir_array_top_axi_0/ir_rx_in] [get_bd_pins ila_2lane_phy/probe1]
connect_bd_net [get_bd_pins ir_array_top_axi_0/ir_sd] [get_bd_pins ila_2lane_phy/probe2]
connect_bd_net [get_bd_pins ir_array_top_axi_0/ir_mode_out] [get_bd_pins ila_2lane_phy/probe3]
connect_bd_net [get_bd_pins ir_loopback_b0/ir_tx_out] [get_bd_pins ila_2lane_phy/probe4]
connect_bd_net [get_bd_pins ir_loopback_b0/ir_rx_in] [get_bd_pins ila_2lane_phy/probe5]
connect_bd_net [get_bd_pins ir_loopback_b0/ir_sd] [get_bd_pins ila_2lane_phy/probe6]
connect_bd_net [get_bd_pins ir_loopback_b0/ir_mode_out] [get_bd_pins ila_2lane_phy/probe7]
connect_bd_net [get_bd_pins ir_loopback_b0/debug_status] [get_bd_pins ila_2lane_phy/probe8]

validate_bd_design
save_bd_design
puts "ILA2: C_NUM_OF_PROBES=[get_property CONFIG.C_NUM_OF_PROBES [get_bd_cells ila_2lane_phy]]"
puts "ILA2: C_DATA_DEPTH=[get_property CONFIG.C_DATA_DEPTH [get_bd_cells ila_2lane_phy]]"
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
update_compile_order -fileset sources_1
close_project

puts "ADD_2LANE_PHY_ILA_DONE"
