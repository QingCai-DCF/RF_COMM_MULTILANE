# P10.1R per-module RX admission and self-echo rejection

Status: four-module guard calibration passed; rebuilt-artifact acceptance pending.

Each physical TFDU owns an independent admission state. The trigger is the final role-local physical `Txd` after `GLOBAL_PERMIT`, endpoint arm, lane permit, one-hot, exact-duty, stuck-high, frame-admission, and final TX-kill logic. A queued descriptor or scheduled frame cannot trigger or bypass this state.

When final `Txd` becomes active, the same module's `rx_frame_accept_enable` is removed combinationally. Its decoder and parser are held clear for all of local TX and the complete echo quarantine. Raw synchronized Rxd remains counted and timestamped, but the blanked path cannot create DATA, ACK/SACK, sequence-window progress, DMA writes, application commits, or RX LED activity. The other lane has a separate instance and is not blanked.

The purpose-limited four-module calibration run measured 1,000 transmissions on each of F0, F1, R0, and R1. It observed 4,000 raw same-module echoes, zero accepted same-module frames, and zero post-TX raw-edge tail on every module. The selected 64 MHz minimum guard is therefore 4,096 cycles (64 us), equal to the observed maximum plus a frozen 4,096-cycle deterministic margin. The separate 256-cycle (4 us) Rxd-idle qualification and 131,072-cycle (2,048 us) fail-closed maximum remain unchanged. The rebuilt artifacts must reverify this bound before `P10_1R-ECHO-005` or the campaign can pass.

Wire-format source identity is defense in depth. Fixed uses node ID 1 and rotating-role uses node ID 2 in previously reserved header bits, without adding airtime bytes. A CRC-valid frame carrying the local node ID is rejected even after admission reopens. Remote DATA and remote ACK/SACK remain admissible according to endpoint role.

The read-only shadow decoder exists solely to count blanked preambles and CRC-valid self echoes. It has no connection to protocol admission, DMA, ACK generation, LEDs, flow control, permit, or safety. All new monotonic telemetry counters saturate at `0xffffffff`; timestamps wrap modulo 2^32. Software obtains a versioned atomic snapshot beginning at register `0x0a00`.

This design preserves one active-high `GLOBAL_PERMIT` per endpoint, receive-only operation with permit low, active-high SD shutdown, active-high Txd, exact rolling duty, continuous-high limit, and the existing fixed/rotating AX7020 pinmaps.
