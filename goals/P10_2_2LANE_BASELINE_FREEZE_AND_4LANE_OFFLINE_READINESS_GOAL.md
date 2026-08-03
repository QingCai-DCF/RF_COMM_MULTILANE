# RF_COMM_MULTILANE — P10.2 2-Lane 基线冻结与 4-Lane 离线就绪 Goal

## 不执行 2 小时测试；完成 P10.1R 收口、4-Lane 参数化、接线/供电/性能/测试包与未来硬件验收准备

```text
DOCUMENT_TYPE:
CODEX_EXECUTION_GOAL

STAGE:
P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS

STAGE_CLASS:
POST_P10_1R_CLOSEOUT_AND_4LANE_OFFLINE_SCALEOUT

NO_2H_QUALIFICATION:
true

NO_NEW_HARDWARE_ACTIONS:
true

CURRENT_RUN_HARDWARE_AUTHORIZATION:
false

HARDWARE_ACTIONS_ALLOWED:
false

P10_1R_ACCEPTED_SCOPE:
DUAL_AX7020_STATIONARY_2LANE_SPEED_STABILITY_PASS

P10_1R_SOURCE_COMMIT:
39df17155ce82e38366fbdac00c79584f0fe1afa

P10_1R_EVIDENCE_CHECKPOINT:
9321ca2f1797eb12bfb02848c3ee27145e1e8eb4

P10_1R_PASS_TAG:
p10.1r-2lane-speed-stability-pass

P10_1R_EXPECTED_CLOSEOUT_TAG:
p10.1r-2lane-speed-stability-closed

RECOMMENDED_BRANCH:
p10.2/4lane-offline-readiness

RECOMMENDED_WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_2

CURRENT_2LANE_ENDPOINTS:
AX7020-F/JTAG:210249855178
AX7020-R/JTAG:210512180081

CURRENT_2LANE_TOPOLOGY:
lane0 = F0 <-> R0
lane1 = F1 <-> R1

FUTURE_4LANE_TOPOLOGY:
lane0 = F0 <-> R0
lane1 = F1 <-> R1
lane2 = F2 <-> R2
lane3 = F3 <-> R3

FUTURE_MODULE_COUNT:
8 total
4 per endpoint

FUTURE_ALLOWED_LANE_MASKS:
0x1 through 0xF

FUTURE_MAX_LANE_MASK:
0xF

FUTURE_4LANE_RAW_CAPABILITY:
16 Mbit/s aggregate

FUTURE_4LANE_APPLICATION_GOODPUT_HARD_TARGET:
>= 8.0 Mbit/s per tested half-duplex direction

FUTURE_4LANE_APPLICATION_GOODPUT_STRETCH:
>= 9.6 Mbit/s per tested half-duplex direction

EXPECTED_NEXT_STAGE:
P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_ONLY_AFTER_PHYSICAL_WIRING_AND_NEW_AUTHORIZATION
```

本 Goal 直接交给 Codex 执行。Codex 必须实际完成：

```text
P10.1R immutable PASS 收口
旧授权消费和机器状态关闭
模块库存与旧 F1 隔离
mainline 同步
新 P10.2 worktree
2-lane 回归基线冻结
4-lane board profile、pinmap、XDC 和 wiring proposal
4-lane RTL/协议/软件参数化
8 个物理模块安全和 echo-admission 模型
4-lane 调度、降级和性能模型
4-lane 双端数字仿真
两端 AX7020 综合、实现、时序、CDC 和资源审计
4-lane 供电/电流/去耦设计输入
未来 4-lane hardware runner 的 fail-closed dry-run
P10.3 运行手册、验收矩阵和 evidence schema
机器状态、需求追踪、evidence、source/checkpoint/tag
```

本 Goal **不执行**：

```text
2 小时静止运行
任何新的 2-lane 硬件运行
任何 4-lane 硬件运行
hw_server / JTAG / program FPGA / PS ELF
UART / ILA / VIO / 真实 DMA
TFDU 发射
Ethernet
SPI
旋转
ABZ
P11 handover
```

---

# 1. 当前 2-Lane 基线

P10.1R 已完成并必须保留：

```text
2-LANE FUNCTION: PASS
2-LANE 4 Mbit/s PHY PER LANE: PASS
2-LANE APPLICATION GOODPUT >=4 Mbit/s/DIRECTION: PASS
2-LANE 64 MiB STREAMING: PASS
2-LANE 30-MINUTE STABILITY: PASS
SAME-MODULE RAW ECHO OBSERVABLE: PASS
SAME-MODULE ACCEPTED DATA ZERO: PASS
CROSS-LANE ACCEPTED DATA ZERO: PASS
SHUTDOWN_FIXED: PASS
SHUTDOWN_ROTATING: PASS
```

关键已接受数值：

```text
300-second F→R:
约 4.502 Mbit/s

300-second R→F:
约 4.502 Mbit/s

30-minute formal F→R:
约 4.154 Mbit/s

30-minute formal R→F:
约 4.154 Mbit/s

5 × 64 MiB F→R:
PASS

5 × 64 MiB R→F:
PASS

same-module raw echo:
非零、保留观测

same-module accepted DATA:
0

cross-lane accepted DATA:
0

CRC/SHA/partial/duplicate/stale/retry-exhausted/descriptor leak/deadlock/safety violation:
0
```

P10.2 不得重新解释、重写或删除这些 evidence。

---

# 2. 当前保留问题

P10.2 必须记录并处理以下非硬件问题：

```text
1. P10.1R current-run authorization 必须保持 false；
2. PROJECT_STATUS.md 中不得残留“partial result does not create PASS”等旧文本；
3. 旧故障 F1 小板不能计入已接受模块库存；
4. replacement F1 必须有 accepted inventory identity；
5. ACK wait ratio 的旧命名语义不适合作为独立 idle 比例；
6. application ceiling/model 与实测口径需要统一；
7. local-source rejection 的第二道防御尚未直接触发；
8. 外部 Txd/SD/VCC2/duty 测量仍为 PENDING；
9. physical GLOBAL_PERMIT 仍为 PENDING_D17；
10. P11 仍为 NOT_STARTED。
```

---

# 3. 开始位置和 Git 发现

从主工作树启动 Codex：

```text
C:\Users\user\Documents\RF_COMM_MULTILANE
```

Codex 必须先发现：

```text
P10.1R branch
P10.1R worktree
P10.1R pass tag
P10.1R source commit
P10.1R evidence checkpoint
main HEAD
remote refs
```

运行只读审计：

```powershell
git worktree list --porcelain
git branch -vv --all
git tag --list
git log --graph --decorate --oneline --all --date-order -n 200
git status --short --branch
git cat-file -t p10.1r-2lane-speed-stability-pass
git rev-list -n 1 p10.1r-2lane-speed-stability-pass
```

必须验证：

```text
P10.1R pass tag 是 annotated tag
tag target = 9321ca2f1797eb12bfb02848c3ee27145e1e8eb4
source commit 是 tag target 的祖先
P10.1R worktree clean
P10.1R frozen evidence 可 verify-existing
```

生成：

```text
evidence/generated/p10_2_repo_discovery.md
evidence/generated/p10_2_repo_discovery.json
```

若上述身份不成立：

```text
P10_2: FAIL_CLOSED
```

不得继续 closeout 或创建 4-lane branch。

---

# 4. P10.1R 纯离线收口

## 4.1 不修改冻结历史

不得修改：

```text
P10.1R raw hardware evidence
P10.1R artifact manifest
P10.1R authorization原文
P10.1R pass tag
P10.1R evidence checkpoint
失败和更早阶段 evidence
```

所有修正通过 pass checkpoint 之后的新 commit 完成。

## 4.2 授权关闭

确保：

```text
current_run_hardware_authorization: false
last_hardware_authorization_consumed: true
last_hardware_stage: P10_1R
last_hardware_evidence_checkpoint: 9321ca2f...
last_shutdown_fixed: PASS
last_shutdown_rotating: PASS
```

未来运行不得复用 P10.1R authorization file。

## 4.3 状态文本修复

重新生成：

```text
PROJECT_STATUS.md
```

必须移除与最终 PASS 冲突的旧 partial 描述。

正确状态至少：

```text
p10_1r_status: PASS
two_lane_speed_stability: PASS
p11_status: NOT_STARTED
p11_hardware_ready: false
current_run_hardware_authorization: false
```

## 4.4 Git checkpoint metadata

生成：

```text
evidence/generated/p10_1r_closeout_summary.md
evidence/generated/p10_1r_closeout_summary.json
evidence/generated/p10_1r_git_checkpoint_metadata.json
```

记录：

```text
source commit
evidence checkpoint
pass tag object和target
formal run ID
fixed/rotating board IDs
bitstream/ELF hashes
wiring hash
module inventory hash
evidence manifest hash
shutdown
authorization consumed
```

## 4.5 关闭标签

若不存在，创建：

```text
p10.1r-2lane-speed-stability-closed
```

annotated tag 指向新的 closeout commit。

不得移动 pass tag。

## 4.6 Mainline

安全将 closed baseline 合入或 fast-forward 到 main。

如果不能 fast-forward：

```text
创建临时 integration branch
不 rebase 冻结历史
解决 state/status/requirements 冲突
运行 verify-existing
```

P10.2 必须从包含 closed baseline 的 main 创建。

---

# 5. 模块库存与隔离

创建：

```text
config/hardware/tfdu_module_inventory.yaml
docs/hardware/TFDU_MODULE_INVENTORY.md
```

最低状态：

```text
F0:
ACCEPTED_P10_1R

F1_REPLACEMENT:
ACCEPTED_P10_1R

R0:
ACCEPTED_P10_1R

R1:
ACCEPTED_P10_1R

F1_ORIGINAL:
QUARANTINED_NOT_ACCEPTED
```

每个模块记录：

```text
module ID
PCB revision
TFDU marking/lot if available
endpoint
position
accepted stage
accepted run ID
known failures
replacement history
inventory status
```

未来新增模块：

```text
F2
F3
R2
R3
```

初始状态：

```text
PENDING_PHYSICAL_INVENTORY
PENDING_PINOUT_CHECK
PENDING_SAFE_IDLE
PENDING_RAW_ACCEPTANCE
```

禁止把旧 F1 原板作为 F2/F3/R2/R3 之一。

生成模块标签和接线标签模板：

```text
docs/hardware/P10_2_MODULE_LABELS.md
```

---

# 6. 创建 P10.2 worktree

从最新 clean main 创建：

```text
WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_2

BRANCH:
p10.2/4lane-offline-readiness
```

命令：

```powershell
git worktree add `
  -b p10.2/4lane-offline-readiness `
  C:\Users\user\Documents\RF_COMM_MULTILANE_P10_2 `
  main
```

若已存在：

```text
不删除
验证branch、HEAD、base、clean状态
```

从此所有 P10.2 修改只在 P10.2 worktree 中进行。

---

# 7. 4-Lane 目标拓扑

P10.2 的未来硬件拓扑固定为：

```text
AX7020-F:
F0
F1
F2
F3

AX7020-R:
R0
R1
R2
R3
```

logical lane：

```text
lane0:
F0 <-> R0

lane1:
F1 <-> R1

lane2:
F2 <-> R2

lane3:
F3 <-> R3
```

本阶段只准备静止 4-lane 半双工。

不包含：

```text
4 fixed + 1 rotating handover
ABZ
旋转
2+2 full-duplex验收
P11
```

---

# 8. 4-Lane 板级 I/O 和接线准备

## 8.1 现有接线保持

当前通过 P10.1R 的：

```text
F0/F1/R0/R1
```

信号和 pin 默认保持不变。

不得为了加入 lane2/3 无理由重接 lane0/1。

如果 I/O 资源冲突导致必须移动既有 pin：

```text
标记 BREAKING_WIRING_CHANGE
不得静默修改
输出原因和迁移风险
```

## 8.2 每板信号预算

四个 TFDU 每板至少：

```text
4 × Txd outputs
4 × Rxd inputs
4 × SD outputs
4 × Mode controls或明确strap
= 16 PL signals per endpoint
```

另需审计：

```text
GLOBAL_PERMIT
fault/status
debug
UART/JTAG保持
未来测量trigger
```

## 8.3 Pin选择要求

Codex 必须根据 AX7020 官方资料检查：

```text
PL connector
FPGA package pin
I/O bank
VCCO
IOSTANDARD
现有板载外设冲突
on-board pull
power-up behavior
输入/输出方向
clock/config专用资源
```

不得：

```text
复用Z7010 XDC
猜测pin
把PS MIO当PL pin
使用电压不兼容bank
```

## 8.4 Wiring proposal

生成：

```text
docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md
config/hardware/p10_2_ax7020_4lane_wiring.yaml
```

每根线记录：

| Endpoint | Module | Signal | FPGA direction | Connector | Connector pin | FPGA package pin | Bank | VCCO | IOSTANDARD | Default | Pull | Source |
|---|---|---|---|---|---|---|---|---|---|---|---|---|

包括：

```text
F0..F3
R0..R3
Txd/Rxd/SD/Mode/VCC/GND
```

输出：

```text
WIRING_PROPOSAL_SHA256
PINMAP_SHA256
BOARD_DOCUMENT_SET_SHA256
```

## 8.5 物理布置指南

生成：

```text
docs/hardware/P10_2_4LANE_PHYSICAL_LAYOUT_GUIDE.md
```

至少包含：

```text
模块标签
lane配对
模块朝向
线束编号
GND回路
供电分组
避免遮挡
formal run期间不得改变位置
接线必须断电
上电前检查
```

本 Goal 完成后，用户按该 wiring proposal 布置硬件。

---

# 9. 4-Lane board profiles

建立：

```text
board_profiles/ax7020_fixed_4lane/
board_profiles/ax7020_rotating_4lane/
```

至少包含：

```text
profile.yaml
pinmap.csv
ACTIVE_PROFILE.json或role-specific equivalent
generated XDC
board identity
exact part
clock/reset
DDR/PS preset
node role
module count
lane count
lane mask width
register-map version
```

固定参数：

```text
LANE_COUNT=4
PHYSICAL_MODULE_COUNT=4 per endpoint
MAX_LANE_MASK=0xF
```

保持 2-lane profiles 不变：

```text
ax7020_fixed_2lane
ax7020_rotating_2lane
```

---

# 10. 4-Lane RTL 参数化审计

扫描并移除 2-lane 硬编码：

```text
2-bit lane mask
0x3 hardcode
lane[1:0]
固定两个scheduler slot
两个counter
两个module admission state
固定F0/F1/R0/R1枚举
```

核心 RTL 必须支持：

```text
LANE_COUNT=2
LANE_COUNT=4
未来LANE_COUNT=8
```

允许 board wrapper 根据 profile裁剪。

不得复制新的 4-lane protocol fork。

---

# 11. 8 个物理模块安全扩展

未来 4-lane 系统共有：

```text
4 fixed endpoint physical modules
4 rotating-role endpoint physical modules
```

每个物理模块独立保持：

```text
exact 1 ms sliding duty
design target <=18%
hard limit <20%
continuous Txd HIGH <=1 us
startup >=500 us
per-module TX/RX frame-admission exclusion
same-module raw echo observable
same-module accepted DATA=0
local-source rejection
```

每端点仍只有：

```text
1 × local active-high GLOBAL_PERMIT
```

禁止：

```text
per-lane GLOBAL_PERMIT
per-module GLOBAL_PERMIT
permit heartbeat
双permit
```

增加 4-lane assertions：

```text
module TX/RX overlap=0
TX lane i only blanks RX admission of module i
其他3 lanes不被blank
same-module accepted DATA=0
cross-lane accepted DATA=0 in model
```

---

# 12. 4-Lane Echo/Crosstalk 模型

未来共有：

```text
8 TX sources
8 RX observations
```

建立 8×8 矩阵模型：

```text
TX_F0..TX_F3
TX_R0..TX_R3

RX_F0..RX_F3
RX_R0..RX_R3
```

模型覆盖：

```text
same-module echo
remote target path
same-endpoint cross-lane
remote non-target cross-lane
同时4-lane发射
echo delay/tail/jitter
反射tail
```

离线硬门：

```text
same-module raw pulse可见
same-module accepted frame=0
target remote frame accepted
non-target accepted CRC-valid frame=0
other lane not blanked
```

生成未来硬件 8×8 matrix schema：

```text
evidence/templates/p10_3_crosstalk_8x8/
```

---

# 13. 4-Lane 调度与降级

scheduler 必须支持：

```text
lane0..lane3
lane masks 0x1..0xF
equal weights
weighted modes
health-aware selection
retry migration
lane unavailable
lane recovery
```

最少测试：

```text
0x1
0x2
0x4
0x8
0x3
0x5
0xA
0x7
0xB
0xD
0xE
0xF
```

降级：

```text
4→3
4→2
4→1
恢复到4
```

要求：

```text
健康lane不被故障lane阻塞
未确认帧可迁移
已确认帧不迁移
duplicate/stale commit=0
```

---

# 14. 4-Lane ARQ 和方向窗口

评估：

```text
global outstanding 32 vs 64
SACK window 32 vs 64
bundle burst 32 vs 64
ACK threshold 32 vs 64
object concurrency 4 vs 8
```

目标：

```text
4 lanes持续占用
不每对象方向反转
Host不在fast path
```

离线模型自动选择达到 8 Mbit/s硬目标的最低资源配置。

建议候选：

```text
OUTSTANDING=64
SACK_WINDOW=64
BURST_FRAMES=64
ACK_THRESHOLD=64
OBJECTS_IN_FLIGHT=8
```

这些只是候选，必须由模型和资源结果冻结。

---

# 15. 4-Lane 性能目标与模型

## 15.1 物理能力

```text
4 lanes × 4 Mbit/s:
16 Mbit/s aggregate RAW capability
```

## 15.2 Application scale-equivalent hard target

最终产品：

```text
8 lanes >=16 Mbit/s application
```

折算当前 4 lanes：

```text
>=8.0 Mbit/s per tested half-duplex direction
```

stretch：

```text
>=9.6 Mbit/s
```

## 15.3 模型必须包含

```text
4PPM frame airtime
247-byte L1 payload
RFAP useful chunk
exact duty target
ACK/SACK
direction quiet
same-module post-TX guard
outstanding
object concurrency
DMA
PS generation
CRC/SHA
remote verification
PER/retry
```

输出：

```text
RAW ceiling
frame ceiling
RFAP useful ceiling
duty ceiling
ACK/guard overhead
expected sustained goodput
resource configuration
bottleneck
```

硬门：

```text
P10_2_4LANE_8MBPS_FEASIBILITY:
PASS
```

若达不到：

```text
FAIL_WITH_ARCHITECTURE_BLOCKER
```

不得降低安全、CRC、SHA或SACK。

---

# 16. 4-Lane Streaming 和对象模型

保持：

```text
64 MiB descriptor-chained streaming
incremental CRC32
incremental SHA256
atomic publish
abort/reset recovery
```

扩展到4lane striping：

```text
segment distribution across 4 lanes
reorder
lane failure during object
retry migration
lane recovery
```

离线测试：

```text
64 MiB clean
128 MiB clean model
lane2 unavailable
lane3 unavailable
two lanes unavailable
reset during streaming
descriptor wrap
sequence wrap
```

要求：

```text
partial/duplicate/stale commit=0
descriptor leak=0
double completion=0
```

---

# 17. 4-Lane PS 软件和寄存器

扩展：

```text
lane mask 4 bit
per-lane counters[4]
per-module admission[4]
per-lane scheduler status
per-lane health
per-lane retry/migration
per-module duty
per-module echo/blank/reject
```

host/PS API：

```text
configure lane mask 0x1..0xF
query 4-lane capabilities
query 4-lane counters
start autonomous performance
stream large object
inject lane unavailable
snapshot
stop
shutdown
```

禁止：

```text
数组长度硬编码2
日志只打印lane0/lane1
错误码依赖2lane
```

---

# 18. 4-Lane register map

扩展：

```text
ACTIVE_LANE_MASK[3:0]
READY_LANE_MASK[3:0]
FAULT_LANE_MASK[3:0]
TX_LANE_MASK[3:0]
RX_ACCEPT_MASK[3:0]

per-lane:
raw/frame/CRC/retry/migration/scheduled bytes

per-module:
duty/headroom
continuous-high
raw echo
blanked frames
local-source reject
accepted remote frames
post-TX guard
```

要求：

```text
旧2-lane地址兼容
新增字段append或版本化
generated C/Python/RTL一致
atomic snapshot
```

---

# 19. 4-Lane 双端数字仿真

建立：

```text
AX7020-F 4-lane endpoint
AX7020-R 4-lane endpoint
独立clock
独立reset
独立DMA
无共享RAM
```

测试：

```text
4-lane clean sustained
lane mask矩阵
lane fault/recovery
sequence wrap
SACK
64 MiB
same-module echo
cross-lane coupling
endpoint reset
DMA reset
```

至少：

```text
100,000 scheduler/protocol events
50,000 echo/admission events
25,000 fault/reset events
```

固定 seeds：

```text
1
7
17
31
127
1024
20260803
```

---

# 20. XSIM 计划

至少：

```text
tb_ax7020_4lane_profile
tb_4lane_lane_mask_matrix
tb_4lane_scheduler_fairness
tb_4lane_retry_migration
tb_4lane_echo_admission
tb_4lane_streaming
tb_4lane_dual_endpoint
tb_2lane_4lane_regression
```

要求：

```text
2-lane行为无回归
4-lane行为通过
future 8-lane elaboration仍通过
```

---

# 21. 双 AX7020 4-Lane 离线构建

构建：

```text
AX7020-F 4-lane top
AX7020-R 4-lane top
```

硬门：

```text
synthesis PASS
route PASS
WNS >=0
WHS >=0
TNS=0
unconstrained internal endpoints=0
critical DRC=0
unsafe CDC=0
REQP-1839=0
resource limits PASS
TFDU safety regression PASS
```

记录：

```text
LUT
FF
BRAM
DSP
timing
2-lane delta
4-lane delta
未来8-lane projected delta
```

不得因4-lane资源压力删除安全或完整性逻辑。

---

# 22. 4-Lane 供电和电流准备

TFDU 发射峰值按每模块约：

```text
0.6 A engineering upper bound
```

四个模块同端同时发射：

```text
约2.4 A peak IRED current
```

该值不包含：

```text
FPGA/PS
其他逻辑
转换损耗
```

生成：

```text
docs/hardware/P10_2_4LANE_POWER_AND_DECOUPLING_REQUIREMENTS.md
config/hardware/p10_2_4lane_power_budget.yaml
scripts/model_p10_2_4lane_power.py
```

至少评估：

```text
1/2/4 simultaneous TX
per-module duty
endpoint average current
peak current
connector/cable
VCC2 droop
bulk capacitance
small-board decoupling
ground return
thermal
```

未来硬件顺序必须：

```text
1 lane
→2 lanes
→4 lanes
```

不得直接从safe idle跳到4模块同时TX。

当前阶段只输出设计输入：

```text
P10_2_POWER_REQUIREMENT_PACKAGE: PASS
P10_3_REAL_POWER_ACCEPTANCE: PENDING
```

---

# 23. 新模块入库和预验收计划

生成：

```text
docs/hardware/P10_2_NEW_MODULE_INTAKE_PLAN.md
```

F2/F3/R2/R3 入库至少检查：

```text
板卡revision
TFDU marking
pinout
静态短路
VCC/GND
SD/Mode
Txd输入
Rxd输出
去耦
模块标签
```

未来硬件测试顺序：

```text
safe idle
receive-only
64 raw pulses
1024 raw pulses
4 Mbit/s frame smoke
```

任何新模块在上述步骤通过前不能进入4-lane formal run。

---

# 24. 4-Lane 硬件验收计划

生成：

```text
docs/plans/P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_PLAN.md
docs/plans/P10_3_4LANE_ACCEPTANCE_MATRIX.md
```

未来阶段顺序：

```text
P10_3-00 wiring/module inventory freeze
P10_3-01 new current-run authorization
P10_3-02 target identity
P10_3-03 shutdown images
P10_3-04 safe boot
P10_3-05 new module per-module intake
P10_3-06 8×8 raw/echo matrix
P10_3-07 lane0 4 Mbit/s
P10_3-08 lane1 4 Mbit/s
P10_3-09 lane2 4 Mbit/s
P10_3-10 lane3 4 Mbit/s
P10_3-11 2-lane regression
P10_3-12 4-lane 16 Mbit/s RAW
P10_3-13 4-lane ARQ/scheduler
P10_3-14 degrade 4→3→2→1
P10_3-15 64 MiB streaming
P10_3-16 application >=8 Mbit/s F→R
P10_3-17 application >=8 Mbit/s R→F
P10_3-18 30-minute stationary
P10_3-19 shutdown
P10_3-20 evidence/checkpoint
```

不含：

```text
2小时
旋转
P11
Ethernet
SPI
full-duplex
```

---

# 25. 未来 4-Lane hardware runner dry-run

新增：

```text
scripts/run_p10_3_ax7020_4lane_hardware.py
tools/run_p10_3_ax7020_4lane_hardware.ps1
```

默认：

```text
NO_HARDWARE=1
dry-run
authorization required
```

必须 fail-closed：

```text
无wiring hash
无8模块inventory
旧F1被选中
错误board ID
错误bitstream/ELF hash
缺shutdown
lane mask>0xF
Ethernet请求
movement请求
2h请求
```

dry-run只打印命令，不连接 hw_server。

---

# 26. 4-Lane evidence schema

创建：

```text
evidence/templates/p10_3_4lane/
```

至少：

```text
authorization
wiring
module inventory
board identity
artifact manifest
safe boot
power baseline
raw 8x8 matrix
per-lane PHY
4-lane RAW
protocol/scheduler
degraded masks
streaming
performance
30min
shutdown
final
```

机器可读字段必须支持：

```text
lane0..lane3
module F0..F3/R0..R3
lane mask 0x0..0xF
```

---

# 27. 性能和诊断语义清理

## 27.1 ACK counters

将旧含义模糊的：

```text
ack_wait_ratio
```

拆成：

```text
outstanding_unacked_occupancy_ratio
tx_idle_due_to_ack_ratio
window_full_stall_ratio
receiver_credit_stall_ratio
direction_turnaround_idle_ratio
```

保留旧字段用于历史读取，但标记：

```text
DEPRECATED_AMBIGUOUS
```

## 27.2 Application ceiling

统一：

```text
RAW ceiling
frame ceiling
RFAP useful ceiling
modeled sustained application
measured application
```

不得用 `application_ceiling` 命名一个包含额外保守假设、但被实测超过的值。

## 27.3 Local-source rejection

增加仿真注入，直接使一帧到达 local-source filter，验证：

```text
local_source_rejected_frame_count >0
application commit=0
```

该项不要求新的2-lane硬件运行。

---

# 28. 2-Lane 回归保护

P10.2 必须保留：

```text
2-lane profile
2-lane XDC
2-lane software
2-lane test vectors
P10.1R verify-existing
```

新 4-lane改动后执行：

```text
P10.1R frozen evidence verify-existing
2-lane focused XSIM
2-lane AX7020 implementation
register compatibility
```

不得修改 P10.1R tag或 raw evidence。

---

# 29. Requirement IDs

新增：

```text
P10_2-CLOSE-001 P10.1R authorization closed
P10_2-INV-001 accepted/quarantined module inventory
P10_2-WIRE-001 4-lane wiring proposal
P10_2-PIN-001 no I/O bank conflict
P10_2-PROFILE-001 fixed 4-lane profile
P10_2-PROFILE-002 rotating 4-lane profile

P10_2-SAFE-001 8 physical-module duty/admission model
P10_2-SAFE-002 one permit per endpoint
P10_2-ECHO-001 8×8 echo/crosstalk model

P10_2-LANE-001 lane count 4
P10_2-LANE-002 lane mask 0x1..0xF
P10_2-LANE-003 degrade 4→3→2→1
P10_2-SCHED-001 four-lane scheduler
P10_2-ARQ-001 four-lane outstanding/SACK
P10_2-STREAM-001 four-lane 64 MiB model

P10_2-PERF-001 16 Mbit/s RAW model
P10_2-PERF-002 >=8 Mbit/s application feasibility
P10_2-PERF-003 9.6 Mbit/s stretch evaluation

P10_2-POWER-001 four-TX peak-current budget
P10_2-HWPREP-001 4-lane fail-closed runner
P10_2-HWPREP-002 4-lane evidence schema
```

---

# 30. Machine state

开始：

```text
current_program_stage:
P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS

p10_2_status:
IN_PROGRESS

current_run_hardware_authorization:
false
```

通过后：

```text
p10_1r_status:
PASS

two_lane_baseline_status:
FROZEN_ACCEPTED

p10_2_status:
PASS

p10_3_status:
PENDING_PHYSICAL_WIRING_AND_NEW_AUTHORIZATION

current_program_stage:
P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE

current_run_hardware_authorization:
false

p11_status:
NOT_STARTED
```

仍保持：

```text
Ethernet deferred
SPI pending
physical GLOBAL_PERMIT pending
external duty pending
handover pending
8×32 pending
600 rpm pending
product final pending
```

---

# 31. Gate 脚本

新增：

```text
scripts/run_p10_2_4lane_offline_gate.py
tools/run_p10_2_4lane_offline_gate.ps1
```

支持：

```text
--quick
--full
--verify-existing
--json-summary
--allow-skips
--no-cache
```

至少运行：

```text
P10.1R closeout recheck
module inventory
wiring/pin audit
profile generation
2-lane/4-lane/8-lane elaboration
safety/echo model
lane-mask matrix
scheduler/ARQ
streaming
performance model
power model
fixed/rotating build
software build
P10.3 runner dry-run
state/requirements
no-hardware scan
evidence consistency
```

核心项不得 skip：

```text
module inventory
wiring/pin audit
4-lane profiles
4-lane safety
4-lane performance feasibility
fixed/rotating build
hardware runner dry-run
evidence consistency
```

---

# 32. Evidence

至少生成：

```text
evidence/generated/p10_2_repo_discovery.md/json
evidence/generated/p10_1r_closeout_summary.md/json
evidence/generated/p10_1r_git_checkpoint_metadata.json

evidence/generated/p10_2_repo_intake.md/json
evidence/generated/p10_2_module_inventory_summary.md/json
evidence/generated/p10_2_wiring_summary.md/json
evidence/generated/p10_2_pin_bank_audit.md/json
evidence/generated/p10_2_profile_summary.md/json
evidence/generated/p10_2_parameterization_summary.md/json
evidence/generated/p10_2_safety_summary.md/json
evidence/generated/p10_2_echo_matrix_model.md/json
evidence/generated/p10_2_scheduler_summary.md/json
evidence/generated/p10_2_arq_summary.md/json
evidence/generated/p10_2_streaming_summary.md/json
evidence/generated/p10_2_performance_model.md/json
evidence/generated/p10_2_power_budget.md/json
evidence/generated/p10_2_xsim_summary.md/json
evidence/generated/p10_2_fixed_build.md/json
evidence/generated/p10_2_rotating_build.md/json
evidence/generated/p10_2_software_build.md/json
evidence/generated/p10_2_hardware_dry_run.md/json
evidence/generated/p10_2_p10_3_readiness.md/json
evidence/generated/p10_2_regression.md/json
evidence/generated/p10_2_evidence_consistency.md/json
evidence/generated/p10_2_final_summary.md/json

evidence/generated/p10_2_raw/artifact_sha256_manifest.json
```

---

# 33. Mandatory exit gates

```text
P10_1R_PASS_TAG_IMMUTABLE: PASS
P10_1R_CLOSEOUT: PASS
P10_1R_AUTHORIZATION_CLOSED: PASS
P10_1R_STATUS_TEXT_CONSISTENT: PASS
P10_1R_FROZEN_VERIFY_EXISTING: PASS

MODULE_INVENTORY: PASS
OLD_F1_QUARANTINED: PASS
NEW_MODULE_PLACEHOLDERS: PASS

FOUR_LANE_WIRING_PROPOSAL: PASS
PIN_BANK_VCCO_AUDIT: PASS
NO_Z7010_XDC_REUSE: PASS
EXISTING_LANE0_LANE1_PIN_PRESERVATION: PASS or BREAKING_CHANGE_EXPLICIT

FIXED_4LANE_PROFILE: PASS
ROTATING_4LANE_PROFILE: PASS
LANE_COUNT_4: PASS
LANE_MASK_0X1_TO_0XF: PASS

EIGHT_PHYSICAL_MODULE_SAFETY_MODEL: PASS
SINGLE_GLOBAL_PERMIT_PER_ENDPOINT: PASS
PER_MODULE_TX_RX_EXCLUSION: PASS
OTHER_LANES_NOT_BLANKED: PASS

ECHO_CROSSTALK_8X8_MODEL: PASS
NON_TARGET_ACCEPTED_FRAME_ZERO_MODEL: PASS

FOUR_LANE_SCHEDULER: PASS
DEGRADED_MASK_MATRIX: PASS
RETRY_MIGRATION: PASS
FOUR_LANE_ARQ_SACK: PASS

FOUR_LANE_STREAMING_64M_MODEL: PASS
FOUR_LANE_RAW_16MBPS_FEASIBILITY: PASS
FOUR_LANE_APPLICATION_8MBPS_FEASIBILITY: PASS
FOUR_LANE_STRETCH_9P6MBPS: PASS / FAIL_NON_BLOCKING / PENDING_WITH_EXPLICIT_GAP

FOUR_TX_POWER_REQUIREMENT_PACKAGE: PASS

FIXED_4LANE_BUILD: PASS
ROTATING_4LANE_BUILD: PASS
TIMING_CDC_DRC: PASS
RESOURCE_LIMITS: PASS
SOFTWARE_BUILD: PASS

P10_3_RUNNER_DRY_RUN: PASS
NO_AUTH_FAIL_CLOSED: PASS
OLD_F1_SELECTION_FAIL_CLOSED: PASS
LANE_MASK_GT_0XF_FAIL_CLOSED: PASS
NO_2H_STAGE_PRESENT: PASS

TWO_LANE_REGRESSION: PASS
NO_HARDWARE_STATIC_SCAN: PASS
EVIDENCE_CONSISTENCY: PASS

NO_HARDWARE_ACTIONS_EXECUTED: true
CURRENT_RUN_HARDWARE_AUTHORIZATION: false
```

---

# 34. Git commits and tags

P10.1R closeout建议：

```text
chore: close P10.1R acceptance and quarantine legacy F1 module
```

closed tag：

```text
p10.1r-2lane-speed-stability-closed
```

P10.2建议提交：

```text
feat: add AX7020 four-lane board profiles and parameterization
feat: add four-lane safety, scheduler and performance models
docs: add four-lane wiring, power and hardware acceptance package
test: add P10.2 four-lane offline readiness gate
test: freeze P10.2 offline readiness checkpoint
```

annotated tag：

```text
p10.2-4lane-offline-ready
```

不 push、不 merge main，除非用户另行要求。

---

# 35. 最终输出格式

```text
P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS:
PASS / FAIL / PARTIAL

P10_1R_SOURCE_COMMIT:
39df17155ce82e38366fbdac00c79584f0fe1afa

P10_1R_EVIDENCE_CHECKPOINT:
9321ca2f1797eb12bfb02848c3ee27145e1e8eb4

P10_1R_PASS_TAG:
p10.1r-2lane-speed-stability-pass

P10_1R_CLOSED_TAG:
<actual tag>

P10_2_SOURCE_COMMIT:
<hash>

P10_2_EVIDENCE_CHECKPOINT:
<hash>

P10_2_TAG:
p10.2-4lane-offline-ready or NONE

BRANCH:
p10.2/4lane-offline-readiness

WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_2

WORKTREE_CLEAN:
true/false

NO_HARDWARE_ACTIONS_EXECUTED:
true

CURRENT_RUN_HARDWARE_AUTHORIZATION:
false

NO_2H_QUALIFICATION_EXECUTED:
true

TWO_LANE_BASELINE:
FROZEN_ACCEPTED

OLD_F1_MODULE:
QUARANTINED_NOT_ACCEPTED

FOUR_LANE_TOPOLOGY:
F0-R0,F1-R1,F2-R2,F3-R3

FUTURE_MODULE_COUNT:
8

FOUR_LANE_WIRING_PROPOSAL:
PASS/FAIL

WIRING_PROPOSAL_SHA256:
<hash>

FIXED_4LANE_PROFILE:
PASS/FAIL

ROTATING_4LANE_PROFILE:
PASS/FAIL

FIXED_4LANE_BITSTREAM_CANDIDATE_SHA256:
<hash or NONE>

ROTATING_4LANE_BITSTREAM_CANDIDATE_SHA256:
<hash or NONE>

LANE_MASK_MATRIX:
PASS/FAIL

EIGHT_PHYSICAL_MODULE_SAFETY_MODEL:
PASS/FAIL

ECHO_CROSSTALK_8X8_MODEL:
PASS/FAIL

FOUR_LANE_SCHEDULER:
PASS/FAIL

FOUR_LANE_ARQ_SACK:
PASS/FAIL

FOUR_LANE_STREAMING_MODEL:
PASS/FAIL

FOUR_LANE_RAW_CAPABILITY_MODEL_BPS:
16000000

FOUR_LANE_MODELED_APPLICATION_GOODPUT_BPS:
<value>

FOUR_LANE_8MBPS_HARD_TARGET_FEASIBILITY:
PASS/FAIL

FOUR_LANE_9P6MBPS_STRETCH:
PASS/FAIL_NON_BLOCKING/PENDING_WITH_EXPLICIT_GAP

RECOMMENDED_OUTSTANDING:
<value>

RECOMMENDED_SACK_WINDOW:
<value>

RECOMMENDED_BURST_FRAMES:
<value>

RECOMMENDED_ACK_THRESHOLD:
<value>

RECOMMENDED_OBJECTS_IN_FLIGHT:
<value>

FOUR_TX_PEAK_CURRENT_BUDGET_A:
<value>

P10_3_RUNNER_DRY_RUN:
PASS/FAIL

P10_3_HARDWARE_READY:
false until physical wiring, eight accepted modules and new authorization

P10_3_MISSING_PREREQUISITES:
<list>

P11_STATUS:
NOT_STARTED

PASS:
<list>

FAIL:
<list>

SKIP_WITH_REASON:
<list>

GENERATED_EVIDENCE:
<list>

NEXT_RECOMMENDED_STAGE:
P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_ONLY_AFTER_PHYSICAL_WIRING_AND_NEW_AUTHORIZATION
```

---

# 36. Definition of Done

本 Goal 完成意味着：

```text
P10.1R 2-lane PASS 已完成授权关闭、状态收口和不可变冻结；
当前2-lane代码和evidence未被4-lane改动破坏；
旧F1模块已隔离，不会混入未来4-lane库存；
4-lane固定侧和旋转侧profile/pinmap/XDC已建立；
lane0..lane3、mask 0x1..0xF、4→3→2→1降级均有离线证据；
8个物理模块的duty、startup、echo admission和单permit模型通过；
4-lane调度、ARQ、SACK、streaming和双节点模型通过；
4-lane 16 Mbit/s RAW capability与8 Mbit/s application目标离线可行；
四模块同时发射的电流、去耦和未来测量要求已形成；
AX7020-F和AX7020-R 4-lane候选完成离线实现、时序和CDC；
未来P10.3硬件runner和evidence schema已fail-closed；
用户可以根据冻结wiring proposal开始布置4-lane硬件；
没有执行2小时测试或任何新硬件动作。
```

本 Goal 完成不意味着：

```text
4-lane真实硬件已通过；
4-lane 16 Mbit/s RAW已通过；
4-lane 8 Mbit/s application已通过；
8×8真实串扰矩阵已通过；
P11 handover已开始；
旋转、8×32、600 rpm或产品最终已通过。
```

现在开始执行本 Goal。先完成 P10.1R closeout，再创建 P10.2 worktree并完成 4-lane 离线就绪包；不要执行任何硬件动作。
