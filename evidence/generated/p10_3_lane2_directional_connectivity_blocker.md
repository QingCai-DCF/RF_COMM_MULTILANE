# P10.3 lane2 directional connectivity blocker audit

`P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE=FAIL`

`CLASSIFICATION=FAIL_RAW_PHYSICAL_DIRECTION_R2_TO_F2`

`EVIDENCE_LEVEL=RAW_PHYSICAL_ONLY`

The corrected immutable P10.3 campaign reached direct lane2 module-intake traffic. `F2 -> R2` passed the 64-pulse and 1024-pulse raw cases. The reciprocal `R2 -> F2` 64-pulse case failed: the fixed receiver reached only 5 of the requested 64 raw events, returned command status 14 (`RAW_TIMEOUT`) in service state 5, while the rotating sender returned status 0 in state 4. Both endpoints reported a zero PHY safety-fault mask and zero lane2 hard-fault count.

This is a direction-specific end-to-end raw failure. It does **not** uniquely identify R2 TX, F2 RX, the optical path/alignment, power, or interconnect as the faulty component. No individual module is declared defective from this evidence alone.

## Executed cases

| Direction / case | Result | Direct evidence |
|---|---|---|
| F2 -> R2 raw64 | PASS | immutable `P10_CASE_PASS=intake_F2_raw_64` |
| F2 -> R2 raw1024 | PASS | immutable `P10_CASE_PASS=intake_F2_raw_1024` |
| R2 -> F2 raw64 | FAIL | fixed receiver 5/64; status 14/state 5; rotating sender status 0/state 4 |
| R2 -> F2 raw1024 | NOT_RUN | fail-fast after raw64 failure |
| F3/R3 intake vector | NOT_RUN | fail-fast before lane3 cases |

The passing F2 cases observed an 8-cycle maximum TX-high pulse at 64 MHz (125 ns) and a peak rolling-duty count of 504/64000 (0.7875%). No executed case reported a pulse-width, rolling-duty, stuck-high, or PHY safety fault. This is not proof that either TFDU module is undamaged.

## Acceptance impact

- F2, R2, F3, and R3 do not have complete mandatory intake vectors and therefore are not accepted for P10.3 formal use.
- The 8x8 matrix, per-lane 4 Mbit/s, four-lane RAW, mask/degrade, ARQ/SACK, DMA, 64 MiB streaming, 8 Mbit/s application test, and 1800-second formal run were not executed.
- P10.3 remains `IN_PROGRESS`; no hardware PASS or pass tag is generated.
- The consumed current-run authorization is false. No additional hardware run is authorized by this record.

## Safety and scope closure

The maximum used lane mask was `0x4`. No Ethernet, movement, rotation, realignment, rewiring, two-hour test, or P11 action occurred. Initial, before/after-stage, and final-emergency shutdown checks all passed for both JTAG-bound boards:

- fixed: `AX7020-F/JTAG:210249855178`
- rotating: `AX7020-R/JTAG:210512180081`

## Immutable evidence

- Run: `p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef`
- Source commit: `d4eef729e91c60fc7a72fa68c95fcd4a569fcffc`
- Goal SHA256: `6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281`
- Module intake summary: `evidence/hardware/p10_3/p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef/module_intake/stage_summary.json` (`3c3b8db1b03f6282a88b64a3668ecfe226bd60b5082b8d7ab687c45750bcb445`)
- Final result: `evidence/hardware/p10_3/p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef/final/orchestrator_result.json` (`77890560e2c9781e3c2a60461c7575b4c9c87b78a4d8a07b3bb7fc70774ecb9e`)
- Shutdown summary: `evidence/hardware/p10_3/p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef/shutdown/summary.json` (`90840753a15eeae0de143249ca8c61ebd9162118f8b6114ef538f3e76c06894b`)
- Run manifest: `evidence/hardware/p10_3/p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef/final/run_evidence_sha256_manifest.json` (`191975aab14d10af6dac2880f6169607a0b80f48fac2781e912cfab715b04b0f`)

## Required next action

Manual physical handling is required before a meaningful retry. With power removed, the user must inspect or correct the R2-to-F2 optical path and the R2 transmitter/F2 receiver hardware, or authorize a controlled swap/replacement diagnostic. A subsequent run requires a fresh current-run authorization and must repeat the immutable module intake from shutdown-before.
