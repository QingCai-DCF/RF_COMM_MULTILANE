# P10.1 duplicate ACK-drop failure diagnosis

`P10_1-HW-DUPLICATE-ACK-DROP-FAILURE-DIAGNOSIS: PASS`

This PASS is only the diagnosis of the failed validation stimulus. The faults stage and P10.1 hardware acceptance remain FAIL.

Run `p10_1_hw_20260801T052733Z_9b453015_1585d1ad_9ad4f85f` completed all 19 observations and reached the XSDB PASS marker. Every vector and clean successor passed except the duplicate-DATA observation gate. The rotating receiver reported `injected_fault_observed_count=0`; both endpoints committed zero bytes during recovery, the following clean 64 MiB stream passed at 2,588,519.65 bit/s, and the stale-session vector directly reported three rejects. Both final shutdowns passed.

The 255-count ACK-drop remediation did not guarantee a DATA retry. RTL decrements the eight-bit counter when it consumes a local cumulative-ACK candidate, not once per serialized optical ACK frame. ACK candidates can therefore exhaust the counter before the fixed 4,000,000-cycle (62.5 ms) RTO, after which a later cumulative ACK covers the outstanding window. The evaluator correctly rejected the missing receiver duplicate counter.

The existing transport already has the deterministic mechanism needed for this test. `protocol_fault_flags[3]` makes the first three sender DATA attempts use `initial_sequence-1` without changing their payload metadata. The receiver computes a modular distance of `0xffff`, takes its behind-base duplicate branch, and increments `P9_RX_DUPLICATE_COUNT`. Subsequent attempts use the canonical sequence.

The next remediation will enable bit 3 on the DATA sender only and remove ACK suppression from this vector. It does not change RTL, normal protocol behavior, pin mapping, `GLOBAL_PERMIT`, TFDU shutdown/kill, duty limits, or any safety path. It requires new role-bound ELF hashes and a fresh faults run; no prior hardware PASS is inherited.

Machine-readable evidence: `evidence/generated/p10_1_hw_duplicate_ack_drop_failure_diagnosis.json`.
