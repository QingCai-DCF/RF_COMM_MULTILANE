###############################################################################
# 8-lane TFDU candidate pin map
#
# Generated: 2026-06-27T01:34:22
# Source: hardware/01_SCH AX7010/AX7020 pin workbook + current PORT1.xdc
#
# This is a candidate for review, not proven hardware acceptance.
# Do not promote it to the active constraints until the physical connector
# mapping, IO bank voltage, shutdown coverage, and TFDU wiring are reviewed.
###############################################################################

# Endpoint A

# Endpoint A, lane 0
# ir_mode_out_0[0] -> IO1_14P / T12 / active_PORT1
set_property PACKAGE_PIN T12 [get_ports {ir_mode_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[0]}]
# ir_rx_in_0[0] -> IO1_16P / B19 / active_PORT1
set_property PACKAGE_PIN B19 [get_ports {ir_rx_in_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[0]}]
# ir_sd_0[0] -> IO1_15P / T11 / active_PORT1
set_property PACKAGE_PIN T11 [get_ports {ir_sd_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[0]}]
# ir_tx_out_0[0] -> IO1_17P / C20 / active_PORT1
set_property PACKAGE_PIN C20 [get_ports {ir_tx_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[0]}]

# Endpoint A, lane 1
# ir_mode_out_0[1] -> IO2_14P / G17 / active_PORT1
set_property PACKAGE_PIN G17 [get_ports {ir_mode_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[1]}]
# ir_rx_in_0[1] -> IO2_16P / H15 / active_PORT1
set_property PACKAGE_PIN H15 [get_ports {ir_rx_in_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[1]}]
# ir_sd_0[1] -> IO2_15P / H16 / active_PORT1
set_property PACKAGE_PIN H16 [get_ports {ir_sd_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[1]}]
# ir_tx_out_0[1] -> IO2_17P / K14 / active_PORT1
set_property PACKAGE_PIN K14 [get_ports {ir_tx_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[1]}]

# Endpoint A, lane 2
# ir_mode_out_0[2] -> IO1_1P / W18 / candidate_auto
set_property PACKAGE_PIN W18 [get_ports {ir_mode_out_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[2]}]
# ir_rx_in_0[2] -> IO1_1N / W19 / candidate_auto
set_property PACKAGE_PIN W19 [get_ports {ir_rx_in_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[2]}]
# ir_sd_0[2] -> IO1_2P / P14 / candidate_auto
set_property PACKAGE_PIN P14 [get_ports {ir_sd_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[2]}]
# ir_tx_out_0[2] -> IO1_2N / R14 / candidate_auto
set_property PACKAGE_PIN R14 [get_ports {ir_tx_out_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[2]}]

# Endpoint A, lane 3
# ir_mode_out_0[3] -> IO1_3P / Y16 / candidate_auto
set_property PACKAGE_PIN Y16 [get_ports {ir_mode_out_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[3]}]
# ir_rx_in_0[3] -> IO1_3N / Y17 / candidate_auto
set_property PACKAGE_PIN Y17 [get_ports {ir_rx_in_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[3]}]
# ir_sd_0[3] -> IO1_4P / V15 / candidate_auto
set_property PACKAGE_PIN V15 [get_ports {ir_sd_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[3]}]
# ir_tx_out_0[3] -> IO1_4N / W15 / candidate_auto
set_property PACKAGE_PIN W15 [get_ports {ir_tx_out_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[3]}]

# Endpoint A, lane 4
# ir_mode_out_0[4] -> IO1_5P / W14 / candidate_auto
set_property PACKAGE_PIN W14 [get_ports {ir_mode_out_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[4]}]
# ir_rx_in_0[4] -> IO1_5N / Y14 / candidate_auto
set_property PACKAGE_PIN Y14 [get_ports {ir_rx_in_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[4]}]
# ir_sd_0[4] -> IO1_6P / N17 / candidate_auto
set_property PACKAGE_PIN N17 [get_ports {ir_sd_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[4]}]
# ir_tx_out_0[4] -> IO1_6N / P18 / candidate_auto
set_property PACKAGE_PIN P18 [get_ports {ir_tx_out_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[4]}]

# Endpoint A, lane 5
# ir_mode_out_0[5] -> IO1_7P / U14 / candidate_auto
set_property PACKAGE_PIN U14 [get_ports {ir_mode_out_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[5]}]
# ir_rx_in_0[5] -> IO1_7N / U15 / candidate_auto
set_property PACKAGE_PIN U15 [get_ports {ir_rx_in_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[5]}]
# ir_sd_0[5] -> IO1_8P / P15 / candidate_auto
set_property PACKAGE_PIN P15 [get_ports {ir_sd_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[5]}]
# ir_tx_out_0[5] -> IO1_8N / P16 / candidate_auto
set_property PACKAGE_PIN P16 [get_ports {ir_tx_out_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[5]}]

# Endpoint A, lane 6
# ir_mode_out_0[6] -> IO1_9P / T16 / candidate_auto
set_property PACKAGE_PIN T16 [get_ports {ir_mode_out_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[6]}]
# ir_rx_in_0[6] -> IO1_9N / U17 / candidate_auto
set_property PACKAGE_PIN U17 [get_ports {ir_rx_in_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[6]}]
# ir_sd_0[6] -> IO1_10N / V18 / candidate_auto
set_property PACKAGE_PIN V18 [get_ports {ir_sd_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[6]}]
# ir_tx_out_0[6] -> IO1_11N / T15 / candidate_auto
set_property PACKAGE_PIN T15 [get_ports {ir_tx_out_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[6]}]

# Endpoint A, lane 7
# ir_mode_out_0[7] -> IO1_12N / V13 / candidate_auto
set_property PACKAGE_PIN V13 [get_ports {ir_mode_out_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[7]}]
# ir_rx_in_0[7] -> IO1_13N / W13 / candidate_auto
set_property PACKAGE_PIN W13 [get_ports {ir_rx_in_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[7]}]
# ir_sd_0[7] -> IO1_14N / U12 / candidate_auto
set_property PACKAGE_PIN U12 [get_ports {ir_sd_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[7]}]
# ir_tx_out_0[7] -> IO1_15N / T10 / candidate_auto
set_property PACKAGE_PIN T10 [get_ports {ir_tx_out_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[7]}]

# Endpoint B

# Endpoint B, lane 0
# loop_mode_b0[0] -> IO1_10P / V17 / active_PORT1
set_property PACKAGE_PIN V17 [get_ports {loop_mode_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[0]}]
# loop_rx_b0[0] -> IO1_12P / U13 / active_PORT1
set_property PACKAGE_PIN U13 [get_ports {loop_rx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[0]}]
# loop_sd_b0[0] -> IO1_11P / T14 / active_PORT1
set_property PACKAGE_PIN T14 [get_ports {loop_sd_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[0]}]
# loop_tx_b0[0] -> IO1_13P / V12 / active_PORT1
set_property PACKAGE_PIN V12 [get_ports {loop_tx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[0]}]

# Endpoint B, lane 1
# loop_mode_b0[1] -> IO2_10P / L16 / active_PORT1
set_property PACKAGE_PIN L16 [get_ports {loop_mode_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[1]}]
# loop_rx_b0[1] -> IO2_16N / G15 / active_PORT1
set_property PACKAGE_PIN G15 [get_ports {loop_rx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[1]}]
# loop_sd_b0[1] -> IO2_11P / M17 / active_PORT1
set_property PACKAGE_PIN M17 [get_ports {loop_sd_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[1]}]
# loop_tx_b0[1] -> IO2_13P / E18 / active_PORT1
set_property PACKAGE_PIN E18 [get_ports {loop_tx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[1]}]

# Endpoint B, lane 2
# loop_mode_b0[2] -> IO1_16N / A20 / candidate_auto
set_property PACKAGE_PIN A20 [get_ports {loop_mode_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[2]}]
# loop_rx_b0[2] -> IO1_17N / B20 / candidate_auto
set_property PACKAGE_PIN B20 [get_ports {loop_rx_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[2]}]
# loop_sd_b0[2] -> IO2_1P / F16 / candidate_auto
set_property PACKAGE_PIN F16 [get_ports {loop_sd_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[2]}]
# loop_tx_b0[2] -> IO2_1N / F17 / candidate_auto
set_property PACKAGE_PIN F17 [get_ports {loop_tx_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[2]}]

# Endpoint B, lane 3
# loop_mode_b0[3] -> IO2_2P / F19 / candidate_auto
set_property PACKAGE_PIN F19 [get_ports {loop_mode_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[3]}]
# loop_rx_b0[3] -> IO2_2N / F20 / candidate_auto
set_property PACKAGE_PIN F20 [get_ports {loop_rx_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[3]}]
# loop_sd_b0[3] -> IO2_3P / G19 / candidate_auto
set_property PACKAGE_PIN G19 [get_ports {loop_sd_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[3]}]
# loop_tx_b0[3] -> IO2_3N / G20 / candidate_auto
set_property PACKAGE_PIN G20 [get_ports {loop_tx_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[3]}]

# Endpoint B, lane 4
# loop_mode_b0[4] -> IO2_4P / J18 / candidate_auto
set_property PACKAGE_PIN J18 [get_ports {loop_mode_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[4]}]
# loop_rx_b0[4] -> IO2_4N / H18 / candidate_auto
set_property PACKAGE_PIN H18 [get_ports {loop_rx_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[4]}]
# loop_sd_b0[4] -> IO2_5P / L19 / candidate_auto
set_property PACKAGE_PIN L19 [get_ports {loop_sd_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[4]}]
# loop_tx_b0[4] -> IO2_5N / L20 / candidate_auto
set_property PACKAGE_PIN L20 [get_ports {loop_tx_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[4]}]

# Endpoint B, lane 5
# loop_mode_b0[5] -> IO2_6P / M19 / candidate_auto
set_property PACKAGE_PIN M19 [get_ports {loop_mode_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[5]}]
# loop_rx_b0[5] -> IO2_6N / M20 / candidate_auto
set_property PACKAGE_PIN M20 [get_ports {loop_rx_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[5]}]
# loop_sd_b0[5] -> IO2_7P / K17 / candidate_auto
set_property PACKAGE_PIN K17 [get_ports {loop_sd_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[5]}]
# loop_tx_b0[5] -> IO2_7N / K18 / candidate_auto
set_property PACKAGE_PIN K18 [get_ports {loop_tx_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[5]}]

# Endpoint B, lane 6
# loop_mode_b0[6] -> IO2_8P / K19 / candidate_auto
set_property PACKAGE_PIN K19 [get_ports {loop_mode_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[6]}]
# loop_rx_b0[6] -> IO2_8N / J19 / candidate_auto
set_property PACKAGE_PIN J19 [get_ports {loop_rx_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[6]}]
# loop_sd_b0[6] -> IO2_9P / J20 / candidate_auto
set_property PACKAGE_PIN J20 [get_ports {loop_sd_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[6]}]
# loop_tx_b0[6] -> IO2_9N / H20 / candidate_auto
set_property PACKAGE_PIN H20 [get_ports {loop_tx_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[6]}]

# Endpoint B, lane 7
# loop_mode_b0[7] -> IO2_10N / L17 / candidate_auto
set_property PACKAGE_PIN L17 [get_ports {loop_mode_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[7]}]
# loop_rx_b0[7] -> IO2_11N / M18 / candidate_auto
set_property PACKAGE_PIN M18 [get_ports {loop_rx_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[7]}]
# loop_sd_b0[7] -> IO2_12N / D20 / candidate_auto
set_property PACKAGE_PIN D20 [get_ports {loop_sd_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[7]}]
# loop_tx_b0[7] -> IO2_13N / E19 / candidate_auto
set_property PACKAGE_PIN E19 [get_ports {loop_tx_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[7]}]

###############################################################################
# Known excluded automatic pin choices
###############################################################################
# D19: previous B_RX1 location was bypassed during hardware debug; keep out of automatic 8-lane candidate until manually cleared
