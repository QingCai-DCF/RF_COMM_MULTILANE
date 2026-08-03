# P10.2 four-lane power and decoupling requirements

This document is a P10.3 design input, not a power acceptance result. The engineering upper bound is 0.6 A peak IRED current per TFDU module, so four simultaneous transmitters require a 2.4 A peak IRED-current path at one endpoint. FPGA/PS current, logic-rail current, conversion loss, cable loss and margin are additional and are not silently assigned guessed values.

| Simultaneous TX modules | IRED peak bound | IRED long-term average at 18% per module | Minimum effective C for 0.1 V over 1 us |
|---:|---:|---:|---:|
| 1 | 0.6 A | 0.108 A | 6 uF |
| 2 | 1.2 A | 0.216 A | 12 uF |
| 4 | 2.4 A | 0.432 A | 24 uF |

The capacitance column is only `C=I·dt/ΔV`; it does not replace impedance, ESR/ESL, regulator transient, cable or connector analysis. The effective value must include voltage and temperature derating. High-frequency local bypassing belongs at each small board, while endpoint bulk capacitance belongs at the distribution entry. Ground returns must be low impedance and must not share an uncontrolled logic-reference drop.

Before any four-lane hardware run, record the actual supply model/rating, rail setpoint, current limit, connector/contact rating, conductor gauge/length, measured resistance, capacitor part/value/derating and grounding topology. Measure VCC2 at all four modules plus endpoint input current during safe idle, one-lane, two-lane and four-lane controlled steps. Record minimum voltage, droop, recovery, ripple and temperature. Unknown values remain pending; zero and guessed defaults are prohibited.

The future order is safe idle → receive-only → one lane → two lanes → four lanes. A transition directly from safe idle to four simultaneous transmitters is prohibited. Every step retains the exact per-module 1 ms rolling duty target `<=18%`, hard limit `<20%`, continuous Txd high `<=1 us`, shutdown-before and shutdown-after requirements.

`P10_2_POWER_REQUIREMENT_PACKAGE=PASS`; `P10_3_REAL_POWER_ACCEPTANCE=PENDING`.
