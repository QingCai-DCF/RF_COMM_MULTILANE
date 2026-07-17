# PROJECT_CONSTRAINTS V3.1 Change Log

```text
CONFIRMATION: 确认按以上修改
CHANGE_DATE: 2026-07-17
SOURCE_PROJECT_CONSTRAINT: PROJECT_CONSTRAINTS(1).txt
SOURCE_AGENTS: RF_COMM_MULTILANE_all_progress_code_50067312.zip!/AGENTS.md
OUTPUT_PROJECT_CONSTRAINT: PROJECT_CONSTRAINTS.txt
OUTPUT_AGENTS: AGENTS.md
PREVIOUS_REPOSITORY_PROJECT_CONSTRAINT_SHA256: cff1a17ee77bbaf90080cf4f97e5920e961aefae3b6752f080e35fcf4d4b1f11
LEGACY_PROJECT_CONSTRAINT_PATH: docs/legacy/项目约束(目标）.txt
LEGACY_PROJECT_CONSTRAINT_SHA256: cff1a17ee77bbaf90080cf4f97e5920e961aefae3b6752f080e35fcf4d4b1f11
NO_HARDWARE_ACTIONS_EXECUTED: true
SOURCE_PROJECT_CONSTRAINT_SHA256: 2014a2dd33fc8eaae98cc7661946bc38021b884b7027581cff131dae9fc8d163
SOURCE_AGENTS_REPOSITORY_SNAPSHOT_SHA256: bb5336c7e98c528df27168b8e1e465a869b9961bb4884bbfa0df6fa725312966
NEW_PROJECT_CONSTRAINT_SHA256: 9688fd14a3a7431c06e65218cbc776a0c6b69e6fc544ab7fd23e20ae42a90758
NEW_AGENTS_SHA256: 6677e4589355aa96dd434f8eb5ab9567c97efcb87ca5b3aae137efbd6776aebb
```

## 1. Canonical and status changes

1. Promoted `PROJECT_CONSTRAINTS.txt` to the sole canonical technical constraint.
2. Marked the old Chinese goal file as `SUPERSEDED` and historical-only.
3. Split responsibilities: `AGENTS.md` controls execution/authorization; `PROJECT_CONSTRAINTS.txt` controls product requirements.
4. Replaced the single ambiguous hardware status with scoped statuses:
   - P7 stationary 2-lane application: PASS;
   - current Z7010 platform: PLATFORM_LIMITED_PASS;
   - Z7020/rotation/final product: PENDING.
5. Renamed current authorization to `CURRENT_RUN_HARDWARE_AUTHORIZATION` and preserved historical hardware evidence.
6. Added `config/project_state.json` and generated `PROJECT_STATUS.md` as mandatory P8A outputs.
7. Added requirement IDs and mandatory machine-readable requirement traceability.

## 2. P7 and lane-history changes

8. Preserved legacy `AB_L1 BAD_DIR` as historical evidence.
9. Added `AB_L1_CURRENT_STATUS: RESOLVED_WITHIN_P7_STATIONARY_PROFILE`.
10. Explicitly prohibited extrapolating P7 lane1 to Z7020, sector-bank, rotating or product hardware.
11. Preserved the real P7 `PS -> PL -> PHY -> PL -> PS` scoped application acceptance.

## 3. Single GLOBAL_PERMIT decision

12. Defined exactly one local active-high `GLOBAL_PERMIT` per independent endpoint.
13. Fixed endpoint: one permit shared by all eight sector banks.
14. Rotating endpoint: one permit shared by all eight rotating TX paths.
15. Prohibited dual permits, permit A/B, permit heartbeat, per-bank and per-lane external permits.
16. Removed the old ambiguous `bank-level GLOBAL_PERMIT/FAULT` wording.
17. Retained `BANK_FAULT`, lane-local permission, arm, one-hot, duty and stuck-high as independent safety conditions, not extra permit channels.
18. Defined `GLOBAL_PERMIT=0` as all-local-TX-off and `GLOBAL_PERMIT=1` as necessary but insufficient.
19. Separated SD/RX control from TX permit so receive-only acquisition can operate with permit low.
20. Added default-low behavior for power-up, reset, open input, unconfigured FPGA and partial power.
21. Added fast permit deassert, filtered assert, explicit re-arm and no partial-frame resume.
22. Added the final TX gating equation and required permit/fault/readback counters.
23. Documented the residual risk: a single permit does not detect a stuck-high-to-supply fault and is not dual-channel safety.
24. Added D17 `SINGLE_GLOBAL_PERMIT_IMPLEMENTATION` gate.

## 4. Geometry, mapping and motion changes

25. Added explicit current/forward/reverse candidate mapping formulas.
26. Added mandatory 8x8 RX/TX permutation crossbar semantics.
27. Added permutation, owner-collision, wrap and path-epoch properties.
28. Replaced unverifiable “unlimited acceleration” wording with a bounded observable motion contract.
29. Added phase error, uncertainty, edge rate, data age and reacquisition parameters.
30. Added three-dimensional mechanical/optical tolerance stack-up and Monte Carlo requirements.
31. Split handover timing into phase update, prepare, atomic commit, service gap and epoch visibility.

## 5. TFDU, duty, power and optical changes

32. Defined exact per-module 1 ms sliding-window duty: strict `<20%`, design target `<=18%`.
33. Set project `MAX_CONTINUOUS_TXD_HIGH_US <=1`.
34. Rejected fixed non-overlapping 1 ms buckets as final duty evidence.
35. Added endpoint instantaneous/average current, active-ratio and rail-droop budgets.
36. Added a formal optical link budget with provisional 6 dB minimum and 10 dB target worst-case margins.
37. Added desired-path, crosstalk, reflection, ambient and full-duplex budget categories.
38. Added D15 TFDU lifecycle/procurement and D16 system optical safety gates.

## 6. Hardware and FPGA path changes

39. Added numerical sector-bank MUX/demux delay, skew and pulse-width-distortion budgets.
40. Added fail-low power-up, select-change and partial-power behavior.
41. Moved complete Z7020 PL I/O and differential-pair budget before core-board procurement.
42. Expanded register observability for mapping, permit, arm, kill, duty and handover timing.
43. Added permit-specific CDC/reset behavior.
44. Clarified that software can read permit and request arm but cannot assert or override it.

## 7. Performance changes

45. Made the 20.46 Mbit/s ceiling derivation explicit.
46. Kept 16 Mbit/s half-duplex application goodput as the hard gate.
47. Marked 19.2 Mbit/s as conditional on the P8 airtime budget.
48. Added an explicit warning that an 18% duty design limit can make 19.2 Mbit/s unavailable with the current frame format.
49. Split handover performance into prepare, atomic commit and service-gap metrics.

## 8. Program path changes

50. Split P8 into P8A through P8E.
51. P8A closes canonical requirements/state/evidence consistency.
52. P8B closes geometry/mapping/crossbar/handover.
53. P8C closes TFDU safety, exact duty and single permit.
54. P8D closes selective-repeat/SACK/DMA.
55. P8E closes dual-target build/resource/timing/CDC.
56. Split P10 into P10A single-Z7020 migration and P10B independent dual endpoints.
57. Allowed P11 real single-lane handover to run after P10A and before P10B.
58. Clarified that 2-hour 600-rpm testing is functional acceptance, not lifetime qualification.

## 9. AGENTS.md changes

59. Updated canonical file rules and three-step user-confirmation process.
60. Added explicit AGENTS/project-constraint responsibility boundaries.
61. Preserved P7 scoped PASS while keeping final scopes pending.
62. Replaced the unconditional AB_L1 prohibition with legacy/current scoped handling.
63. Added the complete single-permit hard constraint and residual-risk rule.
64. Added exact rolling-duty and TFDU safety parameters.
65. Added multi-profile canonical input rules.
66. Added machine state, requirement IDs and evidence-consistency rules.
67. Reclassified P3/P4 and P7-specific rules as historical stage rules.
68. Added the P8A-P8E current program boundary.

## 10. Compatibility and evidence impact

- No existing P0-P7 evidence is deleted or rewritten.
- P7 remains valid only for its stationary Z7010 2-lane profile.
- New V3.1 requirements do not retroactively claim that P7 passed exact rolling duty, sector-bank mapping, Z7020, rotation or final permit hardware.
- D12-D17, Battery, Environment and Optics remain open implementation gates.
- This changelog does not authorize a hardware run.
