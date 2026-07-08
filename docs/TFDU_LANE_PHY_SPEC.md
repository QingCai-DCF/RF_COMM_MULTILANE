# TFDU Lane PHY Spec

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Goal

Define the P2 offline lane PHY wrapper contract around TFDU6102 polarity,
startup, pulse measurement, and TX protection.

## Non-Goals

This spec does not prove any physical TFDU6102 link, board supply, optical
alignment, lane direction, Ethernet path, rotation behavior, or soak behavior.
It does not replace hardware authorization.

## Pin Definitions

- `Txd` is high-active transmit input.
- `Rxd` is low-active receive output.
- `SD` is high-active shutdown.
- `Mode=High` selects the static high-speed MIR/FIR policy for P2.
- `Mode=Low` is treated as low-speed SIR mode and drops FIR pulse tests.

## Reset And Shutdown Defaults

In `RESET` and `SHUTDOWN_SAFE`:

- `txd_o = 0`
- `sd_o = 1`
- `mode_o = 1` when the static high-speed profile is selected
- `startup_done = 0`
- `tx_ready = 0`
- `rx_ready = 0`

## Static Mode=High Strategy

P2 uses static `Mode=High`. The wrapper drives `mode_o=1` as a stable policy
and does not perform dynamic mode programming.

## Dynamic Mode Programming Future Work

If dynamic mode programming is introduced later, the `Mode` pin must not be
treated as a normal force-driven GPIO at the same time. The `SD/Txd/Mode`
timing must be validated independently before any hardware stage.

## Startup Gate

After `SD` leaves shutdown, RX startup wait must cover `500 us` in production
configuration. P2 testbenches may shorten the parameter to keep offline tests
fast. Before `startup_done`, frame TX and RX are blocked.

## RX Active-Low Inversion Boundary

`Rxd` inversion is centralized in the lane PHY wrapper. Protocol layers consume
`rx_raw_active` and must not repeat `~rxd` handling.

## TX Stuck-High Guard

The wrapper tracks continuous TX high time. The default P2 wrapper threshold is
`70 us`, below the `80 us` device protection limit. A fault clamps `txd_o=0`
and returns the lane to shutdown-safe state.

## TX Duty Window Guard

The P2 wrapper exposes the maximum high stretch for the baseline gate. A richer
windowed duty guard remains a later RTL hardening item before hardware use.

## Raw Pulse Counter

The wrapper increments `rx_pulse_count` on synchronized low-active RX pulse
entry after startup.

## Pulse Width Measurement

The wrapper records `rx_last_pulse_width_cycles` for the last low-active RX
pulse.

## Fault Status

P2 exposes `tx_stuck_fault` and `tx_high_max_cycles`. Future revisions may add
fault codes, clear-on-write behavior, and explicit shutdown-forced status.

## Register And Counter Exposure Recommendation

Future AXI exposure should include:

- `startup_done`
- `rx_raw_active`
- `rx_pulse_count`
- `rx_last_pulse_width_cycles`
- `tx_high_max_cycles`
- `tx_stuck_fault`

## Lane Generate Strategy

Disabled lanes must hold `txd=0` and `sd=1`, or an equally explicit inactive
safe state. Lane masks must compile for `LANE_COUNT=1`, `2`, and `8`.

## Recommended State Machine

```text
RESET
  -> SHUTDOWN_SAFE
  -> STARTUP_WAIT
  -> READY
  -> ACTIVE_TX_RX
  -> FAULT
  -> SHUTDOWN_SAFE
```

## P2 Simulation Acceptance

P2 accepts:

- reset/shutdown default checks
- startup gate checks
- active-low RX checks
- pulse width checks
- stuck-high guard checks
- TFDU6102 behavior model smoke checks
- paired link smoke checks when an HDL simulator exists
- explicit `SKIP_WITH_REASON` for HDL tests when no simulator exists

## P3 And Later Hardware Raw PHY Relation

P3 should package a dry-run hardware acceptance plan. P4 or later may perform
raw PHY smoke only after explicit user authorization, safe-wrapper use, and
shutdown evidence.
