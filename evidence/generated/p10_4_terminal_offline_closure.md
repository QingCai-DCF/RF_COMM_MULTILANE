# P10.4 terminal offline closure

Status: `FAIL_WITH_PRESERVED_EVIDENCE`

The P10.4-specific repository intake and existing-evidence checks pass. They directly reverified P10.3, P10.2, P10.1R, P8C safety, and canonical state/requirements consistency without hardware actions.

An additional run of the repository-wide generic offline gate returned `FAIL`. Its root failure is the legacy M4 static predicate: generated headers and documentation contain the P10.2 snapshot, P10 first-fault forensic, and P10.4 counter/local-source offsets, but `rtl/ir_axi_regs_new.sv` does not contain the 48 literal offset tokens that the old checker requires. The plan-completion failures are downstream consequences of that predicate.

No RTL or checker change is made in this terminal checkpoint. Such a change after artifact freeze would create a new source state and require new immutable bitstream/XSA/BSP/ELF artifacts and fresh hardware acceptance. The current P10.4 campaign had already failed closed on direct F2→R2 physical-direction evidence.

- P10.4 intake: `PASS` — `evidence/generated/p10_4_repo_intake.json`
- Generic offline gate: `FAIL` — `evidence/generated/offline_gate_summary.json`
- Generic offline summary SHA256: `abeffc9ae714b0dd2644c702a9cecff1866cba9493b7e295dcbd294aa4558e87`
- Missing literal RTL offset predicates: `48`
- Hardware actions in offline closure: `false`
- Current-run authorization: `false`
- Fixed/rotating shutdown: `PASS` / `PASS`
- P10.3 scoped PASS: preserved
- P10.4: `FAIL`
- P11: `NOT_STARTED`
