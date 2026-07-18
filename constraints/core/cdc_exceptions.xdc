# CDC-001: exact named domain relationships only.  Crossings between these
# groups must use rtl/common primitives and are audited with report_cdc.
set_clock_groups -asynchronous \
  -group [get_clocks protocol_clk] \
  -group [get_clocks axis_dma_clk] \
  -group [get_clocks axi_lite_clk]
