# P10.3 lane2 software-path audit

`P10_3_ACCEPTANCE=FAIL`

`SOFTWARE_DIRECTION_CONTROL=PASS`

`COMPONENT_ATTRIBUTION=INDETERMINATE_EXTERNAL_PATH`

`CURRENT_RUN_HARDWARE_AUTHORIZATION=false`

`HARDWARE_ACTIONS_EXECUTED_THIS_AUDIT=false`

The offline trace closes the suspected host/firmware direction-control question: the failed case was planned as direction 1 on mask `0x4`; XSDB primed fixed as the receiver and launched rotating as the sender; the role-bound rotating firmware alone issued `START_RAW`; and the eight-module P10.2 snapshot recorded 64 rotating R2 final-path digital TX edges. The fixed F2 raw-RX counter recorded only 5 edges. Therefore the latest 5/64 failure was not created by reversing the sender and receiver in the runner.

This does not identify a failed component. The 64-count TX telemetry is an internal post-safety Txd rising-edge count, not an oscilloscope measurement at J11 or proof of optical emission. The remaining boundary includes R2 transmitter/power/interconnect, the R2-to-F2 optical path, and F2 receiver/power/interconnect.

## Direct evidence

| Case | Sender telemetry | Paired remote raw telemetry | Result |
|---|---:|---:|---|
| F2 -> R2 raw64 | F2 = 64 | R2 = 64 | PASS |
| F2 -> R2 raw1024 | F2 = 1024 | R2 = 1024 | PASS |
| R2 -> F2 raw64 | R2 = 64 | F2 = 5 | FAIL |

For `intake_R2_raw_64`, the rotating endpoint completed with status 0/state 4; the fixed endpoint timed out with status 14/state 5. Both endpoint PHY safety masks and both lane2 hard-fault counts were zero. These are raw pulse observations, not valid-frame or external electrical/optical evidence.

The immutable sources are:

- module-intake summary: `evidence/hardware/p10_3/p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef/module_intake/stage_summary.json` (`3c3b8db1b03f6282a88b64a3668ecfe226bd60b5082b8d7ab687c45750bcb445`)
- XSDB result: `evidence/hardware/p10_3/p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef/module_intake/xsdb.result.txt` (`af6f074525d7b2bf64e698f30e2ab986b8030cc6f7ad544cff6099e3685deb69`)
- shutdown summary: `evidence/hardware/p10_3/p10_3_20260804T101727Z_d4eef729_3d8cd207_a8459eef/shutdown/summary.json` (`90840753a15eeae0de143249ca8c61ebd9162118f8b6114ef538f3e76c06894b`)

## Software trace

1. `scripts/run_p10_3_ax7020_4lane_hardware.py:515` generates R2 as direction 1, lane mask `0x4`.
2. `scripts/hw/p10_dual_xsdb_stage.tcl:484` maps direction 1 to rotating sender and fixed receiver; the immutable log contains `P10_PAIRED_LAUNCH=intake_R2_raw_64:receiver=fixed,sender=rotating`.
3. `software/ps_driver/p9_runtime_main.c:227` binds fixed role 1 to direction 0 and rotating role 2 to direction 1. Only the local sender writes `START_RAW`; sender completion requires `RAW_DONE` plus the exact requested count, while the receiver waits on its selected local raw count.
4. `rtl/p9_optical_transport_core.sv:1272` routes direction 1 raw pulses to the B path, applies the lane mask, and passes the request through arm/kill/pulse/duty safety. The diagnostic pulse is eight 64 MHz cycles, or 125 ns.
5. `rtl/tfdu_lane_phy.sv:168` counts Txd rising edges and synchronized active-low Rxd falling edges. The counters are digital telemetry and do not replace external probing.
6. Both independent AX7020 XDCs map lane2 J11-A to Mode G17, SD H16, Rxd H15, and Txd K14 using LVCMOS33.

## Host-evidence guard

A separate latent issue was found in the shared legacy evaluator: its raw matrix assumed the two-lane `F0/F1/R0/R1` mailbox layout. P10.3 did not use that matrix for its lane2 verdict; it uses its own eight-module snapshots. Commit `634ed8b94ca86e8e0c4834dd7c68bf41dd777891` now makes the shared evaluator fail closed for any non-two-lane role contract and has a focused regression test.

Focused verification passed 21/21 tests, Python compilation passed, and the no-hardware checker returned `NO_HARDWARE_ACTIONS_EXECUTED=1`. The repository-wide suite remains red at 528 tests with 18 failures and 17 errors; that failure is preserved and no P10.3 promotion is claimed.

## Remaining acceptance

F2 and R2 lack complete intake vectors; R2 additionally has the direct reverse-direction raw failure. F3/R3 were not reached. The 8x8 matrix, per-lane 4 Mbit/s, two-lane regression, four-lane RAW, mask/degrade, ARQ/SACK, DMA, 64 MiB streaming, 8 Mbit/s application targets, and 30-minute run remain `NOT_RUN`.

The current authorization is consumed and false, and the recorded retries have reached or exceeded the bounded campaign policy. No additional hardware attempt is permitted from this record. The next meaningful step requires powered-off inspection/correction of the external R2-to-F2 path or an explicitly authorized controlled isolation procedure, followed by a retry-limit override and a new machine-readable current-run authorization.
