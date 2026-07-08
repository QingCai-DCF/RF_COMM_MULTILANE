###############################################################################
# Target constraints draft for TFDU_VFIR_Client / design_shiboqi
#
# Purpose:
#   - Zynq-7010 PS controls AXI DMA and the custom ir_array_top_axi IP.
#   - DMA MM2S streams payload bytes into the IR array transmitter.
#   - IR array receiver reassembles packets and streams bytes back to DMA S2MM.
#   - PL external pins are the IR lane pins below.
#
# Notes:
#   - This file is a draft for review. It is not a replacement for PORT1.xdc yet.
#   - Current BD instance uses LANE_COUNT = 1. Lane 1/2/3 sections are templates.
#   - Keep PACKAGE_PIN values aligned with the target board schematic.
#   - Keep IOSTANDARD aligned with the IR transceiver voltage bank.
###############################################################################

###############################################################################
# Helper: apply a property only when the port exists.
###############################################################################
proc set_port_property_if_exists {prop value port_name} {
    set p [get_ports -quiet $port_name]
    if {[llength $p] != 0} {
        set_property $prop $value $p
    }
}

###############################################################################
# IR lane 0: active in current design.
###############################################################################
set_port_property_if_exists IOSTANDARD LVCMOS33 ir_mode_out_0
set_port_property_if_exists IOSTANDARD LVCMOS33 ir_rx_in_0
set_port_property_if_exists IOSTANDARD LVCMOS33 ir_sd_0
set_port_property_if_exists IOSTANDARD LVCMOS33 ir_tx_out_0

set_port_property_if_exists PACKAGE_PIN T12 ir_mode_out_0
set_port_property_if_exists PACKAGE_PIN B19 ir_rx_in_0
set_port_property_if_exists PACKAGE_PIN T11 ir_sd_0
set_port_property_if_exists PACKAGE_PIN C20 ir_tx_out_0

###############################################################################
# IR lane 1: template. Uncomment/update when LANE_COUNT >= 2.
###############################################################################
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_mode_out_1
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_rx_in_1
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_sd_1
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_tx_out_1
#
# set_port_property_if_exists PACKAGE_PIN G17 ir_mode_out_1
# set_port_property_if_exists PACKAGE_PIN H15 ir_rx_in_1
# set_port_property_if_exists PACKAGE_PIN H16 ir_sd_1
# set_port_property_if_exists PACKAGE_PIN K14 ir_tx_out_1

###############################################################################
# IR lane 2: template. Fill from the target board schematic when needed.
###############################################################################
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_mode_out_2
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_rx_in_2
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_sd_2
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_tx_out_2
#
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_mode_out_2
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_rx_in_2
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_sd_2
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_tx_out_2

###############################################################################
# IR lane 3: template. Fill from the target board schematic when needed.
###############################################################################
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_mode_out_3
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_rx_in_3
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_sd_3
# set_port_property_if_exists IOSTANDARD LVCMOS33 ir_tx_out_3
#
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_mode_out_3
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_rx_in_3
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_sd_3
# set_port_property_if_exists PACKAGE_PIN <TODO_PIN> ir_tx_out_3

###############################################################################
# Optional output electrical tuning. Enable only after checking the board IO bank
# and signal integrity requirements.
###############################################################################
# foreach p [list ir_mode_out_0 ir_sd_0 ir_tx_out_0] {
#     set port_obj [get_ports -quiet $p]
#     if {[llength $port_obj] != 0} {
#         set_property DRIVE 8 $port_obj
#         set_property SLEW SLOW $port_obj
#     }
# }

###############################################################################
# Clock domains.
#
# PS/control/AXIS side: processing_system7_0/FCLK_CLK0, usually clk_fpga_0.
# IR PHY side: clk_wiz_0/clk_out1, usually clk_out1_design_shiboqi_clk_wiz_0_0.
# ir_array_top_axi contains explicit CDC between these domains.
#
# Do not add a broad set_clock_groups exception here. Vivado 2023.1 reports
# TIMING-24/TIMING-28 when a project-level clock group overrides generated-IP
# set_max_delay -datapath_only constraints or names the auto-derived PHY clock.
# Keep CDC timing exceptions point-to-point instead.
###############################################################################

###############################################################################
# CDC synchronizer first-stage false path.
#
# Applies to cdc_sync first flip-flop D pins. Kept guarded so this draft can be
# sourced before/after hierarchy names settle.
###############################################################################
set cdc_ff1_d_pins [get_pins -quiet \
    -of_objects [get_cells -hierarchical -filter {NAME =~ *sync_ff1_reg*}] \
    -filter {NAME =~ *D}]
if {[llength $cdc_ff1_d_pins] != 0} {
    set_false_path -to $cdc_ff1_d_pins
}
