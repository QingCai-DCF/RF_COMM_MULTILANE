# TFDU-6102 constraints for board-internal A/B loopback.
# Current target is a 2-lane build: lane0 on J10 and lane1 on J11.

# Lane 0, J10, logical A mapped to board L0-B for A/B swap validation.
set_property PACKAGE_PIN T12 [get_ports {ir_mode_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[0]}]
set_property PACKAGE_PIN B19 [get_ports {ir_rx_in_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[0]}]
set_property PACKAGE_PIN T11 [get_ports {ir_sd_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[0]}]
set_property PACKAGE_PIN C20 [get_ports {ir_tx_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[0]}]

# Lane 1, J11, logical A mapped to board L1-B for A/B swap validation.
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

# Lane 0, J10, logical B mapped to board L0-A for A/B swap validation.
set_property PACKAGE_PIN V17 [get_ports {loop_mode_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[0]}]
set_property PACKAGE_PIN U13 [get_ports {loop_rx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[0]}]
set_property PACKAGE_PIN T14 [get_ports {loop_sd_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[0]}]
set_property PACKAGE_PIN V12 [get_ports {loop_tx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[0]}]

# Lane 1, J11, logical B mapped to board L1-A for A/B swap validation.
# B_RX1 is temporarily moved from J11 PIN26 / D19 to J11 PIN33 / G15
# to isolate whether the original receiver FPGA pin is damaged.
set_property PACKAGE_PIN L16 [get_ports {loop_mode_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[1]}]
set_property PACKAGE_PIN G15 [get_ports {loop_rx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[1]}]
set_property PACKAGE_PIN M17 [get_ports {loop_sd_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[1]}]
set_property PACKAGE_PIN E18 [get_ports {loop_tx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[1]}]
