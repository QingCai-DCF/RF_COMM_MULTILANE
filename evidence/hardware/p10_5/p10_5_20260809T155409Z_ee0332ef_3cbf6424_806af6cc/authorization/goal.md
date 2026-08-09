# RF_COMM_MULTILANE — P10.5 2+2 双向架构实现与硬件验收 Goal

## 从“单一 bundle-wide direction 不支持”推进到真实并发双向数据面

```text
DOCUMENT_TYPE:
CODEX_EXECUTION_GOAL

STAGE:
P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE

STAGE_CLASS:
ARCHITECTURE_EXTENSION_PLUS_AUTHORIZED_HARDWARE_ACCEPTANCE

SOURCE_AUDIT_PACKAGE_SHA256:
6c351c7f7fdcac9d1a2cead7548b940d0345c6e1cc7e48d7e3783c7c38e3c904

P10_4_STATUS:
PASS_WITH_NONBLOCKING_LIMITS

P10_4_FINAL_COMMIT:
7987e6385b65fa2c7ed7d3a008c1ecbdf323ffa8

P10_4_ARTIFACT_SOURCE_COMMIT:
6ff17d33a0ea111fbd796899c49decbfa339e2c1

P10_4_EVIDENCE_CHECKPOINT:
f53d98252dfa85d73f35d49ebf5dc01323bcb4e7

P10_4_PASS_TAG:
p10.4-autonomous-4lane-hardening-pass

P10_4_COMPOSITE_RUN_ID:
p10_4_composite_5da414ba_f53d9825

P10_4_TWO_PLUS_TWO_RESULT:
FAIL_WITH_EVIDENCE

P10_4_TWO_PLUS_TWO_CAPABILITY:
UNSUPPORTED_SINGLE_BUNDLE_DIRECTION

P10_4_TWO_PLUS_TWO_TX_EXECUTED:
false

P10_4_TWO_PLUS_TWO_F_TO_R_BPS:
0

P10_4_TWO_PLUS_TWO_R_TO_F_BPS:
0

P10_4_HARDWARE_SHUTDOWN:
fixed=PASS
rotating=PASS

P10_4_CURRENT_RUN_HARDWARE_AUTHORIZATION:
false

RECOMMENDED_P10_4_CLOSED_TAG:
p10.4-autonomous-4lane-hardening-closed

RECOMMENDED_BRANCH:
p10.5/dual-direction-2plus2

RECOMMENDED_WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_5

FIXED_ENDPOINT:
AX7020-F/JTAG:210249855178

ROTATING_ROLE_ENDPOINT:
AX7020-R/JTAG:210512180081

ACTIVE_MODULES:
F0=A0019
F1=B0012
F2=B0019
F3=B0020
R0=A0010
R1=A0017
R2=B0023
R3=B0025

LANE0:
F0 <-> R0

LANE1:
F1 <-> R1

LANE2:
F2 <-> R2

LANE3:
F3 <-> R3

PRIMARY_2PLUS2_PARTITION:
F_TO_R_MASK=0x3
R_TO_F_MASK=0xC

MAX_LANE_MASK:
0xF

NETWORK_ALLOWED:
false

ETHERNET_REQUIRED:
false

SPI_REQUIRED:
false

HARDWARE_MOVEMENT_ALLOWED:
false

ROTATION_ALLOWED:
false

REALIGNMENT_ALLOWED:
false

REWIRING_ALLOWED:
false

MODULE_REPLACEMENT_ALLOWED:
false

EXTERNAL_INSTRUMENTATION_REQUIRED:
false

TWO_HOUR_TEST_REQUIRED:
false

MAX_SINGLE_FORMAL_RUN_SECONDS:
1800

MINIMUM_INTERSTAGE_COOLDOWN_RATIO:
0.5

AUTOMATION_ONLY:
true

NO_USER_HOLD_POINTS:
true

NO_FURTHER_USER_CONFIRMATION:
true

ASK_USER_FOR_CONTINUATION:
false

CURRENT_RUN_HARDWARE_AUTHORIZATION:
GRANTED_WHEN_USER_SUBMITS_THIS_GOAL_TO_CODEX

ON_SEVERE_BLOCKER:
SHUTDOWN_BOTH_ENDPOINTS
SAVE_ALL_EVIDENCE
FAIL_CLOSED
STOP_WITHOUT_REQUESTING_USER_ACTION

P11_STATUS:
NOT_STARTED
```

提交本 Goal 给 Codex 即构成本次 P10.5 的限定 current-run 硬件授权。Codex 不得再要求用户确认接线、模块身份、板卡角色、是否构建、是否 program、是否运行 ELF、是否执行测试、是否重试或是否继续。

---

# 1. 审计结论与根因

P10.4 的 4-lane 半双工核心结果保持有效：

```text
4-lane half-duplex >=8 Mbit/s/方向:
PASS

64 MiB streaming:
PASS

128 MiB streaming:
PASS_NONBLOCKING

lane degrade/recovery:
PASS

direction switch:
PASS

reset recovery:
PASS

8×8 digital echo/crosstalk:
PASS

mixed formal:
PASS

safety and integrity:
PASS
```

P10.4 的 2+2 阶段没有产生一次失败的数据传输。直接 evidence 表明：

```text
capability:
UNSUPPORTED_SINGLE_BUNDLE_DIRECTION

TX_EXECUTED:
false

F_TO_R_BPS:
0

R_TO_F_BPS:
0
```

因此当前失败不是：

```text
CRC错误
光学串扰
DMA吞吐不足
PS性能不足
协议死锁
TFDU安全违规
```

当前直接根因是：

```text
冻结 artifact 只有一套 bundle-wide direction 状态；
整个 active lane bundle 在同一时刻只能属于一个方向；
无法把 lane0/1 分配给 F→R，同时把 lane2/3 分配给 R→F。
```

P10.5 不再重复“是否是物理问题”的盲目搜索。必须先实现真正的 simultaneous dual-direction architecture，再执行直接硬件验收。

---

# 2. P10.5 总目标

P10.5 必须完成：

```text
1. 冻结并收口 P10.4 PASS_WITH_NONBLOCKING_LIMITS；
2. 保留 P10.4 2+2 未发射和 capability blocker 的 immutable evidence；
3. 增加 versioned simultaneous bidirectional capability；
4. 将 bundle-wide direction 改为 disjoint per-direction lane-role masks；
5. 建立 F→R 和 R→F 两个独立、可并发运行的数据面 context；
6. 实现双向 ACK/SACK piggyback 和 control-only fallback；
7. 允许两端同时运行 TX DMA 和 RX DMA；
8. 保持单模块 TX/RX 互斥和全部 P8C 安全合同；
9. 保持原 4-lane half-duplex compatibility；
10. 完成离线 reference、XSIM、software、Vivado 和资源/时序验证；
11. 生成新的 immutable bitstream/XSA/BSP/ELF；
12. 在现有接线、不移动硬件的条件下实际执行 1+1、2+1、1+2 和 2+2；
13. primary 2+2 每方向 application goodput >=4.0 Mbit/s；
14. 双向 simultaneous 64 MiB streaming；
15. 完成 30 分钟持续 2+2 正式运行；
16. 两端自动 shutdown；
17. 生成完整 evidence、source commit、checkpoint 和 annotated tag。
```

---

# 3. 明确不做的内容

P10.5 不执行：

```text
P11 handover
ABZ
旋转
600 rpm
8×32 full ring
Ethernet
SPI
2小时测试
外部示波器、电流探头或功率计
硬件移动
光学调角
重新接线
模块替换
最终4+4产品验收
physical GLOBAL_PERMIT最终验收
external TFDU duty验收
product-final验收
```

即使 P10.5 通过，也只能形成：

```text
当前双 AX7020、静止4-lane硬件上的2+2 simultaneous bidirectional prototype PASS
```

不得写成：

```text
FINAL_4PLUS4_FULL_DUPLEX: PASS
```

---

# 4. 严重阻塞处理

仅以下情况属于严重阻塞：

```text
现有接线与冻结inventory/hash不一致并有损坏风险
板卡身份无法唯一绑定
JTAG有界重试后仍无法枚举
必须人工移动、重新接线、调角或替换模块
发现VCC/GND或output-to-output风险
任一端无法确认shutdown
出现自主发射、duty、continuous-high或final TX kill安全违规
必须修改PROJECT_CONSTRAINTS.txt
```

发生严重阻塞时，Codex必须：

```text
停止新TX
撤销arm
active lane masks=0
abort/reclaim descriptors
请求SD shutdown
program两端shutdown bitstream
保存所有日志
将stage标记FAIL_CLOSED
停止任务
```

不得向用户请求人工介入。

普通软件、RTL、Vivado、BSP、ELF、DMA、协议、测试或 evidence 错误必须由 Codex 自主修复。

---

# 5. P10.4 Immutable Closeout

## 5.1 验证

自动发现并验证：

```text
P10.4 branch/worktree
final commit 7987e638...
artifact source 6ff17d33...
evidence checkpoint f53d9825...
pass tag p10.4-autonomous-4lane-hardening-pass
composite run p10_4_composite_5da414ba_f53d9825
```

验证：

```text
P10.4 status=PASS_WITH_NONBLOCKING_LIMITS
two_plus_two=FAIL_WITH_EVIDENCE
capability=UNSUPPORTED_SINGLE_BUNDLE_DIRECTION
tx_executed=false
shutdown fixed/rotating PASS
authorization false/consumed
```

## 5.2 不修改冻结 evidence

不得修改：

```text
P10.4 raw hardware run roots
P10.4 composite manifest
P10.4 pass tag
P10.4 final summary
P10.4 two_plus_two requirement closure
parent/resume authorization
shutdown evidence
```

## 5.3 Closeout metadata

生成：

```text
evidence/generated/p10_4_closeout_summary.md
evidence/generated/p10_4_closeout_summary.json
evidence/generated/p10_4_git_checkpoint_metadata.json
```

至少记录：

```text
final commit
artifact source commit
evidence checkpoint
pass tag object/target
component run IDs
component checkpoints
artifact hashes
2+2 capability result
TX_EXECUTED=false
shutdown
authorization consumed
P11 NOT_STARTED
```

## 5.4 Closeout tag

创建：

```text
p10.4-autonomous-4lane-hardening-closed
```

annotated tag 指向新的纯离线 closeout commit。

不得移动：

```text
p10.4-autonomous-4lane-hardening-pass
```

## 5.5 Mainline

若可 fast-forward：

```text
将closed baseline fast-forward到main
```

若不能：

```text
不rebase冻结历史
创建integration分支
只自动解决生成状态文件的确定性冲突
非确定性源码冲突 -> FAIL_CLOSED
```

远端推送失败不阻塞本地 P10.5；自动生成 bundle 和失败 evidence。

---

# 6. P10.5 Worktree

从：

```text
p10.4-autonomous-4lane-hardening-closed
```

创建：

```text
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_5
```

分支：

```text
p10.5/dual-direction-2plus2
```

命令等价于：

```powershell
git worktree add `
  -b p10.5/dual-direction-2plus2 `
  C:\Users\user\Documents\RF_COMM_MULTILANE_P10_5 `
  p10.4-autonomous-4lane-hardening-closed
```

如果已存在：

```text
验证path、branch、HEAD、base和clean状态
不得删除或reset未知worktree
```

---

# 7. Repository Intake

生成：

```text
evidence/generated/p10_5_repo_intake.md
evidence/generated/p10_5_repo_intake.json
```

记录：

```text
branch
HEAD
base tag
P10.4 identities
git status
PROJECT_CONSTRAINTS hash
AGENTS hash
project_state hash
requirements hash
register-map hash
4-lane wiring hash
8-module inventory hash
fixed/rotating profile hash
tool versions
current authorization
start timestamp
```

先运行：

```text
P10.4 verify-existing
P10.3 verify-existing
P10.2 verify-existing
P10.1R verify-existing
P8C safety verify-existing
state/requirements consistency
```

冻结基线失败时不得修改 architecture 或连接硬件。

---

# 8. Canonical Dual-Direction Configuration

新增：

```text
config/p10_5_dual_direction.yaml
```

至少包含：

```text
protocol_capability_version
operating_mode
lane_count
active_lane_mask
f_to_r_lane_mask
r_to_f_lane_mask
role_epoch_width
direction_id_width

per_direction_sequence_width
per_direction_outstanding
per_direction_sack_window
per_direction_rx_reorder_window
per_direction_retry_limit
per_direction_ack_threshold
per_direction_ack_max_delay
per_direction_receiver_credit

per_direction_tx_ring_depth
per_direction_rx_ring_depth
per_direction_object_queue_depth
per_direction_stream_queue_depth

control_queue_depth
control_priority_policy
piggyback_enable
control_only_ack_fallback
control_starvation_limit

performance_targets
formal_runtime
```

Operating modes：

```text
LEGACY_BUNDLE_HALF_DUPLEX
SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL
```

默认 half-duplex profile不得改变。

由该 YAML 生成：

```text
SystemVerilog package
C header
Python constants
register documentation
capability table
```

禁止在 RTL、PS、host 和测试中重复手写核心 mask/queue 常量。

---

# 9. Lane-Role Mask Architecture

## 9.1 Canonical masks

新增：

```text
ACTIVE_LANE_MASK
F_TO_R_LANE_MASK
R_TO_F_LANE_MASK
```

硬不变量：

```text
F_TO_R_LANE_MASK & R_TO_F_LANE_MASK == 0

(F_TO_R_LANE_MASK | R_TO_F_LANE_MASK)
subset of ACTIVE_LANE_MASK

disabled lanes不属于任何方向
```

2+2 primary：

```text
ACTIVE_LANE_MASK=0xF
F_TO_R_LANE_MASK=0x3
R_TO_F_LANE_MASK=0xC
```

## 9.2 Endpoint-local mask derivation

固定端：

```text
LOCAL_TX_MASK = F_TO_R_LANE_MASK
LOCAL_RX_MASK = R_TO_F_LANE_MASK
```

旋转角色端：

```text
LOCAL_TX_MASK = R_TO_F_LANE_MASK
LOCAL_RX_MASK = F_TO_R_LANE_MASK
```

必须证明两端 mask 互补且一致。

## 9.3 Atomic role commit

角色配置使用：

```text
shadow masks
validation
quiet/commit boundary
atomic active commit
ROLE_EPOCH increment
readback
```

禁止在以下状态改变角色：

```text
lane正在发送partial frame
descriptor处于不可切换边界
RX decoder存在partial frame
```

非法 mask：

```text
重叠mask
mask超active
空的必需方向
未知lane bit
```

必须拒绝且不改变 active config。

## 9.4 Half-duplex compatibility

Legacy F→R：

```text
F_TO_R_LANE_MASK=ACTIVE_LANE_MASK
R_TO_F_LANE_MASK=0
```

Legacy R→F：

```text
F_TO_R_LANE_MASK=0
R_TO_F_LANE_MASK=ACTIVE_LANE_MASK
```

P10.3/P10.4 half-duplex vectors必须 bit-exact 或明确兼容。

---

# 10. Versioned Protocol Capability

新增 capability：

```text
CAP_SIMULTANEOUS_BIDIRECTIONAL_V1
```

能力协商至少包括：

```text
protocol version
simultaneous bidirectional support
max lane count
max TX lanes
max RX lanes
mask width
per-direction outstanding
per-direction SACK width
piggyback support
control-only ACK support
role epoch support
```

如果任一 peer 不支持：

```text
明确 fallback 到 LEGACY_BUNDLE_HALF_DUPLEX
或拒绝2+2配置
```

不得静默解释不同 frame 语义。

---

# 11. Frame Direction and Role Epoch

每个 vNext frame 必须携带或从受保护上下文明确确定：

```text
DIRECTION_ID:
F_TO_R / R_TO_F

ROLE_EPOCH
SESSION_EPOCH
SEQUENCE
FRAME_TYPE
LANE_ID
PATH_EPOCH
```

要求：

```text
direction受CRC保护
role epoch stale拒绝
同一sequence只在其direction context中唯一
不同direction可使用相同sequence值
```

不允许通过物理 lane mask隐式猜 direction 后跳过 frame-level consistency check。

---

# 12. Independent Per-Direction L2 Contexts

系统必须存在两个逻辑方向 context：

```text
DIR_F_TO_R
DIR_R_TO_F
```

每个方向独立维护：

```text
TX selective-repeat window
RX reorder window
sequence base
next sequence
ACK base
SACK bitmap
receiver credit
timeout/retry
duplicate history
gap history
completion queue
performance counters
```

硬不变量：

```text
一个方向window full不能直接阻塞另一方向
一个方向ACK丢失不能清空另一方向
一个方向object abort不能清空另一方向
同方向duplicate commit=0
跨方向sequence collision不会误提交
```

共享资源允许：

```text
payload memory
timer engine
DMA infrastructure
register bus
```

但必须通过：

```text
direction tag
owner
generation
bounded arbitration
```

隔离。

---

# 13. Session、Role Epoch 和 Reset

## 13.1 Session

endpoint session仍可为节点级，但所有状态必须带 direction ID。

## 13.2 Role epoch

lane role mask原子变化时：

```text
ROLE_EPOCH++
```

旧 role epoch frame：

```text
拒绝
不ACK为当前frame
不推进window
不写DMA
不提交object
```

## 13.3 Direction-scoped abort

允许：

```text
abort F→R stream
同时 R→F继续
```

不得把普通 stream abort实现为全局bundle reset。

## 13.4 Endpoint reset

真实 endpoint reset可使两方向session重新acquire，但必须：

```text
stale commit=0
descriptor leak=0
另一端有界恢复
```

---

# 14. ACK/SACK Piggyback

## 14.1 方向关系

F→R DATA 的 ACK/SACK 从 R 发向 F。

在 2+2 模式下优先通过：

```text
R→F application DATA frame piggyback
```

发送。

R→F DATA 的 ACK/SACK 同理通过 F→R DATA piggyback。

## 14.2 Piggyback payload

每个 DATA frame可带：

```text
opposite-direction ACK base
opposite-direction SACK bitmap
receiver credit
ACK flags
```

必须受 frame CRC 保护。

## 14.3 Control-only fallback

如果对应反向方向没有应用 DATA，ACK max delay到期时：

```text
在该方向分配的TX lane group发送control-only ACK/SACK bundle
```

不得切换整个bundle方向。

## 14.4 ACK priority

ACK/control队列必须：

```text
高于普通新DATA
低于final TX kill/safety
有bounded starvation
```

## 14.5 Deadlock prevention

禁止：

```text
F→R等待R→F ACK
同时R→F等待F→R ACK
而两个control queue都被DATA堵塞
```

必须证明：

```text
ACK max delay bounded
control admission guaranteed
receiver credit更新bounded
```

---

# 15. Partition-Aware Scheduler

每个 endpoint 本地只有其 LOCAL_TX_MASK 可进入 TX scheduler。

scheduler 输入：

```text
direction context
local TX mask
lane ready
lane health
duty headroom
same-module RX admission
mapping/path epoch
receiver credit
queue occupancy
control priority
```

scheduler不得：

```text
选择LOCAL_RX_MASK中的lane发TX
选择disabled lane
让一个方向的故障阻塞另一方向
```

在 2-lane TX group中：

```text
health-aware weighted fairness
retry migration
ACKed frame不迁移
```

---

# 16. Per-Module PHY and Safety

每个 TFDU 仍是物理半双工模块。

必须满足：

```text
module TX physical active
和
module RX frame admission
永不同时有效
```

2+2 时每个 endpoint：

```text
2 modules TX
2 modules RX
```

但每个单模块只承担一个角色。

保持：

```text
same-module raw echo可观察
same-module accepted DATA=0
same-module accepted ACK/SACK=0
cross-lane accepted DATA=0
other lanes不被blank
```

保持全部安全合同：

```text
startup >=500 us
continuous Txd HIGH <=1 us
1 ms exact sliding duty
design target <=18%
hard limit <20%
single active-high GLOBAL_PERMIT per endpoint
permit drop直达final TX kill
explicit re-arm
```

禁止增加：

```text
per-direction GLOBAL_PERMIT
per-lane GLOBAL_PERMIT
双permit
permit heartbeat
```

---

# 17. AXI-Stream and DMA Concurrency

每个 endpoint 在 2+2 时同时执行：

```text
local TX DMA
local RX DMA
```

要求：

```text
TX/RX rings独立
TX/RX completion独立
direction metadata明确
cache flush/invalidate可并发或有界仲裁
一个ring full不覆盖另一个ring
```

descriptor新增或明确：

```text
direction ID
role epoch
stream/object ID
lane policy
generation
completion direction
```

禁止：

```text
全局bundle direction lock
TX启动时停止RX DMA
RX completion时阻塞TX submit
逐frame host/MMIO干预
```

---

# 18. Object and Streaming Contexts

每方向独立：

```text
object queue
stream queue
CRC32 state
SHA256 state
atomic publish
abort/restart
```

2+2 formal负载必须允许：

```text
F→R 64 MiB stream
和
R→F 64 MiB stream
同时进行
```

一个方向故障时：

```text
该方向错误object不commit
另一方向可继续或有界暂停
```

---

# 19. Register Map

扩展版本化寄存器：

```text
DUAL_DIRECTION_CAPS
OPERATING_MODE
ACTIVE_LANE_MASK
F_TO_R_LANE_MASK
R_TO_F_LANE_MASK
ROLE_EPOCH
ROLE_COMMIT_STATUS
ROLE_CONFIG_ERROR
```

每方向：

```text
TX_WINDOW_OCCUPANCY
RX_WINDOW_OCCUPANCY
ACK_BASE
SACK_BITMAP
RECEIVER_CREDIT
RETRY
TIMEOUT
DATA_BYTES
ACK_BYTES
CONTROL_BYTES
APPLICATION_COMMITTED_BYTES
GOODPUT
```

每 endpoint：

```text
LOCAL_TX_MASK
LOCAL_RX_MASK
TX_DMA_OCCUPANCY
RX_DMA_OCCUPANCY
TX_AXIS_STALL
RX_AXIS_STALL
CONTROL_QUEUE_OCCUPANCY
```

旧 half-duplex寄存器保持兼容或明确deprecated alias。

---

# 20. PS Firmware

新增 API：

```text
p10_5_query_dual_direction_caps()
p10_5_stage_role_masks()
p10_5_commit_role_masks()
p10_5_start_direction_stream()
p10_5_stop_direction_stream()
p10_5_abort_direction_stream()
p10_5_snapshot_direction()
p10_5_clear_direction_errors()
```

PS runtime必须：

```text
同时管理TX和RX ring
同时推进F→R和R→F object service
不持有全局direction mutex
日志不在fast path
```

Host正式测试只：

```text
CONFIG
START
低频SNAPSHOT
STOP
```

不得逐object或逐segment驱动。

---

# 21. Offline Reference Model

建立：

```text
scripts/model_p10_5_dual_direction.py
```

模型包含：

```text
two direction contexts
disjoint lane masks
role epoch
selective-repeat
SACK
piggyback ACK
control-only ACK
receiver credit
DMA TX/RX
same-module admission
duty
fault/retry
```

固定不变量：

```text
wrong-direction lane TX=0
mask overlap=0
same-module TX/RX overlap=0
duplicate commit=0
stale role/session commit=0
descriptor leak=0
deadlock=0
```

---

# 22. Mask Verification Matrix

## 22.1 1+1 ordered pairs

4 条 lane 中选择：

```text
1 lane F→R
1 different lane R→F
```

共 12 个 ordered pairs，全部离线验证。

## 22.2 2+1 and 1+2

全部合法 disjoint mask组合离线验证。

## 22.3 2+2 directed partitions

全部 6 个 directed 2+2 配置：

```text
F→R=0x3, R→F=0xC
F→R=0xC, R→F=0x3

F→R=0x5, R→F=0xA
F→R=0xA, R→F=0x5

F→R=0x9, R→F=0x6
F→R=0x6, R→F=0x9
```

要求：

```text
role commit成功
两方向同时有TX
两方向同时有RX
无mask冲突
```

---

# 23. Offline Fault Matrix

同时双向运行时注入：

```text
F→R DATA loss
R→F DATA loss
F→R ACK loss
R→F ACK loss
一方向duplicate
一方向reorder
一方向stream abort
一方向window full
一方向receiver credit low
lane unavailable
lane recovery
DMA backpressure
endpoint reset
role epoch change
```

必须证明：

```text
方向隔离
ACK/control不饿死
无双向deadlock
另一方向不被无界阻塞
```

---

# 24. Offline Performance Model

## 24.1 RAW capability

2+2：

```text
2 lanes × 4 Mbit/s
=8 Mbit/s RAW per direction
```

## 24.2 Application hard target

```text
>=4.0 Mbit/s per direction
```

## 24.3 Stretch

```text
>=4.8 Mbit/s per direction
```

stretch非阻塞。

## 24.4 Model inputs

```text
frame payload
duty
same-module guard
piggyback overhead
control-only ACK rate
SACK
PER/retry
DMA
PS generation/verification
lane utilization
```

离线硬门：

```text
P10_5_2PLUS2_4MBPS_FEASIBILITY:
PASS
```

若模型不能在完整安全和完整性条件下达到4.0：

```text
FAIL_WITH_ARCHITECTURE_BLOCKER
不得连接硬件
```

---

# 25. RTL / XSIM Verification

至少新增：

```text
tb_p10_5_role_mask_commit
tb_p10_5_half_duplex_compatibility
tb_p10_5_dual_direction_l2
tb_p10_5_ack_piggyback
tb_p10_5_control_only_ack
tb_p10_5_bidirectional_dma
tb_p10_5_1plus1_mask_matrix
tb_p10_5_2plus1_mask_matrix
tb_p10_5_2plus2_partitions
tb_p10_5_role_epoch_stale
tb_p10_5_direction_abort_isolation
tb_p10_5_dual_direction_faults
tb_p10_5_dual_endpoint_integration
```

时钟：

```text
independent fixed/rotating clocks
independent PS/DMA clocks
different phase relationships
```

所有 compile/elaborate/run return code 0。

---

# 26. Random and Exhaustive Verification

固定 seeds：

```text
1
7
17
31
127
1024
20260809
22002200
```

最低：

```text
100,000 dual-direction protocol events
50,000 ACK/control events
50,000 DMA/backpressure events
25,000 role/reset events
```

缩减穷举：

```text
4-bit sequence
small windows
small rings
all legal masks
all role commits
```

---

# 27. Legacy Regression

必须保持：

```text
P10.4 half-duplex >=8 Mbit/s
P10.3 4-lane half-duplex
P10.1R 2-lane speed/stability
P8C safety
```

本阶段不得让新增 dual-direction 支持降低原 half-duplex scoped PASS。

---

# 28. Dual AX7020 Build

构建：

```text
AX7020-F P10.5 dual-direction top
AX7020-R P10.5 dual-direction top
shutdown bitstreams
XSA
BSP
ELF
host tools
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
LUT/FF/BRAM/DSP
half-duplex baseline delta
dual-direction state delta
critical path
```

不得通过删除 safety/CRC/recovery满足资源。

---

# 29. Immutable Artifacts

正式文件使用：

```text
artifacts/p10_5/<source>/<sha256>/
```

授权记录必须绑定：

```text
source commit
fixed/rotating shutdown bitstream
fixed/rotating functional bitstream
fixed/rotating XSA/BSP/ELF
board IDs
wiring hash
module inventory hash
register map
dual-direction config
```

旧 P10.4 artifact 仅用于对照，不能用于 P10.5 PASS。

---

# 30. Current-Run Hardware Authorization

本 Goal 本身授权 Codex执行：

```text
构建和冻结新artifact
启动/连接hw_server
使用Hardware Manager batch和XSDB/JTAG
program两端shutdown和functional bitstream
下载并运行两端ELF
使用DDR、DMA、UART、ILA/VIO和寄存器
在lane mask 0x1..0xF内执行受控TFDU发射
运行1+1、2+1、1+2、2+2
运行同时双向64 MiB streaming
运行最长1800秒formal test
执行数字fault/reset/recovery
异常时shutdown两端
```

不授权：

```text
Ethernet
SPI
移动、旋转、调角、重新接线、换模块
lane mask >0xF
2小时
P11/P12/P13/P14/P15 promotion
```

---

# 31. Hardware Stage 0 — Safe Start

1. 唯一识别 F/R；
2. program两端shutdown；
3. 验证safe state；
4. program新P10.5 fixed candidate；
5. 验证fixed safe boot；
6. program新P10.5 rotating candidate；
7. 验证rotating safe boot；
8. 下载两端ELF；
9. 保持unarmed；
10. 读取capability/build/profile/register/config hashes；
11. 清counter；
12. receive-only；
13. 等待>=500 µs；
14. 显式arm当前case。

safe boot：

```text
Txd[3:0]=0
endpoint armed=0
LOCAL_TX_MASK=0
outstanding physical attempt=0
无自主TX
```

---

# 32. Hardware Stage 1 — Capability and Register Gate

必须读取：

```text
CAP_SIMULTANEOUS_BIDIRECTIONAL_V1=1
max lane count=4
mask width=4
per-direction windows有效
piggyback support=1
control-only ACK support=1
```

提交 primary masks：

```text
ACTIVE=0xF
F→R=0x3
R→F=0xC
```

验证：

```text
fixed local TX=0x3
fixed local RX=0xC
rotating local TX=0xC
rotating local RX=0x3
role epoch一致
```

如果 capability仍为 unsupported：

```text
不得发射
FAIL_WITH_ARCHITECTURE_EVIDENCE
shutdown
```

---

# 33. Hardware Stage 2 — 1+1 Matrix

执行全部 12 个 ordered lane pairs。

每个：

```text
10-second smoke
simultaneous bidirectional
small autonomous objects
```

要求：

```text
TX_EXECUTED=true
两方向committed bytes>0
CRC/SHA=0
same-module accepted=0
cross-lane accepted=0
deadlock=0
```

该阶段用于验证所有lane的同时TX/RX角色组合。

---

# 34. Hardware Stage 3 — 2+1 / 1+2

执行至少覆盖每条 lane作为：

```text
双lane TX group成员
单lane TX group成员
RX group成员
```

每case：

```text
20 seconds
```

要求：

```text
双向均有进展
无全局direction lock
ACK/control正常
```

---

# 35. Hardware Stage 4 — All 2+2 Partitions

执行六个 directed partitions：

```text
0x3/0xC
0xC/0x3
0x5/0xA
0xA/0x5
0x9/0x6
0x6/0x9
```

每case：

```text
30 seconds
```

Mandatory：

```text
TX_EXECUTED=true
F→R committed bytes>0
R→F committed bytes>0
CRC/SHA错误=0
same-module accepted=0
cross-lane accepted=0
```

记录每分区 goodput 和每lane利用率。

---

# 36. Hardware Stage 5 — Dynamic Role Commit

在无partial frame的 commit window中执行：

```text
0x3/0xC
→0x5/0xA
→0x9/0x6
→0x3/0xC
```

要求：

```text
ROLE_EPOCH单次递增
旧epoch frame拒绝
无错误对象commit
切换后两方向继续
```

该测试不允许在 frame 中途强切。

---

# 37. Hardware Stage 6 — Primary 2+2 Performance

配置：

```text
F→R=0x3
R→F=0xC
```

同时运行：

```text
duration>=300 s
board-autonomous
```

硬门：

```text
F→R APPLICATION_GOODPUT >=4,000,000 bit/s
R→F APPLICATION_GOODPUT >=4,000,000 bit/s
```

stretch：

```text
>=4,800,000 bit/s
```

stretch非阻塞。

要求：

```text
timer crosscheck<=1%
host not in fast path
TX_EXECUTED=true
```

---

# 38. Hardware Stage 7 — Simultaneous 64 MiB Streaming

同时启动：

```text
F→R:
至少5 × 64 MiB

R→F:
至少5 × 64 MiB
```

要求：

```text
两个方向同时存在active stream
CRC32正确
SHA256正确
atomic commit
descriptor leak=0
double completion=0
```

不能先完成一个方向再开始另一个方向并称为 simultaneous。

---

# 39. Hardware Stage 8 — Direction-Isolated Faults

在 primary 2+2 下依次：

```text
F→R single DATA drop
R→F single DATA drop
F→R ACK drop
R→F ACK drop
abort F→R stream
abort R→F stream
disable lane0
disable lane2
DMA backpressure fixed TX
DMA backpressure rotating TX
```

要求：

```text
受影响方向有界恢复
另一方向保持进展或有界轻微退化
错误对象不commit
恢复后双向clean stream成功
```

---

# 40. Hardware Stage 9 — 30-Minute Formal 2+2

配置：

```text
F→R mask=0x3
R→F mask=0xC
board autonomous
continuous simultaneous streams
```

总计：

```text
1800 seconds
```

建议：

```text
0..120 s:
warm-up

120..1800 s:
formal simultaneous window
```

整个 formal window：

```text
F→R >=4.0 Mbit/s
R→F >=4.0 Mbit/s
```

硬错误：

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

same-module accepted DATA=0
same-module accepted ACK/SACK=0
cross-lane accepted DATA=0
non-target CRC-valid accepted frame=0

duty violation=0
continuous-high violation=0
illegal one-hot=0
role mask overlap=0
```

---

# 41. Runtime / Rest Policy

每个 hardware stage：

```text
runtime <= configured stage limit
shutdown-after verified
cooldown >=0.5 × measured runtime
```

最大单stage连续运行：

```text
1800 s
```

cooldown自动执行，不需要用户操作。

---

# 42. Shutdown

任何 stage 结束、失败、异常、Ctrl+C、timeout 或 JTAG错误：

```text
停止两方向新TX
停止performance/streaming
撤销arm
LOCAL_TX_MASK=0
abort/reclaim descriptors
请求SD shutdown
program两端shutdown bitstream
保存trace和日志
```

Mandatory：

```text
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
```

无法确认shutdown：

```text
P10_5=FAIL_CLOSED_SHUTDOWN_UNCONFIRMED
```

---

# 43. Evidence

Run ID：

```text
p10_5_<UTC>_<source>_<fixedbit>_<rotbit>
```

目录：

```text
evidence/hardware/p10_5/<run_id>/
```

子目录：

```text
authorization
artifacts
target_identity
safe_boot
capability
role_masks
one_plus_one
two_plus_one
two_plus_two_partitions
role_commit
performance
streaming_64m
faults
formal_30min
shutdown
raw_logs
final
```

Generated summaries：

```text
p10_5_repo_intake
p10_4_closeout
p10_5_architecture
p10_5_capability
p10_5_role_mask
p10_5_direction_contexts
p10_5_ack_piggyback
p10_5_dma_concurrency
p10_5_reference_model
p10_5_xsim
p10_5_fixed_build
p10_5_rotating_build
p10_5_software_build
p10_5_artifact_freeze
p10_5_authorization
p10_5_safe_boot
p10_5_1plus1
p10_5_2plus1
p10_5_2plus2_partitions
p10_5_role_commit
p10_5_performance
p10_5_streaming_64m
p10_5_faults
p10_5_formal_30min
p10_5_shutdown
p10_5_evidence_consistency
p10_5_final_summary
```

每项：

```text
.md
.json
```

---

# 44. Requirement IDs

新增：

```text
P10_5-CLOSE-001 P10.4 immutable closeout
P10_5-CAP-001 simultaneous bidirectional capability
P10_5-ROLE-001 disjoint direction masks
P10_5-ROLE-002 atomic role commit
P10_5-ROLE-003 stale role epoch rejection

P10_5-L2-001 independent F→R context
P10_5-L2-002 independent R→F context
P10_5-ACK-001 bidirectional ACK piggyback
P10_5-ACK-002 control-only ACK fallback
P10_5-ACK-003 no bidirectional ACK deadlock

P10_5-DMA-001 simultaneous TX/RX DMA
P10_5-DMA-002 direction-scoped descriptor ownership
P10_5-OBJ-001 simultaneous direction objects
P10_5-OBJ-002 direction-scoped abort

P10_5-SAFE-001 module TX/RX exclusion
P10_5-SAFE-002 one GLOBAL_PERMIT per endpoint
P10_5-SAFE-003 no mask overlap

P10_5-MASK-001 all 1+1 pairs
P10_5-MASK-002 2+1 and 1+2
P10_5-MASK-003 all directed 2+2 partitions

P10_5-PERF-001 F→R >=4 Mbit/s
P10_5-PERF-002 R→F >=4 Mbit/s
P10_5-STREAM-001 simultaneous 64 MiB
P10_5-SOAK-001 30-minute simultaneous 2+2
```

---

# 45. Project State

开始：

```text
current_program_stage:
P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE

p10_5_status:
IN_PROGRESS

current_run_hardware_authorization:
true
```

结束后：

```text
current_run_hardware_authorization:
false

last_hardware_authorization_consumed:
true
```

PASS：

```text
p10_5_status:
PASS

p10_5_2plus2_simultaneous_bidirectional:
PASS

p11_status:
NOT_STARTED
```

保持：

```text
P10.4 half-duplex PASS_WITH_NONBLOCKING_LIMITS
external power pending
external duty pending
physical permit pending
P11 pending
8×32 pending
600rpm pending
product final pending
```

---

# 46. Mandatory Exit Gates

```text
P10_4_BASELINE_RECHECK: PASS
P10_4_CLOSEOUT: PASS
P10_4_TWO_PLUS_TWO_FAILURE_PRESERVED: PASS

DUAL_DIRECTION_CAPABILITY: PASS
HALF_DUPLEX_BACKWARD_COMPATIBILITY: PASS

DIRECTION_MASK_DISJOINT: PASS
ATOMIC_ROLE_COMMIT: PASS
ROLE_EPOCH_STALE_REJECTION: PASS

F_TO_R_CONTEXT_INDEPENDENT: PASS
R_TO_F_CONTEXT_INDEPENDENT: PASS
ACK_PIGGYBACK: PASS
CONTROL_ONLY_ACK_FALLBACK: PASS
BIDIRECTIONAL_DEADLOCK_ZERO: PASS

SIMULTANEOUS_TX_RX_DMA: PASS
DIRECTION_DESCRIPTOR_ISOLATION: PASS
DIRECTION_ABORT_ISOLATION: PASS

ONE_PLUS_ONE_ALL_PAIRS: PASS
TWO_PLUS_ONE_MATRIX: PASS
TWO_PLUS_TWO_ALL_PARTITIONS: PASS
TWO_PLUS_TWO_TX_EXECUTED: true

PRIMARY_F_TO_R_4MBPS: PASS
PRIMARY_R_TO_F_4MBPS: PASS

SIMULTANEOUS_64M_F_TO_R_5X: PASS
SIMULTANEOUS_64M_R_TO_F_5X: PASS

FORMAL_30MIN_2PLUS2: PASS

CRC_BAD_ZERO: PASS
SHA_MISMATCH_ZERO: PASS
PARTIAL_DUPLICATE_STALE_ZERO: PASS
RETRY_EXHAUSTED_ZERO: PASS
DESCRIPTOR_LEAK_ZERO: PASS
DOUBLE_COMPLETION_ZERO: PASS
DEADLOCK_ZERO: PASS
TRANSPORT_TIMEOUT_ZERO: PASS

SAME_MODULE_ACCEPTED_DATA_ZERO: PASS
CROSS_LANE_ACCEPTED_DATA_ZERO: PASS
DUTY_VIOLATION_ZERO: PASS
CONTINUOUS_HIGH_VIOLATION_ZERO: PASS
ROLE_MASK_OVERLAP_ZERO: PASS

SHUTDOWN_FIXED: PASS
SHUTDOWN_ROTATING: PASS
EVIDENCE_CONSISTENCY: PASS
```

Nonblocking：

```text
F_TO_R_4P8MBPS_STRETCH
R_TO_F_4P8MBPS_STRETCH
REMOTE_PUSH
```

---

# 47. Failure Semantics

## PASS

全部 mandatory gates通过。

## PASS_WITH_NONBLOCKING_LIMITS

mandatory通过，但4.8 Mbit/s stretch或remote push未通过。

## FAIL_WITH_PERFORMANCE_EVIDENCE

双向功能、完整性和安全正确，但任一方向低于4.0 Mbit/s。

## FAIL_WITH_PHYSICAL_CROSSTALK_EVIDENCE

新architecture实际发射后出现：

```text
cross-lane accepted DATA
non-target CRC-valid accepted frames
错误对象提交风险
```

## FAIL_WITH_ARCHITECTURE_EVIDENCE

以下任一：

```text
capability仍unsupported
TX_EXECUTED=false
mask无法并发
双向ACK deadlock
```

## FAIL

以下任一：

```text
safe boot失败
错误对象提交
descriptor double completion
duty/stuck-high违规
无法确认shutdown
artifact/evidence不一致
```

无论 P10.5 结果如何，P10.4 已通过的 half-duplex scoped acceptance保持。

---

# 48. Git Checkpoint

建议提交：

```text
chore: close P10.4 hardening checkpoint
feat: add split-lane simultaneous bidirectional architecture
feat: add dual-direction ACK, DMA and object contexts
test: add P10.5 offline dual-direction acceptance
test: add P10.5 hardware 2plus2 evidence
test: freeze P10.5 checkpoint
```

PASS tag：

```text
p10.5-2plus2-dual-direction-pass
```

如果仅完成根因实现但硬件未达标：

```text
p10.5-2plus2-dual-direction-investigated
```

不得使用 pass。

---

# 49. Final Output

```text
P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE:
PASS / PASS_WITH_NONBLOCKING_LIMITS / FAIL / PARTIAL

P10_4_FINAL_COMMIT:
7987e6385b65fa2c7ed7d3a008c1ecbdf323ffa8

P10_4_EVIDENCE_CHECKPOINT:
f53d98252dfa85d73f35d49ebf5dc01323bcb4e7

P10_4_PASS_TAG:
p10.4-autonomous-4lane-hardening-pass

P10_4_CLOSED_TAG:
<actual tag>

P10_5_SOURCE_COMMIT:
<hash>

P10_5_EVIDENCE_CHECKPOINT:
<hash>

P10_5_TAG:
<tag>

BRANCH:
p10.5/dual-direction-2plus2

WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_5

WORKTREE_CLEAN:
true/false

AUTOMATION_ONLY:
true

USER_HOLD_POINTS:
0

CURRENT_RUN_HARDWARE_AUTHORIZATION:
false after completion

HARDWARE_ACTIONS_EXECUTED:
true/false

NETWORK_USED:
false

HARDWARE_MOVED:
false

WIRING_CHANGED:
false

DUAL_DIRECTION_CAPABILITY:
PASS/FAIL

OPERATING_MODE:
SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL

ACTIVE_LANE_MASK:
0xF

F_TO_R_LANE_MASK:
0x3

R_TO_F_LANE_MASK:
0xC

ROLE_EPOCH:
<value>

FIXED_LOCAL_TX_MASK:
0x3

FIXED_LOCAL_RX_MASK:
0xC

ROTATING_LOCAL_TX_MASK:
0xC

ROTATING_LOCAL_RX_MASK:
0x3

ONE_PLUS_ONE_ALL_PAIRS:
PASS/FAIL

TWO_PLUS_ONE_MATRIX:
PASS/FAIL

TWO_PLUS_TWO_ALL_PARTITIONS:
PASS/FAIL

TWO_PLUS_TWO_TX_EXECUTED:
true/false

F_TO_R_APPLICATION_GOODPUT_BPS:
<value>

R_TO_F_APPLICATION_GOODPUT_BPS:
<value>

F_TO_R_4MBPS_TARGET:
PASS/FAIL

R_TO_F_4MBPS_TARGET:
PASS/FAIL

F_TO_R_4P8MBPS_STRETCH:
PASS/FAIL_NONBLOCKING

R_TO_F_4P8MBPS_STRETCH:
PASS/FAIL_NONBLOCKING

SIMULTANEOUS_64M_F_TO_R:
PASS/FAIL

SIMULTANEOUS_64M_R_TO_F:
PASS/FAIL

ACK_PIGGYBACK:
PASS/FAIL

CONTROL_ONLY_ACK_FALLBACK:
PASS/FAIL

BIDIRECTIONAL_DEADLOCK:
0

FORMAL_30MIN:
PASS/FAIL

RUNTIME_SECONDS:
<value>

COMMITTED_BYTES_F_TO_R:
<value>

COMMITTED_BYTES_R_TO_F:
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

TRANSPORT_TIMEOUT:
0

SAME_MODULE_ACCEPTED_DATA:
0

CROSS_LANE_ACCEPTED_DATA:
0

DUTY_VIOLATION:
0

CONTINUOUS_HIGH_VIOLATION:
0

ROLE_MASK_OVERLAP:
0

SHUTDOWN_FIXED:
PASS/FAIL

SHUTDOWN_ROTATING:
PASS/FAIL

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
P11_OFFLINE_PREPARATION
or
P10_5_REMEDIATION
```

---

# 50. Definition of Done

P10.5 完成意味着：

```text
P10.4的非阻塞2+2 blocker被不可变保留并正确收口；
新artifact明确报告simultaneous bidirectional capability；
bundle-wide direction已被disjoint lane-role masks替代；
F→R和R→F具有独立L2、ACK/SACK、DMA和object context；
ACK可以在反向DATA中piggyback，并有control-only fallback；
所有1+1、2+1、1+2和2+2 mask组合均实际工作；
2+2探针确实执行了TX，不再是capability拒绝；
primary 2+2双向均达到>=4.0 Mbit/s application goodput；
双向simultaneous 64 MiB streaming通过；
30分钟持续2+2无完整性、协议、DMA、echo或安全错误；
两端shutdown可确认；
所有PASS绑定immutable artifacts、run ID、raw logs和SHA256。
```

P10.5 完成不意味着：

```text
最终4+4全双工已通过；
P11 handover已通过；
8×32、600 rpm、Ethernet、SPI或product-final已通过；
外部供电、duty或physical GLOBAL_PERMIT已通过。
```

现在开始执行本 Goal。先完成 P10.4 immutable closeout，然后实现和离线验证 dual-direction architecture；只有离线 mandatory gates 全部通过后，才使用新的 immutable artifacts 执行硬件 2+2 验收。
