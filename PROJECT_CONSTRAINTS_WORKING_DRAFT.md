# RF_COMM_MULTILANE 临时约束与方案工作稿

```text
DOCUMENT_STATUS: NON_NORMATIVE_WORKING_DRAFT
CANONICAL_TARGET: PROJECT_CONSTRAINTS.txt
CANONICAL_TARGET_EDIT_LOCK: LOCKED_UNTIL_ALL_QUESTIONS_RESOLVED
NO_HARDWARE_ACTIONS_EXECUTED: true
HARDWARE_ACCEPTANCE: PENDING_HW
```

本文件用于保存 `grill-with-docs` 分批审核结果。它不是项目规范、不是硬件授权，也不能覆盖 `PROJECT_CONSTRAINTS.txt`、活动 profile、canonical pinmap/XDC、register map 或任何正式 evidence。

## 工作流门禁

1. 自动从代码、文档和证据提出问题，并优先自行回答。
2. 只有会实质改变技术方向且无法从仓库推断的问题才提交用户决定。
3. 每累计 50 个问题，或确认没有新问题时，输出审核包。
4. 审核结论先并入本临时文件。
5. 只有全部问题清零后，才允许修改 `PROJECT_CONSTRAINTS.txt`。
6. 默认 `NO_HARDWARE=1`；本工作流不授权任何硬件动作。

## 第 1 批审核状态（Q001–Q050）

```text
BATCH_001_STATUS: REVIEWED
REVIEW_DATE: 2026-07-17
DIRECTION_QUESTIONS_RESOLVED: 5
CANONICAL_TARGET_SHA256_AT_LOCK: D9C9AC9981DAC3B97FDCE8446B71002A688053ABF97111EB3A306D9CEAA7A2E9
```

### 用户冻结的方向决策

| ID | 决策 | 已确认答案 | 临时约束含义 |
|---|---|---|---|
| D1 | 最终器件 | `XC7Z020-2CLG400I` | Vivado part 为 `xc7z020clg400-2`；最终板级 profile 仍需单独建立 |
| D2 | 双端控制器 | 固定侧和旋转侧相同 | 两端均使用 `XC7Z020-2CLG400I`，最终验收为两个独立节点 |
| D3 | 任意角度 8-lane | 最终验收硬性要求 | 构建阶段可逐步达到；任何中间结果不得冒充最终 8-lane PASS |
| D4 | 固定环几何 | D600 确定 | `r=100 mm`、`R=300 mm`、名义径向光程 `200 mm` |
| D5 | 32/16 Mbit/s 口径 | RAW 速率 | 32 Mbit/s 半双工、16 Mbit/s/方向全双工均为 PHY RAW capability，不等于应用 goodput |

### 已确认的事实边界

- P7 正式结果只证明静止、无 Ethernet、无运动、真实 PS runtime 的 2-lane 应用闭环。
- 当前 P0–P7 canonical profile 和构建输入仍绑定 AX7010 / `xc7z010clg400-1`，不能直接冒充最终 Zynq-7020 实现。
- 当前 P6 dynamic transport engine 固定为 2 lane，64 MHz 下 `CHIP_CYCLES=32`，实际 RAW 速率为 1 Mbit/s/lane。
- 当前 scheduler 选择 first-enabled lane；当前 ARQ 为单 outstanding stop-and-wait；RFAP v1 为 strict-order、`out_of_order_window=0`。
- TFDU6102 startup、Txd stuck-high、rolling duty、shutdown-on-exit 和系统级阵列安全优先于吞吐目标。
- Offline、仿真和历史证据不得把最终硬件状态提升为 PASS。

### 当前工作架构假设（尚未全部冻结）

```text
PC / Ethernet / TCP
  -> fixed XC7Z020 PS
  -> AXI DMA SG over AXI HP
  -> aggregate AXI-Stream
  -> 8-lane PL scheduler / ARQ / handover
  -> fixed 32-module optical front-end
  -> TFDU6102 optical paths
  -> rotating 8-module front-end
  -> rotating XC7Z020 PL/PS/application
```

- 固定侧 32 个 TFDU、旋转侧 8 个 TFDU作为首版工程基线；如果实测 FOV、公差或系统级安全不能闭合，应增加余量或改进光机设计，不得降低最终任意角度 8-lane 硬要求来维持既定模块数。
- 32 模块可以同时用 4 个相位 Bank（每组 8 个）和 8 个 sector bank（每组连续 4 个）两种正交视图描述；编号和职责不得混用。
- 推荐 primary/candidate 双 RX、单 TX、candidate 预启动、quiet-window 原子切换和 path epoch 去重。
- 推荐聚合、非 multichannel AXI DMA SG；lane 分发、重排和重传留在 PL。
- RFAP v1 保持兼容；窗口、SACK、path epoch 和多 outstanding 使用版本化后继协议。
- 4 Mbit/s/lane 需要重新闭合独立时钟接收、20% duty airtime、帧时长、时序和真实硬件验证；不得从当前 1 Mbit/s P7 证据外推。

## 第 2 批状态（Q051–Q100）

```text
BATCH_002_STATUS: REVIEWED
REVIEW_DATE: 2026-07-17
DIRECTION_QUESTIONS_RESOLVED: 6
OPEN_DIRECTION_DECISIONS: 0
CANONICAL_TARGET_EDIT_LOCK: LOCKED
```

### 用户冻结的方向决策

| ID | 决策 | 已确认答案 | 临时约束含义 |
|---|---|---|---|
| D6 | 最终板卡形态 | 商业核心板 + 自研载板 | 两端核心板均必须实际装配 `XC7Z020-2CLG400I`；固定侧和旋转侧允许使用角色专用载板；核心板型号、revision、原理图和可用 I/O 在生成最终 profile/XDC 前冻结 |
| D7 | 固定侧 32-to-8 前端 | 单个中央 XC7Z020；8 个无 FPGA/MCU 的四模块 bank | 每 bank 使用离散双 4:1 RX MUX、1:4 TX 选择/安全缓冲、SD 锁存/开漏控制和保护电路；全系统保持 8 TX + 16 RX；bank 上不得放 FPGA、CPLD 或 MCU |
| D8 | 运动包络 | 正反转、速度变化；不规定最大加速度/减速度 | 硬速度边界仍为 `|rpm| <= 600`；设计不得依赖固定转向或加速度预测；正常 RUN 至少保持正向和反向相邻候选 RX 都已 startup-ready，推荐固定侧全部 RX 常态唤醒；相位异常时停止新 TX 并重新 acquisition |
| D9 | 轴角传感器 | 增量式 ABZ，分辨率足够 | ABZ 进入 PL 计数、方向、速度和相位逻辑；实际 PPR、电气接口、最高边沿率、滤波和 index 标定作为待冻结实现参数，必须用采样/延迟预算验证而不能只写“足够” |
| D10 | 旋转侧本地接口 | SPI | 旋转侧通过版本化、带长度/CRC/流控/超时的 SPI 服务与本地应用交换数据；master/slave 角色和最高 SCLK 仍作为接口实现参数 |
| D11 | PS 软件平台 | 采用推荐方案 | 两端使用 FreeRTOS；固定侧使用 lwIP 提供 Ethernet/TCP；微秒级 PHY、handover、ABZ 捕获和安全门控全部留在 PL/外部硬件 |

### 第 2 批确认结论

- `XC7Z020-2CLG400I` 的芯片 I/O 数量可容纳约 24 条高速数据线和必要控制线，但商业核心板实际引出能力必须由具体型号证明。
- 现有 AX7010 profile、pinmap 和 XDC 不能复用为最终板级输入；最终需要固定侧和旋转侧独立 profile。
- 4 个相位 Bank 和 8 个四模块 sector bank 是正交视图；最终文档应统一分别称为“相位索引”和“物理 bank”，避免把两者都简称 Bank。
- D7 取代此前“每 bank 使用 CPLD”的工作假设。离散 bank 必须通过异步安全清零、`GLOBAL_PERMIT`、TX 硬件门控和 readback/故障检测达到等效失败关闭能力。
- 双 RX、单 TX 保持：handover 期间 current/candidate 可以同时接收，但任何 bank 任一时刻最多一个模块获得 TX 许可。
- 正反转兼容通过双方向预启动消除对加速度上限的依赖；若只预启动一个预测方向，则仍必须规定加速度/反转边界，该降级实现不满足 D8。
- 现有 P7 polling、MMIO payload 和 strict-order stop-and-wait 仅保留兼容基线；最终数据面采用聚合 AXI DMA SG、HP DDR、bounded reorder/selective repeat 和多 outstanding。
- 两端独立时钟、独立 reset、独立 session；FreeRTOS 调度和 TCP 断线不得参与 TFDU 的硬实时安全闭环。
- D5 只冻结 RAW 能力；当前文件中的 application-goodput 数值继续作为待数学闭合和实测验证的候选门槛。

## 第 3 批状态（Q101–Q150）

```text
BATCH_003_STATUS: REVIEWED
REVIEW_DATE: 2026-07-17
DIRECTION_QUESTIONS_RESOLVED_OR_DEFERRED_BY_USER: 8
OPEN_DIRECTION_DECISIONS: 0
DEFERRED_IMPLEMENTATION_PARAMETERS: D12,D13,D14
CANONICAL_TARGET_EDIT_LOCK: LOCKED
```

### 用户冻结或明确延期的方向决策

| ID | 决策 | 已确认答案 | 临时约束含义 |
|---|---|---|---|
| D12 | 商业核心板具体型号 | 当前不冻结，实际硬件构建时再问；FPGA 型号一致即可 | 当前只冻结两端 FPGA 均为 `XC7Z020-2CLG400I`；具体核心板必须在原理图、pinmap、XDC 和硬件采购前通过阶段门，未冻结时不得进入最终载板实现或硬件验收 |
| D13 | ABZ 电气接口和上电绝对定位 | 延期到旋转阶段再问 | 当前冻结“增量式 ABZ”方向；电气标准、PPR、Z 标定和静止上电 acquisition 必须在任何旋转硬件执行前关闭，延期不等于允许凭假设宣称 phase valid |
| D14 | SPI 主从、速率和实现位置 | SPI 的另一端也是 FPGA，具体参数暂不冻结 | 旋转侧本地链路是 FPGA-to-FPGA SPI；master/slave、MIO/PL、SCLK、READY/IRQ 和吞吐门槛在 SPI 实现前冻结；未冻结时 SPI 端到端验收保持 PENDING |
| D15 | 旋转侧供电 | 首版使用电池 | 旋转侧为独立电池电源域；电芯体系、BMS、容量、续航、连接器、保险、低压关断、动平衡和安全安装由后续功耗/机械预算冻结 |
| D16 | 光学封闭与隔离 | 系统不封闭；同侧模块之间设置格挡 | 开放式阵列必须进行系统级可接近红外辐射评估；格挡同时承担同侧串扰抑制，但不能自动替代眼安全、反射、跨侧串扰和维护状态验证 |
| D17 | 网络安全 | 不考虑；仅内网 | 网络边界冻结为可信内网；不要求 TLS/远程身份体系，但仍必须做长度校验、状态机校验、错误隔离和拒绝畸形输入，且不得宣称适用于不可信网络 |
| D18 | 单模块故障后的 lane 保证 | 允许降级 | D3 的任意角度 8-lane 硬要求适用于无故障正常配置；模块故障后允许明确降为 7..1 lane，并且必须报告，不能继续声称 8-lane PASS |
| D19 | 应用 goodput | 同意推荐门槛 | 最低端到端 application goodput 为半双工 `>=16 Mbit/s`、全双工每方向 `>=8 Mbit/s`；`19.2/9.6 Mbit/s` 为挑战目标；统计边界覆盖 PC/TCP、固定 PS/PL、光链路、旋转 PS/PL 和 SPI FPGA 端点 |

### 第 3 批确认结论

- D7 的最终 bank 不含 FPGA、CPLD 或 MCU；当前 CPLD 版设计文档只能作为被方向决策覆盖的参考输入。
- 正常 RUN 推荐固定侧全部 32 个 RX 常态唤醒；TX 仍为每 bank one-hot。旧路径不得因一次 handover 立即 shutdown，从而使正反转正确性只依赖 `|rpm| <= 600`、位置连续和有界切换延迟，而不依赖加速度上限。
- 24 条 raw 数据接口保持不变：8 TX、8 current RX、8 candidate RX。off-board 原始脉冲默认经过差分 line driver/receiver；单端长线必须有 SI 证据。
- SD 串行控制必须原子锁存、实际输出回读、链故障检测，并由独立 active-high `GLOBAL_PERMIT` 在外部直接门控 SD NMOS 和 TX buffer。
- ABZ 在首次 Z 或替代 acquisition 前不具备绝对相位；D13 阶段门未关闭时只能保持 receive-only/safe acquisition，不得进入确定性 handover。
- Zynq-7000 PS SPI 的 MIO/EMIO 能力只用于约束候选实现；D14 未关闭前不能假定 SPI 不会成为端到端瓶颈。
- FreeRTOS/lwIP 的任务优先级、DMA ownership 和 cache 一致性必须有界；网络、SPI 或日志任务不得参与微秒级安全闭环。
- 单个固定模块失效时相邻模块可能超出名义 FOV，旋转模块失效则必然少一 lane；因此故障后降级与正常配置 8-lane 验收必须使用不同状态和证据字段。

## 第 4 批状态（Q151–Q200）

```text
BATCH_004_STATUS: REVIEWED
REVIEW_DATE: 2026-07-17
DIRECTION_QUESTIONS_RESOLVED: 1
OPEN_DIRECTION_DECISIONS: 0
CANONICAL_TARGET_EDIT_LOCK: LOCKED
```

### 用户冻结的方向决策

| ID | 决策 | 已确认答案 | 临时约束含义 |
|---|---|---|---|
| D20 | 开放阵列的人体接近策略 | 同意推荐方案 | 系统级可接近红外辐射测量与合规评估通过前，发射区使用受控排除区、钥匙许可和急停；维护状态强制 `GLOBAL_PERMIT=0`。只有系统级测量证明安全后，才可按书面条件放宽人体接近策略；格挡不替代该安全门。 |

### Q151–Q200 审核结论

| Q | 问题 | 审核结论 |
|---:|---|---|
| 151 | 延期参数是否可留到最终验收 | D12/D13/D14 只能延期到各自阶段门；核心板在原理图/profile/XDC/采购前、ABZ 在旋转执行前、SPI 在接口实现前冻结。 |
| 152 | 4 Mbit/s 4PPM 的符号/脉冲基线 | 每 bit 250 ns；按 TFDU6102 的 4PPM 路径使用 125 ns 发射脉冲并重新闭合真实时序。 |
| 153 | RAW 速率是否等于连续发光 | 否；RAW 是编码比特率能力，发光受 4PPM 脉冲、帧开销和 duty 上限约束。 |
| 154 | 发射 duty 硬边界 | 每个发射器在规定窗口内严格 `<20%`，并保留 stuck-high 与外部失效关闭。 |
| 155 | 当前 RTL 是否真正实现 rolling duty | 否；当前实现是固定 1 ms 分桶，不是任意起点的滑动窗口。 |
| 156 | 固定分桶为何不充分 | 跨桶边界的前后各 200 µs 发射可令两个桶分别合格，但同一滑动 1 ms 内达到 40%。 |
| 157 | duty 修复路线 | 使用精确滑动和、形式化证明的保守整形器或二者组合；固定分桶不得作为最终 PASS。 |
| 158 | duty 的统计范围 | 同时提供 per-emitter、per-physical-bank、全阵列发射并发与系统级光学测量证据。 |
| 159 | 最大现有帧的 airtime | 247-byte payload 基线约 1076 个 4PPM symbol、约 538 µs airtime、约 134.5 µs Txd-high。 |
| 160 | 20% duty 下理论 payload 上限 | 现有最大帧格式约 2.94 Mbit/s/lane；计入 RFAP 分片约 2.56 Mbit/s/lane，8 lane 理想约 20.46 Mbit/s。 |
| 161 | goodput 门槛是否有数学余量 | 半双工 16 Mbit/s 约占理想上限 78.2%，可作为硬门；19.2 Mbit/s 约占 93.8%，仅作挑战目标。 |
| 162 | stop-and-wait 是否可保留为最终数据面 | 仅作 RFAP v1 兼容路径；最终使用有界 selective-repeat、SACK 和多 outstanding。 |
| 163 | 半双工 ACK 路径 | 采用成批反向窗口/方向切换，不按每帧反转；切换必须受 duty、quiet window 和安全门约束。 |
| 164 | 全双工 ACK 路径 | 优先在反向 4-lane 数据流中聚合或捎带 ACK，避免独立 ACK 风暴。 |
| 165 | handover 边界能否启动任意长帧 | 不能；scheduler 必须做 frame admission，证明帧可在安全窗口完成或可无损迁移。 |
| 166 | L1 payload 上限是否立即扩大 | 首版保持 247-byte 量级以控制 airtime；扩大前必须重做窗口、duty、buffer 和错误恢复证明。 |
| 167 | RFAP v1 如何演进 | 保持兼容；新窗口、SACK、path epoch、streaming 能力通过版本协商进入后继协议。 |
| 168 | 协议层职责 | L1 管帧完整性，L2 管 ARQ，L3 管逻辑 lane/物理路径/handover，L4 管对象完整性，禁止跨层隐式状态。 |
| 169 | outstanding 下限 | 全局至少 32，推荐 64；还须按 lane/方向设置有界配额，防止单 lane 饥饿。 |
| 170 | SACK/序号下限 | SACK 窗口至少 32；序号域至少 16 bit，并由 session epoch 消除回绕歧义。 |
| 171 | lane scheduler | 使用 health-aware weighted round-robin；普通数据不复制，控制/切换关键帧可有限复制。 |
| 172 | 降级状态如何传播 | `active_lane_mask`、`degraded_reason`、`path_epoch` 和计数器原子快照，传播到 PL、PS、网络与 evidence。 |
| 173 | 跨 lane 重传 | 只迁移未确认帧；已确认数据不得因路径变化重复提交，接收端按 session/sequence/object 去重。 |
| 174 | 大对象策略 | 支持至少 64 MiB 或真正流式对象；不要求整体驻留 OCM/DDR，提交前完成 CRC/SHA 与原子发布。 |
| 175 | DMA 选型 | 单个聚合 AXI DMA scatter-gather 通过 HP 口连接 DDR；lane 分发、重排和 ARQ 留在 PL。 |
| 176 | backpressure 范围 | 从旋转侧 SPI 到 PC/TCP 的每一级都必须有界并可观测；溢出失败关闭且不得静默丢对象。 |
| 177 | 两端独立性 | 固定与旋转节点具有独立时钟、复位、session、bitstream/firmware 和故障恢复；共享 RAM/数字 loopback 不算最终链路。 |
| 178 | SPI 服务边界 | FPGA-to-FPGA SPI 使用显式 framing、长度、CRC、流控、超时和版本；D14 阶段门前不冻结角色/速率。 |
| 179 | FreeRTOS 的职责 | 负责服务、策略和恢复，不参与微秒级 PHY、ABZ、handover 或安全闭环。 |
| 180 | 可信内网是否免除输入校验 | 否；可不做 TLS/远程身份，但长度、状态机、CRC、资源上限和畸形输入隔离仍是硬要求。 |
| 181 | 旋转端发射峰值电流 | 8 个 TFDU 同时按 0.6 A 峰值估算为 4.8 A；电池、连接器、铜皮与瞬态储能按峰值设计。 |
| 182 | 发射平均电流基线 | 在 20% duty 上界下约 0.96 A、3.17 W（仅 3.3 V IRED 部分），还需叠加 FPGA、PS、收发器和损耗。 |
| 183 | 电池子系统最低要求 | 电芯/BMS、保险、低压保护、温度监测、容量/续航、连接器、充电维护和故障隔离形成独立阶段门。 |
| 184 | 600 rpm 的机械载荷 | 半径 100 mm 处向心加速度约 394.8 m/s²（40.3 g）；电池宜靠近轴并做留存、动平衡和超速裕量验证。 |
| 185 | 欠压时系统行为 | 先撤销 `GLOBAL_PERMIT` 并持久化故障，再关闭数据面；禁止在电压跌落中产生不受控发射。 |
| 186 | 单器件 Class 1 能否代表阵列安全 | 不能；多发射器、反射、窗口/聚光、维护和单故障必须做系统级可接近辐射评估。 |
| 187 | 开放阵列的人体接近策略 | 采用 D20：测量通过前受控排除区、钥匙许可、急停，维护 `GLOBAL_PERMIT=0`。 |
| 188 | 格挡几何如何约束 | 若通道长度为 L、全开口宽 W，±12° 基线要求 `W/L >= 0.425`；±15° 要求 `W/L >= 0.536`，实际还需公差。 |
| 189 | “黑色格挡”是否足够 | 不足；必须测量约 886 nm 的反射/吸收与温升，不能用可见光颜色代替近红外证据。 |
| 190 | 环境光边界 | 日光、灯具、反射、污染和温度作为可参数化测试条件；未冻结前不承诺室外或强日照性能。 |
| 191 | 串扰测试范围 | 覆盖同侧相邻、跨侧多发射、反射面、4+4 同时双向、静止最坏相位与 600 rpm。 |
| 192 | 单模块故障的产品语义 | 正常无故障配置才允许 8-lane PASS；故障后报告 7..1 lane 与原因，必要时继续受限服务。 |
| 193 | `lane_ready` 定义 | 不能只表示几何选中；必须包含 startup、无 safety fault、近期有效帧/ACK、session/path epoch 一致与 buffer 可服务。 |
| 194 | 运动验收曲线 | 覆盖正转、反转、变速、停转、方向反转和相位重新 acquisition；只限制 `|rpm|<=600`，不设数值加速度上限。 |
| 195 | goodput 统计边界 | 以 PC/TCP 到远端 SPI FPGA 应用端点的已校验有效字节为准，排除协议头、重传、填充和未提交对象。 |
| 196 | duty 验证证据 | 需要 RTL/形式化、门级或仿真计数、电气波形和系统级光学测量；任一离线结果不能替代硬件接受。 |
| 197 | 新增离线 gate | 增加 8-lane elaboration、CDC、rolling-duty、handover model、protocol invariants、geometry/property 与资源/时序 gate。 |
| 198 | 硬件推进顺序 | 离线架构 → 静止高吞吐 → 双独立节点 → 单 lane 动态 handover → 全环低速 → 分级升速 → 端到端/全双工。 |
| 199 | 应形成哪些 ADR | 精确 Zynq-7020、32×8 几何、中央 PL+离散 bank、双 RX/单 TX、聚合 DMA、RFAP 后继协议、开放阵列安全、电池旋转端。 |
| 200 | 是否已经允许修改目标文件 | 尚不允许；先完成 Q201–Q250 的最终一致性、ADR、术语、风险与验证收敛并经用户审核。 |

### 第 4 批确认结论

- D20 关闭了最后一个当前已知的方向决策；系统级测量通过前，开放阵列不得作为可自由接近发射设备运行。
- 4 Mbit/s/lane 与 20% duty 不是独立口号，必须通过滑动窗口整形、帧 admission、ARQ 效率和端到端 goodput 同时闭合。
- 当前 `tfdu_lane_phy.sv` 的固定 1 ms 分桶不能证明任意起点 1 ms 滑动 duty，最终实现必须修正并增加形式化/硬件证据。
- 半双工 `16 Mbit/s` 和全双工 `8 Mbit/s/方向` 保持硬验收门；`19.2/9.6 Mbit/s` 保持挑战目标，不能反向削弱安全裕量。
- 电池旋转端的峰值电流、欠压关闭、约 40 g 向心载荷、动平衡和留存是进入 600 rpm 前的硬阶段门。
- `PROJECT_CONSTRAINTS.txt` 继续锁定，等待 Q201–Q250 审核完成。

## 第 5 批状态（Q201–Q250）

```text
BATCH_005_STATUS: REVIEWED
REVIEW_DATE: 2026-07-17
OPEN_DIRECTION_DECISIONS: 0
NO_NEW_DIRECTION_QUESTIONS: true
CANONICAL_TARGET_EDIT_LOCK: UNLOCKED_FOR_APPROVED_REWRITE
```

### Q201–Q250 审核结论

| Q | 问题 | 审核结论 |
|---:|---|---|
| 201 | 最终文件的规范地位 | `PROJECT_CONSTRAINTS.txt` 管理项目级目标、架构和验收；不覆盖 `AGENTS.md`、硬约束文件或机器可读 canonical 配置。 |
| 202 | 最终器件表达 | 两端订货型号均为 `XC7Z020-2CLG400I`，Vivado part 为 `xc7z020clg400-2`。 |
| 203 | 两端 FPGA 一致性 | 固定侧和旋转侧均使用同型号器件，角色专用载板可以不同。 |
| 204 | 核心板未选型是否阻塞 | 不阻塞约束冻结；在原理图、采购、profile、pinmap、XDC 前作为硬阶段门关闭。 |
| 205 | AX7010/Zynq-7010 定位 | 仅为 P0–P7 和后续可移植功能的受限开发基线，不能代表最终 Zynq-7020 产品。 |
| 206 | 4 Bank/8 Bank 术语冲突 | 4 个值称 `Phase Index`；8 个四模块实体称 `Physical Sector Bank`，禁止混称。 |
| 207 | 最终计数字段 | 固定模块 32、physical sector bank 8、每 bank 4、phase index 4；移除含糊的 `FIXED_BANK_COUNT=4`。 |
| 208 | logical lane 绑定 | `L0..L7` 固定绑定 `R0..R7`，固定侧 physical path 随角度变化但 logical lane 身份不变。 |
| 209 | FOV 设计线 | ±15°作器件名义参考，±12°作首版保守设计线，最终由实际光机测量闭合。 |
| 210 | 任意角度 8 lane | 正常无故障且相位有效时，任意角度 8 个 logical lane 都有可完成有效帧交易的路径。 |
| 211 | 模块故障后的要求 | 进入显式 degraded mode，报告 mask/reason/epoch，不再声称 8-lane PASS。 |
| 212 | 最大加速度 | 不设数值；硬边界为 `|rpm|<=600`、角度连续、phase valid，设计不依赖转向预测。 |
| 213 | ABZ 未获得绝对相位 | 保持 receive-only/safe acquisition，首次 Z 或替代标定前禁止确定性 TX handover。 |
| 214 | 正常 RUN 的固定 RX | 32 个 RX 全部保持 startup-ready；SD 用于上电、维护、故障隔离和紧急关闭。 |
| 215 | 固定侧 TX/RX 结构 | 每 physical sector bank 单 TX one-hot、current/candidate 双 RX；总计 8 TX + 16 RX。 |
| 216 | bank 上可编程器件 | 禁止 FPGA/CPLD/MCU；使用离散 MUX、demux/缓冲、锁存、开漏和保护电路。 |
| 217 | 安全门控 | 独立 `GLOBAL_PERMIT` 直接门控外部 TX/SD，SD 原子锁存并回读，链故障失败关闭。 |
| 218 | raw 脉冲传输 | off-board 默认差分；单端只有在真实 SI/EMI/时序证据通过后允许。 |
| 219 | duty/stuck-high | 使用任意对齐滑动窗口、连续高限制、外部脉冲限制和失效关闭；固定分桶不合格。 |
| 220 | 开放阵列安全 | 按 D20 执行排除区、钥匙许可、急停和维护 `GLOBAL_PERMIT=0`。 |
| 221 | 电池最低边界 | 按 4.8 A 发射峰值并叠加数字负载设计，包含 BMS、保险、欠压、温度、留存和动平衡。 |
| 222 | 未冻结环境 | 作为阶段门；未测试环境不在产品保证范围，不阻塞当前架构约束冻结。 |
| 223 | 64 MHz 是否最终硬要求 | 否；独立时钟与 4 Mbit/s 时序是硬要求，64 MHz 仅为当前兼容基线。 |
| 224 | CDC/reset | 两端独立时钟和复位；所有跨域使用明确同步器、异步 FIFO 或握手并通过 CDC gate。 |
| 225 | Z7020 资源预算 | 设计目标 LUT/FF≤70%、BRAM/DSP≤75%、无负时序余量，并保留调试/修复空间。 |
| 226 | 核心板 I/O | 当前仅建立约 24 条 raw 线及控制线预算；最终由核心板引出、bank 电压和原理图证明。 |
| 227 | SPI 性能 | 不预设角色/SCLK；有效 goodput 比对应 IR application 门槛高至少 20%，且有 framing/CRC/流控。 |
| 228 | PS 平台 | 两端 FreeRTOS；固定侧 lwIP/Ethernet/TCP；微秒级实时和安全逻辑留在 PL/外部硬件。 |
| 229 | 可信内网 | 不要求 TLS/远程身份，但解析、长度、CRC、状态机和资源上限必须失败关闭。 |
| 230 | DMA | 聚合 AXI DMA SG 经 HP 口访问 DDR；lane 调度、ARQ 和重排留在 PL。 |
| 231 | RFAP v1 | 保留兼容；窗口、SACK、path epoch 和 streaming 进入版本化后继协议。 |
| 232 | 首版帧大小 | L1 payload 先保持最多 247 byte；v1 对象有效分片约 215 byte。 |
| 233 | ARQ | 有界 selective-repeat、SACK 和多 outstanding；stop-and-wait 仅作兼容/诊断。 |
| 234 | 序号回绕 | 序号至少 16 bit，并与 session epoch/path epoch 组合；拒绝旧 session ACK。 |
| 235 | lane 调度 | health-aware weighted round-robin；普通数据不复制，关键控制/切换帧可有限复制。 |
| 236 | ACK | 半双工采用批量方向窗口；全双工在反向数据流聚合或捎带 ACK。 |
| 237 | backpressure | 覆盖 PC/TCP、两端 PS/DMA/PL、光链路和 SPI，所有队列有界且可观测。 |
| 238 | 对象提交 | CRC32、SHA256、长度和 session 均正确后原子发布；拒绝 partial/duplicate/stale。 |
| 239 | application goodput 边界 | PC/TCP 到远端 SPI FPGA 应用端点的已校验有效字节，不含头、重传、填充和未提交对象。 |
| 240 | 性能硬门 | RAW 32/16 Mbit/s/方向；应用 16/8 Mbit/s/方向；19.2/9.6 为挑战目标。 |
| 241 | 实施阶段 | 受限开发→高吞吐→Z7020/双节点→单 lane handover→全环→600 rpm→端到端→全双工。 |
| 242 | 是否授权硬件 | 否；继续 `NO_HARDWARE=1`，未来硬件动作需要单独授权和安全关闭。 |
| 243 | 离线是否能产生硬件 PASS | 不能；离线、仿真和缺工具路径保持 `HARDWARE_ACCEPTANCE: PENDING_HW`。 |
| 244 | 正式 evidence | 冻结源码、bitstream/ELF、profile/XDC/register-map 哈希、硬件 ID、标定、条件、日志和 shutdown。 |
| 245 | 故障验收 | 正常模式验证 8 lane；故障注入验证检测、降级、恢复和报告，证据不可混用。 |
| 246 | ADR | 记录双 Z7020、32×8 几何、中央 PL+离散 bank、全 RX/双 RX 单 TX、PL/RTOS 边界、DMA、RFAP、安全、电池。 |
| 247 | 术语表 | 固结 Logical Lane、Physical Path、Sector Bank、Phase Index、Path Epoch、Handover、Lane Ready、Goodput 等。 |
| 248 | 风险与验证 | 几何、安全、duty、效率、I/O、SPI、电池/机械、ABZ、CDC、资源、环境串扰和协议均绑定阶段门。 |
| 249 | 最终修改范围 | 只重构 `PROJECT_CONSTRAINTS.txt`，不修改代码、设计文档、canonical 配置或硬约束文件。 |
| 250 | 是否还有方向问题 | 没有；剩余内容均为已定义的实现/硬件阶段参数。 |

### 批后新增并由用户直接冻结的方向决策

| ID | 决策 | 已确认答案 | 临时约束含义 |
|---|---|---|---|
| D21 | 当前硬件到最终平台的开发迁移路线 | 当前只有 1 块 Zynq-7010 开发板、2 lane、4 个 TFDU 小板；先在该平台尽可能开发和验证，再迁移到 Zynq-7020 开发板 | 建立 `Z7010_2LANE_DEV` 受限 profile 与最终 `Z7020_8LANE` profile；可移植核心、协议、寄存器和安全语义共源，板级 wrapper/pin/clock/BSP 分离。7010 证据只覆盖静止 2-lane 和实际运行范围，8-lane、双独立节点、32-to-8、旋转、最终吞吐与产品验收继续 PENDING。该决策不授权当前硬件执行。 |

### 第 5 批确认结论

- `OPEN_DIRECTION_DECISIONS=0`；D21 是用户给出的确定路线，不产生新的方向问题。
- 最终约束必须同时维护两个边界：当前 7010/2-lane/4-board 的最大可验证范围，以及最终双端 `XC7Z020-2CLG400I`/8-lane 产品范围。
- 7010 优先验证可移植功能，但不得为了塞入 7010 而删除最终所需的安全、协议或可观测性语义；资源不足时允许 feature-sliced 开发构建，但不能冒充集成验收。
- 迁移通过参数化 core、板级 wrapper、版本化 register map/协议和双目标离线构建矩阵完成；最终 Z7020 硬件证据必须重新取得。

## Canonical 合并记录

```text
MERGE_DATE: 2026-07-17
REVIEWED_BATCHES: Q001-Q250
REVIEWED_DECISIONS: D1-D21
OPEN_DIRECTION_DECISIONS: 0
CANONICAL_TARGET_MERGE_STATUS: COMPLETED
CANONICAL_TARGET_VERSION: V3
CANONICAL_TARGET_SHA256_AFTER_MERGE: 2014A2DD33FC8EAAE98CC7661946BC38021B884B7027581CFF131DAE9FC8D163
HARDWARE_ACTIONS_EXECUTED: false
HARDWARE_ACCEPTANCE: PENDING_HW
```

本临时文件继续只作为审核轨迹；项目级规范内容以已更新的 `PROJECT_CONSTRAINTS.txt` 为准。
