# P10 wiring design audit

The confirmed J10 A/B mapping is independently supported by the AX7020 manual, schematic, and pin workbook. Both role-specific pinmaps/XDC files use `xc7z020clg400-2`, LVCMOS33, bank 34/35 at documented 3.3 V, and do not source the AX7010 XDC.

Mapping is complete, but hardware admission fails closed:

- `P10-SAFETY-POWERUP-001`: no passive Txd-low/SD-high guarantee in reset/fault, unconfigured, or partial-power states.
- `P10-RX-B-R29-001`: J10-26/U13 Rxd is loaded by R29=1 kohm to ground, outside the TFDU6102 guaranteed VOH test load; user-confirmed prior AX7010 operation on the byte-identical base/J10 circuit supplies empirical compatibility context.
- physical F/R role binding by JTAG cable serial is pending: `ENUMERATED_UNASSIGNED: 210249855178, 210512180081`.
- TFDU small-board identity is accepted from user-confirmed prior operation; renewed marking/revision/photo checks are not required.

Result: `FAIL_CLOSED_SEVERE_BLOCKER` for programming and active hardware; bounded read-only JTAG identity enumeration is allowed. Artifact-generation hardware actions executed: `false`.
