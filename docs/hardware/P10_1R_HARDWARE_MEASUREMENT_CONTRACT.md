# P10.1R hardware measurement contract

No P10.1R acceptance run is currently authorized. This file defines the follow-up contract only; it does not authorize JTAG, programming, ELF execution, UART writes, or TFDU drive.

The purpose-limited calibration run `p10_1r_20260801T190357Z_38f83531_080a35e6_18287e66` measured 1,000 transmissions on each of F0, F1, R0, and R1. It observed 4,000 raw same-module echoes, zero same-module accepted frames, and no post-TX raw edge on any module. The selected final post-TX guard is therefore 4,096 cycles (64 us): the measured maximum of zero plus a 4,096-cycle deterministic margin. The independent 256-cycle (4 us) idle qualification remains in force, making the reverse-direction quiet interval 4,352 cycles (68 us). The immutable selection record is `evidence/generated/p10_1r_echo_guard_selection.json`; these measurements authorize neither artifact reuse nor an acceptance run.

Fresh authorization must bind the final source commit; fixed/rotating performance and shutdown bitstream hashes; XSA, BSP, and ELF hashes; exact AX7020 pinmaps/XDC; `config/tfdu_rx_admission.yaml`; `config/performance/p10_1r_hardware_runtime.yaml`; fixed JTAG serial 210249855178; rotating-role JTAG serial 210512180081; lane mask at most `0x3`; and a maximum formal runtime of 1,800 seconds.

Every stage requires shutdown-before and independently verified shutdown on success, error, timeout, interrupt, and normal exit. Ethernet, SPI, rewiring, movement, rotation, angle changes, module exchange, lane masks above `0x3`, P11, 8x32, and 600 rpm remain out of scope.

The final campaign must remeasure at least 1,000 transmissions per module using the rebuilt artifacts and report first/last post-TX Rxd edges, maximum, p99, and p99.9 echo-tail cycles. The configured guard must remain no shorter than the observed maximum plus its frozen deterministic margin. The 4x4 matrix must show intended remote valid traffic, raw same-module echo (allowed), exactly zero same-module accepted DATA/ACK/protocol events, zero cross-lane accepted frames, and zero non-target CRC-valid accepted frames.

Performance acceptance then requires 1,000 clean 247-byte frames per lane at 4 Mbit/s, bounded ACK/burst tuning, 300 seconds at at least 4,000,000 application bit/s in each direction, five 64 MiB transfers in each direction, abort/reset recovery, and one 1,800-second formal run. CRC/SHA mismatch, partial/duplicate/stale commit, retry exhaustion, descriptor leak, double completion, deadlock, duty or continuous-high violation, or unverifiable shutdown is a failure.

Offline simulation, models, routed implementation, PL LEDs, and historical P10/P10.1 runs cannot substitute for these direct measurements.
