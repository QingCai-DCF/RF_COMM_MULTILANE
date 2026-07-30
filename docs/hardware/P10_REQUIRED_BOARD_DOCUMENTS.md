# P10 remaining board and safety evidence

The official AX7020 reference set is sufficient to derive the J10 package pins, banks, documented VCCO, connector orientation, and independent AX7020 XDCs. The user confirms that all four TFDU small boards previously operated on AX7010 and does not require renewed small-board identity inspection. The supplied comparison records byte-identical AX7010/AX7020 base-PCB J10 design files.

Required before any programming or TFDU-driving hardware action in P10:

- explicit F/R role assignment for the two read-only-enumerated JTAG cable serials recorded in `config/hardware/p10_jtag_identity_inventory.json`;

Current role state: `BOUND_EXPLICIT_SERIAL_TO_ROLE: AX7020-F=210249855178, AX7020-R=210512180081`.

Retained for D17/final-hardware closure, but not required to start the already-powered no-intentional-power-cycle P10 campaign:

- as-built fail-low circuit/bias evidence for open-circuit, FPGA-unconfigured, and relevant partial-power sequences;
- bounded external Txd/SD measurements for those sequences;
- physical GLOBAL_PERMIT/final-kill circuit, readback, and deassertion-latency evidence.

These items remain `PENDING_D17`; P10 does not claim they pass. No rewire is authorized by the fast-track.

Nonblocking documentation gaps retained for provenance:

- physical AX7020 PCB revision/silkscreen and FPGA top marking;
- front/back photographs of the two AX7020 boards;
- direct physical confirmation of bank 34/35 VCCO and VCC1/VCC2 rail values.

Not requested again for P10 per the user's 2026-07-30 clarification:

- TFDU module front/back photographs;
- renewed TFDU module marking or PCB-revision confirmation;
- renewed proof that the modules functioned on AX7010.

Do not substitute zero, `unknown`, target order, a similar board revision, or the AX7010 XDC for a missing identity or electrical value.
