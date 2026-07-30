# P10 remaining board and safety evidence

The official AX7020 reference set is sufficient to derive the J10 package pins, banks, documented VCCO, connector orientation, and independent AX7020 XDCs. The user confirms that all four TFDU small boards previously operated on AX7010 and does not require renewed small-board identity inspection. The supplied comparison records byte-identical AX7010/AX7020 base-PCB J10 design files.

Required before any programming or TFDU-driving hardware action:

- two distinct live JTAG cable serials, each explicitly bound to AX7020-F or AX7020-R;
- existing circuit or measurement evidence that every physical Txd remains LOW during reset/fault, FPGA-unconfigured, and partial-power conditions;
- safe external measurement evidence for the Txd/SD states above, or a separately authorized documented fail-safe hardware revision (the current goal prohibits rewiring).

Nonblocking documentation gaps retained for provenance:

- physical AX7020 PCB revision/silkscreen and FPGA top marking;
- front/back photographs of the two AX7020 boards;
- direct physical confirmation of bank 34/35 VCCO and VCC1/VCC2 rail values.

Not requested again for P10 per the user's 2026-07-30 clarification:

- TFDU module front/back photographs;
- renewed TFDU module marking or PCB-revision confirmation;
- renewed proof that the modules functioned on AX7010.

Do not substitute zero, `unknown`, target order, a similar board revision, or the AX7010 XDC for a missing identity or electrical value.
