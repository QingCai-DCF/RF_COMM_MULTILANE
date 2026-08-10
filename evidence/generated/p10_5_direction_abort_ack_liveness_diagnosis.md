# P10.5 direction-abort ACK liveness diagnosis

- Status: `OFFLINE_REMEDIATED_PENDING_NEW_ARTIFACT_HARDWARE`
- Failed run: `p10_5_20260810T070056Z_eefca40c_78726594_498ca074`
- Failed case: `fault_abort_r2f`
- Root cause: canceled DATA piggyback cleared ACK dirty without a later duplicate/credit event restoring it
- Fixed frozen window: `next=52`, `ack_base=21`, `outstanding=31`, `retry_exhausted=1`
- Safety containment: fixed shutdown `PASS`, rotating shutdown `PASS`
- Runtime accounting corrected: `12.026811 s` recorded versus `617.530 s` observed; corrected cooldown `308.765 s`
- Post-fix 52-fragment symmetric abort XSIM: `PASS`
- Hardware PASS inherited: `false`
- Hardware actions executed by remediation: `false`

New immutable FPGA/software artifacts and a complete fresh hardware campaign
are mandatory before P10.5 can be promoted.

