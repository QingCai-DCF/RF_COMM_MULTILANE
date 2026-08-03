# P10.3 AX7020 stationary four-lane hardware acceptance plan

P10.3 may begin only after the P10.2 wiring hash, eight-module inventory, board/JTAG identities, content-addressed bitstream/XSA/BSP/ELF hashes, bounded duration, safe wrapper and a new current-run authorization are frozen together. P10.2 itself grants no hardware authority.

The ordered stages are P10_3-00 inventory/wiring freeze; 01 authorization; 02 identity; 03 shutdown images; 04 safe boot; 05 per-module intake; 06 8×8 raw/echo matrix; 07–10 lane0..lane3 at 4 Mbit/s; 11 two-lane regression; 12 aggregate 16 Mbit/s RAW capability; 13 ARQ/scheduler; 14 degradation 4→3→2→1 and recovery; 15 64 MiB streaming; 16/17 application `>=8 Mbit/s` in each half-duplex direction; 18 stationary 30-minute run; 19 verified shutdown; 20 evidence/checkpoint.

Every active stage is preceded by verified dual-board shutdown. Error, timeout, Ctrl+C and normal exit must also produce verified dual-board shutdown markers. Lane masks are limited to `0x1..0xF`. The runner must reject Ethernet, movement, rotation, rewiring, a two-hour request, missing artifacts, an old-F1 selection or any identity/hash mismatch.

P10.3 excludes Ethernet, SPI, full duplex, two-hour qualification, rotation, P11, 8×32, 600 rpm and product-final acceptance.
