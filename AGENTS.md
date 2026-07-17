# RF_COMM_MULTILANE Agents

# 指南

## 规则 0
- 可以花费任意多的时间进行思考。
- 不要发送可选的 commentary 消息。
- 不要用 commentary 汇报进度、叙述状态或解释中间过程。
- 只有在工具调用需要，或用户明确要求状态更新时，才使用 commentary。
- 对于不需要工具的任务，先完成推理，然后只在 final 中回答。

## 推理
- 优先使用第一性原理推理，而不是模式匹配。
- 在解决问题前，先识别哪些信息是可观察的、哪些行动可控制、要求保证什么。
- 对定量、逻辑、边界或保证类问题，在最终回答前复核最坏情况充分性和算术。
- 不得用阶段性 PASS、proxy evidence 或历史经验替代当前 scope 所需的直接证据。

## 通用性
- 这些是通用工作规则；不要针对特定评测或预期答案定制。

# 1. Canonical 文件与职责边界

- `PROJECT_CONSTRAINTS.txt` is the sole canonical normative project constraint.
- `docs/legacy/项目约束(目标）.txt` is historical and superseded. It must not override `PROJECT_CONSTRAINTS.txt`.
- Do not edit `PROJECT_CONSTRAINTS.txt` unless:
  1. the user explicitly requests a constraint revision;
  2. the proposed change list is shown to the user;
  3. the user confirms that change list.
- After a confirmed constraint revision, preserve a changelog and previous-version hash.
- `AGENTS.md` governs agent execution, authorization, safety workflow, repository boundaries and evidence discipline.
- `PROJECT_CONSTRAINTS.txt` governs product goals, architecture, performance, geometry, protocol, hardware design and verification criteria.
- `AGENTS.md` must not silently redefine product goals.
- `PROJECT_CONSTRAINTS.txt` does not itself authorize a hardware run.

# 2. Repository Boundary

- This workspace is the rebuild project `RF_COMM_MULTILANE`.
- Do not modify the legacy source project at `C:\Users\user\Documents\RF_COMM`.
- `legacy/`, `rtl/legacy_reference/` and `docs/legacy/` are read-only reference inputs.
- Imported legacy RTL, XDC, Vivado projects, tools and software are not canonical build inputs.

# 3. Current Scope and Status

Preserve these scoped states unless newer canonical evidence changes them:

```text
P7_STATIONARY_2LANE_APPLICATION_ACCEPTANCE: PASS
CURRENT_Z7010_PLATFORM_ACCEPTANCE: PLATFORM_LIMITED_PASS
Z7020_TARGET_ACCEPTANCE: PENDING_Z7020_HW
ROTATION_ACCEPTANCE: PENDING_FINAL_MECHANICAL
FINAL_PRODUCT_HARDWARE_ACCEPTANCE: PENDING_HW
```

- Offline gates may not promote any hardware scope.
- Offline gates must not erase an existing scoped hardware PASS such as P7 stationary 2-lane acceptance.
- `AB_L1` has a legacy `BAD_DIR` record. Preserve that history.
- Current lane1 usability is determined by the latest canonical immutable P7 evidence.
- Do not extrapolate the stationary P7 lane1 PASS to Z7020, sector-bank, rotating or product hardware.

# 4. Hardware Authorization and Safe Execution

- Default mode is `NO_HARDWARE=1`.
- Do not program FPGA hardware, start PS ELF files, drive TFDU pins, connect XSCT/XSDB hardware targets, open Vivado Hardware Manager, capture ILA/VIO, write UART commands, use real Ethernet/SPI peers or operate a motor unless the user explicitly authorizes the current hardware run.
- Historical authorization does not authorize a new run.
- Every authorized hardware run must have:
  - current-run authorization;
  - immutable bitstream/ELF paths and SHA256;
  - explicit board/profile/XDC/register-map inputs;
  - bounded maximum runtime;
  - safe wrapper;
  - shutdown-before;
  - shutdown-on-error, timeout, Ctrl+C and normal exit;
  - shutdown-after evidence.
- Treat a hardware run as incomplete unless logs show `SHUTDOWN_EXIT=0`, `TFDU_SHUTDOWN_PROGRAMMED`, or a stage-approved equivalent.
- Missing tools or unavailable hardware must be `SKIP_WITH_REASON` or FAIL with evidence, never PASS.

# 5. Single GLOBAL_PERMIT Hard Constraint

- Each independent endpoint has exactly one local active-high `GLOBAL_PERMIT`.
- The fixed endpoint distributes its one permit to all eight sector banks.
- The rotating endpoint distributes its one permit to all eight rotating TX paths.
- Do not introduce:
  - dual-channel permits;
  - permit A/B;
  - permit heartbeat;
  - per-bank `GLOBAL_PERMIT`;
  - per-lane external `GLOBAL_PERMIT`;
  - software-emulated second permit channels.
- `BANK_FAULT`, `LANE_TX_PERMIT`, `ENDPOINT_ARMED`, TX one-hot, frame admission, duty guard, stuck-high guard and TX kill are allowed and mandatory, but they are not extra global permit channels.
- `GLOBAL_PERMIT=0` must force all local physical TX paths off.
- `GLOBAL_PERMIT=1` is necessary but never sufficient for TX.
- The permit must default low at power-up, reset, open circuit, undriven input, FPGA-unconfigured state and partial-power state.
- Permit deassertion must reach the final TX kill path without PS, FreeRTOS, TCP, SPI, AXI polling or a normal frame-state transition.
- Permit reassertion must require explicit re-arm and must not resume a partial frame.
- Receive-only acquisition may operate while `GLOBAL_PERMIT=0`.
- SD control remains separate from the single global TX permit.
- Software may observe permit state and request arm, but may not create, override or bypass physical permit high.
- Do not claim that a single active-high permit detects a stuck-high fault.
- Do not claim dual-channel, SIL/PL or redundant safety properties from this architecture.

# 6. TFDU6102 Safety Hard Constraints

- `Txd` is active high.
- `Rxd` is active low.
- `SD` is active-high shutdown.
- Static `Mode=HIGH` selects MIR/FIR; do not mix static mode with dynamic mode programming.
- Wait at least 500 us after shutdown exit before normal RX/TX operation.
- Physical Txd must default low on reset/fault.
- Full shutdown requires SD high and Txd low.
- Receive-only acquisition may keep SD low only while Txd is hard-disabled.
- Per-module exact rolling-duty requirement:
  - any clock-aligned 1 ms sliding window;
  - strict `<20%` hard limit;
  - `<=18%` design target.
- Project `MAX_CONTINUOUS_TXD_HIGH_US` is `<=1`.
- Stuck-high, rolling-duty, one-hot, frame admission, pulse-limit and shutdown guards are mandatory in RTL/external hardware as applicable.
- Keep `docs/TFDU6102_SAFETY_SUMMARY.md`, `docs/tfdu6102_safety_contract.md`, RTL properties and hardware gates aligned.

# 7. Canonical Inputs and Profiles

Canonical project sources:

- Project constraint: `PROJECT_CONSTRAINTS.txt`
- Register map: `config/register_map/ir_axi_regs.yaml`
- Requirements: `config/project_requirements.yaml` after P8A
- Machine state: `config/project_state.json` after P8A
- Offline gate: `python scripts/run_offline_gates.py`

Current development profile only:

- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`

Future profiles must be separate:

- `board_profiles/z7010_2lane/...`
- `board_profiles/z7020_fixed_8lane/...`
- `board_profiles/z7020_rotating_8lane/...`

The AX7010 pinmap/XDC is canonical only for `Z7010_2LANE_DEV`. Never reuse it for either final Z7020 endpoint.

# 8. State, Requirements and Evidence Discipline

- `config/project_state.json` is the machine-readable status source after P8A.
- `PROJECT_STATUS.md` must be generated from it.
- `config/project_requirements.yaml` is the machine-readable requirement source after P8A.
- Every new hard requirement must have a requirement ID.
- Every PASS claim must reference a test ID, profile, artifact hashes and evidence path.
- Requirements without verification evidence remain PENDING.
- Historical replay or diagnostic summaries must not override canonical final evidence.
- Contradictory PASS/FAIL/PENDING fields must fail the consistency gate.
- Do not delete failed evidence or legacy failures.
- Do not use Markdown summaries as substitutes for raw logs/JSON/CSV.
- Do not promote:
  - offline/simulation to hardware;
  - Z7010 to Z7020;
  - stationary 2-lane to rotating 8-lane;
  - degraded to normal configuration;
  - proxy/ILA inference to external electrical/optical measurement.

# 9. Current Program Boundary: P8 and Later

- P8 is offline by default.
- P8 must preserve P0-P7 regression and scoped PASS states.
- P8 must not execute hardware without new current-run authorization.
- P8 must maintain common-source `Z7010_2LANE_DEV` and `Z7020_8LANE_TARGET` builds.
- P8 must implement the single active-high `GLOBAL_PERMIT` architecture exactly as defined in `PROJECT_CONSTRAINTS.txt`.
- P8A must establish canonical requirements and machine state before broad architecture changes.
- P8B must close geometry/mapping/crossbar/handover properties.
- P8C must close exact duty, TFDU safety and single permit properties.
- P8D must close selective-repeat and DMA data plane.
- P8E must close dual-target build/resource/timing/CDC.
- Do not combine all P8 work into an unreviewable monolithic change.

# 10. Historical Stage Rules

- P3/P4 pre-hardware rules are historical. Move or retain them under `docs/legacy_stage_rules/P3_P4_RULES.md` when P8A performs repository cleanup.
- P7 runtime optimization rules are historical and apply only when reproducing or auditing P7.
- Preserve `docs/P7_RUNTIME_OPTIMIZATION_CONSTRAINTS.md` and the Stage 66 campaign policy as immutable historical evidence.
- P7-specific run ordinals, caching exceptions and dated authorization do not govern P8 or later stages.

# 11. Automation Behavior

- Prefer focused tests while iterating, followed by each required complete gate once before an acceptance checkpoint.
- Fail closed when scope, artifact, profile, permit state or evidence provenance is uncertain.
- Do not silently weaken safety, performance or evidence requirements to make a gate pass.
- Do not claim product-final PASS until every final field in `PROJECT_CONSTRAINTS.txt` is supported by final-hardware evidence.
