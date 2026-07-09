# TFDU6102 Safety Contract

NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

- [x] Reset holds `Txd=0`.
- [x] Reset holds `SD=1`.
- [x] Disabled lane holds `SD=1`.
- [x] Enabled lane waits for startup before valid TX/RX.
- [x] Startup incomplete means TX FSM must not emit pulses.
- [x] Startup incomplete means RX FSM must not count valid frames.
- [x] Continuous `Txd=1` time is bounded below the 80 us device limit.
- [x] P4 smoke profiles use `Txd_stuck_high_trip_us <= 10 us`.
- [x] TX duty window is bounded or a blocker is recorded.
- [x] RX inversion appears only in the PHY wrapper.
- [x] Mode strategy is single-choice static high-speed mode.
- [x] Static mode and dynamic mode programming are not mixed.
- [x] All future hardware tests must program shutdown on exit.
- [x] P2 simulation keeps HARDWARE_ACCEPTANCE at PENDING_HW.
- [x] P2 model treats Rxd idle as high and valid receive pulses as low.
- [x] P2 model drops FIR pulses while Mode=Low.
- [x] P2 model records stuck-high protection instead of allowing unbounded Txd high.
