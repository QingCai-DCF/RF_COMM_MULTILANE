# Z7010 core timing profile.  HD.CLK_SRC describes abstract OOC BUFG entry,
# not a package pin; actual TFDU LOC/IOSTANDARD remain in the canonical board XDC.
set_property HD.CLK_SRC BUFGCTRL_X0Y0 [get_ports protocol_clk_i]
set_property HD.CLK_SRC BUFGCTRL_X0Y1 [get_ports axis_dma_clk_i]
set_property HD.CLK_SRC BUFGCTRL_X0Y2 [get_ports axi_lite_clk_i]
