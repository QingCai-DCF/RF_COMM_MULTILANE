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
- 在解决问题前，先识别哪些信息是可观察的，哪些行动是可控制的，以及要求保证什么。
- 如果某个属性可以被观察、触摸感知、标记、排序或以其他方式控制，就用一个可以利用分阶段/自适应选择的策略来求解；不要把问题简化成盲目的一次性抽样。
- 对于定量、逻辑、边界或保证类等问题，在最终回答前，证明该策略在最坏情况下的充分性，并证明匹配的下界。
- 如果答案是数字，重新检查算术，并确保最终数值准确回答了问题。

## 通用性
- 这些是通用工作规则；不要针对某个特定评测、预期答案等进行定制。

## RF_COMM Rebuild Hard Constraints
- `项目约束(目标）.txt` is a hard project constraint. Do not edit it unless the user explicitly asks for an exact constraint change and confirms it.
- This workspace is the new rebuild project. Do not modify the legacy source project at `C:\Users\user\Documents\RF_COMM`.
- Default mode is `NO_HARDWARE=1`. Do not program FPGA hardware, start PS ELF files, drive TFDU pins, use XSCT hardware targets, open Vivado Hardware Manager, capture ILA, or write UART commands unless the user explicitly authorizes hardware execution.
- Any authorized hardware run must use a safe wrapper and must program TFDU shutdown afterwards. Treat the run as incomplete unless logs show `SHUTDOWN_EXIT=0` or `TFDU_SHUTDOWN_PROGRAMMED`.
- Legacy `RF_COMM` evidence proves only the scope it actually covers. Do not promote degraded lane0 evidence into 2-lane, 8-lane, Ethernet, rotation, or soak-test PASS claims.
- Imported legacy RTL, XDC, Vivado projects, tools, and software under `legacy/` or `rtl/legacy_reference/` are read-only reference inputs, not canonical build inputs.
- Old active top XDC and IP-local XDC conflict. New builds must use the canonical generated XDC at `constraints/active/PORT1.generated.xdc`, generated from `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`.
- `AB_L1` is a legacy raw-layer BAD_DIR and must not be enabled as a reliable lane until fresh lane1 raw-pulse, frame CRC, ACK-only, and session/mask readback gates pass.

## Canonical Project Inputs
- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- Register map source of truth: `config/register_map/ir_axi_regs.yaml`
- Offline gate entrypoint: `python scripts/run_offline_gates.py`
