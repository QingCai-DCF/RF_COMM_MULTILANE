# Next Hardware Acceptance Plan

This plan does not authorize hardware execution.

## Authorization Prerequisites

Require a user-provided token file, RF_COMM_ALLOW_HW=I_UNDERSTAND_AND_AUTHORIZE,
explicit safe wrapper flag, max runtime, run id, and shutdown cleanup.

## Instrumentation Prerequisites

Prepare scope captures, VCC2 droop measurement, IRED current estimate, board id,
bitstream id, and profile hash.

## Stages

- H0 dry-run.
- H1 pin idle check: Txd=0, SD=1, Mode strategy.
- H2 TFDU startup check: leave shutdown and wait, no transmit.
- H3 raw pulse low-rate check.
- H4 AB/BA lane0 raw.
- H5 AB/BA lane1 raw.
- H6 frame+CRC lane0.
- H7 ACK lane0.
- H8 two-lane only after lane1 raw pass.
- H9 Ethernet after IR lane baseline.
- H10 rotation after stationary pass.
