# P10 Fast-Track Mid-Run Override

```text
STAGE: P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET
THIS_GOAL_SUPERSEDES_PREVIOUS_P10_GOAL: true
OLD_HOLD_POINTS_CANCELLED: true

WIRING_ALREADY_COMPLETED: true
WIRING_ALREADY_CONFIRMED_WITH_CODEX: true
NO_FURTHER_USER_CONFIRMATION_REQUIRED: true
ASK_USER_ONLY_FOR_SEVERE_BLOCKERS: true

P10_HARDWARE_AUTHORIZATION: GRANTED_WITH_THIS_GOAL
MAX_RUNTIME_SECONDS: 1800

MAIN:
C:\Users\user\Documents\RF_COMM_MULTILANE

P10_WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10

P10_BRANCH:
p10/ax7020-dual-node-2lane

HARDWARE:
2 × AX7020
2 × TFDU small boards per AX7020

ROLES:
AX7020-F owns F0/F1
AX7020-R owns R0/R1

LANES:
lane0 = F0 <-> R0
lane1 = F1 <-> R1

NETWORK_USED: false
HARDWARE_MOVEMENT_ALLOWED: false
ROTATION_ALLOWED: false
REWIRING_ALLOWED: false
ALLOWED_LANE_MASKS: 0x1, 0x2, 0x3
```

## 1. 立即切换任务

收到本文件后：

1. 停止继续执行旧 P10 Goal 的确认流程和 HOLD POINT。
2. 保留旧 Goal 已完成的有效文件、审计、profile 和代码。
3. 不执行 `reset --hard`、自动 stash、删除 evidence 或重建未知 worktree。
4. 保存当前 branch、HEAD、worktree、dirty files和正在运行的命令。
5. 若旧任务尚未连接硬件，完成或安全终止当前离线命令后继续。
6. 若已经意外连接硬件，先 shutdown 两端并保存日志。
7. 本文件本身即为本次 P10 硬件授权。
8. 不再询问用户是否继续、是否构建、是否连接 JTAG、是否 program、是否运行 ELF 或是否执行正式测试。

## 2. 只有严重阻塞才询问用户

仅以下情况允许暂停：

- 接线与官方 pinout 明确冲突，存在损坏风险；
- VCC/GND、output-to-output 或 I/O bank 电压不兼容；
- 无法唯一地区分 AX7020-F 与 AX7020-R，存在 program 错板风险；
- 两块板经过有界重试仍无法被 JTAG 枚举，必须人工插拔或上电；
- 任一端无法确认 shutdown；
- 出现 duty、continuous-high、自主发射或最终 TX kill 安全违规；
- 必须连接 Ethernet、移动/旋转/调角/重接线或使用 lane mask >0x3；
- 必须修改 `PROJECT_CONSTRAINTS.txt`。

以下问题由 Codex 自主修复，不询问用户：

```text
编译/综合/时序错误
Vivado/Vitis/BSP/ELF错误
JTAG脚本和普通连接错误
DMA/cache/寄存器错误
协议和测试失败
日志解析错误
需要重新构建或重跑受影响stage
```

持续无法通过 mandatory gate 时，安全 shutdown 后输出 FAIL，不询问“是否继续”。

## 3. Worktree

优先继续现有：

```text
C:\Users\user\Documents\RF_COMM_MULTILANE_P10
p10/ax7020-dual-node-2lane
```

若尚不存在，从当前 clean `main` 创建。

必须验证：

```text
包含当前main整理基线
包含p8e-pass
包含p9-z7010-2lane-pass
无未知tracked修改
```

之后只在 P10 worktree 工作，不修改 P8/P9 冻结 worktree。

## 4. 复用已确认接线

直接复用当前会话和旧 Goal 中最新接线记录。

至少形成：

```text
config/hardware/p10_active_wiring.yaml
config/hardware/p10_board_inventory.yaml
config/hardware/p10_tfdu_module_inventory.yaml
```

记录每个模块的：

```text
Txd/Rxd/SD/Mode
VCC/GND
connector/package pin
I/O bank/VCCO/IOSTANDARD
module和lane ID
资料来源
```

非危险的文档缺口只标记 `DOCUMENTATION_GAP_NONBLOCKING`，不得再次停下来确认。

## 5. 精简预检

只运行：

```text
git/worktree状态
main/P8E/P9祖先检查
PROJECT_CONSTRAINTS hash
project_state与register-map一致性
P8E verify-existing
P9 verify-existing
接线和I/O bank安全审计
no-hardware静态扫描
```

不要默认重跑 P0-P9 全部历史回归。

规则：

- 仅改 board profile/wrapper/XDC/BSP：运行板级 build、timing、CDC、安全 smoke和focused simulation。
- 改公共 protocol/safety/DMA core：运行受影响回归，并在正式硬件run前执行一次当前P10所需的portable regression。
- 公共core未改：复用immutable P8/P9 evidence。

## 6. 双AX7020构建

建立或完善：

```text
board_profiles/ax7020_common/
board_profiles/ax7020_fixed_2lane/
board_profiles/ax7020_rotating_2lane/
```

冻结：

```text
exact part
board revision
DDR
clock/reset
PS preset
pinmap/XDC
TFDU pins
node role/ID
DMA
register-map version
```

禁止复用 Z7010 XDC。

生成内容寻址 artifact：

```text
F shutdown bitstream
R shutdown bitstream
F functional bitstream
R functional bitstream
F XSA/BSP/ELF
R XSA/BSP/ELF
```

必要离线门：

```text
synthesis PASS
route PASS
WNS/WHS >= 0
TNS = 0
critical DRC = 0
unsafe CDC = 0
REQP-1839 = 0
register-map一致
TFDU safety smoke PASS
```

## 7. 已授权硬件动作

允许 Codex 自动：

```text
启动/连接hw_server
使用Hardware Manager batch和XSDB/JTAG
唯一识别两块AX7020
program shutdown/functional bitstream
下载运行两端PS ELF
使用JTAG/AXI、DDR、AXI DMA、UART、ILA/VIO
使能receiver并等待>=500 us
在0x1/0x2/0x3上受控TFDU发射
执行PS/PL/DMA reset和数字故障注入
运行最长1800秒静止测试
异常后自动shutdown两端
```

禁止：

```text
Ethernet
移动、旋转、调角、遮挡、换板、重接线
lane mask >0x3
```

## 8. 安全启动

每个正式run：

1. 唯一绑定 F/R 两块板；
2. program两端shutdown image；
3. 验证两端safe state；
4. program F candidate并检查safe boot；
5. program R candidate并检查safe boot；
6. 下载两端ELF，保持unarmed；
7. 读取build/profile/register hash；
8. 两端receive-only；
9. 等待>=500 us；
10. 按test stage显式arm。

safe boot必须：

```text
Txd request=0
TX intent=0
endpoint armed=0
active TX mask=0
outstanding physical attempt=0
no autonomous TX
```

任一端失败：立即shutdown两端并停止formal run。

## 9. 快速正式测试

### A. 单板bring-up

两端分别验证：

```text
DDR
AXI-Lite
DMA ring/cache
descriptor wrap
reset/abort
TFDU SD/Mode/Txd/Rxd
startup/duty/stuck-high
shutdown
```

### B. 四方向raw

```text
F0→R0
R0→F0
F1→R1
R1→F1
```

每方向：

```text
64 pulse smoke
1024 pulse acceptance
```

同时读取全部4个RX，输出4×4 echo/crosstalk矩阵。

### C. 4 Mbit/s/lane

raw通过后直接测试4 Mbit/s；失败时才回退2/1 Mbit/s诊断。

每lane每方向：

```text
100-frame smoke
10000-frame clean run
247-byte counter/PRBS
```

要求：

```text
CRC bad=0
retry exhausted=0
duty violation=0
continuous-high violation=0
```

随后验证：

```text
lane mask=0x3
4 Mbit/s/lane
8 Mbit/s aggregate RAW capability
```

### D. 双节点协议

验证：

```text
selective-repeat
32 outstanding
SACK 32
ACK aggregation
sequence wrap
loss/reorder/duplicate recovery
stale session/path rejection
```

### E. 两端真实DMA/DDR/cache

验证：

```text
F TX DMA → R RX DMA
R TX DMA → F RX DMA
ring wrap/generation
cache ownership
reset/abort
single completion
descriptor leak=0
```

JTAG direct copy不能代替远端DMA。

### F. 双PS对象

正式路径：

```text
PS-F→PL-F→TFDU→TFDU→PL-R→PS-R
PS-R→PL-R→TFDU→TFDU→PL-F→PS-F
```

mandatory：

```text
4 KiB
64 KiB
1 MiB
```

通过后执行16 MiB；64 MiB为非阻塞扩展。

每个对象：

```text
CRC32 match
SHA256 match
partial/duplicate/stale commit=0
```

### G. 节点重启恢复

执行：

```text
不同启动顺序
F/R PS reboot
F/R PL soft reset
F/R DMA reset
outstanding期间单端reset
旧data/ACK迟到
```

要求：

```text
stale commit=0
bounded reacquisition
重启后新对象成功
```

### H. Scheduler/fault

验证：

```text
lane0-only
lane1-only
2-lane equal weight
lane0/1 unavailable和恢复
retry migration
acked frame never migrates
```

### I. 性能

报告：

```text
PHY_RAW_BPS
FRAME_GOODPUT_BPS
APPLICATION_GOODPUT_BPS_F_TO_R
APPLICATION_GOODPUT_BPS_R_TO_F
DMA/PS/airtime延迟
```

当前2-lane P10不以最终产品16 Mbit/s为门。

### J. 30分钟正式run

```text
1800 seconds
lane mask=0x3
无Ethernet
无移动
```

循环F→R和R→F的4 KiB、64 KiB、1 MiB对象。

clean acceptance：

```text
CRC bad=0
SHA mismatch=0
partial/duplicate/stale commit=0
retry exhausted=0
descriptor leak/double completion=0
deadlock=0
duty/continuous-high violation=0
```

## 10. 非阻塞扩展

核心mandatory通过且不需人工操作时可执行：

```text
lane0 F→R + lane1 R→F 的1+1 full-duplex实验
FreeRTOS local-service smoke
16/64 MiB chained streaming
更完整的crosstalk分析
```

扩展失败不推翻P10核心半双工PASS。

## 11. 自动修复和重试

Codex自主修复RTL、XDC、BSP、ELF、DMA、协议和脚本。

有界重试：

```text
JTAG connect <=3
program <=2
单stage diagnostic run_id <=2
```

每次硬件重试前shutdown两端。

最终formal PASS必须来自一个完整run_id，不拼接多个run。

## 12. Shutdown

任一失败、异常、超时或退出：

```text
停止新TX
撤销arm
active TX mask=0
处理outstanding attempt
请求SD shutdown
program两端shutdown image
保存日志
```

最终必须：

```text
SHUTDOWN_FIXED: PASS
SHUTDOWN_ROTATING: PASS
```

无法确认任一端shutdown属于严重阻塞。

## 13. Evidence和Git

每次run：

```text
evidence/hardware/p10/<run_id>/
```

至少保存：

```text
authorization/wiring/board identity
artifact manifest
safe boot
raw/PHY/protocol
DMA/DDR/cache
dual-PS objects
reset recovery
scheduler/performance
30-minute run
shutdown/raw logs/final
```

生成：

```text
evidence/generated/p10_fasttrack_final_summary.md
evidence/generated/p10_fasttrack_final_summary.json
```

成功提交并tag：

```text
feat: migrate two independent AX7020 endpoints
test: freeze P10 AX7020 dual-node evidence
tag: p10-ax7020-dual-node-2lane-pass
```

不要push远端。

## 14. Mandatory结果

```text
F/R build、role binding、safe boot、shutdown: PASS
四方向raw: PASS
lane0/lane1双向4 Mbit/s: PASS
2-lane 8 Mbit/s RAW capability: PASS
selective-repeat/SACK/ACK aggregation/wrap: PASS
两端DMA/DDR/cache: PASS
双独立PS/reset、无共享RAM: PASS
F→R与R→F对象CRC/SHA: PASS
重启恢复、scheduler、lane fault、retry migration: PASS
30分钟静止run: PASS
evidence consistency: PASS
```

P10通过后只允许声明：

```text
P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET: PASS
DUAL_Z7020_INDEPENDENT_ENDPOINTS: PASS
DUAL_Z7020_2LANE_OPTICAL_LINK: PASS
DUAL_Z7020_PS_PL_PHY_PL_PS: PASS
STATIONARY_2LANE_30MIN: PASS
```

仍保持：

```text
ETHERNET: DEFERRED
SPI: PENDING
PHYSICAL_GLOBAL_PERMIT: PENDING_D17
EXTERNAL_TFDU_DUTY: PENDING
HANDOVER: PENDING_P11
8X32: PENDING_P12
600RPM: PENDING_P13
PRODUCT_FINAL: PENDING
```

## 15. 最终输出

```text
P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET:
PASS / FAIL / PARTIAL

P10_SOURCE_COMMIT:
P10_EVIDENCE_CHECKPOINT:
P10_TAG:
WORKTREE_CLEAN:

WIRING_ALREADY_CONFIRMED: true
CURRENT_RUN_HARDWARE_AUTHORIZATION: true
HARDWARE_ACTIONS_EXECUTED:
NETWORK_USED: false
NO_HARDWARE_MOVEMENT: true
MAX_LANE_MASK_USED: 0x3

FIXED_BOARD_ID:
ROTATING_BOARD_ID:

FOUR_DIRECTION_RAW:
LANE0_4MBPS:
LANE1_4MBPS:
TWO_LANE_8MBPS_RAW:

SELECTIVE_REPEAT_SACK:
DMA_DDR_CACHE_FIXED:
DMA_DDR_CACHE_ROTATING:
DUAL_INDEPENDENT_PS:
NO_SHARED_RAM:
F_TO_R_OBJECT:
R_TO_F_OBJECT:
OBJECT_SHA256:
ENDPOINT_REBOOT_RECOVERY:
STATIONARY_30MIN:

APPLICATION_GOODPUT_F_TO_R_BPS:
APPLICATION_GOODPUT_R_TO_F_BPS:

SHUTDOWN_FIXED:
SHUTDOWN_ROTATING:

PASS:
FAIL:
NONBLOCKING_EXTENSIONS:
GENERATED_EVIDENCE:
UNCHANGED_PENDING_SCOPES:

NEXT_RECOMMENDED_STAGE:
P11_SINGLE_LOGICAL_LANE_FOUR_FIXED_MODULE_HANDOVER
or P10_REMEDIATION
```

立即保存旧Goal当前状态并切换到本Goal。不要再停在旧HOLD POINT；只有本文第2节定义的严重阻塞才联系用户。
