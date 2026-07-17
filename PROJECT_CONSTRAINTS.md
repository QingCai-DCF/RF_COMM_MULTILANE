# RF_COMM_MULTILANE 项目约束、目标、架构与验证方案（V3）

> **镜像说明：** 本文件用于 Markdown 阅读与渲染；规范源仍为 `PROJECT_CONSTRAINTS.txt`。源文件 SHA-256：`2014A2DD33FC8EAAE98CC7661946BC38021B884B7027581CFF131DAE9FC8D163`。修改约束时必须先更新规范源，再同步本文件。

```text
DOCUMENT_STATUS: NORMATIVE_PROJECT_CONSTRAINT
DECISION_BASIS: D1-D21 / Q001-Q250
DECISION_REVIEW_STATUS: APPROVED
OPEN_DIRECTION_DECISIONS: 0
CURRENT_DEVELOPMENT_PROFILE: Z7010_2LANE_DEV
FINAL_PRODUCT_PROFILE: Z7020_8LANE_DUAL_ENDPOINT
NO_HARDWARE_ACTIONS_AUTHORIZED_BY_THIS_DOCUMENT: true
HARDWARE_ACCEPTANCE: PENDING_HW
```

本文件定义 RF_COMM_MULTILANE 的最终目标、硬约束、架构选择、技术路线、实施阶段、风险、验证方案、ADR 和项目术语。它同时区分：

1. 当前只有一块 Zynq-7010 开发板、2 lane、4 个 TFDU 小板时可完成的受限开发与验证；
2. 迁移到 Zynq-7020 开发板后的集成验证；
3. 最终双端 `XC7Z020-2CLG400I` 产品的正式验收。

任何低一级证据都不得冒充高一级 PASS。

---

## 0. 规范边界

### 0.1 规范性用语

- **必须 / 禁止**：硬约束，违反即不能通过对应阶段。
- **应 / 推荐**：默认技术选择；偏离时必须记录理由、风险与等效验证。
- **可以**：允许的实现自由度。
- **PENDING**：尚无足够证据，不表示失败，也不表示通过。
- **SKIP_WITH_REASON**：工具或前置条件缺失而无法运行；不得记为 PASS。

### 0.2 约束优先级

发生冲突时按以下顺序处理：

1. `AGENTS.md` 与 `项目约束(目标）.txt` 中的硬约束；
2. 本文件的项目目标、架构和验收约束；
3. 机器可读 canonical 配置；
4. 设计文档、计划和生成的摘要；
5. 历史 evidence 与 legacy 参考。

本文件不得修改或弱化 `项目约束(目标）.txt`。`C:\Users\user\Documents\RF_COMM`、本仓库 `legacy/` 和 `rtl/legacy_reference/` 只读。

当前开发板机器可读源仍为：

- pinmap：`board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`；
- XDC：`constraints/active/PORT1.generated.xdc`；
- active profile：`board_profiles/ACTIVE_PROFILE.json`；
- register map：`config/register_map/ir_axi_regs.yaml`；
- offline gate：`python scripts/run_offline_gates.py`。

这些输入只描述当前 AX7010/Zynq-7010 开发平台，不是最终 Zynq-7020 板级约束。最终固定侧与旋转侧必须分别建立新 profile、pinmap 和 XDC。

### 0.3 硬件执行边界

- 默认 `NO_HARDWARE=1`。
- 本文件不授权 FPGA 下载、PS ELF 启动、TFDU 管脚驱动、XSCT target、Hardware Manager、ILA、UART 或电机动作。
- 未来硬件执行必须取得单独授权，使用安全 wrapper，并在退出日志中出现 `SHUTDOWN_EXIT=0` 或 `TFDU_SHUTDOWN_PROGRAMMED`。
- 离线、仿真、综合、实现和缺工具结果都不能把 `HARDWARE_ACCEPTANCE` 提升为 PASS。
- 当前状态保持 `HARDWARE_ACCEPTANCE: PENDING_HW`。

---

## 1. 最终目标

### 1.1 最终产品硬目标

| 项目 | 最终约束 |
|---|---|
| 固定侧 FPGA | `XC7Z020-2CLG400I`；Vivado part `xc7z020clg400-2` |
| 旋转侧 FPGA | `XC7Z020-2CLG400I`；Vivado part `xc7z020clg400-2` |
| 板卡形态 | 商业核心板 + 自研载板；两端允许使用不同载板 |
| 旋转侧直径 | 200 mm，名义半径 `r=100 mm` |
| 固定侧直径 | 600 mm，名义半径 `R=300 mm` |
| 旋转模块 | 8 个 TFDU6102，45° 等间隔 |
| 固定模块 | 32 个 TFDU6102，11.25° 等间隔 |
| 物理 sector bank | 8 个，每个连续管理 4 个固定模块 |
| logical lane | 8 个；`Lk` 固定对应旋转模块 `Rk` |
| 运动范围 | 正转、反转、速度变化、停转和重新启动；`|rpm| <= 600` |
| 加速度 | 不设数值上限；实现不得依赖固定转向或加速度预测 |
| 半双工 RAW | 8 lane 同向，32 Mbit/s capability |
| 全双工 RAW | 4+4 lane，16 Mbit/s/方向 capability |
| 半双工应用 goodput | 硬门 `>=16 Mbit/s`；挑战目标 `>=19.2 Mbit/s` |
| 全双工应用 goodput | 硬门 `>=8 Mbit/s/方向`；挑战目标 `>=9.6 Mbit/s/方向` |
| 连续运行 | 600 rpm、2 小时、正常配置 8 lane ready |
| 数据完整性 | 错误对象提交数为 0；partial/stale/duplicate 不得误提交 |
| 固定侧外部接口 | Ethernet/TCP，FreeRTOS + lwIP |
| 旋转侧本地接口 | FPGA-to-FPGA SPI，具体角色与速率由阶段门冻结 |
| 开放阵列安全 | 系统级评估通过前实行排除区、钥匙许可、急停和维护禁发 |
| 模块故障 | 允许降级到 7..1 lane，但必须显式报告，不能继续声称 8-lane PASS |

### 1.2 端到端目标拓扑

```text
PC application
  <-> Ethernet/TCP
fixed XC7Z020 PS: FreeRTOS + lwIP
  <-> AXI DMA SG / HP DDR
fixed XC7Z020 PL: protocol + 8-lane scheduler + handover + safety
  <-> 8 discrete four-module sector banks / 32 fixed TFDU6102
  <-> free-space infrared paths
8 rotating TFDU6102
  <-> rotating XC7Z020 PL: PHY + protocol + safety
  <-> AXI DMA SG / HP DDR
rotating XC7Z020 PS: FreeRTOS services
  <-> framed FPGA-to-FPGA SPI
local application FPGA
```

### 1.3 明确不保证的范围

- 当前 Zynq-7010 开发板不属于最终产品平台。
- 当前静止 2-lane evidence 不证明 8-lane、旋转、Ethernet 端到端、SPI 端到端或最终吞吐。
- 单模块故障后不保证仍有 8 lane。
- 环境参数未冻结前，不保证室外、强日照、粉尘、油雾、特定温度或振动环境。
- 网络只按可信内网设计，不宣称适用于不可信公网。
- 单个 TFDU6102 的器件级安全分类不代表 8/32 模块开放阵列的系统级安全结论。

---

## 2. 当前开发基线与 Z7010 优先路线

### 2.1 当前可用硬件

```text
CURRENT_FPGA_BOARD_COUNT: 1
CURRENT_FPGA_FAMILY: Zynq-7010 development board
CURRENT_CANONICAL_PART: xc7z010clg400-1
CURRENT_LOGICAL_LANE_CAPACITY: 2
CURRENT_TFDU_SMALL_BOARD_COUNT: 4
CURRENT_ROTATION_FIXTURE: unavailable/not accepted
CURRENT_HARDWARE_AUTHORIZATION: false
```

当前开发平台的目标不是模拟已经拥有最终硬件，而是在不破坏迁移性的前提下最大化验证可移植功能。

### 2.2 已有 P0–P7 证据的有效范围

已有成果可作为以下内容的回归基线：

- TFDU 极性、startup、shutdown、stuck-high 和基础 duty 保护结构；
- 4PPM codec、L1 frame、CRC、ACK、重传和基础 lane 调度；
- AXI-Lite register map 和软件访问；
- RFAP v1 对象分片、重组、CRC32、SHA256、backpressure 和恢复；
- 单块 Zynq-7010 上的静止 2-lane PS 应用闭环；
- P7 约 `0.081 Mbit/s` 的应用 goodput 功能基线。

已有证据不能外推为：

- 单 lane 4 Mbit/s 已通过；
- 8 lane 同时工作；
- 两个独立节点、独立时钟和独立 reset；
- 32-to-8 sector bank 或动态 handover；
- 任意角度、正反转或 600 rpm；
- 32/16 Mbit/s RAW capability；
- 16/8 Mbit/s application goodput；
- Ethernet 到远端 SPI FPGA 的端到端链路；
- 最终产品安全或可靠性。

`AB_L1` 仍是 legacy raw-layer `BAD_DIR`，在新的 lane1 raw pulse、frame CRC、ACK-only、session 和 mask readback gate 全部通过前，不得作为可靠 lane 使用。

### 2.3 Z7010 平台应尽可能完成的工作

在未来取得硬件授权后，现有一块 Z7010、2 lane、4 小板平台应优先验证：

1. 单 lane 和 2-lane PHY 的极性、startup、stuck-high、精确滑动 duty 与 shutdown；
2. 在现有电气条件允许时逐步达到单 lane 4 Mbit/s，并记录真实波形、误码和温升；
3. 2-lane 并发、独立队列、health-aware 调度和故障隔离；
4. selective-repeat、SACK、至少 32 outstanding、ACK aggregation 和 retry migration；
5. AXI-Stream、聚合 AXI DMA SG、descriptor ring、cache ownership 和 backpressure；
6. RFAP v1 兼容、后继协议、streaming、对象 CRC/SHA 和原子发布；
7. 固定侧 FreeRTOS/lwIP、TCP framing、断线恢复、telemetry 和 evidence 导出；
8. 通过仿真输入或受控逻辑输入验证 phase、path epoch、handover 状态机和正反方向转换；
9. 如果 4 个小板的实际接线允许，可做受限的单 lane/多 physical path 选择原型，但不得写成真实旋转或最终 bank PASS；
10. 所有参数化 core 同时对 Z7010 2-lane 和 Z7020 8-lane 做离线 elaboration/synthesis。

### 2.4 Z7010 平台不能关闭的最终风险

仅凭当前硬件不能关闭：

- 8-lane 硬件并发和 32 个固定模块；
- 双独立 Zynq 节点；
- 8 个 physical sector bank 的真实 MUX/SD/TX 控制链；
- ABZ、光机公差、动态 FOV 和 600 rpm；
- 旋转电池、约 40 g 向心载荷和动平衡；
- 开放阵列系统级可接近辐射；
- 4+4 全双工光学串扰；
- 最终 Z7020 I/O、资源、时序和载板信号完整性；
- PC 到远端 SPI FPGA 的最终 goodput。

### 2.5 可移植实现合同

从现在开始，新增设计必须遵循：

- protocol、safety、register semantics 和核心状态机共用同一份源代码；
- `LANE_COUNT`、`FIXED_MODULE_COUNT`、`SECTOR_BANK_COUNT`、队列深度和时钟比率参数化；
- 板级 pin、clock、reset、DDR、Ethernet 和外设只存在于 board wrapper/profile；
- PS BSP、FreeRTOS port、lwIP netif 和 cache/DMA glue 与应用服务分层；
- register map 继续由 `config/register_map/ir_axi_regs.yaml` 生成并版本化；
- Z7010 可以使用受限 lane 数和较小 buffer，但不得改变协议字段、安全语义和错误码；
- 如果 Z7010 资源不足，可以建立 feature-sliced 开发构建，但必须保持接口一致并明确标记 `PLATFORM_LIMITED_PASS`；
- 不得为了塞入 Z7010 而删除最终必须存在的安全、可观测性、CRC、超时或恢复语义；
- 每次相关改动至少维护两种离线构建：`Z7010_2LANE_DEV` 与 `Z7020_8LANE_TARGET`；
- Z7020 开发板若不是最终精确订货型号，只能形成迁移证据，不能替代最终核心板验收。

### 2.6 证据等级

| 状态 | 含义 |
|---|---|
| `PORTABLE_FUNCTION_PASS` | 平台无关算法/协议通过仿真或受限硬件验证，可迁移但仍需目标平台复验 |
| `PLATFORM_LIMITED_PASS` | 仅在当前 Z7010/2-lane/4-board 范围通过 |
| `Z7020_OFFLINE_PASS` | 对目标 part 的 elaboration/synthesis/implementation 通过，没有硬件接受含义 |
| `PENDING_Z7020_HW` | 必须在 Z7020 开发板或核心板上复验 |
| `PENDING_FINAL_MECHANICAL` | 必须在最终光机、电池或旋转结构上复验 |
| `HARDWARE_ACCEPTANCE: PENDING_HW` | 当前正式硬件接受状态 |

---

## 3. 项目术语表

**Logical Lane（逻辑 lane）**：端到端稳定的数据服务身份 `L0..L7`，固定绑定旋转模块 `R0..R7`。物理路径切换不改变 logical lane。
_避免_：把 logical lane 当作固定侧某一个永久模块。

**Physical Module（物理模块）**：一个具体 TFDU6102 及其板级电气接口。固定侧为 `F0..F31`，旋转侧为 `R0..R7`。

**Physical Path（物理路径）**：某 logical lane 在某一时刻使用的一对固定/旋转物理模块及其方向。

**Physical Sector Bank（物理 sector bank）**：固定侧连续的 4 个 TFDU 模块及其离散选择/保护电路，共 8 个，编号 `SB0..SB7`。
_避免_：4 Bank、phase bank。

**Phase Index（相位索引）**：固定侧每个 sector bank 内被选择的模块槽位 `Q0..Q3`，由转角决定；不是实体 bank。

**Primary Path（主路径）**：当前承担某 logical lane 接收/发送服务的物理路径。

**Candidate Path（候选路径）**：与 primary 同时 startup-ready、用于下一次或反方向 handover 的相邻路径。

**Path Epoch（路径纪元）**：每次路径映射原子提交后递增的标识，用于去重、拒绝 stale 状态和关联 evidence。

**Handover**：logical lane 保持不变时，固定侧 physical path 从一个模块切换到相邻模块的过程。

**Acquisition**：上电、相位丢失或故障后重新获得 session、方向、速度和绝对光学映射的过程。

**Lane Ready**：该 logical lane 至少有一条 startup 完成、无 safety fault、session/path epoch 一致、近期可完成有效帧交易且队列可服务的路径。
_避免_：仅几何选中、仅 Rxd 翻转。

**Normal Configuration（正常配置）**：所有规定模块可用、phase valid、无 safety fault，并满足最终 8-lane 保证的状态。

**Degraded Mode（降级模式）**：模块或路径故障后继续以 7..1 lane 受限服务，并显式报告 mask、reason 和 epoch 的状态。

**PHY RAW Capability**：4PPM 物理编码的名义比特率能力，不扣除帧、ACK、重传和对象开销。

**Frame Goodput**：扣除 L1/L2 开销后成功确认的帧 payload 速率。

**Application Goodput**：完成对象校验并原子提交的有效应用字节速率。

**End-to-End Goodput**：PC/TCP 与远端 SPI FPGA 应用端点之间的 application goodput。

**Half Duplex（半双工）**：8 个 logical lane 在一个方向成批传输，方向切换受 quiet/commit 和 duty 约束。

**4+4 Full Duplex（4+4 全双工）**：4 个物理 lane 用于一个方向，另外 4 个用于反方向；单个 TFDU 不同时发射和接收。

**GLOBAL_PERMIT**：独立、active-high、失败关闭的全局发射许可，直接参与外部 TX buffer/SD 门控。

**Safe State（安全状态）**：所有 Txd 低、SD 有效、外部 TX 禁止、状态和故障可读的状态。

**Evidence Package（证据包）**：包含配置哈希、原始日志、计数器、运行条件、错误和 shutdown 结果的不可混淆验收材料。

---

## 4. 最终架构选择

### 4.1 两个独立节点

最终系统必须由固定侧和旋转侧两个独立 Zynq 节点组成：

- 独立 bitstream；
- 独立 FreeRTOS firmware；
- 独立时钟和 reset；
- 独立 node ID、session epoch、DMA ring 和 watchdog；
- 不共享 RAM；
- 不允许用同一 FPGA 内部数字 loopback 代表最终光链路；
- 一个节点重启时，另一节点进入有界 acquisition，不提交旧 session 数据。

### 4.2 固定侧节点

固定侧使用一个中央 `XC7Z020-2CLG400I`，负责：

- Ethernet/TCP 与 PC；
- FreeRTOS/lwIP、配置、telemetry 和 evidence；
- AXI DMA SG/HP DDR；
- 8-lane PHY、L1/L2/L3、调度、handover 和安全；
- ABZ 捕获与 phase mapping；
- 8 个离散 physical sector bank；
- 32 个固定 TFDU 的状态、SD 和故障管理。

任何 sector bank 上禁止放置 FPGA、CPLD 或 MCU。

### 4.3 固定侧 sector bank

每个 `SBj` 包含连续的 4 个固定 TFDU，并至少具备：

- 两个彼此独立的 4:1 RX MUX：current 与 candidate；
- 一个 1:4 TX demux/one-hot fail-safe buffer；
- 4 个模块的 SD 控制；
- SD 串行写入后的原子 latch；
- 实际输出 readback 或等效 PISO；
- 链断、非法 one-hot、供电或 readback 不一致检测；
- bank 级 `GLOBAL_PERMIT/FAULT`；
- 外部 downstream pulse limiter/kill；
- raw data 的差分 line driver/receiver，除非单端 SI 已证明。

全系统数据接口预算为：

```text
8 TX data
8 current RX data
8 candidate RX data
control/readback/fault/clock as required
```

具体 I/O 和核心板引出能力在 D12 阶段门关闭后证明。

### 4.4 旋转侧节点

旋转侧使用一个 `XC7Z020-2CLG400I` 和 8 个 TFDU：

- 每个 logical lane 固定绑定一个旋转 TFDU；
- 支持半双工 8 lane 与 4+4 全双工角色；
- 本地应用通过 FPGA-to-FPGA SPI 接入；
- 旋转节点使用独立电池电源；
- 电池/BMS/保险/连接器/储能/低压检测不依赖软件轮询完成安全关闭；
- 欠压先撤销 `GLOBAL_PERMIT`、记录 fault，再停止数据面。

### 4.5 实时职责边界

必须在 PL 或外部硬件中完成：

- 4PPM 编解码；
- startup、stuck-high、rolling duty 和 shutdown；
- ABZ 边沿捕获、方向、速度和 phase validity；
- current/candidate selection 与 handover；
- frame CRC、ARQ 时限、lane health 和 path epoch；
- TX one-hot、`GLOBAL_PERMIT` 和故障快速关闭。

PS/FreeRTOS 负责：

- 配置与策略；
- DMA ring；
- RFAP object service；
- Ethernet/TCP 或 SPI service；
- 日志、telemetry、长期统计和恢复编排。

PS、TCP、SPI 或日志任务不得成为微秒级安全闭环的一部分。

---

## 5. 几何、映射与 handover

### 5.1 名义几何

```text
rotor radius r = 100 mm
stator radius R = 300 mm
radial optical gap = 200 mm
rotating module spacing = 45 degrees
fixed module spacing = 11.25 degrees
```

固定模块编号 `F0..F31`，旋转模块编号 `R0..R7`。physical sector bank 定义为：

```text
SB0 = F0..F3
SB1 = F4..F7
...
SB7 = F28..F31
```

### 5.2 映射模型

设 `m0` 为当前最接近 `R0` 的固定模块索引：

```text
q = m0 mod 4                      # Phase Index
s = floor(m0 / 4) mod 8           # R0 当前起始 sector
fixed_index(k) = (m0 + 4*k) mod 32
sector_bank(k) = (s + k) mod 8
slot_in_bank(k) = q
```

因此所有 logical lane 在同一时刻使用相同 Phase Index，但分别落在 8 个 physical sector bank。`q` 变化时发生相邻模块 handover；`q=3 -> 0` 时 `s` 同时循环更新。所有映射必须原子提交并递增 path epoch。

### 5.3 FOV 与 overlap

- TFDU6102 名义参考为约 ±15°；
- 首版设计使用 ±12°保守线；
- 32 模块、±12°时的名义最小角度 overlap 约 4.80°；
- 600 rpm 时对应约 1.33 ms overlap；
- 500 µs startup 在 600 rpm 对应 1.8°转角；
- 最终保证必须使用装配后实际 FOV、窗口、格挡、偏心、跳动和轴向误差重新计算和测量。

### 5.4 RX 与 TX 策略

- 正常 RUN 时固定侧 32 个 RX 全部保持 startup-ready；
- current/candidate 两条 RX 路径在 handover 前后可以同时接收；
- 旧 RX 不因一次 handover 立即 shutdown；
- 每个 physical sector bank 任一时刻最多一个 TX 获得许可；
- 未选 TX 的 Txd 必须为低；
- TX 只在 frame boundary/quiet commit 切换；
- 同帧被 current/candidate 同时收到是正常现象，按 session、sequence 和 path epoch 去重。

该策略使正确性依赖 `|rpm|<=600`、phase 连续和有界切换，而不依赖加速度或转向预测。

### 5.5 phase 丢失

增量式 ABZ 在首次 Z 或替代 acquisition 前没有绝对相位。出现下列任一条件时必须撤销新 TX admission 并进入 acquisition：

- ABZ 非法跳变或边沿超限；
- phase uncertainty 超预算；
- direction/speed 不可信；
- mapping/readback 不一致；
- endpoint reset；
- path epoch 无法对齐。

### 5.6 故障降级

- 正常配置才允许 `ANY_ANGLE_8_LANE_READY: PASS`；
- 固定模块故障可能使相邻模块超出设计 FOV；
- 旋转模块故障必然减少一个 logical lane；
- 故障后允许 7..1 lane，但必须原子更新 `active_lane_mask`、`degraded_reason` 和 `path_epoch`；
- goodput 门槛必须注明实际 active lane 数；
- degraded evidence 不得与正常 8-lane evidence 合并。

---

## 6. 光学、电源、机械与人员安全

### 6.1 TFDU6102 安全合同

所有开发与最终 profile 必须保持：

- `Txd` 高有效；
- `Rxd` 低有效；
- `SD` 高有效 shutdown；
- `Mode=HIGH` 固定高速模式；
- 退出 shutdown 后等待至少 500 µs；
- 连续 Txd HIGH 远低于 80 µs，并由硬件 guard 限制；
- 任意对齐的滑动 duty 窗口满足严格 `<20%`；
- fault、reset、timeout、异常退出和授权丢失后进入 safe state；
- 不得用软件延时替代硬件 stuck-high/duty guard；
- 安全文档、RTL gate 与外部门控保持一致。

当前 `rtl/tfdu_lane_phy.sv` 的 duty 逻辑是固定 1 ms 分桶，不是任意起点滑动窗口。它是已知缺口，修复前不得写成最终 rolling-duty PASS。最终可采用精确滑动和、形式化证明的保守整形器或二者组合。

### 6.2 发射电流与电池

- 按单 TFDU 0.6 A 发射峰值估算，8 个同时发射为 4.8 A 峰值；
- 在 20% duty 上界下，IRED 平均电流基线约 0.96 A、3.17 W，另加 FPGA/PS/收发器和转换损耗；
- 电池、BMS、保险、连接器、铜皮、稳压器和 bulk capacitance 按峰值及瞬态设计；
- 容量、续航、低压阈值、温升、充电维护和故障隔离在旋转硬件前冻结；
- 电池宜靠近旋转轴，固定结构必须有机械留存、冗余防松和动平衡证据。

### 6.3 旋转载荷

600 rpm、半径 100 mm 处名义向心加速度约：

```text
omega = 62.83 rad/s
a = omega^2 * 0.1 m = 394.8 m/s^2 ~= 40.3 g
```

所有旋转器件、线束、电池、连接器和小板必须按实际半径、质量、公差和超速裕量复算。进入 600 rpm 前必须完成静态留存、低速动平衡和分级升速。

### 6.4 格挡与串扰

同侧模块间设置格挡，但格挡必须同时满足 FOV 与近红外材料验证：

```text
for half-angle 12 degrees: W/L >= 2*tan(12 degrees) ~= 0.425
for half-angle 15 degrees: W/L >= 2*tan(15 degrees) ~= 0.536
```

`W` 为完整开口宽度，`L` 为通道长度。可见光下“黑色”不等于约 886 nm 下低反射；必须测试近红外反射、吸收、温升和污染后的表现。

串扰验证覆盖：

- 同侧相邻模块；
- 跨侧多发射器；
- 窗口与结构反射；
- 静止最坏相位；
- 4+4 双向同时发射；
- 0..600 rpm；
- 环境光和污染边界。

### 6.5 开放阵列人体接近策略

系统不封闭。系统级可接近红外辐射测量与适用标准评估通过前：

- 发射区设置受控排除区；
- 使用钥匙或等效受控 `GLOBAL_PERMIT`；
- 提供独立急停；
- 维护、对准、拆卸格挡或人员进入危险区域时强制 `GLOBAL_PERMIT=0`；
- 不允许普通 GUI 或网络命令绕过安全门；
- 单器件 Class 1、格挡或软件限制均不能单独作为阵列安全结论。

只有系统级测量证明在明确的窗口、距离、反射、并发和单故障条件下安全，才可按书面条件放宽人体接近策略。

---

## 7. PL/FPGA 技术路线

### 7.1 逻辑分层

```text
board wrapper / clocks / resets / physical I/O
  -> tfdu safety PHY per physical module
  -> 4PPM codec and L1 frame
  -> L2 selective-repeat ARQ
  -> L3 logical lane / path / handover / health
  -> aggregate AXI-Stream and AXI DMA SG
  -> register/telemetry/evidence interface
```

固定侧另包含：

```text
ABZ capture -> phase estimator -> mapping engine
sector-bank control -> current/candidate RX -> one-hot TX
SD atomic latch/readback -> GLOBAL_PERMIT/fault
```

### 7.2 参数化要求

核心 RTL 禁止硬编码最终与开发平台之间的差异：

- `LANE_COUNT=2/8`；
- `FIXED_MODULE_COUNT=4/32` 或仿真值；
- `SECTOR_BANK_COUNT=1/8` 或受限原型值；
- `MODULES_PER_BANK=4`；
- queue/outstanding 深度；
- clock-to-symbol 比率；
- fixed/rotating endpoint role。

Z7010 与 Z7020 的差异通过参数、wrapper、profile 和生成配置表达，不允许复制分叉一套不可追溯协议核心。

### 7.3 duty、帧与 airtime

4 Mbit/s/lane 必须重新闭合真实时序、独立时钟容差和 TFDU 波形。以现有最大 L1 payload 247 byte 为基线：

```text
preamble and frame representation ~= 1076 4PPM symbol slots
nominal airtime ~= 538 us
nominal Txd-high sum ~= 134.5 us
```

由此得到的理想上限约为：

```text
frame payload ceiling ~= 2.94 Mbit/s/lane
RFAP v1 useful chunk ceiling ~= 2.56 Mbit/s/lane
8-lane ideal aggregate ~= 20.46 Mbit/s
```

因此：

- 16 Mbit/s 半双工硬门约占理想上限 78%，保留实现/重传余量；
- 19.2 Mbit/s 挑战目标约占理想上限 94%，只能在低错误率和高效率下达到；
- 不得为了挑战目标削弱 duty、CRC、重传或安全；
- 临近 handover 边界必须做 frame admission；
- 更大帧必须重新证明 airtime、overlap、buffer 和恢复。

### 7.4 ARQ 与调度

- 最终数据面使用 bounded selective-repeat；
- 全局 outstanding 至少 32，推荐 64；
- SACK window 至少 32；
- sequence 至少 16 bit，并结合 session epoch 和 path epoch；
- scheduler 使用 health-aware weighted round-robin；
- 普通数据不复制；关键控制/切换帧可有限复制；
- 只迁移未确认帧；已确认帧不得因 path 变化再次提交；
- retry、timeout、queue 和 recovery 都必须有上限；
- lane fault 不得阻塞其他健康 lane。

### 7.5 CDC、reset 与故障

- 两端时钟独立；
- PS、DMA、PHY、ABZ 和外部 SPI 时钟域之间使用同步器、异步 FIFO 或有证明的 handshake；
- CDC 工具报告中不得保留未解释的 critical crossing；
- reset assertion 可以异步，deassertion 必须按域同步；
- 任一 reset 不得产生 Txd 毛刺或非法 one-hot；
- PL watchdog、illegal state、FIFO corruption、mapping collision 和 readback mismatch 都撤销相关 permit。

### 7.6 DMA 与 DDR

- 使用聚合 AXI DMA scatter-gather，经 Zynq HP 口访问 DDR；
- lane striping、reorder、ARQ 和 handover 留在 PL；
- PS 管理 descriptor ownership、cache flush/invalidate、batching 和回收；
- TX/RX ring 独立且有 generation/epoch；
- reset、abort、disconnect 后 descriptor 可确定性回收；
- 不依赖逐 fragment MMIO copy 达成最终吞吐。

### 7.7 register 与可观测性

register map 必须提供版本化、原子快照和 clear 语义，至少覆盖：

- build/profile/register-map ID 与哈希；
- node/session/path epoch；
- active lane mask 与 degraded reason；
- 32 个固定模块和 8 个旋转模块状态；
- current/candidate path、sector bank、Phase Index；
- ABZ count、phase、direction、rpm、validity；
- per-lane raw/frame/CRC/retry/duplicate/gap；
- duty、stuck-high、SD/readback、GLOBAL_PERMIT；
- DMA queue、watermark、drop/overflow；
- handover count、latency 和 failure；
- safety fault history 和 shutdown result。

### 7.8 Z7020 资源与时序目标

最终 `xc7z020clg400-2` 实现目标：

- LUT 与 FF 使用率各不高于 70%；
- BRAM 与 DSP 使用率各不高于 75%；
- 所有正式时钟 worst slack 非负；
- 无未解释 CDC critical；
- I/O bank 电压、pin 数和 simultaneous switching 有板级证明；
- 保留 debug、ILA、协议扩展和 ECO 余量；
- 资源不足时不得删除 safety/CRC/recovery 来硬塞，必须优化、分层或调整非安全 buffer。

Z7010 的高资源使用率只用于识别热点，不作为最终 Z7020 资源 PASS。

---

## 8. PS、网络与 SPI 技术路线

### 8.1 FreeRTOS 服务划分

两端使用 FreeRTOS。建议任务边界：

```text
safe boot/profile manager
PL/register driver
DMA ring manager
RFAP object service
network service (fixed side)
SPI service (rotating side)
configuration transaction manager
telemetry/event service
watchdog/recovery coordinator
evidence/logger
```

优先级必须保证 DMA 回收、错误处理和 watchdog 不被日志或 GUI 请求饿死。硬实时和发射许可不依赖任务调度。

### 8.2 固定侧 Ethernet/TCP

固定侧使用 lwIP，至少支持：

- DHCP；
- 静态 IP fallback；
- 链路断开检测；
- 有界重连/重新监听；
- heartbeat；
- 显式 TCP message framing；
- protocol/capability negotiation；
- backpressure；
- telemetry 与 evidence 导出。

TCP 一次 `recv` 不代表一条完整消息。envelope 至少包含：

```text
magic
protocol_version
message_type
flags
request_id
payload_length
header_crc
payload_crc
```

网络属于可信内网，不要求 TLS 和远程身份体系；但长度、状态机、CRC、版本、内存上限和 malformed input 隔离仍为硬要求。

### 8.3 旋转侧 SPI

SPI 的另一端也是 FPGA。协议必须包含：

- magic/version/type；
- payload length；
- sequence/request ID；
- CRC；
- READY/credit 或等效流控；
- timeout、abort 和 reset recovery；
- capability negotiation；
- 明确的 object boundary。

master/slave、MIO/PL、SCLK 和 READY/IRQ 在 D14 阶段门关闭时冻结。SPI payload goodput 必须比对应 IR application goodput 硬门至少高 20%，否则不得进入端到端性能验收。

### 8.4 配置事务

- `CONFIG_SET` 只写 staging；
- `CONFIG_COMMIT` 在 quiet window 原子提交并递增 config/path epoch；
- 非法组合拒绝且不改变 active config；
- safety 字段不能被普通网络/SPI 命令放宽；
- profile/readback/hash 不一致时保持 safe state。

---

## 9. 协议、数据完整性与性能口径

### 9.1 协议分层

```text
L0  TFDU6102 electrical/optical PHY and safety
L1  4PPM symbol, preamble, frame length and CRC
L2  sequence, ACK/SACK, selective-repeat ARQ
L3  logical lane, physical path, handover, health and degradation
L4  RFAP object fragmentation, streaming and integrity
L5  PS services, Ethernet/TCP and SPI application APIs
```

层间禁止隐式共享不可恢复状态。path 变化不得清空 object/session；object abort 不得绕过 PHY safe state。

### 9.2 RFAP 演进

RFAP v1 保留为兼容和回归基线。版本化后继协议至少支持：

- endpoint/node ID；
- session epoch；
- stream/object ID；
- fragment offset/length；
- sequence 与 SACK；
- path epoch；
- priority/lane policy；
- object CRC32；
- host/endpoint SHA256；
- atomic publish；
- stale/replay rejection；
- abort/restart；
- 至少 64 MiB 对象或不受固定对象大小限制的 streaming。

### 9.3 ACK 与方向

- 半双工不按每帧反转；使用成批方向窗口和聚合 ACK；
- 方向切换只能发生在 quiet/commit window；
- 全双工优先在反向 4-lane 数据流中捎带/聚合 ACK；
- ACK loss 触发有界重传，不得造成无限反转或死锁。

### 9.4 数据完整性

只有同时满足以下条件才允许提交对象：

- 完整长度收到；
- fragment map 无缺口；
- frame/object CRC 正确；
- SHA256 与声明值一致；
- session/object ID 当前有效；
- 未发生 abort、timeout 或 stale epoch；
- atomic publish 成功。

错误、partial、duplicate、stale 或 retry-exhausted 对象都不得标为完成。

### 9.5 性能口径

必须分别记录：

- `PHY_RAW_BPS`；
- `FRAME_GOODPUT_BPS`；
- `APPLICATION_GOODPUT_BPS`；
- `PC_TO_REMOTE_GOODPUT_BPS`；
- `REMOTE_TO_PC_GOODPUT_BPS`；
- on-air、ACK、handover、PL queue、DMA、PS、network、SPI 和 object completion latency。

端到端 application goodput 统计 PC/TCP 与远端 SPI FPGA 应用端点之间已校验并提交的有效字节；协议头、重传、填充和未提交对象不计入。

### 9.6 最终性能门

| 指标 | 硬验收门 | 挑战目标 |
|---|---:|---:|
| 单 lane PHY RAW | 4 Mbit/s | — |
| 8-lane 半双工 PHY RAW | 32 Mbit/s capability | — |
| 4+4 全双工 PHY RAW | 16 Mbit/s/方向 capability | — |
| 600 rpm 半双工 application goodput | >=16 Mbit/s | >=19.2 Mbit/s |
| 600 rpm 全双工 application goodput | >=8 Mbit/s/方向 | >=9.6 Mbit/s/方向 |
| handover mapping commit | <=200 µs | <=100 µs |
| handover 导致不可恢复对象失败 | 0 | 0 |
| 正常配置错误对象提交 | 0 | 0 |
| 网络与 SPI 可持续 payload goodput | 不成为瓶颈 | 比 IR 硬门高至少 20% |

挑战目标失败不能反向判定硬门失败；硬门失败不能用 RAW capability 或挑战测试的部分结果掩盖。

---

## 10. 实施阶段

### P8：Z7010-first 可移植架构与离线重构

目标：在不执行硬件的前提下，把现有 2-lane 代码重构为可同时面向 Z7010 和 Z7020 的共源架构。

任务：

1. 建立 `Z7010_2LANE_DEV` 与 `Z7020_8LANE_TARGET` 构建矩阵；
2. 参数化 lane、endpoint、queue、clock 和 board wrapper；
3. 修复精确 rolling-duty；
4. 建立 8-lane elaboration、independent-clock、CDC 和 reset 仿真；
5. 建立 32×8 几何、phase、handover property model；
6. 实现 selective-repeat、SACK、多 outstanding 和 health-aware scheduler；
7. 建立聚合 AXI-Stream/DMA 接口和 descriptor model；
8. 保持 RFAP v1 与 P0–P7 回归；
9. 对 `xc7z020clg400-2` 做离线资源/时序估计；
10. 硬件状态保持 PENDING。

退出条件：

```text
Z7010_2LANE_DEV elaboration/regression: PASS or SKIP_WITH_REASON
Z7020_8LANE_TARGET elaboration: PASS
rolling-duty formal/property gate: PASS
independent-clock/CDC/reset simulation: PASS
32x8 geometry/handover model: PASS
P0-P7 regression: PASS
HARDWARE_ACCEPTANCE: PENDING_HW
```

### P9：现有一块 Z7010、2 lane、4 小板的最大验证

目标：在未来单独授权硬件后，尽量关闭平台无关功能风险，同时严格标注平台边界。

任务：

1. 安全 startup/shutdown、stuck-high、rolling duty 和异常退出；
2. lane0 与修复后的 lane1 raw pulse、frame CRC、ACK-only、session/mask；
3. 单 lane 4 Mbit/s 逐级验证，以及 2-lane 并发；
4. DMA、descriptor batching、多 outstanding、SACK 和 backpressure；
5. RFAP v1/vNext、large-object streaming、CRC/SHA、abort/restart；
6. 固定侧 FreeRTOS/lwIP、TCP framing 和断线恢复；
7. 4 小板可支持时进行受限 path selection/handover 原型；
8. fault injection 与 bounded recovery；
9. 至少 30 分钟静止稳定性；
10. evidence 明确写 `PLATFORM_LIMITED_PASS`。

不得把 P9 写成 8-lane、双节点、旋转、Z7020 或产品 PASS。

### P10：迁移到 Zynq-7020 开发板并形成双节点

目标：先把共源实现移植到 Zynq-7020 开发板，再形成两个独立端点。

任务：

1. 冻结所选 Z7020 开发板 part、原理图、时钟、DDR、Ethernet、I/O 和 BSP；
2. 建立开发板 profile/pinmap/XDC，不复用 AX7010 XDC；
3. 运行 Z7010 与 Z7020 的协议/寄存器一致性回归；
4. 在一块 Z7020 板上完成迁移和资源/时序验证；
5. 在具备第二端硬件后建立固定/旋转两套 bitstream 与 firmware；
6. 验证独立 clock/reset/session、endpoint reboot 和双向对象；
7. 无共享 RAM、无内部数字 loopback 冒充最终链路；
8. 开发板器件若不是 `XC7Z020-2CLG400I`，证据标记为迁移证据并在最终核心板复验。

### P11：单 logical lane、四固定模块的动态 handover

目标：在完整 32×8 全环前证明真实光机 FOV、overlap、ABZ 和 current/candidate handover。

至少覆盖：

- 1 个旋转模块；
- 4 个固定模块，11.25°间隔；
- D200/D600 名义几何；
- ABZ/phase input；
- 静止角度 sweep；
- 正转、反转、变速、停转和 reacquisition；
- 0、30、60、120、300、450、600 rpm 分级；
- startup、overlap、frame admission 和去重；
- 实际 FOV、格挡、反射和串扰。

P11 不得跳过。

### P12：8×32 全环 bring-up

任务：

1. 32 固定模块和 8 physical sector bank 安装/ID/readback；
2. 8 旋转模块安装、留存和动平衡；
3. 8-lane 静止 raw matrix；
4. 全角度 mapping 唯一性和 path epoch；
5. current/candidate overlap；
6. all-32-RX 功耗和固定侧供电；
7. 旋转电池、电压跌落和温升；
8. 同侧、跨侧和反射串扰；
9. 低速 30 分钟；
10. 系统级开放阵列安全测量仍可保持 PENDING，但人员接近控制必须生效。

### P13：600 rpm 8-lane 连续性

按以下速度逐级进入，前一级未通过不得升速：

```text
0 -> 30 -> 60 -> 120 -> 300 -> 450 -> 600 rpm
```

每级覆盖正转、反转、速度变化、停转和 reacquisition，并检查：

- `logical_lane_ready_count=8`；
- mapping collision=0；
- retry exhausted=0（正常配置）；
- safety fault=0；
- handover count 与速度一致；
- shutdown-before/after PASS。

600 rpm 完成 10 分钟校准、30 分钟功能和 2 小时稳定性；应用数据损坏和不可恢复 handover 失败均为 0。

### P14：Ethernet、SPI 与端到端闭环

覆盖：

- DHCP/static fallback；
- TCP framing、重连和 backpressure；
- FPGA-to-FPGA SPI framing、CRC、credit 和 reset recovery；
- PC -> fixed PS/PL -> IR -> rotating PS/PL -> SPI FPGA；
- 反向完整路径；
- 600 rpm 下同时运行；
- 端到端 16 Mbit/s 半双工 application goodput；
- 网线重插、PC/endpoint 重启、SPI peer reset；
- telemetry 和 evidence 导出。

### P15：4+4 全双工与产品最终验收

覆盖：

- 4+4 lane 原子角色分配；
- 16 Mbit/s/方向 RAW capability；
- 8 Mbit/s/方向 application goodput；
- 双向 ACK 聚合；
- 全双工光学串扰；
- 正反转与 600 rpm 2 小时；
- 模块、encoder、DMA、网络、SPI、电池故障注入；
- 电源、温升、机械、环境和系统级人员安全；
- 完整 evidence freeze。

---

## 11. 风险登记与验证方案

| ID | 风险 | 主要后果 | 缓解与验证 |
|---|---|---|---|
| R1 | 过度围绕 Z7010 优化 | 迁移困难或删减最终功能 | 共源参数化 core、双目标离线构建、Z7010 evidence 明确受限 |
| R2 | Z7020 开发板不是最终订货型号 | 时序/I/O/温度证据不可直接继承 | 区分迁移板与最终核心板，在 `XC7Z020-2CLG400I` 上复验 |
| R3 | 商业核心板引出 I/O 不足 | 24 raw 线和控制无法落板 | 采购前冻结原理图、bank 电压、引出和 SI 预算 |
| R4 | 当前 duty 是固定分桶 | 跨边界超 duty，安全不成立 | 精确滑动/保守整形、形式化、仿真、电气与光学证据 |
| R5 | 19.2 Mbit/s 效率裕量过小 | 重传或 handover 后达不到挑战目标 | 硬门保持 16 Mbit/s，DMA、batching、SACK、低开销与实测 |
| R6 | 实际 FOV/公差低于模型 | 任意角度丢 lane | ±12°设计线、Monte Carlo、P11 sweep、P12 全环测量 |
| R7 | 开放阵列系统级辐射 | 人员伤害或无法验收 | D20 接近控制、外部硬件门、系统级测量与单故障评估 |
| R8 | 格挡/反射/环境串扰 | CRC、误触发、全双工失败 | 886 nm 材料测试、反射面/污染/日光和 4+4 矩阵 |
| R9 | 电池峰值与约 40 g 载荷 | 欠压、脱落、失控发射 | 峰值供电、BMS/保险、欠压 permit、留存、动平衡和分级升速 |
| R10 | 增量 ABZ 无绝对相位 | 错误 mapping/TX | receive-only acquisition、Z/光学标定、phase validity 和故障注入 |
| R11 | 双节点 CDC/reset | 亚稳、stale session、毛刺 | async FIFO/同步器、CDC tool、独立 reset/reboot 测试 |
| R12 | 协议/队列复杂度 | 死锁、重复或内存耗尽 | bounded window/queue/retry、property test、长对象和 backpressure soak |
| R13 | 4+4 光学互扰 | 全双工 goodput 不达标 | 独立角色、串扰测量、调度和必要的光机优化；不得虚报 capability |
| R14 | evidence 混淆 | 受限结果被写成最终 PASS | evidence 等级、hash、原始日志、机器可读状态和 review gate |

### 11.1 离线验证

至少包含：

- lint/elaboration；
- unit and integration simulation；
- 2-lane/8-lane parameter matrix；
- independent-clock/CDC/reset；
- exact rolling-duty properties；
- stuck-high and illegal-state injection；
- 32×8 geometry and handover properties；
- selective-repeat/SACK/sequence wrap；
- duplicate/stale/object atomicity；
- DMA ring and backpressure model；
- Z7010/Z7020 synthesis/resource/timing；
- P0–P7 regression。

缺失工具必须记录 `SKIP_WITH_REASON`，不得把未运行写为 PASS。

### 11.2 硬件验证层级

| 层级 | 平台 | 可形成的结论 |
|---|---|---|
| H0 | 当前无授权 | 不执行硬件，`PENDING_HW` |
| H1 | 一块 Z7010、2 lane、4 小板 | `PLATFORM_LIMITED_PASS`；静止、2-lane、实际接线范围 |
| H2 | Z7020 开发板 | 迁移、资源、板级接口和单/双节点证据 |
| H3 | P11 光机原型 | 单 lane 真实 FOV/handover/ABZ |
| H4 | 8×32 全环 | 静止/低速 8-lane 和供电/串扰 |
| H5 | 最终双端产品 | 600 rpm、端到端、全双工、安全和产品接受 |

---

## 12. 配置、证据与验收纪律

每个正式运行必须冻结并记录：

- source commit；
- bitstream、固定 ELF、旋转 ELF/firmware SHA256；
- board profile、pinmap、XDC、register-map SHA256；
- FPGA exact part、板卡型号/revision/serial；
- 固定/旋转模块 ID；
- 机械安装、FOV、ABZ 和 phase calibration 版本；
- lane/bank/module masks；
- speed、direction、环境、电池状态；
- start/end time；
- raw logs、JSON/CSV、counters、faults；
- authorization inputs；
- shutdown result。

禁止：

- 使用可被覆盖的同名 bitstream 作为正式 evidence；
- 使用未记录的手工 Vivado 修改；
- 删除失败 evidence；
- 用 Markdown 摘要代替原始日志；
- 用 ILA/proxy 推断冒充外部电气或光学测量；
- 用 Z7010 结果替代 Z7020；
- 用静止 2-lane 结果替代旋转 8-lane；
- 用 degraded lane 结果替代正常配置；
- 用离线结果提升 hardware status。

---

## 13. Architecture Decision Records

### ADR-001：采用 Z7010-first 开发、Z7020 最终产品

**Status: Accepted.** 当前只有一块 Zynq-7010、2 lane、4 小板，因此先在该平台验证可移植功能；最终两端仍固定为 `XC7Z020-2CLG400I`。通过共源参数化 core 与板级 wrapper 隔离，避免当前资源限制改变最终架构；所有目标平台相关证据必须在 Z7020 上重取。

### ADR-002：采用 D200/D600、8×32 几何

**Status: Accepted.** 旋转侧 8 模块、固定侧 32 模块在 45°/11.25°节距下提供任意角度 8 logical lane 的几何基础，并在 ±12°设计线下保留 handover overlap。更少固定模块会显著压缩 FOV、公差和切换余量。

### ADR-003：一个中央 XC7Z020 加八个离散 sector bank

**Status: Accepted.** 固定侧所有实时选择由中央 PL 完成；每个四模块 bank 只使用离散 MUX、buffer、SD latch 和保护电路，不放 FPGA/CPLD/MCU。这样避免 8 套固件、时钟、升级和分布式安全状态，同时用外部失败关闭弥补离散控制风险。

### ADR-004：正常 RUN 全部 32 RX 唤醒、每 bank 双 RX 单 TX

**Status: Accepted.** all-RX-ready 使正反转和速度变化不依赖加速度预测；current/candidate 双 RX 支持 make-before-break 和去重；单 TX one-hot 控制功耗、串扰和非法并发。代价是固定侧 RX 平均功耗增加。

### ADR-005：PL/外部硬件承担硬实时与安全，PS 使用 FreeRTOS

**Status: Accepted.** 微秒级 PHY、ABZ、handover、duty 和 permit 不可依赖任务调度、TCP 或日志；PS/FreeRTOS 负责服务、配置、DMA、网络和恢复编排。该边界降低调度抖动和软件失控对发射安全的影响。

### ADR-006：聚合 AXI DMA SG 加 selective-repeat

**Status: Accepted.** P7 的 MMIO/stop-and-wait 只能证明功能，无法满足 8-lane goodput。最终采用聚合 DMA、descriptor batching、多个 outstanding、SACK 和 health-aware 调度；lane/path 细节留在 PL，避免 PS 逐帧干预。

### ADR-007：保留 RFAP v1，使用版本化后继协议扩展

**Status: Accepted.** 现有 P7 evidence 和工具依赖 RFAP v1，因此保留兼容模式；窗口、path epoch、streaming 和多节点能力通过协商进入后继版本，避免一次性破坏回归基线。

### ADR-008：开放阵列在系统级测量前实行受控接近

**Status: Accepted.** 单个 TFDU 的器件分类不能覆盖多发射器、反射、窗口、维护和单故障。系统测量通过前使用排除区、钥匙许可、急停和维护禁发；格挡只承担光路/串扰作用，不作为独立安全结论。

### ADR-009：旋转侧首版使用电池

**Status: Accepted.** 电池避免滑环对高速数据和电源噪声的耦合，但引入峰值电流、欠压、续航、约 40 g 载荷和动平衡风险。因此电池/BMS/留存/低压 permit 是进入旋转验收前的硬阶段门。

### ADR-010：正常 8-lane 与故障降级分开验收

**Status: Accepted.** 32/8 模块几何不能保证任意单模块故障后仍有 8 lane。正常配置保持硬性 8-lane 要求；故障后允许 7..1 lane 受限服务，但使用独立状态和 evidence，防止鲁棒性结果掩盖正常能力不足。

---

## 14. 已延期但必须关闭的阶段参数

这些参数不是当前开放的架构方向问题，但会阻塞对应硬件阶段或最终验收：

| Gate | 必须冻结的内容 | 最迟时点 |
|---|---|---|
| D12 核心板 | 精确型号/part、revision、原理图、I/O、bank 电压、时钟、DDR、BSP | 原理图、采购、profile/XDC 前 |
| D13 ABZ | PPR、电气标准、最高边沿率、滤波、Z/绝对 acquisition、标定和误差预算 | 任何旋转硬件动作前 |
| D14 SPI | master/slave、MIO/PL、SCLK、READY/IRQ、帧和 payload goodput | SPI 实现与验收前 |
| Battery | 电芯、BMS、容量、续航、保险、低压、温度、充电和机械留存 | 旋转电池采购与 P11/P12 前 |
| Environment | 温度、环境光、污染、振动、冲击和维护周期 | 对应环境声明与 P15 前 |
| Optics | 实际 FOV、格挡材料、反射、窗口和系统级可接近辐射 | P11/P12/P15 相应 gate 前 |

未关闭阶段门时只能保持 PENDING 或受限结论，不能用默认假设生成产品 PASS。

---

## 15. 最终验收矩阵与 Definition of Done

### 15.1 阶段完成条件

```text
P0-P7 regression and limited baseline: PASS
P8 portable Z7010/Z7020 architecture and offline gates: PASS
P9 Z7010 2-lane/4-board limited development: PASS or formally superseded with evidence
P10 Z7020 migration and independent endpoints: PASS
P11 single-lane real optical handover: PASS
P12 8x32 full-ring bring-up: PASS
P13 600-rpm 8-lane continuity: PASS
P14 Ethernet-to-SPI end-to-end: PASS
P15 4+4 full-duplex and product acceptance: PASS
```

P9 可以因后续更强 Z7020 evidence 被正式 supersede，但不得静默跳过其安全和协议覆盖。

### 15.2 最终产品字段

只有真实最终硬件 evidence 支持时，以下字段才允许为 PASS：

```text
FINAL_FIXED_FPGA: XC7Z020-2CLG400I
FINAL_ROTATING_FPGA: XC7Z020-2CLG400I
ROTATING_DIAMETER_MM: 200
STATOR_DIAMETER_MM: 600
ROTATING_MODULE_COUNT: 8
FIXED_MODULE_COUNT: 32
FIXED_SECTOR_BANK_COUNT: 8
FIXED_MODULES_PER_BANK: 4
PHASE_INDEX_COUNT: 4
LOGICAL_LANE_COUNT: 8
MAX_ABS_SPEED_RPM: 600
NORMAL_ANY_ANGLE_8_LANE_READY: PASS
HALF_DUPLEX_RAW_32MBPS_CAPABILITY: PASS
FULL_DUPLEX_RAW_16MBPS_PER_DIRECTION_CAPABILITY: PASS
HALF_DUPLEX_APPLICATION_GOODPUT_16MBPS: PASS
FULL_DUPLEX_APPLICATION_GOODPUT_8MBPS_PER_DIRECTION: PASS
ROTATION_600RPM_BIDIRECTIONAL_2H: PASS
ETHERNET_TO_REMOTE_SPI_END_TO_END: PASS
APPLICATION_DATA_INTEGRITY: PASS
SYSTEM_ACCESSIBLE_IR_SAFETY: PASS
SHUTDOWN_SAFETY: PASS
PRODUCT_FINAL_ACCEPTANCE: PASS
```

任一必需项缺失时：

```text
PRODUCT_FINAL_ACCEPTANCE: PENDING
HARDWARE_ACCEPTANCE: PENDING_HW or LIMITED
```

不得用挑战目标、受限平台或 degraded evidence 改写这一规则。

---

## 16. 参考与当前事实源

- `evidence/generated/p7_final_summary.md`；
- `evidence/generated/p7_final_acceptance_summary.json`；
- `evidence/generated/p7_performance_summary.md`；
- `docs/P7_RUNTIME_OPTIMIZATION_CONSTRAINTS.md`；
- `docs/P7_APPLICATION_PROTOCOL.md`；
- `config/p7_app_protocol.yaml`；
- `docs/TFDU_LANE_PHY_SPEC.md`；
- `docs/TFDU6102_SAFETY_SUMMARY.md`；
- `docs/tfdu6102_safety_contract.md`；
- `docs/datasheets/TFDU6102datasheet.pdf`；
- `rtl/tfdu_lane_phy.sv`；
- `rtl/ir_4ppm_codec.sv`；
- `rtl/ir_frame_l1.sv`；
- `rtl/ir_arq_l2.sv`；
- `rtl/ir_multilane_scheduler.sv`；
- `config/register_map/ir_axi_regs.yaml`；
- `board_profiles/ACTIVE_PROFILE.json`；
- `constraints/active/PORT1.generated.xdc`。

当参考文档与本文件的已批准方向决策冲突时，以本文件为项目级约束；当机器配置与本文件不一致时，必须显式报错并通过受控变更解决，不能默默选择其一。
