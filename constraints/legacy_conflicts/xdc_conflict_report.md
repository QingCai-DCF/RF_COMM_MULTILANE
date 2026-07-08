# XDC Conflict Report

IP legacy PORT1.xdc differs from active top PORT1.xdc.
Do not use IP legacy PORT1.xdc in new builds.
Use canonical generated XDC from the pinmap for new builds.

XDC_GENERATED_FROM_PINMAP=1
XDC_GENERATED_MATCHES_ACTIVE_REFERENCE=1
XDC_LEGACY_CONFLICT_RECORDED=1
NO_LEGACY_PORT1_XDC_IN_BUILD=1

## Notable Differences
- `ir_mode_out_0[0]` active={'PACKAGE_PIN': 'T12', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'V17', 'IOSTANDARD': 'LVCMOS33'}
- `ir_rx_in_0[0]` active={'PACKAGE_PIN': 'B19', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'U13', 'IOSTANDARD': 'LVCMOS33'}
- `ir_sd_0[0]` active={'PACKAGE_PIN': 'T11', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'T14', 'IOSTANDARD': 'LVCMOS33'}
- `ir_tx_out_0[0]` active={'PACKAGE_PIN': 'C20', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'V12', 'IOSTANDARD': 'LVCMOS33'}
- `loop_mode_b0[0]` active={'PACKAGE_PIN': 'V17', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'T12', 'IOSTANDARD': 'LVCMOS33'}
- `loop_rx_b0[0]` active={'PACKAGE_PIN': 'U13', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'B19', 'IOSTANDARD': 'LVCMOS33'}
- `loop_rx_b0[1]` active={'PACKAGE_PIN': 'G15', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'D19', 'IOSTANDARD': 'LVCMOS33'}
- `loop_sd_b0[0]` active={'PACKAGE_PIN': 'T14', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'T11', 'IOSTANDARD': 'LVCMOS33'}
- `loop_tx_b0[0]` active={'PACKAGE_PIN': 'V12', 'IOSTANDARD': 'LVCMOS33'} legacy={'PACKAGE_PIN': 'C20', 'IOSTANDARD': 'LVCMOS33'}

`loop_rx_b0[1]` differs between active and IP legacy XDC. Treat the active top XDC as the imported reference and keep IP legacy XDC out of new builds.
Plan note: older written plans mention D19 versus G15; this imported active file is authoritative for this workspace, and the exact active/legacy values above are the evidence.
