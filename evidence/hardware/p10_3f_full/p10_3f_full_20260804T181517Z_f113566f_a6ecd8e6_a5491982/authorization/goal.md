# RF_COMM_MULTILANE — P10.3 双 AX7020 静止 4-Lane 硬件验收 Goal

## 8 个 TFDU6102 小板、4 条双向光学 Lane、16 Mbit/s RAW、8 Mbit/s 应用吞吐与 30 分钟稳定性

```text
DOCUMENT_TYPE:
CODEX_EXECUTION_GOAL

STAGE:
P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE

STAGE_CLASS:
AUTHORIZED_HARDWARE_ACCEPTANCE

OFFLINE_BASE_TAG:
p10.2-4lane-offline-ready

OFFLINE_SOURCE_COMMIT:
dd44b0a4163ce74a491bae49bb6079b82dd94b7d

OFFLINE_EVIDENCE_CHECKPOINT:
08771d6bf9e852c9d34bcff61add1598e120b70a

P10_1R_PASS_TAG:
p10.1r-2lane-speed-stability-pass

P10_1R_CLOSED_TAG:
p10.1r-2lane-speed-stability-closed

P10_1R_SOURCE_COMMIT:
39df17155ce82e38366fbdac00c79584f0fe1afa

P10_1R_EVIDENCE_CHECKPOINT:
9321ca2f1797eb12bfb02848c3ee27145e1e8eb4

P10_2_WIRING_PROPOSAL_SHA256:
5f4a89b818b007af4863534759068dda529fe3c34501569ea4da89a42d8026fc

P10_2_FIXED_FUNCTIONAL_CANDIDATE_SHA256:
b50c9ea25a3519ab55de77a8f937ec4639f46dbffa75d3fef38a832b6685aa98

P10_2_ROTATING_FUNCTIONAL_CANDIDATE_SHA256:
d0afa4ae6e1698d6b35229367617f7718edafc7877899c278db9c44c1f2e41e1

RECOMMENDED_BRANCH:
p10.3/ax7020-stationary-4lane-hardware

RECOMMENDED_WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_3

FIXED_ENDPOINT:
AX7020-F/JTAG:210249855178

ROTATING_ROLE_ENDPOINT:
AX7020-R/JTAG:210512180081

PHYSICAL_MODULE_COUNT:
8

MODULES_PER_ENDPOINT:
4

LOGICAL_LANE_COUNT:
4

LANE0:
F0 <-> R0

LANE1:
F1 <-> R1

LANE2:
F2 <-> R2

LANE3:
F3 <-> R3

ALLOWED_LANE_MASKS:
0x1 through 0xF

MAX_LANE_MASK:
0xF

NETWORK_CABLE_CONNECTED:
false

ETHERNET_ALLOWED:
false

HARDWARE_MOVEMENT_ALLOWED:
false

ROTATION_ALLOWED:
false

OPTICAL_REALIGNMENT_ALLOWED_DURING_FORMAL_RUN:
false

REWIRING_ALLOWED_DURING_FORMAL_RUN:
false

TWO_HOUR_QUALIFICATION_REQUIRED:
false

MAX_SINGLE_FORMAL_RUN_SECONDS:
1800

FOUR_LANE_RAW_CAPABILITY_TARGET_BPS:
16000000

FOUR_LANE_APPLICATION_GOODPUT_HARD_TARGET_BPS:
8000000 per tested half-duplex direction

FOUR_LANE_APPLICATION_GOODPUT_STRETCH_BPS:
9600000 per tested half-duplex direction

CURRENT_RUN_HARDWARE_AUTHORIZATION:
false until explicitly granted for this stage

P11_STATUS:
NOT_STARTED
```

本 Goal 直接交给 Codex 执行。Codex 必须在用户完成 4-lane 物理布置并授予新的 P10.3 current-run 硬件授权后，实际完成：

```text
P10.2 immutable baseline recheck
8 模块 inventory 和 wiring freeze
双端 4-lane shutdown / functional artifact 构建与冻结
两块 AX7020 唯一身份绑定
两端 safe boot
F2/F3/R2/R3 新模块逐个验收
8 TX × 8 RX raw / echo / crosstalk matrix
lane0..lane3 双向 4 Mbit/s
2-lane 既有基线回归
4-lane 16 Mbit/s aggregate RAW capability
mask 0x1..0xF 和 4→3→2→1 降级
4-lane selective-repeat / SACK / scheduler / retry migration
双端真实 DMA / DDR / cache
双向 64 MiB streaming
F→R application goodput >=8 Mbit/s
R→F application goodput >=8 Mbit/s
30 分钟正式速度与稳定性验收
两端 shutdown
完整 evidence、source commit、checkpoint 和 tag
```

本 Goal 不执行：

```text
P11 handover
ABZ
旋转
600 rpm
8×32 full ring
Ethernet
SPI
2+2 或最终 4+4 full-duplex 验收
2 小时测试
外部 GLOBAL_PERMIT 最终验收
产品最终验收
```

---

# 1. P10.3 的工程定位

P10.3 是 P10 双独立 AX7020 节点和 P10.1R 2-lane 高速稳定链路的静止 4-lane 扩展验收。

允许形成的结论：

```text
两块 AX7020
两个独立 PS / PL / DDR / DMA
8 个 TFDU6102 小板
4 条双向 logical lane
静止固定布置
无 Ethernet
4 Mbit/s/lane
16 Mbit/s aggregate RAW capability
>=8 Mbit/s application goodput / tested half-duplex direction
30 分钟稳定运行
```

不得外推：

```text
最终 8-lane 产品
32 个固定模块
sector bank
current/candidate handover
ABZ
旋转
600 rpm
全双工
最终供电和系统红外安全
```

---

# 2. 已确认的 2-Lane 基线

以下 P10.1R 结果必须保持，不得因 4-lane 工作被覆盖：

```text
lane0 / lane1 4 Mbit/s bidirectional: PASS
2-lane application goodput >=4 Mbit/s/direction: PASS
5 × 64 MiB F→R: PASS
5 × 64 MiB R→F: PASS
30-minute stationary speed/stability: PASS
same-module raw echo observable: PASS
same-module accepted DATA: 0
cross-lane accepted DATA: 0
CRC/SHA/partial/duplicate/stale/retry-exhausted/descriptor leak/deadlock: 0
shutdown both endpoints: PASS
```

4-lane 正式运行之前必须 fresh 重跑 lane0+lane1 的 focused 回归，但不得重写 P10.1R frozen evidence。

---

# 3. 不可复用的旧授权

以下授权均不可用于 P10.3：

```text
P10 authorization
P10.1 hardware authorization
P10.1R authorization
```

P10.3 必须创建新的 authorization record，并绑定：

```text
P10.3 stage
固定端和旋转角色端 board IDs
8 个 module IDs
实际 wiring SHA256
pinmap / XDC SHA256
shutdown bitstream SHA256
functional bitstream SHA256
fixed/rotating ELF SHA256
lane mask <=0xF
max runtime <=1800 s
禁止 Ethernet、移动和旋转
shutdown-on-exit
```

---

# 4. 用户物理前置条件

进入任何 JTAG 或发射动作前，必须具备：

```text
1. F2、F3、R2、R3 已安装；
2. 8 个模块均有唯一标签；
3. 原故障 F1 仍处于 QUARANTINED_NOT_ACCEPTED；
4. replacement F1 仍为当前 accepted F1；
5. 实际接线与冻结 wiring proposal 一致；
6. 两块 AX7020 在接线期间断电；
7. 两端 J11 wiring 完成；
8. VCC/GND、Mode、SD、Txd、Rxd 已核对；
9. 去耦、bulk 和地回路已布置；
10. formal run 期间不会移动、调角或重新接线。
```

用户完成物理布置后，应向 Codex提供一次性声明：

```text
P10_3_PHYSICAL_WIRING_COMPLETED: true
P10_2_WIRING_PROPOSAL_SHA256:
5f4a89b818b007af4863534759068dda529fe3c34501569ea4da89a42d8026fc

MODULES_INSTALLED:
F0,F1,F2,F3,R0,R1,R2,R3

OLD_F1_QUARANTINED:
true

BOTH_BOARDS_POWERED_OFF_DURING_WIRING:
true

NO_UNDOCUMENTED_WIRES:
true

NO_HARDWARE_MOVEMENT_DURING_FORMAL_RUN:
true
```

如果实际接线与 proposal 有差异：

```text
不得 program 旧 candidate
必须更新 wiring / pinmap / XDC
必须生成新的 SHA256
必须重新 build
```

---

# 5. 只有严重阻塞才询问用户

授权后，Codex 不得就普通工程问题反复请求用户确认。

只允许在以下情况暂停：

```text
接线与官方资料明确冲突并可能损坏硬件
VCC/GND错误
output-to-output
I/O bank电压不兼容
无法唯一绑定AX7020-F和AX7020-R
必须人工插拔、移动、调角或重新接线
JTAG有界重试后仍无法枚举板卡
任一端无法确认shutdown
出现duty/continuous-high/自主发射/最终TX kill安全违规
必须修改PROJECT_CONSTRAINTS.txt
必须使用Ethernet、运动机构或lane mask>0xF
```

以下问题由 Codex 自主诊断、修复、重新构建并继续：

```text
Python/C/RTL错误
Vivado/Vitis错误
时序或资源错误
BSP/ELF错误
JTAG脚本错误
DMA/cache错误
协议错误
测试失败
日志/evidence解析错误
需要重新生成artifact
```

如果 mandatory gate 持续失败且不存在用户可解决的物理阻塞，Codex应安全 shutdown并输出 FAIL，不询问“是否继续”。

---

# 6. Git 与 Worktree

## 6.1 创建 P10.3 worktree

从：

```text
p10.2-4lane-offline-ready
```

创建：

```text
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_3
```

分支：

```text
p10.3/ax7020-stationary-4lane-hardware
```

命令：

```powershell
git worktree add `
  -b p10.3/ax7020-stationary-4lane-hardware `
  C:\Users\user\Documents\RF_COMM_MULTILANE_P10_3 `
  p10.2-4lane-offline-ready
```

若已存在：

```text
验证 path、branch、HEAD、base、clean
不得删除或 reset 未知 worktree
```

## 6.2 冻结历史

不得移动或修改：

```text
p10.1r-2lane-speed-stability-pass
p10.1r-2lane-speed-stability-closed
p10.2-4lane-offline-ready
P10.1R raw evidence
P10.2 offline evidence
```

---

# 7. Repository Intake

生成：

```text
evidence/generated/p10_3_repo_intake.md
evidence/generated/p10_3_repo_intake.json
```

至少记录：

```text
worktree
branch
HEAD
P10.2 tag object和target
P10.1R tags
git status
PROJECT_CONSTRAINTS SHA256
AGENTS SHA256
project_state SHA256
requirements SHA256
register-map SHA256
4-lane wiring SHA256
fixed/rotating profile SHA256
module inventory SHA256
tool versions
current authorization
start timestamp
```

硬件前先运行：

```text
P10.2 verify-existing
P10.1R verify-existing
P10 verify-existing
P8C safety verify-existing
state/requirements consistency
no-hardware static scan
```

任何 immutable baseline 失败时，不得进入硬件。

---

# 8. 8 模块 Inventory Freeze

Canonical inventory：

```text
config/hardware/tfdu_module_inventory.yaml
```

必须包含：

```text
F0
F1 replacement
F2
F3
R0
R1
R2
R3
F1 original quarantined
```

每个 active module 至少记录：

```text
module ID
PCB revision
TFDU marking/lot if available
endpoint
connector position
lane
pinout revision
inventory status
accepted stage
```

P10.3 开始时：

```text
F0/F1/R0/R1:
ACCEPTED_P10_1R

F2/F3/R2/R3:
INSTALLED_PENDING_P10_3_INTAKE

F1_ORIGINAL:
QUARANTINED_NOT_ACCEPTED
```

runner 必须 fail-closed：

```text
旧F1被选为active module
module ID重复
module position重复
lane配对缺失
inventory hash与authorization不一致
```

---

# 9. Wiring Freeze

使用：

```text
docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md
config/hardware/p10_2_ax7020_4lane_wiring.yaml
```

必须核对：

```text
F0-R0
F1-R1
F2-R2
F3-R3

Txd
Rxd
SD
Mode
VCC
GND
connector pin
FPGA package pin
I/O bank
VCCO
IOSTANDARD
```

保持：

```text
lane0/lane1 已通过接线不变
lane2/lane3 使用冻结J11方案
```

生成 actual-as-wired：

```text
config/hardware/p10_3_actual_wiring.yaml
docs/hardware/P10_3_AS_WIRED_RECORD.md
```

并计算：

```text
P10_3_ACTUAL_WIRING_SHA256
```

只有实际 wiring 与授权绑定后才能 program。

---

# 10. 供电和去耦 Preflight

## 10.1 工程预算

按每模块：

```text
0.6 A peak engineering upper bound
```

四个同时发射：

```text
2.4 A peak IRED current / transmitting endpoint
```

不包含：

```text
AX7020
DDR
其他板载负载
转换损耗
连接器压降
```

## 10.2 自动检查

若板卡提供可读 telemetry，自动记录：

```text
rail voltage
brownout/reset flags
temperature
current monitor
```

若没有外部/板载测量，保留：

```text
EXTERNAL_4LANE_POWER_ACCEPTANCE:
PENDING_EXTERNAL_MEASUREMENT
```

不能把无 brownout 当作真实电压跌落 PASS。

## 10.3 渐进式发射

必须按：

```text
1 lane
→2 lanes
→4 lanes
```

逐级进入。

每级检查：

```text
JTAG稳定
PS/PL未reset
DMA无异常
TFDU counter正常
duty无违规
shutdown可用
```

---

# 11. Artifact 构建与冻结

## 11.1 Functional Candidates

P10.2 候选：

```text
fixed:
b50c9ea25a3519ab55de77a8f937ec4639f46dbffa75d3fef38a832b6685aa98

rotating:
d0afa4ae6e1698d6b35229367617f7718edafc7877899c278db9c44c1f2e41e1
```

如果 actual wiring、inventory、pinmap、XDC、profile 和 source 与 P10.2 完全一致，可作为功能候选重新验证并复制到本次内容寻址目录。

任一输入变化：

```text
必须重新build
```

## 11.2 Shutdown Artifacts

必须新生成：

```text
AX7020-F 4-lane shutdown bitstream
AX7020-R 4-lane shutdown bitstream
```

shutdown image 必须：

```text
所有4个Txd低
所有4个SD请求shutdown
endpoint unarmed
active lane mask=0
GLOBAL_PERMIT effective low
无自动发送
```

## 11.3 PS Artifacts

构建/冻结：

```text
fixed XSA/BSP/ELF
rotating XSA/BSP/ELF
host control tool
trace decoder
evidence finalizer
```

## 11.4 内容寻址

```text
artifacts/p10_3/<source>/<sha256>/
```

不得从可覆盖 Vivado run 目录直接 program。

## 11.5 离线硬门

两端均必须：

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
register-map一致
TFDU safety smoke PASS
software build PASS
```

正式 candidate 不默认加入大规模 ILA。

---

# 12. Current-Run Authorization

用户完成接线后，将本 Goal 与以下授权一起发给 Codex：

```text
我授权 Codex 在
P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE
范围内，对当前两块 AX7020 和八个 TFDU6102 小板执行自动化硬件操作。

固定端：
AX7020-F/JTAG:210249855178

旋转角色端：
AX7020-R/JTAG:210512180081

lane0=F0-R0
lane1=F1-R1
lane2=F2-R2
lane3=F3-R3

实际接线已经按照 P10.3 actual-as-wired record 完成。
禁止使用原故障 F1 模块。

允许：
- 构建、冻结和program内容寻址的4-lane shutdown和functional bitstream；
- 下载运行两端ELF；
- 使用hw_server、Hardware Manager batch、XSDB/JTAG、DDR、DMA、
  UART、ILA/VIO和寄存器；
- 在lane mask 0x1..0xF上执行受控TFDU发射；
- 按1→2→4 lane进行供电功能preflight；
- 执行新模块验收、8×8 raw/echo矩阵、每lane 4 Mbit/s、
  4-lane RAW、mask/degrade、ARQ/SACK、64 MiB streaming、
  application performance和最长1800秒正式运行；
- 自动执行PS/PL/DMA reset和恢复；
- 失败、异常、超时或退出时shutdown两端。

禁止：
- 连接Ethernet；
- 移动、旋转、调角、遮挡、交换模块或重新接线；
- 使用lane mask>0xF；
- 执行2小时测试；
- 推进P11、8×32或600rpm；
- 将内部power telemetry冒充外部电气验收。

除明确电气危险、无法唯一绑定板卡、必须人工物理操作或无法确认shutdown外，
不要再次请求用户确认。
```

授权记录必须绑定本次最终 artifact 和 actual wiring hash。

---

# 13. Target Role Binding

唯一绑定：

```text
AX7020-F:
JTAG 210249855178

AX7020-R:
JTAG 210512180081
```

同时读取：

```text
FPGA part
device DNA if available
profile ID
build ID
node role
UART identity
```

不得按 JTAG target 顺序猜角色。

---

# 14. Safe Startup

每个正式 run：

1. 唯一识别 F/R；
2. program 两端 4-lane shutdown image；
3. 验证 8 个物理 TX 全关闭；
4. program F functional candidate；
5. 验证 F safe boot；
6. program R functional candidate；
7. 验证 R safe boot；
8. 下载两端 ELF；
9. 保持 unarmed；
10. 读取 build/profile/register/wiring/inventory hash；
11. 清 counter；
12. 两端 receive-only；
13. 等待至少 500 µs；
14. 当前 stage 显式 arm。

safe boot：

```text
Txd[3:0]=0
endpoint armed=0
active lane mask=0
outstanding physical attempt=0
无自主TX
```

任一端失败：

```text
立即shutdown两端
停止formal run
```

---

# 15. 新模块逐个 Intake

F2、F3、R2、R3 必须逐个验收。

每个模块：

```text
SD control
Mode state
Txd default low
Rxd idle
receive-only startup
64 raw pulses
1024 raw pulses
100 frame smoke
1000 frame 4 Mbit/s clean run
same-module accepted DATA=0
shutdown
```

验收后状态：

```text
ACCEPTED_P10_3_MODULE_INTAKE
```

失败模块：

```text
QUARANTINED_P10_3
```

不得进入 4-lane formal run。

---

# 16. 8×8 Raw / Echo / Crosstalk Matrix

TX：

```text
TX_F0
TX_F1
TX_F2
TX_F3
TX_R0
TX_R1
TX_R2
TX_R3
```

RX：

```text
RX_F0
RX_F1
RX_F2
RX_F3
RX_R0
RX_R1
RX_R2
RX_R3
```

每个 TX 依次执行：

```text
64 raw pulses
1024 raw pulses
10-second 4 Mbit/s frame stream
```

同时读取全部 8 个 RX。

记录：

```text
raw edges
normalized pulses
same-module raw echo
blanked frame starts
local-source rejected frames
accepted remote frames
cross-lane accepted frames
non-target CRC-valid frames
pulse-width proxy
```

验收：

```text
目标 remote path 正确
same-module raw echo允许存在
same-module accepted DATA=0
same-module accepted ACK/SACK=0
cross-lane accepted DATA=0
non-target CRC-valid accepted frame=0
other lanes not blanked
```

---

# 17. 每 Lane 双向 4 Mbit/s

分别 fresh 验证：

```text
lane0 F→R
lane0 R→F
lane1 F→R
lane1 R→F
lane2 F→R
lane2 R→F
lane3 F→R
lane3 R→F
```

每个 case：

```text
100 frame smoke
10000 frame clean acceptance
247-byte payload
counter
deterministic PRBS
```

要求：

```text
configured raw=4 Mbit/s
CRC bad=0
retry exhausted=0
same-module accepted=0
cross-lane accepted=0
duty violation=0
continuous-high violation=0
shutdown-after=PASS
```

若 lane2/3 4 Mbit/s失败，可自动回退 2/1 Mbit/s诊断，但 formal 4-lane不能继续。

---

# 18. 2-Lane 基线回归

在新增 J11 和 4-lane wrapper 后 fresh 验证：

```text
mask=0x3
lane0+lane1
```

至少：

```text
4 Mbit/s/lane
64 MiB F→R
64 MiB R→F
application goodput >=4 Mbit/s/direction
same-module accepted DATA=0
```

该回归只证明新增硬件未破坏 2-lane，不替代 4-lane验收。

---

# 19. 4-Lane 渐进式 RAW Bring-Up

按：

```text
1 lane
→2 lanes
→3 lanes
→4 lanes
```

建议：

```text
0x1
0x3
0x7
0xF
```

每级：

```text
10-second raw/frame smoke
供电功能telemetry
reset/brownout检查
duty
shutdown
```

最终：

```text
lane mask=0xF
4 Mbit/s/lane
16 Mbit/s aggregate RAW capability
```

必须明确：

```text
RAW capability != application goodput
```

---

# 20. 全 Lane-Mask Matrix

执行所有非零 mask：

```text
0x1
0x2
0x3
0x4
0x5
0x6
0x7
0x8
0x9
0xA
0xB
0xC
0xD
0xE
0xF
```

每个 mask：

```text
配置/readback一致
仅选中lane可TX
未选lane不TX
RX admission正确
scheduler不会选择disabled lane
object integrity通过
```

---

# 21. 4→3→2→1 降级与恢复

从：

```text
0xF
```

依次注入：

```text
单lane unavailable
两lane unavailable
三lane unavailable
恢复到0xF
```

至少覆盖每个 lane 单独故障。

要求：

```text
healthy lanes继续
unacked frame迁移
acked frame不迁移
active mask原子更新
degraded reason正确
path/session不被错误清空
duplicate/stale commit=0
恢复后4-lane clean object成功
```

---

# 22. 4-Lane ARQ / SACK / Scheduler

初始配置使用 P10.2推荐：

```text
outstanding=32
SACK window=32
burst frames=32
ACK threshold=32
objects in flight=4
```

验证：

```text
selective-repeat
sequence wrap
ACK aggregation
ACK loss
SACK loss
data loss
reorder
duplicate
retry migration
scheduler fairness
```

等权健康 lane：

```text
长期scheduled bytes差异 <=10%
```

如果 8 Mbit/s 目标无法达到且 trace 显示 window/ACK瓶颈，可在资源允许下自动测试：

```text
outstanding=64
SACK=64
burst=64
ACK threshold=64
objects in flight=8
```

最多 6 个调优 case，每个不超过 30 秒。

不得通过削弱 duty、CRC、SHA、SACK 或 same-module echo admission 调优。

---

# 23. 真实 DMA / DDR / Cache

两端分别 fresh 验证：

```text
TX/RX ring
ring depth
generation
wrap
descriptor batching
cache flush/invalidate
abort/reset
single completion
leak zero
```

4-lane 数据面不得退化成逐 frame JTAG 或 MMIO copy。

---

# 24. 64 MiB Streaming

双向：

```text
F→R:
至少 3 × 64 MiB

R→F:
至少 3 × 64 MiB
```

使用：

```text
lane mask=0xF
descriptor chaining
incremental CRC32
incremental SHA256
atomic commit
```

故障用例：

```text
lane2 unavailable during stream
lane3 unavailable during stream
DMA reset
endpoint service reset
```

恢复后必须：

```text
新64 MiB对象成功
```

要求：

```text
partial commit=0
wrong hash commit=0
descriptor leak=0
double completion=0
```

---

# 25. 4-Lane Application Performance

## 25.1 测量口径

正式：

```text
APPLICATION_SUSTAINED
board autonomous generator/verifier
host不在fast path
PS/PL timer crosscheck <=1%
```

## 25.2 F→R

```text
lane mask=0xF
duration>=300 s
committed bytes>=300 MiB
```

硬门：

```text
APPLICATION_GOODPUT_F_TO_R >=8,000,000 bit/s
```

stretch：

```text
>=9,600,000 bit/s
```

## 25.3 R→F

同样：

```text
APPLICATION_GOODPUT_R_TO_F >=8,000,000 bit/s
```

## 25.4 模型对照

报告：

```text
measured/model ratio
measured/RFAP ceiling ratio
per-lane utilization
primary bottleneck
```

若任一方向低于 8 Mbit/s：

```text
P10_3_PERFORMANCE_TARGET:
FAIL_WITH_EVIDENCE
```

P10.1R 2-lane PASS 保留。

---

# 26. 30 分钟正式验收

总计：

```text
1800 seconds
```

划分：

```text
0..120 s:
warm-up、timer和queue稳定

120..960 s:
F→R formal

960..1800 s:
R→F formal
```

主负载：

```text
连续64 MiB streaming
lane mask=0xF
board-autonomous
无Ethernet
无移动
```

每个方向：

```text
application goodput >=8 Mbit/s
```

完整性：

```text
CRC bad=0
SHA mismatch=0
partial commit=0
duplicate commit=0
stale commit=0
retry exhausted=0
descriptor leak=0
double completion=0
deadlock=0
transport timeout=0
```

光路隔离：

```text
same-module accepted DATA=0
cross-lane accepted DATA=0
non-target CRC-valid accepted frame=0
other-lane blanked=0
```

安全：

```text
duty violation=0
continuous-high violation=0
startup violation=0
illegal one-hot=0
shutdown fixed=PASS
shutdown rotating=PASS
```

不执行 2 小时测试。

---

# 27. TFDU 安全合同

8 个模块均必须独立保持：

```text
Txd active high
Rxd active low
SD active high shutdown
Mode=HIGH high-speed
startup >=500 µs
continuous Txd HIGH <=1 µs
1 ms exact sliding duty
design target <=18%
hard limit <20%
per-module TX/RX frame-admission exclusion
same-module raw echo observable
same-module accepted frame=0
```

每端点仍只有：

```text
1 × active-high GLOBAL_PERMIT
```

不得引入：

```text
per-lane permit
per-module permit
dual permit
permit heartbeat
```

本阶段仍不能声明：

```text
physical GLOBAL_PERMIT final implementation PASS
external duty/pin measurement PASS
```

---

# 28. 自动修复和有界重试

Codex可自主修复：

```text
RTL
wrapper/XDC
PS firmware
DMA/cache
scheduler/ARQ
host tool
Vivado/XSDB scripts
evidence parser
```

有界重试：

```text
JTAG connect <=3
program <=2
每个stage diagnostic run IDs <=2
```

每次重试前：

```text
shutdown两端
```

formal PASS必须来自单一完整 run_id，不能拼接多个 run。

---

# 29. Shutdown

每个 hardware stage：

```text
shutdown-before
bounded run
shutdown-after
```

异常、timeout、Ctrl+C、JTAG错误时：

```text
停止新TX
撤销arm
active mask=0
abort performance/streaming
回收或abort descriptor
请求SD shutdown
program两端shutdown bitstream
保存全部日志
```

最终：

```text
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
```

无法确认任一端 shutdown 属于严重失败。

---

# 30. Evidence

Run ID：

```text
p10_3_<UTC>_<source>_<fixedbit>_<rotbit>
```

目录：

```text
evidence/hardware/p10_3/<run_id>/
```

子目录：

```text
authorization
wiring
module_inventory
artifacts
target_identity
safe_boot
module_intake
power_preflight
raw_8x8
per_lane_phy
two_lane_regression
four_lane_raw
mask_matrix
degraded_modes
arq_scheduler
dma_ddr_cache
streaming_64m
performance_f2r
performance_r2f
formal_30min
shutdown
raw_logs
final
```

Generated summaries：

```text
p10_3_repo_intake
p10_3_wiring
p10_3_module_inventory
p10_3_artifact_freeze
p10_3_authorization
p10_3_target_identity
p10_3_safe_boot
p10_3_module_intake
p10_3_power_preflight
p10_3_raw_8x8
p10_3_per_lane_phy
p10_3_two_lane_regression
p10_3_four_lane_raw
p10_3_mask_matrix
p10_3_degraded_modes
p10_3_arq_scheduler
p10_3_dma_ddr_cache
p10_3_streaming_64m
p10_3_performance
p10_3_formal_30min
p10_3_shutdown
p10_3_evidence_consistency
p10_3_final_summary
```

每项：

```text
.md
.json
```

---

# 31. Requirement IDs

新增或更新：

```text
P10_3-WIRE-001 actual 4-lane wiring freeze
P10_3-INV-001 eight-module inventory
P10_3-INV-002 old F1 excluded
P10_3-HW-001 current-run authorization
P10_3-HW-002 immutable 4-lane artifacts
P10_3-SAFE-001 safe boot both endpoints
P10_3-SAFE-002 four-module duty and shutdown
P10_3-MOD-001 F2 intake
P10_3-MOD-002 F3 intake
P10_3-MOD-003 R2 intake
P10_3-MOD-004 R3 intake
P10_3-XTALK-001 8×8 matrix
P10_3-PHY-001 lane0 bidirectional 4 Mbit/s
P10_3-PHY-002 lane1 bidirectional 4 Mbit/s
P10_3-PHY-003 lane2 bidirectional 4 Mbit/s
P10_3-PHY-004 lane3 bidirectional 4 Mbit/s
P10_3-PHY-005 16 Mbit/s aggregate RAW
P10_3-MASK-001 masks 0x1..0xF
P10_3-DEG-001 degrade 4→3→2→1
P10_3-ARQ-001 4-lane selective-repeat/SACK
P10_3-STREAM-001 64 MiB F→R
P10_3-STREAM-002 64 MiB R→F
P10_3-PERF-001 F→R >=8 Mbit/s
P10_3-PERF-002 R→F >=8 Mbit/s
P10_3-SOAK-001 30-minute stationary 4-lane
P10_3-EVID-001 evidence consistency
```

---

# 32. Project State

开始：

```text
current_program_stage:
P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE

p10_3_status:
IN_PROGRESS

current_run_hardware_authorization:
true only after validated authorization
```

通过后：

```text
p10_3_status:
PASS

stationary_4lane_hardware:
PASS

four_lane_raw_16mbps:
PASS

four_lane_application_8mbps:
PASS

current_program_stage:
USER_DECISION_AFTER_P10_3

p11_status:
NOT_STARTED

current_run_hardware_authorization:
false after closeout
```

保持：

```text
P10.1R 2-lane PASS
Ethernet deferred
SPI pending
physical GLOBAL_PERMIT pending
external duty/power pending
handover pending P11
8×32 pending P12
600rpm pending P13
product final pending
```

---

# 33. Mandatory Exit Gates

```text
P10_2_BASE_RECHECK: PASS
P10_1R_2LANE_BASE_IMMUTABLE: PASS

ACTUAL_WIRING_FREEZE: PASS
EIGHT_MODULE_INVENTORY: PASS
OLD_F1_EXCLUDED: PASS
CURRENT_RUN_AUTHORIZATION: PASS

FIXED_ARTIFACT_PROVENANCE: PASS
ROTATING_ARTIFACT_PROVENANCE: PASS
SHUTDOWN_ARTIFACTS: PASS
TARGET_ROLE_BINDING: PASS
SAFE_BOOT_BOTH: PASS

F2_MODULE_INTAKE: PASS
F3_MODULE_INTAKE: PASS
R2_MODULE_INTAKE: PASS
R3_MODULE_INTAKE: PASS

RAW_8X8_MATRIX: PASS
SAME_MODULE_ACCEPTED_DATA_ZERO: PASS
CROSS_LANE_ACCEPTED_DATA_ZERO: PASS
NON_TARGET_CRC_VALID_ZERO: PASS

LANE0_4MBPS_BIDIRECTIONAL: PASS
LANE1_4MBPS_BIDIRECTIONAL: PASS
LANE2_4MBPS_BIDIRECTIONAL: PASS
LANE3_4MBPS_BIDIRECTIONAL: PASS

TWO_LANE_REGRESSION: PASS
FOUR_LANE_16MBPS_RAW_CAPABILITY: PASS
LANE_MASK_0X1_TO_0XF: PASS
DEGRADE_4_TO_3_TO_2_TO_1: PASS

FOUR_LANE_SELECTIVE_REPEAT: PASS
FOUR_LANE_SACK: PASS
FOUR_LANE_SCHEDULER_FAIRNESS: PASS
RETRY_MIGRATION: PASS

REAL_DMA_DDR_CACHE_FIXED: PASS
REAL_DMA_DDR_CACHE_ROTATING: PASS
DESCRIPTOR_LEAK_ZERO: PASS
DOUBLE_COMPLETION_ZERO: PASS

STREAMING_64M_F_TO_R: PASS
STREAMING_64M_R_TO_F: PASS
STREAM_RECOVERY: PASS

F_TO_R_APPLICATION_GOODPUT_8MBPS: PASS
R_TO_F_APPLICATION_GOODPUT_8MBPS: PASS

STATIONARY_30MIN: PASS

CRC_BAD_ZERO: PASS
SHA_MISMATCH_ZERO: PASS
PARTIAL_DUPLICATE_STALE_ZERO: PASS
RETRY_EXHAUSTED_ZERO: PASS
DEADLOCK_ZERO: PASS

DUTY_VIOLATION_ZERO: PASS
CONTINUOUS_HIGH_VIOLATION_ZERO: PASS
SHUTDOWN_FIXED: PASS
SHUTDOWN_ROTATING: PASS
EVIDENCE_CONSISTENCY: PASS

NETWORK_USED: false
NO_HARDWARE_MOVEMENT: true
NO_2H_QUALIFICATION_EXECUTED: true
MAX_LANE_MASK_USED: 0xF
```

非阻塞：

```text
FOUR_LANE_9P6MBPS_STRETCH
EXTERNAL_POWER_MEASUREMENT
EXTERNAL_TFDU_DUTY_MEASUREMENT
```

---

# 34. 失败分级

## PASS

所有 mandatory gates通过。

## PARTIAL

例如：

```text
lane0..lane3 PHY和16 Mbit/s RAW通过
但一方向application<8 Mbit/s
```

必须：

```text
P10_3=PARTIAL
4LANE_RAW=PASS
4LANE_APPLICATION=FAIL
```

不得用RAW掩盖application失败。

## FAIL_WITH_PERFORMANCE_EVIDENCE

功能和完整性通过，但8 Mbit/s目标未达。

## FAIL

以下任一：

```text
错误模块或旧F1被启用
wiring/hash不匹配
safe boot自主发射
same-module accepted DATA>0
cross-lane accepted DATA>0
错误对象提交
descriptor double completion
duty/stuck-high violation
无法确认shutdown
artifact/evidence不一致
```

---

# 35. Git Checkpoint

建议提交：

```text
feat: add AX7020 stationary four-lane hardware integration
test: add P10.3 four-lane PHY and mask evidence
test: add P10.3 streaming and performance evidence
test: freeze P10.3 four-lane acceptance checkpoint
```

PASS tag：

```text
p10.3-ax7020-stationary-4lane-pass
```

若未完全通过：

```text
p10.3-ax7020-stationary-4lane-investigated
```

不得使用 pass。

不 push、不 merge main，除非用户另行要求。

---

# 36. 最终输出格式

```text
P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE:
PASS / FAIL / PARTIAL

OFFLINE_BASE_TAG:
p10.2-4lane-offline-ready

P10_3_SOURCE_COMMIT:
<hash>

P10_3_EVIDENCE_CHECKPOINT:
<hash>

P10_3_TAG:
<tag or NONE>

BRANCH:
p10.3/ax7020-stationary-4lane-hardware

WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_3

WORKTREE_CLEAN:
true/false

CURRENT_RUN_HARDWARE_AUTHORIZATION:
true/false

HARDWARE_ACTIONS_EXECUTED:
true/false

NETWORK_USED:
false

NO_HARDWARE_MOVEMENT:
true

NO_2H_QUALIFICATION_EXECUTED:
true

FIXED_BOARD_ID:
AX7020-F/JTAG:210249855178

ROTATING_BOARD_ID:
AX7020-R/JTAG:210512180081

ACTUAL_WIRING_SHA256:
<hash>

MODULE_INVENTORY_SHA256:
<hash>

ACTIVE_MODULES:
F0,F1,F2,F3,R0,R1,R2,R3

OLD_F1_STATUS:
QUARANTINED_NOT_ACCEPTED

FIXED_SHUTDOWN_BITSTREAM_SHA256:
<hash>

ROTATING_SHUTDOWN_BITSTREAM_SHA256:
<hash>

FIXED_FUNCTIONAL_BITSTREAM_SHA256:
<hash>

ROTATING_FUNCTIONAL_BITSTREAM_SHA256:
<hash>

FIXED_ELF_SHA256:
<hash>

ROTATING_ELF_SHA256:
<hash>

F2_MODULE_INTAKE:
PASS/FAIL

F3_MODULE_INTAKE:
PASS/FAIL

R2_MODULE_INTAKE:
PASS/FAIL

R3_MODULE_INTAKE:
PASS/FAIL

RAW_8X8_MATRIX:
PASS/FAIL

SAME_MODULE_RAW_ECHO_COUNT:
<value>

SAME_MODULE_ACCEPTED_DATA_COUNT:
0

CROSS_LANE_ACCEPTED_DATA_COUNT:
0

LANE0_4MBPS:
PASS/FAIL

LANE1_4MBPS:
PASS/FAIL

LANE2_4MBPS:
PASS/FAIL

LANE3_4MBPS:
PASS/FAIL

TWO_LANE_REGRESSION:
PASS/FAIL

FOUR_LANE_16MBPS_RAW:
PASS/FAIL

LANE_MASK_MATRIX:
PASS/FAIL

DEGRADED_MODE_MATRIX:
PASS/FAIL

FOUR_LANE_ARQ_SACK:
PASS/FAIL

FOUR_LANE_SCHEDULER:
PASS/FAIL

DMA_DDR_CACHE_FIXED:
PASS/FAIL

DMA_DDR_CACHE_ROTATING:
PASS/FAIL

STREAMING_64M_F_TO_R:
PASS/FAIL

STREAMING_64M_R_TO_F:
PASS/FAIL

F_TO_R_APPLICATION_GOODPUT_BPS:
<value>

R_TO_F_APPLICATION_GOODPUT_BPS:
<value>

F_TO_R_8MBPS_TARGET:
PASS/FAIL

R_TO_F_8MBPS_TARGET:
PASS/FAIL

F_TO_R_9P6MBPS_STRETCH:
PASS/FAIL

R_TO_F_9P6MBPS_STRETCH:
PASS/FAIL

STATIONARY_30MIN:
PASS/FAIL

RUNTIME_SECONDS:
<value>

COMMITTED_BYTES_F_TO_R:
<value>

COMMITTED_BYTES_R_TO_F:
<value>

MAX_DUTY_F0:
<value>

MAX_DUTY_F1:
<value>

MAX_DUTY_F2:
<value>

MAX_DUTY_F3:
<value>

MAX_DUTY_R0:
<value>

MAX_DUTY_R1:
<value>

MAX_DUTY_R2:
<value>

MAX_DUTY_R3:
<value>

CRC_BAD:
0

SHA_MISMATCH:
0

PARTIAL_COMMIT:
0

DUPLICATE_COMMIT:
0

STALE_COMMIT:
0

RETRY_EXHAUSTED:
0

DESCRIPTOR_LEAK:
0

DOUBLE_COMPLETION:
0

DEADLOCK:
0

DUTY_VIOLATION:
0

CONTINUOUS_HIGH_VIOLATION:
0

SHUTDOWN_FIXED:
PASS/FAIL

SHUTDOWN_ROTATING:
PASS/FAIL

EXTERNAL_4LANE_POWER_ACCEPTANCE:
PENDING_EXTERNAL_MEASUREMENT or PASS_WITH_DIRECT_EVIDENCE

EXTERNAL_TFDU_DUTY:
PENDING_EXTERNAL_MEASUREMENT

P11_STATUS:
NOT_STARTED

PASS:
<list>

FAIL:
<list>

NONBLOCKING_RESULTS:
<list>

GENERATED_EVIDENCE:
<list>

NEXT_RECOMMENDED_STAGE:
USER_DECISION_AFTER_P10_3
```

---

# 37. Definition of Done

P10.3 完成意味着：

```text
8个TFDU模块均有唯一身份；
F2/F3/R2/R3完成物理入库验收；
实际4-lane接线与授权hash一致；
两端4-lane shutdown和functional artifacts不可变；
8×8 raw/echo/crosstalk矩阵通过；
lane0..lane3均双向4 Mbit/s通过；
lane0/1既有2-lane基线无回归；
4-lane 16 Mbit/s aggregate RAW capability通过；
所有lane mask和4→3→2→1降级通过；
4-lane selective-repeat/SACK/scheduler/retry migration通过；
双向64 MiB streaming通过；
F→R和R→F均达到>=8 Mbit/s application goodput；
30分钟正式运行无完整性、协议、descriptor或安全错误；
两端shutdown可确认；
所有PASS绑定board、module、wiring、artifact、run和raw evidence。
```

P10.3 完成不意味着：

```text
P11 handover通过；
8×32 full ring通过；
600 rpm通过；
Ethernet/SPI通过；
2+2或4+4全双工通过；
physical GLOBAL_PERMIT最终实现通过；
external供电/duty测量通过；
产品最终验收通过。
```

现在开始执行本 Goal。物理布置和新授权缺失时，只允许完成 repository intake、artifact准备和 dry-run；物理前置条件及授权满足后，按风险递增顺序完成正式 4-lane 硬件验收。
