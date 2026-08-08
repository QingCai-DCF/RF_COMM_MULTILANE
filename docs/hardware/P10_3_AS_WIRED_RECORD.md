# P10.3 AX7020 four-lane as-wired record

This record binds the user's current P10.3 installation to the frozen P10.2 independent AX7020 wiring proposal. The fixed board is `AX7020-F/JTAG:210249855178`; the rotating-role board is `AX7020-R/JTAG:210512180081`. The installed topology is `lane0=F0-R0`, `lane1=F1-R1`, `lane2=F2-R2`, and `lane3=F3-R3`. The eight active module names are exclusively `F0..F3/R0..R3`; the historical failed fixed-side module remains separately quarantined and is ineligible for any active position. `P10_3_PHYSICAL_WIRING_COMPLETED=true` is a user physical-state attestation, not an electronic intake result.

| Module | Board / position | Small-board identity | Mode | SD | Rxd | Txd |
|---|---|---|---:|---:|---:|---:|
| F0 | AX7020-F / J10-A | A0019 | J10-30 / T12 | J10-32 / T11 | J10-34 / B19 | J10-36 / C20 |
| F1 | AX7020-F / J10-B | B0012 | J10-22 / V17 | J10-24 / T14 | J10-26 / U13 | J10-28 / V12 |
| F2 | AX7020-F / J11-A | B0019 | J11-30 / G17 | J11-32 / H16 | J11-34 / H15 | J11-36 / K14 |
| F3 | AX7020-F / J11-B | B0020 | J11-22 / L16 | J11-24 / M17 | J11-26 / D19 | J11-28 / E18 |
| R0 | AX7020-R / J10-A | A0010 | J10-30 / T12 | J10-32 / T11 | J10-34 / B19 | J10-36 / C20 |
| R1 | AX7020-R / J10-B | A0017 | J10-22 / V17 | J10-24 / T14 | J10-26 / U13 | J10-28 / V12 |
| R2 | AX7020-R / J11-A | B0023 | J11-30 / G17 | J11-32 / H16 | J11-34 / H15 | J11-36 / K14 |
| R3 | AX7020-R / J11-B | B0025 | J11-22 / L16 | J11-24 / M17 | J11-26 / D19 | J11-28 / E18 |

All signal I/O uses `LVCMOS33` against 3.3 V VCCO. Mode is static high, SD is active-high shutdown, Txd is active high and must be low in configured reset/fault/shutdown, and Rxd is active low. Per-signal bank, series-resistor, pull, source-page and connector-orientation details remain authoritative in `config/hardware/p10_2_ax7020_4lane_wiring.yaml` and the frozen proposal whose SHA256 is `5f4a89b818b007af4863534759068dda529fe3c34501569ea4da89a42d8026fc`.

The user's existing power/ground connections are preserved and Codex is not authorized to change them. The user states that the J11 modules use the same conductor gauge, supply source, and decoupling arrangement as the established J10 modules and confirms that arrangement is adequate for current use. This is a user attestation, not an independent voltage/current/droop measurement; external four-lane power acceptance remains `PENDING_EXTERNAL_MEASUREMENT`. Every active run must use dual-board shutdown-before and shutdown-after, mask `<=0xF`, no Ethernet, no movement/rotation/realignment/rewiring, and no two-hour or P11 operation. The user did not state whether historical wiring was performed with power removed, so this record makes no such claim.

The user-supplied small-board identifiers are unique across all eight active modules. They are not interpreted as PCB revisions, TFDU component markings, manufacturer serials, or lots. Electronic safe-idle, raw, frame and shutdown intake remains required before four-lane formal acceptance.

On 2026-08-04 the user reported that the former R2 small board `B0015` had been replaced by a new small board `B0023` at AX7020-R/J11-A. This record captures only that user-provided identity and position. Codex did not perform the replacement and does not claim the replacement power state, component marking, PCB revision, or electronic acceptance. Historical evidence involving R2=`B0015` remains immutable and is not relabeled as evidence for `B0023`.

The bounded run `p10_3_raw_20260804T114152Z_d4eef729_3d8cd207_a8459eef` subsequently passed lane2 raw connectivity in both directions: F2→R2 produced/received 64/64 and 1024/1024 raw events, and R2→F2 produced/received 64/64 and 1024/1024 raw events. Both boards reached verified shutdown. This is `RAW_PHYSICAL_ONLY` evidence; it does not complete framed module intake or any downstream P10.3 acceptance stage.

Later on 2026-08-04 the user reported replacing the former F3 small board `B0004` with `B0020` at AX7020-F/J11-B and requested a quick lane3 retest. Codex did not perform the replacement and does not claim the replacement power state. The prior two-direction lane3 failures remain immutable evidence for the old F3=`B0004` / R3=`B0017` pairing; they are not evidence for the new F3=`B0020` installation. Electronic status for the new pair remains pending until a fresh, shutdown-bounded bidirectional test completes.

The fresh bounded run `p10_3_raw_20260804T122719Z_d4eef729_3d8cd207_a8459eef` tested the current F3=`B0020` / R3=`B0017` pair in both raw directions. F3→R3 produced 64 final-path physical TX events and R3 observed 0 raw RX events; R3→F3 produced 64 final-path physical TX events and F3 observed 0 raw RX events. Both directions therefore failed and their 1024-event cases were not run fail-closed. Both boards reached verified shutdown at all seven checkpoints. This remains `RAW_PHYSICAL_ONLY` evidence and does not identify a unique component or wiring cause.

The user then reported replacing R3=`B0017` with R3=`B0025` at AX7020-R/J11-B and requested a quick raw-only lane3 retest. Codex did not perform the replacement and does not claim its power state. Prior evidence involving B0017 remains immutable and is not relabeled for B0025.

Run `p10_3_raw_20260804T124121Z_d4eef729_3d8cd207_a8459eef` passed raw connectivity for the current F3=`B0020` / R3=`B0025` pair in both directions at 64/64 and 1024/1024 events, with verified shutdown on both boards. The result is limited to `RAW_PHYSICAL_ONLY`.

On 2026-08-08 the user reported replacing F2=`B0008` with F2=`B0019` at AX7020-F/J11-A. Codex did not perform the replacement and does not claim its power state. All B0008 evidence remains immutable and is not relabeled for B0019. The B0019/R2=`B0023` pair therefore required a fresh, shutdown-bounded bidirectional raw retest. The same user instruction adds a prospective maximum continuous module runtime of 1800 seconds and requires a verified-shutdown cooldown of at least half the preceding stage runtime before any later transmission; the machine-readable policy is `config/safety/p10_tfdu_runtime_rest_policy.yaml`.

Run `p10_4_l2b0019raw_20260808T084408Z_6ff17d33_94506af9_2b2b37d4` then passed current-pair raw connectivity in both directions: F2→R2 and R2→F2 each produced/received 64/64 and 1024/1024 raw events. Maximum requested Txd high time was eight 64 MHz cycles (125 ns). The measured direction stages were 44.763652 s and 43.460145 s; verified-shutdown cooldowns were 22.382137 s and 21.731190 s, satisfying the half-runtime rule. Both final shutdown markers passed. This remains `RAW_PHYSICAL_ONLY`; framed intake and the remaining P10.4 campaign are separate.
