# TFDU6102 Reference Model Summary

generated_at_utc: 2026-07-09T11:04:43+00:00
current_commit: 4768ef76c1d9bc6042d4058f52eef5fc0da5ca01
command: python sim/scripts/run_reference_tests.py --json
RESULT: PASS
REASON: Python reference model tests passed
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW

- returncode: 0
- tests: 11

| Test | Result | Reason |
| --- | --- | --- |
| test_125_ns_pulse_mapping | PASS | ok |
| test_250_ns_pulse_mapping | PASS | ok |
| test_mode_low_drops_fir_pulse | PASS | ok |
| test_reset_shutdown_idle | PASS | ok |
| test_rxd_low_active | PASS | ok |
| test_shutdown_blocks_transmitter | PASS | ok |
| test_startup_delay_500_us | PASS | ok |
| test_startup_not_done_drops_receiver_pulses | PASS | ok |
| test_static_high_speed_mode | PASS | ok |
| test_txd_high_active | PASS | ok |
| test_txd_over_80_us_protection | PASS | ok |
