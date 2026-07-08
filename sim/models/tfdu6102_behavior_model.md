# TFDU6102 Behavior Model

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

`tfdu6102_behavior_model.sv` is a digital offline model for P2 simulation.
It is not an analog circuit model, optical power model, supply droop model,
angle or distance model, rotation model, or crosstalk model.

Mode policy:

- `Mode=1` permits high-speed FIR-like pulse behavior in this model.
- `Mode=0` drops FIR pulse reception for P2 negative tests.
- Static `Mode=High` must not be mixed with future dynamic mode programming.

Safety behavior:

- `SD=1` enters shutdown, idles `Rxd=1`, and disables transmission.
- After `SD=0`, receiver startup waits `STARTUP_US`, default `500 us`.
- `Txd=1` is high-active.
- Continuous `Txd=1` at or beyond `TXD_PROTECT_US`, default `80 us`, disables
  the transmitter and raises `protect_fault`.
- Optical input pulses map 125 ns pulses to 100-140 ns low-active `Rxd`
  pulses and 250 ns pulses to 225-275 ns low-active `Rxd` pulses.

This model exists to verify RTL control, polarity, startup, and pulse-level
smoke behavior before future hardware authorization.
