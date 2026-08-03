# P10.1R lane1 directional blocker audit

```text
P10_1R_RESULT: PARTIAL
BLOCKER_STATUS: BLOCKED_MANUAL_HARDWARE
HARDWARE_ACCEPTANCE_STATUS: FAIL
LANE1_CONNECTIVITY_RESULT: FAIL
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
SHUTDOWN_FIXED: PASS
SHUTDOWN_ROTATING: PASS
```

## Outcome

The frozen P10.1R bundle currently passes the preserved raw lane1 direction `R1 -> F1` but fails `F1 -> R1`. After the user reported power-cycling/re-powering the setup, a fresh authorized run again failed `F1 -> R1` at sample 0. Its pre-shutdown atomic snapshot again proves that the fixed internal final-Txd path pulsed on lane1 and that fixed F1 observed a contemporaneous local raw event, while rotating R1 observed no raw event. The power-cycle therefore did not restore this direction. Automated reset/reprogram retries cannot distinguish or repair the remaining external physical boundary, and this campaign forbids Codex from moving, aligning, obstructing, exchanging, or rewiring the hardware.

This is a current-setup, direction-specific failure. It is not evidence that a particular TFDU, cable, connector, or FPGA pin is defective, and it is not a P10.1R PASS.

## Frozen identity

| Item | Value |
|---|---|
| Goal SHA256 | `299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f` |
| Artifact source | `cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d` |
| Artifact freeze SHA256 | `05681978cba335cb4aa1c1cea41e8a4661017d64a307e9b037ded7064ec01a54` |
| Fixed bitstream | `c13706860a003721d45e9a6fd90f444825aaa1b342a74a095079eceffa856a27` |
| Rotating bitstream | `bfb1c51d639188ea60392c8ceb39b25276e12b819c8e2ee0c5ae3ef63497639f` |
| Fixed ELF | `0d3963ce7fbcaab95373ebec97f4c62712bd216f041a23547c9006024e219db4` |
| Rotating ELF | `5abf3d3d597b14e182d07665609a8dd8ff05d7c6159fd2deb1f81813723c035e` |
| Fixed board | `AX7020-F/JTAG:210249855178` |
| Rotating-role board | `AX7020-R/JTAG:210512180081` |
| lane1 | `F1-R1`, J10 position B on both boards |

## Direct directional evidence

Evidence level is `RAW_AB_BA`: role-bound raw-command and receiver telemetry, not a DATA-loopback verdict and not an external electrical/optical measurement.

| Direction | Result | Strongest direct evidence |
|---|---|---|
| `R1 -> F1` | `PASS_RAW_DIRECTIONAL_PRESERVED` | The earlier same-bundle run passed 1000/1000 samples; this fail-fast post-power-cycle run did not re-execute the reverse direction. |
| `F1 -> R1` | `FAIL_NO_REMOTE_RAW_ACTIVITY_POST_POWER_CYCLE` | On sample 0, fixed completed with status `0x0`, state `4`; its final-Txd tap rose at `34007980` and fell at `34007985`, fixed A1 physical-TX count was `1`, and fixed F1 recorded `sender_raw=1` while local TX was high. Rotating R1 recorded `receiver_raw=0` and returned `0xE` (`P9_RUNTIME_RAW_TIMEOUT`), state `5`; both PHY status and error-detail registers were zero. |

The decisive reverse-first transcript is [echo-tail XSDB result](../../evidence/hardware/p10_1r/p10_1r_20260802T182921Z_cce2180b_c1370686_bfb1c51d/echo_tail/xsdb.result.txt), SHA256 `30ac4a455e0091b4cc62d050bff5beaccf4b0b02631f28edcb0b00e5ac4455c0`. The 1000-row reverse-direction raw record is [echo_R1.echo_tail.psv](../../evidence/hardware/p10_1r/p10_1r_20260802T182921Z_cce2180b_c1370686_bfb1c51d/echo_tail/dumps/echo_R1.echo_tail.psv), SHA256 `b5d42ea404e7d028a2706a8cca2c3efea24f929e4d1c23c3ef2d26f1fd78e7fd`.

The post-power-cycle fixed-to-rotating transcript is [XSDB result](../../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/echo_tail/xsdb.result.txt), SHA256 `ebfb1cb86e0242d9aeb86d93b44060985aca8305073719a87621da49855a08a5`. Its coherent endpoint snapshots are [fixed](../../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/echo_tail/dumps/echo_F1_failure_0000.fixed.p10_1r.psv), SHA256 `8ed9373af25269ba024ab53e4a563582354d33134c3fd308bb9f7a549bb4abdf`, and [rotating](../../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/echo_tail/dumps/echo_F1_failure_0000.rotating.p10_1r.psv), SHA256 `a3b0c219c1aad1ce271c6fbac90c35fd5009be3218c750cbb7029d5ddac920e5`.

## Reproduction controls

1. Run `p10_1r_20260802T174940Z_cce2180b_c1370686_bfb1c51d` initially passed all four 1000-sample echo sweeps, crosstalk remediation, PHY sanity, and ACK tuning. This rules out treating the static pinmap or frozen artifact as inherently lane1-inapplicable.
2. During the same run, four F-to-R objects completed at 4.673–4.684 Mbit/s with zero lane1 symbol/CRC errors. A later 16 MiB object fell to 1.557 Mbit/s while rotating lane1 accumulated 765,218 symbol errors and two bad/CRC frames; the following command timed out.
3. Run `p10_1r_20260802T182703Z_cce2180b_c1370686_bfb1c51d` made `F1 -> R1` the first post-boot raw test and failed at sample 0 with the same rotating `RAW_TIMEOUT`. The failure therefore does not depend on prior F0 load.
4. Run `p10_1r_20260802T182921Z_cce2180b_c1370686_bfb1c51d` made `R1 -> F1` first and passed 1000/1000 before `F1 -> R1` failed at sample 0. The current lane1 failure is directional, not a total lane1 outage.
5. Run `p10_1r_20260802T191315Z_cce2180b_c1370686_bfb1c51d` made `F1 -> R1` first and captured both atomic endpoint snapshots before host-side error shutdown. The fixed raw generator completed one pulse, the fixed final-Txd tap and A1 physical-TX counter advanced, and fixed F1 saw one local raw event; rotating R1 saw zero raw events. This closes the host command, lane selection, raw generator, permit/duty/kill, and internal final-Txd path for that pulse, but does not prove external optical power or identify a component defect.
6. After the user-reported power-cycle/re-power action, run `p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d` reproduced the same first-sample `F1 -> R1` failure and the same localization boundary. The reverse direction was not re-executed because the safe stage failed closed at the first required direction.

## Supported boundary

The fixed endpoint completes its F1 raw command, its internal final-Txd tap pulses for five protocol cycles after the permit/duty/kill path, its A1 physical-TX counter advances, and fixed F1 records one local raw event while the rotating endpoint sees no R1 raw event. Together with the working reverse direction, the unresolved boundary begins after the internal fixed final-Txd tap and extends through the fixed F1 external pin/J10/module emission, optical path, and rotating R1 module/J10/input detection chain.

Without user physical inspection or external electrical/optical evidence, the following remain indistinguishable:

- fixed F1 FPGA package-pin/J10 electrical delivery, emitter/module power/SD/Mode/Txd, or optical output;
- F1-to-R1 line of sight, alignment, obstruction, or reflection condition;
- rotating-role R1 detector/module power/SD/Mode/Rxd/connector/board-input path.

No component-level defect is asserted.

## Safety and authorization closure

The latest current-run authorization is consumed and false. No Ethernet or SPI was used; Codex did not move, rotate, align, obstruct, exchange, or rewire any hardware. The last final shutdown record reports:

```text
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
TFDU_SHUTDOWN_PROGRAMMED=1
SHUTDOWN_EXIT=0
fixed active TX mask=0
rotating active TX mask=0
fixed endpoint armed=0
rotating endpoint armed=0
fixed SD request active=1
rotating SD request active=1
```

See [final shutdown record](../../evidence/hardware/p10_1r/p10_1r_20260803T034619Z_cce2180b_c1370686_bfb1c51d/shutdown/finally_emergency/attempt_1.result.txt), SHA256 `e9cae8f81d93ea6a36e424ae37379b433920658e2cc0c6206f996d7c20d3f065`.

## Unfinished mandatory gates

The current four-module echo-tail set, sustained 4 Mbit/s in both directions, 5 x 64 MiB in both directions, abort/reset recovery for this bundle, 30-minute formal run, final evidence consistency, and P10.1R final acceptance remain incomplete or failed. No PASS tag is permitted.

## Required user action

The reported power-cycle did not change the result. With both boards powered off, inspect the existing `F1 -> R1` physical path without changing board roles. Check the F1/R1 line of sight and the existing fixed-F1 transmitter-side and rotating-R1 receiver-side TFDU power, ground, SD, Mode, Txd/Rxd, and J10 position-B connections. Report exactly what was changed or confirmed.

After that report, Codex can create a fresh immutable per-run authorization from the standing P10.1R authorization, execute shutdown-before, repeat the bidirectional lane1 raw diagnostic, and resume the remaining P10.1R campaign only if the lane passes.

The adjacent JSON is the authoritative machine-readable blocker record.
