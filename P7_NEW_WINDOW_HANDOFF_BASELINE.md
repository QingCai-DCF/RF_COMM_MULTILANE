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
