# Hardware Safety

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

RF_COMM_MULTILANE defaults to NO_HARDWARE=1. Do not program FPGA hardware,
start PS ELF files, open Vivado Hardware Manager, connect XSCT hardware
targets, open real serial devices, drive TFDU pins, or access board network
endpoints without explicit user authorization.

## TFDU6102 Policy

- Txd is active high and must default to 0.
- Rxd is active low and inversion belongs in the TFDU lane PHY wrapper.
- SD is active high shutdown and must default to 1.
- Static high-speed mode uses Mode=High; do not mix it with dynamic mode programming.
- Startup wait after leaving shutdown must cover at least 500 us.
- Continuous Txd high must stay below the 80 us device limit and be guarded in RTL.
- TX duty window protection is required before any hardware claim.
- IRED current, VCC2 droop, C1/C3 4.7 uF, C2 0.1 uF, layout inductance, and supply quality are hardware acceptance checklist items.

## Authorization

Future hardware scripts must default to dry-run, require a token file, require
RF_COMM_ALLOW_HW=I_UNDERSTAND_AND_AUTHORIZE, require max runtime, and program
TFDU shutdown on every exit path.
