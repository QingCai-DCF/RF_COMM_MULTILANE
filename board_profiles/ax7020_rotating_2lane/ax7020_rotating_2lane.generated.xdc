# Independently generated from AX7020 official references for P10_AX7020_ROTATING_2LANE.
# This is not copied from, sourced from, or validated by the AX7010 XDC.
# HARDWARE_ADMISSION=BLOCKED_PENDING_EXTERNAL_TXD_SD_FAILSAFE

# R0 Mode: J10-30 -> T12 bank 34
set_property PACKAGE_PIN T12 [get_ports {tfdu_mode_o[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_mode_o[0]}]
set_property DRIVE 4 [get_ports {tfdu_mode_o[0]}]
set_property SLEW SLOW [get_ports {tfdu_mode_o[0]}]

# R0 SD: J10-32 -> T11 bank 34
set_property PACKAGE_PIN T11 [get_ports {tfdu_sd_o[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_sd_o[0]}]
set_property DRIVE 4 [get_ports {tfdu_sd_o[0]}]
set_property SLEW SLOW [get_ports {tfdu_sd_o[0]}]

# R0 Rxd: J10-34 -> B19 bank 35
set_property PACKAGE_PIN B19 [get_ports {tfdu_rxd_i[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_rxd_i[0]}]

# R0 Txd: J10-36 -> C20 bank 35
set_property PACKAGE_PIN C20 [get_ports {tfdu_txd_o[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_txd_o[0]}]
set_property DRIVE 4 [get_ports {tfdu_txd_o[0]}]
set_property SLEW SLOW [get_ports {tfdu_txd_o[0]}]

# R1 Mode: J10-22 -> V17 bank 34
set_property PACKAGE_PIN V17 [get_ports {tfdu_mode_o[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_mode_o[1]}]
set_property DRIVE 4 [get_ports {tfdu_mode_o[1]}]
set_property SLEW SLOW [get_ports {tfdu_mode_o[1]}]

# R1 SD: J10-24 -> T14 bank 34
set_property PACKAGE_PIN T14 [get_ports {tfdu_sd_o[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_sd_o[1]}]
set_property DRIVE 4 [get_ports {tfdu_sd_o[1]}]
set_property SLEW SLOW [get_ports {tfdu_sd_o[1]}]

# R1 Rxd: J10-26 -> U13 bank 34
set_property PACKAGE_PIN U13 [get_ports {tfdu_rxd_i[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_rxd_i[1]}]

# R1 Txd: J10-28 -> V12 bank 34
set_property PACKAGE_PIN V12 [get_ports {tfdu_txd_o[1]}]
set_property IOSTANDARD LVCMOS33 [get_ports {tfdu_txd_o[1]}]
set_property DRIVE 4 [get_ports {tfdu_txd_o[1]}]
set_property SLEW SLOW [get_ports {tfdu_txd_o[1]}]

# AX7020 onboard PL user LEDs, official manual section 7.6.
# All four are Bank 35, VCCO=3.3 V, and active-low through the board LED load.
# LED1 = R0 TX; LED2 = R0 RX; LED3 = R1 TX; LED4 = R1 RX.
set_property PACKAGE_PIN M14 [get_ports {pl_activity_led_n_o[0]}]
set_property PACKAGE_PIN M15 [get_ports {pl_activity_led_n_o[1]}]
set_property PACKAGE_PIN K16 [get_ports {pl_activity_led_n_o[2]}]
set_property PACKAGE_PIN J16 [get_ports {pl_activity_led_n_o[3]}]
set_property IOSTANDARD LVCMOS33 [get_ports {pl_activity_led_n_o[*]}]
set_property DRIVE 4 [get_ports {pl_activity_led_n_o[*]}]
set_property SLEW SLOW [get_ports {pl_activity_led_n_o[*]}]
