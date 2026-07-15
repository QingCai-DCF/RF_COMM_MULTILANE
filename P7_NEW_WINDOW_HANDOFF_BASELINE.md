# P7 新窗口交接基准

> 快照时间：2026-07-11T11:23:37.405+08:00
> 工作区：`C:\Users\user\Documents\RF_COMM_MULTILANE`
> 用途：让一个全新的 Codex 窗口在不依赖旧对话上下文的情况下，安全、准确地继续现有 P7 goal。
> 状态：**工作未完成；硬件 acceptance 尚未执行；最终 1800 秒 stationary run 尚未启动。**

本文件是交接快照，不替代 goal objective、`AGENTS.md` 或 P7 计划。若内容冲突，以最新用户指令、`AGENTS.md`、goal objective 和 P7 计划为准。新窗口必须先复核实际文件、Git 状态、进程和证据；不要仅凭本文件宣称 PASS。

旧窗口的 goal service 在快照时报告 `paused`，不是 `complete` 或 `blocked`。所有旧窗口子任务已停止写入并结束；新窗口应使用下面提供的 `/goal` prompt 重新承接同一目标，不要创建定时继续任务。

## 1. 权威输入与读取顺序

新窗口开始后，依次完整读取：

1. `C:\Users\user\.codex\attachments\b91d562c-df1b-4626-8256-f1dd87a7da0e\goal-objective.md`
   - bytes: `14113`
   - SHA256: `0b979b83027143a565a0b4a74d476c5341045eee41c743dcec81ebf4e34ef3a0`
2. `C:\Users\user\Documents\RF_COMM_MULTILANE\AGENTS.md`
3. 本文件：`C:\Users\user\Documents\RF_COMM_MULTILANE\P7_NEW_WINDOW_HANDOFF_BASELINE.md`
4. `C:\Users\user\Downloads\p7_stationary_local_application_layer_no_ethernet_30min_plan.md`
   - bytes: `34806`
   - SHA256: `c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd`
5. goal objective 指定的 `PROJECT_STATUS.md`、TFDU6102 safety contract、P0-P6 summaries 和 immutable manifests。

P7 计划文件目前不在仓库根目录；使用上面的 `Downloads` 绝对路径，不要因根目录同名文件不存在而猜测或重建计划。

## 2. 不得改变的目标与边界

- 完整实现并验证 P7 本地 application-layer transport：真实 PS ELF/mailbox runtime、任意长度对象分片/重组、双 lane 调度、队列/背压、故障恢复、CRC/SHA256 完整性和机器可解析 evidence。
- 最终验收只能有一次正式 `1800 seconds` stationary application run；没有额外 30 分钟 calibration，也没有 2 小时 soak。
- 不使用 Ethernet；不插网线；不移动、旋转、调角或遮挡硬件。
- 物理 lane 仅 lane0/lane1；允许 mask `0x1`、`0x2`、`0x3`，最大 `0x3`。
- 最终主路径必须是 PS input -> real PS ELF -> AXI -> PL/TFDU physical link -> PL/AXI -> PS output，并验证反向 ACK；JTAG/AXI 只能是辅助路径。
- 不编辑 `项目约束(目标）.txt`。
- 不修改 legacy 项目 `C:\Users\user\Documents\RF_COMM`。
- 不改变既定计划，不创建任何定时继续任务或自动化。
- 除既定、显式授权的安全 wrapper 外，不得启动额外硬件操作。
- 任何硬件失败都必须停止新 TX、保存原始证据并独立恢复 shutdown；没有 `SHUTDOWN_EXIT=0` 或 `TFDU_SHUTDOWN_PROGRAMMED` 的运行不完整。
- 离线/仿真结果不得把 `HARDWARE_ACCEPTANCE: PENDING_HW` 提升为 PASS。
- Ethernet、rotation、8-lane 和 product-final 状态最终仍必须保持 deferred/pending，不能因 P7 通过而升级。

## 3. Git 基线

- Branch: `codex/p7-stationary-application`
- Current committed HEAD: `81b0f2ea68be5399c8dcdf734ac99f49fa49e3bd`
- HEAD subject: `fix: validate Vivado exit helper topology`
- 之前的 P7 提交：
  - `53dca543` — `feat: add P7 stationary local application transport`
  - `246d06f5` — `fix: harden P7 preflight and preserve retry evidence`
  - `81b0f2ea` — `fix: validate Vivado exit helper topology`
- P6/main 基线：`ca041d48`

当前工作树是有意的 dirty state。不要 reset、checkout、clean 或覆盖用户/代理改动。开始时先运行 `git status --short`、`git diff --stat` 和 `git diff --check`，并逐项归属变更。

## 4. 已完成且需要保留的历史

### H1/H1b 离线基线

- H1 source commit: `246d06f58986593e53dbde2b9cd62888e2bafa35`
- H1b source/current HEAD: `81b0f2ea68be5399c8dcdf734ac99f49fa49e3bd`
- H1b P7 offline gate 曾在干净 H1b 上 PASS。
- H1b checkpoint：
  - path: `evidence/generated/p7_offline_gate_summary.json`
  - SHA256: `6e2d353edf0b6237bb3e70ee4e7cfac94fe89e11751db2da93b20029162d882b`
  - hardware status: `PENDING_HW`
- 该 checkpoint 已冻结进 r3 历史目录；因为当前源代码已修改，它不能授权未来 r4。r4 前必须在新的干净 source commit 上重新运行一次新的 P7 offline gate。

### r2

- r2 在 stage1 的 read-only preflight containment 失败；candidate/JTAG/TX/PS 均未启动。
- 随后独立 P4 recovery shutdown PASS，失败证据已冻结并随 H1b 提交。
- r2 不得 resume。

### r3

- Run ID: `p7_20260711_stationary_app_r3`
- Plan SHA256: `aa5eb1bfd16b3a047a70056a44e2eb50cc7b19f01603fe9f3796db6640acb91a`
- Plan generator、66 项授权和 66 项 dry validation 曾 PASS；生成阶段没有硬件操作。
- r3 executor 只启动过一次、未 resume，并在 stage index 0 / `p7_safe_idle` 停止：
  - preflight/board identity/helper containment PASS；
  - shutdown-before 和 shutdown-after 都以 rc `41` 失败；
  - 根因是 H1b Tcl 的非法 `string map {\ /}`，错误发生在 `open_hw_manager` 和 `program_hw_devices` 之前；
  - candidate stage process、candidate bitstream、JTAG AXI transaction、TX/RX、PS ELF、mailbox/UART 全部未启动；
  - completed stage count `0`，attempt count `1`；
  - 最终 stationary run 没有启动。
- r3 **永远不得 resume**。修复验证并生成新 checkpoint 后，下一硬件 run ID 必须是 r4。

r3 证据根目录：

`evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r3/`

冻结的历史输入目录：

`evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r3/historical_preflight_inputs/`

其 manifest schema 为 `rf-comm-p7-historical-failed-stage-inputs-v1`，冻结 7 项输入，包括 H1b Tcl Git blob `e8d2500ba5708dec57acc1bd0cfb46fa926e55b7`（25601 bytes；SHA256 `ede2539f3f48fdb9fa4ca008fc56be496b58bf49bf0f84fe99e5d5e935c625fd`）。不要改写或删除这些失败证据。

### r3 独立安全恢复

恢复目录：

`evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r3/recovery_shutdown_after_failed_stage1_20260711T0252Z/`

观测证据：

- `SHUTDOWN_RAW_EXIT=125`
- `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`
- `SHUTDOWN_EXIT=0`
- `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`

因此最近一次已记录的物理安全状态是独立 shutdown PASS。新窗口仍必须在任何未来授权硬件步骤前重新只读核查环境和安全前置条件。

## 5. 当前未提交源码工作

当前 HEAD 之后有 9 个 source/test 文件被修改：

- `scripts/hw/p7_jtag_axi_transactions.tcl`
- `scripts/hw/p7_ps_application_execute.tcl`
- `scripts/hw/run_p7_jtag_axi_stage_safe.py`
- `scripts/hw/run_p7_ps_application_stage_safe.py`
- `tools/run_p7_authorized_hardware_sequence.py`
- `tools/summarize_p7_hardware.py`
- `tests/test_p7_authorized_hardware_sequence.py`
- `tests/test_p7_jtag_axi_stage_safe.py`
- `tests/test_p7_ps_application_stage_safe.py`

已实现但尚未完成主线程最终审阅/提交的内容：

- 修复两个活动 Tcl 中 6 处非法 path map。
- 新增 fail-safe 单行 error sanitizer。
- 在 shutdown/stage 的 `program_hw_devices` 调用前记录 programming attempt。
- wrapper 只信任 fresh result；要求唯一且精确的 TFDU marker、attempt marker 和 P7 PASS marker；拒绝 stdout/`SHUTDOWN_EXIT` 替代与重复 marker。
- shutdown bitstream 绑定授权路径；PS shutdown 绑定 frozen path/SHA。
- outer sequence validator 检查 before/after attempted/programming、fresh result 和精确路径/SHA。
- 增加 Tcl offline command-stub、program failure、ordering 和 wrapper provenance 回归。
- `tools/summarize_p7_hardware.py` 增加窄化的 r3 failed-stage 历史解析，并已对真实 r3 私有解析入口报告 0 errors。

子任务在停止写入前报告：8 个 Tcl/wrapper/outer-validator 相关文件的 5 个 focused suites 为 `89/89 PASS`，`py_compile` 和 `git diff --check` PASS；这不是完整 gate，主窗口应复核。

## 6. 当前仍未闭合的审计项

在创建本交接快照时，以下事项仍未完成，不能把当前工作树提交为已验证 PASS：

1. `tools/summarize_p7_hardware.py` 的 generic future-PASS shutdown 汇总/ledger 路径仍需收紧：普通 P7 stage 只能接受 fresh result 中唯一、精确的授权 shutdown path、`P7_TCL_PROGRAMMING_ATTEMPTED=1`、`TFDU_SHUTDOWN_PROGRAMMED` 和 `P7_SHUTDOWN_RESULT=PASS`，同时要求 block-level `attempted=true` 与 `programming_attempted=true`；不得接受 stdout fallback 或单独 `SHUTDOWN_EXIT=0`。P4 recovery 保持独立逻辑。
2. `tests/test_summarize_p7_hardware.py` 尚未加入 r1/r2/r3 三 epoch 正向测试、r3 tamper tests，以及 generic fresh-result-only shutdown 的正负测试。
3. PS frozen-shutdown 的 outer-validator 正向测试需要确认/补齐。
4. 完整 `tests.test_summarize_p7_hardware` 没有可声明的最终 PASS 结果。快照时曾观察到只读测试进程 PID `23204`：`python.exe -m unittest tests.test_summarize_p7_hardware`；交付前复核时该进程已自然退出，但没有取得可采信结果。不要把自然退出当作 PASS，必须明确重跑。
5. 尚未在新的 active source commit/checkpoint 下生成并验证包含 r3 的完整 sequence ledger。
6. 尚未运行新的完整 P7 offline gate；不要在 dirty source 上运行或消费一次性 checkpoint。

## 7. 当前 generated 输出与清理边界

当前 `git status` 还包含：

- 3 个 tracked `evidence/generated` 文件被 H1b gate 重写：
  - `evidence/generated/p7_ps_runtime_build_summary.json`
  - `evidence/generated/p7_ps_runtime_build_summary.md`
  - `evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json`
- 26 个 untracked `evidence/generated/p7_*` H1b gate 输出。
- untracked r3 evidence 根目录；它必须保留并进入下一准确的失败修复提交。
- 本交接文件自身也是用户要求的新文件，必须保留。

在创建下一 source commit 之前：先验证 H1b checkpoint 和所需输入均已完整冻结到 r3 历史目录；随后只清除/恢复上述 H1b generated 输出，绝不能删除 r3 失败/恢复 evidence。不要使用 destructive `git reset --hard`、`git checkout --` 或 `git clean`。

## 8. 快照时的进程与授权状态

2026-07-11T11:23:37+08:00 附近的只读观察：

- root 环境 `RF_COMM_HW_AUTH` 为空。
- `.hardware_authorization/P7_GO.txt` 不存在。
- `.hardware_authorization/P7_ABORT.txt` 不存在。
- `.hardware_authorization/p7_execution.lock` 不存在。
- 没有观察到 Vivado、cs_server、xsdb 或 rdi_xsdb P7 helper。
- 存在外部历史 `hw_server.exe` PID `45220`，命令行日志属于 legacy `RF_COMM`。它不是本次 P7 启动的；不得终止、重启或修改它。PID 可能随时间变化，新窗口必须重新识别，而不是只按旧 PID 操作。
- 存在若干与 Codex/MCP 有关的 Python 服务；不要误杀。
- 快照时曾存在上节所述 summarizer 单元测试 PID `23204`；交付前已确认它不再运行，但没有可采信测试结果。

## 9. 安全继续顺序（保持现有计划）

新窗口应从当前 dirty worktree 继续，不要从头重做已经完成的 P7 实现，也不要跳过失败证据：

1. 只读复核 Git、goal、计划、AGENTS、安全文档、r3 ledger/raw logs/manifest/hash 和当前进程；确认没有其他代理仍在写共享树。
2. 审阅并完成第 6 节的 generic shutdown provenance 和 summarizer tests；不要触碰硬件。
3. 运行有针对性的 non-hardware suites、完整 summarizer suite、P7 application suite、`py_compile`、`python scripts/check_no_hardware_calls.py`、`git diff --check`；缺工具必须 `SKIP_WITH_REASON` 或 FAIL，不能伪装 PASS。
4. 对真实 r1/r2/r3 历史 epoch 运行解析验证并执行 tamper 回归；保持 r3 coverage 为 false/zero。
5. 在确认冻结完整后，精确移除 H1b generated 重跑输出，保留 r3 evidence 和本交接文件。
6. 创建准确的修复提交 H1c；提交信息不能声称 P7/hardware complete。
7. 仅在 H1c 工作树干净后，运行一次新的完整 P7 offline gate，记录 source commit 和 checkpoint SHA；hardware 状态仍为 `PENDING_HW`。
8. 基于新 checkpoint 生成新的 r4 66-stage plan 并完成全部 dry validation；不得 resume r3。
9. 在任何硬件前重新确认 shutdown、安全 authorization、bitstream/ELF/profile/XDC hashes、board/part/device/IDCODE、进程 containment、预算和 no-Ethernet/no-motion 边界。
10. 只有所有低层 gate PASS 后，才可通过既定 safe wrapper、scoped `RF_COMM_HW_AUTH` 执行 r4 一次；失败就停止、更换 run ID、独立 shutdown 恢复并冻结证据，永不 resume 失败 run。
11. 只有分级硬件 stage 全部 PASS 后才进入唯一一次 1800 秒 stationary run。不要预跑、重复或补跑第二次 final stationary acceptance。
12. 最后验证 shutdown-after、evidence consistency、状态声明和 diff，生成准确 summaries，再按真实结果提交。

## 10. 当前状态声明

截至本快照，只能准确声明：

```text
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PARTIAL
SOURCE_COMMIT: 81b0f2ea68be5399c8dcdf734ac99f49fa49e3bd
NO_ETHERNET_USED: true
NO_HARDWARE_MOVEMENT: true
AVAILABLE_LANES: 2
MAX_LANE_MASK_USED: 0x3
PS_PL_PHY_PL_PS_APPLICATION_PASS: false
STATIONARY_30MIN: NOT_RUN
HARDWARE_ACCEPTANCE: PENDING_HW
R3_RESULT: FAIL_PRE_CANDIDATE_SHUTDOWN_TCL_PARSE
R3_RESUME_ALLOWED: false
LATEST_INDEPENDENT_RECOVERY_SHUTDOWN: PASS
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING
```

`MAX_LANE_MASK_USED: 0x3` 仅描述 P7 允许/既有测试范围，不表示 r3 已执行 candidate traffic；r3 没有启动 candidate、TX、PS 或 stationary workload。

## 11. 新窗口的首要原则

- 先证据、后结论；先低风险 gate、后硬件；先 shutdown provenance、后任何 candidate program。
- 当前最紧迫的是完成并验证源码/历史汇总修复，而不是立即运行硬件。
- 不要把 r3 的 preflight identity/containment PASS 扩大为 stage、lane、PS、application 或 stationary PASS。
- 不要把独立 P4 recovery shutdown PASS 伪装为 r3 wrapper shutdown-before/after PASS。
- 不要覆盖失败 evidence；不要修饰旧 raw logs；通过独立历史解析说明旧 schema 与旧缺陷。
- 若观察与本文件不同，以可复现的当前证据为准，并在新 evidence 中解释差异。

## 12. 2026-07-11 r4 增量交接（本节覆盖前文过时的 HEAD/run-id 描述）

- H1c 已提交：`dfcd26a1d343e81761c3bd591b47ba05c5a426f9`。
- offline gate 超时修复已提交：`8d827258c9ec89689e8debdaddf422ee30f8df18`。
- 在干净的 `8d827258...` source 上生成的 r4 offline checkpoint 为 PASS；SHA256
  `6f28d380cfdfe41f979d70a87db578b68ec3f604ceebfd362b9bd2c2864a8df3`，硬件状态仍为
  `HARDWARE_ACCEPTANCE: PENDING_HW`。
- r4 plan SHA256 为 `bea97a123cd089f8d43f5df211e96e0505113147774338fa10588b93c5b878bc`；
  66 个授权和 66 个 dry validation 均通过且未触发硬件。
- r4 run ID 为 `p7_20260711_stationary_app_r4`。它只启动一次，在 stage index 0 / `p7_safe_idle`
  以 `FAIL_STAGE` 停止；completed stage count 为 0。r4 永远不得 resume；下一次硬件 run ID 必须是 r5。
- r4 的 candidate bitstream、shutdown-before 和 shutdown-after 均曾被编程；safe-idle 状态读取均为 0；
  第一个事务 `0x100` 在真正 AXI 写入前被 Tcl allowlist 的十六进制字符串/十进制数值比较缺陷拒绝。
  未启动 PS ELF，未驱动 TXd，未启用接收，未使用 UART/Ethernet，未移动硬件，未启动 stationary run。
- r4 失败后第一次独立恢复因参数/授权不足而 `AUTHORIZATION_MISSING` 且
  `NO_HARDWARE_ACTIONS_EXECUTED=1`；第二次独立恢复记录 raw rc125、
  `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0` 和
  `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。恢复 PASS 不得记为 r4 stage PASS。
- r4 原始 ledger/log、两个恢复目录和 7 项 frozen input manifest 位于：
  `evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r4/`。
- allowlist 修复把固定 offset 改为 Tcl 数值，并增加真实 r1/r2/r3/r4 历史正向验证及 r4 tamper
  fail-closed 回归。提交前非硬件结果：JTAG suite 33/33、focused wrapper/safety suites 89/89、
  application/backend suites 36/36、summarizer suite 13/13；`py_compile` 与
  `check_no_hardware_calls.py` 通过。
- 后续只能先准确提交 r4 修复/失败证据，再在新的干净 source commit 上生成一次新 offline checkpoint，
  生成 r5 plan 并通过全部 dry validation；之后才允许使用既定 wrapper/scoped authorization 启动 r5。
- 最终 1800 秒 stationary run 仍为 `NOT_RUN`，其正式执行次数仍为 0。

## 13. 2026-07-11 r5 增量交接（本节覆盖第 12 节的 next-run 描述）

- r4 allowlist 修复和 immutable r4 evidence 已提交：
  `63d08f78dabaa2dcd0369dc2c89f6006b93fa04f`。
- 在干净的 `63d08f78...` source 上新生成的 offline checkpoint 为 PASS；SHA256
  `5e14ab0f7dae66481045a0bf738ac1c2d9ed1dd7414cb10b9ad97ebf573bf567`；
  `HARDWARE_ACCEPTANCE` 仍为 `PENDING_HW`。
- r5 计划 SHA256 为 `b90330e38ea641b283510bb02abfabf517fe77e56ca184105f98a6faa2c55fa3`；
  66 个授权、66 个 child dry validation 和 executor dry validation 均通过。
- r5 run ID 为 `p7_20260711_stationary_app_r5`。它只启动一次：stage 1 / `p7_safe_idle`
  PASS，stage 2 / `p7_p6_frame_regression_m1` 为 `FAIL_STAGE`，随后立即停止。completed stage count
  为 1；r5 永远不得 resume；下一次硬件 run ID 必须是 r6。
- r5 stage 2 的 inner candidate transaction、20 个 fragment、lane0 frame/CRC/ACK、shutdown-before 和
  shutdown-after 均完成；strict backend parser 随后以
  `RAW_PULSE_COUNTER: fragment 1 RAW_TX_PULSES did not increase` 拒绝整个 stage。
- 根因是 evidence contract 错配：真实 `tfdu_lane_phy.sv` 在每个 fragment 前的
  `P6_CTRL_CLEAR_STICKY` 上把 raw TX/RX pulse counters 清零；旧 parser 却把它们当作跨 fragment
  cumulative counter 并要求 delta 增长。修复后 raw pulse counters 按每个 fragment 的 clear-scoped
  非零 observation 验证，其他累计 counters 仍使用严格 delta。
- r5 失败后的独立恢复目录为
  `recovery_shutdown_after_failed_stage2_20260711T043700Z`，记录 raw rc125、
  `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0` 和
  `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。恢复 PASS 不得写成 stage 2 PASS。
- r5 原始 ledger/log、恢复和 9 项 frozen inputs 位于：
  `evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r5/`。
  frozen sources 同时绑定旧 backend Python、Tcl 和 lane-PHY RTL Git blobs，以机器证明旧 parser/RTL
  contract mismatch。
- 修复后的 parser 已对真实 r5 raw log 严格重解析 PASS；这只是 bug-fix 回归，不改变 immutable r5
  wrapper 的 FAIL 状态，也不贡献 active-checkpoint coverage。
- 提交前非硬件结果：focused wrapper/safety suites 89/89、application/backend suites 37/37、
  summarizer suite 13/13、真实 r1-r5 历史正向验证与 r5 tamper fail-closed 均 PASS。
- 后续只能先提交本修复和 r5 失败证据，再在新干净 source commit 上生成一次新 offline checkpoint、
  r6 plan 和全部 dry validation；之后才允许启动 r6。
- 最终 1800 秒 stationary run 仍为 `NOT_RUN`，正式执行次数仍为 0。

## 14. 2026-07-11 r6 增量交接（本节覆盖第 13 节的 next-run 描述）

- r5 raw-pulse 修复与 immutable r5 evidence 已提交：
  `c64baa0a5ca57e35249e6ec49869095c8da388ae`。
- 首次在该提交上运行的 clean-source offline gate 暴露历史 r5 safe-idle 仍错误要求等于当前 HEAD；
  修复历史 source 必须为当前 HEAD 的祖先且保持活动证据 HEAD 严格绑定后，提交为
  `36a67aef2e39c7ca52ec2765d5eebb0363c44bdb`。
- 在干净的 `36a67aef...` source 上唯一新生成的 offline checkpoint 为 PASS；SHA256
  `f1e770a00435ead1126f62986772d9912c707e0e86ef2aa3409a313159a5a412`，
  `NO_HARDWARE_ACTIONS_EXECUTED=true`，`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r6 run ID 为 `p7_20260711_stationary_app_r6`；plan SHA256 为
  `9ce58238a1fa8264b56d5bf3cdd13af1b48ff70e5c4a90f73a44d2cf044c12cd`。
  66 个 authorization、66 个 child dry validation 和 executor dry validation 全部 PASS，
  且 stationary 是唯一的第 66 项；生成和 dry 阶段未启动 Vivado/XSDB/硬件。
- r6 只启动一次且永远不得 resume。stage 1--27 均在 outer ledger 中终态 PASS；stage 28 /
  `p7_fragment_boundary_216_rep3` 以 `FAIL_SHUTDOWN_AFTER` 停止。stage 29--66、PS ELF 和
  stationary 均未启动；最终 1800 秒 stationary 正式尝试次数仍为 0。
- r6 stage 28 的 candidate transaction、frame/CRC/ACK 和 in-band STOP|SHUTDOWN 均 PASS；
  shutdown-after 的 fresh result 也包含唯一的 `P7_TCL_PROGRAMMING_ATTEMPTED=1`、
  `TFDU_SHUTDOWN_PROGRAMMED=<canonical shutdown bitstream>` 和 `P7_SHUTDOWN_RESULT=PASS`。
  但 Vivado helper forest 在约 20 秒 idle 边界发生父 PID 查询退出竞态；wrapper 在仍未取得
  terminal-empty Job proof 时执行 forced cleanup，故 return code 125、process_tree_reaped=false，
  并正确拒绝整个 stage。不得把 shutdown marker 或 recovery PASS 写成 stage 28 PASS。
- r6 独立恢复目录：
  `evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r6/recovery_shutdown_after_failed_stage28_20260711T063732Z/`。
  其中记录 `SHUTDOWN_RAW_EXIT=125`、`TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、
  `SHUTDOWN_EXIT=0` 和 `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。恢复后临时
  `rdi_xsdb/cs_server` 均自然退出，只保留未触碰的 legacy `hw_server`。
- r6 冻结目录：
  `evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r6/historical_preflight_inputs/`。
  其 10-file manifest SHA256 为
  `bba8f98ce66d115120ae11d97ceaf8b7c2860685748810ac4eeace4f319efa07`，并明确
  `result=FAIL_SHUTDOWN_AFTER`、`coverage_claimed=false`；同时冻结 checkpoint、plan、stage
  authorization/transactions、generation manifest、P4 authorization、历史 Tcl、JTAG wrapper、
  backend 和 lane-PHY RTL Git blobs。
- 当前未提交修复仅允许在同一固定 30 秒 deadline 内，在身份查询重试耗尽后增加一次不超过
  0.1 秒的 Job terminal-empty proof；只有 Job 直接证明空且采样 gap 仍不超过 250 ms 才可
  清除 transient query error 并 PASS。任何仍非空 Job、拓扑增长/变异、hash/path 不匹配或
  deadline 到期仍继续 forced cleanup 并 FAIL。完整 JTAG wrapper suite 34/34、summarizer
  suite 13/13（含真实 r1--r6 与 r6 tamper）已 PASS。
- 下一次硬件 run ID 必须是 r7。必须先准确提交本修复和 r6 evidence，再在新干净 source 上
  只生成一次新 offline checkpoint，生成 r7 66-stage plan，并通过所有 dry validation。
  r7 也必须从 stage 1 全新开始；r6 的 27-stage PASS prefix 只作为已验证历史记录，贡献 0
  active-checkpoint coverage。

## 15. 2026-07-11 r7 增量交接（本节覆盖第 14 节的 next-run 描述）

- r6 helper-exit race 修复与 immutable r6 evidence 已提交为
  `f3333ec561d8981793573ef6a934c1948db8bce5`。
- 在干净的 `f3333ec5...` source 上唯一一次新生成的 offline checkpoint 为 PASS；SHA256
  `7d2622a3fb6afae23eaae9c710dc9f8da9881225debf483e60a4a1cc1a6699dd`，13/13 checks
  为 true，`NO_HARDWARE_ACTIONS_EXECUTED=true`，`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r7 run ID 为 `p7_20260711_stationary_app_r7`；plan SHA256 为
  `1a5df0cf5f7461f27647d0604f26d0b3de89d6e4fb75c6719869e531c6f9034e`。66 个
  authorization、66 个 child dry validation、生成器 executor dry 和独立 executor dry 均 PASS；唯一
  stationary 仍是第 66 项，生成和 dry 阶段未启动 Vivado/XSDB/硬件。
- r7 只启动一次并永远不得 resume。stage 1 `p7_safe_idle` 和 stage 2
  `p7_p6_frame_regression_m1` 完整 PASS；stage 3 `p7_p6_frame_regression_m2` 以
  `FAIL_SHUTDOWN_AFTER` 停止。完成前缀为 2/66；stage 4--66、PS ELF 和 stationary 均未启动，正式
  1800 秒 stationary 尝试次数仍为 0。
- r7 stage 3 candidate transaction 自身 rc=0、process tree reaped=true，lane1 frame/CRC/ACK 原始结果
  为 PASS；但 shutdown-after 的旧固定 30 秒上限在 Vivado 仅写出 target identity 后到期，return code
  124、`timed_out=true`，在 shutdown bitstream programming attempt 之前被 wrapper 强制回收。因此整个
  stage 正确 FAIL；candidate PASS 不得提升 stage 3，也不得贡献 active-checkpoint coverage。
- r7 第一次独立恢复因输入 profile SHA 拼写错误在授权阶段安全拒绝，记录
  `AUTHORIZATION_MISSING` 与 `NO_HARDWARE_ACTIONS_EXECUTED=1`。随后在新的 evidence 目录使用机器读取的
  正确 SHA 重试，记录 `SHUTDOWN_RAW_EXIT=125`、`TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、
  `SHUTDOWN_EXIT=0` 和 `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。恢复 PASS 不得写成 stage 3 PASS。
- r7 原始 ledger/log、两次恢复与 frozen inputs 位于
  `evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r7/`。frozen 10-file manifest SHA256
  为 `05683b694f95ee04a873c6b8c99ee0d7342ffc645e4c697407a8b4fb5be3f906`，明确
  `result=FAIL_SHUTDOWN_AFTER`、`coverage_claimed=false`。
- 当前修复把所有 shutdown barrier 预算从 30 秒提高到 60 秒。普通 JTAG stage 的 global ceiling 从
  900 秒提高到 960 秒，使最坏情况预算 `60 + 2*60 + 550 + 120 + 65 = 915` 秒后仍保留 45 秒余量；
  safe-idle 为 425/600 秒。PS stationary 的 active service window 仍严格为 1800 秒，未提前执行或重复。
- summarizer 已新增 r7 精确历史失败分类、2-stage 历史 PASS prefix 零覆盖验证、30 秒旧 plan 绑定、两次
  recovery 顺序/分类和 r7 tamper fail-closed 测试。下一次硬件 run ID 必须为 r8；只有本修复和 r7
  evidence 准确提交、在新干净 source 上生成唯一一次新 offline checkpoint、生成 r8 plan 且全部 dry
  validation PASS 后，才允许从 stage 1 全新启动 r8。

## 16. 2026-07-11 r8 增量交接（本节覆盖第 15 节的 next-run 描述）

- r7 shutdown-budget 修复与 immutable r7 evidence 已提交为
  `11961c92d22713032d92095d87e6c4362b3254dc`。
- 在干净的 `11961c92...` source 上唯一一次新生成的 offline checkpoint 为 PASS；SHA256
  `7146e8000b2e4763f95d07e9ca7671646c5536b89077a615cb645538d6d132a1`，13/13 checks
  为 true，`NO_HARDWARE_ACTIONS_EXECUTED=true`，`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r8 run ID 为 `p7_20260711_stationary_app_r8`；plan SHA256 为
  `58e07164f1aa38816b9b360bb28a838d6afd986a292863e3152f6daab914522d`。66 个
  authorization、66 个 child dry validation、生成器 executor dry 与独立 executor dry 全部 PASS。
- r8 只启动一次并永远不得 resume。stage 1--54 在 outer ledger 中终态 PASS；stage 55
  `p7_large_jtag_64k_rr_prbs15` 以 `FAIL_STAGE` 停止，completed stage count 为 54。stage 56--66、
  PS ELF 与唯一 1800 秒 stationary 均未启动；正式 stationary 尝试次数仍为 0。
- r8 stage 55 candidate transaction rc=0、process tree reaped=true，305 个 fragment 的 payload/CRC/ACK
  与 shutdown-before/after 均完成。strict backend parser 随后以
  `COUNTER_DELTA: fragment 200 FRAME_GOOD delta=2 expected=1` 拒绝整个 stage。
- 原始 fragment 199/200/201 证明 fragment 200 发生一次合法 ARQ retry：`RETRY_COUNT` 当前值为 1，
  `TX_COUNT`、`ACK_SEEN` 和目标 lane `RX_GOOD` 各增加 1，而累计 `FRAME_GOOD`、`ACK_SENT` 各增加 2；
  `RETRY_EXHAUSTED=0`、CRC/error counters 为 0。RTL 在每次 `clear_pulse` 把 `retry_count` 清零，因此旧
  parser 同时错把 RETRY_COUNT 当累计计数，并错误要求 FRAME_GOOD/ACK_SENT 固定增量 1。
- r8 失败后的独立恢复目录为
  `evidence/hardware/p7/authorized_sequence/p7_20260711_stationary_app_r8/recovery_shutdown_after_failed_stage55_20260711T104455Z/`，
  记录 `SHUTDOWN_RAW_EXIT=125`、`TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0` 与
  `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。恢复 PASS 不得写成 stage 55 PASS。
- r8 frozen 10-file manifest SHA256 为
  `df2b3e3854d6eb948c0939cb237f895bee40d77e18ddb40a6818689047021f9d`，明确
  `result=FAIL_STAGE`、`coverage_claimed=false`。
- 当前 parser 修复把 `RETRY_COUNT` 作为 clear-scoped per-fragment observation，严格限制在 RTL
  `MAX_RETRY=3` 的 0..3 范围；累计 `FRAME_GOOD` 与 `ACK_SENT` 的期望增量改为
  `1 + retry_count`，而 `TX_COUNT`、`ACK_SEEN`、目标 lane `RX_GOOD` 仍严格要求增量 1。
- 下一次硬件 run ID 必须为 r9。必须先准确提交 parser/summarizer 修复和 r8 evidence，再在新干净
  source 上只生成一次新 offline checkpoint、生成 r9 66-stage plan 并通过全部 dry validation；r9 必须
  从 stage 1 全新开始。r8 的 54-stage PASS prefix 仅为祖先 source 历史记录，贡献 0 active coverage。

## 17. 2026-07-11 r9 增量交接（本节覆盖第 16 节的 next-run 描述）

- r8 ARQ retry counter parser/summarizer 修复与 immutable r8 evidence 已提交为
  `91b8fbd45f339dfb143bac8374000486bd4a37a0`。
- 在干净的 `91b8fbd4...` source 上唯一一次新生成的 offline checkpoint 为 PASS；SHA256
  `a243fb6f5786ded7a04e40ce212dc963a1079829af3b144e62b6fa1dae79e315`，13/13 checks
  为 true，`NO_HARDWARE_ACTIONS_EXECUTED=true`，`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r9 run ID 为 `p7_20260711_stationary_app_r9`；plan SHA256 为
  `f3dd86f1e18cfb2998d4ffbdd9836d601732411dd34b1fbe38ee6ff1cf1c744c`。66 个
  authorization、66 个 child dry validation、生成器 executor dry 与独立 executor dry 全部 PASS；唯一
  stationary 严格为第 66 项，且生成/dry 未启动硬件。
- r9 只启动一次并永远不得 resume。stage 1 `p7_safe_idle` 与 stage 2
  `p7_p6_frame_regression_m1` 完整 PASS。启动后发现承载 executor 的交互命令被配置了 7200 秒外层工具
  deadline，而 r8 机器 ledger 已证明仅前 55 stage 就耗时 182.68 分钟；继续会导致外层工具在 safe
  wrapper 内部被强制终止，不能保证 shutdown-on-exit。为避免该风险，使用 plan 已绑定的
  `.hardware_authorization/ABORT_NOW.txt` 请求动态 abort。
- abort 在 stage 3 `p7_p6_frame_regression_m2` 的 candidate 启动后被检测。candidate rc=130、
  `abort_seen=true`、forced containment cleanup 与 process reap 均有记录；candidate 尚未写出 programming/
  transaction PASS markers，故 stage 3 正确为 `FAIL_STAGE`。shutdown-before 和 shutdown-after 均完整 PASS，
  outer ledger 以 completed=2、failed_stage_index=2 停止；stage 4--66、PS ELF 与 stationary 均未启动，
  正式 1800 秒 stationary 尝试次数仍为 0。stage 1--2 前缀只属失败的祖先 epoch，贡献 0 active coverage。
- 第一次独立恢复 launcher 因本机 PowerShell execution policy 在脚本加载前拒绝，机器记录明确
  `script_loaded=false`、`vivado_started=false`、`hardware_actions_executed=false`，不得当作 shutdown。
  随后通过 `powershell.exe -ExecutionPolicy Bypass` 启动既定 P4 shutdown wrapper；有效恢复目录为
  `recovery_shutdown_after_failed_stage3_20260711T112013Z/`，记录正确 profile SHA、raw rc125、唯一
  `TFDU_SHUTDOWN_PROGRAMMED`、`SHUTDOWN_EXIT=0` 和 `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。
  临时 helper 随后自然退出，只保留未触碰的外部 legacy `hw_server` PID 45220。
- r9 frozen 10-file manifest SHA256 为
  `eec891c13048a1f0afb0ca922b15074d22aabff77ae56b93fd51564edb80b661`，明确
  `result=FAIL_STAGE`、`coverage_claimed=false`。summarizer 必须将该 epoch 分类为外层 deadline 不足后主动
  fail-closed abort，精确验证 abort/outer/inner/recovery 证据并对 tamper fail closed。
- 下一次硬件 run ID 必须为 r10。必须先准确提交 r9 summarizer/tests/handoff 与全部 r9 evidence，再在新干净
  source 上只生成一次新 offline checkpoint、生成 r10 66-stage plan 并通过全部 dry validation。r10 必须从
  stage 1 全新开始；承载 executor 的工具命令上限必须覆盖完整风险序列（至少 24 小时），不得依赖 resume。

## 18. 2026-07-11 diagnostic suffix 授权（本节覆盖第 17 节的 next-run 描述）

- 用户已明确授权新的零覆盖诊断策略，以避免每个新问题都重复完整低风险前缀；这不是失败 run resume 授权，
  也不是提前执行 stationary 的授权。r9 仍为 immutable FAIL，永远不得 resume。
- 在 r9 历史验证/evidence 准确提交、diagnostic plan 支持准确提交且新干净 offline checkpoint PASS 后，下一
  hardware run 必须使用带诊断后缀的新 run ID，例如
  `p7_20260711_stationary_app_r10_diag_suffix55`，不得使用会被误解为正式验收的名称。
- diagnostic plan 严格只包含原 full plan 的 stages 1--4（safe-idle 与三个 P6 frame regression）以及
  stages 55--65，共 15 项；不得包含原 stage 66 `p7_ps_stationary`，不得创建 stationary launch intent。
- plan、ledger、summaries 与 frozen manifest 必须明确 `DIAGNOSTIC_ONLY`、`coverage_claimed=false`、
  `HARDWARE_ACCEPTANCE=PENDING_HW`。任何历史 prefix/suffix PASS 都贡献 0 final acceptance coverage。
- diagnostic run 仍需全套新 run ID、scoped authorization、immutable path/hash、offline/dry gates、
  shutdown-before/after。任一失败立即停止、保存原始 evidence、执行独立 shutdown recovery、冻结 epoch，
  再换新 diagnostic run ID；不得 resume。
- suffix 问题全部修复/提交且非硬件 gates PASS 后，才生成新的正式 run ID，从完整 stages 1--66 重新执行。
  只有该正式全量 run 可以启动唯一一次 stage 66 的 1800 秒 stationary acceptance。

## 19. 2026-07-11 r10 diagnostic suffix 增量交接（本节覆盖第 18 节的 next-run 描述）

- r10 diagnostic source 为 `6bd9980eb7cc82093e47099dcd7fe38ebbc5f3d7`；clean offline checkpoint SHA256 为
  `4304f94d4bff6e449955c487257064477b4bdbe58d150cdb94d2aa3b3134636c`；15-stage diagnostic plan SHA256 为
  `5cefcc79a8c3d4114688086631c1ed1974355f4d74a26db28715ab4814fccb8d`。
- run ID `p7_20260711_stationary_app_r10_diag_suffix55` 只启动一次且永远不得 resume。full ordinals
  1--4 与 55--57 完整 PASS；full ordinal 58 / `p7_large_jtag_1m_l0_random` 在 candidate 的 1400 秒硬截止
  到期后 rc=124、`timed_out=true`、forced containment/reap，并以 `FAIL_STAGE` 停止。outer ledger 为
  completed=7、attempts=8、failed_stage_index=7、full_stage_ordinal=58。
- stage 58 原始日志只到 `P7F00944_RXW017=F72C793C`，没有 `P7F00945_*`、`P7_TRANSACTION_COUNT`、
  `P7_JTAG_AXI_TRANSACTIONS=PASS` 或 `P7_JTAG_STAGE_RESULT=PASS`。因此它是 immutable timeout FAIL，
  不是部分 PASS；r10 的所有 prefix/suffix 仍贡献零 acceptance coverage。
- stage wrapper 的 shutdown-before 与 shutdown-after 均 PASS。独立 recovery 位于
  `recovery_shutdown_after_failed_stage058_20260711T125648Z/`，记录唯一 TFDU shutdown marker、
  `SHUTDOWN_EXIT=0` 和 `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。该 recovery PASS 不改变 stage 58 FAIL。
- r10 frozen 10-file input manifest SHA256 为
  `d1897482ed7ab9e77e2a293f6d2a2d0a133cc2352ae3d1b48190a3650db4af29`，并明确
  `full_stage_ordinal=58`、`coverage_claimed=false`。r10 evidence、历史/tamper validator 与修复已提交为
  `f508e864fbf4c9103684637faa864e5f8d4c6494`。
- 根因不是 optical/CRC/ACK failure，而是旧 Tcl 对每个 payload/readback word 各启动一个 JTAG/AXI transaction；
  1 MiB DSL 有 1,073,038 个 operations，在 1400 秒只完成到 fragment 944。修复只把自然连续的 TX payload
  与 TX/RX readback words 合并为最多 64 words 的授权 `INCR` burst；control/status/poll 仍逐项执行，原 DSL
  operation count、验证顺序、每 word result key 和 strict backend evidence 不变。对 frozen stage 58 transaction
  的 dry validation 把实际 JTAG transaction launch 数从 1,073,038 降为 180,508，最大 burst 62 words。
- 完整非硬件回归结果：top-level discovery 106/106 PASS，`tests/p7` 39/39 PASS，合计 145/145；
  `py_compile`、`check_no_hardware_calls.py` 与 `git diff --check` PASS。这些结果仍只属于非硬件验证。
- 最终 1800 秒 stationary 正式尝试次数仍为 0；r10 明确为 `DIAGNOSTIC_ONLY`、
  `coverage_claimed=false`、`HARDWARE_ACCEPTANCE=PENDING_HW`，未创建任何 stationary stage directory/marker。
- 下一次只允许先在本节提交后的 clean source 上生成一次新 offline checkpoint，再生成新的
  `p7_20260711_stationary_app_r11_diag_suffix55` 计划并通过全部 dry validation。r11 仍是零覆盖 diagnostic，
  只运行 full ordinals 1--4 与 55--65，绝不运行 stage 66。任何失败仍需新 run ID、独立 shutdown recovery，
  不得 resume。只有 suffix 全部 PASS、所有修复提交并重新生成 clean checkpoint 后，才可另建正式 full run。

## 20. 2026-07-11 r11 diagnostic suffix 增量交接（本节覆盖第 19 节的 next-run 与 INCR-burst 结论）

- 在 `9cdfe6c22f1efc2e51f44803d4aeae1da40a6342` 上运行的 canonical full-project offline gate 为 PASS，
  summary SHA256 为 `3ab076c8717836fff97a241f5dcfd2f80d1947b454ec98a925618f41f023e63b`，
  `NO_HARDWARE=true`、`HARDWARE_ACCEPTANCE=PENDING_HW`。它重生成了 52 个 tracked generic reports，导致紧随其后的
  第一次 P7 gate 正确地只在 `P7_CLEAN_SOURCE_CHECKPOINT` fail-closed；该失败 summary SHA256 为
  `02686d70ddc99e608dea53c02d5dc4bfe972f4d657ffb2fe0187f7d2ec73b1f9`，其余 12 项 PASS，未执行硬件。
  通用 PASS 输出与该失败 checkpoint 已准确提交为 `b9bb0b93b711bb5eefcfc4aebb6bc25b39c8c31d`。
- 在干净的 `b9bb0b93...` 上重新生成的 P7 checkpoint 13/13 PASS，SHA256 为
  `118c8aab027a22fcea5188340f2741594ff08ee8d7a00340ba0e4edbf6ca95f8`，
  `NO_HARDWARE_ACTIONS_EXECUTED=true`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r11 run ID 为 `p7_20260711_stationary_app_r11_diag_suffix55`；15-stage plan SHA256 为
  `c04e2796b5431958234b0ae986dcc876e873e455382e8c533cbeac160ead7041`。生成器、15 个 authorization、
  15 个 child dry validation、生成器 executor dry 与独立 executor dry 均 PASS；精确 ordinals 为
  `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`，无 stationary stage/PS stationary mode，
  `DIAGNOSTIC_ONLY`、`coverage_claimed=false`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- 第一次 outer execution 请求因临时环境授权值错误，在 ledger/wrapper/hardware 之前返回
  `P7_AUTHORIZED_HARDWARE_SEQUENCE=BLOCKED`、`hardware_actions_executed=false`；它没有启动 r11 epoch 或消费 run ID。
  随后使用代码唯一要求的 scoped 值启动一次真实 r11，且没有 `--resume`。
- r11 stage 1 / `p7_safe_idle` 终态 PASS；full ordinal 2 / `p7_p6_frame_regression_m1` 终态
  `FAIL_STAGE`，outer ledger 为 attempts=2、completed=1、failed_stage_index=1。stage 3 以后均未启动，
  stationary 正式尝试次数仍为 0；r11 永远不得 resume，stage 1 历史 PASS 贡献零 acceptance coverage。
- stage 2 的 candidate 已编程，但在任何 `P7F*` fragment traffic 前以 rc=41 失败。raw error 为：
  `Protocol 'AXI4-Lite' does not support bursts. Only value '1' is valid for option 'LEN'`。
  因此第 19 节“用多 word INCR burst 优化”的假设已被真实硬件否证；这不是 optical/CRC/ACK failure。
  stage 2 的 shutdown-before/after 均 PASS，但不改变 stage FAIL。
- 独立 recovery 位于
  `recovery_shutdown_after_failed_stage002_20260711T144611Z/`，记录 `SHUTDOWN_RAW_EXIT=125`、
  `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0`、`PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`；
  临时 helper 已自然退出，外部 legacy `hw_server` PID 45220 未被触碰。
- r11 frozen 10-file manifest SHA256 为
  `0d97cb0e67fe3bf3ebef6a2afba3cd03ec2e5babfb70aa9f4385bd70fe5c76db`，明确
  `full_stage_ordinal=2`、`result=FAIL_STAGE`、`coverage_claimed=false`。
- 当前修复保持所有 live AXI transaction 为 `LEN=1` 且完全删除 `-burst`；只把最多 16 个有序单字
  AXI4-Lite transaction（Vivado 2023.1 文档规定的单方向 queue 上限）交给一次 `run_hw_axi -queue`。DSL operation、实际单字 AXI transfer 数、顺序、
  per-word evidence 与 strict backend contract 不变。dry metrics 现在分别报告最小单字 AXI4-Lite transaction 数、
  最小 `run_hw_axi` call 数和 batch 结构，不再把 batch 冒充 burst 或减少后的 AXI transaction 数。
- 新 validator 对 frozen r11 stage 2 报告 4,269 个单字 AXI4-Lite transactions、最少 933 次
  `run_hw_axi`、231 个 multi-transaction batches、最大 batch 16；对 frozen stage 58 报告 1,073,038 个
  单字 transactions、最少 224,401 次 `run_hw_axi`、58,527 个 multi-transaction batches、最大 batch 16。
  Vivado 2023.1 本机 `help run_hw_axi` 明确证明该命令接受多个 transaction objects，且 `-queue` 单方向最多 16 个。
- 最终非硬件回归：summarizer 13/13、top-level discovery 106/106、`tests/p7` 39/39，合计 145/145 PASS；
  `py_compile`、`check_no_hardware_calls.py`、`git diff --check` PASS；Vivado Tcl 真实 parser 在无参数时于任何
  hardware-manager 动作前按预期拒绝，证明修改后的 Tcl 可被 Vivado 2023.1 加载。这些结果不提升硬件 acceptance。
- 下一次硬件 run ID 必须是新的 `p7_20260711_stationary_app_r12_diag_suffix55`。必须先准确提交 r11 evidence、
  summarizer/tamper tests 与本修复，再在新干净 source 上生成新 P7 checkpoint、r12 plan 并通过全部 dry validation。
  r12 仍只允许 ordinals 1--4 与 55--65，不得运行 stage 66；任何失败仍需新 ID、独立 recovery、永不 resume。

## 21. 2026-07-11 r12 diagnostic suffix 增量交接（本节覆盖第 20 节的 next-run 与 queue-limit 结论）

- r11 evidence、queued-single fix 与历史验证已提交为
  `999cbc327009459fcd768380fe25918c5213a763`。在该 clean source 上生成的 P7 checkpoint 13/13 PASS，
  SHA256 为 `e5865683587f203ddc292fd998c5bc04f84a1de931bbc0c05cc7260382b42452`；
  `NO_HARDWARE_ACTIONS_EXECUTED=true`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r12 run ID 为 `p7_20260711_stationary_app_r12_diag_suffix55`，15-stage diagnostic plan SHA256 为
  `afbd14093989a62d3bc149abc3d840647e352ccd87e5c221ee689ee849d2ef0d`。生成器、15 个 authorization、
  15 个 child dry validation 与 executor dry validation 均 PASS；full ordinals 精确为
  `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`，无 stage 66/stationary。
- r12 只启动一次且永远不得 resume。stage 1 / `p7_safe_idle` PASS；full ordinal 2 /
  `p7_p6_frame_regression_m1` 以 `FAIL_STAGE` 停止；outer ledger 为 attempts=2、completed=1、
  failed_stage_index=1。后续所有 stage 和 stationary 均未启动；整次仍为 `DIAGNOSTIC_ONLY`、
  `coverage_claimed=false`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- stage 2 candidate 已编程，但在任何 `P7F*` fragment traffic 前 rc=41。raw result 只记录通用
  `ERROR: [Common 17-39] 'run_hw_axi' failed due to earlier errors.`；stderr 的精确根因是
  `ERROR: [Xicom 50-38] xicom:  Queueing Transaction Failed. As total write transactions count 16 is greater than maximum allowed value 1 of targetted JTAG_AXI IP.`。
  shutdown-before/after 均 PASS，但不能提升失败 stage。
- 独立 recovery 位于 `recovery_shutdown_after_failed_stage002_20260711T152922Z/`，记录 raw rc125、唯一 TFDU
  shutdown marker、`SHUTDOWN_EXIT=0` 与 `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。recovery PASS 不改变 r12 FAIL。
  frozen 10-file manifest SHA256 为
  `d3c9f93a43d1c45e63507fd24c7933f1d9f9360a4fa7d0a9628a32cb9321c9b9`。
- 根因是 content-addressed P6 JTAG candidate 的 JTAG_AXI IP 仍使用 Vivado 默认
  `CONFIG.RD_TXN_QUEUE_LENGTH=1` / `CONFIG.WR_TXN_QUEUE_LENGTH=1`；工具支持最多 16 个 transaction objects
  不等于目标 IP queue depth 已是 16。旧 build Tcl 没有覆盖这两个参数。
- 本次离线修复把正式 build 与独立 IP inspection 均设为 RD/WR queue depth 16。本机 Vivado 2023.1 离线 IP
  generation 已证明两个属性均接受并回读为 16。随后唯一一次离线全量 synth/place/route/bitstream build PASS，
  timing met、DRC clean；新 immutable bit SHA256 为
  `674cf4a14988bbce15b8025162e7d528aa888c44e188a3a94ef5acd97d01d8d9`，LTX SHA256 仍为
  `76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083`，旧 artifacts 保持不变。
- r12 exact summarizer suite 14/14 PASS（含真实 r1--r12 与 r12 tamper fail-closed）；top-level discovery
  107/107、`tests/p7` 39/39，合计 146/146 PASS。`py_compile`、`check_no_hardware_calls.py` 与
  `git diff --check` PASS。canonical generic offline gate 的唯一进程最终自然完成并写出
  `status=PASS`、`no_hardware=true`、`hardware_acceptance=PENDING_HW`，summary SHA256 为
  `c9499340c17aa9d8c5ec1ce8d252563114bdd9d3af87abc36cfe09efb8de04b2`。调用端在 904 秒先结束等待，
  但原 gate PID 继续同一离线 Vivado matrix 到终态；未启动第二次 gate，也未连接硬件。
- 下一次硬件 run ID 必须是新的 `p7_20260711_stationary_app_r13_diag_suffix55`，绝不得恢复 r12。必须先完成
  r12 exact summarizer/history/tamper 回归、提交全部 r12 evidence 与 queue-depth 修复，再从新 clean source 生成一次
  P7 checkpoint、r13 plan 并通过全部 dry validation。r13 仍只允许 full ordinals 1--4 与 55--65，严禁 stage 66；
  任一失败仍需立即停止、独立 shutdown recovery、冻结证据并更换 run ID。

## 22. 2026-07-11 r13 diagnostic suffix 增量交接（本节覆盖第 21 节的 next-run 描述）

- r12 evidence、queue-depth 修复与新 candidate build 已提交为 `9a83eca66bbc5718e52aaccea0a14e1493fc44a9`；历史
  diagnostic prefix collapse 修复提交为 `d614ed203eca9b615e9fd3782da1e81f01d93fea`。在后者 clean source 上生成的
  P7 checkpoint 13/13 PASS，SHA256 为 `5dca5487a44ddd17396704959ef080171a867579202822e7650d7b9a1627ab72`，
  `NO_HARDWARE_ACTIONS_EXECUTED=true`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r13 run ID 为 `p7_20260711_stationary_app_r13_diag_suffix55`，15-stage plan SHA256 为
  `442f597b75b1d8261c443b5f7611096cfab0a592a8adb5e966c62453ef9824c7`。它只启动一次且永远不得 resume；
  full ordinals 1--4 与 55--57 PASS，full ordinal 58 / `p7_large_jtag_1m_l0_random` 在 candidate 的
  1400 秒上限以 rc=124、`timed_out=true`、forced containment/reap 终止。outer ledger 为 attempts=8、completed=7、
  failed_stage_index=7；stage 59--65 与 stage 66 均未启动，所有 prefix/suffix 贡献零 acceptance coverage。
- stage 58 原始结果只完整到 fragment 1665，fragment 1666 在 `P7F01666_ACK_SEN...` 处中断，没有终端
  `P7_TRANSACTION_COUNT` / transaction PASS / stage PASS marker。因此 r13 是 immutable timeout FAIL，不是部分 PASS。
  shutdown-before/after 均 PASS；独立 recovery 位于 `recovery_shutdown_after_failed_stage058_20260711T181718Z/`，
  记录 raw rc125、唯一 TFDU shutdown marker、`SHUTDOWN_EXIT=0` 与
  `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`，但不改变 stage 58 FAIL。
- r13 frozen 10-file manifest SHA256 为 `8b5352ca562518dc4f2e49872b90819c5318b12b9dbe0aa8d7e97cefc3ad6984`；
  r13 timeout、完整原始 evidence、历史 validator 与 AXI4/AXI4-Lite converter candidate rebuild 已提交为
  `822245b64995788269403793b44be537d46a702f`。后续 checkpoint provenance 修复提交为
  `3b03414f279a8205207c7d67bdc8923a4723b866` 与 `4ac85146409b58d4715e2d9350f993681cdddc5d`。新 candidate bit SHA256 为
  `798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f`，LTX SHA256 为
  `76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083`。

## 23. 2026-07-11 r14 diagnostic suffix 增量交接（本节覆盖第 22 节的 next-run 描述）

- post-gate global ledger allowlist 修复提交为 `bd3f1a41c69173915abbc294dc16b0233dbb244c`。首次 P7 checkpoint 在其余
  12 项 PASS 时仅 `P7_CLEAN_SOURCE_CHECKPOINT` 正确 FAIL；该可复现 cleanliness-failure 输出提交为
  `dac35ce44fa8b2316ff67b2abd6a45ad6a7d6998`。随后只在该 clean source 上重新生成一次 checkpoint：13/13 PASS，
  SHA256 为 `a4783583d1f098b6d8145ea043cd68b702e0e6f61136cf4fdd503145537dbb68`，硬件状态仍为 PENDING。
- r14 run ID 为 `p7_20260711_stationary_app_r14_diag_suffix55`，15-stage plan SHA256 为
  `396b6974bfc117cbc61f6ca0db9c78d948f349b04c7d7d5b430152a22fc1e82d`。一次缺少 outer control 参数的请求在
  ledger/wrapper/hardware 前安全 BLOCKED，未消耗该 ID；随后真实 r14 只启动一次且没有 `--resume`。
- r14 stage 1 / `p7_safe_idle` PASS；full ordinal 2 / `p7_p6_frame_regression_m1` 的 candidate process rc=0、
  Tcl transaction markers PASS、shutdown-before/after PASS，但 strict backend 以
  `BackendValidationError: TX_CRC32: fragment 0 committed CRC differs from manifest` 拒绝。fragment 0 的预期 CRC 为
  `3ED470A1`，观测 `TX_CRC32=RX_CRC32=RX_DIGEST=A155F91B`；TX word 回读与 manifest 一致，但
  `TXW000=50414652`、`RXW000=00414652`。因此 stage 2 正确为 immutable `FAIL_STAGE`，outer ledger SHA256 为
  `c7302e43b37061d549c488707e2662bfdc6c5d119130b05cb0a400c0a09481a7`，attempts=2、completed=1、
  failed_stage_index=1；其余 stages 与 stationary 均未启动。
- 独立 recovery 位于 `recovery_shutdown_after_failed_stage002_20260711T210200Z/`，记录
  `SHUTDOWN_RAW_EXIT=125`、唯一 shutdown marker、`SHUTDOWN_EXIT=0` 与
  `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`；它不提升 r14 stage 2。r14 frozen 10-file manifest SHA256 为
  `429a7c45f0570f3184b84bf4f1ae7e6b04b6b11a1671ad63c02a8f635d3fb540`。
- 当时的首要根因假设是 full AXI4 JTAG master 仍把 P6 `0x100` side-effect control writes 与依赖它们的数据操作放入独立 queued
  transactions；该假设及其 control-order 修复后来由 r15 的精确 20-fragment word-reversal 证据进一步收窄，不能再作为最终根因。修复保持 payload/readback 的 bounded INCR burst 和真正独立的
  queued singles，但把每个 `0x100` control write 作为 dependency barrier：先 flush，再 standalone 执行，且 dry report
  强制 `queued_control_write_transaction_count=0`。r1--r14 exact history/tamper test 与完整 14-test summarizer suite 已 PASS。
- 完整非硬件回归为 top-level 112/112、`tests/p7` 39/39，合计 151/151 PASS；`py_compile`、两项 no-hardware
  static/dry-run scan 与 `git diff --check` PASS。随后只启动一次 canonical `scripts/run_offline_gates.py`，同一进程在
  3334 秒后自然返回 `OFFLINE_GATES_RAN=1 status=PASS`；JSON SHA256 为
  `dcc8b007b4f6916f4ca7c73b43527d134f8c7890e035978375a6ab1bfd18e2aa`，明确
  `no_hardware=true`、`hardware_acceptance=PENDING_HW`。未启动第二个 offline gate，也未连接硬件。
- r14 永远不得 resume。下一硬件 ID 必须为新的 `p7_20260711_stationary_app_r15_diag_suffix55`；必须先准确提交 r14
  evidence、summarizer/tests、control-order 修复与本交接，再从新 clean source 只生成一次 P7 checkpoint、r15 plan 并通过
  全部 dry validation。r15 仍只允许 full ordinals 1--4 与 55--65，严禁 stage 66；最终 1800 秒 stationary 启动次数仍为 0。

## 24. 2026-07-11 r15 diagnostic suffix 增量交接（本节覆盖第 23 节的根因与 next-run 描述）

- r14 immutable evidence、独立 recovery、control-order 修复、r1--r14 历史验证、完整 generic offline gate 与交接已提交为
  `28e7bb8f5266d654aefdbd3fede7b7dae7ab584e`。在该 clean source 上只生成一次新的 P7 checkpoint，13/13 PASS，
  summary SHA256 为 `b3cee8d98e748ec8af42fea56b4e205887d0d9eea8ee4bbf849a607d64f460b7`；
  `NO_HARDWARE_ACTIONS_EXECUTED=true`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r15 run ID 为 `p7_20260711_stationary_app_r15_diag_suffix55`；15-stage diagnostic plan SHA256 为
  `35bbff877b3c5de0b4cdcac9a06adfb4fade9f7f3dcf6b5421c41eb94c0bc2b5`，generation manifest SHA256 为
  `5a072ab06e91e7f00b2f766c64881ae97db96a3d59774061dd2fa1e875c0af94`。generator、15 个 authorization、
  15 个 child dry validation、generator executor dry 与独立 executor dry 均 PASS；精确 ordinals 为
  `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`，无 stage 66/stationary，整次为 `DIAGNOSTIC_ONLY`、
  `coverage_claimed=false`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r15 只启动一次且没有 `--resume`。stage 1 / `p7_safe_idle` PASS；full ordinal 2 /
  `p7_p6_frame_regression_m1` 的 candidate rc=0、transaction/stage markers PASS、shutdown-before/after PASS，但 strict backend 仍以
  `BackendValidationError: TX_CRC32: fragment 0 committed CRC differs from manifest` 拒绝，因此 stage 2 是 immutable
  `FAIL_STAGE`。outer ledger 在退出时 SHA256 为
  `bede8b3173f1ff3f2059c3d2222a1b24e0fe91fd1b5499cf631c948a8f119b49`，attempts=2、completed=1、
  failed_stage_index=1；其余 stages 与 stationary 均未启动。
- r15 dry/runtime metrics 证明第 23 节的 control-order 修复确已生效：`ordered_control_write_run_hw_axi_call_count=63`、
  `queued_control_write_transaction_count=0`，但相同 CRC failure 仍存在。对全部 20 个 fragment 的原始 `TXW*` 机器重算均精确证明：
  每个 raw `TXW*` 都逐项等于 frozen authorization transaction 中同地址的 low-to-high payload word；该自然顺序的 CRC 不等于硬件观测 CRC，
  而把同一组 32-bit words 整体反转后再按 encoded length
  截断，其 CRC 则逐 fragment 精确等于观测 `TX_CRC32`。fragment 0 的自然 CRC 为 `3ED470A1`，反转后及观测值均为
  `A155F91B`。因此第 23 节的 queued-control 解释只是已被 r15 否证的中间假设，最终根因是 Vivado multiword AXI `DATA`
  property 为 MSW-first（右端 word 对应最低 `INCR` address），而旧 Tcl 写入与读取解析都按左端最低地址处理；读回路径的同向错误掩盖了
  物理 memory 中的 whole-burst word reversal。
- 修复现在在 multiword write 时反转 natural DSL word list，在 multiword read 时把 property word index 反向映射回低到高地址；
  独立 Tcl stub 使用不同 word 值验证两个方向。它不改变 bitstream、DSL operation count、授权边界、control barrier、每-word evidence
  或 strict backend contract。
- r15 失败后的独立 recovery 位于
  `recovery_shutdown_after_failed_stage002_20260711T224807Z/`，记录 `SHUTDOWN_RAW_EXIT=125`、
  `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0`、`PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`；它不提升失败 stage。
  r15 frozen 10-file manifest SHA256 为 `c2e71047cae5cfe01012d5da4461a9e0c18d0a5de5dc9842dad66decc9e6812d`。
- r1--r15 exact history/tamper test、完整 summarizer 14/14、top-level 112/112、`tests/p7` 39/39 均 PASS；
  `py_compile`、JTAG wrapper 38/38、两项 no-hardware static/dry-run scan 与 `git diff --check` 均 PASS。随后只启动一次
  canonical `scripts/run_offline_gates.py`，同一进程在 3277 秒后自然返回 `OFFLINE_GATES_RAN=1 status=PASS`；
  `evidence/generated/offline_gate_summary.json` SHA256 为
  `988fcd16f14f88c098cea514099c35f5dba94533b876b371da404d6b55276845`，明确 `no_hardware=true`、
  `hardware_acceptance=PENDING_HW`。这些全部是非硬件结果，不提升任何硬件 stage 或 acceptance。
- r15 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260711_stationary_app_r16_diag_suffix55`。必须先完成 r15 exact
  summarizer/history/tamper 与完整非硬件回归，准确提交全部 r15 evidence、word-order 修复和本交接，再从新 clean source 只生成一次
  checkpoint、r16 plan 并通过全部 dry validation。r16 仍只允许 full ordinals 1--4 与 55--65，严禁 stage 66；最终 1800 秒
  stationary 正式启动次数仍为 0。

## 25. 2026-07-12 r16 diagnostic suffix 增量交接（本节覆盖第 24 节的 next-run 描述）

- r15 immutable failure/recovery、20-fragment word-order machine proof、修复、历史/tamper validator、完整 generic offline 输出与交接已提交为
  `594f91c14a9a28b0be98463bd9faac33ff92d75d`。在该 clean source 上只生成一次新的 P7 checkpoint，13/13 PASS，
  SHA256 为 `c6d9f5758476a5daa353d5bd7e4af446b086d3ada76b08801057ae78b9d31709`；
  `NO_HARDWARE_ACTIONS_EXECUTED=true`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r16 run ID 为 `p7_20260711_stationary_app_r16_diag_suffix55`；15-stage diagnostic plan SHA256 为
  `bcbbcbe6378df274232d445e774385398ad9efaedb2ed0c8a7c1df6b73632cbe`，generation manifest SHA256 为
  `ede962b26269cf995ac046283e5824b239102de4671a8f4375f6a8e65ed21673`。generator、15 个 authorizations、
  15 个 child dry validations、generator executor dry 与独立 executor dry 均 PASS；精确 ordinals 为
  `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`，无 stage 66/stationary，整次仍为 `DIAGNOSTIC_ONLY`、
  `coverage_claimed=false`、`HARDWARE_ACCEPTANCE=PENDING_HW`。
- r16 只启动一次且没有 `--resume`。full ordinals 1--4 与 55--61 全部终态 PASS；这精确证明 word-order 修复后的三个 P6
  frame regressions、三个 64 KiB cases 和四个 1 MiB lane-policy cases 在 r16 source 上通过，但它们仍只属于 superseded diagnostic
  prefix，贡献零最终 acceptance coverage。full ordinal 62 / `p7_ps_functional` 终态 `FAIL_SHUTDOWN_AFTER`，outer ledger
  SHA256 为 `f645d6fa82cb86eb1d8627adfc47d95af277e67f47b040c1bb63309c45955a49`，attempts=12、completed=11、
  failed_stage_index=11；ordinals 63--65 与 stage 66 均未启动。
- r16 stage 62 的 read-only hardware preflight PASS，但 shutdown-before 和 finally shutdown-after 都在任何 programming 前以 rc=41
  fail-closed；两份 stdout 的精确终端错误均为 `P7 JTAG Tcl requires exactly 17 arguments`。PS candidate 未编程、PS ELF 未启动、
  TFDU TXD 未驱动，summary SHA256 为 `19900c6a4b9b470e8ce54b440e0bfad1b4fb8ab4c0e0dacab4df11089748c999`。
  根因是 PS wrapper 的 `build_shutdown_command()` 仍只传 16 个 Tcl arguments，遗漏 JTAG Tcl 新增的
  `max_transaction_bytes`；修复在 `max_operations` 与 `max_runtime_sec` 之间传入同一 canonical upper bound，并新增逐位置 17-argument
  offline regression。read-only preflight PASS 和 recovery PASS 均不得提升 stage 62。
- r16 失败后的独立 recovery 位于
  `recovery_shutdown_after_failed_stage062_20260712T020031Z/`，记录 `SHUTDOWN_RAW_EXIT=125`、
  `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0`、`PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`；外部 legacy
  `hw_server` PID 45220 未被触碰。r16 frozen 12-file manifest SHA256 为
  `0ab0dc9ba4116efd196f769ddb73bdbceed6391be2a7accf383bceae3050993e`，并准确记录失败 PS stage 自身
  `mutation_attempted=false`、`candidate_mutation_attempted=false`。
- r16 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r17_diag_suffix62`。必须先完成 r16 exact
  summarizer/history/tamper、完整非硬件回归与 generic offline gate，准确提交全部 r16 evidence、PS shutdown argv 修复、运行优化约束和本交接，
  再从新 clean source 只生成一次 checkpoint、r17 plan 并通过全部 dry validation。只有机器可重验的
  `rf-comm-p7-diagnostic-impact-proof-v1` 同时绑定 r16 plan/FAIL ledger、55--61 exact PASS summaries、所有 stage-consumed
  artifacts/settings、完整 JTAG source/Tcl/backend/register closure、重新生成的 input/transaction/manifest 及 Python/Vivado/helper identity，
  且逐项 unchanged 时，r17 才允许精确 ordinals `1,2,3,4,62,63,64,65`；任一缺失/不确定/哈希变化都 fail closed 并从最早受影响
  stage 重跑。r17 仍为 `DIAGNOSTIC_ONLY`、零 coverage、PENDING_HW，严禁 stage 66；最终 1800 秒 stationary 正式启动次数仍为 0。

## 26. 2026-07-12 P7 runtime optimization 约束增量交接

- `AGENTS.md` 与 `docs/P7_RUNTIME_OPTIMIZATION_CONSTRAINTS.md` 现在是每个新 P7 diagnostic、offline checkpoint cycle 和 formal
  preparation 的强制入口。优化不改变失败 run 永不 resume、新 ID、scoped authorization、immutable hashes、dry gates、独立 shutdown
  recovery、no-Ethernet、no-motion、max mask 0x3、外部 `hw_server` 隔离或最终 formal 1--66 约束。
- adaptive diagnostic 必须先跑 safety/regression prefix 1--4，然后从 earliest unresolved 或 earliest provably affected ordinal 开始。
  skipped historical PASS 始终贡献零 coverage；diagnostic 永不包含 stationary。当前 r16 的 earliest unresolved 是 62，55--61 只有在上述
  transitive impact proof 完整 PASS 时才能跳过。
- canonical offline gate 当前显式记录 `OFFLINE_CACHE_STATUS=BYPASS` 与真实 build 已运行。未来若加入 cache，只允许完整 content-addressed、
  tool hash/version 与全部 transitive inputs 绑定、hit 后重验 outputs 的 offline cache；hardware auth/raw/shutdown/PASS 永不缓存。最终 formal
  full run 前仍必须在 exact clean source 上保存至少一次 cache-bypassed canonical offline gate。
- 开发迭代只跑 focused tests；用于 hardware authorization 的 checkpoint 前，由 `tools/run_p7_regression_suites.py` 在 clean source 上把
  top-level discovery 与独立 `tests/p7` complete suite 各运行恰好一次，记录命令、discovered count、return code、原始 log hashes 与
  `FULL_SUITE_INVOCATION_COUNT`。checkpoint 用 path+SHA256 重新验证该 summary/logs，不重复执行已覆盖的 suites；任何后续 code/validator
  改动都会使 source-commit binding 失效并要求生成一份新的 exactly-once regression summary。

## 27. 2026-07-12 r17/r18 adaptive diagnostic 增量交接（本节覆盖第 25 节的 next-run 描述）

- r17 仅完成离线计划生成，未连接或操作硬件。生成器错误地把 adaptive plan 序列化为旧的
  `DIAGNOSTIC_SUFFIX_55`，独立 executor 在任何硬件动作前 fail closed。该 blocked 计划及 proof 已冻结在
  `evidence/hardware/p7/plan_generation_history/p7_20260712_stationary_app_r17_diag_suffix62/`；r17 不是硬件
  acceptance run，也永远不得 resume。
- 修复 adaptive plan-mode 序列化后，clean-source exactly-once regression 为 158/158 PASS，P7 checkpoint 为
  13/13 PASS。r18 run ID 为 `p7_20260712_stationary_app_r18_diag_suffix62`；机器 impact proof 允许且计划严格只含
  full ordinals `1,2,3,4,62,63,64,65`，保持 `DIAGNOSTIC_ONLY`、`coverage_claimed=false`、
  `HARDWARE_ACCEPTANCE=PENDING_HW`，没有 stage 66。
- r18 只启动一次且没有 `--resume`。ordinals 1--4 全部 exact PASS；stage 62 在 candidate bit programming 和 ELF
  start 之前以 `P7 XSDB reset target is not unique on the exact authorized device` fail closed。stage 63--65 未启动；
  stationary 正式启动次数仍为 0。r18 ledger SHA256 为
  `2fc74e20e1056960cb6d5fcd06c150b6fd0143aad8fdd18690ad96e309e2fbad`，失败 stage summary SHA256 为
  `6532f6506eaaafa47bc84f13c7c9c9a4c08e5b8f9cc3240617d332cebb5f9d4a`。
- stage 62 的 read-only preflight、shutdown-before、shutdown-after 都 PASS；summary 明确记录
  `programmed_candidate=false`、`started_ps_elf=false`。失败后的独立 recovery 位于
  `recovery_shutdown_after_failed_stage062_20260712T044704Z/`，精确记录 `SHUTDOWN_RAW_EXIT=125`、
  `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0`、`PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`；外部既有
  `hw_server` PID 45220 未被触碰。r18 frozen 12-file manifest SHA256 为
  `c2e48dfa2ebc3e0e967f4cba1706c2d6de083df58c61c0cfb963838c2a674331`。
- r18 的证据只证明旧 Tcl 的 identity-filtered property row count 不唯一；它没有记录各 row 的 target ID，因此不能
  声称已证明“重复 target-ID row”是现场原因。修复采用更稳健且仍 fail-closed 的规则：先验证每条已 identity-filtered
  row 都有非负整数 `target_id`，按 numeric target ID 去重，再要求恰好一个 distinct reset/FPGA/CPU target；在任何 reset
  或 candidate programming 前输出 distinct target counts。
- r18 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r19_diag_suffix62`（若离线生成阻断则继续更换
  新 ID）。必须先准确提交 r18 exact history、target-ID 修复和本交接，再在新 clean source 上完成 required complete suites
  exactly once、P7 checkpoint、impact proof、plan 和全部 dry validation。只有机器 proof 证明 55--61 的全部 transitive
  consumed inputs 未变，r19 才允许严格运行 `1,2,3,4,62,63,64,65`；否则从最早受影响 stage 开始。r19 仍为零 coverage
  diagnostic，严禁 stage 66。

## 28. 2026-07-12 r19--r21 adaptive diagnostic 增量交接（本节覆盖第 27 节的 next-run 描述）

- r19 与 r20 都只在离线 plan generation 阶段 fail closed，均未生成可执行授权或连接硬件。r19 暴露 adaptive proof
  validator 只接受原始 `DIAGNOSTIC_SUFFIX_55` parent；r20 因尚未提交的 r19 blocked record 超出 post-checkpoint
  reproducible-dirty allowlist 而拒绝。两次机器记录分别位于
  `evidence/hardware/p7/plan_generation_history/p7_20260712_stationary_app_r19_diag_suffix62/` 与同级 r20 目录；两者
  永远不得复用。
- 在 commit `b149620f92a2abda4add8529166dd7d5f5359506` 上，required complete suites exactly once 为
  120 + 39 = 159/159 PASS；P7 checkpoint 13/13 PASS，SHA256 为
  `3417abe3497a450bacfb000cede722fa5eff930ded6feeeb7b280eff0b5a9f7b`。r21 impact proof 重新直接绑定 r16 的
  immutable suffix55 plan/ledger 与 55--61 exact PASS，不依赖或提升 r18；proof SHA256 为
  `fa18fcd7efb3cb92583181ee034b1a9e9433b26f59c725d9d4d5b0829277b9b9`。r21 plan SHA256 为
  `d221abb909316b3ab71af5fd8a375077084b03a12d211609b65480655c19b3c3`，严格只含 ordinals
  `1,2,3,4,62,63,64,65`，全部 generator/child/independent dry validation PASS。
- r21 只启动一次且没有 `--resume`。ordinals 1--4 exact PASS；stage 62 的 low-level exact FPGA target count 为 1，
  但旧 high-level filter 得到 `DAP=0, APU=0, CPU0=0`，因此在 reset、candidate programming 和 ELF start 前以
  `P7 XSDB reset target is not unique on the exact authorized device` fail closed。stage 63--65 未启动；stage 66 不在
  plan 中，stationary 正式启动次数仍为 0。ledger SHA256 为
  `7fdd5f36b290666c2b0fe8959db54c1a9476db0bf7bd641d5468f6989b504dc9`，失败 summary SHA256 为
  `feedcbbb8e19609a8cfd35a696d3469574caead2cf67b9eca77ba40366350dc5`。
- 第一次独立 recovery 因使用错误的 P7 outer authorization token 而准确记录 `AUTHORIZATION_MISSING` 且
  `NO_HARDWARE_ACTIONS_EXECUTED=1`；随后新 recovery directory 使用既有 P4 scoped authorization，精确记录
  `SHUTDOWN_RAW_EXIT=125`、`TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、`SHUTDOWN_EXIT=0`、
  `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`。外部 `hw_server` PID 45220 未被触碰。r21 frozen 12-file manifest
  SHA256 为 `29360ddae81a9e847e2858e0067517b6813c9293a331d8ecc9b83bd98cc4dc46`。
- r21 只证明旧 predicate 把所有 APU/CPU0 rows 排除，不能声称现场 row 缺少某个特定 property。修复先把 low-level
  JTAG inventory 收紧为整个连接恰好一个 cable root、一个 device node，且两者精确匹配授权 serial/device/IDCODE；在此
  单设备连接证明成立后，APU/DAP/CPU child rows 按 name 与 distinct numeric target ID 唯一化，FPGA row 仍必须直接携带
  exact JTAG device/cable identity。任何额外 cable/device、重复 distinct child target 或缺失 target ID 都 fail closed。
- r21 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r22_diag_suffix62`（若离线阻断则继续换新 ID）。
  必须先提交 r21 exact history/tamper、两次 recovery、child-target 修复和本交接，再在新 clean source 上重新完成 exactly-once
  suites、checkpoint、impact proof、plan 与全部 dry validation。r22 仍只允许零 coverage diagnostic ordinals
  `1,2,3,4,62,63,64,65`，严禁 stage 66。

## 29. 2026-07-12 r22 adaptive diagnostic 增量交接（本节覆盖第 28 节的 next-run 描述）

- 在 commit `0da648c128e4cdf363754f06a20560bc42b76aae` 上，required complete suites exactly once 为
  121 + 39 = 160/160 PASS；P7 checkpoint 13/13 PASS，SHA256 为
  `254c26015f164e7a855533ed47950eb9d0aba1b3b7c2e5f9ac9adadb52e63ac4`。r22 impact proof SHA256 为
  `bf976a86d44b35250c251ad8c72d8fca0394611aebd68d1d76b253ea536bedd1`；plan SHA256 为
  `aea4a1e20a24eb97552c4d86ef96a4ff3a3f71e7c530ed0dfdefe4eb528d7277`。generator、8 个 child dry
  validations 与 independent executor dry 均 PASS；plan 仍严格只含 `1,2,3,4,62,63,64,65`。
- r22 只启动一次且没有 `--resume`。ordinals 1--4 exact PASS；stage 62 在 reset、candidate programming 和 ELF start
  前以 `P7 XSDB live chain must contain only the one exact device/IDCODE match` fail closed。该证据证明新加的
  `all_device_nodes == 1` 条件过严：low-level JTAG inventory 可含多个带 IDCODE 的 node，而旧有 exact
  device-name/IDCODE predicate 仍只匹配一个授权 Zynq device。stage 63--65 未启动，stage 66 不在 plan 中。
  ledger SHA256 为 `347f3e2e20eec662b6af16b807ae9b03a4d9076f4556ee656b149c1134f54ab5`，失败 summary SHA256 为
  `b9b385a1bc370b500bb1f82d2873d2119ffe4affc9c9356f65b1495ef64124c2`。
- r22 后独立 recovery 精确记录 `SHUTDOWN_RAW_EXIT=125`、`TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`、
  `SHUTDOWN_EXIT=0`、`PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`；外部 `hw_server` PID 45220 未被触碰。frozen
  12-file manifest SHA256 为 `e5b428566872c1f2fd4577690dc3d5dbe7f1453588bf78e98a9413a73ccc7ee9`。
- 修复保留整个 XSDB connection 恰好一个授权 cable root，保留授权 Zynq device-name/IDCODE match 恰好一个，删除
  对“所有任意 IDCODE nodes 总数必须为 1”的无根据限制。随后 child debug targets 仍按 distinct target ID 唯一化；若同一
  cable 上存在第二个 Zynq debug context，它会形成额外 APU/CPU identity 并 fail closed；FPGA row 仍需直接匹配授权
  JTAG device/cable identity。
- r22 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r23_diag_suffix62`。仍须先提交 r22 exact
  history/tamper、recovery、cardinality 修复与本交接，再从 clean source 重新完成 exactly-once suites、checkpoint、impact
  proof、plan 和全部 dry validation。r23 仍为零 coverage diagnostic，无 stage 66。

## 30. 2026-07-12 r23 adaptive diagnostic 增量交接（本节覆盖第 29 节的 next-run 描述）

- 在 commit `f9a3d34641c2aabd08d88e84070e2a1e98ccef79` 上，required complete suites exactly once 为
  121 + 39 = 160/160 PASS；P7 checkpoint 13/13 PASS，SHA256 为
  `6167e0bdfa1936340f745aa3382b3f8a69e5589d9c565bd3297b346e438e0643`。r23 impact proof SHA256 为
  `60b823582b487dba2df805de7bf385b86fb9721f868c25278ba5556b119f6514`；plan SHA256 为
  `18f868adbda3fde8e8e882bc319d0c7f4807b335b07bff40a3c13f7caa15308f`。全部 dry validation PASS，plan
  仍严格只含 `1,2,3,4,62,63,64,65`。
- r23 只启动一次且没有 `--resume`。ordinals 1--4 exact PASS。stage 62 成功证明 `DAP=0, APU=1, FPGA=1,
  CPU0=1, cable_root=1, JTAG_device_nodes=2`，安全选择 APU reset target，精确匹配授权 target/part/serial/IDCODE，
  candidate bit 编程成功，4,456,448 bytes host-to-PS preload 完成，PS ELF 下载并启动且 service ready；随后第一个
  非空 30-byte lane0 functional boundary（index 8）终态失败。原 Tcl 仅保留
  `P7 functional boundary case failed: index=8 length=30`，没有在 shutdown 前保存 descriptor status/error，因此当前证据不能
  猜测具体 firmware/P6 error code。stage 63--65 未启动，stage 66 不在 plan 中。ledger SHA256 为
  `08c16478121c8384e410aad6c64f779610ac04eb13fedc1914a30bcc08f5a9cb`，失败 summary SHA256 为
  `f8439034d8d7a54a2d93b3b350877c198b7d5ad532d12cf5e6c8f49792d0b757`。
- r23 后独立 recovery 精确记录 shutdown programming marker 与 `SHUTDOWN_EXIT=0`；外部 `hw_server` PID 45220 未被
  触碰。frozen 12-file manifest SHA256 为
  `2b3947bcb922289190490b69a3b617226658ed5ccd6f2bf64187950ef8d9c3ed`。
- 诊断改动不改变 candidate 行为：当 functional boundary 非 DONE/zero-error 时，先把失败 descriptor 下载到 immutable bundle，
  输出 index、length、status、error_code 与 capture marker，再抛出包含 status/error 的终端错误。这样下一新-ID run 若在同一点失败，
  可由机器证据定位，仍不会把 recovery 或部分 boundary 结果提升为 stage PASS。
- r23 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r24_diag_suffix62`。必须先提交 r23 exact
  history/tamper、recovery、failure-descriptor capture 与本交接，再从 clean source 完成 exactly-once suites、checkpoint、impact
  proof、plan 和全部 dry validation。r24 仍为零 coverage diagnostic，无 stage 66。

## 31. 2026-07-12 r24 adaptive diagnostic 增量交接（本节覆盖第 30 节的 next-run 描述）

- 在 commit `9a01b3da79f8a0e3561a56f799355915c132f3b1` 上，required complete suites exactly once 为
  122 + 39 = 161/161 PASS；P7 checkpoint 13/13 PASS，SHA256 为
  `c6e2ec78fd44430e3fb453f8b518ab4fbee69f65d2b3f8cf41132f86a7ae318a`。r24 impact proof SHA256 为
  `c96a2f5d50c91660fe4fef85f93a9b526395c11dc16d7f5e8a608f9d850ea720`；plan SHA256 为
  `a9376a13b08eef4890abe7a064aaca5902dbe0ba492a7ba3c48b2910bfb900d6`；全部 dry validation PASS。
- r24 只启动一次且没有 `--resume`。ordinals 1--4 exact PASS；stage 62 再次完成 exact target selection、candidate
  programming、host-to-PS preload 与 ELF start，但新的 failure capture 错误使用 XSDB `dow -data`（host file 到 target
  memory）去执行 target-to-host snapshot，因目标 host file 不存在而在输出 descriptor status/error markers 前 fail closed。
  这次失败证明 capture 实现方向错误，不证明原 30-byte boundary 的具体 error code。stage 63--65 未启动，无 stage 66。
  ledger SHA256 为 `305c4a23b771f4d355bd0225d73c1fa266ccb471b10ab30911439e18b80e7d60`，失败 summary SHA256 为
  `f05bbd4320bcaa1f177f4a3617f487a5e199ca4ea46d4fa4de3566aa863fa0a9`。
- r24 后独立 recovery 精确记录 `SHUTDOWN_RAW_EXIT=125`、shutdown programming marker 与 `SHUTDOWN_EXIT=0`；外部
  `hw_server` PID 45220 未被触碰。frozen 12-file manifest SHA256 为
  `07f616f8050801505a3b76cd5a8c38bd9d9cf0824f0669533c9fd69f656f7e34`。
- 修复把错误的 `dow -data` 替换为既有、已验证的 atomic target-to-host dump helper
  `p7_atomic_dump ... 256`，保持先 capture descriptor、再输出 status/error markers、最后抛错的顺序。不得把 r24 的
  candidate programming/ELF start 或独立 recovery 提升为 stage PASS。
- r24 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r25_diag_suffix62`。必须先提交 r24 exact
  history/tamper、recovery、capture-direction 修复与本交接，再从 clean source 完成 exactly-once suites、checkpoint、impact
  proof、plan 和全部 dry validation。r25 仍为零 coverage diagnostic，无 stage 66。

## 32. 2026-07-12 r24 提交后通用非硬件回归增量交接

- r24 evidence、exact history/tamper、独立 recovery 与 descriptor capture-direction 修复已提交为
  `460d8de525c34fde98240398359d31758c8e5f3f`。
- 随后在该 clean source 上完成一次通用 `scripts/run_offline_gates.py` 非硬件回归；结果为 `status=PASS`、
  `no_hardware=true`、`hardware_acceptance=PENDING_HW`、`OFFLINE_CACHE_STATUS=BYPASS`、
  `OFFLINE_REAL_BUILD_PROCESS_RAN=true`。`evidence/generated/offline_gate_summary.json` SHA256 为
  `5d8a09f1357aee6f26f532bcc165c9b567ba00a5ac1e4b5fb79176b549b52c81`。外部 legacy `hw_server` PID 45220
  未被触碰；本次通用回归未连接硬件。
- 该通用回归不是 r25 的 P7 authorization checkpoint，也没有提升任何硬件 stage/acceptance。必须先准确提交这些生成输出，
  再从新的 clean source 用 `tools/run_p7_regression_suites.py` 完成 required complete suites 各恰好一次，并由
  `tools/run_p7_gate.py` 以 summary path+SHA256 消费该结果生成新的 P7 checkpoint；不得复用 r24 checkpoint。
- r24 仍永远不得 resume；下一硬件 ID 仍必须是 `p7_20260712_stationary_app_r25_diag_suffix62`。r25 仍只允许
  `1,2,3,4,62,63,64,65`（且必须先通过 r16-based transitive impact proof）、零 coverage、PENDING_HW、无 stage 66。

## 33. 2026-07-12 r25 adaptive diagnostic 增量交接（本节覆盖第 32 节的 next-run 描述）

- 通用非硬件刷新已提交为 `6cb92a2cdd7c056d67f79b83e7de4b9fd139104d`。在该 clean source 上，required
  complete suites 各运行恰好一次，122 + 39 = 161/161 PASS；regression summary SHA256 为
  `be1117c4f39e46e39424ccc3cf40c0d41cf0706d887f996bfdcdf011c1e8a07b`。P7 checkpoint 13/13 PASS，
  SHA256 为 `eb1854a9ad1002ca54d75c683e3597159389cc0d3e3700e71275a30f35e6c72c`，明确 no-hardware、
  PENDING_HW、cache BYPASS。
- r25 impact proof SHA256 为 `9eeb81a36b641d14d9031ac2d2595ce5f22719d0bd7f58de5fbff9e76a63a089`；plan
  SHA256 为 `d38f35e6e2475652fc88d168dd07e7b00d7bd41f09d8c2904a053ffd85d1a324`。generator、8 个 child
  wrapper dry validations 与独立 executor dry validation 全部 PASS；plan 严格只含 `1,2,3,4,62,63,64,65`。
- r25 只启动一次且没有 `--resume`。ordinals 1--4 exact PASS；stage 62 成功完成 exact target selection、candidate
  programming、4,456,448-byte host-to-PS preload 与 ELF start。正确的 atomic descriptor capture 随后在 boundary index 6、
  length 1 记录 status 4 / `P7_ERROR_OBJECT_CRC`(13)，stage 立即 FAIL；63--65 未启动，无 stage 66。ledger SHA256 为
  `3219623758db68abfc9dd81f1e1f93d1b450abca3f3a1844cf35c0408d2b8e6c`，失败 stage summary SHA256 为
  `50cf351e5e45c0af3b714fecd668afa4c3568c4d931823863e14e5918722578e`。
- captured 256-byte descriptor SHA256 为 `06be977397d309af45d492dea1208171153b9fa7324b4f52faccca01d21d1acb`。
  它机器可解析地绑定：input 为单字节 `0x00`，expected/input/output SHA256 都是该字节的
  `6e340b9c...17afa01d`，expected CRC32 为 `0xd202ef8d`，但 recorded output CRC32 为 `0x3c0c8ea1`
  （等于单字节 `0x02` 的 CRC32）。这证明旧实现的 CRC/SHA 两次 DDR 读取产生了自相矛盾的 terminal integrity snapshot；
  它不单独证明该瞬态可见性变化的更底层写入来源。
- r25 后独立 recovery `recovery_shutdown_after_failed_stage062_20260712T084539Z` 精确记录 raw rc125、唯一 shutdown
  programming marker、`SHUTDOWN_EXIT=0` 与 PASS；外部 legacy `hw_server` PID 45220 未被触碰。frozen 12-file manifest
  SHA256 为 `4b28cd6d3f53eb28c66a19cfe43842f976b14a4b40e0ea296e594af7d19549a3`。
- 修复把 `p7_integrity_checked` 改为每个最多 256-byte chunk 先 invalidate 并复制到 64-byte aligned local snapshot，
  再让 CRC32 与 SHA256 只消费同一份 immutable snapshot，禁止两个 digest 分别重读 DDR。focused wrapper/history tests、
  py_compile、no-hardware checker 与真实 Vitis build PASS；新 candidate ELF SHA256 为
  `72c6d51db888f15e18fc8de459f41707e9c9601507bf42bfed6a07385b79523a`，map SHA256 为
  `8af051f80babc7e075c668ebb500f8e796e1d8c9616ab7dbbc6dd7a6a7a99fec`；这些仍是非硬件结果。
- r25 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r26_diag_suffix62`。必须先准确提交 r25
  exact history/tamper、recovery、integrity snapshot 修复、新 candidate 与本交接，再从 clean source 完成 exactly-once suites、
  checkpoint、r16-based impact proof、plan 和全部 dry validation。r26 仍为零 coverage diagnostic，无 stage 66。

## 34. 2026-07-12 r26 diagnostic suffix 增量交接（本节覆盖第 33 节的 next-run 描述）

- r25 evidence、single-snapshot integrity 修复与新 Vitis candidate 已准确提交为
  `e4d6937ad559065a650054998807599f859f34bf`。在该 clean source 上，required complete suites 各运行恰好一次，
  122 + 39 = 161/161 PASS；regression summary SHA256 为
  `2978f86f5e23bf9c74c51e713ca0353184ea19dc935fdc794b7a0e64d7825b28`。新 P7 offline checkpoint
  13/13 PASS，SHA256 为 `e200f338f8ef1cd251fe38da1dac8e8d4a5017fc1146348abfa7024120c3f3b1`，明确
  `NO_HARDWARE_ACTIONS_EXECUTED=true`、`HARDWARE_ACCEPTANCE=PENDING_HW`、cache BYPASS 与 real build。
- 首次请求 r26 adaptive suffix62 在任何 plan/authorization/hardware action 前 fail closed：机器 impact proof 发现 r16
  ordinal 55 的 transitive consumed `elf` 已改变，因此不得跳过 55--61。该阻断没有消费硬件 run ID。随后生成的实际
  r26 为 `p7_20260712_stationary_app_r26_diag_suffix55`，sequence plan SHA256
  `0cfdfa7604dcc652715f3f519e3998329dbdadde4abcbd6033d0a671de68371c`，generation manifest SHA256
  `8150e41ab81b69f9208f72018ea2035d605500484f3651259d88e71b56d8adef`；15 个 authorization、15 个 child dry
  validation、generator executor dry 与独立 executor dry 全部 PASS。plan 仅含 ordinals
  `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`，零 coverage、PENDING_HW、无 stage 66。
- r26 只启动一次且没有 `--resume`。ordinals 1--4 与 55--61 exact PASS，但它们只属于 immutable diagnostic
  prefix/suffix，贡献零 acceptance coverage。stage 62 `p7_ps_functional` 完成 exact target selection
  (`DAP=0, APU=1, FPGA=1, CPU0=1, cable_root=1, JTAG_device_nodes=2`)、candidate programming、
  4,456,448-byte preload、ELF start 与 service ready；boundary 0--7 PASS，boundary index 8 / length 30 / lane0
  以 status 4、`P7_ERROR_OBJECT_CRC`(13) 终止。stage 62 正确为 FAIL，63--65 未运行，stage 66 不在 plan；正式
  stationary 启动次数仍为 0。outer ledger SHA256 为
  `72acea5438a578619bd1c508e3d5649c4a1779058d985255278c80f789cafa45`。
- captured descriptor `boundary_8_descriptor_failure.bin` SHA256 为
  `e367cde75315414d98e2db62c6ef175f6ee156f9566ea7f73192148662647847`。它机器可解析地绑定 30-byte input
  `00..1d`、expected/input SHA256 `f2192584b67da35dfc26f743e5f53bb0376046f899dc6dabd5e7b541ae86c32f`、
  expected CRC32 `0xc5665f58`、recorded output CRC32 `0x0a703d75` 与 recorded output SHA256
  `7b1241c20725167eb4bf923caa908244ee622a994ec2e3fcc8cadea7584f1d46`。r26 没有捕获失败 output/trace
  bytes，因此这些 digest 只能证明 terminal integrity rejection，不能证明实际 output bytes 或更底层根因。r25 修复已把首个失败
  从 length 1/index 6 推进到 length 30/index 8，但不得把任何 boundary PASS 提升为 stage PASS。
- r26 后独立 recovery `recovery_shutdown_after_failed_stage062_20260712T105210Z` 精确记录 raw rc125、唯一 shutdown
  programming marker、`SHUTDOWN_EXIT=0` 与 PASS；summary SHA256 为
  `59f57517f0094a7dc09c1b8b12a727a50c0642685b3ab45c3aa924245e46806c`。recovery PASS 不改变 stage 62 FAIL。
  frozen 12-file manifest SHA256 为 `aad1f3da5324f3c13f4919d8ae437a36225325b257c22fd714d225f28362b799`；
  外部 legacy `hw_server` PID 45220 未被触碰，临时 helper 已自然退出。
- 当前诊断改动不改变 candidate 行为：在 functional boundary 失败后、抛出终端错误前，按顺序 atomic capture descriptor、
  output bytes 与完整 trace capacity，并分别输出机器可解析 capture marker；status/error markers 在 capture 前先写出，从而即使某个
  capture 自身失败也保留原始 terminal 状态。r26 frozen source 明确不存在这些新的 output/trace capture，因此历史验证必须继续要求
  r26 bundle 中没有 `boundary_8_output_failure.bin` 与 `boundary_8_trace_failure.bin`。
- r26 永远不得 resume；下一硬件 ID 必须为新的 `p7_20260712_stationary_app_r27_diag_suffix62`（若任何离线 gate 或 impact proof
  阻断则更换新 ID）。必须先准确提交 r26 exact history/tamper、recovery、output/trace capture 与本交接，再以新 clean source 完成
  required complete suites exactly once、cache-bypassed canonical P7 checkpoint、impact proof、plan 和全部 dry validation。只有机器
  proof 证明 r26 的 55--61 全部 transitive consumed inputs 未变，r27 才允许 `1,2,3,4,62,63,64,65`；否则从最早受影响 stage
  fail closed。r27 仍是零 coverage diagnostic，严禁 stage 66。

## 35. 2026-07-12 r27 adaptive diagnostic 增量交接（本节覆盖第 34 节的 next-run 描述）

- r26 exact history、recovery 与 failure output/trace capture 已准确提交为
  `164cedde1e7d91a7eeb3787ec160525e3352da9f`。在该 clean source 上，required complete suites 的唯一 invocation
  自然完成 122 + 39 = 161/161 PASS；regression summary SHA256 为
  `140bb4694ef5ef147f9fcdd67e8c6b34af99daa6c2be47197ad9b81a4ef8e210`。cache-bypassed canonical P7 checkpoint
  13/13 PASS，SHA256 为 `605fb5d8b914e654c70fe29167a7ce5f7339604919813477f9ff0365c465d6f1`，明确 no-hardware、
  real build 与 `HARDWARE_ACCEPTANCE=PENDING_HW`。
- r27 machine impact proof 直接绑定 r26 immutable plan/ledger，逐项重验 ordinals 55--61 的 authorization settings、
  tool/runtime identity、source dependencies、bit/LTX/profile/transactions/backend manifests、ELF/XSA、register map、XDC 与 pinmap；
  所有 transitive consumed inputs unchanged，proof SHA256 为
  `c42727a4c438b757247a039023c6a71e32affddda8665e37060c53657433cc8c`。r27 plan SHA256 为
  `66cbbf3471ce8a2cef7d653ffb16be2bb56f27374dff1276b090bdf7277f0cc2`，generation manifest SHA256 为
  `1761ca1db20e91953bdce7c4f3bdcaf353e9807d9524bace4baa568d9c08fa8c`；8 个 authorization、8 个 child dry、
  generator executor dry 与独立 executor dry 全部 PASS。plan 只含 `1,2,3,4,62,63,64,65`，零 coverage、PENDING_HW、
  无 stage 66。
- r27 run ID 为 `p7_20260712_stationary_app_r27_diag_suffix62`，只启动一次且没有 `--resume`。ordinals 1--4 exact PASS；
  stage 62 完成 exact target selection、candidate programming、4,456,448-byte preload、ELF start 与 service ready，boundary
  0--7 PASS，但 boundary index 8 / length 30 / lane0 再次以 status 4、`P7_ERROR_OBJECT_CRC`(13) FAIL。63--65 未运行，
  stage 66 不在 plan，stationary 正式启动次数仍为 0。outer ledger SHA256 为
  `16bf3a1c6a9c6f39a1254c951b1fc1c1aeb6f338265d00a5d6b664d0ccf41134`；stage summary SHA256 为
  `bdc64ce7ef248aa2e9e25d1496a80a51ebf0b6d867aa89461a444cb05e140662`。
- r27 descriptor SHA256 `d6ff7937295d60a6c337a60989c80da61c58767b07082e5df965895ba8f0483a` 绑定 expected/input
  SHA256 `f2192584...e86c32f`、expected CRC32 `0xc5665f58`、recorded output CRC32 `0x1fda9db9` 与 recorded
  output SHA256 `85cc3c9bdc8b6699e216e48c446c9f4f7d861a8bcfef504fcaeb02b3e99ad750`；两个 output digest 来自同一
  immutable firmware snapshot。fragment trace SHA256 `dd4721823cdd22ae8537c86582eca9ea268e3e9faf4abd824a22fae2bbd71bda`
  精确记录 lane0、fragment 0/1、attempt 1、`result=0` 与 zero error/retry failure；该 trace 不得写成 accepted PASS。host terminal output capture SHA256
  `0679246d6c4216de0daa08e5523fb2674db2b6599c3b72ff946b488a15290b62` 是 30 个零字节；frozen firmware 明确先
  `p7_wipe_partial` 再发布 FAILED，因此该文件证明 cleanup wipe 生效，不是 digest 所消费的失败 snapshot，也不能用于猜测原始错误字节。
- r27 后独立 recovery `recovery_shutdown_after_failed_stage062_20260712T113542Z` 精确记录 raw rc125、唯一 shutdown marker、
  `SHUTDOWN_EXIT=0` 与 PASS；summary SHA256 为
  `4f10313c44b51f3cb5dd922a7117c248466b2e9df56ab856d1559cf8440a4992`。recovery PASS 不改变 stage 62 FAIL。
  frozen 12-file manifest SHA256 为 `ff14c3fd754fe22d2defe3fc9be11819305f4ea9350a5d1123913e4a50fc9b45`；临时 helper
  已自然退出，外部 legacy `hw_server` PID 45220 未被触碰。
- 当前诊断修复保留 r27 的安全清理顺序：output digest 使用的 immutable snapshot 最多保留前 256 bytes；若发生 CRC/SHA
  integrity rejection，firmware 在进入 shutdown/wipe/FAILED 路径前把 64-byte self-describing header 与该 retained snapshot
  发布到 trace array 后的独立、对齐、range/overlap-validated diagnostic region。host 只对 error 13/14 验证 publication magic，
  atomic capture 320 bytes，随后逐 word 清零、读回验证、保存 wipe verification，再抛出原始 stage error。正常成功路径、P6 事务、
  output wipe、shutdown 与 acceptance 语义不变；该机制只用于在下一次失败时机器验证 digest 对应的实际 bytes。
- focused history/wrapper tests、py_compile、core-readiness 23/23 与真实 Vitis build PASS；新 candidate ELF SHA256 为
  `96233942db9e17ace2ab240303e8402c8075c706094de416d5c7347769ae8731`，map SHA256 为
  `bcd406305971fad92e760075b912020ff3b265b2ecf68046bade13ecbf5bcf43`，OCM image end `0x00015830` 仍低于
  hard boundary `0x00020000`。这些均为非硬件结果，不能提升 stage 62 或 hardware acceptance。
- r27 永远不得 resume；下一硬件 ID 必须为新 ID r28。由于 firmware/ELF 改变，任何跳过 55--61 的请求都必须重新通过机器
  transitive impact proof；若现有 proof 模型把 ELF 视为 ordinal 55 consumed input，则必须 fail closed 从 55 开始，不得人工豁免。
  必须先准确提交 r27 exact history/tamper、recovery、pre-wipe integrity snapshot capture 与本交接，再从新 clean source 完成
  required complete suites exactly once、cache-bypassed checkpoint、plan 与全部 dry validation。r28 仍只能是零 coverage diagnostic，
  不得包含 stage 66。

## 36. 2026-07-12 r28 suffix55 diagnostic 增量交接（本节覆盖第 35 节的 next-run 描述）

- clean source `e4c369f380119d527b3238b09fc5fe3d628760d7` 上 exactly-once 非硬件回归为 161 PASS，摘要
  `build/p7_regression_e4c369f_r28.json` SHA256
  `7b0ad946dc1259042f55a0787bbb2a1cfc27a7dd7507f736048d6be343955707`；cache-bypassed canonical offline checkpoint
  13/13 PASS，SHA256 `2d617d9ba3668a4e8c7e8247db31cf924b6f06f40f3e5927a0b237bebaa598fd`，保持
  `HARDWARE_ACCEPTANCE=PENDING_HW`。因 ELF 改变，55--61 impact 无法证明不变，按 fail-closed 规则直接选择 suffix55。
- r28 run ID `p7_20260712_stationary_app_r28_diag_suffix55` 只启动一次、没有 `--resume`。15-stage diagnostic plan SHA256
  `beb36742ff67111b67ca7e2ce1034d1ea04f3ce284fc03127587c05d450de5f8`，generation manifest SHA256
  `631fa6b89f71d6bcf8b97011a9fdd6a9196ab4592e2f25f00d5b25a9fd474c87`；全部 authorization/dry validation PASS。
  r28 是 `DIAGNOSTIC_ONLY`、`coverage_claimed=false`、`HARDWARE_ACCEPTANCE=PENDING_HW`，无 stage 66。
- r28 ordinals 1--4、55--61 exact PASS，但只属于 superseded diagnostic prefix，零 acceptance coverage。stage 62 在 functional
  boundary index 11、length 30、replicate-0x3 policy 处 FAIL，status 4、error 13；63--65 未运行。outer ledger SHA256
  `268f91df72b7b9956772ddc7f8fba6b1e0ed2925f80c4a5f081de435dd321f4a`。不得将前缀或 recovery 写成 stage 62 PASS。
- r28 failure descriptor SHA256 `042c8059fca445532853554af7b4b67acba1a56fb5a32a96c6df557c25fff58e`：session
  `0x50370001`、object 12、expected/input CRC32 `0xc5665f58`、output CRC32 `0x0b14a45e`、output SHA256
  `152b23e36032b5b79a2f47434511a939aa869078ef97c37d757772102af7972c`、fragments/completed 1/1、lane0/lane1/replicated
  1/1/1、completion sequence 12。post-terminal output 是 30 个零字节（SHA256
  `0679246d6c4216de0daa08e5523fb2674db2b6599c3b72ff946b488a15290b62`），仅证明安全清理后的状态。
- r28 trace SHA256 `775a705154de00d454df4390dc4d8cabaa66f00eb17a75333d840eee7b53c608` 精确记录 lane mask `0x3`、attempt 1、
  result 1、error 0；它证明该 fragment 的 P6 accepted trace，不提升整个 stage。Tcl 随后因
  `P7 integrity failure snapshot publication marker missing` fail closed；没有生成 integrity snapshot 或 wipe-verify 文件。
- r28 后独立 recovery `recovery_shutdown_after_failed_stage062_20260712T134058Z` 记录 raw exit 125、唯一 shutdown marker、
  `SHUTDOWN_EXIT=0`、PASS；summary SHA256 `d2947f41dc28832f93599d27f8ed6130a1f57addce569768ee582c522edfd208`。
  historical freeze manifest SHA256 `2ccf309c28f907388152e393b4cae877754955bf0b7fd7cb03e39ed47bceb81a`。
- 当前修复把 failure snapshot address/bytes/status 放入 mailbox words 39--41，并在 terminal descriptor 之前发布；Tcl 先记录
  三个机器可解析 marker，再核对 status/address/320-byte length 和 DDR magic，仍在退出前 capture 后 wipe。这样下一次新 run
  即使仍失败，也能区分 firmware validation rejection 与 DDR publication visibility mismatch。
- focused wrapper/history tests、py_compile、core-readiness 24/24 与真实 Vitis build PASS；新 candidate ELF SHA256
  `814ebddc5a84635556530d9f62d628c4626e582a58eeb2d3b60a98c672cbc031`，map SHA256
  `4191e2a75016dd56abf67f03e148cc790fbf66328048354a335cfca089441320`，OCM image end `0x00015830`，低于
  hard boundary `0x00020000`。这些仍是非硬件结果，不提升 stage 62 或 hardware acceptance。
- r28 永远不得 resume。下一硬件 run ID 必须为新的 r29；先准确提交 r28 history/tamper/recovery 与 mailbox diagnostic 修复，
  在 clean source 上完成 exactly-once required suites、cache-bypassed offline checkpoint、plan/authorization/全部 dry validation。
  ELF 再次改变，因此除非新的机器 transitive impact proof 证明 55--61 consumed inputs 全部不变，否则 r29 仍必须 fail closed
  从 stage 55 开始。r29 仍为零 coverage diagnostic，严禁 stage 66；最终 1800 秒 stationary 仍保持零次启动。

## 37. 2026-07-12 r29 suffix55 diagnostic incremental handoff

- r28 history/recovery and the mailbox-diagnostic change were committed as `529ac9a4bfd8e5c694b5c7221a1ad6a4cb619df9`; the clean checkpoint binding and historical inner-preflight reap fact were committed as `cd26d97b036366b901d9c20f0273da38f6042953`.
- On clean `cd26d97b...`, the exactly-once complete regression was 161/161 PASS with summary SHA256 `4aecff5392e06d2c4ef4cd23e987bf68a8dbf575c1f4de651e43a812e8b1ef45`; the cache-bypassed canonical offline checkpoint was 13/13 PASS with SHA256 `72366ba4ae1eb406e0a976c2344298ec56bfc1ca73d6b6812398285a807b70b9`. Both remain non-hardware evidence and `HARDWARE_ACCEPTANCE=PENDING_HW`.
- r29 was `p7_20260712_stationary_app_r29_diag_suffix55`; plan SHA256 was `11f71be6068ca3e0ae4935a21e5a7b5c264c1718c882ae1487f6235d0b8c3d2a`, generation-manifest SHA256 was `fd2a97a6764a294a6dd4a93f8654f4d3442f23bb1ca152fb486733d3aaa45d3d`, and all authorization/dry validations passed. The plan contained only ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`, zero coverage, PENDING_HW, and no stage 66.
- r29 was launched exactly once without `--resume`. Ordinals 1--4 and 55--61 were exact diagnostic PASS with zero acceptance coverage. Stage 62 failed at boundary index 13, length 214, lane1 policy, status 4, error 13; stages 63--65 did not run. Outer ledger SHA256 is `e2adcc5dd96b0c9d5d20454de41a1c6a28090591448778899b8afcfaa808b0cb`.
- The exact failure descriptor SHA256 is `8df414a31c8beabb0706ee7c4afa61f87c51d83c4f58340cfc13cc556a989f37`: session `0x50370001`, object 14, length 214, expected CRC32 `0xf05c083e`, output CRC32 `0xe56aefe1`, expected/input SHA256 `dedff2184de121c60ec94c4cb94a0450cac47257c56afa8f2e11c5f64d3dd661`, output SHA256 `fa740d204a804cb81d21e7d56bff7091dbc387d59c9e50e2d400a4275f85bcf0`, lane0/lane1/replicated `0/1/0`, completion sequence 14.
- Trace SHA256 `c8fcb94f910b24a4e0da0f5a59eb128343936a8f66ef874e547e5f69a6765883` records lane mask `0x2`, attempt 1, result 1 and zero error/retry fields. Post-terminal output SHA256 `c087c4c3d79aa6dabe40b1a5f5d8cc1b7d96be35a2b4795b692171fdf58a3c1b` contains only byte `0x02` at offset 100. Firmware mailbox reported snapshot address `0x0b100040`, bytes 320, status PUBLISHED, but the host could not observe the DDR magic; no snapshot or wipe-verify file was created. These facts do not promote stage 62.
- Independent recovery `recovery_shutdown_after_failed_stage062_20260712T160421Z` recorded raw exit 125, one shutdown-programmed marker, `SHUTDOWN_EXIT=0`, and PASS; recovery summary SHA256 is `5d4bca28a224a3fc316415aa20b27eb6297745da0fc6ee854ecd6b820865e936`. Frozen historical manifest SHA256 is `09f2f89d8567c5927ab3a84853482a9c3673df4dc648ab76a05a08dc1ad69210`. Recovery PASS does not alter the stage FAIL. External legacy `hw_server` PID 45220 was not touched.
- The current non-hardware fix moves the single integrity-failure snapshot to fixed 64-byte-aligned reserved OCM address `0x00021000` (after the eight descriptors and ending before `0x00030000`), clears it before READY, publishes the magic with a barrier, reads it back in firmware, and publishes the readback in mailbox word 42. Status PUBLISHED is impossible unless firmware readback equals `0x53463750`; the host independently requires exact address/bytes/status/readback and then reads, captures, wipes, and verifies the same OCM region.
- Focused wrapper/history tests, `py_compile`, no-hardware checker, core-readiness 24/24, and a real offline Vitis build passed. The new candidate ELF SHA256 is `187ad735062bf85b04424b0f80b4ae5b6de1aba72fd105b44cd467b509f48f7e`; map SHA256 is `e2229c32790508eb59b441a32172a020bfa1792db1a4e42aaf6e205a91df60db`; OCM linked image end remains `0x00015830`, below the `0x00020000` hard boundary. These remain non-hardware results.
- r29 is immutable FAIL and must never resume. Before any new hardware, accurately commit r29 history/tamper/recovery, the OCM snapshot fix, new artifacts and this handoff; then on the new clean source run required complete suites exactly once, create one cache-bypassed checkpoint, generate r30 and pass every dry validation. Because the ELF changed, fail closed from stage 55 unless a new machine transitive-impact proof proves every consumed input for 55--61 unchanged. r30 remains zero-coverage diagnostic and must not contain stage 66; the formal 1800-second stationary run has still never started.

## 38. 2026-07-13 r30 suffix55 diagnostic incremental handoff

- The r29 immutable failure, exact historical validation, OCM snapshot relocation, and new build artifacts were committed as `7ce64d36a4a9c98c14c639d21cae3740119c5f68`. On that clean source, the only required complete-suite invocation passed 122 + 39 = 161/161; `build/p7_regression_7ce64d3_r30.json` SHA256 is `3a6acbc75375ed6e917e05e054b4fd767bf2ec998ed521c209583669deeae002`. The cache-bypassed canonical offline checkpoint passed 13/13 with SHA256 `096f7833148e39a5b1e2880928c7d8ad935e17de5089e1841cee52b0ce2f536d`, no hardware actions, and `HARDWARE_ACCEPTANCE=PENDING_HW`.
- r30 was `p7_20260712_stationary_app_r30_diag_suffix55`. Its plan SHA256 was `1d795f2b9e475409602fe8993d58d77cf73f8df2903b2fb9cdf412d5df9030b2`, generation-manifest SHA256 was `43d98fa47adc34a5bddef8e38767dcd5e11e62024ea705ef26d4418192898842`, and all 15 authorizations, 15 child dry validations, generator executor dry validation, and independent executor dry validation passed. The plan contained only ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`, zero coverage, PENDING_HW, and no stage 66.
- r30 was launched exactly once without `--resume`. Ordinals 1--4 and 55--61 were exact diagnostic PASS but contribute zero acceptance coverage. Stage 62 failed at boundary index 10, length 30, stripe-round-robin policy with lane0 selected, status 4, error 13; stages 63--65 did not run. The immutable outer ledger SHA256 is `e63d773e01c5678fd37277ca7effc5bf4d69273df50b378e452b75b7d729eb11`; stage-summary SHA256 is `f33356a7e93da1b2945c215c9a57c8b1598d934c49a61f0a7a798bc8e93e9df1`; raw-manifest SHA256 is `1f58c0931674b5cf6f3da67f1e40acc0cfc751a9b213801fdc99b985d40bd4f9`.
- The exact descriptor SHA256 is `31bbae84a4619feab7312fe0a7afa683bded879788239c19f25c24f61fade980`: session `0x50370001`, object 11, length 30, expected CRC32 `0xc5665f58`, output CRC32 `0x1fda9db9`, expected/input SHA256 `f2192584b67da35dfc26f743e5f53bb0376046f899dc6dabd5e7b541ae86c32f`, output SHA256 `85cc3c9bdc8b6699e216e48c446c9f4f7d861a8bcfef504fcaeb02b3e99ad750`, fragments total/completed `1/1`, lane0/lane1/replicated `1/0/0`, completion sequence 11. Trace SHA256 `7e22964c05ee1c45a9d14f04444a52ece17c61296547c1ae716d373efc2ead0d` records lane mask `0x1`, attempt 1, result 1, and zero error/retry fields. Post-terminal DDR output SHA256 `0679246d6c4216de0daa08e5523fb2674db2b6599c3b72ff946b488a15290b62` is 30 zero bytes after fail-closed wipe; it is not the pre-wipe payload.
- The r29 OCM publication fix is hardware-proven: firmware reported address `0x00021000`, bytes 320, status PUBLISHED, and magic readback `0x53463750`; the host captured and then wiped the snapshot. Snapshot SHA256 `e99af3fe526f68a64c6bbc42207db7d440008e3a38b2685d2a812ee3e02fd95d` has an exact 64-byte self-describing header whose CRC/SHA match the descriptor and whose 30-byte payload is `000002030000060700000a0b00000e0f000012130000161700001a1b0000`: every little-endian 32-bit input word has its low 16 bits zeroed. Wipe-verify SHA256 `7b6436b0c98f62380866d9432c2af0ee08ce16a171bda6951aecd95ee1307d61` is exactly 320 zero bytes. This proves deterministic pre-wipe payload corruption, not stage PASS or final root-cause closure.
- Independent recovery `recovery_shutdown_after_failed_stage062_20260713T015350Z` recorded raw exit 125, the unique shutdown-programmed marker, `SHUTDOWN_EXIT=0`, and PASS; recovery-summary SHA256 is `524f377392d57c61567d2eb037619252fe910c108c926619b353975f34b19edb`. The 12-file frozen historical manifest SHA256 is `28940bc3ff4de3c264ffa71cee11d3946572626c354b42923f917b5a77fb25b7`. Recovery PASS does not alter stage 62 FAIL. External legacy `hw_server` PID 45220 remains untouched.
- The current non-hardware repair removes opaque word-copy behavior from the critical P7 payload boundaries. A volatile byte-copy helper writes and reads back every byte with a barrier; it now covers encoded-chunk repair, PS-to-P6 staging, P6-to-PS staging, and DDR output publication. A volatile byte comparator replaces the pre-decode `memcmp`. New distinct fail-closed codes identify encode-copy (21), transfer-copy (22), and output-copy (23) failures. The output-copy failure path wipes the entire possibly written current chunk. This is a source-level repair supported by r30's deterministic pattern, not hardware proof of success.
- The real offline Vitis build passes with candidate ELF SHA256 `47257305c56b99641421a716c4530d28ea2d22901f4a27c79f0a2beb77d9eb0b`, map SHA256 `7b66a3cd0b9ca39eabec2cc90094824577fe5bdbb19eb03e90212703a63bf97a`, OCM image end `0x00015830`, and build-summary SHA256 `d87e75f1ec177495e65934ba2cad26766d91502dc33bfc425d3f5e33e7a71733`. Machine-parsed disassembly (SHA256 `69e1eac881dee277d087c599900a921ed27aba4073952d786624140a99e3bd55`) proves `ldrb`/`strb`, `dsb`, no helper-local `memcpy`/`memcmp`, at least four copy-helper calls, and one comparator call. Core readiness passes 25/25 with SHA256 `462212026a8618428a7c88baa23fc1e08822ce072facad931d2971d125a9834a`. All are non-hardware results and retain PENDING_HW.
- r30 is immutable FAIL and must never resume. The next hardware run ID is r31. First accurately commit r30 evidence/history/tamper/recovery, the byte-copy repair, build artifacts, and this handoff. Then, from the new clean source, run every required complete suite exactly once, create one cache-bypassed canonical offline checkpoint, and pass plan/authorization/all dry validations. Because the ELF and wrapper/tool inputs changed, fail closed from stage 55 unless a new machine transitive-impact proof proves all consumed inputs for 55--61 unchanged. r31 remains zero-coverage diagnostic and must not contain stage 66. The formal 1800-second stationary run has never started.

## 39. 2026-07-13 r31 suffix55 diagnostic incremental handoff

- The r30 evidence, exact history/tamper validation, byte-copy hardening, and build artifacts were committed as `0539667cfbaa29a8ddb0b137bb9d4b222f1e4eb4`. On that clean source, the one required complete-suite invocation passed 122 + 39 = 161/161; regression summary SHA256 is `c2a71a9d7097e7f6172b229352f0bd855d762ee93d15e2e4c7985ef81ccd4d67`. The cache-bypassed canonical P7 checkpoint passed 13/13 with SHA256 `73e2c9db0df532885833a8e2fd2899c95fe180360e105d77e2ba193cfe455748`, no hardware actions, and `HARDWARE_ACCEPTANCE=PENDING_HW`.
- r31 was `p7_20260713_stationary_app_r31_diag_suffix55`. Sequence-plan SHA256 was `581470b697b2bffe1fa66049fb4371465925297b57ff5ab19ab79fc8464c22de`, generation-manifest SHA256 was `2919f3963843aed27ba82fab8e293d51ccf997033654791fa0c08b46a5b8f4b6`, and all 15 authorizations, 15 child dry validations, generator executor dry validation, and independent executor dry validation passed. The diagnostic plan contained only ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`, claimed zero coverage, retained PENDING_HW, and did not contain stage 66.
- r31 was launched exactly once without `--resume`. Ordinals 1--4 and 55--61 were exact diagnostic PASS but provide zero acceptance coverage. Stage 62 failed at functional boundary index 8, length 30, lane0 policy, status 4, error 23 (`P7_ERROR_OUTPUT_COPY`); stages 63--65 did not run. Outer ledger SHA256 is `fbb0ace48ad3c5c41d2a078e9a683d72699b4c1d54c59c4c3fd3256f4e783984`; stage-summary SHA256 is `346ce310967babed365810f230b4a7ae887e9e3250fc844b9a285bbaad4dcc07`; raw-manifest SHA256 is `1b465b72b7bd7ca73421cbf086542ec484fd998d2eb41a6379c851e94de2951b`.
- Failure descriptor SHA256 `60dd6a044ef42e7bd13273aad8d4c423cb74568a56d9006e20aba7d1c63efe33` binds session `0x50370001`, object 9, length 30, expected CRC32 `0xc5665f58`, expected/input SHA256 `f2192584b67da35dfc26f743e5f53bb0376046f899dc6dabd5e7b541ae86c32f`, fragments total/completed `1/0`, output CRC32 zero, all-zero output SHA256, zero lane completion counters, error 23, and completion sequence 9. Trace SHA256 `71b5234332dc3355db44b7e36b459d3805bdf3b85968306c59ed9b7e35adb969` records lane mask `0x1`, attempt 1, result 0, trace error 23, and P6 error 23. Post-terminal output SHA256 `0679246d6c4216de0daa08e5523fb2674db2b6599c3b72ff946b488a15290b62` is exactly 30 zero bytes and equals the prefilled zero file because firmware wiped the possible partial output before FAILED publication. It is not a pre-wipe observation.
- r31 proves only that the overwrite-first hardening reached the verified final DDR-output-copy boundary and that its write/read comparison rejected. It does not record the first differing offset or the pre-wipe destination bytes, cannot distinguish a bad source reread from a failed destination write/readback, and cannot establish the original `rf_app_encode_fragment` boundary. It therefore does not prove that volatile byte copying fixed r30 or that the confirmed `rx_payload` misalignment is the root cause.
- The wrapper's stage-local shutdown-after passed and reaped its process tree. A separate recovery at `recovery_shutdown_after_failed_stage062_20260713T044102Z` recorded raw exit 125, the shutdown-programmed marker, `SHUTDOWN_EXIT=0`, and PASS; recovery-summary SHA256 is `9f59c86fe9fc2ff621d71d2c3063f7d223198a57fbed843a6e04d9bc80fba762`. Frozen historical manifest SHA256 is `fac42095fa2572b02b069b10e6cfc3eb551a7eea7ff3eefbc41370f6e0511c6c`. Neither shutdown result changes stage 62 FAIL. External legacy `hw_server` PID 45220 remained untouched.
- The consultation document `C:\Users\user\Downloads\P7_STAGE62_FIX_RECOMMENDATIONS_CN.md` was read in full and verified at SHA256 `d606e6acd4d4ca74a975607bdf9167a714da80adcdcb91cd80a8bfcf91a4d13d`. Its ZIP-proposed diff is empty, so it is conceptual advice rather than a reviewed patch. Direct source inspection confirms an alignment hazard on 32-bit Cortex-A9: two pointers occupy eight bytes, `tx_payload[247]` then makes `rx_payload` begin at offset 255 (`mod 4 = 3`). This is a confirmed risk and strong suspect, not a confirmed root cause.
- Before any next hardware, replace the current overwrite-first diagnostic with a pre-repair `ENCODE_RAW` comparison against an independent immutable input reference, publish exactly one atomic first-error diagnostic in fixed OCM before timely output wipe, and make the host capture/validate/wipe the diagnostic without pausing shutdown. Add nonzero output canary and a nonzero-leading 30-byte vector; explicit 64-byte alignment/capacity separation for critical local buffers; source/destination address-low-six, mismatch, digest, and snapshot evidence; end-to-end input-reference comparisons; host/Tcl parsing tests; 1--247 and alignment/canary/first-error offline matrices; and final ELF disassembly/map/stack checks. A large aligned automatic input reference must not silently change the stack layout, so prefer fixed static/OCM diagnostic storage or explicitly controlled address-layout evidence.
- r31 is immutable FAIL and must never resume, restart, or be copied as a new run. Any later hardware diagnostic must use a new ID, currently r32, pass scoped authorization/hashes/offline/dry gates, run the mandatory safety prefix, claim zero coverage, retain PENDING_HW, and exclude stage 66. It may skip 55--61 only if machine-readable transitive-input proof establishes that every consumed input is unchanged; otherwise it must fail closed from the earliest affected stage. The formal complete run remains stages 1--66, and the unique 1800-second stationary stage has never started.

## 40. 2026-07-13 r31 post-failure non-hardware diagnostic hardening

- A repeated read-only audit leaves r31 unchanged: its authoritative per-run ledger is FAIL with SHA256 `fbb0ace48ad3c5c41d2a078e9a683d72699b4c1d54c59c4c3fd3256f4e783984`; ordinals 1--4 and 55--61 are diagnostic-only PASS, ordinal 62 is FAIL, and 63--65 are unrun. The raw bundle remains 278/278 hash-valid with no partial files. No r31, Vivado, XSCT, or candidate helper process remains. The pre-existing external legacy `hw_server` PID 45220 is the only relevant live process and remains untouched. These observations do not restart, resume, or copy r31.
- The implemented first-corruption chain now uses fixed reserved OCM input-reference and TX-readback storage rather than a large new automatic reference. It observes `INPUT_REF -> ENCODE_RAW -> ENCODE_REPAIR -> P6_TX_LOCAL -> P6_TX_MMIO_READBACK -> P6_RX_LOCAL -> RECEIVED -> DDR_OUTPUT_IMMEDIATE_READBACK -> DDR_OUTPUT_END_TO_END`, publishes only the first mismatch as a 320-byte committed P7CD record, and retains the older P7FS record only for CRC/SHA failures whose final input/output bytes compare equal. Raw encoder output is compared before the byte-copy hardening is allowed to rewrite it. This is diagnostic/hardening logic, not a confirmed root cause or hardware PASS.
- Critical local TX/RX/encoded/received storage is 256-byte physical capacity while the protocol maximum remains 247 bytes; each buffer is explicitly 64-byte aligned and guarded by compile-time offset/alignment assertions. Output files use a manifest-bound `0xA5` canary, the 30-byte boundary vector does not begin with zero, and a final deadline-aware byte comparison always binds DDR output back to the independent original input before success. The confirmed old offset-255 `rx_payload` layout remains an alignment hazard only, not a proven explanation of r31.
- Firmware publishes first-error identity, first differing offset/bytes, addresses and low-six address bits, CRC32/SHA256, and bounded snapshots with a magic/readback commit. The XSDB child now atomically captures and clears the fixed `0x00021000`/320-byte OCM region before trusting firmware address, length, status, marker, identity, digest, or geometry; parsing consumes the captured host file, and output cleanup remains timely. Python postprocessing independently reconstructs expected chunk/encoded/object bytes from the immutable input bundle and rejects marker, length, lane, fragment, digest, snapshot, wipe, or tamper mismatches.
- Focused P7CD codec/tamper/object-level tests, wrapper ordering/source-binding tests, regression-evidence dedup tests, Python compile checks, Tcl `info complete`, and diff checks pass. The 1000-case native matrix covers lengths 1--247, every source/destination mod-64 value, all 16 mod-4 pairs, `0xA5` canaries, buffer-base alignment, and driver argument limits. The exact r1--r31 history/tamper regression also passes; it does not promote any historical failure.
- A fresh real offline Vitis build passes without hardware. Candidate ELF SHA256 is `26f93c15b66be63bed6fa469edaed4578eab2cd64b58e9eeb4b447ebf952503c`; map SHA256 is `76fc4a82a46a5e7b2c52a997eaed7a1ee682e32cca71920cb855d92ca4d64825`; disassembly SHA256 is `ddbcbc17f26e117d75d3abc4c7c9b56fc79eb06cc43588f1e304166b6f59f1f3`; stack-evidence SHA256 is `7d3331e832966dd0937142149c74108214facd8aa95316e66e909bcc7ef3957a`. The linked OCM image ends at `0x00015830`, below `0x00020000`; `p7_process_descriptor` uses 2088/4096 bytes; the conservative diagnostic chain is 3608 bytes with 4584 bytes remaining; disassembly proves byte loads/stores, barrier, exact helper calls, and 14 first-error publication call sites. Build-summary SHA256 is `3a0b986600158c82f7cc7238d7f9b7d1dcece9875403cd6daba6288d116e985b`. All remain offline evidence with `HARDWARE_ACCEPTANCE=PENDING_HW`.
- The complete-suite optimization is now fail closed end to end. A shared validator binds the clean source commit before and after both canonical discoveries, exact commands/counts/return codes, immutable log paths/sizes/hashes, no-hardware/PENDING status, and exactly one invocation per suite. The canonical P7 gate passes the same validated summary into core readiness, which records zero new test invocations instead of rerunning `tests/p7`. Any validator/source change invalidates the summary. A pre-commit probe against the obsolete r31 regression summary correctly records readiness FAIL with only `p7_python_and_codec_tests=false`, cites the source/post-suite-clean binding errors, and records `invocation_count_in_core_gate=0`; it is not an authorization checkpoint.
- Before any hardware, accurately commit this source, machine build evidence, and handoff. On that new clean source, run each required complete suite exactly once, consume the path+SHA256 in one cache-bypassed canonical P7 gate, and only then generate r32 impact proof/plan and pass all authorization/dry validation. Because the ELF and wrapper/Tcl/core inputs changed, skipping 55--61 requires new complete transitive-input proof and otherwise fails closed from the earliest affected stage. r32 remains a new zero-coverage diagnostic with mandatory prefix, PENDING_HW, and no stage 66. The formal stationary run has still never started.

## 41. 2026-07-15 Campaign D specialist integration and main-thread resume

- The reviewed Campaign D package head is `73dc23a1ad95cddd06e7693dc1fa4fe3d629d648`; corrected AX7010 artifacts are rooted at `a7bc060aa29f15815891af463b1f7ff1d600cb31`, the bounded Stage 62 evidence-harvest fix is `6e8043716a6797257bbc46c172c287abed93198d`, and the Campaign D evidence commit is `1e6b5185cb1f0bdc2de0f148e715e1c726cb8b5e`. The main thread preserved its r32 handoff in `a473516635b3a138019b4f9d3ebef0e34c4613d2` and integrated the reviewed specialist tree without a merge as `38789d21f5bf3a3ba3b9256aa79562093a5d4018`.
- Campaign D run IDs `p7_20260714_ddr_external_campaign_d_01`, `_02`, and `_03` each passed original functional Stage 62. Aggregate evidence is boundary 144/144, 4 KiB 3/3, 64 KiB 12/12, 1 MiB 12/12, and 1275/1275 raw records hash-exact with no partial files. All three shutdown-after results passed. These runs are diagnostic-only, claim zero acceptance coverage, and leave `HARDWARE_ACCEPTANCE=PENDING_HW`.
- Main-thread cache-bypass Vivado and Vitis builds passed together with the complete generated AX7010 PS7/DDR contract. New immutable hashes are bitstream `c2995ac0b154467fb136fd2cad582da185850544086cf23dd4ec01cd47cda25a`, XSA `3e7eabda40a9936dd4e0bd3f7e55e4153aac48abdb8356493e13244916cdf57a`, ELF `51e1bc8342a88625d830274049dfeb91183e3c6d39dad3ca97a6081bd3e597bd`, map `9aefab06a1b76debea2c2dac95127f9b4579351670f3e456b2775b9f98f8a011`, and `ps7_init.tcl` `86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d`.
- A first fresh-worktree complete-suite checkpoint accurately failed two top-level tests because four pre-existing immutable bit/XSA files had remained ignored rather than packaged. No validator was changed. Commit `0b14e763a6955d627a14be81f04f0c5dfb3445b7` tracks those exact known-hash artifacts, the two focused failures then passed, and `stage62_handoff/return/MAIN_THREAD_INTEGRATION_PRECONDITION.json` preserves the failed checkpoint and repair evidence.
- On clean source `4bc49b1684be5eac655d75314f0da95e0bc1ffa8`, the required complete suites ran exactly once each and passed 185/185 plus 42/42; regression-summary SHA256 is `1b30923cfae5561c85a350c36c076f006452df1fb64d84984e586d7620b49b4a`. The canonical P7 gate then passed 13/13 with cache status BYPASS, real offline builds recorded, no hardware action, and summary SHA256 `8cae72c539f309bd58c59511dafcdf2e0a70525c341bcba265b5e76300803fcd`.
- Current exact markers are `STAGE62_DIAGNOSTIC_FUNCTIONAL_STREAK=PASS_3_OF_3`, `STAGE62_SPECIALIST_INTEGRATION=READY`, `SAFE_SHUTDOWN_COMPLETE=true`, and `HARDWARE_ACCEPTANCE=PENDING_HW`. Full-project, formal stages 1--66, stationary, Ethernet, motion, soak, and product-final PASS are not claimed. The 1800-second stationary stage has never started.
- The next original-goal step is preparation only: select a new formal run ID, create fresh scoped authorization bound to the integrated hashes, generate the complete stages 1--66 plan, and pass all dry validation. Do not reuse Campaign D authorization and do not launch hardware as part of this integration handoff.

## 42. 2026-07-15 r34 formal-prefix result and authorization-contract repair

- The formal run `p7_20260715_stationary_app_r34_formal_full` was launched once without `--resume` from exact source `4bc49b1684be5eac655d75314f0da95e0bc1ffa8`. Ledger SHA256 is `95b9678cee1d2cf4c89e32445f3cd2057487bca5c488f524b38f04f4f4771a27`. Stages 1--61 ended with exact PASS observations and shutdown-after PASS. Stage 62 ended `FAIL_STAGE`; stages 63--66 did not run, and the 1800-second stationary stage was never started. The run is immutable FAIL, claims no acceptance coverage, and must never be resumed, restarted, or copied.
- Stage 62 failed before the candidate bitstream or PS ELF started. Raw result SHA256 `12f402a54842cef9b778993015e93b5e57e7309fff3b363ea7cf0fcf2a069976` records `P7 authorization mismatch for P7_EXECUTION_SCOPE expected=P7_PS_APPLICATION_STAGE observed=`. The frozen authorization SHA256 `7ea880600d989768c208be8d118ed698896ab474f67473694f17e65b2805696c` contains neither `P7_EXECUTION_SCOPE` nor `P7_RUN_ID`, while the historical Tcl requires the expected scope and run ID `NONE`. This confirms a generator plus offline-validator authorization-contract gap; it is not a Stage 62 payload or DDR failure.
- Stage 62 shutdown-before and shutdown-after both passed. A separate recovery at `recovery_shutdown_after_failed_stage062_20260714T205916Z` also passed with summary SHA256 `0cddeed3f2afa59792504f65e8a8f7958dd9600bcad747978c6ff222fb8c3469`. Recovery PASS remains separate and does not promote stage 62 or r34.
- The original raw evidence remains at `C:\Users\user\.codex\worktrees\formalr33\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260715_stationary_app_r34_formal_full`: 1,373 files, 779,831,422 bytes, no partial files, canonical tree SHA256 `5939caafff8147a5f056046a382c161ec37293d49e3528be27469e459277cd6f`. A 30-file portable failure package is under `evidence/generated/p7_r34_failure_package`; its canonical tree SHA256 is `b0cac29abbcc155ab71b6376d9dbc268b7fa9d1b8e2fe479a3bfc8364dae1f07`.
- The generator now emits `P7_EXECUTION_SCOPE=P7_PS_APPLICATION_STAGE` and `P7_RUN_ID=NONE` for every normal PS stage. The PS safe wrapper now validates those two fields during offline child validation for normal and Stage62-only execution. Focused generator, wrapper, failure-package, and tamper tests pass 56/56. This is an offline repair only and is not hardware PASS.
- Before any new hardware, accurately commit the r34 package and repair, run each required complete suite exactly once on the resulting clean source, create a fresh cache-bypassed canonical checkpoint, and produce a new-ID plan with all dry validations. An adaptive diagnostic may skip 55--61 only if a machine-readable transitive-input proof passes; otherwise include the earliest affected stage. Diagnostic execution remains zero-coverage, PENDING_HW, and excludes stage 66. Final acceptance still requires a later new formal run of complete stages 1--66.

## 43. 2026-07-15 first post-r34 clean-source precondition failure

- Source `229299db9c6c5098d30ae5922508f4426546e665` was clean before and after the required complete-suite driver. The driver was invoked once, and each constituent suite was invoked exactly once. Top-level discovery ran 190 tests and returned FAIL with two failures and two errors; `tests/p7` passed 42/42. The regression summary SHA256 is `b23670d8655cbb3d66254387187237a2e9fb92ab7ceb9daf0c943dff12e066be`. No hardware action occurred and `HARDWARE_ACCEPTANCE` remains `PENDING_HW`.
- The first failure class is packaging, not a changed r34 fact: seven existing byte-exact `.log` files under `evidence/generated/p7_r34_failure_package` were ignored and absent from a fresh checkout, so the expected 30-file package appeared as 23 files. The source worktree retains the exact files; they are to be force-tracked without changing the package's 30-file, 2,781,609-byte canonical tree SHA256 `b0cac29abbcc155ab71b6376d9dbc268b7fa9d1b8e2fe479a3bfc8364dae1f07`.
- The second failure class is validation ordering: a fresh checkout did not yet contain ignored generated XCI, block-design, XSA, `ps7_init`, and Vitis platform/FSBL artifacts required by the real AX7010 board-contract test. The contract was not weakened or skipped. On the next new clean source, canonical real Vivado/Vitis outputs must be materialized before the once-only complete suites; the resulting regression summary must then be consumed by a cache-bypassed canonical gate without rerunning either complete suite.
- The exact failed summary and four suite logs are preserved under `evidence/generated/p7_r35prep_precondition_failure`, with portable tree SHA256 `21a8c986c61146369bed90fb79b277df29a52530bd318d5b28baf3a57cf3aac5`; the machine classification is `evidence/generated/p7_r35prep_precondition_failure.json`. Do not rerun the complete suites at source `229299db...`. Commit the package repair and this evidence, then use the resulting new clean source for the real-build, once-only suites, and cache-bypassed offline checkpoint. No new hardware run is ready or authorized.

## 44. 2026-07-15 post-r34 canonical-gate precondition failure

- Commit `7c6b50ff3450562b95c59029ec225f6d365541f9` fixed the portable r34 package and preserved the first failed suite checkpoint. Fresh cache-bypass P6 PS Vivado and P7 Vitis builds then passed without hardware; new build hashes are bitstream `2e1d225ff79bf182a1c13e81672950bc9ca5ac5e5bd3bafc18c89b294104bc8b`, XSA `8ecccf761142c853a3c5734b1c520a837e680d85aa183d131aa4f194b3d7ad7c`, ELF `07963f967f6dc4901e7c4ecb2f7d44a1d54976be5c95434299b610369b1e5ffe`, linker map `f40a6b00e807c22eebf06d0397a7d61858582c89735fa9499718c518fb202ed2`, and `ps7_init.tcl` `86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d`. The generated AX7010/Vitis board contract passed with zero errors.
- On that clean source, the required complete-suite driver ran once. Top-level discovery passed 191/191 and `tests/p7` passed 42/42, each invoked exactly once; summary SHA256 is `df0ce0d72558bacf97d1b8f01ed35b11cf7f2cbf1e108c79b8a3470ffecdcdad`. Source and worktree remained unchanged/clean, no hardware action occurred, and hardware acceptance stayed pending.
- The canonical gate consumed that exact summary without invoking either complete suite again, but accurately failed 12/13. The only false check was `P7_PS_CORE_HARDWARE_READINESS`; within it, the only false check was `stage62_only_microtest_bypasses_pl_and_is_disassembly_bound`. Gate-summary SHA256 is `c83b66a8e0325286045350647eb2c05e193d278c3122df42645f48065f859ffa`, and core-readiness SHA256 is `f3d3ded1ae57bac22f2ff9f89cce1513570889d9add6cff3fe1b86e04bf14c61`.
- Confirmed cause is static-contract representation, not payload, DDR, firmware, or hardware: the r34 normal-PS repair generalized Stage62-only and normal execution scopes into one conditional tuple, removing the explicit `("P7_EXECUTION_SCOPE", "STAGE62_ONLY")` literal required by the independent core-readiness gate. The wrapper now keeps explicit conditional tuples for `STAGE62_ONLY` and `P7_PS_APPLICATION_STAGE`, with branch tests for both. No check was skipped or weakened.
- Exact raw build, suite, board-contract, gate, and core-readiness evidence is preserved under `evidence/generated/p7_r35validate_7c6b50f_precondition`, canonical tree SHA256 `4e0b53a7dc9bf0bcde3587ddfbcfb3dc902673f6d65abc5e1d86d479d802419f`; the machine classification is `evidence/generated/p7_r35validate_7c6b50f_precondition.json`. Do not rerun complete suites at `7c6b50f...`. Commit the explicit tuple repair and fresh build artifacts, then use the resulting new clean source for one complete-suite invocation and a zero-duplicate canonical gate. Hardware remains blocked and stage 66 remains unstarted.

## 45. 2026-07-15 clean post-repair canonical checkpoint

- Commit `1d0c30fa7988acc0ae345cfec1c1917a56f07592` preserves explicit authorization tuples for both `STAGE62_ONLY` and `P7_PS_APPLICATION_STAGE`. The fresh cache-bypass build outputs from source `7c6b50ff3450562b95c59029ec225f6d365541f9` were materialized only as ignored complete-suite prerequisites after a fail-closed content/input proof showed no overlap with any P6 Vivado or P7 Vitis consumed source. Tool executables, all tracked build inputs, XCI/BD/XSA/`ps7_init`, ELF, map, BSP, and bitstream outputs were hash-revalidated. The proof SHA256 is `d0b3f390dc8404ebe70cec5ac61dad40001620a07bbb686f471ce48644469a78`; canonical offline cache-hit status was not claimed.
- The generated AX7010 PS7/DDR board contract passed with zero errors. The required complete-suite driver then ran exactly once on the clean source: top-level discovery passed 192/192 and `tests/p7` passed 42/42, each with invocation count one. The summary SHA256 is `5bb9560fae3b7439843ef8a788d1bde7621657f73d19880569476f9492d8e34a`; source and worktree stayed unchanged and clean.
- The canonical gate consumed that exact summary and did not invoke either complete suite again. All 13/13 checks passed, including PS core readiness and both explicit execution-scope contracts. Gate-summary SHA256 is `6a4c530c89668c98bf3d320e483928180816336bb109eab68752c93bd632bb98`; core-readiness SHA256 is `a5a796191553354b54fd8dc1785a76847b02bbc79a45b5bb3229107470a2d40b`. Cache status is BYPASS, no hardware action occurred, and `HARDWARE_ACCEPTANCE=PENDING_HW`.
- The exact 12-file checkpoint package is `evidence/generated/p7_r35validate_1d0c30f_checkpoint`, canonical tree SHA256 `1c3237869422d38921455d2dac44d694747855f4c97e503174ef0c8f35b07d1d`; its machine classification is `evidence/generated/p7_r35validate_1d0c30f_checkpoint.json`. r34 remains immutable FAIL and must never resume. No new run ID, authorization, or hardware process has been started, and stage 66 remains unstarted.
- The next action is preparation only: create a new diagnostic run ID, prove the adaptive suffix start from transitive inputs, generate new scoped authorization and immutable hashes, and pass every dry validator. The diagnostic must run its mandatory safety prefix, claim zero acceptance coverage, remain `PENDING_HW`, and exclude stage 66. Do not launch hardware from this checkpoint merely because offline gates pass.

## 46. 2026-07-15 r39 diagnostic suffix preparation

- The new unused run ID is `p7_20260715_stationary_app_r39_diag_suffix55`; r34 remains immutable FAIL and is not resumed, restarted, or copied. r35--r37 were already consumed by the Stage62 specialist and r38 was reserved by the offline DDR matrix, so r39 is the next collision-free main-thread ID.
- Adaptive selection failed closed at ordinal 55 rather than skipping directly to 62. Although r34 observed exact PASS at 55--61, the newly bound XSA changed from `3e7eabda...` to `8ecccf76...`, the ELF changed from `51e1bc83...` to `07963f96...`, the source commit changed, and the generated backend-manifest bytes changed. The machine decision is `evidence/generated/p7_r39_diag_suffix55_impact_decision.json`; therefore 55--61 are included and contribute no acceptance coverage.
- The exact diagnostic plan SHA256 is `fb44c68f2a740d43a143eff024a80450b3e803cfe2be7282f362f85aaa1fbc0f`. It contains 15 ordinals: `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`. It is `DIAGNOSTIC_ONLY`, `coverage_claimed=false`, `HARDWARE_ACCEPTANCE=PENDING_HW`, has zero stage 66/stationary entries, and binds no Ethernet, no motion, lane count two, max mask `0x3`, and shutdown-on-exit for every stage.
- The generator manifest SHA256 is `68f1081410df6f9513112cf1a3a59e690effda4837205acaa072234855943d6b`; all 15 child dry validations pass. The independent plan audit SHA256 is `ab5828880e503450b75be4f3d22360312346d13fe4edbbdd2bc35bc0bddf8b12`, and the separately invoked executor dry-validation SHA256 is `a9be4eca1cd5c029abf37733677292d5e6f4f3ffec5879a96318d7e245ff27d9`; both have zero errors and launched no process.
- The execution workspace remains source `1d0c30fa7988acc0ae345cfec1c1917a56f07592`. It has no non-generated tracked dirt; its 24 generated-summary modifications are the checkpoint's explicit allowed post-gate outputs. The r39 execution evidence root does not exist, `RF_COMM_HW_AUTH` is absent, no project Vivado/XSDB/runner process is active, and external legacy `hw_server` PID 45220 remains untouched.
- r39 is ready but not started. Readiness is not a hardware PASS and does not authorize stage 66. If the main thread later enters hardware execution, it must use only this exact plan through the sequence executor, without `--resume`, stop on the first failure, preserve raw evidence, perform independent recovery, retire r39, and use another new ID. Final acceptance still requires a later new formal run of complete stages 1--66, with the unique stationary launch only after that same run's 1--65 PASS.

## 47. 2026-07-15 r39 diagnostic Stage 64 failure and output-wipe repair

- `p7_20260715_stationary_app_r39_diag_suffix55` was launched exactly once from source `1d0c30fa7988acc0ae345cfec1c1917a56f07592`, using plan SHA256 `fb44c68f2a740d43a143eff024a80450b3e803cfe2be7282f362f85aaa1fbc0f` and without `--resume`. Its terminal ledger SHA256 is `f77a32c84f39a11bcf3b2e63738b7d491c8d2e823b2068bd979072c6a991e4f5`. r39 is immutable FAIL and must never be resumed, restarted, or copied.
- Ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63` reached terminal diagnostic PASS and each recorded shutdown-after PASS. These observations contribute zero acceptance coverage. Stage 62 completed its boundary and large-policy matrices and is a diagnostic PASS only. Stage 64 ended `FAIL_STAGE`; stage 65 did not run. The plan contained no stage 66, and the unique 1800-second stationary attempt count remains zero.
- The Stage 64 raw PS child returned zero and emitted `P7_PS_STAGE_RESULT=PASS` together with abort count one, abort shutdown result zero, interphase shutdown programmed, candidate reprogrammed, new epoch, replay rejected, and no requeue after cutoff. The outer wrapper correctly refused to promote that raw result: its exact postprocess failure is `slot 2: failed/aborted output was not atomically wiped`. The rejected duplicate-replay descriptor has status 6, error 19, zero completed bytes, and observed 1 MiB output SHA256 `16c7f1d8a38b4b84560e558ab03b13c82e2ff374d87eaacb4df22f03604e7a4f`, rather than the all-zero SHA256 `30e14955ebf1352266dc2ff8067e68104607e750abb9d3b36582b8af909fcb58`. Stage-summary SHA256 is `8749cac8523752abc7b59c5b611258ff5abfcad3d15252a0576bb0057e381102`; raw-manifest SHA256 is `e98b65280f7e13d7041898fa348bef9d8cac8047ac759cb003d29e0029213b64`.
- The confirmed defect is a validation-reject output-wipe gap, not a payload or DDR-corruption conclusion. Historical source SHA256 `d1ed23121305f657e44faa02548b16bafca92d973e793c43dbd8d3071277295a` validates every descriptor-controlled input/output/trace range and overlap before the stale-session and duplicate-object identity policies, but its validation-reject branch shuts down and publishes `REJECTED` without wiping the now-private output range. The source repair carries a `private_output_validated` bit from that exact structural boundary, performs shutdown first, wipes only a trusted private output, and then publishes the rejection. Structural address, geometry, or overlap rejection leaves the bit clear and remains write-free.
- The first independent recovery directory, timestamped `20260715T0052Z`, failed closed before hardware because the scoped P4 environment marker was absent. It records `NO_HARDWARE_ACTIONS_EXECUTED=1`; its four-file tree SHA256 is `a8509b07548839d9de07799bc8589401a5b4f8041c4599919786eed0042bf737`. A second new recovery directory, timestamped `20260715T0054Z`, was separately authorized and records `TFDU_SHUTDOWN_PROGRAMMED_SEEN=1`, `SHUTDOWN_EXIT=0`, and `PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS`; its six-file tree SHA256 is `8c8ef1845a47eff9c334b82cdc83916af9d9d81aaa0bf87b115a0ec738460ab6`. Recovery PASS remains separate and does not alter Stage 64 or r39.
- Original r39 evidence remains only in the validation worktree at `C:\Users\user\.codex\worktrees\r35validate_1d0c30f\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260715_stationary_app_r39_diag_suffix55`: 743 files, 796,712,508 bytes, zero partial files, canonical tree SHA256 `d8e77dde31fa229c08b84fb779e7a805e18e53f20522f7256824f4e9f32bd69f`. The 73-file portable package under `evidence/generated/p7_r39_failure_package` has 7,638,319 bytes, zero partial files, and canonical tree SHA256 `dbb1974da49b7be1efcc0c68f073a4ccf00fff024a9b3f7b44e92c0fc7056ef3`. Its historical-input manifest freezes 44 exact plan, authorization, checkpoint, build, profile, source, wrapper, recovery, and Stage 64 bundle records.
- A read-only replay of the historical summarizer produced a fail-closed aggregate output tree with SHA256 `75dec379a9a97a1db5b4464a9ea2fab18fc166d5a0ec1cff105f00dab57dd4d8`. The outer wait timed out before observing the child exit code, so no replay exit code is claimed; the child later completed, left no process, and its generated final summary is `FAIL`. Its shutdown summary remains PASS and its stationary summary remains `PENDING_HW`. `evidence/generated/p7_r39_summarizer_replay_result.json` records this distinction. The focused r39 package/history/tamper tests pass 7/7, the focused Stage 64 source/wrapper module passes 41/41, and the exact summarizer history/tamper module passes 16/16.
- External legacy `hw_server` PID 45220 remains the sole listener on port 3121 and was not touched. No project Vivado, XSDB, runner, or summarizer process remains. No Ethernet was used, no hardware was moved, and the maximum lane mask remained `0x3`.
- No new hardware is ready. First commit the r39 package, machine summaries, documentation, and source repair accurately. Then use the resulting new clean source for a fresh cache-bypassed Vitis build, the required complete suites exactly once, and a cache-bypassed canonical offline checkpoint consuming that suite evidence without duplication. Only after a new machine transitive-input impact proof, a new run ID (r40 or later), fresh scoped authorization, immutable hashes, and all dry validators pass may another diagnostic be considered. That diagnostic remains zero-coverage, `PENDING_HW`, mandatory-prefix, and excludes stage 66. Final acceptance still requires a later new formal run of complete stages 1--66, with the sole stationary launch only after the same formal run's stages 1--65 pass.

## 48. 2026-07-15 first post-r39 canonical-gate precondition failure

- Fresh cache-bypass P6/Vitis artifacts were committed as `5a99b98c7cbe91d76ad22721c057b6edfb31e1c1`; bitstream SHA256 is `bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868`, XSA is `3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8`, ELF is `d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da`, and map is `a282a162efff2d7d1fdef7abf32774659cb1b2448050cc95887e0aea3fa5ebde`. A hash-exact materialization proof and generated board contract passed with no hardware.
- On clean source `5a99b98c...`, required suites passed 199/199 plus 42/42 exactly once, but the canonical gate failed 12/13. The sole false core check searched for the first `p7_wipe_partial` in the whole process function, so the newly added validation-reject wipe before `failed:` shadowed the later integrity-failure-path wipe. The actual integrity path remained snapshot publication -> `failed:` -> path-local wipe. The same source was not rerun. Exact 12-file failure evidence is under `evidence/generated/p7_r40validate_5a99b98_precondition_failure`, tree SHA256 `65209b5b7484e639a95cee900c4684aa445dcf2f8b555535bc482c343a67f32a`.
- The checker now verifies ordered path tokens beginning at snapshot publication, with focused positive and missing-post-label-wipe negatives. This is a static gate repair, not a hardware, DDR, or payload finding.

## 49. 2026-07-15 post-checker complete-suite precondition failure

- Commit `6999166b89fdf57a79b291992eebb47e09762cf4` preserved the first gate failure byte-exactly and the scoped checker repair. Its clean required-suite invocation was not rerun: `tests/p7` passed 42/42, while top-level discovery failed one of 201 tests because `evidence/generated/p7_r39_diagnostic_failure.json` still bound the old current checker SHA256. Canonical gate was not run.
- The exact nine-file failure package is `evidence/generated/p7_r40validate_6999166_suite_failure`, tree SHA256 `0eb20ae5a628d4558f4fa26ac94d69020a7328ebea1ca2cb429aa435cc44413d`. The r39 ledger, raw package, immutable FAIL, and hardware conclusions were unchanged. Only the current checker SHA binding was updated to `a9d1191f26608d512c96dcfe67a792c82e953576b1da7257a7aacba250793d71`; focused r39 package and checker tests passed.

## 50. 2026-07-15 clean post-r39 canonical checkpoint

- Clean source `37182768047dc4afdc18699a1142852418b382b5` revalidated every P6/Vitis consumed input, tool executable, XCI/BD/XSA/`ps7_init`, BSP, bitstream, ELF, map, and copied build-tree byte. The 51 changed paths since the fresh build source have zero consumed-input overlap. Final materialization proof SHA256 is `349f20dcf6d2bacae028fba49893f6d2f435268483350e2cade03084e920505b`; no canonical cache hit is claimed, and the generated AX7010 board contract passed with zero errors.
- Required suites ran exactly once on that source and passed 201/201 plus 42/42; summary SHA256 is `1f397f78c5325271015d19b623090fe56c432ed62329a7501e1b67beae4cbb85`. The canonical gate consumed that summary with zero duplicate suite invocations and passed 13/13. Gate SHA256 is `cf6a6d6c839f1e0251279964f5b73b56967f5440e3687253fb78b149ea0886a5`; core-readiness SHA256 is `c3961b381bb7f9276064f7220908640b7969bdbd02dfb877ad5453095b616d5d`. No hardware action occurred and `HARDWARE_ACCEPTANCE=PENDING_HW`.
- The exact 12-file checkpoint is `evidence/generated/p7_r40validate_3718276_checkpoint`, canonical tree SHA256 `cf6fc3176e2801ae56e8cb40bd769bf9a7910219aacef17d42dec0c6a86a8955`; its machine classification is `evidence/generated/p7_r40validate_3718276_checkpoint.json`. Campaign D remains diagnostic Stage 62 PASS 3/3 with zero acceptance coverage. r39 remains immutable FAIL and cannot resume. No r40 plan, authorization, hardware execution, or stage 66 attempt exists.
- The next action is preparation only: choose a new diagnostic run ID, run the mandatory safety prefix, prove the earliest affected suffix from complete transitive inputs, generate fresh scoped authorization and immutable hashes, and pass every dry validator. The diagnostic remains zero-coverage, `PENDING_HW`, no Ethernet, no motion, lane mask at most `0x3`, and excludes stage 66. A later formal run must still execute complete stages 1--66, with the sole stationary attempt only after the same run's stages 1--65 pass.

## 51. 2026-07-15 r40 diagnostic suffix preparation

- The new unused run ID is `p7_20260715_stationary_app_r40_diag_suffix55`; r39 remains immutable FAIL and is not resumed, restarted, or copied. The exact execution source is the clean checkpoint commit `37182768047dc4afdc18699a1142852418b382b5` in `C:\Users\user\.codex\worktrees\r40validate_3718276\RF_COMM_MULTILANE`.
- The machine selection considered ordinal 64 because r39 passed 55--63 and failed 64, but failed closed to ordinal 55. The stage-55 safe-wrapper authorization closure changed source commit, XSA `8ecccf76...` to `3e9e3382...`, and ELF `07963f96...` to `d47f28ff...`; the PS bitstream also changed from `2e1d225f...` to `bd9bce92...`. Therefore no unchanged-transitive-input proof can justify skipping 55--63. The pre-plan selection SHA256 is `c407ff7b6d88e831a3089ae52243f3225fb4e73a7649c63d696c9df4d5007fcf`; the final decision SHA256 is `c4a1edb64463539196d4ef709d8992d673c3198439dfe625968d8b5352eb616a`.
- The exact plan SHA256 is `27de005c49a34c2d663b596ab94ef415c6cdbe5a4e5086c79d6c19a127803b0e`. It contains the mandatory prefix and suffix ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65`. It is `DIAGNOSTIC_ONLY`, `coverage_claimed=false`, `HARDWARE_ACCEPTANCE=PENDING_HW`, contains no `--resume`, and has zero stage 66 or stationary entries.
- Fifteen fresh scoped authorization records bind source `37182768...`, the current immutable bitstream/XSA/ELF/profile/configuration hashes, no Ethernet, no motion, lane count two, maximum mask `0x3`, and shutdown-on-exit. Their canonical tree SHA256 is `f6499f05b1fedc064f46d34c277a5d81eedfec75ee3dd10a63ebf144af5eaaba`.
- Generator manifest SHA256 is `7d018b337541f09930bff78e4f072e6be0e55b4e1df390d43f3b4c94d05cc39d`; all 15 child wrapper dry validations have zero errors. Independent plan-audit SHA256 is `c37418034b396ac66a1f3eaba1a608c8453aa91d2f7cb0162204dc51a6bf96f5`; separately invoked executor dry-validation SHA256 is `579248bc8412df09f009669e60d6247589e7a7664549d09df54f6ed38528e430`. Final preparation selfcheck SHA256 is `3a402d2ac23b556292a8adfd38aff1f14ebf8bc6320c03dc875f6d8ce8744edf`. Neither generation nor validation launched Vivado, XSDB, a safe wrapper, or hardware.
- The r40 evidence root does not exist, `RF_COMM_HW_AUTH` is absent, and no project hardware process is active. External legacy `hw_server` PID 45220 remains the sole port-3121 listener and was not touched. r40 is ready but not started; this is preparation evidence, not hardware or acceptance PASS.
- If execution is entered, use only the exact plan from the bound source workspace, without `--resume`, and stop on the first failure. Preserve raw evidence, run independent shutdown recovery if needed, retire r40 after any failure, and use a new ID. The diagnostic contributes zero acceptance coverage and cannot run stage 66. Final acceptance still requires a later new formal run of complete stages 1--66, with the sole stationary attempt only after same-run stages 1--65 pass.

## 52. 2026-07-15 r40 diagnostic suffix terminal PASS and evidence freeze

- `p7_20260715_stationary_app_r40_diag_suffix55` was launched exactly once from source `37182768047dc4afdc18699a1142852418b382b5`, using exact plan SHA256 `27de005c49a34c2d663b596ab94ef415c6cdbe5a4e5086c79d6c19a127803b0e` and no `--resume`. It is now completed and must never be reused or resumed.
- Terminal ledger SHA256 is `756c83030a6224b0381b7a90f0bf9085e3fe59eebe09957a9b68008ae9ca77a5`. Its status is `DIAGNOSTIC_PASS`; all 15 ordinals `1,2,3,4,55,56,57,58,59,60,61,62,63,64,65` are terminal PASS, every child return code is zero, all child process trees are reaped, all containment is closed, and no descendant remains. Stage 66 is absent and the stationary attempt count is zero.
- Every stage records shutdown-before and shutdown-after attempted, programming attempted, return code zero, exact shutdown artifact SHA256 `bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810`, and PASS. Because the final stage also completed its normal shutdown-after barrier, independent recovery was neither required nor run. `SAFE_SHUTDOWN_COMPLETE=true`.
- The outer monitor observed tool-cell exit code zero, but its separate PowerShell `Start-Process` exit-code field was blank. No executor process exit code is inferred or claimed. The exact executor stdout records `P7_AUTHORIZED_HARDWARE_SEQUENCE=DIAGNOSTIC_PASS`, zero validation errors, zero coverage, and `HARDWARE_ACCEPTANCE=PENDING_HW`; its stderr is zero bytes. This distinction is frozen in `executor/outer_monitor_observation.json` inside the portable package.
- The original raw evidence root remains only in `C:\Users\user\.codex\worktrees\r40validate_3718276\RF_COMM_MULTILANE\evidence\hardware\p7\authorized_sequence\p7_20260715_stationary_app_r40_diag_suffix55`: 836 files, 797,132,623 bytes, zero `.partial` files, canonical tree SHA256 `2702bb0019ddb5899a82c6aa8d6eea775612168a8e0d4d962f0c5fee0db270a2`. Do not mutate, resume, restart, or copy this run as another run ID.
- The portable package is `evidence/generated/p7_r40_diagnostic_pass_package`: 129 files, 60,394,279 bytes, zero partial files, canonical tree SHA256 `c66d889d6d6e46a22a83b897284b689c064500a218962b1ab3e1d34a9c0e2570`. It contains the exact ledger, a content-addressed manifest for all 836 original files, lossless deterministic archives of all 15 stage summaries and raw result logs, direct shutdown/preflight/raw-manifest records, executor logs, and 69 frozen authorization/checkpoint/source/tool/configuration/artifact inputs. Machine classification is `evidence/generated/p7_r40_diagnostic_pass.json`, SHA256 `28aa31bcc122e65e3269dc6030f815a542190fee252434fc8bd8d08585371d9e`.
- The historical formal-acceptance summarizer was run offline exactly once over only the r40 diagnostic suffix. It exited 1 and accurately failed closed because a diagnostic suffix is not a complete formal 1--66 run; the generated shutdown result is PASS and stationary is `PENDING_HW`. The 72-file replay tree SHA256 is `d8d69008655da29dbdfd74a178cd8ee65724ac68a8678ec60f1f8785b649f5c8`, and `evidence/generated/p7_r40_summarizer_replay_result.json` preserves the interpretation. Aggregate formal-summary FAIL is not an r40 stage failure and must not replace the exact ledger result.
- Focused package, history, archive, shutdown, tamper, outer-observation, and summarizer tests pass 9/9; machine-record SHA256 is `eebed533fb20df4f214f2e198dbc277512c340702ced1bbf9fb09c875418dcf8`. No complete suite or canonical gate was repeated on source `3718276...`; its earlier exactly-once 201/201 plus 42/42 suites and 13/13 gate remain the bound pre-run checkpoint evidence.
- No Ethernet was used, no hardware was moved, lane count remained two with max mask `0x3`, `RF_COMM_HW_AUTH` and the project lock are absent after the run, no project hardware process remains, and external `hw_server` PID 45220 remains the sole port-3121 listener and was not touched.
- r40 contributes zero acceptance coverage and remains `HARDWARE_ACCEPTANCE=PENDING_HW`. The next allowed work is non-hardware: accurately commit this evidence, create a new clean source checkpoint, invoke each required complete suite exactly once, run a cache-bypassed canonical gate, then create a new formal run ID, complete stages 1--66 plan, fresh scoped authorization, immutable hashes, and all dry validations. Only that new formal run may start the unique 1800-second stationary stage, after its own stages 1--65 pass. Do not reuse Campaign D, r39, or r40 authorization.

## 53. 2026-07-15 post-r40 clean formal-preparation checkpoint

- A fresh checkout of source `680f0c7e31a9ae62cbfb7ac01a04e917eafb874a` exposed a package-portability precondition failure: 12 objects already listed in the immutable r40 package manifest were ignored and absent from the Git tree, so focused package tests passed 6/9. The original main-worktree copies were present and hash-exact; commit `1daa8920919617a3b5e5e118f0ee0ab84868baaf` force-tracks those exact bytes without repackaging or changing r40. The failed source was not rerun.
- The required suite driver at source `1daa8920...` was accidentally interrupted by a 1000 ms outer executor timeout before it emitted a summary or logs. No residual process remained, the source was retired in `9cbea83c7881b668e35c28250dada7501ef49706`, and the driver was not rerun at that source. The next clean source `9cbea83c...` completed the driver once: top-level discovery was 209/210 and `tests/p7` was 42/42. The sole failure was the real AX7010 board-contract test because nine ignored generated XCI/BD/XSA/`ps7_init` prerequisites had not yet been materialized. Canonical gate was not run, the source was retired in `b6a934de6660d18d3a37358010847872f5fd05b1`, and exact evidence is under `evidence/generated/p7_r41validate_9cbea83_suite_failure`, tree SHA256 `7afef9afb0d542e00fe323bbef55e7653fc79ce68ee6b3bfd3c993843708dd37`.
- Fresh cache-bypassed P6 PS Vivado and P7 Vitis builds then passed from `b6a934de...`, and the exact build tree was frozen as `18661fc24bdb580e7ff2c645aa674bf7c2dc2e4a` and integrated byte-identically as main commit `946ccbad66d64d715ad6745449b95f6c261ddf76`; both resolve to tree `d05bb9d85868b380800e37c94388a43dc6092347`. Vivado timing and DRC passed, the generated AX7010 board contract passed, and no hardware action occurred. Current hashes are P6 PS bitstream `532b60778cea34f1ec12c8961b5ad34a0a632cd00d5c13c6c2d81f2dcab576b0`, XSA `e796b4ae0832e081c34497354262f3e17e71c9ed6162a02fa4150a06103b2df1`, P7 ELF `3a7c63a9918bf53e6232cda98bda5597298a215aa0e860fcc439a5f627ee1644`, linker map `0ec32b6d5828ab9f1061a6a1157962a4c74f1e0a3f25c679560e7fa0730a096b`, `ps7_init.tcl` `86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d`, and `ps7_init.c` `6196821e87f973e6b2aaca7ff96187c49a78fa2e43020c69e1a16a2c8d9bea34`.
- At exact clean source `946ccbad...`, the nine ignored board-contract prerequisites were materialized only after a hash-exact, tool-bound, equal-tree proof. Proof SHA256 is `0dc8fd72ae71087954c8c52f691c3fb2ab8d9352b0e7529861b40d7d15ca7338`; no canonical cache hit is claimed. The required complete-suite driver ran exactly once and passed 210/210 plus 42/42, each invocation count one; summary SHA256 is `83f878f3f374cf59504b4b9d87d7d2b512c0ea7e45316ef7ce480347662ee3d8`. Source and tracked worktree stayed unchanged and clean.
- The canonical gate consumed that exact regression summary with no duplicate complete-suite invocation and passed 13/13. Gate-summary SHA256 is `85358dd1d4069f4953b2c205bcbb87680b7a45bdda3203f22f0e835a28cd946a`; PS-core readiness passed 40/40 with SHA256 `a55f0e7d4c62c82403c117cbddf2c5686d86e47bade0b8ca4193ecb5178524d6`; cache status is BYPASS and a real build had run. The exact 12-file checkpoint package is `evidence/generated/p7_r41validate_946ccba_checkpoint`, 119,473 bytes, canonical tree SHA256 `944366420fba2f8fffc63ca59c8ab0bad827c30e828e3b7808ae5464f181a8fe`; its machine classification is `evidence/generated/p7_r41validate_946ccba_checkpoint.json`.
- Campaign D remains diagnostic Stage 62 PASS 3/3 with zero acceptance coverage; r40 remains a completed diagnostic-only run that cannot be reused or resumed. No new formal run ID, plan, authorization, hardware launch, or stage 66 attempt exists. `HARDWARE_ACCEPTANCE=PENDING_HW`. The next step is preparation only: create a collision-free formal full-run ID at exact source `946ccbad...`, generate stages 1--66 and fresh scoped authorization, bind current immutable artifacts, and pass all dry validators before considering any launch. The unique stationary stage remains unstarted and may execute only after stages 1--65 pass in that same new formal run.
