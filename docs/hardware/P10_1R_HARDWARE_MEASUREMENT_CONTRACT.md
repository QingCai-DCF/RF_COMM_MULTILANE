# P10.1R hardware measurement contract

No P10.1R hardware run is currently authorized. This file defines the follow-up contract only; it does not authorize JTAG, programming, ELF execution, UART writes, or TFDU drive.

Fresh authorization must bind the final source commit; fixed/rotating performance and shutdown bitstream hashes; XSA, BSP, and ELF hashes; exact AX7020 pinmaps/XDC; `config/tfdu_rx_admission.yaml`; `config/performance/p10_1r_hardware_runtime.yaml`; fixed JTAG serial 210249855178; rotating-role JTAG serial 210512180081; lane mask at most `0x3`; and a maximum formal runtime of 1,800 seconds.

Every stage requires shutdown-before and independently verified shutdown on success, error, timeout, interrupt, and normal exit. Ethernet, SPI, rewiring, movement, rotation, angle changes, module exchange, lane masks above `0x3`, P11, 8x32, and 600 rpm remain out of scope.

The campaign must directly measure at least 1,000 transmissions per module and report first/last post-TX Rxd edges, maximum, p99, and p99.9 echo-tail cycles. The final guard must be no shorter than the observed maximum plus deterministic margin. The 4x4 matrix must show intended remote valid traffic, raw same-module echo (allowed), exactly zero same-module accepted DATA/ACK/protocol events, zero cross-lane accepted frames, and zero non-target CRC-valid accepted frames.

Performance acceptance then requires 1,000 clean 247-byte frames per lane at 4 Mbit/s, bounded ACK/burst tuning, 300 seconds at at least 4,000,000 application bit/s in each direction, five 64 MiB transfers in each direction, abort/reset recovery, and one 1,800-second formal run. CRC/SHA mismatch, partial/duplicate/stale commit, retry exhaustion, descriptor leak, double completion, deadlock, duty or continuous-high violation, or unverifiable shutdown is a failure.

Offline simulation, models, routed implementation, PL LEDs, and historical P10/P10.1 runs cannot substitute for these direct measurements.
