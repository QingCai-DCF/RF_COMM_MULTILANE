# RF_COMM_MULTILANE — P10.4 全自动 4-Lane 性能余量、鲁棒性与 2+2 双向实验 Goal

## 保持现有接线和硬件位置；无人工暂停点、无外部仪器、无重新布置

```text
DOCUMENT_TYPE:
CODEX_EXECUTION_GOAL

STAGE:
P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT

STAGE_CLASS:
POST_P10_3_AUTOMATED_HARDWARE_HARDENING

AUTOMATION_ONLY:
true

NO_USER_HOLD_POINTS:
true

NO_FURTHER_USER_CONFIRMATION:
true

ASK_USER_FOR_CONTINUATION:
false

ON_SEVERE_BLOCKER:
FAIL_CLOSED_SHUTDOWN_AND_STOP_WITH_EVIDENCE

P10_3_EVIDENCE_COMMIT:
e64c04843d5d996f8d66d650fafaf3a43a2dd7dc

P10_3_EXPECTED_PASS_TAG:
p10.3-ax7020-stationary-4lane-pass

P10_3_EXPECTED_STATUS:
PASS

P10_3_EXPECTED_STAGE_COUNT:
23/23 PASS

P10_3_FIXED_ENDPOINT:
AX7020-F/JTAG:210249855178

P10_3_ROTATING_ROLE_ENDPOINT:
AX7020-R/JTAG:210512180081

CURRENT_HARDWARE_TOPOLOGY:
8 TFDU6102 small boards
4 modules per endpoint
4 bidirectional logical lanes

LANE0:
F0 <-> R0

LANE1:
F1 <-> R1

LANE2:
F2 <-> R2

LANE3:
F3 <-> R3

RECOMMENDED_BRANCH:
p10.4/autonomous-4lane-hardening

RECOMMENDED_WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_4

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

EXTERNAL_POWER_ACCEPTANCE:
PENDING_NOT_IN_SCOPE

EXTERNAL_TFDU_DUTY_ACCEPTANCE:
PENDING_NOT_IN_SCOPE

TWO_HOUR_TEST_REQUIRED:
false

MAX_SINGLE_FORMAL_RUN_SECONDS:
1800

CURRENT_RUN_HARDWARE_AUTHORIZATION:
GRANTED_WHEN_USER_SUBMITS_THIS_GOAL_TO_CODEX

AUTHORIZED_ACTIONS:
build immutable artifacts
start/connect hw_server
use Hardware Manager batch and XSDB/JTAG
program shutdown and functional bitstreams
download/run both PS ELFs
use DDR, AXI DMA, UART, ILA/VIO and registers
drive TFDU through lane masks 0x1..0xF
run autonomous performance, fault, reset and streaming tests
run 2+2 simultaneous bidirectional experiment
run bounded 30-minute formal tests
automatically shutdown both endpoints on every exit

FORBIDDEN_ACTIONS:
Ethernet
SPI peer
moving hardware
rotating hardware
optical realignment
rewiring
module replacement
lane mask >0xF
external oscilloscope/power-meter dependency
P11/P12/P13/P14/P15 acceptance promotion
product-final promotion
```

提交本 Goal 给 Codex 即构成本次 P10.4 的限定硬件授权。Codex 不得再要求用户确认接线、板卡角色、模块身份、是否构建、是否 program、是否运行 ELF、是否执行测试或是否继续。

若遇到无法自动消除的电气危险、板卡身份冲突、需要物理操作或无法确认 shutdown，Codex必须：

```text
停止新TX
撤销arm
尝试program两端shutdown bitstream
保存所有原始日志
将stage标记FAIL_CLOSED
停止任务
```

不得询问用户“是否继续”。

---

# 1. 当前 P10.3 基线

P10.3 已有以下直接结果：

```text
P10.3 stationary 4-lane hardware:
PASS

formal run:
1800.011 seconds

F→R application goodput:
8,416,570.026666667 bit/s

R→F application goodput:
8,444,532.053333333 bit/s

committed bytes F→R:
921,698,304

committed bytes R→F:
926,941,184

fixed shutdown:
PASS

rotating shutdown:
PASS

network:
not used

movement/rotation/realignment/rewiring:
not performed
```

P10.4 必须保留 P10.3 的 scoped PASS，不得重写 P10.3 raw evidence、evidence commit 或 pass tag。

P10.3 未关闭：

```text
external power measurement
external duty measurement
P11 handover
8×32
600 rpm
product-final
```

P10.4 不尝试通过代理计数器把这些 PENDING 项写成 PASS。

---

# 2. P10.4 目标

本阶段只使用当前已连接、已固定的 4-lane 硬件，自动完成以下工作：

```text
1. 完成 P10.3 Git/evidence/authorization closeout；
2. 提高半双工 4-lane application goodput 的稳定余量；
3. 统一模型、airtime、计数器和实测语义；
4. 验证连续方向切换；
5. 验证所有 lane 降级和恢复路径；
6. 验证持续 64/128 MiB streaming；
7. 验证 endpoint、DMA 和数据面自动恢复；
8. 完成数字 8×8 echo/crosstalk 长时间回归；
9. 完成 2+2 simultaneous bidirectional 实验；
10. 完成 30 分钟混合鲁棒性正式运行；
11. 输出 P11/P12 可用的风险和资源输入；
12. 创建 source commit、evidence checkpoint 和 annotated tag。
```

---

# 3. 结果分层

P10.4 必须分别报告：

```text
P10_4_CORE_ROBUSTNESS:
PASS / FAIL

P10_4_HALF_DUPLEX_8MBPS_RETENTION:
PASS / FAIL

P10_4_MARGIN_TARGET_9MBPS:
PASS / FAIL_NONBLOCKING

P10_4_STRETCH_9P6MBPS:
PASS / FAIL_NONBLOCKING

P10_4_2PLUS2_EXPERIMENT:
PASS / FAIL_WITH_EVIDENCE / PARTIAL

P10_4_EXTERNAL_ELECTRICAL:
PENDING_NOT_IN_SCOPE
```

9.0 Mbit/s、9.6 Mbit/s 和 2+2 实验不能推翻已通过的 P10.3 8.0 Mbit/s scoped acceptance，但必须如实记录。

---

# 4. P10.3 自动收口

## 4.1 发现与验证

从公共仓库自动发现：

```text
P10.3 branch
P10.3 worktree
P10.3 source commit
P10.3 evidence commit
P10.3 pass tag
formal run ID
artifact manifest
authorization record
shutdown evidence
```

验证：

```text
evidence commit = e64c04843d5d996f8d66d650fafaf3a43a2dd7dc
23/23 stages PASS
457 direct observations
formal runtime 1800.011 s
shutdown both PASS
authorization consumed
current authorization false
```

## 4.2 Pass tag

如果：

```text
p10.3-ax7020-stationary-4lane-pass
```

尚未创建，则创建 annotated tag 指向 P10.3 evidence commit。

如果已经存在：

```text
验证tag type、object和peeled target
不得移动或覆盖
```

## 4.3 Closeout metadata

生成：

```text
evidence/generated/p10_3_closeout_summary.md
evidence/generated/p10_3_closeout_summary.json
evidence/generated/p10_3_git_checkpoint_metadata.json
```

至少记录：

```text
source commit
evidence commit
pass tag
formal run ID
fixed/rotating board IDs
8-module inventory hash
actual wiring hash
bitstream/ELF hashes
evidence manifest hash
shutdown
authorization consumed
external power/duty pending
```

## 4.4 Closeout tag

创建：

```text
p10.3-ax7020-stationary-4lane-closed
```

annotated tag指向新的纯离线 closeout commit。

## 4.5 Mainline

如果 main 是 closed baseline 的祖先：

```text
fast-forward main
```

如果不能 fast-forward：

```text
不rebase冻结历史
创建integration分支
只自动解决生成状态文件的确定性冲突
任何非确定性源码冲突 -> FAIL_CLOSED，不询问用户
```

## 4.6 远端

若已有可用凭据：

```text
push P10.3 branch
push pass tag
push closed tag
push main
```

如果远端推送失败：

```text
不阻塞本地P10.4
生成git bundle和push failure evidence
不得询问用户
```

---

# 5. P10.4 Worktree

从：

```text
p10.3-ax7020-stationary-4lane-closed
```

创建：

```text
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_4
```

分支：

```text
p10.4/autonomous-4lane-hardening
```

如果 closed tag 因确定性 closeout尚未生成，则先完成第4节。

P10.4 所有构建、运行和 evidence 只在 P10.4 worktree 中产生。

---

# 6. Repository Intake

生成：

```text
evidence/generated/p10_4_repo_intake.md
evidence/generated/p10_4_repo_intake.json
```

记录：

```text
branch
HEAD
base tag
P10.3 evidence identity
git status
PROJECT_CONSTRAINTS hash
AGENTS hash
project_state hash
requirements hash
register map hash
board profiles
wiring hash
module inventory hash
tool versions
hardware authorization
start timestamp
```

运行 focused immutable checks：

```text
P10.3 verify-existing
P10.2 verify-existing
P10.1R verify-existing
P8C safety verify-existing
state/requirements consistency
```

不默认重跑全部 P0–P10 历史 campaign。

---

# 7. 自动化安全边界

任何正式运行均必须：

```text
唯一绑定AX7020-F和AX7020-R
program两端shutdown image
验证safe state
program两端functional candidate
验证safe boot
下载两端ELF但保持unarmed
读取build/profile/wiring/inventory hash
清计数器
进入receive-only
等待>=500 us
显式arm
```

safe boot：

```text
Txd[3:0]=0
endpoint armed=0
active lane mask=0
outstanding physical attempt=0
无自主TX
```

每个 test stage：

```text
shutdown-before
bounded test
shutdown-after
```

---

# 8. 外部测量排除

本 Goal 明确不要求：

```text
示波器
电流探头
功率计
热像仪
人工读表
人工调角
人工断开/插入线缆
```

因此以下状态必须保持：

```text
EXTERNAL_4LANE_POWER_ACCEPTANCE:
PENDING_NOT_IN_SCOPE

EXTERNAL_TFDU_DUTY:
PENDING_NOT_IN_SCOPE

PHYSICAL_GLOBAL_PERMIT:
PENDING_D17
```

允许记录：

```text
内部 rail telemetry
内部温度 telemetry
brownout/reset flags
内部 duty counters
```

但不得将其写成外部电气测量 PASS。

---

# 9. 性能和 Counter 语义清理

## 9.1 拆分旧 ACK 指标

将含义模糊的：

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

旧字段保留为：

```text
DEPRECATED_AMBIGUOUS
```

不得用于自动瓶颈结论。

## 9.2 模型和实测统一

统一：

```text
PHY_RAW_BPS
FRAME_GOODPUT_BPS
RFAP_USEFUL_BPS
APPLICATION_GOODPUT_BPS
HOST_ORCHESTRATED_BPS
```

每个 ceiling 必须列出：

```text
payload bytes
frame airtime
duty
ACK/SACK
direction quiet
retry assumption
```

## 9.3 Local-source rejection 注入

通过仿真和可控数字 test injection，直接使本地 source frame 到达 source-ID filter，要求：

```text
local_source_rejected_frame_count >0
application commit=0
```

不需要改变物理接线。

---

# 10. Immutable P10.4 Artifacts

若仅软件和性能配置变化：

```text
重新构建ELF和host工具
bitstream可复用前必须验证source/profile/register兼容
```

若 RTL、register、scheduler、counter或trace变化：

```text
重新构建两端bitstream/XSA/BSP/ELF
```

所有正式文件使用：

```text
artifacts/p10_4/<source>/<sha256>/
```

硬门：

```text
synthesis PASS
route PASS
WNS >=0
WHS >=0
TNS=0
critical DRC=0
unsafe CDC=0
REQP-1839=0
resource limits PASS
TFDU safety regression PASS
software build PASS
```

---

# 11. 基线 Fresh Smoke

运行：

```text
target identity
safe boot
8模块readback
每lane双向64 raw pulses
每lane双向100 frames
lane mask 0xF 1 MiB F→R
lane mask 0xF 1 MiB R→F
timer crosscheck
shutdown/re-arm
```

要求：

```text
same-module accepted DATA=0
cross-lane accepted DATA=0
CRC/SHA=0
duty/stuck-high=0
```

---

# 12. 半双工性能余量自动调优

## 12.1 固定不变

不得修改：

```text
4 Mbit/s/lane PHY
exact duty target/hard limit
CRC/SHA/SACK
same-module echo admission
module mapping
wiring
```

## 12.2 起始配置

从 P10.3 正式配置自动读取：

```text
buffer count
ring depth
descriptor batch
outstanding
SACK window
burst frames
ACK threshold
ACK max delay
objects in flight
direction quiet
```

## 12.3 自适应参数

最多：

```text
12 cases
每case <=30 s/方向
```

允许自动调整：

```text
buffer count
ring depth
descriptor batch
outstanding 32/64
SACK 32/64
burst 32/64
ACK threshold 32/64
objects in flight 4/8
interrupt coalescing
cache batching
direction quiet within already-proven safety bound
```

禁止调整：

```text
post-TX guard到未经证明范围
duty
continuous-high
startup
GLOBAL_PERMIT
```

## 12.4 选择标准

最佳配置必须同时：

```text
最高稳定application goodput
CRC/SHA错误=0
retry exhausted=0
descriptor leak=0
same-module accepted DATA=0
cross-lane accepted DATA=0
安全违规=0
```

## 12.5 目标

Mandatory retention：

```text
F→R >=8.0 Mbit/s
R→F >=8.0 Mbit/s
```

Margin target：

```text
F→R >=9.0 Mbit/s
R→F >=9.0 Mbit/s
```

Stretch：

```text
>=9.6 Mbit/s
```

---

# 13. 持续半双工性能验证

使用最佳配置：

```text
F→R 300 s
R→F 300 s
lane mask=0xF
board autonomous
host not in fast path
```

要求：

```text
每方向>=8.0 Mbit/s
timer crosscheck<=1%
committed bytes连续增长
无周期性长idle
```

输出：

```text
measured/model ratio
measured/airtime ceiling ratio
PS/DMA/PL/PHY瓶颈
per-lane utilization
```

---

# 14. 64 MiB 和 128 MiB 自动 Streaming

## 14.1 64 MiB

双向各：

```text
10 × 64 MiB
```

要求：

```text
CRC32
SHA256
atomic commit
descriptor leak=0
double completion=0
```

## 14.2 128 MiB

双向各：

```text
3 × 128 MiB
```

该项非阻塞；失败必须保留 evidence。

## 14.3 故障恢复

自动注入：

```text
lane unavailable
DMA reset
PS service reset
PL data-plane soft reset
stale segment
duplicate segment
```

每个故障后：

```text
错误对象不commit
资源回收
新的64 MiB对象成功
```

---

# 15. Lane 降级与恢复资格

在持续 streaming 中执行：

```text
0xF → 0xE → 0xF
0xF → 0xD → 0xF
0xF → 0xB → 0xF
0xF → 0x7 → 0xF
0xF → 0x3 → 0xF
0xF → 0x5 → 0xF
0xF → 0xA → 0xF
0xF → 0x1 → 0xF
```

每个 degraded mask：

```text
持续至少10 s
```

要求：

```text
healthy lanes继续
active mask/readback一致
未确认帧迁移
已确认帧不迁移
duplicate/stale commit=0
恢复后goodput回到基线的>=90%
```

---

# 16. Direction-Switch 循环

自动执行：

```text
30 s F→R
30 s R→F
重复10次
```

总 formal traffic：

```text
600 s
```

要求：

```text
每次方向切换成功
session不重建
object pipeline不全局泄漏
same-module accepted DATA=0
cross-lane accepted DATA=0
无deadlock
```

记录：

```text
turnaround latency
direction quiet
first-object latency
goodput recovery time
```

---

# 17. Endpoint / DMA / PL 恢复循环

在独立诊断 run 中自动执行：

```text
fixed PS service reset ×5
rotating PS service reset ×5
fixed DMA reset ×5
rotating DMA reset ×5
fixed PL data-plane soft reset ×3
rotating PL data-plane soft reset ×3
```

每次恢复后：

```text
完成64 MiB对象
CRC/SHA正确
stale session commit=0
descriptor leak=0
```

不得执行需要用户物理断电的测试。

---

# 18. 8×8 Digital Echo/Crosstalk 长时间回归

使用现有 raw/frame counters，自动执行每个 TX：

```text
TX_F0..TX_F3
TX_R0..TX_R3
```

每个：

```text
64 pulses
1024 pulses
30 s 4 Mbit/s frame stream
```

读取全部 RX：

```text
RX_F0..RX_F3
RX_R0..RX_R3
```

要求：

```text
目标remote path正确
same-module raw echo允许存在
same-module accepted DATA=0
same-module accepted control=0
cross-lane accepted DATA=0
non-target CRC-valid accepted frame=0
other lanes not blanked
```

外部光功率、反射率和实际波形不在本阶段范围。

---

# 19. 2+2 Simultaneous Bidirectional Experiment

## 19.1 配置

```text
lane0 + lane1:
F→R

lane2 + lane3:
R→F
```

## 19.2 Smoke

```text
duration:
300 s

payload:
continuous 64 MiB streams

board autonomous:
true
```

## 19.3 目标

每方向：

```text
application goodput >=4.0 Mbit/s
```

非阻塞 stretch：

```text
>=4.8 Mbit/s
```

## 19.4 完整性

```text
CRC bad=0
SHA mismatch=0
partial/duplicate/stale commit=0
retry exhausted=0
descriptor leak=0
same-module accepted DATA=0
cross-lane accepted DATA=0
duty/stuck-high=0
```

## 19.5 结果边界

允许声明：

```text
P10_4_2PLUS2_SIMULTANEOUS_BIDIRECTIONAL_EXPERIMENT:
PASS
```

不得声明：

```text
FINAL_4PLUS4_FULL_DUPLEX:
PASS
```

---

# 20. 30 分钟混合鲁棒性正式运行

总计：

```text
1800 s
```

自动划分：

```text
0..120 s:
warm-up

120..540 s:
F→R half-duplex mask 0xF

540..960 s:
R→F half-duplex mask 0xF

960..1260 s:
direction-switch循环

1260..1560 s:
lane degradation/recovery

1560..1800 s:
2+2 simultaneous bidirectional
```

Formal mandatory half-duplex windows：

```text
F→R >=8.0 Mbit/s
R→F >=8.0 Mbit/s
```

2+2 result 单独报告，不阻塞 half-duplex core result。

整个 1800 s：

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
cross-lane accepted DATA=0
duty violation=0
continuous-high violation=0
```

不执行 2 小时测试。

---

# 21. 只读 Telemetry

每 5 秒自动 snapshot：

```text
application bytes
frame bytes
wire bytes
per-lane scheduled bytes
ACK/SACK
queue occupancy
ring occupancy
buffer occupancy
retry
lane health
degraded mask
same-module raw echo
blanked frames
local-source rejects
accepted remote frames
duty headroom
internal temperature if available
brownout/reset flags
```

Snapshot 必须为非阻塞只读。

---

# 22. 自动化运行和重试

有界重试：

```text
hw_server/JTAG connect <=3
program <=2
单个diagnostic stage新run_id <=2
```

每次重试前：

```text
shutdown两端
```

不得自动进行：

```text
物理断电
拔插JTAG
重新接线
移动模块
```

若这些动作成为必要条件：

```text
FAIL_CLOSED
```

不询问用户。

---

# 23. Shutdown

任何 stage 失败、异常、timeout、Ctrl+C 或进程退出：

```text
停止新TX
撤销arm
active lane mask=0
停止performance/streaming
abort/reclaim descriptor
请求SD shutdown
program两端shutdown bitstream
保存日志
```

Mandatory：

```text
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
```

如果 JTAG 丢失导致无法确认 shutdown：

```text
P10_4=FAIL_CLOSED_SHUTDOWN_UNCONFIRMED
```

---

# 24. Evidence

Run ID：

```text
p10_4_<UTC>_<source>_<fixedbit>_<rotbit>
```

目录：

```text
evidence/hardware/p10_4/<run_id>/
```

子目录：

```text
authorization
artifacts
target_identity
safe_boot
baseline_smoke
counter_semantics
performance_tuning
half_duplex_performance
streaming_64m
streaming_128m
degraded_modes
direction_switch
reset_recovery
echo_crosstalk_8x8
two_plus_two
mixed_30min
shutdown
raw_logs
final
```

Generated summaries：

```text
p10_4_repo_intake
p10_4_p10_3_closeout
p10_4_artifact_freeze
p10_4_authorization
p10_4_safe_boot
p10_4_counter_semantics
p10_4_baseline_smoke
p10_4_performance_tuning
p10_4_half_duplex_performance
p10_4_streaming_64m
p10_4_streaming_128m
p10_4_degraded_modes
p10_4_direction_switch
p10_4_reset_recovery
p10_4_echo_crosstalk
p10_4_two_plus_two
p10_4_mixed_30min
p10_4_shutdown
p10_4_evidence_consistency
p10_4_final_summary
```

每项：

```text
.md
.json
```

---

# 25. Requirement IDs

新增：

```text
P10_4-CLOSE-001 P10.3 closeout
P10_4-METRIC-001 split ACK stall semantics
P10_4-MODEL-001 model/measured reconciliation
P10_4-PERF-001 retain F→R >=8 Mbit/s
P10_4-PERF-002 retain R→F >=8 Mbit/s
P10_4-PERF-003 margin target >=9 Mbit/s
P10_4-STREAM-001 10×64 MiB F→R
P10_4-STREAM-002 10×64 MiB R→F
P10_4-DEG-001 lane degradation/recovery
P10_4-DIR-001 direction switching
P10_4-RESET-001 endpoint/DMA/PL recovery
P10_4-XTALK-001 8×8 digital echo/crosstalk
P10_4-FD-001 2+2 experiment
P10_4-SOAK-001 mixed 30-minute run
P10_4-SAFE-001 shutdown both endpoints
```

---

# 26. Machine State

开始：

```text
current_program_stage:
P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT

p10_4_status:
IN_PROGRESS

current_run_hardware_authorization:
true
```

结束后无论 PASS/FAIL：

```text
current_run_hardware_authorization:
false

last_hardware_authorization_consumed:
true
```

PASS 时：

```text
p10_4_status:
PASS

stationary_4lane_core_robustness:
PASS

p11_status:
NOT_STARTED
```

保持：

```text
P10.3 PASS
external power pending
external duty pending
physical permit pending
P11 pending
8×32 pending
600rpm pending
product final pending
```

---

# 27. Mandatory Exit Gates

```text
P10_3_BASELINE_RECHECK: PASS
P10_3_PASS_TAG_IMMUTABLE: PASS
P10_3_CLOSEOUT: PASS
CURRENT_RUN_AUTHORIZATION_BOUND: PASS

ARTIFACT_PROVENANCE: PASS
TARGET_ROLE_BINDING: PASS
SAFE_BOOT_BOTH: PASS
SHUTDOWN_BEFORE_BOTH: PASS
SHUTDOWN_AFTER_BOTH: PASS

COUNTER_SEMANTICS_SPLIT: PASS
MODEL_MEASURED_RECONCILIATION: PASS
LOCAL_SOURCE_REJECTION_INJECTION: PASS

BASELINE_SMOKE: PASS
HALF_DUPLEX_F_TO_R_8MBPS: PASS
HALF_DUPLEX_R_TO_F_8MBPS: PASS

STREAMING_64M_F_TO_R_10X: PASS
STREAMING_64M_R_TO_F_10X: PASS
STREAM_RECOVERY: PASS

LANE_DEGRADATION_RECOVERY: PASS
DIRECTION_SWITCH_LOOP: PASS
ENDPOINT_DMA_PL_RESET_RECOVERY: PASS

ECHO_CROSSTALK_8X8_DIGITAL: PASS
SAME_MODULE_ACCEPTED_DATA_ZERO: PASS
CROSS_LANE_ACCEPTED_DATA_ZERO: PASS

MIXED_30MIN: PASS

CRC_BAD_ZERO: PASS
SHA_MISMATCH_ZERO: PASS
PARTIAL_DUPLICATE_STALE_ZERO: PASS
RETRY_EXHAUSTED_ZERO: PASS
DESCRIPTOR_LEAK_ZERO: PASS
DOUBLE_COMPLETION_ZERO: PASS
DEADLOCK_ZERO: PASS
DUTY_VIOLATION_ZERO: PASS
CONTINUOUS_HIGH_VIOLATION_ZERO: PASS
EVIDENCE_CONSISTENCY: PASS
```

Nonblocking：

```text
HALF_DUPLEX_MARGIN_9MBPS
HALF_DUPLEX_STRETCH_9P6MBPS
STREAMING_128M
TWO_PLUS_TWO_4MBPS_PER_DIRECTION
REMOTE_PUSH
```

---

# 28. Failure Semantics

## PASS

所有 mandatory gates通过。

## PASS_WITH_NONBLOCKING_LIMITS

Mandatory通过，但以下一项或多项未通过：

```text
9.0 Mbit/s margin
9.6 Mbit/s stretch
128 MiB
2+2 target
remote push
```

## PARTIAL

核心 8 Mbit/s某方向失败，但其他鲁棒性 gate通过。

## FAIL

以下任一：

```text
safe boot失败
shutdown无法确认
错误对象commit
same-module accepted DATA>0
cross-lane accepted DATA>0
descriptor double completion
duty/stuck-high violation
artifact/evidence错误
```

---

# 29. Git Checkpoint

建议提交：

```text
chore: close P10.3 stationary four-lane acceptance
feat: harden four-lane performance and diagnostics
test: add automated four-lane robustness and 2plus2 evidence
test: freeze P10.4 checkpoint
```

PASS 或 PASS_WITH_NONBLOCKING_LIMITS：

```text
p10.4-autonomous-4lane-hardening-pass
```

若 core mandatory 失败：

```text
p10.4-autonomous-4lane-hardening-investigated
```

不得使用 pass。

---

# 30. Final Output

```text
P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT:
PASS / PASS_WITH_NONBLOCKING_LIMITS / FAIL / PARTIAL

P10_3_EVIDENCE_COMMIT:
e64c04843d5d996f8d66d650fafaf3a43a2dd7dc

P10_3_PASS_TAG:
p10.3-ax7020-stationary-4lane-pass

P10_3_CLOSED_TAG:
<actual tag>

P10_4_SOURCE_COMMIT:
<hash>

P10_4_EVIDENCE_CHECKPOINT:
<hash>

P10_4_TAG:
<tag>

BRANCH:
p10.4/autonomous-4lane-hardening

WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_4

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

EXTERNAL_INSTRUMENTATION_USED:
false

P10_3_BASELINE_RECHECK:
PASS/FAIL

BEST_BUFFER_COUNT:
<value>

BEST_RING_DEPTH:
<value>

BEST_DESCRIPTOR_BATCH:
<value>

BEST_OUTSTANDING:
<value>

BEST_SACK_WINDOW:
<value>

BEST_BURST_FRAMES:
<value>

BEST_ACK_THRESHOLD:
<value>

F_TO_R_APPLICATION_GOODPUT_BPS:
<value>

R_TO_F_APPLICATION_GOODPUT_BPS:
<value>

F_TO_R_8MBPS_RETENTION:
PASS/FAIL

R_TO_F_8MBPS_RETENTION:
PASS/FAIL

F_TO_R_9MBPS_MARGIN:
PASS/FAIL_NONBLOCKING

R_TO_F_9MBPS_MARGIN:
PASS/FAIL_NONBLOCKING

F_TO_R_9P6MBPS_STRETCH:
PASS/FAIL_NONBLOCKING

R_TO_F_9P6MBPS_STRETCH:
PASS/FAIL_NONBLOCKING

STREAMING_64M_F_TO_R:
PASS/FAIL

STREAMING_64M_R_TO_F:
PASS/FAIL

STREAMING_128M:
PASS/FAIL_NONBLOCKING

LANE_DEGRADATION_RECOVERY:
PASS/FAIL

DIRECTION_SWITCH_LOOP:
PASS/FAIL

RESET_RECOVERY:
PASS/FAIL

ECHO_CROSSTALK_8X8_DIGITAL:
PASS/FAIL

SAME_MODULE_ACCEPTED_DATA:
0

CROSS_LANE_ACCEPTED_DATA:
0

TWO_PLUS_TWO_EXPERIMENT:
PASS/FAIL_WITH_EVIDENCE/PARTIAL

TWO_PLUS_TWO_F_TO_R_BPS:
<value>

TWO_PLUS_TWO_R_TO_F_BPS:
<value>

MIXED_30MIN:
PASS/FAIL

RUNTIME_SECONDS:
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

EXTERNAL_POWER_ACCEPTANCE:
PENDING_NOT_IN_SCOPE

EXTERNAL_TFDU_DUTY:
PENDING_NOT_IN_SCOPE

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
P10_4_REMEDIATION
```

---

# 31. Definition of Done

本 Goal 完成意味着：

```text
P10.3已完成不可变收口；
整个阶段不存在用户确认点；
当前4-lane硬件未被移动、重新接线或依赖外部仪器；
4-lane半双工8 Mbit/s/方向能力保持；
性能余量被自动调优和量化；
64 MiB长对象多次双向通过；
lane降级/恢复、方向切换和自动reset恢复通过；
8×8数字echo/crosstalk回归通过；
2+2同时双向实验完成并有直接证据；
30分钟混合鲁棒性运行无完整性、协议、descriptor或安全错误；
两端shutdown可确认；
所有结果绑定immutable artifacts、run ID、raw logs和SHA256。
```

本 Goal 完成不意味着：

```text
外部供电或duty已验收；
最终4+4全双工已通过；
P11 handover已通过；
8×32、600 rpm、Ethernet、SPI或产品最终已通过。
```

现在开始执行本 Goal。不得设置任何用户 HOLD POINT；遇到无法自动解决的严重阻塞时，执行 shutdown、保存 evidence并 fail closed。
