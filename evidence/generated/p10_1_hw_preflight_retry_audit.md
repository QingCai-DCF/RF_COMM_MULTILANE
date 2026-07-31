# P10.1 hardware preflight retry audit

## Outcome

`P10_1_HARDWARE_ACCEPTANCE: FAIL`

The hardware campaign stopped after two distinct `preflight` run IDs. This is the hard limit in section 23 of the Goal (`每个 diagnostic stage 新 run_id <= 2`). No third hardware attempt was made, and no hardware PASS or P11 promotion is claimed.

Both attempts ended with verified shutdown on both AX7020 boards. Ethernet, movement, rotation, module exchange, and rewiring were not used. The maximum lane mask was `0x3`.

## Retry ledger

| Attempt | Run ID | Result | Terminal cause | Final shutdown |
|---|---|---|---|---|
| 1 | `p10_1_hw_20260731T211516Z_fd40629d_20ba7ef6_a1e3fbf5` | FAIL | XSDB used stale register-map identity constants and rejected the current PL version/hash before any case observation | fixed PASS; rotating PASS |
| 2 | `p10_1_hw_20260731T214947Z_ddf4a064_1585d1ad_9ad4f85f` | FAIL | `pattern_prbs_1m`: rotating receiver did not publish an XSDB-observable P10.1 `PRIMED` state before paired-source launch | fixed PASS; rotating PASS |

Attempt 2 first passed `preflight_identity`, `diagnostic_only_1byte`, `short_ring_wrap`, and `idle_heavy_5s`. The one-byte case proved a real fixed-to-rotating physical transfer with matching CRC32 and SHA256; it does not substitute for the failed command-13 or formal acceptance scope.

Raw evidence:

- Attempt 1: [XSDB result](../hardware/p10_1/p10_1_hw_20260731T211516Z_fd40629d_20ba7ef6_a1e3fbf5/stages/preflight/xsdb.result.txt), [orchestrator result](../hardware/p10_1/p10_1_hw_20260731T211516Z_fd40629d_20ba7ef6_a1e3fbf5/final/orchestrator_result.json)
- Attempt 2: [XSDB result](../hardware/p10_1/p10_1_hw_20260731T214947Z_ddf4a064_1585d1ad_9ad4f85f/stages/preflight/xsdb.result.txt), [stage summary](../hardware/p10_1/p10_1_hw_20260731T214947Z_ddf4a064_1585d1ad_9ad4f85f/stages/preflight/stage_summary.json), [orchestrator result](../hardware/p10_1/p10_1_hw_20260731T214947Z_ddf4a064_1585d1ad_9ad4f85f/final/orchestrator_result.json)

## Causal defect

The second run exposed a sufficient cache-coherency defect in command 13:

1. The P10.1 host-polled result page is at `0x00020400`.
2. The exact frozen BSP’s Cortex-A9 `translation_table.S` maps `0x00000000–0x3fffffff` as normal write-back cacheable memory.
3. Command 13 enables D-cache before publishing `PRIMING`, `PRIMED`, `RUNNING`, `VERIFYING`, `COMPLETE`, or `FAULT`.
4. The old publication helper wrote `service_state` and executed `dsb`, but did not clean the result page.
5. A DSB orders accesses; it does not itself clean a dirty write-back cache line for XSDB physical-memory polling.

Consequently, the host had no guarantee of observing the `PRIMED` transition that gates paired-source launch. This is a proven software defect sufficient to cause the observed timeout. It is not claimed as the sole hardware cause because the failed run did not capture the live P10.1 result page before fail-closed shutdown.

The exact BSP archive is SHA256 `ce07b946468f167abff530a5be3786ce6e983f2a3f203deb2bfc27aca4e141d8`; its `translation_table.S` member is SHA256 `7ccfa42671763772fbee72b2bb6073a7d8839118bba0d00d2a59577c634c72f3`.

## Offline remediation

Source checkpoint: `bfff483663e51862a0e1e4aed31940bd84d80cdb`

The state word is now written last, then the complete 912-byte P10.1 result record is cleaned with `Xil_DCacheFlushRange` whenever D-cache is enabled, followed by the final DSB. XSDB prime-timeout errors now preserve the main mailbox, PL, PHY, and P10.1 state/status/sequence values.

Focused unit tests, both role-bound Vitis builds, ELF disassembly checks, and immutable artifact finalization passed offline. The remediated ELF hashes are:

- fixed: `5dbf7e2668b1ddac9f742085d907c90324b7ca931dc47e932ae70dcd8881f4e6`
- rotating: `9b9bef44b65b3f08ca9442d2d577bdbdc79db2d2d8da3991eb93a4b1dd5946a0`

These new ELFs have no hardware PASS. The earlier hardware observations apply only to their originally authorized artifacts.

## Required next action

Before any third `preflight` run ID, the user must explicitly extend or override the Goal’s two-run diagnostic-stage limit. Until then:

- `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`
- no further JTAG/program/ELF/TFDU action is permitted
- P10.1 hardware acceptance remains FAIL
- P11 remains not promoted

The machine-readable audit is [p10_1_hw_preflight_retry_audit.json](p10_1_hw_preflight_retry_audit.json).
