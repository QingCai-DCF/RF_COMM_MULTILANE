# Hardware Acceptance Checklist

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

- [ ] User explicitly authorizes P4 hardware testing
- [ ] Authorization file exists and is signed/dated
- [ ] RF_COMM_HW_AUTH environment variable is set
- [ ] Board ID recorded
- [ ] Fixture ID recorded
- [ ] Vivado/Vitis version recorded
- [ ] Active XDC hash recorded
- [ ] Pinmap hash recorded
- [ ] Bitstream hash recorded
- [ ] PS app hash recorded
- [ ] Test profile recorded
- [ ] Emergency stop method defined
- [ ] Maximum runtime defined
- [ ] Shutdown-on-exit enabled
- [ ] Txd default low verified by design
- [ ] SD default shutdown verified by design
- [ ] Mode strategy selected: static High or dynamic programming, not both
- [ ] Startup delay >= 500 us verified in RTL/simulation
- [ ] Txd stuck-high guard enabled
- [ ] TX duty guard enabled
- [ ] VCC1 voltage measurement plan ready
- [ ] VCC2 voltage measurement plan ready
- [ ] IRED current path reviewed
- [ ] C1/C3 4.7 uF decoupling reviewed
- [ ] C2 0.1 uF ceramic decoupling reviewed
- [ ] Scope probes assigned
- [ ] Logic analyzer channels assigned
- [ ] Raw counter readback method defined
- [ ] Shutdown log path defined
- [ ] Stop conditions reviewed

This checklist does not authorize hardware execution.
P4 hardware execution requires explicit user approval in a later step.
