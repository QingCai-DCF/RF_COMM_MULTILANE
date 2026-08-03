# P10.1R current physical blocker

`P10_1R_STATUS: PARTIAL`

`BLOCKER: F1_TO_R1_RAW_PHYSICAL_PATH`

The latest complete four-direction matrix used the frozen `cce2180b` artifacts and an additional 5 ms receiver-settle interval after the rotating R1 endpoint reported receiver-primed. The result was unchanged:

| Direction | Result |
|---|---|
| F0 to R0 | PASS, 1000/1000 |
| R0 to F0 | PASS, 1000/1000 |
| F1 to R1 | FAIL at sample 0 |
| R1 to F1 | PASS, 1000/1000 |

For the failing direction, the fixed FPGA recorded final lane1 physical TX activity and same-module raw activity, while the rotating FPGA lane1 raw counter remained zero. This excludes a missing final FPGA TX event and shows that adding receiver startup margin did not restore the path. It does not uniquely distinguish the fixed F1 optical transmitter, rotating R1 optical receiver, their existing external electrical connections, or the optical path.

The board serial binding and artifact hashes were exact. No Ethernet, motion, rotation, alignment change, obscuration, module exchange, or rewiring was performed. Both role-bound shutdown images were programmed after the run; fixed and rotating shutdown were PASS with `TFDU_SHUTDOWN_PROGRAMMED=1` and `SHUTDOWN_EXIT=0`.

Further ACK/window tuning, performance, 64 MiB streaming, recovery, and formal acceptance would substitute protocol failures for the missing raw direction and therefore must not proceed.

## Required manual action

With both boards powered off, inspect and restore the existing fixed F1/J10-B transmit path and rotating R1/J10-B receive path:

- fixed F1 module seating and existing VCC/GND, SD, Mode, and Txd connections;
- rotating R1 module seating and existing VCC/GND, SD, Mode, and Rxd connections;
- the stationary F1-to-R1 optical path without moving the boards or changing the optical geometry unless that additional scope is explicitly authorized.

After the inspection, report that it is complete. The next Codex run will create a fresh immutable current-run authorization and repeat the four-direction raw matrix before resuming the P10.1R campaign.

Machine-readable evidence: `evidence/generated/p10_1r_current_physical_blocker.json`

Latest raw run: `evidence/hardware/p10_1r/p10_1r_20260803T064202Z_cce2180b_c1370686_bfb1c51d/`
