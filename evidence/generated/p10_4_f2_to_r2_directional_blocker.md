# P10.4 F2→R2 directional blocker

Status: `FAIL_CLOSED_PHYSICAL_DIRECTIONAL_BLOCKER`

Run: `p10_4_20260806T034503Z_6ff17d33_94506af9_2b2b37d4`

## Direct observation

The current immutable P10.4 bundle was run on the fixed board `210249855178` and rotating-role board `210512180081` with lane mask `0xF`.

| Direction | Lane-2 sender physical TX | Lane-2 receiver raw RX | Application goodput | Retries/timeouts/migrations | Result |
|---|---:|---:|---:|---:|---|
| F2 (`B0001`) → R2 (`B0023`) | 5,324,445 | 99 | 1,005,824.408 bps | 5,076 / 5,076 / 5,076 | FAIL: selected lane made no progress |
| R2 (`B0023`) → F2 (`B0001`) | 4,450,326 | 4,450,326 | 9,265,725.556 bps | 0 / 0 / 0 | PASS: directional raw progress |

The same exact bitstreams, ELFs, board binding, lane mapping, and runtime configuration therefore exhibit a current unidirectional physical loss from F2 to R2. Cross-lane retry recovered the transferred object, but the four-lane mandatory counter-semantics gate correctly failed because lane2 itself made no usable receive progress.

This is direct FPGA counter evidence. It is not an external electrical or optical measurement, and it does not identify which physical component is defective.

## Safety and terminal disposition

- Safety, integrity, and descriptor counters remained zero, including CRC bad, SHA mismatch, retry exhausted, duty violation, and continuous-high violation.
- Neither endpoint recorded a first safety fault (`NO_FAULT`); loss of lane progress was detected by the stage evaluator.
- New TX was stopped and the authorization was consumed as `CONSUMED_AFTER_P10_4_FAIL`.
- Both independent shutdown bitstreams were programmed and verified: fixed `PASS`, rotating `PASS`, `TFDU_SHUTDOWN_PROGRAMMED=1`, `SHUTDOWN_EXIT=0`.
- No Ethernet, movement, rewiring, module replacement, or external instrumentation was used.
- The Goal forbids the physical action needed to eliminate this blocker. No further hardware retry is permitted in this task.

## Evidence

- Raw stage: `evidence/hardware/p10_4/p10_4_20260806T034503Z_6ff17d33_94506af9_2b2b37d4/stages/counter_semantics/stage_summary.json`
- Final result: `evidence/hardware/p10_4/p10_4_20260806T034503Z_6ff17d33_94506af9_2b2b37d4/final/orchestrator_result.json`
- Final result SHA256: `d7461aeeaf288bfdf07f9ce5f615801df2a16c7952be1919781c856df8623077`
- Manifest: `evidence/hardware/p10_4/p10_4_20260806T034503Z_6ff17d33_94506af9_2b2b37d4/final/run_evidence_sha256_manifest.json`
- Manifest SHA256: `74bc79ca7a01dc3ea0db12b7507988dff5654fd32af285e0fbb36607246e8f26`
