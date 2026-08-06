# P10.4 offline verifier remediation

Status: `PASS` for the verification-source-only remediation.

The generic M4 checker previously looked for 48 P10.2/P10.FF/P10.4 registers in the legacy P8 RTL block. Those registers are actually decoded by the P9/P10 endpoint and P10.1 performance-monitor RTL. The corrected checker now proves the owning decoder, the complete P10.2 128-word indexed window, and the P10.4 monitor-to-endpoint forwarding range. Four mutation-oriented unit tests protect those proofs.

The full canonical no-hardware gate then ran without cache and passed all 31 subprocesses, including Vivado non-hardware builds and XSIM. The resulting summary is `evidence/generated/offline_gate_summary.json`, SHA256 `e5c4bb88d52cdb2b479de6e2603825f59753126f6a9922b8ddfc1ba00c0952cf`. A subsequent code review tightened macro recognition from any occurrence to a complete case item, followed by canonical state/evidence metadata updates. The affected M4, P8A consistency/unit, no-hardware, status/traceability, and plan-completion checks were rerun and passed. RTL and all Vivado/XSIM build inputs remained byte-unchanged.

This remediation changes no RTL, constraints, register map, firmware, bitstream, XSA, BSP, or ELF. The frozen P10.4 artifact bytes rehash unchanged and remain bound to source commit `6ff17d33a0ea111fbd796899c49decbfa339e2c1`. No old or new hardware PASS is inherited.

The prior generic-gate FAIL remains preserved at checkpoint `e40abc2086a63a899c481881c00494df32a7cccc`. P10.4 itself remains `FAIL` because direct evidence still shows the F2→R2 directional physical blocker; P10.3 remains `PASS`. Current-run hardware authorization is `false`, both endpoints remain shutdown, and this remediation performed no hardware actions.
