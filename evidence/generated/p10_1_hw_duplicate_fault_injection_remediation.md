# P10.1 duplicate-fault injection remediation

`P10_1-HW-DUPLICATE-FAULT-INJECTION-REMEDIATION: PASS`

This is an offline remediation and artifact-freeze PASS, not a faults-stage or hardware PASS.

The duplicate vector now suppresses 255 cumulative ACKs on the receiver only; the sender ACK-drop count remains zero. At 64 MHz, the hardware RTO is 62.5 ms, so the bounded 250 ms observation interval must contain at least one real DATA retransmission if the optical path remains active. The existing receiver gate still requires a positive `P9_RX_DUPLICATE_COUNT` delta and zero application commit during recovery.

No RTL, pinmap, `GLOBAL_PERMIT`, TFDU kill, rolling-duty, or normal runtime path changed. The validation-firmware source fix is commit `a47ac64f408b11798f2e54402c003663be6b8442`; the final artifact source is `9b453015fdc9a4c16373ac185099ef87238a142e`.

The functional bitstream, XSA, and BSP content hashes remain unchanged and were re-bound to the final source namespace after a clean reuse-existing audit. The role-bound ELF hashes changed:

- fixed: `27177f776520d3266cf7733b4a905d1eceb24a71b871797ae4dfa9f7aab9ac93`
- rotating: `3f023515e87cad79ec92cbb1353a1079b43356b1656904be7dacf39148c83fee`

Offline verification passed 19 hardware-acceptance unit tests, 10 finalizer unit tests, Python compilation, both role builds, the native crypto protocol test, and a byte-identical native PE reproducibility rebuild. `NO_HARDWARE=1` and `CURRENT_RUN_HARDWARE_AUTHORIZATION=false` remained in force.

The earlier `a47ac64f…` artifact namespace is preserved as an unreferenced intermediate build and is explicitly ineligible for authorization. Only the `9b453015…` namespace is the final frozen set.

Old ELF hardware results are not inherited by this bundle. A fresh immutable run authorization, shutdown-before, faults run, and then the full remaining campaign are required. Machine-readable evidence is `evidence/generated/p10_1_hw_duplicate_fault_injection_remediation.json`.
