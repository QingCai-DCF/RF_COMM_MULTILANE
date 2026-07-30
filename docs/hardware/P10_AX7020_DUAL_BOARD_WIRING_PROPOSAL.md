# P10 AX7020 dual-board J10 wiring proposal and audit

> Mapping status: user-confirmed. Hardware admission: **blocked** by `P10-SAFETY-POWERUP-001`.

The fixed-role board is proposed as `AX7020-F` with `F0/F1`; the stationary rotating-role board is proposed as `AX7020-R` with `R0/R1`. Lane 0 is `F0 ↔ R0` (A-to-A) and lane 1 is `F1 ↔ R1` (B-to-B). A/B cross-pairing is prohibited.

## Connector orientation

With J10 board silkscreen readable and the keyed shroud as photographed, pin 1 is the left near/lower-row corner marked '1'; pin 2 is directly above/far-row and marked '2'.

## Signal wiring

| Board role | Module | Lane | Signal | FPGA direction | Connector pin | Package pin | Bank | VCCO | IOSTANDARD | TFDU header/device pin | Reset/default | Pull | Source location | Notes |
|---|---|---:|---|---|---|---|---:|---:|---|---|---|---|---|---|
| fixed | F0 | 0 | Mode | output_to_tfdu | J10-30 | T12 | 34 | 3.3 V | LVCMOS33 | 8 / 7 | HIGH (static MIR/FIR); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| fixed | F0 | 0 | SD | output_to_tfdu | J10-32 | T11 | 34 | 3.3 V | LVCMOS33 | 7 / 5 | HIGH (shutdown); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| fixed | F0 | 0 | Rxd | input_from_tfdu | J10-34 | B19 | 35 | 3.3 V | LVCMOS33 | 5 / 4 | input; active-low; TFDU internal weak pull-up in shutdown | TFDU shutdown weak pull-up approximately 500 kohm; no AX7020 pull shown | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| fixed | F0 | 0 | Txd | output_to_tfdu | J10-36 | C20 | 35 | 3.3 V | LVCMOS33 | 3 / 3 | LOW; FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| fixed | F1 | 1 | Mode | output_to_tfdu | J10-22 | V17 | 34 | 3.3 V | LVCMOS33 | 8 / 7 | HIGH (static MIR/FIR); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| fixed | F1 | 1 | SD | output_to_tfdu | J10-24 | T14 | 34 | 3.3 V | LVCMOS33 | 7 / 5 | HIGH (shutdown); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| fixed | F1 | 1 | Rxd | input_from_tfdu | J10-26 | U13 | 34 | 3.3 V | LVCMOS33 | 5 / 4 | input; active-low; TFDU internal weak pull-up in shutdown | AX7020 R29 1 kohm pull-down to GND on IO1_12P, plus TFDU shutdown weak pull-up | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | Electrical guarantee gap: a 1 kohm pull-down requires about 3.3 mA at 3.3 V, outside the TFDU6102 guaranteed VOH test currents of 250/500 uA. |
| fixed | F1 | 1 | Txd | output_to_tfdu | J10-28 | V12 | 34 | 3.3 V | LVCMOS33 | 3 / 3 | LOW; FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| rotating_role | R0 | 0 | Mode | output_to_tfdu | J10-30 | T12 | 34 | 3.3 V | LVCMOS33 | 8 / 7 | HIGH (static MIR/FIR); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| rotating_role | R0 | 0 | SD | output_to_tfdu | J10-32 | T11 | 34 | 3.3 V | LVCMOS33 | 7 / 5 | HIGH (shutdown); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| rotating_role | R0 | 0 | Rxd | input_from_tfdu | J10-34 | B19 | 35 | 3.3 V | LVCMOS33 | 5 / 4 | input; active-low; TFDU internal weak pull-up in shutdown | TFDU shutdown weak pull-up approximately 500 kohm; no AX7020 pull shown | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| rotating_role | R0 | 0 | Txd | output_to_tfdu | J10-36 | C20 | 35 | 3.3 V | LVCMOS33 | 3 / 3 | LOW; FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| rotating_role | R1 | 1 | Mode | output_to_tfdu | J10-22 | V17 | 34 | 3.3 V | LVCMOS33 | 8 / 7 | HIGH (static MIR/FIR); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| rotating_role | R1 | 1 | SD | output_to_tfdu | J10-24 | T14 | 34 | 3.3 V | LVCMOS33 | 7 / 5 | HIGH (shutdown); FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |
| rotating_role | R1 | 1 | Rxd | input_from_tfdu | J10-26 | U13 | 34 | 3.3 V | LVCMOS33 | 5 / 4 | input; active-low; TFDU internal weak pull-up in shutdown | AX7020 R29 1 kohm pull-down to GND on IO1_12P, plus TFDU shutdown weak pull-up | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | Electrical guarantee gap: a 1 kohm pull-down requires about 3.3 mA at 3.3 V, outside the TFDU6102 guaranteed VOH test currents of 250/500 uA. |
| rotating_role | R1 | 1 | Txd | output_to_tfdu | J10-28 | V12 | 34 | 3.3 V | LVCMOS33 | 3 / 3 | LOW; FPGA-unconfigured/partial-power level not guaranteed by supplied schematics | no selected-signal pull shown; 33 ohm connector series resistor only | AX7020 schematic sheets 5 and 15; manual section 7.4 J10 table; TFDU datasheet pin table and electrical characteristics; SchDoc FileHeader records | No PL peripheral conflict shown on the selected J10 net. |

## Power, JTAG, UART, and pre-power checks

- Existing TFDU VCC/GND wiring remains user-owned and must not be altered under the current authorization.
- Any future connector change requires both AX7020 boards and all TFDU rails to be powered off.
- Before power-up: verify ground continuity, supply polarity, actual VCC1/VCC2 voltage/topology, no shorts, and all four passive Txd-low/SD-high states.
- Bind two distinct JTAG cable identities to AX7020-F and AX7020-R before programming either board.
- UART is role-local diagnostic output only; it cannot arm TX or bypass the final TX kill.
- A shutdown bitstream must drive both Txd outputs low and both SD outputs high, but it does not cure an unconfigured/partial-power electrical gap.

## Open items

- Severe blocker: no documented passive Txd pull-down or SD pull-up on any supplied TFDU small-board schematic.
- J10-26/U13 (F1/R1 Rxd) has AX7020 R29=1 kohm to ground; TFDU6102 high-level compliance is not guaranteed at that load.
- Actual AX7020-F/AX7020-R PCB revisions, FPGA markings, and unique JTAG identities remain unbound.
- Actual four-module markings/revisions and as-built VCC1/VCC2/harness bias remain undocumented.

## Hardware admission decision

`FAIL_CLOSED`: no hw_server/JTAG/program/ELF/UART/TFDU action is admitted until `P10-SAFETY-POWERUP-001` is resolved.
