###############################################################################
# 8-lane TFDU shutdown candidate constraints
#
# Generated: 2026-06-27T01:39:40
# Source: reports/8lane_candidate_pinmap_current.csv
#
# Candidate only: build/review before hardware use.
# This file is not used by the current program_tfdu_shutdown.tcl path.
###############################################################################

# ir_mode_out_0[0] endpoint=A lane=0 signal=MODE shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN T12 [get_ports {ir_mode_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[0]}]
# ir_rx_in_0[0] endpoint=A lane=0 signal=RX shutdown=input origin=active_PORT1
set_property PACKAGE_PIN B19 [get_ports {ir_rx_in_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[0]}]
# ir_sd_0[0] endpoint=A lane=0 signal=SD shutdown=1 origin=active_PORT1
set_property PACKAGE_PIN T11 [get_ports {ir_sd_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[0]}]
# ir_tx_out_0[0] endpoint=A lane=0 signal=TX shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN C20 [get_ports {ir_tx_out_0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[0]}]
# ir_mode_out_0[1] endpoint=A lane=1 signal=MODE shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN G17 [get_ports {ir_mode_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[1]}]
# ir_rx_in_0[1] endpoint=A lane=1 signal=RX shutdown=input origin=active_PORT1
set_property PACKAGE_PIN H15 [get_ports {ir_rx_in_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[1]}]
# ir_sd_0[1] endpoint=A lane=1 signal=SD shutdown=1 origin=active_PORT1
set_property PACKAGE_PIN H16 [get_ports {ir_sd_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[1]}]
# ir_tx_out_0[1] endpoint=A lane=1 signal=TX shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN K14 [get_ports {ir_tx_out_0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[1]}]
# ir_mode_out_0[2] endpoint=A lane=2 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN W18 [get_ports {ir_mode_out_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[2]}]
# ir_rx_in_0[2] endpoint=A lane=2 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN W19 [get_ports {ir_rx_in_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[2]}]
# ir_sd_0[2] endpoint=A lane=2 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN P14 [get_ports {ir_sd_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[2]}]
# ir_tx_out_0[2] endpoint=A lane=2 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN R14 [get_ports {ir_tx_out_0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[2]}]
# ir_mode_out_0[3] endpoint=A lane=3 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN Y16 [get_ports {ir_mode_out_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[3]}]
# ir_rx_in_0[3] endpoint=A lane=3 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN Y17 [get_ports {ir_rx_in_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[3]}]
# ir_sd_0[3] endpoint=A lane=3 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN V15 [get_ports {ir_sd_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[3]}]
# ir_tx_out_0[3] endpoint=A lane=3 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN W15 [get_ports {ir_tx_out_0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[3]}]
# ir_mode_out_0[4] endpoint=A lane=4 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN W14 [get_ports {ir_mode_out_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[4]}]
# ir_rx_in_0[4] endpoint=A lane=4 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN Y14 [get_ports {ir_rx_in_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[4]}]
# ir_sd_0[4] endpoint=A lane=4 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN N17 [get_ports {ir_sd_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[4]}]
# ir_tx_out_0[4] endpoint=A lane=4 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN P18 [get_ports {ir_tx_out_0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[4]}]
# ir_mode_out_0[5] endpoint=A lane=5 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN U14 [get_ports {ir_mode_out_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[5]}]
# ir_rx_in_0[5] endpoint=A lane=5 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN U15 [get_ports {ir_rx_in_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[5]}]
# ir_sd_0[5] endpoint=A lane=5 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN P15 [get_ports {ir_sd_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[5]}]
# ir_tx_out_0[5] endpoint=A lane=5 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN P16 [get_ports {ir_tx_out_0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[5]}]
# ir_mode_out_0[6] endpoint=A lane=6 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN T16 [get_ports {ir_mode_out_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[6]}]
# ir_rx_in_0[6] endpoint=A lane=6 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN U17 [get_ports {ir_rx_in_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[6]}]
# ir_sd_0[6] endpoint=A lane=6 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN V18 [get_ports {ir_sd_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[6]}]
# ir_tx_out_0[6] endpoint=A lane=6 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN T15 [get_ports {ir_tx_out_0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[6]}]
# ir_mode_out_0[7] endpoint=A lane=7 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN V13 [get_ports {ir_mode_out_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_mode_out_0[7]}]
# ir_rx_in_0[7] endpoint=A lane=7 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN W13 [get_ports {ir_rx_in_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_rx_in_0[7]}]
# ir_sd_0[7] endpoint=A lane=7 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN U12 [get_ports {ir_sd_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_sd_0[7]}]
# ir_tx_out_0[7] endpoint=A lane=7 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN T10 [get_ports {ir_tx_out_0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {ir_tx_out_0[7]}]
# loop_mode_b0[0] endpoint=B lane=0 signal=MODE shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN V17 [get_ports {loop_mode_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[0]}]
# loop_rx_b0[0] endpoint=B lane=0 signal=RX shutdown=input origin=active_PORT1
set_property PACKAGE_PIN U13 [get_ports {loop_rx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[0]}]
# loop_sd_b0[0] endpoint=B lane=0 signal=SD shutdown=1 origin=active_PORT1
set_property PACKAGE_PIN T14 [get_ports {loop_sd_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[0]}]
# loop_tx_b0[0] endpoint=B lane=0 signal=TX shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN V12 [get_ports {loop_tx_b0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[0]}]
# loop_mode_b0[1] endpoint=B lane=1 signal=MODE shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN L16 [get_ports {loop_mode_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[1]}]
# loop_rx_b0[1] endpoint=B lane=1 signal=RX shutdown=input origin=active_PORT1
set_property PACKAGE_PIN G15 [get_ports {loop_rx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[1]}]
# loop_sd_b0[1] endpoint=B lane=1 signal=SD shutdown=1 origin=active_PORT1
set_property PACKAGE_PIN M17 [get_ports {loop_sd_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[1]}]
# loop_tx_b0[1] endpoint=B lane=1 signal=TX shutdown=0 origin=active_PORT1
set_property PACKAGE_PIN E18 [get_ports {loop_tx_b0[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[1]}]
# loop_mode_b0[2] endpoint=B lane=2 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN A20 [get_ports {loop_mode_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[2]}]
# loop_rx_b0[2] endpoint=B lane=2 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN B20 [get_ports {loop_rx_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[2]}]
# loop_sd_b0[2] endpoint=B lane=2 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN F16 [get_ports {loop_sd_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[2]}]
# loop_tx_b0[2] endpoint=B lane=2 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN F17 [get_ports {loop_tx_b0[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[2]}]
# loop_mode_b0[3] endpoint=B lane=3 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN F19 [get_ports {loop_mode_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[3]}]
# loop_rx_b0[3] endpoint=B lane=3 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN F20 [get_ports {loop_rx_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[3]}]
# loop_sd_b0[3] endpoint=B lane=3 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN G19 [get_ports {loop_sd_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[3]}]
# loop_tx_b0[3] endpoint=B lane=3 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN G20 [get_ports {loop_tx_b0[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[3]}]
# loop_mode_b0[4] endpoint=B lane=4 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN J18 [get_ports {loop_mode_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[4]}]
# loop_rx_b0[4] endpoint=B lane=4 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN H18 [get_ports {loop_rx_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[4]}]
# loop_sd_b0[4] endpoint=B lane=4 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN L19 [get_ports {loop_sd_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[4]}]
# loop_tx_b0[4] endpoint=B lane=4 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN L20 [get_ports {loop_tx_b0[4]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[4]}]
# loop_mode_b0[5] endpoint=B lane=5 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN M19 [get_ports {loop_mode_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[5]}]
# loop_rx_b0[5] endpoint=B lane=5 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN M20 [get_ports {loop_rx_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[5]}]
# loop_sd_b0[5] endpoint=B lane=5 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN K17 [get_ports {loop_sd_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[5]}]
# loop_tx_b0[5] endpoint=B lane=5 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN K18 [get_ports {loop_tx_b0[5]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[5]}]
# loop_mode_b0[6] endpoint=B lane=6 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN K19 [get_ports {loop_mode_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[6]}]
# loop_rx_b0[6] endpoint=B lane=6 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN J19 [get_ports {loop_rx_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[6]}]
# loop_sd_b0[6] endpoint=B lane=6 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN J20 [get_ports {loop_sd_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[6]}]
# loop_tx_b0[6] endpoint=B lane=6 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN H20 [get_ports {loop_tx_b0[6]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[6]}]
# loop_mode_b0[7] endpoint=B lane=7 signal=MODE shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN L17 [get_ports {loop_mode_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_mode_b0[7]}]
# loop_rx_b0[7] endpoint=B lane=7 signal=RX shutdown=input origin=candidate_auto
set_property PACKAGE_PIN M18 [get_ports {loop_rx_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_rx_b0[7]}]
# loop_sd_b0[7] endpoint=B lane=7 signal=SD shutdown=1 origin=candidate_auto
set_property PACKAGE_PIN D20 [get_ports {loop_sd_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_sd_b0[7]}]
# loop_tx_b0[7] endpoint=B lane=7 signal=TX shutdown=0 origin=candidate_auto
set_property PACKAGE_PIN E19 [get_ports {loop_tx_b0[7]}]
set_property IOSTANDARD LVCMOS33 [get_ports {loop_tx_b0[7]}]

set_property DRIVE 4 [get_ports {
  ir_mode_out_0[0] ir_mode_out_0[1] ir_mode_out_0[2] ir_mode_out_0[3] ir_mode_out_0[4] ir_mode_out_0[5] ir_mode_out_0[6] ir_mode_out_0[7] ir_sd_0[0] ir_sd_0[1] ir_sd_0[2] ir_sd_0[3] ir_sd_0[4] ir_sd_0[5] ir_sd_0[6] ir_sd_0[7] ir_tx_out_0[0] ir_tx_out_0[1] ir_tx_out_0[2] ir_tx_out_0[3] ir_tx_out_0[4] ir_tx_out_0[5] ir_tx_out_0[6] ir_tx_out_0[7] loop_mode_b0[0] loop_mode_b0[1] loop_mode_b0[2] loop_mode_b0[3] loop_mode_b0[4] loop_mode_b0[5] loop_mode_b0[6] loop_mode_b0[7] loop_sd_b0[0] loop_sd_b0[1] loop_sd_b0[2] loop_sd_b0[3] loop_sd_b0[4] loop_sd_b0[5] loop_sd_b0[6] loop_sd_b0[7] loop_tx_b0[0] loop_tx_b0[1] loop_tx_b0[2] loop_tx_b0[3] loop_tx_b0[4] loop_tx_b0[5] loop_tx_b0[6] loop_tx_b0[7]
}]
set_property SLEW SLOW [get_ports {
  ir_mode_out_0[0] ir_mode_out_0[1] ir_mode_out_0[2] ir_mode_out_0[3] ir_mode_out_0[4] ir_mode_out_0[5] ir_mode_out_0[6] ir_mode_out_0[7] ir_sd_0[0] ir_sd_0[1] ir_sd_0[2] ir_sd_0[3] ir_sd_0[4] ir_sd_0[5] ir_sd_0[6] ir_sd_0[7] ir_tx_out_0[0] ir_tx_out_0[1] ir_tx_out_0[2] ir_tx_out_0[3] ir_tx_out_0[4] ir_tx_out_0[5] ir_tx_out_0[6] ir_tx_out_0[7] loop_mode_b0[0] loop_mode_b0[1] loop_mode_b0[2] loop_mode_b0[3] loop_mode_b0[4] loop_mode_b0[5] loop_mode_b0[6] loop_mode_b0[7] loop_sd_b0[0] loop_sd_b0[1] loop_sd_b0[2] loop_sd_b0[3] loop_sd_b0[4] loop_sd_b0[5] loop_sd_b0[6] loop_sd_b0[7] loop_tx_b0[0] loop_tx_b0[1] loop_tx_b0[2] loop_tx_b0[3] loop_tx_b0[4] loop_tx_b0[5] loop_tx_b0[6] loop_tx_b0[7]
}]
