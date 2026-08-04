# TFDU module inventory

Status: `PASS` for P10.1R baseline classification; future 4-lane modules remain pending physical intake.

## Accepted P10.1R baseline

| Logical identity | Endpoint / position | User-provided small-board ID | Status | Evidence basis |
|---|---|---|---|---|
| F0 | AX7020-F / J10-A | `A0019` | `ACCEPTED_P10_1R` | Raw four-direction run plus 30-minute formal run |
| F1_REPLACEMENT (runtime label F1) | AX7020-F / J10-B | `B0012` | `ACCEPTED_P10_1R` | User replacement record followed by raw and formal PASS |
| R0 | AX7020-R / J10-A | `A0010` | `ACCEPTED_P10_1R` | Raw four-direction run plus 30-minute formal run |
| R1 | AX7020-R / J10-B | `A0017` | `ACCEPTED_P10_1R` | Raw four-direction run plus 30-minute formal run |

These four identifiers were supplied directly by the user on 2026-08-04 and were not independently read or verified by Codex. They are recorded as physical small-board identifiers only and are not interpreted as PCB revisions, TFDU component markings, manufacturer serials, or lots. No unsupplied value is inferred. `B0012` belongs to the replacement module currently carrying runtime label F1, not to quarantined `F1_ORIGINAL`.

This post-freeze identity record does not rewrite the immutable P10.1R/P10.2 acceptance evidence or move `p10.2-4lane-offline-ready`.

## Quarantine

`F1_ORIGINAL` is `QUARANTINED_NOT_ACCEPTED`. It is not a spare and must never be relabeled F2, F3, R2, or R3. Its historical directional failures remain preserved; only the replacement F1 participated in the accepted run bundle.

## Future four-lane intake

F2, F3, R2, and R3 each start with all of the following unresolved states:

- `PENDING_PHYSICAL_INVENTORY`
- `PENDING_PINOUT_CHECK`
- `PENDING_SAFE_IDLE`
- `PENDING_RAW_ACCEPTANCE`

The machine-readable authority is `config/hardware/tfdu_module_inventory.yaml`. A future P10.3 runner must reject any module lacking an accepted immutable identity record.
