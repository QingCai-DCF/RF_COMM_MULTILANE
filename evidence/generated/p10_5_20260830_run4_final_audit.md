# P10.5 run 4 final audit

- Classification: `PASS_WITH_NONBLOCKING_LIMITS`
- Runner result: `PASS`
- Run ID: `p10_5_20260830T142630Z_e1f8c01a_4015142e_79607d01`
- Authorization: ordinal `4` of `10`, consumed; `6` remain unused
- Fixed / rotating shutdown: `PASS` / `PASS`
- Immutable manifest: `1107/1107` files rehashed, `0` failures

All 14 hardware stages passed. This includes every 1+1, 2+1/1+2 and directed 2+2 mask case, dynamic role commit, the 300-second performance stage, five simultaneous 64 MiB streams in each direction, direction-isolated fault/recovery cases, and the 1800-second formal 2+2 stage.

The fixed-to-rotating and rotating-to-fixed application goodputs were both `4,292,171.093 bit/s`, passing the mandatory 4 Mbit/s threshold. Neither direction reached the nonblocking 4.8 Mbit/s stretch target, so Goal section 47 requires `PASS_WITH_NONBLOCKING_LIMITS`.

The formal hardware-reported TX-capable interval was exactly `1800.000 s`; the longer observation/shutdown envelope was `1800.325 s`. The runtime-limit gate passed, both boards shut down, and the subsequent `900.163207 s` cooldown exceeded the required `900.163 s`. Formal transport timeout, CRC, SHA, partial/duplicate/stale commit, retry exhaustion, descriptor leak and double-completion counters were all zero.

The final summary preserves an aggregate count of 292 nonformal diagnostic TX timeouts and explicitly marks them diagnostic. This does not replace or relax the Goal's direct formal-window hard gate, whose timeout count is zero.

The run did not use Ethernet or SPI, move hardware, change wiring, replace a module during the run, start P11, or claim external electrical/optical or product-final acceptance.
