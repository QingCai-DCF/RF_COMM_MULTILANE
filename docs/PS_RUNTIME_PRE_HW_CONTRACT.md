# PS Runtime Pre-HW Contract

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

Required future PS sequence:

1. reset core
2. write cfg registers
3. write lane masks
4. write session
5. write payload length
6. write retry/timeout/guard
7. commit toggle
8. readback verify
9. enable PHY
10. wait >= 500 us startup
11. clear telemetry counters only; never clear sticky safety faults or duty history
12. start bounded test
13. stop
14. force shutdown
15. read final counters
16. write evidence

P3 only documents and checks this sequence. P3 does not run PS code on hardware.
