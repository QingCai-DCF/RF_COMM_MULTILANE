# P10.2 stationary four-lane physical layout guide

This guide is an offline wiring aid, not permission to power, program or transmit.

## Labels and lane geometry

Use `AX7020-F` with F0/F1 on J10-A/B and F2/F3 on J11-A/B. Use `AX7020-R` with R0/R1 on J10-A/B and R2/R3 on J11-A/B. Pair only F0-R0, F1-R1, F2-R2 and F3-R3. Label both ends of every Mode/SD/Rxd/Txd conductor and every power/return harness.

Keep every paired module at a fixed, unobstructed, face-to-face orientation. Route signal and power harnesses so they cannot shade an aperture or pull a module out of alignment. Separate high-current supply/return bundles from Rxd signal runs; use a short low-impedance return for each module and join at a documented star point.

## Harness identifiers

Signal harness IDs are `F0-SIG` through `F3-SIG` and `R0-SIG` through `R3-SIG`. Power harness IDs are the corresponding `-PWR` and `-RET`. J10-A/B retain the accepted P10.1R pin pattern. J11-A/B use the identical logical order at J11 pins 30/32/34/36 and 22/24/26/28.

## Mandatory sequence

1. Switch off both AX7020 boards and all TFDU supplies; verify absence of voltage before inserting, moving or measuring continuity on a harness.
2. Quarantine the original F1 in a separately marked container. It may not occupy any F/R slot.
3. Verify board and module labels, actual PCB revisions, connector names, pin-1 marks, polarity and signal direction against the frozen proposal.
4. Check continuity end-to-end and verify no short between adjacent connector pins, 3.3 V and GND, or any signal and a power rail.
5. Verify the external module supply current rating, decoupling, star returns and planned droop measurement points. Do not assume a J10/J11 3.3-V pin is a four-module power feed.
6. Photograph and record the completed unpowered layout. During any future formal run, do not move, rotate, re-aim, shade, swap or rewire anything.
7. A future separately authorized P10.3 run starts with role-bound shutdown programming, verified Txd-low/SD-high, one-module intake, then 1 -> 2 -> 4 lane escalation. Never jump directly to four simultaneous transmitters.
