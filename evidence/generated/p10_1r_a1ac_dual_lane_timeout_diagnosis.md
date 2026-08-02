# P10.1R a1ac dual-lane timeout diagnosis

Status: `FAIL_WITH_DIRECT_DUAL_LANE_TIMEOUT_EVIDENCE`

The four single-lane PHY controls each delivered 1,000 frames with zero sender timeout and zero retry. The 15 MB two-lane ACK case committed all bytes with clean CRC, SHA, descriptor, duty, and shutdown evidence, but the sender recorded 399 timeouts and 399 retries. Application goodput was only `3,659,562.70 bit/s`.

The high-confidence mechanism is a premature two-lane boundary ACK. The turnaround-tagged frame can complete before an older frame still active on the other serializer. The first ACK may therefore omit the older base sequence. Once that ACK starts, `endpoint_turnaround_pending_q` is cleared; a later cumulative timer ACK cannot be transmitted in endpoint mode. A full 32-frame sender window can then remain blocked until the `4,000,000`-cycle retransmission timeout.

Remediation will retain the existing safety, duty, echo guard, and half-duplex boundaries. It will hold the explicit turnaround request until the cumulative receive base covers the tagged boundary sequence, with a bounded SACK fallback for genuine loss, and will add a forced completion-skew XSIM case.

The adjacent JSON is the authoritative machine-readable record and binds every cited raw file by SHA256.
