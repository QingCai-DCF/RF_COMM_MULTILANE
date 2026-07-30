# RF_COMM_MULTILANE — P10 AX7020 双独立节点、静止 2-Lane、无 Ethernet Goal

## 两块 AX7020、每板两个 TFDU 小板、双独立 PS/PL/DMA/DDR 的真实光链路迁移与验收

```text
DOCUMENT_TYPE: CODEX_EXECUTION_GOAL
STAGE: P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET
STAGE_CLASS: BOARD_MIGRATION_AND_AUTHORIZED_HARDWARE_STAGE

EXPECTED_PREVIOUS_STAGE:
P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION

EXPECTED_P9_SCOPE:
PLATFORM_LIMITED_PASS

RECOMMENDED_BRANCH:
p10/ax7020-dual-node-2lane

RECOMMENDED_WORKTREE:
C:\Users\user\Documents\RF_COMM_MULTILANE_P10

HARDWARE_TOPOLOGY:
2 × AX7020 development boards
2 × TFDU small boards per AX7020
4 × TFDU small boards total
2 × bidirectional optical lanes

FIXED_ROLE_BOARD:
AX7020-F

ROTATING_ROLE_BOARD:
AX7020-R
# 本阶段保持静止；“ROTATING_ROLE”仅表示最终架构角色。

LANE0:
AX7020-F / F0  <->  AX7020-R / R0

LANE1:
AX7020-F / F1  <->  AX7020-R / R1

NETWORK_CABLE_CONNECTED:
false

ETHERNET_REQUIRED:
false

HARDWARE_MOVEMENT_ALLOWED:
false

ROTATION_ALLOWED:
false

OPTICAL_ALIGNMENT_CHANGE_ALLOWED_DURING_FORMAL_RUN:
false

LANE_MASK_ALLOWED:
0x1, 0x2, 0x3

MAX_LANE_MASK:
0x3

MAX_FORMAL_STATIONARY_RUN_SECONDS:
1800

WIRING_CONFIRMATION_REQUIRED:
true

CURRENT_RUN_HARDWARE_AUTHORIZATION:
false until separately granted by the user

PRODUCT_FINAL_ACCEPTANCE:
PENDING
```

本文件是 Codex 的可执行 Goal。Codex 必须实际完成仓库 intake、P9 收口、AX7020 板级资料审计、接线方案生成、用户确认门、双 board profile、离线构建、真实硬件 bring-up、双节点光链路、真实 DMA/DDR/cache、双向对象、节点重启恢复、性能测量、30 分钟静止测试、shutdown、evidence 和 Git checkpoint。

本 Goal 中存在两个不可跳过的人工边界：

```text
HOLD POINT A:
用户确认 Codex 生成的具体接线表和接线图。

HOLD POINT B:
用户完成接线后，明确授权本次 P10 硬件运行。
```

在两个 hold point 均未关闭前，Codex 不得连接硬件。

---

# 1. P10 的目标和范围

P10 的主目标是把已在 Z7010 单板双端点上通过的 portable architecture，迁移到两块真实 AX7020，并首次形成：

```text
两个独立 FPGA
两个独立 PS
两个独立 PL
两个独立 DDR
两套真实 DMA ring
两套独立时钟和 reset
两套独立 node/session epoch
无共享 RAM
无内部 payload loopback
两条真实 TFDU 光学 lane
```

正式主路径：

```text
Host loads object into AX7020-F PS memory
→ AX7020-F PS service
→ AX7020-F DMA / DDR
→ AX7020-F PL endpoint
→ F0/F1 TFDU transmitter
→ real stationary optical path
→ R0/R1 TFDU receiver
→ AX7020-R PL endpoint
→ AX7020-R DMA / DDR
→ AX7020-R PS object service
→ Host reads AX7020-R committed object
```

反向路径：

```text
Host loads object into AX7020-R PS memory
→ AX7020-R PS/PL
→ R0/R1 TFDU
→ optical path
→ F0/F1 TFDU
→ AX7020-F PL/PS
→ Host reads AX7020-F committed object
```

反向 ACK/SACK 同样必须经过真实光链路。

P10 不允许用以下路径替代正式验收：

```text
PC 内存直接复制
两板之间 USB/JTAG 文件复制
共享 host buffer
一个 FPGA 内部 loopback
一个 PS 控制两个 endpoint
JTAG-to-AXI 绕过远端 PS runtime
纯 RTL 数字回环
```

JTAG、UART 和 host 工具只用于：

```text
加载输入
启动两端程序
配置
日志
诊断
读取最终输出和 evidence
```

---

# 2. P10 不证明的内容

即使 P10 全部通过，仍不能声明：

```text
8-lane hardware PASS
32 fixed modules PASS
8 rotating modules PASS
sector-bank PASS
ABZ PASS
真实 handover PASS
真实旋转 PASS
600 rpm PASS
D200/D600 全环 PASS
Ethernet PASS
SPI peer PASS
最终 4+4 full-duplex PASS
最终物理 GLOBAL_PERMIT PASS
最终系统红外安全 PASS
产品最终验收 PASS
```

当前四个 TFDU 小板只能组成：

```text
2 个端到端双向 lane
```

不能组成正式 P11 所需的：

```text
1 rotating module + 4 fixed modules
```

因此 P10 不是 handover 阶段。

---

# 3. P9 收口必须先完成

开始 P10 前，Codex 必须审计最新 canonical P9 evidence，并关闭以下流程遗留：

```text
current_run_hardware_authorization 必须恢复 false
P9 authorization 标记 consumed
P9 source/evidence/tag 身份固定
P9 final summary 不保留 checkpoint 占位值
P9 project_state 与 PROJECT_STATUS 一致
external duty 状态改为 PENDING_EXTERNAL_MEASUREMENT
physical permit 状态保持 PENDING_D17
legacy AB_L1 failure 保留
current P9 stationary lane1 状态为 PASS
```

新增或验证：

```text
evidence/generated/p9_closeout_summary.md
evidence/generated/p9_closeout_summary.json
evidence/generated/p9_git_checkpoint_metadata.json
```

若 P9 尚未存在正式 pass tag：

- 不得自行伪造；
- 使用最新 canonical P9 PASS checkpoint；
- 记录实际 tag/commit；
- 若 P9 不是 PASS，停止创建 P10 正式硬件阶段，先完成 P9 收口。

P10 worktree 必须从最新 P9 evidence checkpoint/tag 创建，以继承真实 DMA、PS runtime、安全和协议修复。

---

# 4. Worktree 和 Git

推荐：

```text
C:\Users\user\Documents\RF_COMM_MULTILANE_P10
branch:
p10/ax7020-dual-node-2lane
```

Codex 自动发现 P9 pass tag；预期名称可能为：

```text
p9-z7010-2lane-pass
```

但不得只依赖名称。必须验证：

```text
tag type
tag target
source commit
evidence commit
project state
artifact manifest
P9 final status
```

创建：

```powershell
git worktree add `
  -b p10/ax7020-dual-node-2lane `
  C:\Users\user\Documents\RF_COMM_MULTILANE_P10 `
  <verified-p9-pass-tag-or-checkpoint>
```

不得修改：

```text
C:\Users\user\Documents\RF_COMM
C:\Users\user\Documents\RF_COMM_MULTILANE
冻结的 P8/P9 worktree
```

不得移动：

```text
p8a-pass
p8b-pass
p8c-pass
p8d-pass
p8e-pass
P9 pass tag
```

---

# 5. 开始前 repository intake

生成：

```text
evidence/generated/p10_repo_intake.md
evidence/generated/p10_repo_intake.json
```

记录：

```text
worktree
branch
HEAD
P9 base tag/checkpoint/source
git status
PROJECT_CONSTRAINTS.txt hash
AGENTS.md hash
project_state hash
project_requirements hash
register map hash
P9 closeout summary hash
Vivado version
Vitis version
xsim version
Python version
current hardware authorization
start timestamp
```

运行：

```powershell
$env:NO_HARDWARE = '1'
$env:CURRENT_RUN_HARDWARE_AUTHORIZATION = 'false'

python scripts/run_offline_gates.py --include-p8e
python <p9-gate-entry> --verify-existing --json-summary
git diff --check
```

要求：

```text
P8E/P9 immutable recheck: PASS
offline regression: PASS
worktree clean before P10 changes
hardware authorization: false
```

---

# 6. AX7020 板级资料 intake

## 6.1 不允许仅凭“AX7020”猜测

Codex 必须确定两块开发板的：

```text
厂家
完整型号
PCB revision
FPGA 完整料号
package
speed grade
temperature grade
board serial or inventory ID
DDR 型号和容量
输入时钟源和频率
PS preset
MIO 分配
JTAG controller/cable identity
UART bridge和端口
PL connector名称
PL connector pinout
PL I/O bank
bank VCCO
clock-capable pins
on-board pull-up/down
电源和 reset 拓扑
```

若两块板 revision 不同，必须使用独立 board base profile。

若资料不在仓库中，Codex 必须生成：

```text
docs/hardware/P10_REQUIRED_BOARD_DOCUMENTS.md
```

并向用户请求：

```text
两块板正反面清晰照片
PCB revision照片
FPGA marking照片
官方用户手册
官方原理图
PL connector pinout
TFDU 小板原理图或 pinout
```

在关键资料缺失时，不得猜 pin，不得进入接线确认。

## 6.2 官方资料优先级

接线依据优先级：

```text
1. 官方原理图
2. 官方 PCB/connector pinout
3. 官方用户手册
4. FPGA package/bank data
5. 用户提供的实际板卡照片
6. 已验证的现有小板资料
```

论坛图、非官方博客或相似型号资料不能作为唯一接线依据。

## 6.3 两块板唯一身份

创建：

```text
config/hardware/p10_ax7020_board_inventory.yaml
```

至少：

```text
fixed_board:
  role: FIXED
  board_model:
  pcb_revision:
  fpga_part:
  jtag_cable_serial:
  device_dna:
  uart_port:
  connector_revision:

rotating_board:
  role: ROTATING
  board_model:
  pcb_revision:
  fpga_part:
  jtag_cable_serial:
  device_dna:
  uart_port:
  connector_revision:
```

不能用 JTAG target 顺序区分角色。

---

# 7. TFDU 小板资料 intake

每块 TFDU 小板分配固定 ID：

```text
F0
F1
R0
R1
```

必须记录：

```text
小板 revision
TFDU 型号
connector pin order
VCC1/VCC2结构
是否集成去耦
是否集成 Mode strap
是否集成 SD pull
是否集成 Txd buffer
是否有 Rxd buffer
输入输出逻辑电平
GND pin
任何 LED、跳线或反相逻辑
```

创建：

```text
config/hardware/p10_tfdu_module_inventory.yaml
docs/hardware/P10_TFDU_SMALL_BOARD_PINOUT.md
```

如果小板资料不明确，Codex 应先让用户确认小板 pinout，不能从旧 Z7010 XDC 推断。

---

# 8. 接线方案设计

## 8.1 每个 TFDU 的基本信号

对每个模块至少处理：

```text
Txd   FPGA output → TFDU input，active high
Rxd   TFDU output → FPGA input，active low
SD    FPGA output → TFDU input，active high shutdown
Mode  FPGA output或硬件strap → TFDU input，高速模式
VCC
GND
```

如果小板已有固定 Mode strap，则不得同时由 FPGA 强驱。

如果 VCC1/VCC2分开引出，必须在 wiring proposal中分别定义。

## 8.2 每块 AX7020 的最小 PL I/O

若 Mode 由 PL 驱动，每板至少：

```text
2 × Txd outputs
2 × Rxd inputs
2 × SD outputs
2 × Mode outputs
= 8 PL signals
```

可选：

```text
GLOBAL_PERMIT physical input
external fault input
debug trigger
```

当前没有最终 D17电路时，不得强行把普通 PL寄存器冒充最终物理 permit。

## 8.3 选 pin 原则

Codex 必须检查：

```text
pin 属于 PL，不是 PS MIO
pin 未被 DDR占用
pin 未被启动/配置占用
pin 未与板载外设冲突
VCCO 与 TFDU逻辑电平兼容
output pin power-up状态可控
Rxd使用输入
Txd/SD/Mode使用输出
无 output-to-output连接
无跨bank电压冲突
无未解释的on-board pull
连接器pin编号无镜像错误
GND回路明确
```

优先：

```text
同一或兼容I/O bank
短路径
明确3.3V或经确认的兼容电平
避免时钟/差分专用资源冲突
保留未来debug pin
```

不得复用 Z7010 pinmap/XDC。

## 8.4 Lane 配对

固定：

```text
Lane0:
F0 ↔ R0

Lane1:
F1 ↔ R1
```

模块物理位置和朝向由用户完成，formal run期间不再改变。

---

# 9. Codex 必须生成的接线提案

生成：

```text
docs/hardware/P10_AX7020_DUAL_BOARD_WIRING_PROPOSAL.md
config/hardware/p10_ax7020_dual_board_wiring_proposal.yaml
evidence/generated/p10_wiring_design_audit.md
evidence/generated/p10_wiring_design_audit.json
```

Markdown中每根线必须有一行：

| Board role | Module | Logical signal | Direction at FPGA | AX7020 connector | Connector pin | FPGA package pin | I/O bank | VCCO | IOSTANDARD | TFDU board pin | Reset/default | Pull | Source document | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|

至少覆盖：

```text
F0 Txd/Rxd/SD/Mode/VCC/GND
F1 Txd/Rxd/SD/Mode/VCC/GND
R0 Txd/Rxd/SD/Mode/VCC/GND
R1 Txd/Rxd/SD/Mode/VCC/GND
```

提案还必须包含：

```text
板级俯视连接器方向说明
pin-1定位方法
线束编号
模块编号标签
lane0/lane1光学配对图
JTAG cable角色
UART角色
供电顺序
未使用pin处理
接线前检查
接线后但上电前检查
```

生成冻结哈希：

```text
WIRING_PROPOSAL_SHA256
BOARD_DOC_SET_SHA256
TFDU_PINOUT_SHA256
```

---

# 10. HOLD POINT A：用户接线确认

Codex 完成接线提案后必须停止，不得连接硬件。

终端输出：

```text
P10_WIRING_PROPOSAL_READY: true
HARDWARE_ACTIONS_EXECUTED: false
USER_CONFIRMATION_REQUIRED: true

WIRING_PROPOSAL:
docs/hardware/P10_AX7020_DUAL_BOARD_WIRING_PROPOSAL.md

WIRING_PROPOSAL_SHA256:
<sha256>

OPEN_WIRING_QUESTIONS:
<list>

NEXT_REQUIRED_USER_ACTION:
review and confirm or correct the proposed wiring
```

用户确认文本至少包含：

```text
P10_WIRING_MAP_CONFIRMED: true
WIRING_PROPOSAL_SHA256: <exact hash>
FIXED_BOARD_ROLE_CONFIRMED: true
ROTATING_BOARD_ROLE_CONFIRMED: true
LANE0_PAIR_CONFIRMED: F0-R0
LANE1_PAIR_CONFIRMED: F1-R1
```

如果用户修改任意 pin，Codex必须更新提案和hash，再次等待确认。

不能接受：

```text
“差不多”
“按之前接”
“应该对”
```

作为 wiring freeze。

---

# 11. 用户完成实际接线后的状态确认

用户实际接线后，应提供：

```text
P10_PHYSICAL_WIRING_COMPLETED: true
WIRING_PROPOSAL_SHA256: <exact confirmed hash>
BOTH_BOARDS_POWERED_OFF_DURING_WIRING: true
NO_UNDOCUMENTED_WIRES: true
```

建议用户提供接线照片供 Codex与冻结表核对，但照片不是自动电气安全证明。

Codex生成：

```text
evidence/hardware/p10/<run_id>/wiring/user_wiring_confirmation.txt
evidence/hardware/p10/<run_id>/wiring/wiring_confirmation_record.json
```

---

# 12. HOLD POINT B：当前运行硬件授权

接线确认不等于硬件执行授权。

Codex必须等待用户发送等价声明：

```text
我授权 Codex 按已确认的
P10_AX7020_DUAL_BOARD_WIRING_PROPOSAL
和本 P10 Goal，对两块 AX7020、四个 TFDU 小板、静止两 lane
执行自动化硬件操作。

允许：
- 启动/连接 hw_server、Vivado Hardware Manager、XSDB/JTAG；
- 分别识别两块板和 JTAG cable；
- 构建并 program 已冻结 SHA256 的 shutdown/candidate bitstream；
- 下载并运行已冻结 SHA256 的两端 PS ELF；
- 使用 JTAG、UART、AXI、DMA、DDR、ILA/VIO和寄存器；
- 使能 TFDU receiver并等待至少500 us；
- 在lane mask 0x1、0x2、0x3上受控发射；
- 执行节点reset/reboot、DMA reset和协议故障注入；
- 运行最长1800秒静止测试；
- 异常时自动关闭两端发射并program shutdown image。

禁止：
- 移动、旋转、调角、遮挡、交换或重新接线硬件；
- 使用lane mask >0x3；
- 使用Ethernet；
- 将结果外推到8 lane、旋转、600 rpm或产品最终验收。
```

授权记录必须绑定：

```text
wiring proposal hash
fixed/rotating profile hash
source commit
bitstream hashes
ELF hashes
max runtime
board JTAG identities
lane mask upper bound
```

如果没有当前授权：

```text
P10_HARDWARE_AUTHORIZATION: FAIL_CLOSED
```

只允许离线构建和dry-run。

---

# 13. Board profile架构

## 13.1 Common base + role overlay

如果两块板型号和revision相同，推荐：

```text
board_profiles/ax7020_common/
board_profiles/ax7020_fixed_2lane/
board_profiles/ax7020_rotating_2lane/
```

common包含：

```text
exact part
DDR
clock
reset
connector base
I/O bank
PS preset
JTAG/UART基础
```

role overlay包含：

```text
node role
node ID
session role
F0/F1或R0/R1命名
firmware role
endpoint defaults
```

如果revision不同，建立两个独立base profile。

## 13.2 必需文件

至少：

```text
board_profiles/ax7020_common/board_identity.yaml
board_profiles/ax7020_common/ps_preset.tcl
board_profiles/ax7020_common/clock_reset.yaml

board_profiles/ax7020_fixed_2lane/profile.yaml
board_profiles/ax7020_fixed_2lane/pinmap.csv
board_profiles/ax7020_fixed_2lane/ACTIVE_PROFILE.json

board_profiles/ax7020_rotating_2lane/profile.yaml
board_profiles/ax7020_rotating_2lane/pinmap.csv
board_profiles/ax7020_rotating_2lane/ACTIVE_PROFILE.json

constraints/active/AX7020_FIXED_2LANE.generated.xdc
constraints/active/AX7020_ROTATING_2LANE.generated.xdc
```

不得把两份active XDC同时加入一个build。

## 13.3 Profile差异

固定侧和旋转侧可以共用core，但必须有：

```text
独立 top/wrapper
独立 build/profile ID
独立 node ID
独立 firmware image
独立 artifact manifest
```

不允许一个 bitstream通过JTAG target顺序自动猜角色。

---

# 14. Offline build和验证

在硬件连接前必须完成：

```text
profile schema
pin uniqueness
I/O bank voltage audit
constraint completeness
DDR/PS preset generation
common-core source manifest
register map consistency
software header consistency
fixed build
rotating build
synthesis
implementation
timing
CDC/RDC
DRC
resource
post-synthesis safety smoke
dual-endpoint XSIM
P0-P9 preserved regression
```

对每个角色正式build：

```text
exact discovered AX7020 FPGA part
correct top
correct XDC
correct PS preset
correct DDR
correct node role
```

硬门：

```text
WNS >=0
WHS >=0
TNS=0
unconstrained internal endpoints=0
critical DRC=0
critical methodology=0
unsafe CDC=0
REQP-1839=0
```

未知外部 I/O delay不能伪造为0 ns。必须通过：

```text
documented board timing contract
or
PENDING_BOARD_IO_EXTERNAL_CONTRACT
```

但 pin和IOSTANDARD必须真实冻结。

---

# 15. Immutable artifacts

每个角色构建：

```text
AX7020-F shutdown bitstream
AX7020-R shutdown bitstream
AX7020-F functional bitstream
AX7020-R functional bitstream
AX7020-F XSA
AX7020-R XSA
AX7020-F BSP/platform
AX7020-R BSP/platform
AX7020-F PS ELF
AX7020-R PS ELF
```

内容寻址：

```text
artifacts/p10/<run_id>/fixed/<sha256>/...
artifacts/p10/<run_id>/rotating/<sha256>/...
```

禁止：

```text
latest.bit
current.bit
output.bit
app.elf
```

直接用于正式program。

manifest记录：

```text
source commit
board role
board identity
exact part
top
profile hash
pinmap hash
XDC hash
PS preset hash
register map hash
bitstream hash
XSA hash
BSP hash
ELF hash
Vivado/Vitis version
build command
timing/DRC report hash
```

---

# 16. 双板target识别

Codex必须通过：

```text
JTAG cable serial
device DNA
FPGA part
board inventory
UART identity
build ID readback
```

区分：

```text
AX7020-F
AX7020-R
```

不得使用：

```text
第一个target=固定
第二个target=旋转
```

除非同时由唯一硬件身份确认。

如果身份不明确：

```text
P10_TARGET_ROLE_BINDING: FAIL_CLOSED
```

不得program functional bitstream。

---

# 17. 安全启动顺序

每次运行：

1. 启动hw_server；
2. 枚举两个target；
3. 验证board身份；
4. program两端shutdown image；
5. 验证safe state；
6. 先program AX7020-F candidate；
7. 验证AX7020-F safe boot；
8. program AX7020-R candidate；
9. 验证AX7020-R safe boot；
10. 下载两端ELF但不自动arm；
11. 读取build/profile/register hash；
12. 清counter；
13. 进入receive-only；
14. 等待至少500 us；
15. 仅在当前test stage显式arm。

safe boot必须：

```text
Txd request=0
physical TX intent=0
endpoint armed=0
active lane mask=0
outstanding physical attempt=0
no autonomous payload TX
```

任何一端safe boot失败：

```text
立即shutdown两端
停止formal run
```

---

# 18. P10A：每块AX7020单板bring-up

对 AX7020-F 和 AX7020-R 分别执行。

## 18.1 PS/DDR

```text
DDR basic memory test
address/data pattern
large buffer
cache enabled
cache flush/invalidate
unaligned reject/handle
PS reset recovery
```

## 18.2 AXI-Lite

```text
build ID
profile ID
register-map version/hash
node role
node ID
session epoch
read/write/readback
invalid config reject
atomic config commit
```

## 18.3 DMA

```text
TX/RX ring
ring depth 8
ring depth 32
wrap
generation
full/empty
abort/reset
descriptor single completion
descriptor leak zero
```

## 18.4 TFDU control

每模块：

```text
Mode
SD
Txd
Rxd
startup
duty counter
continuous-high guard
shutdown
```

单板bring-up期间不得要求远端收到有效payload；远端可以只处于shutdown或receive-only。

## 18.5 节点独立性

验证：

```text
reset AX7020-F does not reset AX7020-R
reset AX7020-R does not reset AX7020-F
DDR内容不共享
DMA ring不共享
session epoch独立
node ID独立
```

---

# 19. P10B：fresh raw光学矩阵

正式四方向：

```text
F0 → R0
R0 → F0
F1 → R1
R1 → F1
```

每个方向：

```text
64 pulse smoke
1000 pulse diagnostic
4096 pulse acceptance
```

记录全部4个receiver，而不只目标receiver：

```text
RX_F0
RX_F1
RX_R0
RX_R1
```

输出完整4×4矩阵：

| Active TX | RX_F0 | RX_F1 | RX_R0 | RX_R1 |
|---|---:|---:|---:|---:|
| TX_F0 | | | | |
| TX_F1 | | | | |
| TX_R0 | | | | |
| TX_R1 | | | | |

分别记录：

```text
raw edge
normalized pulse
false frame start
valid frame
CRC false positive
pulse width if observable
```

目标lane acceptance：

```text
sent=4096
target normalized receive=4096
duty violation=0
continuous-high violation=0
shutdown-after=PASS
```

非目标RX上的pulse不自动判raw失败，但必须作为crosstalk/eho数据保留。

---

# 20. P10C：PHY逐级验证

每条lane、每个方向：

```text
1 Mbit/s
2 Mbit/s
4 Mbit/s
```

每级：

```text
100-frame smoke
10000-frame clean acceptance
short payload
247-byte payload
incrementing
deterministic PRBS
```

硬门：

```text
lane0 F→R 4 Mbit/s
lane0 R→F 4 Mbit/s
lane1 F→R 4 Mbit/s
lane1 R→F 4 Mbit/s
CRC bad=0 in clean run
retry exhausted=0
duty violation=0
continuous-high violation=0
```

两lane并发：

```text
lane mask=0x3
configured 4 Mbit/s/lane
aggregate raw capability=8 Mbit/s
```

`8 Mbit/s`只能声明为RAW capability，不是application goodput。

---

# 21. P10D：双节点 selective-repeat / SACK

运行真实：

```text
global outstanding >=32
SACK window >=32
16-bit sequence
ACK aggregation
bounded retry
health-aware scheduler
retry migration
```

两端分别读取配置，不能只读一端。

测试：

```text
F→R lane0
F→R lane1
F→R 2-lane
R→F lane0
R→F lane1
R→F 2-lane
sequence wrap
window fill/drain
ACK loss
SACK loss
data loss
reorder
duplicate
stale session
stale path epoch
```

要求：

```text
duplicate app commit=0
stale commit=0
descriptor double completion=0
window deadlock=0
bounded recovery
next clean transaction succeeds
```

---

# 22. P10E：两端真实DMA/DDR/cache

必须在两块板分别通过：

```text
real AXI DMA
real PS DDR
cache flush
cache invalidate
memory barriers
descriptor generation
ring wrap
abort/reset
```

双端路径中不能用JTAG direct copy代替远端DMA。

测试：

```text
F TX DMA + R RX DMA
R TX DMA + F RX DMA
simultaneous ring activity
one endpoint DMA reset
one endpoint PS application restart
one endpoint PL soft reset
```

要求：

```text
descriptor single completion
descriptor leak=0
stale completion=0
payload stale=0
input/output SHA match
```

---

# 23. P10F：真实双PS对象闭环

## 23.1 A→B

```text
Host→F PS
→F DMA/PL
→F TFDU
→R TFDU
→R PL/DMA
→R PS
→Host
```

## 23.2 B→A

```text
Host→R PS
→R DMA/PL
→R TFDU
→F TFDU
→F PL/DMA
→F PS
→Host
```

Host只负责边界加载/读取，不参与中间数据转发。

对象：

```text
4 KiB
64 KiB
1 MiB
16 MiB
64 MiB descriptor-chained streaming
```

如果64 MiB被DMA单次长度限制阻塞，必须实现：

```text
descriptor chaining
segmented DMA transaction
incremental CRC/SHA
stream-level completion
atomic publish
```

不能继续以单transfer限制跳过。

payload：

```text
zero
one
counter
PRBS
binary corpus
boundary length
```

每个对象：

```text
size match
CRC32 match
SHA256 match
missing=0
unexpected duplicate=0
partial publish=0
stale publish=0
```

---

# 24. P10G：节点启动顺序、重启和session恢复

自动覆盖：

```text
F先启动，R后启动
R先启动，F后启动
F中途PS reboot
R中途PS reboot
F PL soft reset
R PL soft reset
F DMA reset
R DMA reset
两端application restart
两端同时restart
outstanding存在时单端reset
旧data迟到
旧ACK/SACK迟到
session epoch wrap/advance
```

必须证明：

```text
另一端不会提交旧session数据
duplicate object commit=0
partial object commit=0
stale object commit=0
bounded reacquisition
新session对象成功
```

记录：

```text
reacquisition latency
session negotiation latency
outstanding recovery/abort count
stale rejection count
```

---

# 25. P10H：2-lane scheduler和fault isolation

模式：

```text
lane0 only
lane1 only
equal-weight 2-lane
weight 1:3
weight 3:1
```

注入：

```text
lane0 unavailable
lane1 unavailable
lane recovers
fault while queued
fault while in-flight
duty throttle
permit low
mapping invalid model input
all lanes unavailable
```

要求：

```text
healthy lane continues
unacked frame may migrate
acked frame never migrates
sequence unchanged
payload unchanged
no duplicate commit
bounded recovery
```

---

# 26. P10I：FreeRTOS本地服务迁移

最终产品使用FreeRTOS。P10应在无Ethernet条件下尽可能推进：

```text
safe boot/profile manager
DMA ring task
RFAP object service
configuration task
telemetry task
watchdog/recovery task
evidence logger
```

host transport使用：

```text
JTAG mailbox
UART control
local host adapter
```

不要求Ethernet。

建议结果分层：

```text
P10_DUAL_NODE_BAREMETAL_CORE:
mandatory PASS

P10_DUAL_NODE_FREERTOS_LOCAL_SERVICE:
PASS
or
DEFERRED_WITH_EXPLICIT_TOOLCHAIN_OR_SCHEDULE_REASON
```

FreeRTOS测试：

```text
task priority
DMA completion starvation
stack watermark
heap watermark
queue full
watchdog
task restart
30-minute runtime
```

不得把bare-metal PASS写成FreeRTOS PASS。

---

# 27. P10J：1+1 full-duplex实验

这是高价值实验，但不是P10半双工主验收的阻塞门。

配置：

```text
lane0:
F → R continuous/application traffic

lane1:
R → F continuous/application traffic
```

同时运行。

验证：

```text
双方同时TX/RX
本地自回波
跨lane串扰
双向DMA
ACK piggyback
双向session
双向object integrity
```

输出：

```text
P10_1PLUS1_FULL_DUPLEX_EXPERIMENT:
PASS / FAIL / PARTIAL
```

不得写：

```text
FINAL_4PLUS4_FULL_DUPLEX: PASS
```

如果1+1失败但半双工全部通过：

```text
P10_DUAL_NODE_2LANE_HALF_DUPLEX: PASS
P10_1PLUS1_FULL_DUPLEX_EXPERIMENT: FAIL_WITH_EVIDENCE
```

---

# 28. P10K：性能模型和测量

运行前冻结双节点2-lane性能模型：

```text
PHY raw
frame payload
ACK/SACK
duty shaping
DMA
DDR
cache
PS preparation
CRC/SHA
object publish
```

分别报告：

```text
PHY_RAW_BPS
FRAME_GOODPUT_BPS
APPLICATION_GOODPUT_BPS
ENDPOINT_TO_ENDPOINT_GOODPUT_BPS
```

不能把8 Mbit/s raw写成application goodput。

测量：

```text
F→R lane0
F→R lane1
F→R 2-lane
R→F lane0
R→F lane1
R→F 2-lane
1+1 full-duplex experiment
```

记录：

```text
payload preparation
cache
DMA submission
DMA completion
PL queue
airtime
ACK/SACK
reassembly
SHA
publish
```

P10 functional PASS不以最终16 Mbit/s为门。最终16 Mbit/s是8-lane、600rpm产品指标。

建议平台门：

```text
correctness: mandatory
bounded recovery: mandatory
performance measurement: mandatory
measured/model ratio: reported
```

如需设相对目标，必须在运行前冻结，不能测试后调整。

---

# 29. 30分钟静止正式运行

总时间：

```text
1800 seconds
```

建议：

```text
first 300 s warm-up
next 1500 s formal acceptance
```

主路径：

```text
两块真实AX7020
两端真实PS ELF
两端真实DMA/DDR/cache
两条真实TFDU lane
lane mask=0x3
无Ethernet
无移动
```

循环：

```text
F→R
R→F
4 KiB
64 KiB
1 MiB
deterministic payloads
scheduler weights
```

formal clean window：

```text
CRC bad=0
SHA mismatch=0
partial publish=0
duplicate publish=0
stale publish=0
retry exhausted=0
descriptor leak=0
descriptor double completion=0
deadlock=0
duty violation=0
continuous-high violation=0
safety fault=0
```

1+1 full-duplex可在独立窗口测试，不应污染主半双工clean acceptance。

---

# 30. Shutdown规则

每个硬件stage：

```text
shutdown-before
bounded run
shutdown-after
```

任何一端失败，必须shutdown两端。

shutdown结果：

```text
F Txd intent=0
R Txd intent=0
F endpoint armed=0
R endpoint armed=0
F active TX mask=0
R active TX mask=0
F outstanding physical attempt=0
R outstanding physical attempt=0
F SD shutdown request
R SD shutdown request
```

成功标志：

```text
SHUTDOWN_EXIT=0
or
TFDU_SHUTDOWN_PROGRAMMED
```

JTAG丢失时：

```text
SHUTDOWN_UNCONFIRMED_JTAG_LOST
```

整个formal run必须FAIL，不得写安全退出PASS。

---

# 31. Evidence目录

每次run：

```text
run_id:
p10_<UTC>_<source-short>_<fixed-bit-short>_<rot-bit-short>
```

目录：

```text
evidence/hardware/p10/<run_id>/
```

子目录：

```text
authorization
wiring
board_identity
artifacts
safe_idle
single_board_bringup
raw_4x4_matrix
phy
selective_repeat
dma_ddr_cache
dual_ps_objects
session_reboot
scheduler_faults
freertos
full_duplex_1plus1
performance
stationary_30min
shutdown
raw_logs
final
```

generated summaries至少：

```text
p10_repo_intake
p10_p9_closeout
p10_board_identity
p10_wiring_design
p10_wiring_confirmation
p10_artifact_freeze
p10_authorization
p10_safe_idle
p10_single_board_bringup
p10_raw_matrix
p10_phy
p10_selective_repeat
p10_dma_ddr_cache
p10_dual_ps_runtime
p10_object_integrity
p10_session_reboot
p10_scheduler_fault
p10_freertos
p10_1plus1_full_duplex
p10_performance
p10_stationary_30min
p10_shutdown
p10_evidence_consistency
p10_final_summary
```

每项同时输出：

```text
.md
.json
```

原始日志必须保留：

```text
Vivado
Vitis
hw_server
XSDB
UART
ILA/VIO
register snapshots
DMA descriptor logs
object manifests
CRC/SHA manifests
performance CSV
fault traces
shutdown logs
artifact hash manifest
```

---

# 32. 自动化入口

新增：

```text
scripts/run_p10_ax7020_dual_node_2lane.py
tools/run_p10_ax7020_dual_node_2lane.ps1
```

支持：

```text
--wiring-proposal-only
--dry-run
--build-only
--authorize-from
--wiring-confirmation-from
--run-id
--stage
--fixed-target
--rotating-target
--fixed-bitstream
--rotating-bitstream
--fixed-elf
--rotating-elf
--max-runtime
--json-summary
```

默认：

```text
wiring proposal only
NO_HARDWARE=1
CURRENT_RUN_HARDWARE_AUTHORIZATION=false
```

fail-closed测试：

```text
未确认wiring hash -> 不连接硬件
未授权 -> 不启动hw_server
错误board identity -> 不program
错误fixed/rotating target binding -> 不program
错误bitstream hash -> fail
错误ELF hash -> fail
错误XDC/profile -> fail
缺shutdown image -> fail
max runtime缺失 -> fail
lane mask>0x3 -> fail
要求移动/旋转 -> fail
要求Ethernet -> fail
```

---

# 33. 执行顺序

严格：

```text
P10-00 P9 closeout
P10-01 worktree/repo intake
P10-02 board document intake
P10-03 TFDU small-board intake
P10-04 wiring proposal
P10-05 HOLD POINT A: user wiring confirmation
P10-06 user physical wiring completion
P10-07 board profiles/pinmaps/XDC
P10-08 offline fixed/rotating builds
P10-09 immutable artifact freeze
P10-10 HOLD POINT B: current-run hardware authorization
P10-11 target role binding
P10-12 shutdown images
P10-13 safe-idle
P10-14 single-board F bring-up
P10-15 single-board R bring-up
P10-16 raw 4×4 matrix
P10-17 lane0 PHY
P10-18 lane1 PHY
P10-19 2-lane concurrent PHY
P10-20 selective-repeat/SACK
P10-21 DMA/DDR/cache both endpoints
P10-22 F→R object runtime
P10-23 R→F object runtime
P10-24 session/reboot recovery
P10-25 scheduler/fault/retry migration
P10-26 64 MiB chained streaming
P10-27 FreeRTOS local-service path
P10-28 performance characterization
P10-29 1+1 full-duplex experiment
P10-30 30-minute half-duplex formal soak
P10-31 shutdown-after
P10-32 evidence consistency
P10-33 commits/tag
```

mandatory stage失败后，不得继续更高风险formal stage。

---

# 34. Mandatory acceptance gates

## 34.1 Wiring/profile

```text
P9_CLOSEOUT: PASS
BOARD_DOCUMENT_SET: PASS
FIXED_BOARD_IDENTITY: PASS
ROTATING_BOARD_IDENTITY: PASS
TFDU_SMALL_BOARD_PINOUT: PASS
WIRING_PROPOSAL: PASS
USER_WIRING_CONFIRMATION: PASS
NO_UNDOCUMENTED_WIRES: PASS
FIXED_PROFILE: PASS
ROTATING_PROFILE: PASS
NO_Z7010_XDC_REUSE: PASS
```

## 34.2 Offline implementation

```text
FIXED_SYNTHESIS: PASS
FIXED_ROUTED_TIMING: PASS
ROTATING_SYNTHESIS: PASS
ROTATING_ROUTED_TIMING: PASS
CDC_RDC: PASS
DRC: PASS
REGISTER_MAP_CONSISTENCY: PASS
DUAL_ENDPOINT_SIM: PASS
P0_P9_REGRESSION: PASS
```

## 34.3 Hardware safety

```text
CURRENT_RUN_AUTHORIZATION: PASS
TARGET_ROLE_BINDING: PASS
ARTIFACT_PROVENANCE: PASS
SAFE_BOOT_FIXED: PASS
SAFE_BOOT_ROTATING: PASS
SHUTDOWN_BEFORE_BOTH: PASS
SHUTDOWN_AFTER_BOTH: PASS
STARTUP_WAIT_BOTH: PASS
CONTINUOUS_HIGH_GUARD_BOTH: PASS
INTERNAL_DUTY_ACCOUNTING_BOTH: PASS
```

## 34.4 Optical/PHY

```text
F0_TO_R0_RAW: PASS
R0_TO_F0_RAW: PASS
F1_TO_R1_RAW: PASS
R1_TO_F1_RAW: PASS
RAW_4X4_CROSSTALK_MATRIX: REPORTED
LANE0_4MBPS_BIDIRECTIONAL: PASS
LANE1_4MBPS_BIDIRECTIONAL: PASS
TWO_LANE_8MBPS_RAW_CAPABILITY: PASS
```

## 34.5 Protocol/data plane

```text
SELECTIVE_REPEAT_32_OUTSTANDING: PASS
SACK_WINDOW_32: PASS
ACK_AGGREGATION: PASS
SEQUENCE_WRAP: PASS
ACK_LOSS_RECOVERY: PASS
DUPLICATE_COMMIT_ZERO: PASS
STALE_SESSION_PATH_COMMIT_ZERO: PASS
```

## 34.6 Dual-node runtime

```text
REAL_DMA_DDR_CACHE_FIXED: PASS
REAL_DMA_DDR_CACHE_ROTATING: PASS
DESCRIPTOR_LEAK_ZERO_BOTH: PASS
DUAL_INDEPENDENT_PS: PASS
DUAL_INDEPENDENT_RESET: PASS
NO_SHARED_RAM: PASS
F_TO_R_OBJECT: PASS
R_TO_F_OBJECT: PASS
OBJECT_CRC32: PASS
OBJECT_SHA256: PASS
PARTIAL_OBJECT_COMMIT_ZERO: PASS
ENDPOINT_REBOOT_RECOVERY: PASS
```

## 34.7 Scheduler/soak

```text
TWO_LANE_SCHEDULER: PASS
LANE_FAULT_ISOLATION: PASS
RETRY_MIGRATION: PASS
ACKED_FRAME_NEVER_MIGRATES: PASS
PERFORMANCE_CHARACTERIZATION: PASS
STATIONARY_30MIN: PASS
NO_HARDWARE_MOVEMENT: true
NETWORK_USED: false
MAX_LANE_MASK_USED: 0x3
EVIDENCE_CONSISTENCY: PASS
```

非blocking：

```text
FREERTOS_LOCAL_SERVICE:
PASS or DEFERRED_WITH_EXPLICIT_REASON

P10_1PLUS1_FULL_DUPLEX_EXPERIMENT:
PASS / FAIL_WITH_EVIDENCE / PARTIAL
```

---

# 35. 状态声明

P10全mandatory通过后允许：

```text
P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET: PASS

AX7020_FIXED_SINGLE_NODE_BRINGUP: PASS
AX7020_ROTATING_SINGLE_NODE_BRINGUP: PASS
DUAL_Z7020_INDEPENDENT_ENDPOINTS: PASS
DUAL_Z7020_2LANE_OPTICAL_LINK: PASS
DUAL_Z7020_PS_PL_PHY_PL_PS: PASS
STATIONARY_2LANE_30MIN: PASS
```

若开发板器件不是最终：

```text
XC7Z020-2CLG400I
```

必须写：

```text
Z7020_DEVELOPMENT_BOARD_MIGRATION: PASS
FINAL_XC7Z020_2CLG400I_ACCEPTANCE: PENDING
```

仍保持：

```text
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
SPI_ACCEPTANCE: PENDING
PHYSICAL_GLOBAL_PERMIT: PENDING_D17
EXTERNAL_TFDU_DUTY: PENDING_EXTERNAL_MEASUREMENT
HANDOVER: PENDING_P11
8X32_RING: PENDING_P12
600RPM: PENDING_P13
PRODUCT_FINAL_ACCEPTANCE: PENDING
```

---

# 36. 失败分级

## FAIL

以下任一：

```text
接线hash不匹配
board身份错误
错误bitstream/ELF
safe boot自主发射
shutdown无法确认
duty/stuck-high violation
错误对象提交
descriptor double completion
stale session提交
evidence不一致
```

## PARTIAL

例如：

```text
lane0全通过
lane1失败
双节点单lane通过
```

应写：

```text
P10_STATUS: PARTIAL
ACTIVE_RELIABLE_LANE_MASK: 0x1
TWO_LANE_ACCEPTANCE: FAIL
```

不得将degraded结果写成2-lane PASS。

---

# 37. 项目状态和需求追踪

更新：

```text
config/project_state.json
config/project_requirements.yaml
docs/REQUIREMENT_TRACEABILITY_MATRIX.md
PROJECT_STATUS.md
```

新增 requirement IDs：

```text
P10-BOARD-001 fixed board identity
P10-BOARD-002 rotating board identity
P10-WIRE-001 wiring proposal/source traceability
P10-WIRE-002 exact user-confirmed wiring hash
P10-PROFILE-001 fixed profile/XDC
P10-PROFILE-002 rotating profile/XDC
P10-HW-001 target role binding
P10-HW-002 immutable dual-role artifacts
P10-PHY-001 four-direction raw matrix
P10-PHY-002 4 Mbit/s/lane bidirectional
P10-PHY-003 2-lane aggregate raw capability
P10-DUAL-001 two independent PS/PL/DDR
P10-DUAL-002 no shared RAM
P10-DUAL-003 endpoint reboot/reacquisition
P10-DMA-001 real DMA fixed
P10-DMA-002 real DMA rotating
P10-RFAP-001 F→R object integrity
P10-RFAP-002 R→F object integrity
P10-REC-001 stale session rejection
P10-SOAK-001 stationary 30-minute
P10-XTALK-001 4×4 crosstalk matrix
P10-FD-001 1+1 full-duplex experiment
```

每个PASS绑定：

```text
run ID
board identities
wiring hash
source commit
artifact hashes
test ID
raw evidence
summary
```

---

# 38. Git checkpoint

建议：

```text
docs: freeze AX7020 dual-board wiring and profiles
feat: migrate dual-node 2-lane runtime to AX7020
test: add P10 dual-node hardware evidence
test: freeze P10 AX7020 dual-node checkpoint
```

tag：

```text
p10-ax7020-dual-node-2lane-pass
```

若partial：

```text
p10-ax7020-dual-node-2lane-partial
```

tag指向最终evidence checkpoint。

---

# 39. 最终输出格式

```text
P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET:
PASS / FAIL / PARTIAL

P9_BASE_TAG: <tag>
P9_BASE_CHECKPOINT: <hash>
P10_SOURCE_COMMIT: <hash>
P10_EVIDENCE_CHECKPOINT: <hash>
P10_TAG: <tag>
BRANCH: p10/ax7020-dual-node-2lane
WORKTREE_CLEAN: true/false

WIRING_PROPOSAL_SHA256: <hash>
USER_WIRING_CONFIRMATION: PASS/FAIL
CURRENT_RUN_HARDWARE_AUTHORIZATION: true/false
HARDWARE_ACTIONS_EXECUTED: true/false
NO_HARDWARE_MOVEMENT: true
ROTATION_EXECUTED: false
NETWORK_USED: false
MAX_LANE_MASK_USED: 0x3

FIXED_BOARD_MODEL: <value>
FIXED_BOARD_REVISION: <value>
FIXED_FPGA_PART: <value>
FIXED_JTAG_ID: <value>

ROTATING_BOARD_MODEL: <value>
ROTATING_BOARD_REVISION: <value>
ROTATING_FPGA_PART: <value>
ROTATING_JTAG_ID: <value>

FIXED_PROFILE_SHA256: <hash>
ROTATING_PROFILE_SHA256: <hash>
FIXED_BITSTREAM_SHA256: <hash>
ROTATING_BITSTREAM_SHA256: <hash>
FIXED_ELF_SHA256: <hash>
ROTATING_ELF_SHA256: <hash>

F0_TO_R0_RAW: PASS/FAIL
R0_TO_F0_RAW: PASS/FAIL
F1_TO_R1_RAW: PASS/FAIL
R1_TO_F1_RAW: PASS/FAIL

LANE0_4MBPS_BIDIRECTIONAL: PASS/FAIL
LANE1_4MBPS_BIDIRECTIONAL: PASS/FAIL
TWO_LANE_8MBPS_RAW_CAPABILITY: PASS/FAIL

DUAL_INDEPENDENT_PS: PASS/FAIL
DUAL_INDEPENDENT_RESET: PASS/FAIL
NO_SHARED_RAM: PASS/FAIL
DMA_DDR_CACHE_FIXED: PASS/FAIL
DMA_DDR_CACHE_ROTATING: PASS/FAIL
ENDPOINT_REBOOT_RECOVERY: PASS/FAIL

F_TO_R_OBJECT: PASS/FAIL
R_TO_F_OBJECT: PASS/FAIL
OBJECT_SHA256: PASS/FAIL
PARTIAL_OBJECT_COMMIT_ZERO: PASS/FAIL
STALE_OBJECT_COMMIT_ZERO: PASS/FAIL

SELECTIVE_REPEAT: PASS/FAIL
SACK: PASS/FAIL
ACK_AGGREGATION: PASS/FAIL
SCHEDULER: PASS/FAIL
RETRY_MIGRATION: PASS/FAIL

FREERTOS_LOCAL_SERVICE: PASS/DEFERRED/FAIL
P10_1PLUS1_FULL_DUPLEX_EXPERIMENT: PASS/FAIL/PARTIAL

PHY_RAW_BPS_PER_LANE: <value>
TWO_LANE_RAW_CAPABILITY_BPS: <value>
FRAME_GOODPUT_BPS: <value>
APPLICATION_GOODPUT_BPS_F_TO_R: <value>
APPLICATION_GOODPUT_BPS_R_TO_F: <value>

STATIONARY_30MIN: PASS/FAIL
RUNTIME_SECONDS: <value>
OBJECTS_COMPLETED: <value>
BYTES_COMMITTED: <value>
CRC_BAD: <value>
SHA_MISMATCH: <value>
RETRY_EXHAUSTED: <value>
DUTY_VIOLATION: <value>
CONTINUOUS_HIGH_VIOLATION: <value>
DESCRIPTOR_LEAK: <value>
DEADLOCK: <value>

PASS:
<list>

FAIL:
<list>

SKIP_WITH_REASON:
<list>

GENERATED_SUMMARIES:
<list>

UNCHANGED_PENDING_SCOPES:
ETHERNET_ACCEPTANCE=DEFERRED_NO_NETWORK_CABLE
SPI_ACCEPTANCE=PENDING
PHYSICAL_GLOBAL_PERMIT=PENDING_D17
EXTERNAL_TFDU_DUTY=PENDING_EXTERNAL_MEASUREMENT
HANDOVER=PENDING_P11
8X32_RING=PENDING_P12
600RPM=PENDING_P13
PRODUCT_FINAL_ACCEPTANCE=PENDING

NEXT_RECOMMENDED_STAGE:
P11_SINGLE_LOGICAL_LANE_FOUR_FIXED_MODULE_HANDOVER
or
P10_REMEDIATION
```

---

# 40. Definition of Done

P10完成意味着，在用户确认的接线和当前静止布置下，已经直接证明：

```text
两块真实AX7020的准确板级profile、pinmap和XDC已冻结；
两块板分别安全启动、DDR、DMA、cache和TFDU控制通过；
两端为独立PS、PL、DDR、clock、reset、node和session；
lane0和lane1四个光学方向均fresh raw通过；
两条lane均实现双向4 Mbit/s raw capability；
两lane并发实现8 Mbit/s raw capability；
selective-repeat、SACK、ACK聚合和retry migration在双节点硬件通过；
两端真实DMA/DDR/cache通过；
F→R和R→F大对象均经过真实PS→PL→PHY→PL→PS；
endpoint重启和旧session拒绝通过；
30分钟静止双节点2-lane运行无对象损坏、无deadlock和无安全违规；
全部证据绑定board identity、wiring hash、artifact hash和shutdown。
```

P10完成不意味着：

```text
8 lane通过；
32 fixed modules通过；
handover通过；
旋转通过；
600 rpm通过；
Ethernet通过；
SPI通过；
最终4+4全双工通过；
最终物理permit通过；
产品最终验收通过。
```

现在开始执行 P10 的离线 intake 和接线提案阶段。Codex 在输出接线提案和 SHA256 后必须停在 HOLD POINT A，等待用户确认；不得提前连接硬件。
