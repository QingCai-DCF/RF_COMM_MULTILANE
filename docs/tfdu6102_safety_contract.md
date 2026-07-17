# TFDU6102 Safety Contract

NO_HARDWARE_ACTIONS_EXECUTED: true

CURRENT_RUN_HARDWARE_AUTHORIZATION: false

HARDWARE_ACCEPTANCE: PENDING_HW

The normative product requirements remain in `PROJECT_CONSTRAINTS.txt`; constants below are generated from `config/tfdu_safety.yaml`.

## Portable RTL contract

- [x] `Txd` is active high, `Rxd` active low, `SD` active-high shutdown, and static `Mode=1` selects MIR/FIR.
- [x] Reset/fault holds the physical transmit request low.
- [x] Each receiver waits at least 500 us after shutdown exit.
- [x] Each physical module has an exact arbitrary-alignment 1000 us history; strict hard duty is `<20%` and normal target admission is `<=18%`.
- [x] History survives permit, arm, logical-lane, mapping, and path-epoch transitions.
- [x] History invalidation and accepted safety clear force at least one complete 1000 us TX-low cooldown.
- [x] Continuous physical high is limited to `<=1 us`; `MAX+1` latches a fault and kills output.
- [x] One endpoint consumes exactly one active-high `global_permit_i`.
- [x] Raw permit low is the last RTL gate on every physical `Txd` and does not wait for software or a frame transition.
- [x] Permit high is synchronized/filtered and requires explicit arm; reassertion cannot resume a partial frame.
- [x] `SD` control is separate, so receive-only acquisition can proceed with permit low and all TX hard-disabled.
- [x] Illegal one-hot, bank fault, stale path epoch, invalid mapping, start-up, cooldown, duty, and stuck-high conditions fail closed.
- [x] Permit status is read-only; software can request arm/disarm/shutdown/clear/snapshot but cannot create permit high.
- [x] Snapshot telemetry is atomic and indexed by physical-module identity.

## Controlled clear

Safety-fault clear is accepted only while the raw permit is low and both pre-final and physical TX vectors are all low. Acceptance clears the eligible sticky module fault and simultaneously invalidates duty history, so TX remains blocked for the full refill cooldown. Telemetry clear is a distinct request and never clears sticky safety faults.

## Hardware follow-up contract

- [ ] External fail-low bias at power-up, open circuit, FPGA-unconfigured, and partial-power states: `PENDING_D17`.
- [ ] Physical final-kill path and deassertion latency measurement: `PENDING_D17`.
- [ ] Current Z7010 permit pin freeze: `PENDING_P9_PIN_FREEZE`; Z7020 board/profile constraints remain separate and pending.
- [ ] External electrical/optical rolling-duty, current, VCC2 droop, and simultaneous-path power measurements: `PENDING_P9_OR_LATER`.

The single permit does not detect a stuck-high permit and carries no dual-channel, redundant, SIL, or PL claim.
