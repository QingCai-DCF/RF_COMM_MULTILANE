# Independently generated from official AX7020 sources for P10.2 fixed four-lane profile.
# This file is not copied from, sourced from, or validated by any Z7010/AX7010 XDC.
# OFFLINE_CANDIDATE_ONLY=1; CURRENT_RUN_HARDWARE_AUTHORIZATION=false
# F0/F1 or R0/R1 package pins are preserved from the accepted AX7020 2-lane profile.

# F0 Mode: J10-30 -> T12 bank 34
set_property PACKAGE_PIN T12 [get_ports {tfdu_mode_o[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_mode_o[0]}]
set_property DRIVE 4 [get_ports {tfdu_mode_o[0]}]
set_property SLEW SLOW [get_ports {tfdu_mode_o[0]}]

# F0 SD: J10-32 -> T11 bank 34
set_property PACKAGE_PIN T11 [get_ports {tfdu_sd_o[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_sd_o[0]}]
set_property DRIVE 4 [get_ports {tfdu_sd_o[0]}]
set_property SLEW SLOW [get_ports {tfdu_sd_o[0]}]

# F0 Rxd: J10-34 -> B19 bank 35
set_property PACKAGE_PIN B19 [get_ports {tfdu_rxd_i[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_rxd_i[0]}]

# F0 Txd: J10-36 -> C20 bank 35
set_property PACKAGE_PIN C20 [get_ports {tfdu_txd_o[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_txd_o[0]}]
set_property DRIVE 4 [get_ports {tfdu_txd_o[0]}]
set_property SLEW SLOW [get_ports {tfdu_txd_o[0]}]

# F1 Mode: J10-22 -> V17 bank 34
set_property PACKAGE_PIN V17 [get_ports {tfdu_mode_o[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_mode_o[1]}]
set_property DRIVE 4 [get_ports {tfdu_mode_o[1]}]
set_property SLEW SLOW [get_ports {tfdu_mode_o[1]}]

# F1 SD: J10-24 -> T14 bank 34
set_property PACKAGE_PIN T14 [get_ports {tfdu_sd_o[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_sd_o[1]}]
set_property DRIVE 4 [get_ports {tfdu_sd_o[1]}]
set_property SLEW SLOW [get_ports {tfdu_sd_o[1]}]

# F1 Rxd: J10-26 -> U13 bank 34
set_property PACKAGE_PIN U13 [get_ports {tfdu_rxd_i[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_rxd_i[1]}]

# F1 Txd: J10-28 -> V12 bank 34
set_property PACKAGE_PIN V12 [get_ports {tfdu_txd_o[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_txd_o[1]}]
set_property DRIVE 4 [get_ports {tfdu_txd_o[1]}]
set_property SLEW SLOW [get_ports {tfdu_txd_o[1]}]

# F2 Mode: J11-30 -> G17 bank 35
set_property PACKAGE_PIN G17 [get_ports {tfdu_mode_o[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_mode_o[2]}]
set_property DRIVE 4 [get_ports {tfdu_mode_o[2]}]
set_property SLEW SLOW [get_ports {tfdu_mode_o[2]}]

# F2 SD: J11-32 -> H16 bank 35
set_property PACKAGE_PIN H16 [get_ports {tfdu_sd_o[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_sd_o[2]}]
set_property DRIVE 4 [get_ports {tfdu_sd_o[2]}]
set_property SLEW SLOW [get_ports {tfdu_sd_o[2]}]

# F2 Rxd: J11-34 -> H15 bank 35
set_property PACKAGE_PIN H15 [get_ports {tfdu_rxd_i[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_rxd_i[2]}]

# F2 Txd: J11-36 -> K14 bank 35
set_property PACKAGE_PIN K14 [get_ports {tfdu_txd_o[2]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_txd_o[2]}]
set_property DRIVE 4 [get_ports {tfdu_txd_o[2]}]
set_property SLEW SLOW [get_ports {tfdu_txd_o[2]}]

# F3 Mode: J11-22 -> L16 bank 35
set_property PACKAGE_PIN L16 [get_ports {tfdu_mode_o[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_mode_o[3]}]
set_property DRIVE 4 [get_ports {tfdu_mode_o[3]}]
set_property SLEW SLOW [get_ports {tfdu_mode_o[3]}]

# F3 SD: J11-24 -> M17 bank 35
set_property PACKAGE_PIN M17 [get_ports {tfdu_sd_o[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_sd_o[3]}]
set_property DRIVE 4 [get_ports {tfdu_sd_o[3]}]
set_property SLEW SLOW [get_ports {tfdu_sd_o[3]}]

# F3 Rxd: J11-26 -> D19 bank 35
set_property PACKAGE_PIN D19 [get_ports {tfdu_rxd_i[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_rxd_i[3]}]

# F3 Txd: J11-28 -> E18 bank 35
set_property PACKAGE_PIN E18 [get_ports {tfdu_txd_o[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_txd_o[3]}]
set_property DRIVE 4 [get_ports {tfdu_txd_o[3]}]
set_property SLEW SLOW [get_ports {tfdu_txd_o[3]}]

# AX7020 onboard PL user LEDs: Bank 35, VCCO=3.3 V, active-low.
# Four-lane candidate maps one monitor-only LED to aggregate accepted activity per lane.
set_property PACKAGE_PIN M14 [get_ports {pl_activity_led_n_o[0]}]
set_property PACKAGE_PIN M15 [get_ports {pl_activity_led_n_o[1]}]
set_property PACKAGE_PIN K16 [get_ports {pl_activity_led_n_o[2]}]
set_property PACKAGE_PIN J16 [get_ports {pl_activity_led_n_o[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {pl_activity_led_n_o[*]}]
set_property DRIVE 4 [get_ports {pl_activity_led_n_o[*]}]
set_property SLEW SLOW [get_ports {pl_activity_led_n_o[*]}]
