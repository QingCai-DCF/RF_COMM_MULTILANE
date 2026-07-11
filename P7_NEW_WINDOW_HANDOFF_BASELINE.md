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
