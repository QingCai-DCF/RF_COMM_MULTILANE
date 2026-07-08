# RTL Structure Policy

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

Active RTL lives under `rtl/`. Legacy reference RTL remains under
`rtl/legacy_reference/`. TFDU pin control belongs in a lane PHY wrapper. Codec,
frame, ARQ, scheduler, and AXI register responsibilities should remain separate
as the rebuild advances.
