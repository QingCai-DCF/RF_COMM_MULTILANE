# P10.5 capability timer root-cause audit

- Status: `PASS` for root-cause isolation; hardware acceptance remains `PENDING_RETEST`.
- Failed run: `p10_5_20260809T225128Z_ec4dc468_f7fe756b_f3a5718e`.
- Both endpoints returned P10.1 status `0x107` (`TIMER`) after one clean 256-KiB object; the host observed 1397 ms against the capability case's 1000-ms deadline.
- Both endpoints recorded 262144 TX bytes and 262144 RX bytes, 1063 control-only ACKs, and zero CRC, SHA, retry-exhausted, transport-timeout, direction-reject, or role-epoch-reject errors.
- Both final shutdown results are `PASS`.

The capability gate was incorrectly implemented as a one-second duration-accuracy test. That deadline included DMA/RX priming and the first complete optical object, so it expired before the post-commit capability readback. This is a host-plan defect, not evidence of a physical-link, protocol, DMA, integrity, or safety failure.

The remediated gate performs one finite 1-MiB transfer (four 256-KiB objects), with a 10-second active-runtime guard. All required 10/20/30/300/1800-second timed stages remain unchanged. The target bitstreams, XSA, BSP, and ELF are unchanged; a new exact harness freeze, plan hash, current-run authorization, and run ID are required before retest.
