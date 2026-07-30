# P10 wiring design audit

The confirmed J10 A/B mapping is independently supported by the AX7020 manual, schematic, and pin workbook. Both role-specific pinmaps/XDC files use `xc7z020clg400-2`, LVCMOS33, bank 34/35 at documented 3.3 V, and do not source the AX7010 XDC.

Mapping is complete, but hardware admission fails closed:

- `P10-SAFETY-POWERUP-001`: no passive Txd-low/SD-high guarantee in unconfigured/open-circuit/partial-power states.
- `P10-RX-B-R29-001`: J10-26/U13 Rxd is loaded by R29=1 kohm to ground, outside the TFDU6102 guaranteed VOH test load.
- physical F/R board identity and JTAG cable binding are pending.

Result: `FAIL_CLOSED_SEVERE_BLOCKER`; hardware actions executed: `false`.
