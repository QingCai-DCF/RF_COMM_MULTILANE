# P10.5 fail-closed closeout: R3 to F3

`P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE=FAIL`

P10.5 is closed fail-safe because the exact lane-matching artifact reproduced an FPGA-visible `R3 -> F3` physical connectivity loss twice.

The blocking run `p10_5_20260810T114211Z_e1f8c01a_4015142e_79607d01` failed in the early 1+1 case `oneplusone_f0_r3`. During that same case, F0 transmitted 284,280 physical pulses and R0 received all 284,280, while R3 transmitted 284,852 and F3 received zero. Both protocol endpoints then reported `0x50090004` retry exhaustion. The earlier run `p10_5_20260810T111841Z_e1f8c01a_4015142e_79607d01` independently captured R3 transmitting 427,200 while F3 again received zero.

No safety fault, rolling-duty hard fault, continuous-high violation, CRC/SHA error, or descriptor leak was recorded. Both runs finished with independently verified shutdown on both boards.

The architecture and immutable artifacts remain separately evidenced: all offline gates and 31/31 XSIM tests passed; run `101302` executed real 2+2 TX, passed all legal mask stages through five simultaneous bidirectional 64 MiB transfers, and measured 4,292,171.093 bit/s per direction. Those results do not override the current physical blocker and are not promoted to a complete P10.5 PASS.

Under Goal section 4, proceeding now would require a physical action outside autonomous scope. No further TX is authorized or scheduled. P11 remains not started, and the pass tag is prohibited.

