# Release/methodology note:
# Do not apply a broad asynchronous clock group between clk_fpga_0 and the
# 64 MHz IR PHY clock. Vivado 2023.1 reports this as TIMING-24/TIMING-28
# because it overrides generated-IP set_max_delay -datapath_only constraints
# and references an auto-derived clock by name.
#
# CDC exceptions are kept point-to-point in PORT1.xdc and generated IP XDCs.
