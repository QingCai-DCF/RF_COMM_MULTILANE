# P10.4 CRC-bad root-cause diagnosis

- Status: `REMEDIATION_REQUIRED`
- Run: `p10_4_20260805T173745Z_6c7418e6_b20f137e_795f3f34`
- Source commit: `6c7418e630d07be54e01d51ba05d90d6ceac3990`
- Campaign result: `PARTIAL`
- Blocking mandatory gate: `CRC_BAD_ZERO`
- Final shutdown: fixed `PASS`, rotating `PASS`

The physical CRC counter remained zero until the final 240-second compatibility-fallback segment. The first `mask=0x3` fixed-to-rotating window produced two rejects on rotating lane1. Every `mask=0xC` rotating-to-fixed window then increased fixed lane3, reaching `113`, `324`, `604`, and finally `929`. All application CRC/SHA, commit, retry-exhaustion, descriptor, safety, and liveness hard counters remained zero.

The 8x8 matrix independently shows connector-neighbour raw coupling without accepted non-target frames. In particular, F2 transmission produced 11 F3 raw edges during the 1024-pulse vector and 45 F3 raw edges during the first 30-second framed object; the reciprocal-direction R2 object produced 95 F3 raw edges. Lane pairs 0/1 share J10 and 2/3 share J11. The transport always emits an ACK on the first schedulable lane, while the present RX quarantine follows only the same module's final physical Txd.

The evidence-supported causal hypothesis is therefore local ACK connector-pair echo reaching the adjacent parser: mask `0x3` selects ACK lane0 and exposes lane1; mask `0xC` selects ACK lane2 and exposes lane3. This is not yet called a hardware defect or a confirmed optical measurement. It is a directly testable RTL admission hypothesis.

The remediation is narrowly scoped: preserve same-module quarantine; preserve the rule that ordinary DATA TX does not blank another lane; additionally quarantine the paired receiver only while the adjacent module is emitting an actual physical ACK, then apply the existing post-TX guard and idle qualification. J10 and J11 remain independent, so the other connector's receive paths stay open. This monitor-only gate must not feed TX, permit, SD, Mode, duty, kill, scheduling, or flow-control paths.

Because the change affects RTL, no result from the old artifact bundle is inherited. A new source checkpoint, fixed/rotating bitstream, XSA, BSP and ELF bundle, complete offline verification, fresh current-run authorization, and fresh hardware campaign are required.

Machine-readable record: `evidence/generated/p10_4_crc_bad_root_cause_diagnosis.json`.
