# RF_COMM_MULTILANE — P10.1R 双 AX7020 2-Lane 速度与稳定性专项修复 Goal

## Same-Module Self-Echo 抑制、ACK/方向窗口流水优化、4 Mbit/s 应用吞吐与 30 分钟稳定性复验

```text
DOCUMENT_TYPE:
CODEX_EXECUTION_GOAL

STAGE:
P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION

STAGE_CLASS:
FOCUSED_OFFLINE_AND_AUTHORIZED_HARDWARE_REACCEPTANCE

FOCUS:
2-LANE HALF-DUPLEX SPEED_AND_STABILITY_ONLY

P11_EXECUTION_ALLOWED:
false

ONEPLUSONE_FULL_DUPLEX_REQUIRED:
false

ETHERNET_REQUIRED:
false

ROTATION_ALLOWED:
false

HARDWARE_MOVEMENT_ALLOWED:
false

REWIRING_ALLOWED:
false

MAX_LANE_MASK:
0x3

CURRENT_RUN_HARDWARE_AUTHORIZATION:
false until explicitly granted for the new immutable remediation artifacts

ASK_USER_ONLY_FOR_SEVERE_BLOCKERS:
true
```

---

# 1. 当前失败基线

本阶段基于以下 P10.1 硬件 campaign 和 remediation audit：

```text
P10.1 hardware source commit:
bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1

Selected crosstalk run:
p10_1_hw_20260801T073224Z_bb6ce78a_1585d1ad_9ad4f85f

Formal run:
p10_1_hw_20260801T090528Z_bb6ce78a_1585d1ad_9ad4f85f

Fixed board:
AX7020-F/JTAG:210249855178

Rotating-role board:
AX7020-R/JTAG:210512180081

Fixed performance bitstream:
1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e

Rotating performance bitstream:
9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f

Fixed ELF:
17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728

Rotating ELF:
88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0
```

P10.1 hardware terminal result：

```text
STATUS:
FAIL

FAILURE_CLASSIFICATION:
FAIL_WITH_PERFORMANCE_EVIDENCE_AND_CROSSTALK_GATE_FAILURE
```

但以下功能、安全和完整性结果已经通过，必须保留：

```text
P10功能性双节点PASS
P10.1 offline base recheck PASS
model sanity PASS
timer crosscheck PASS
single-lane baseline PASS
two-lane baseline PASS
adaptive tuning PASS
sustained pipeline PASS
64 MiB F→R PASS
64 MiB R→F PASS
stream abort/reset recovery PASS
descriptor leak zero
double completion zero
CRC bad zero
SHA mismatch zero
partial/duplicate/stale commit zero
retry exhausted zero
deadlock zero
duty violation zero
continuous-high violation zero
shutdown fixed PASS
shutdown rotating PASS
evidence consistency PASS
```

本 remediation 不得重写或删除上述历史 evidence，也不得把失败 campaign 改写成 PASS。

---

# 2. 当前需要关闭的两个根问题

## 2.1 Same-module self-reception

已观察到：

```text
TX_F0:
target R0 = 64/1024
local F0 = 64/1024
other lane = 0

TX_F1:
target R1 = 64/1024
local F1 = 64/1024
other lane = 0

TX_R0:
target F0 = 64/1024
local R0 = 64/1024
other lane = 0

TX_R1:
target F1 = 64/1024
local R1 = 64/1024
other lane = 0
```

Frame-level 每个方向：

```text
intended remote CRC-valid DATA frames:
4246

sender-side same-module CRC-valid DATA frames:
4246

cross-lane CRC-valid frames:
0
```

因此：

```text
near-end echo:
HIGH

cross-lane crosstalk:
LOW

current all-RX-ready acceptance:
BLOCKED
```

当前 evidence 能证明 deterministic same-module self-reception，不能独立区分：

```text
直接光耦合
附近反射
电耦合
RTL/counter-path loopback
```

用户给出的 remediation design intent：

```text
同一个TFDU模块在任意时刻只能处于：
- 物理TX活动
或
- RX frame admission有效

二者不得同时有效。
```

该规则是 per-module，不得因为 lane0 TX 自动 blank lane1。

## 2.2 ACK turnaround 与 inter-object serialization

当前测量：

```text
F→R application goodput:
2,587,436.300 bit/s

R→F application goodput:
2,585,671.499 bit/s

corrected modeled goodput:
4,189,709.130 bit/s

airtime ceiling:
4,497,844.632 bit/s

measured/model:
约61.7%

measured/airtime:
约57.5%
```

当前主要瓶颈：

```text
ACK_TURNAROUND_AND_INTER_OBJECT_CONTROL_SERIALIZATION
```

telemetry：

```text
ACK wait / PL elapsed:
约91.3%–91.4%

AXIS stall / PL elapsed:
约99.6%

inter-object control / PL elapsed:
约44.5%–44.9%
```

上述 counters 有重叠，禁止相加。

当前最佳配置：

```text
buffer_count:
4

ring_depth:
32

descriptor_batch:
8

outstanding:
32

ack_threshold:
8
```

64 MiB 双向已经通过，说明对象和 descriptor chain 基础功能可用；下一步必须让数据面持续占用光链路，而不是在 ACK 和对象边界长期停顿。

---

# 3. 本阶段唯一目标

本阶段只完成当前静止 2-lane 半双工链路的速度和稳定性。

必须关闭：

```text
1. same-module accepted DATA frame = 0；
2. cross-lane accepted DATA frame = 0；
3. raw same-module echo保持可观测；
4. F→R application goodput >=4.0 Mbit/s；
5. R→F application goodput >=4.0 Mbit/s；
6. 64 MiB streaming双向稳定；
7. 30分钟正式运行双向均达到目标；
8. 无数据完整性、安全、descriptor和shutdown错误。
```

本阶段明确不做：

```text
P11
旋转
ABZ
8×32
1+1正式全双工验收
Ethernet
SPI
重新接线
移动或调角
128 MiB硬门
最终physical GLOBAL_PERMIT
外部示波器/光功率验收
```

可选的 1+1 实验从本 Goal 删除，不得分散当前 2-lane 半双工优化资源。

---

# 4. 先冻结失败证据

在修改源码前，Codex 必须找到：

```text
P10.1 hardware branch/worktree
source commit bb6ce78a...
terminal campaign summary
combined remediation audit
所有 selected run manifests
shutdown evidence
```

若失败 evidence 尚未形成 Git checkpoint：

1. 保持所有 raw evidence 原样；
2. 关闭旧 current-run authorization；
3. 标记旧授权 consumed；
4. 提交 audit、terminal summary和状态收口；
5. 创建 annotated tag：

```text
p10.1-hardware-performance-fail-20260801
```

该 tag 只能指向失败 evidence checkpoint。

若已有等价 immutable tag：

```text
验证并复用
不得移动
不得覆盖
```

生成：

```text
evidence/generated/p10_1r_failure_baseline_summary.md
evidence/generated/p10_1r_failure_baseline_summary.json
```

记录：

```text
source commit
artifact hashes
run IDs
fail gates
measured goodput
crosstalk result
shutdown
authorization consumed
```

---

# 5. Remediation worktree

从最新、已收口的失败 baseline 创建：

```text
WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R

BRANCH:
p10.1r/2lane-speed-stability-remediation
```

不得直接修改：

```text
P10 pass worktree
P10.1 offline worktree
P10.1 failed-hardware evidence worktree
main
```

验证：

```text
包含p10.1-offline-performance-ready
包含P10 pass/closed tags
包含失败source/evidence
worktree clean
```

---

# 6. 保持的物理映射

不得修改：

```text
AX7020-F:
JTAG 210249855178

AX7020-R:
JTAG 210512180081
```

J10映射：

| Position | Mode | SD | Rxd | Txd |
|---|---:|---:|---:|---:|
| A | 30 | 32 | 34 | 36 |
| B | 22 | 24 | 26 | 28 |

模块：

```text
AX7020-F position A:
F0

AX7020-F position B:
F1

AX7020-R position A:
R0

AX7020-R position B:
R1
```

lane：

```text
lane0:
F0 <-> R0

lane1:
F1 <-> R1
```

禁止：

```text
A-B交叉配对
B-A交叉配对
VCC/GND修改
重新接线
复用Z7010 XDC
```

---

# 7. LED观测要求

保留 active-low PL LED monitor：

```text
LED1:
lane0 TX activity

LED2:
lane0 accepted RX activity

LED3:
lane1 TX activity

LED4:
lane1 accepted RX activity
```

LED必须是纯监控 tap：

```text
不参与GLOBAL_PERMIT
不参与Txd kill
不参与SD/Mode
不参与ACK
不参与backpressure
不参与acceptance决定
```

RX LED使用：

```text
synchronized accepted RX event
```

不是 raw self-echo pulse。

reset、shutdown、fault：

```text
all LEDs off
```

LED不是安全证据或光学PASS证据。

---

# 8. Per-module TX/RX mutual exclusion

## 8.1 Canonical contract

对每个模块：

```text
F0
F1
R0
R1
```

必须满足：

```text
never(
  TX_PHYSICAL_ACTIVE(module)
  &&
  RX_FRAME_ACCEPT_ENABLE(module)
)
```

逻辑：

```text
TX_PHYSICAL_ACTIVE(module)
→ RX_FRAME_ACCEPT_ENABLE(module)=0

RX_FRAME_ACCEPT_ENABLE(module)=1
→ PHYSICAL_TXD(module)=0
```

## 8.2 TX active来源

`TX_PHYSICAL_ACTIVE` 必须由最终物理发射路径导出，覆盖：

```text
preamble
DATA
ACK
SACK/control
retry
每一个真实Txd event
```

禁止从以下早期信号推断：

```text
软件send request
descriptor queued
frame scheduled
lane requested
```

必须反映经过：

```text
GLOBAL_PERMIT
endpoint arm
lane permit
one-hot
duty
stuck-high
frame admission
```

之后的最终物理TX行为。

## 8.3 RX admission

增加每模块：

```text
rx_frame_accept_enable
rx_decoder_clear
rx_echo_quarantine
rx_post_tx_guard_active
```

TX开始时：

```text
立即关闭same-module frame admission
清除partial preamble
清除partial frame
清除decoder byte/CRC state
```

TX期间：

```text
raw Rxd继续同步和计数
frame decoder不得生成accepted frame
不得生成ACK/SACK
不得推进sequence window
不得写DMA
不得提交application data
```

TX结束后：

```text
进入bounded echo quarantine
```

结束条件不能盲猜固定常数，必须使用：

```text
minimum guard
+
Rxd idle qualification
+
local-source frame filter
+
direction-turnaround contract
```

## 8.4 Post-TX guard参数

新增 canonical config：

```text
config/tfdu_rx_admission.yaml
```

至少：

```text
minimum_post_tx_guard_cycles
rxd_idle_qual_cycles
maximum_echo_quarantine_cycles
decoder_clear_cycles
local_source_reject_enable
guard_measurement_mode
```

初值由：

```text
TFDU datasheet timing
P2 behavior model
fresh hardware echo-tail timestamp
```

共同确定。

不得把 0、1 us或500 us当作无证据默认最终值。

## 8.5 Echo tail测量

增加每模块 timestamp：

```text
last_physical_txd_rise
last_physical_txd_fall
first_local_rxd_edge_after_tx
last_local_rxd_edge_after_tx
local_echo_tail_cycles
```

硬件阶段自动测量：

```text
1000 frames/module
4 modules
最大值
p99
p99.9
```

最终guard：

```text
>=最大观测echo tail + deterministic margin
```

如果guard过长影响ACK：

```text
使用bundle burst降低turnaround频率
禁止通过缩短guard引入same-module accepted frame
```

## 8.6 Local-source rejection

即使 admission重新打开，也必须拒绝：

```text
source_node_id == local_node_id
且 frame type为本端刚发出的DATA/CONTROL
```

该过滤是 protocol defense-in-depth，不替代 per-module admission。

Remote ACK/SACK必须仍可接收。

## 8.7 不blank另一lane

例如：

```text
F0 TX
→ F0 RX admission off
→ F1 RX admission保持原状态
```

必须提供 assertion。

---

# 9. 新可观测性

每模块新增：

```text
raw_rx_pulse_count
raw_rx_pulse_while_local_tx
blanked_rx_pulse_count
blanked_frame_start_count
blanked_crc_valid_frame_count
local_source_rejected_frame_count
accepted_remote_frame_count
post_tx_guard_cycles_total
post_tx_guard_max
echo_tail_max_cycles
echo_tail_p99_cycles
decoder_clear_count
```

全局：

```text
non_target_accepted_crc_valid_frames
cross_lane_accepted_frames
rx_admission_violation
tx_rx_overlap_violation
```

寄存器快照必须原子或版本化。

---

# 10. Offline self-echo model

扩展 TFDU/channel model：

```text
remote desired optical path
same-module echo path
configurable echo delay
configurable echo duration
configurable jitter
reflection tail
cross-lane coupling
```

测试延迟范围至少覆盖：

```text
0
1
2
4
8
16
32
64
128
256
512 us
```

如果 datasheet/实际trace指向更长范围，自动扩展。

assertions：

```text
same-module raw pulse remains observable
same-module accepted DATA=0
remote DATA accepted
remote ACK/SACK accepted
other lane unaffected
no protocol commit from blanked path
```

---

# 11. ACK 和方向窗口重构

## 11.1 目标

把当前：

```text
约91% ACK wait
```

降低到不阻塞4.0 Mbit/s目标。

## 11.2 Bundle-wide burst

使用统一 2-lane bundle window：

```text
global sequence
global outstanding
shared SACK
```

默认 baseline：

```text
OUTSTANDING=32
ENDPOINT_BURST_FRAMES=32
ACK_THRESHOLD=32
```

不得继续以每8帧或每个对象强制反转，除非：

```text
receiver credit low
gap阻塞窗口
ACK max delay到期
fault
stop/abort
```

## 11.3 ACK trigger

ACK/SACK只在：

```text
bundle frame threshold
ACK max delay
receiver credit low watermark
gap blocks forward progress
fault/control
explicit stop
```

触发。

## 11.4 对象边界

对象边界不得默认触发：

```text
direction switch
optical ready round trip
receiver priming
mailbox dump
global pipeline drain
```

多个对象可共享同一个方向窗口。

## 11.5 多对象in-flight

至少支持：

```text
4 concurrent objects
```

或等价 streaming segments。

对象：

```text
prepare
DMA
optical
remote verify
commit
```

允许重叠。

## 11.6 Host不在fast path

正式窗口：

```text
1 × CONFIG
1 × START
只读snapshot
1 × STOP
```

硬门：

```text
host_fast_path_dependency_count=0
host blocking command count <=4/方向
segments_per_host_command >=1000
```

只读memory snapshot不要求远端pipeline停顿。

---

# 12. 持续流水

固定 baseline：

```text
buffer_count=4
ring_depth=32
descriptor_batch=8
outstanding=32
```

不再重复宽泛buffer/ring sweep。

只优化：

```text
ACK threshold
burst frames
ACK max delay
direction quiet
inter-object control
object concurrency
```

pipeline至少：

```text
object N+2 prepare
object N+1 DMA
object N optical
object N-1 remote DMA
object N-2 verify/commit
```

禁止：

```text
每对象drain
每对象重新prime receiver
每对象host mailbox dump
每对象重新建立session
```

---

# 13. Performance model remediation

模型必须包含：

```text
4 Mbit/s/lane
2 lanes
247-byte L1 payload
RFAP useful bytes
exact duty
bundle burst
ACK airtime
post-TX echo guard
direction quiet
PER
retry
DMA/PS overlap
```

输出：

```text
airtime ceiling
application ceiling
guard overhead
ACK overhead
direction overhead
expected sustained goodput
```

硬门：

```text
modeled F→R >=4.0 Mbit/s
modeled R→F >=4.0 Mbit/s
```

4.8 Mbit/s不作为本 remediation硬门。

若模型在安全guard下达不到4.0：

```text
FAIL_WITH_ARCHITECTURE_BLOCKER
```

不得削弱：

```text
duty
CRC
SHA
SACK
self-echo admission
shutdown
```

---

# 14. Offline verification

## 14.1 Unit tests

至少：

```text
per-module mutual exclusion
decoder clear
guard state
idle qualification
local-source reject
other-lane independence
ACK threshold
burst window
multi-object pipeline
host command independence
```

## 14.2 XSIM

至少：

```text
tb_tfdu_rx_admission_same_module_echo
tb_tfdu_rx_admission_remote_ack
tb_tfdu_rx_admission_other_lane
tb_tfdu_echo_guard_sweep
tb_bundle_ack_window_2lane
tb_multi_object_continuous_pipeline
tb_p10_1r_dual_endpoint
```

## 14.3 Random tests

固定seeds：

```text
1
7
17
31
127
1024
20260801
```

至少：

```text
50,000 echo/admission events
50,000 ACK/window events
25,000 reset/fault events
```

## 14.4 Assertions

```text
TX/RX admission overlap=0
same-module accepted DATA=0
remote accepted DATA>0
remote ACK accepted
cross-lane accepted frame=0
descriptor leak=0
duplicate/stale commit=0
```

---

# 15. 双AX7020离线构建

构建：

```text
AX7020-F remediation bitstream
AX7020-R remediation bitstream
两端XSA/BSP/ELF
shutdown bitstreams
```

使用原接线、pinmap和XDC。

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
```

新增 admission/trace逻辑不得破坏：

```text
GLOBAL_PERMIT
exact duty
continuous-high
startup
one-hot
final TX kill
```

---

# 16. 新 immutable artifacts

所有正式文件使用：

```text
artifacts/p10_1r/<source>/<sha256>/
```

记录：

```text
source commit
fixed/rotating bitstream
fixed/rotating ELF
XSA/BSP
pinmap/XDC
rx admission config
performance config
measurement contract
Vivado/Vitis版本
```

旧 `1585d1ad...` 和 `9ad4f85f...` artifact 只能用于历史比较，不能用于 remediation PASS。

---

# 17. 新硬件授权

当前旧授权已经消费，不得复用。

发送本 Goal 给 Codex 执行硬件阶段时，用户应附带：

```text
我授权 Codex 在
P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION
范围内，对当前两块 AX7020 和四个 TFDU6102 小板执行自动化硬件操作。

允许：
- 构建并program新的内容寻址shutdown/remediation bitstream；
- 下载运行两端新的ELF；
- 使用hw_server、Hardware Manager batch、XSDB/JTAG、DDR、DMA、
  UART、ILA/VIO和寄存器；
- 在lane mask 0x1、0x2、0x3上执行受控TFDU发射；
- 自动测量same-module echo tail和选择安全guard；
- 执行2-lane ACK/window调优、64 MiB streaming和最长1800秒正式运行；
- 自动执行PS/PL/DMA reset和故障恢复；
- 失败、异常、超时或退出时shutdown两端。

禁止：
- 连接Ethernet；
- 移动、旋转、调角、遮挡、交换模块或重新接线；
- 使用lane mask>0x3；
- 推进P11、8×32或600rpm；
- 将raw same-module echo本身误写成协议失败，只要accepted frame为0。

除明确电气危险、无法唯一绑定板卡、必须人工物理操作或无法确认shutdown外，
不要再次请求用户确认。
```

授权必须绑定新artifact hash。

---

# 18. Hardware stage 0：safe start

顺序：

```text
识别F/R板
program两端shutdown
确认safe state
program两端remediation candidate
确认safe boot
下载两端ELF
保持unarmed
读取build/profile/hash
清counter
receive-only
等待>=500 us
```

safe boot：

```text
Txd=0
endpoint armed=0
active TX mask=0
RX admission状态可读
无自主TX
```

---

# 19. Hardware stage 1：echo-tail characterization

每模块：

```text
F0
F1
R0
R1
```

执行：

```text
1000个短pulse/frame
记录last Txd fall
记录最后local raw Rxd edge
记录remote目标RX
```

输出：

```text
echo tail max
p99
p99.9
minimum safe guard
remote ACK earliest safe start
```

自动选择：

```text
post_tx_guard
idle qualification
```

选择条件：

```text
same-module accepted frame=0
remote ACK loss=0
guard最小化
```

该stage只在配置范围内自动选择，不需要用户确认。

---

# 20. Hardware stage 2：4×4 remediation gate

每个TX：

```text
TX_F0
TX_F1
TX_R0
TX_R1
```

测试：

```text
64 raw pulses
1024 raw pulses
10-second 4 Mbit/s frame stream
```

同时读取全部4个RX。

新的验收语义：

```text
intended remote valid frames >0
intended remote integrity correct

sender-side same-module raw pulses:
可以 >0，必须记录

sender-side same-module accepted DATA frames:
exactly 0

sender-side same-module ACK/SACK/protocol events:
exactly 0

cross-lane accepted frames:
exactly 0

non-target CRC-valid accepted frames:
exactly 0
```

允许：

```text
blanked_valid_frame_count >0
local_source_rejected_frame_count >0
```

因为它们证明抑制路径工作。

硬门：

```text
CROSSTALK_FRAME_ADMISSION_REMEDIATED: PASS
```

---

# 21. Hardware stage 3：4 Mbit/s/lane sanity

分别：

```text
F→R lane0
F→R lane1
R→F lane0
R→F lane1
```

每case：

```text
1000 frames
247-byte payload
counter/PRBS
```

要求：

```text
CRC bad=0
same-module accepted=0
cross-lane accepted=0
retry exhausted=0
duty/stuck-high=0
```

不重复1/2 Mbit/s，除非4 Mbit/s失败时诊断。

---

# 22. Hardware stage 4：ACK/burst定向调优

起点：

```text
buffer=4
ring=32
batch=8
outstanding=32
```

只测试最多8个配置。

建议矩阵：

```text
Case 1:
burst=16, ack_threshold=16

Case 2:
burst=24, ack_threshold=24

Case 3:
burst=32, ack_threshold=32

Case 4:
burst=32, ack_threshold=24

Case 5:
最佳burst/threshold + reduced ACK max delay

Case 6:
最佳burst/threshold + minimized safe direction quiet

Case 7:
最佳配置 + 4 concurrent objects

Case 8:
最佳配置 + continuous stream/no per-object control
```

每case：

```text
F→R 30 s
R→F 30 s
```

选择条件：

```text
最高稳定application goodput
same-module accepted=0
CRC/SHA=0
retry exhausted=0
descriptor leak=0
安全违规=0
```

额外目标：

```text
data frames per ACK window >=24
ACK wait / PL elapsed显著低于旧91%
inter-object blocking显著低于旧44%
host blocking commands <=4/方向
```

ACK wait counter有重叠，只用于趋势，不作为独立时间求和。

---

# 23. Hardware stage 5：持续2-lane性能

使用最佳配置：

```text
F→R:
300 s

R→F:
300 s
```

正式 application goodput：

```text
>=4,000,000 bit/s each direction
```

统计：

```text
APPLICATION_SUSTAINED
eligible_for_scaling=true
timer crosscheck <=1%
host not in fast path
```

如果任一方向低于4.0：

```text
P10_1R_PERFORMANCE_TARGET: FAIL_WITH_EVIDENCE
```

P10功能性PASS仍保留。

---

# 24. Hardware stage 6：64 MiB 双向稳定

执行：

```text
F→R:
5 × 64 MiB

R→F:
5 × 64 MiB
```

每个对象：

```text
incremental CRC32
incremental SHA256
atomic commit
```

随后各执行一次：

```text
abort at 50%
endpoint service reset
DMA reset
```

恢复后：

```text
新的64 MiB对象成功
```

要求：

```text
partial commit=0
wrong hash commit=0
descriptor leak=0
double completion=0
```

---

# 25. Hardware stage 7：30分钟正式速度与稳定性

总：

```text
1800 seconds
```

划分：

```text
0..120 s:
warm-up

120..960 s:
F→R formal sustained window

960..1800 s:
R→F formal sustained window
```

每方向：

```text
lane mask=0x3
board autonomous
continuous multi-object/stream
>=4.0 Mbit/s
```

推荐负载：

```text
64 MiB continuous objects
或无固定对象上限的stream
```

必须：

```text
APPLICATION_GOODPUT >=4.0 Mbit/s

CRC bad=0
SHA mismatch=0
partial commit=0
duplicate commit=0
stale commit=0
retry exhausted=0
descriptor leak=0
double completion=0
deadlock=0

sender same-module accepted DATA=0
cross-lane accepted DATA=0

duty violation=0
continuous-high violation=0
shutdown PASS
```

---

# 26. Stability telemetry

每5秒snapshot：

```text
application bytes
frame bytes
wire bytes
ACK count
ACK wait
direction switches
queue occupancy
buffer occupancy
ring occupancy
retry
blanked frames
local-source rejected frames
duty headroom
temperature if available
```

snapshot只读，不阻塞pipeline。

检测：

```text
goodput drift
queue sawtooth
periodic idle
counter saturation
memory leak
descriptor leak
```

---

# 27. Shutdown

每个hardware stage：

```text
shutdown-before
bounded run
shutdown-after
```

任一异常：

```text
停止新TX
撤销arm
active mask=0
abort performance mode
处理descriptor
SD shutdown
program两端shutdown bitstream
保存日志
```

最终：

```text
SHUTDOWN_FIXED=PASS
SHUTDOWN_ROTATING=PASS
```

无法确认shutdown属于严重阻塞。

---

# 28. 精简回归策略

本阶段不默认重跑所有历史。

运行：

```text
P10/P10.1 frozen verify-existing
P8C safety verify-existing
focused admission/ACK/pipeline tests
fixed/rotating build
P10.1R hardware campaign
```

公共core修改时，仅扩大受影响的：

```text
selective-repeat
SACK
DMA
safety
```

回归。

---

# 29. Evidence

run ID：

```text
p10_1r_<UTC>_<source>_<fixedbit>_<rotbit>
```

目录：

```text
evidence/hardware/p10_1r/<run_id>/
```

子目录：

```text
authorization
artifacts
safe_boot
echo_tail
crosstalk_remediation
phy_sanity
ack_tuning
sustained_performance
streaming_64m
formal_30min
shutdown
raw_logs
final
```

generated：

```text
p10_1r_repo_intake
p10_1r_failure_baseline
p10_1r_rx_admission_design
p10_1r_self_echo_model
p10_1r_ack_pipeline_model
p10_1r_xsim
p10_1r_fixed_build
p10_1r_rotating_build
p10_1r_artifact_freeze
p10_1r_authorization
p10_1r_safe_boot
p10_1r_echo_tail
p10_1r_crosstalk_remediation
p10_1r_phy_sanity
p10_1r_ack_tuning
p10_1r_performance
p10_1r_streaming_64m
p10_1r_formal_30min
p10_1r_shutdown
p10_1r_evidence_consistency
p10_1r_final_summary
```

每项：

```text
.md
.json
```

---

# 30. Requirement IDs

新增：

```text
P10_1R-ECHO-001 per-module TX/RX exclusion
P10_1R-ECHO-002 same-module accepted DATA zero
P10_1R-ECHO-003 raw echo remains observable
P10_1R-ECHO-004 other lane not blanked
P10_1R-ECHO-005 guard measured and bounded

P10_1R-ACK-001 bundle burst >=24
P10_1R-ACK-002 no per-object turnaround
P10_1R-ACK-003 multiple objects in flight
P10_1R-HOST-001 host not in fast path

P10_1R-PERF-001 F→R >=4.0 Mbit/s
P10_1R-PERF-002 R→F >=4.0 Mbit/s
P10_1R-STREAM-001 5×64 MiB F→R
P10_1R-STREAM-002 5×64 MiB R→F
P10_1R-SOAK-001 30-minute speed/stability
```

---

# 31. Machine state

开始：

```text
current_program_stage:
P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION

p10_1r_status:
IN_PROGRESS

current_run_hardware_authorization:
false until validated
```

通过后：

```text
p10_1r_status:
PASS

two_lane_speed_stability:
PASS

p11_status:
NOT_STARTED

p11_hardware_ready:
false
```

保持：

```text
P10 PASS
Ethernet deferred
SPI pending
physical permit pending
external duty pending
handover pending
8x32 pending
600rpm pending
product final pending
```

---

# 32. Mandatory exit gates

```text
FAILURE_BASELINE_FROZEN: PASS
OLD_AUTHORIZATION_CLOSED: PASS

PER_MODULE_TX_RX_EXCLUSION: PASS
OTHER_LANE_NOT_BLANKED: PASS
DECODER_CLEAR_ON_TX: PASS
POST_TX_GUARD_MEASURED: PASS
LOCAL_SOURCE_REJECTION: PASS

SAME_MODULE_RAW_ECHO_OBSERVABLE: PASS
SAME_MODULE_ACCEPTED_DATA_ZERO: PASS
NON_TARGET_ACCEPTED_CRC_VALID_ZERO: PASS
CROSS_LANE_ACCEPTED_ZERO: PASS

ACK_BUNDLE_WINDOW: PASS
NO_PER_OBJECT_TURNAROUND: PASS
MULTI_OBJECT_PIPELINE: PASS
HOST_NOT_IN_FAST_PATH: PASS

F_TO_R_APPLICATION_GOODPUT_4MBPS: PASS
R_TO_F_APPLICATION_GOODPUT_4MBPS: PASS

STREAMING_64M_F_TO_R_5X: PASS
STREAMING_64M_R_TO_F_5X: PASS
STREAM_ABORT_RESET_RECOVERY: PASS

STATIONARY_30MIN: PASS

CRC_BAD_ZERO: PASS
SHA_MISMATCH_ZERO: PASS
PARTIAL_DUPLICATE_STALE_ZERO: PASS
RETRY_EXHAUSTED_ZERO: PASS
DESCRIPTOR_LEAK_ZERO: PASS
DOUBLE_COMPLETION_ZERO: PASS
DEADLOCK_ZERO: PASS
DUTY_VIOLATION_ZERO: PASS
CONTINUOUS_HIGH_VIOLATION_ZERO: PASS

SHUTDOWN_FIXED: PASS
SHUTDOWN_ROTATING: PASS
EVIDENCE_CONSISTENCY: PASS
```

---

# 33. 失败分级

## PASS

全部 mandatory gates通过。

## PARTIAL

例如：

```text
self-echo admission修复通过
64 MiB和稳定性通过
但一个方向goodput<4.0
```

状态：

```text
P10_1R:
PARTIAL

P10_FUNCTIONAL:
PASS

TWO_LANE_PERFORMANCE:
FAIL
```

## FAIL_WITH_PERFORMANCE_EVIDENCE

完整性和安全通过，但速度不达标。

## FAIL

以下任一：

```text
same-module accepted DATA >0
错误对象提交
descriptor double completion
duty/stuck-high violation
无法shutdown
artifact/evidence错误
```

---

# 34. Git checkpoint

建议提交：

```text
feat: add per-module TFDU TX/RX admission exclusion
feat: pipeline two-lane ACK windows and multi-object transfer
test: add P10.1R two-lane speed and stability evidence
test: freeze P10.1R checkpoint
```

PASS tag：

```text
p10.1r-2lane-speed-stability-pass
```

未达到4.0：

```text
p10.1r-2lane-remediation-investigated
```

不得使用pass。

不push、不merge main，除非用户另行要求。

---

# 35. 最终输出

```text
P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION:
PASS / FAIL / PARTIAL

BASE_FAILURE_TAG:
<value>

P10_1R_SOURCE_COMMIT:
<hash>

P10_1R_EVIDENCE_CHECKPOINT:
<hash>

P10_1R_TAG:
<tag>

BRANCH:
p10.1r/2lane-speed-stability-remediation

WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10_1R

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

WIRING_CHANGED:
false

RX_GUARD_CYCLES_F0:
<value>

RX_GUARD_CYCLES_F1:
<value>

RX_GUARD_CYCLES_R0:
<value>

RX_GUARD_CYCLES_R1:
<value>

SAME_MODULE_RAW_ECHO_COUNT:
<value>

SAME_MODULE_BLANKED_FRAME_COUNT:
<value>

SAME_MODULE_ACCEPTED_DATA_COUNT:
0

CROSS_LANE_ACCEPTED_DATA_COUNT:
0

BEST_BURST_FRAMES:
<value>

BEST_ACK_THRESHOLD:
<value>

BEST_ACK_MAX_DELAY:
<value>

OBJECTS_IN_FLIGHT:
<value>

HOST_BLOCKING_COMMANDS_F_TO_R:
<value>

HOST_BLOCKING_COMMANDS_R_TO_F:
<value>

F_TO_R_APPLICATION_GOODPUT_BPS:
<value>

R_TO_F_APPLICATION_GOODPUT_BPS:
<value>

F_TO_R_4MBPS_TARGET:
PASS/FAIL

R_TO_F_4MBPS_TARGET:
PASS/FAIL

ACK_WAIT_RATIO_BEFORE:
~0.914

ACK_WAIT_RATIO_AFTER:
<value>

INTER_OBJECT_RATIO_BEFORE:
~0.445

INTER_OBJECT_RATIO_AFTER:
<value>

STREAMING_64M_F_TO_R:
PASS/FAIL

STREAMING_64M_R_TO_F:
PASS/FAIL

STATIONARY_30MIN:
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

P11_STATUS:
NOT_STARTED

PASS:
<list>

FAIL:
<list>

GENERATED_EVIDENCE:
<list>

NEXT_RECOMMENDED_STAGE:
USER_DECISION_AFTER_2LANE_SPEED_STABILITY_PASS
```

---

# 36. Definition of Done

本阶段完成意味着：

```text
当前4个TFDU的same-module raw echo仍可观测；
same-module echo不再进入frame、ACK/SACK、sequence、DMA和object路径；
lane0 TX不blank lane1，lane1 TX不blank lane0；
2-lane ACK和方向窗口使用大burst而非每对象串行；
Host不参与每对象fast path；
F→R和R→F均达到>=4.0 Mbit/s application goodput；
64 MiB双向多次传输通过；
30分钟正式运行无完整性、协议、descriptor、安全和shutdown错误；
P10功能性PASS保留；
P11仍未启动。
```

本阶段完成不意味着：

```text
1+1或4+4全双工通过；
P11 handover通过；
8×32通过；
600 rpm通过；
Ethernet/SPI通过；
physical GLOBAL_PERMIT通过；
external TFDU duty通过；
产品最终通过。
```

现在开始执行本 Goal。先冻结失败 evidence，再实施 per-module TX/RX admission 和 ACK/multi-object pipeline，完成focused offline gate；取得新的 current-run authorization后执行硬件复验。
