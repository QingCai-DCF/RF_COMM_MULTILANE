# P8E common core clocks.  No board LOC or I/O electrical property belongs here.
# All P8E implementation wrappers expose the same three clock ports, so these
# commands are deliberately unconditional and remain valid XDC (not Tcl flow
# control embedded in an XDC file).
create_clock -name protocol_clk -period 15.625 [get_ports protocol_clk_i]
create_clock -name axis_dma_clk -period 10.000 [get_ports axis_dma_clk_i]
create_clock -name axi_lite_clk -period 20.000 [get_ports axi_lite_clk_i]
