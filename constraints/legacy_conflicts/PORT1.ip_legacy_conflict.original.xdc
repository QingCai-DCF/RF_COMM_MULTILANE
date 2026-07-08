# TFDU-6102 two-lane constraints for board-internal A/B loopback.
# Lane 0 is wired on J10, lane 1 is wired on J11.

# Lane 0, J10, board L0-A. A/B swapped for J10 connector validation.
set_property PACKAGE_PIN V17 [get_ports {ir_mode_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[0]}]
set_property PACKAGE_PIN U13 [get_ports {ir_rx_in_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[0]}]
set_property PACKAGE_PIN T14 [get_ports {ir_sd_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[0]}]
set_property PACKAGE_PIN V12 [get_ports {ir_tx_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[0]}]

# Lane 1, J11, board L1-A.
set_property PACKAGE_PIN G17 [get_ports {ir_mode_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[1]}]
set_property PACKAGE_PIN H15 [get_ports {ir_rx_in_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[1]}]
set_property PACKAGE_PIN H16 [get_ports {ir_sd_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[1]}]
set_property PACKAGE_PIN K14 [get_ports {ir_tx_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[1]}]

# First synchronizer stage CDC path.
set_false_path -to [get_pins -of_objects [get_cells -hierarchical -filter {NAME =~ *sync_ff1_reg*}] -filter {NAME =~ *D}]

# Lane 0, J10, board L0-B partner endpoint. A/B swapped for J10 connector validation.
set_property PACKAGE_PIN T12 [get_ports {loop_mode_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[0]}]
set_property PACKAGE_PIN B19 [get_ports {loop_rx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[0]}]
set_property PACKAGE_PIN T11 [get_ports {loop_sd_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[0]}]
set_property PACKAGE_PIN C20 [get_ports {loop_tx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[0]}]

# Lane 1, J11, board L1-B partner endpoint.
set_property PACKAGE_PIN L16 [get_ports {loop_mode_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[1]}]
set_property PACKAGE_PIN D19 [get_ports {loop_rx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[1]}]
set_property PACKAGE_PIN M17 [get_ports {loop_sd_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[1]}]
set_property PACKAGE_PIN E18 [get_ports {loop_tx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[1]}]
