# Exact-part rotating core profile.  Board pins and external I/O delays are
# intentionally PENDING_D12 and are not fabricated here.
set_property HD.CLK_SRC BUFGCTRL_X0Y0 [get_ports protocol_clk_i]
set_property HD.CLK_SRC BUFGCTRL_X0Y1 [get_ports axis_dma_clk_i]
set_property HD.CLK_SRC BUFGCTRL_X0Y2 [get_ports axi_lite_clk_i]
