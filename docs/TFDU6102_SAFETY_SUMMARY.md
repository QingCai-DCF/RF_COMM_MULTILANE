# TFDU6102 Safety Summary

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

## Pin Semantics

- Txd is active high transmit input.
- Rxd is active low receive output.
- SD is active high shutdown.
- Mode=High selects MIR/FIR high-speed mode; Mode=Low selects SIR low-speed mode.

## Shutdown Default

Reset and disabled lanes must hold Txd=0 and SD=1.

## Static High-Speed Mode

The current project policy is static Mode=High after reset. SD exit must be
followed by receiver startup wait before TX or RX is considered valid.

## Dynamic Mode Programming

Dynamic mode programming is not active. If introduced later, Mode must not be
simultaneously driven as a static GPIO and SD/Txd timing must remain separate.

## Startup Wait

Receiver startup wait must cover at least 500 us after shutdown exit or power-on.

## TX Stuck-High Protection

Txd continuous high must not approach or exceed 80 us. RTL must expose a
stuck-high guard or a blocking TODO before hardware promotion.

## Duty-Cycle / Pulse Width Guard

TX duty window protection is required; missing implementation must be a blocker,
not a PASS.

## IRED Current and VCC2 Droop

IRED current and VCC2 droop are hardware acceptance measurements and are not
validated by offline gates.

## Decoupling and Layout

C1/C3 4.7 uF, C2 0.1 uF, layout inductance, and supply quality must be checked
before hardware acceptance.

## RX Active-Low Convention

Rxd inversion is centralized in the TFDU lane PHY wrapper.

## Hardware Test Authorization

This document does not authorize hardware execution.

## Evidence Requirements

Hardware evidence must include authorization, run id, bitstream id, profile hash,
shutdown evidence, and raw logs. Offline evidence cannot promote PENDING_HW.
