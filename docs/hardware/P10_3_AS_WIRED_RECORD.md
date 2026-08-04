# P10.3 AX7020 four-lane as-wired record

This record binds the user's current P10.3 installation to the frozen P10.2 independent AX7020 wiring proposal. The fixed board is `AX7020-F/JTAG:210249855178`; the rotating-role board is `AX7020-R/JTAG:210512180081`. The installed topology is `lane0=F0-R0`, `lane1=F1-R1`, `lane2=F2-R2`, and `lane3=F3-R3`. The eight active module names are exclusively `F0..F3/R0..R3`; the historical failed fixed-side module remains separately quarantined and is ineligible for any active position. `P10_3_PHYSICAL_WIRING_COMPLETED=true` is a user physical-state attestation, not an electronic intake result.

| Module | Board / position | Small-board identity | Mode | SD | Rxd | Txd |
|---|---|---|---:|---:|---:|---:|
| F0 | AX7020-F / J10-A | A0019 | J10-30 / T12 | J10-32 / T11 | J10-34 / B19 | J10-36 / C20 |
| F1 | AX7020-F / J10-B | B0012 | J10-22 / V17 | J10-24 / T14 | J10-26 / U13 | J10-28 / V12 |
| F2 | AX7020-F / J11-A | B0001 | J11-30 / G17 | J11-32 / H16 | J11-34 / H15 | J11-36 / K14 |
| F3 | AX7020-F / J11-B | B0004 | J11-22 / L16 | J11-24 / M17 | J11-26 / D19 | J11-28 / E18 |
| R0 | AX7020-R / J10-A | A0010 | J10-30 / T12 | J10-32 / T11 | J10-34 / B19 | J10-36 / C20 |
| R1 | AX7020-R / J10-B | A0017 | J10-22 / V17 | J10-24 / T14 | J10-26 / U13 | J10-28 / V12 |
| R2 | AX7020-R / J11-A | B0023 | J11-30 / G17 | J11-32 / H16 | J11-34 / H15 | J11-36 / K14 |
| R3 | AX7020-R / J11-B | B0017 | J11-22 / L16 | J11-24 / M17 | J11-26 / D19 | J11-28 / E18 |

All signal I/O uses `LVCMOS33` against 3.3 V VCCO. Mode is static high, SD is active-high shutdown, Txd is active high and must be low in configured reset/fault/shutdown, and Rxd is active low. Per-signal bank, series-resistor, pull, source-page and connector-orientation details remain authoritative in `config/hardware/p10_2_ax7020_4lane_wiring.yaml` and the frozen proposal whose SHA256 is `5f4a89b818b007af4863534759068dda529fe3c34501569ea4da89a42d8026fc`.

The user's existing power/ground connections are preserved and Codex is not authorized to change them. The user states that the J11 modules use the same conductor gauge, supply source, and decoupling arrangement as the established J10 modules and confirms that arrangement is adequate for current use. This is a user attestation, not an independent voltage/current/droop measurement; external four-lane power acceptance remains `PENDING_EXTERNAL_MEASUREMENT`. Every active run must use dual-board shutdown-before and shutdown-after, mask `<=0xF`, no Ethernet, no movement/rotation/realignment/rewiring, and no two-hour or P11 operation. The user did not state whether historical wiring was performed with power removed, so this record makes no such claim.

The user-supplied small-board identifiers are unique across all eight active modules. They are not interpreted as PCB revisions, TFDU component markings, manufacturer serials, or lots. Electronic safe-idle, raw, frame and shutdown intake remains required before four-lane formal acceptance.

On 2026-08-04 the user reported that the former R2 small board `B0015` had been replaced by a new small board `B0023` at AX7020-R/J11-A. This record captures only that user-provided identity and position. Codex did not perform the replacement and does not claim the replacement power state, component marking, PCB revision, or electronic acceptance. Historical evidence involving R2=`B0015` remains immutable and is not relabeled as evidence for `B0023`.
