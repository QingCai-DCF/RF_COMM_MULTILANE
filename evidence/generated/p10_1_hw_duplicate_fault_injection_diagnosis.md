# P10.1 duplicate-fault injection diagnosis

`P10_1-HW-DUPLICATE-FAULT-INJECTION-DIAGNOSIS: PASS`

This PASS classifies the failure; it is not a faults-stage or hardware PASS.

The immutable run `p10_1_hw_20260801T042441Z_bfff4836_1585d1ad_9ad4f85f` executed all 19 planned observations and reached the XSDB stage PASS marker. Every other fault and clean successor passed, including all reset/rebootstrap paths. Both final shutdowns passed. The stage remained FAIL because the rotating receiver reported `injected_fault_observed_count=0` for `duplicate_segment_f_to_r_64m`. By comparison, the fixed receiver directly reported three stale-session rejects for `stale_segment_r_to_f_64m`.

Source audit shows that the duplicate vector currently writes bit 8 of `P9_FAULT_INJECTION`. That bit is not a direct duplicate-DATA command; it is an ACK-drop count of one. The endpoint transports four DATA frames per burst and uses cumulative ACKs. A later cumulative ACK can therefore acknowledge the outstanding data before the 62.5 ms RTO, so one dropped ACK is not a deterministic duplicate stimulus. The strict evaluator is correct to reject the zero receiver counter.

The bounded remediation is receiver-only ACK suppression long enough to cross at least one RTO. The proposed count is 255, with the sender count held at zero. The receiver must still show a positive `P9_RX_DUPLICATE_COUNT` delta within the existing 250 ms observation interval, and the recovery vector must still show zero remote/partial/duplicate/stale application commits and safe shutdown. This changes validation firmware, requires new role-bound ELF hashes, and requires a fresh faults hardware run. No wiring or optical failure is inferred.

Machine-readable evidence: `evidence/generated/p10_1_hw_duplicate_fault_injection_diagnosis.json`.
