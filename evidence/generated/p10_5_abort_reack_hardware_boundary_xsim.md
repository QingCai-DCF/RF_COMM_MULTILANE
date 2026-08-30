# P10.5 abort/re-ACK hardware-boundary XSIM

- Status: `PASS`
- Hardware actions executed: `false`
- Boundary reproduced: `TX_NEXT=84/84`, fixed `ACK_BASE=52`, fixed `OUTSTANDING=32`
- Post-abort result: surviving fixed TX descriptors retired to `OUTSTANDING=0`; physical ACK-good and rotating control-only fallback both increased; direction/epoch rejects and retry exhaustion remained zero.
- Log SHA256: `7c39852419ddd26c7fca5ce6d5eb86f4166f0205e48e9a76db93903966e21365`

This excludes the exact partial-ACK boundary alone as a sufficient reproducer in ideal XSIM. It does not promote hardware status. The next run captures live pre-terminal hardware counters because terminal cleanup erased those counters in run 2.
