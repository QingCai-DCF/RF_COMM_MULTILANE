# Four-direction physical-connectivity retest — 2026-08-03

```text
FOUR_DIRECTION_CONNECTIVITY_RESULT=PASS
EVIDENCE_LEVEL=RAW_PHYSICAL_ONLY
F0_TO_R0=PASS_1000_OF_1000
R0_TO_F0=PASS_1000_OF_1000
F1_TO_R1=PASS_1000_OF_1000
R1_TO_F1=PASS_1000_OF_1000
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
CURRENT_RUN_HARDWARE_AUTHORIZATION=false
```

## Outcome

The fresh role-bound run directly retested all four stationary physical directions with the frozen P10.1R AX7020 artifacts. Every direction completed 1000/1000 intended remote raw observations:

| Physical direction | Lane | Result | Remote raw | Violations |
|---|---:|---:|---:|---:|
| `F0 -> R0` | lane0 | `PASS` | 1000 | 0 |
| `R0 -> F0` | lane0 | `PASS` | 1000 | 0 |
| `F1 -> R1` | lane1 | `PASS` | 1000 | 0 |
| `R1 -> F1` | lane1 | `PASS` | 1000 | 0 |

The run recorded 4000 total remote raw observations, 4000 same-module local raw echoes, zero same-module accepted events, zero cross-lane/admission violations, and a maximum measured echo tail of zero protocol cycles. The configured 4096-cycle guard therefore retains its full deterministic margin for this measurement.

## Evidence boundary

This is `RAW_PHYSICAL_ONLY` evidence. It directly supports present bidirectional raw physical connectivity for lane0 (`F0-R0`) and lane1 (`F1-R1`) under the tested stationary setup. It does not by itself prove CRC-valid DATA transfer, application goodput, streaming integrity, long-duration stability, external optical power, or final P10.1R acceptance.

The earlier `F1 -> R1` failures are preserved in [the historical blocker record](../evidence/generated/p10_1r_lane1_directional_blocker.json). This fresh run supersedes that record only for the current raw-connectivity verdict. No evidence identifies why the physical state changed after the earlier failed run.

## Frozen binding

| Item | Value |
|---|---|
| Fixed board | `AX7020-F/JTAG:210249855178` |
| Rotating-role board | `AX7020-R/JTAG:210512180081` |
| Artifact source | `cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d` |
| Fixed bitstream | `c13706860a003721d45e9a6fd90f444825aaa1b342a74a095079eceffa856a27` |
| Rotating bitstream | `bfb1c51d639188ea60392c8ceb39b25276e12b819c8e2ee0c5ae3ef63497639f` |
| Fixed ELF | `0d3963ce7fbcaab95373ebec97f4c62712bd216f041a23547c9006024e219db4` |
| Rotating ELF | `5abf3d3d597b14e182d07665609a8dd8ff05d7c6159fd2deb1f81813723c035e` |

Primary evidence:

- [stage summary](../evidence/hardware/p10_1r/p10_1r_20260803T053211Z_cce2180b_c1370686_bfb1c51d/echo_tail/stage_summary.json), SHA256 `afebdcc5121df41e0a28fb7fa261ff1cc6e16fe50539d98ffcb6a05e9b705235`;
- [XSDB transcript](../evidence/hardware/p10_1r/p10_1r_20260803T053211Z_cce2180b_c1370686_bfb1c51d/echo_tail/xsdb.result.txt), SHA256 `c4b4418f1e8b11c4be7a992996b259115a4247649c7cc77fd13572e36135811b`;
- [orchestrator result](../evidence/hardware/p10_1r/p10_1r_20260803T053211Z_cce2180b_c1370686_bfb1c51d/final/orchestrator_result.json), SHA256 `6d7c2ea2c6b6ab6bd6e6bc1a23d41a3b8a94f6553179e36c685c82ec5f0e221f`;
- [run manifest](../evidence/hardware/p10_1r/p10_1r_20260803T053211Z_cce2180b_c1370686_bfb1c51d/final/run_evidence_sha256_manifest.json), SHA256 `31f6ad2be7d6eb2b586394dc02550bec9cefeaafc2862c2e82e42e653d2b23f4`.

The 47 declared manifest entries were rehashed with zero size/hash mismatches.

## Safety closure

Shutdown-before, stage shutdown-after, final shutdown, and the `finally` shutdown all passed for both role-bound boards. The terminal record contains `TFDU_SHUTDOWN_PROGRAMMED=1` and `SHUTDOWN_EXIT=0`. The run authorization is consumed and false. No Ethernet, SPI, movement, alignment change, module exchange, or rewiring was performed.

P10.1R remains `PARTIAL`: performance, 64 MiB streaming, recovery, 1800-second formal stability, and final evidence consistency are not established by this connectivity-only run.
