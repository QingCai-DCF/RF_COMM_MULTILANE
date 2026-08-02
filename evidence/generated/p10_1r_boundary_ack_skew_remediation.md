# P10.1R dual-lane boundary ACK skew remediation

Status: `PASS` for the diagnostic comparison only.

The isolated two-lane case delays fixed lane0 by 8,192 protocol-clock cycles while lane1 carries the tagged 32nd frame. Before the RTL change, clean traffic reached the sender retransmission timeout and recorded retries `1/0`. After the receiver held the turnaround request until its wrap-safe cumulative base passed the tagged sequence, the same case completed with retries `0/0`.

The final diagnostic starts at sequence `0xFFF0`, crosses `0xFFFF -> 0x0000`, and also completes with retries `0/0`. The 64,000-cycle fallback remains available for genuine earlier-frame loss, but normal traffic releases the ACK from cumulative state and does not pay a fixed 1 ms delay.

The first pre-fix attempt and first post-fix attempt are retained rather than deleted. They are classified in the adjacent JSON as harness setup/assertion failures; the decisive pre-fix, post-fix, and wrap logs are separately hash-bound there.

All entries were produced from a dirty diagnostic worktree with `NO_HARDWARE=1` and `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`. They are not exact-source acceptance evidence and do not authorize JTAG or inherit hardware PASS. A clean source checkpoint, complete offline regression, newly frozen artifacts, and a fresh per-run authorization remain mandatory.
