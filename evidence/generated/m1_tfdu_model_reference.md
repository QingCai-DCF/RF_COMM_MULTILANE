# M1 TFDU Model Reference

M1_TFDU_MODEL_REFERENCE_REPORT=1
M1_MODEL_STARTUP_500US_PASS=1
M1_MODEL_RX_LOW_ACTIVE_PASS=1
M1_MODEL_125NS_RX_RANGE_PASS=1
M1_MODEL_250NS_RX_RANGE_PASS=1
M1_MODEL_JITTER_PATTERN_PASS=1
M1_MODEL_PULSE_LOSS_PATTERN_PASS=1
M1_MODEL_NEAR_END_ECHO_PASS=1
M1_MODEL_LONG_HIGH_DISABLE_PASS=1
M1_TFDU_MODEL_REFERENCE=PASS

| Item | Value |
|---|---:|
| 125 ns Txd reference Rxd low width | 120 ns |
| 250 ns Txd reference Rxd low width | 250 ns |
| default leading-edge jitter | 20 ns |
| default long-high cutoff | 80 us |

This offline reference checks the TFDU behavior-model contract without claiming SystemVerilog simulation or hardware acceptance.
