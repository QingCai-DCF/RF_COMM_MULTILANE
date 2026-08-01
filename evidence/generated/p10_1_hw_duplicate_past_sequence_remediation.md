# P10.1 duplicate-DATA remediation freeze

Status: **PASS (offline freeze only)**  
Source commit: `bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1`  
Goal SHA256: `b3d0ae793a89ba270ca72880fb4fa38bcb17ac7631f3fc650e2557963840f9d3`

The failed ACK-drop injection is replaced by a deterministic sender-side duplicate-DATA vector. The sender applies protocol fault flag bit 3 and transmits three same-session DATA attempts at `object_initial_sequence - 1`; the receiver's established behind-base classification (`receive_distance >= 16'h8000`) increments its duplicate counter. The clean successor restores the canonical sequence.

This change does not alter the functional bitstreams, AX7020 pinmaps, lane masks, single `GLOBAL_PERMIT`, TFDU `SD`/`Txd` kill, duty guard, or shutdown paths. It rebuilds and freezes role-specific PS ELFs:

- fixed ELF: `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- rotating ELF: `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- fixed bitstream: `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- rotating bitstream: `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`

Offline validation passed: 19 hardware-runner unit tests, 10 finalizer unit tests, ten-record artifact collection, retry-override validation, and `git diff --check`. No hardware action occurred during this freeze.

No old hardware PASS is inherited by the new ELF bundle. The next admissible step is a fresh, run-bound `faults` authorization followed by shutdown-before, the real fault campaign, and verified shutdown on every exit path.
