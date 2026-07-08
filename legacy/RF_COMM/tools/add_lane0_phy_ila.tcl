# Add a compact ILA to the current physical lane0 A/B block design.
#
# Probes:
#   0 A_TX   ir_array_top_axi_0/ir_tx_out
#   1 A_RX   ir_array_top_axi_0/ir_rx_in
#   2 B_TX   ir_loopback_b0/ir_tx_out
#   3 B_RX   ir_loopback_b0/ir_rx_in

set repo_root [file normalize [file join [file dirname [info script]] ..]]
set project_file [file join $repo_root TFDU_VFIR_Client_Array TFDU_VFIR_Client.xpr]
set ip_repo [file join $repo_root IPs ip_ir_array]

if {![file exists $project_file]} {
  error "Missing Vivado project: $project_file"
}

set_param general.maxThreads 16
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
    puts "ILA: delete old BD cell $name"
    delete_bd_objs $obj
  }
}

foreach name {
  ila_lane0_phy
  system_ila_0
} {
  delete_bd_cell_if_exists $name
}

foreach required_pin {
  ir_array_top_axi_0/ir_tx_out
  ir_array_top_axi_0/ir_rx_in
  ir_loopback_b0/ir_tx_out
  ir_loopback_b0/ir_rx_in
  clk_wiz_0/clk_out1
} {
  if {[llength [get_bd_pins -quiet $required_pin]] == 0} {
    error "Missing required BD pin for ILA: $required_pin"
  }
}

puts "ILA: create compact lane0 physical ILA"
create_bd_cell -type ip -vlnv xilinx.com:ip:ila:6.2 ila_lane0_phy
set_property -dict [list \
  CONFIG.C_MONITOR_TYPE {Native} \
  CONFIG.C_NUM_MONITOR_SLOTS {0} \
  CONFIG.C_NUM_OF_PROBES {4} \
  CONFIG.C_PROBE0_WIDTH {1} \
  CONFIG.C_PROBE1_WIDTH {1} \
  CONFIG.C_PROBE2_WIDTH {1} \
  CONFIG.C_PROBE3_WIDTH {1} \
  CONFIG.C_DATA_DEPTH {1024} \
  CONFIG.C_INPUT_PIPE_STAGES {0} \
  CONFIG.C_EN_STRG_QUAL {0} \
  CONFIG.C_ADV_TRIGGER {false} \
  CONFIG.C_TRIGIN_EN {false} \
  CONFIG.C_TRIGOUT_EN {false} \
] [get_bd_cells ila_lane0_phy]

connect_bd_net [get_bd_pins clk_wiz_0/clk_out1] [get_bd_pins ila_lane0_phy/clk]
connect_bd_net [get_bd_pins ir_array_top_axi_0/ir_tx_out] [get_bd_pins ila_lane0_phy/probe0]
connect_bd_net [get_bd_pins ir_array_top_axi_0/ir_rx_in] [get_bd_pins ila_lane0_phy/probe1]
connect_bd_net [get_bd_pins ir_loopback_b0/ir_tx_out] [get_bd_pins ila_lane0_phy/probe2]
connect_bd_net [get_bd_pins ir_loopback_b0/ir_rx_in] [get_bd_pins ila_lane0_phy/probe3]

validate_bd_design
save_bd_design
puts "ILA: C_NUM_OF_PROBES=[get_property CONFIG.C_NUM_OF_PROBES [get_bd_cells ila_lane0_phy]]"
puts "ILA: C_DATA_DEPTH=[get_property CONFIG.C_DATA_DEPTH [get_bd_cells ila_lane0_phy]]"
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

puts "ADD_LANE0_PHY_ILA_DONE"
