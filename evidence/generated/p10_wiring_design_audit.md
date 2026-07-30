# P10 wiring design audit

The confirmed J10 A/B mapping is independently supported by the AX7020 manual, schematic, and pin workbook. Both role-specific pinmaps/XDC files use `xc7z020clg400-2`, LVCMOS33, bank 34/35 at documented 3.3 V, and do not source the AX7010 XDC.

Mapping is complete. Current admission findings:

- `P10-SAFETY-POWERUP-001`: `PENDING_D17_NONBLOCKING_FOR_P10_SCOPED_NO_POWER_CYCLE_RUN`. Configured reset/fault and shutdown images are Txd-low/SD-high; ordinary configuration is optically inhibited by SD-high; FPGA-unconfigured/partial-power fail-low stays PENDING_D17.
- `P10-RX-B-R29-001`: J10-26/U13 Rxd is loaded by R29=1 kohm to ground, outside the TFDU6102 guaranteed VOH test load; user-confirmed prior AX7010 operation on the byte-identical base/J10 circuit supplies empirical compatibility context.
- physical F/R role binding by JTAG cable serial: `ENUMERATED_UNASSIGNED: 210249855178, 210512180081`.
- TFDU small-board identity is accepted from user-confirmed prior operation; renewed marking/revision/photo checks are not required.

Result: `FAIL_CLOSED_PENDING_ROLE_BINDING`. Artifact generation itself executed no hardware action. Every active stage still requires shutdown-before/on-error/after and the no-intentional-power-cycle scope.
