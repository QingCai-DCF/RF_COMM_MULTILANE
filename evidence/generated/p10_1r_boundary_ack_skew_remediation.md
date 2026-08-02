# P10.1R dual-lane boundary ACK skew remediation

Status: `PASS` for exact-source offline remediation; direct hardware acceptance remains pending.

The isolated two-lane case delays fixed lane0 by 8,192 protocol-clock cycles while lane1 carries the tagged 32nd frame. Before the RTL change, clean traffic reached the sender retransmission timeout and recorded retries `1/0`. After the receiver held the turnaround request until its wrap-safe cumulative base passed the tagged sequence, the same case completed with retries `0/0`.

The final diagnostic starts at sequence `0xFFF0`, crosses `0xFFFF -> 0x0000`, and also completes with retries `0/0`. The 64,000-cycle fallback remains available for genuine earlier-frame loss, but normal traffic releases the ACK from cumulative state and does not pay a fixed 1 ms delay.

The first pre-fix attempt and first post-fix attempt are retained rather than deleted. They are classified in the adjacent JSON as harness setup/assertion failures; the decisive pre-fix, post-fix, and wrap logs are separately hash-bound there.

The before/after entries were produced from a dirty diagnostic worktree and remain explicitly classified as diagnostic evidence. The remediation was then checkpointed at `f8d36805c4d2fc19d1695092655629b40860e421`; the finalizer-only follow-up produced exact source commit `af46d3b9d09fca6d9c57e79b7e91ef634a1ecf5c`.

That exact source independently passed the eight-test focused XSIM suite, portable dual-endpoint fault/loss and P9 regression, fixed/rotating routed functional builds, the performance/settle model, and the complete canonical/P8C/P8D offline capture. Their paths and SHA256 values are bound in the adjacent JSON. All runs used `NO_HARDWARE=1` and `CURRENT_RUN_HARDWARE_AUTHORIZATION=false`.

This closes only the offline remediation requirement. It does not authorize JTAG, inherit any old hardware PASS, or prove direct two-board throughput. Newly frozen artifacts and a fresh per-run authorization remain mandatory before hardware acceptance.
