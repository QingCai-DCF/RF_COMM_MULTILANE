# P10.2 new-module intake plan

F2, F3, R2 and R3 are placeholders only. None is accepted for a future four-lane run until its own immutable intake record contains the actual small-board revision, TFDU marking/lot, front/back photographs, header pinout, VCC/GND continuity and static-short measurements, VCC1/VCC2 structure, SD/Mode structure, Txd input path, Rxd output path, decoupling inventory and durable module label.

The original failed `F1_ORIGINAL` is `QUARANTINED_NOT_ACCEPTED`; it cannot be a spare and cannot be relabeled as F2, F3, R2 or R3. The currently accepted lane1 identity is the replacement F1 recorded by the immutable P10.1R evidence.

For each new module, the later authorized P10.3 sequence is safe idle, receive-only, 64 bounded raw pulses, 1024 bounded raw pulses, then a 4 Mbit/s frame smoke. Every transition uses shutdown-before and verified shutdown-after. Any identity mismatch, unsafe idle level, short, supply droop, duty/stuck-high event, unexpected accepted echo or missing shutdown marker quarantines that module; it does not become accepted by analogy with another module.
