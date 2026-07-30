# P10 required physical board/module evidence

The official AX7020 reference set is sufficient to derive the J10 package pins, banks, documented VCCO, and connector orientation. It does not identify the two physical boards or prove the as-built TFDU fail-safe network.

Required from the user before hardware admission:

- full model marking for both physical AX7020 boards;
- PCB revision/silkscreen for both boards;
- full FPGA top marking for both boards;
- clear front/back photographs of both boards, including J10 pin-1 markings;
- the official user manual and schematic revision that matches each physical PCB (the current local copies remain reference candidates);
- physical confirmation that J10 bank 34 and bank 35 VCCO are 3.3 V on both boards;
- clear front/back photographs and revision markings for F0, F1, R0, and R1;
- an as-built TFDU small-board schematic/pinout that identifies the mounted device as TFDU6102 rather than only a TFDU6108 library symbol;
- exact VCC1/VCC2 rail voltage and the actual R1/R6/decoupling population;
- exact Mode and SD structure;
- passive fail-safe component values and locations proving Txd LOW and SD HIGH for every module at reset, FPGA-unconfigured, open-circuit, and partial-power states;
- unique JTAG cable/target identifiers that bind the physical fixed and rotating-role boards.

Do not substitute zero, `unknown`, a similar board revision, or the AX7010 XDC for any missing item.
