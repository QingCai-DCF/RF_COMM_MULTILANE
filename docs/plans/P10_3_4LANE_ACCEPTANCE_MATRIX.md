# P10.3 four-lane acceptance matrix

| Stage | Direct evidence | Fail-closed condition |
|---|---|---|
| 00–05 | exact board/module/wiring/artifact identities; safe idle and per-module intake | any pending or quarantined identity |
| 06 | 64-cell TX-source × RX-observation raw/accepted matrix | any non-target CRC-valid accepted frame or same-module accepted DATA |
| 07–10 | per-lane raw/frame counts, pulse width, duty, guard and integrity | missing direction or any safety/integrity fault |
| 11 | frozen lane0/lane1 regression | mismatch with scoped two-lane contract |
| 12 | four-lane physical counters and timing | RAW capability not directly demonstrated |
| 13–14 | masks `0x1..0xF`, fairness, migration, degradation and recovery | healthy-lane block, ACKed migration, duplicate/stale commit |
| 15 | 64 MiB input/output CRC32+SHA256 and atomic commit | partial, duplicate or stale commit; descriptor leak |
| 16–17 | remote-verified application bytes over remote-confirmed elapsed time | either direction below 8 Mbit/s |
| 18 | 30-minute stationary counters and integrity | any reset, fault, integrity mismatch or missing shutdown |
| 19–20 | dual shutdown marker and immutable evidence manifest | shutdown unconfirmed or evidence inconsistent |
