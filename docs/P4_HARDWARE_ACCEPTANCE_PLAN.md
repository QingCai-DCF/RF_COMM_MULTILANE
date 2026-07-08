# P4 Hardware Acceptance Plan

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

P4 is blocked until a new user instruction explicitly authorizes hardware.

Required instruction form:

```text
I authorize P4 hardware acceptance for RF_COMM_MULTILANE on board <board_id>, using bitstream <path>, max runtime <N> seconds, with shutdown-on-exit enabled.
```

Without that instruction and the authorization gate inputs, P4 remains blocked.
P4 must start with visual/electrical review, idle no-emission checks, startup
gate observation, single-pulse raw PHY smoke, raw lane matrix, then protocol
checks only after raw evidence is valid.
