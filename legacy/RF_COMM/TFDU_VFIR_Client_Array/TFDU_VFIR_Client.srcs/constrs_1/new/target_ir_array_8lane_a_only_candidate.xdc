###############################################################################
# 8-lane TFDU A-only external candidate constraints
#
# Generated: 2026-06-27T02:20:27
# Source: reports/8lane_candidate_pinmap_current.csv
#
# Candidate only: build/review before hardware use.
# Intended profile: IR_LANE_COUNT=8, IR_B_MODE=external.
# This file deliberately excludes loop_* B-endpoint ports.
###############################################################################

# First synchronizer stage CDC path, preserved from PORT1.xdc.
set_false_path -to [get_pins -of_objects [get_cells -hierarchical -filter {NAME =~ *sync_ff1_reg*}] -filter {NAME =~ *D}]

# Endpoint A lane=0 signal=MODE ir_mode_out_0[0] -> IO1_14P / T12 / active_PORT1
set_property PACKAGE_PIN T12 [get_ports {ir_mode_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[0]}]
# Endpoint A lane=0 signal=RX ir_rx_in_0[0] -> IO1_16P / B19 / active_PORT1
set_property PACKAGE_PIN B19 [get_ports {ir_rx_in_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[0]}]
# Endpoint A lane=0 signal=SD ir_sd_0[0] -> IO1_15P / T11 / active_PORT1
set_property PACKAGE_PIN T11 [get_ports {ir_sd_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[0]}]
# Endpoint A lane=0 signal=TX ir_tx_out_0[0] -> IO1_17P / C20 / active_PORT1
set_property PACKAGE_PIN C20 [get_ports {ir_tx_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[0]}]
# Endpoint A lane=1 signal=MODE ir_mode_out_0[1] -> IO2_14P / G17 / active_PORT1
set_property PACKAGE_PIN G17 [get_ports {ir_mode_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[1]}]
# Endpoint A lane=1 signal=RX ir_rx_in_0[1] -> IO2_16P / H15 / active_PORT1
set_property PACKAGE_PIN H15 [get_ports {ir_rx_in_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[1]}]
# Endpoint A lane=1 signal=SD ir_sd_0[1] -> IO2_15P / H16 / active_PORT1
set_property PACKAGE_PIN H16 [get_ports {ir_sd_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[1]}]
# Endpoint A lane=1 signal=TX ir_tx_out_0[1] -> IO2_17P / K14 / active_PORT1
set_property PACKAGE_PIN K14 [get_ports {ir_tx_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[1]}]
# Endpoint A lane=2 signal=MODE ir_mode_out_0[2] -> IO1_1P / W18 / candidate_auto
set_property PACKAGE_PIN W18 [get_ports {ir_mode_out_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[2]}]
# Endpoint A lane=2 signal=RX ir_rx_in_0[2] -> IO1_1N / W19 / candidate_auto
set_property PACKAGE_PIN W19 [get_ports {ir_rx_in_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[2]}]
# Endpoint A lane=2 signal=SD ir_sd_0[2] -> IO1_2P / P14 / candidate_auto
set_property PACKAGE_PIN P14 [get_ports {ir_sd_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[2]}]
# Endpoint A lane=2 signal=TX ir_tx_out_0[2] -> IO1_2N / R14 / candidate_auto
set_property PACKAGE_PIN R14 [get_ports {ir_tx_out_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[2]}]
# Endpoint A lane=3 signal=MODE ir_mode_out_0[3] -> IO1_3P / Y16 / candidate_auto
set_property PACKAGE_PIN Y16 [get_ports {ir_mode_out_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[3]}]
# Endpoint A lane=3 signal=RX ir_rx_in_0[3] -> IO1_3N / Y17 / candidate_auto
set_property PACKAGE_PIN Y17 [get_ports {ir_rx_in_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[3]}]
# Endpoint A lane=3 signal=SD ir_sd_0[3] -> IO1_4P / V15 / candidate_auto
set_property PACKAGE_PIN V15 [get_ports {ir_sd_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[3]}]
# Endpoint A lane=3 signal=TX ir_tx_out_0[3] -> IO1_4N / W15 / candidate_auto
set_property PACKAGE_PIN W15 [get_ports {ir_tx_out_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[3]}]
# Endpoint A lane=4 signal=MODE ir_mode_out_0[4] -> IO1_5P / W14 / candidate_auto
set_property PACKAGE_PIN W14 [get_ports {ir_mode_out_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[4]}]
# Endpoint A lane=4 signal=RX ir_rx_in_0[4] -> IO1_5N / Y14 / candidate_auto
set_property PACKAGE_PIN Y14 [get_ports {ir_rx_in_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[4]}]
# Endpoint A lane=4 signal=SD ir_sd_0[4] -> IO1_6P / N17 / candidate_auto
set_property PACKAGE_PIN N17 [get_ports {ir_sd_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[4]}]
# Endpoint A lane=4 signal=TX ir_tx_out_0[4] -> IO1_6N / P18 / candidate_auto
set_property PACKAGE_PIN P18 [get_ports {ir_tx_out_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[4]}]
# Endpoint A lane=5 signal=MODE ir_mode_out_0[5] -> IO1_7P / U14 / candidate_auto
set_property PACKAGE_PIN U14 [get_ports {ir_mode_out_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[5]}]
# Endpoint A lane=5 signal=RX ir_rx_in_0[5] -> IO1_7N / U15 / candidate_auto
set_property PACKAGE_PIN U15 [get_ports {ir_rx_in_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[5]}]
# Endpoint A lane=5 signal=SD ir_sd_0[5] -> IO1_8P / P15 / candidate_auto
set_property PACKAGE_PIN P15 [get_ports {ir_sd_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[5]}]
# Endpoint A lane=5 signal=TX ir_tx_out_0[5] -> IO1_8N / P16 / candidate_auto
set_property PACKAGE_PIN P16 [get_ports {ir_tx_out_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[5]}]
# Endpoint A lane=6 signal=MODE ir_mode_out_0[6] -> IO1_9P / T16 / candidate_auto
set_property PACKAGE_PIN T16 [get_ports {ir_mode_out_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[6]}]
# Endpoint A lane=6 signal=RX ir_rx_in_0[6] -> IO1_9N / U17 / candidate_auto
set_property PACKAGE_PIN U17 [get_ports {ir_rx_in_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[6]}]
# Endpoint A lane=6 signal=SD ir_sd_0[6] -> IO1_10N / V18 / candidate_auto
set_property PACKAGE_PIN V18 [get_ports {ir_sd_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[6]}]
# Endpoint A lane=6 signal=TX ir_tx_out_0[6] -> IO1_11N / T15 / candidate_auto
set_property PACKAGE_PIN T15 [get_ports {ir_tx_out_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[6]}]
# Endpoint A lane=7 signal=MODE ir_mode_out_0[7] -> IO1_12N / V13 / candidate_auto
set_property PACKAGE_PIN V13 [get_ports {ir_mode_out_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[7]}]
# Endpoint A lane=7 signal=RX ir_rx_in_0[7] -> IO1_13N / W13 / candidate_auto
set_property PACKAGE_PIN W13 [get_ports {ir_rx_in_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[7]}]
# Endpoint A lane=7 signal=SD ir_sd_0[7] -> IO1_14N / U12 / candidate_auto
set_property PACKAGE_PIN U12 [get_ports {ir_sd_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[7]}]
# Endpoint A lane=7 signal=TX ir_tx_out_0[7] -> IO1_15N / T10 / candidate_auto
set_property PACKAGE_PIN T10 [get_ports {ir_tx_out_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[7]}]
