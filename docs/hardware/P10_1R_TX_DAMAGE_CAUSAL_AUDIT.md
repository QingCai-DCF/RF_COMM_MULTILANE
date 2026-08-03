# P10.1R TX 长时间发射与器件损坏因果审计

## 审计结论

状态：`PARTIAL_CAUSAL_ASSESSMENT / HARDWARE_HOLD`

对“运行代码使 Txd 长时间保持高电平并烧坏 TFDU6102”的判断是：

- **现有记录不支持“代码造成长时间连续发射”这一具体因果链。** 对 P10、P10.1 和 P10.1R 留存的全部 4,809 份有效 1024-byte mailbox 快照重新解码后，记录到的最大连续 Txd 高电平是 16 个 64 MHz 周期，即 250 ns；没有一份超过 RTL 的 64 周期/1 us 限值。
- 记录到的最大任意对齐 1 ms 窗口高电平为 11,504/64,000 周期，即 17.975%；没有超过 18% 设计目标或 TFDU6102 数据手册 `<20%` 的重复脉冲占空比上限。全部快照的 hard-duty fault counter 和 PHY sticky safety mask 均为零。
- 最新 F1→R1 失败样本中，最终物理 TX 时间戳的上升沿到下降沿只相差 5 个周期，即 78.125 ns，并非长高电平。
- **这些数字证据不能证明器件没有损坏，也不能排除板外电气、供电、部分上电、接触、光路、ESD 或器件本身故障。** 本项目没有示波器、电流、温度或外部光功率记录；FPGA 内部计数器不能替代包脚波形和光学测量。
- 审计发现一个与“烧坏”方向相反、但会影响诊断可信度的代码问题：P10.1R raw connectivity 发生器使用 5 个周期（78.125 ns）的脉冲，短于 TFDU6102 数据手册表征的 `0.1 us` 下限，也短于 4 Mbit/s 的 125 ns 标称脉冲。它可能制造物理连通性的假阴性或暴露边缘链路，但不会形成热过载型长发射。

因此，本审计不能给出“器件未损坏”的 PASS，也不能把当前 F1→R1 故障归因于烧毁。可支持的最窄结论是：**记录内没有长 Txd 或超占空比证据；器件状态和真正因果仍需板外测量。**

## 立即隔离状态

- 本审计期间：`NO_HARDWARE=1`，`CURRENT_RUN_HARDWARE_AUTHORIZATION=false`。
- 没有执行新的 JTAG 连接、program、ELF、UART、寄存器写或 TFDU 驱动。
- 当前授权记录已经消费：`CONSUMED_AFTER_P10_1R_HARDWARE_FAIL`，`current_run_hardware_authorization=false`。
- 最新 run `p10_1r_20260803T064202Z_cce2180b_c1370686_bfb1c51d` 的最后证据记录 fixed/rotating shutdown 均为 PASS；最终 orchestrator SHA256 为 `6b5b055197f00823d2b6d60507e850a70deda2126a7f6bac994c5cd4d0e79423`。
- 当前仅观察到自 2026-07-28 起存在的 `hw_server` 进程；没有活动的 Vivado、XSDB 或 XSCT 进程。该观察不等价于重新读取硬件状态。

## 官方器件限值

审计源为 Vishay `TFDU6102datasheet.pdf`，SHA256：

`54db2771cf8887eb264f38518b13ec5eb17be04d63a20712d18a558b0c7376ef`

| 项目 | 官方资料位置 | 限值或行为 |
|---|---|---|
| Txd 保护 | PDF page 4 / printed page 3，Pin Description | Txd 高于约 80 us 时，片上保护电路禁用 LED driver。 |
| 重复脉冲绝对最大值 | PDF page 5 / printed page 4，Absolute Maximum Ratings | `t < 90 us`，占空比 `<20%`。 |
| 标准 4 Mbit/s 发射脉冲 | PDF page 8 / printed page 7，Transmitter | 125 ns 输入对应 117–133 ns 光脉冲；250 ns 输入对应 242–258 ns 光脉冲。 |
| 较长输入脉冲 | PDF page 8 / printed page 7，Transmitter | `0.1 us < tTxd < 80 us` 时光脉冲通常跟随输入；更长输入由内部保护限制为 20–85 us。 |
| shutdown 优先级 | PDF page 10 / printed page 9，Truth Table | `SD=HIGH` 时 transmitter 为 0，与 Txd 无关。 |
| 温度降额 | PDF page 11 / printed page 10，Figure 4 | 20% duty 下的允许环境温度随供电电压降额；实际模块温度未被本项目测量。 |

数据手册的内部保护使“FPGA Txd 永久高就永久光发射”这一推断本身不成立。不过，内部保护不能替代系统级限幅，也不能证明经历未知供电或部分上电状态后器件一定完好。

## 全部已记录 mailbox 的重新审计

解码条件：文件长度 1024 bytes、mailbox magic `0x424D3950`、PL snapshot magic `0x5031305A`。连续高、rolling duty、hard-duty fault 和 PHY safety mask 均直接取自冻结硬件 mailbox 中的 PL snapshot；不是从 Markdown PASS 汇总反推。

| 范围 | 有效 mailbox | 最大连续高 | 最大连续高时间 | 最大 1 ms rolling high | 最大占空比 | hard-duty 非零 | PHY safety mask 非零 |
|---|---:|---:|---:|---:|---:|---:|---:|
| P10 | 2,942 | 16 cycles | 250 ns | 8,928 / 64,000 | 13.950% | 0 | 0 |
| P10.1 | 1,124 | 16 cycles | 250 ns | 8,928 / 64,000 | 13.950% | 0 | 0 |
| P10.1R | 743 | 16 cycles | 250 ns | 11,504 / 64,000 | 17.975% | 0 | 0 |
| 合计 | 4,809 | 16 cycles | 250 ns | 11,504 / 64,000 | 17.975% | 0 | 0 |

门限：

- RTL continuous-high limit：64 cycles = 1 us。
- 1 ms exact window：64,000 cycles。
- strict hard maximum：12,799 cycles，保证严格 `<20%`。
- design target register：11,520 cycles = 18%。

最大值原始文件：

| 范围 | 原始 mailbox | SHA256 |
|---|---|---|
| P10 | `evidence/hardware/p10/p10_formal_20260730T181535Z_03/stages/p10_j/dumps/soak_00395_1048576_d1.rotating.bin` | `128f98cac8afa69002e28e77aab9c8ad0d56e760588ec194493e4cab32810ad9` |
| P10.1 | `evidence/hardware/p10_1/p10_1_hw_20260801T090528Z_bb6ce78a_1585d1ad_9ad4f85f/stages/formal/dumps/stationary_30min_warmup_r2f_0012_1048576.rotating.bin` | `e85c7929d9cdc17061f909c94aba5cde2f7c01dc0f9914c5140a02196c1ec0ff` |
| P10.1R | `evidence/hardware/p10_1r/p10_1r_20260803T061448Z_cce2180b_c1370686_bfb1c51d/crosstalk_remediation/dumps/remediation_frame_lane0_r2f_0000_1048576.rotating.bin` | `93b97bca119c08b343608ec2102e29b2e2f14a2cdab75d16fc69de55b326af9a` |

正常 4PPM serializer 使用 8-cycle/125 ns 脉冲。跨相邻 symbol 边界的两个脉冲可以在数字域连续相接为 16 cycles/250 ns，这与记录最大值一致，仍远低于 1 us 项目限值和 80/90 us 器件级限值。

这些 mailbox 是离散采样，并且部分命令会在边界清 telemetry；它们不是示波器的无间断外部波形记录。RTL sticky fault 设计使同一启动周期内的 continuous/duty fault 应保持到 reset 并触发 fail-closed，但重新 program/reset 之间的 FPGA-unconfigured/partial-power 行为不在 mailbox 可观测域中。

## 冻结 RTL 与 artifact 绑定

P10 final、P10.1 和当前 P10.1R 使用的三个 source commit 中，以下 safety 源的内容 SHA256 完全一致：

| 文件 | SHA256 |
|---|---|
| `rtl/generated/tfdu_safety_config.svh` | `afce2804034e0423a954988aeb0b59b2b97d28a53165648891b3cc33b2718e1d` |
| `rtl/ir_tfdu_physical_module_safety.sv` | `428a40acf4f5638294d8fd516c3ba86fbe3e90ce0bc0a2ddc9b2a4051020ac19` |
| `rtl/ir_tfdu_exact_duty_accountant.sv` | `05385eee22ad7ace59da7ced41296ce0480fcd0339d8dee3194534cc5af9cb2f` |
| `rtl/tfdu_lane_phy.sv` | `2382f84ac66d358e24a47e5864753637283aa6800b83899d0194d070da230ba7` |

核对的 source commits：

- P10 final：`8aa3879c5a8a5a4ed327b1084575bcfcc953f06b`
- P10.1：`bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1`
- P10.1R：`cce2180bcaa9dd1cb4f0f09bf02a68530f6eb62d`

安全路径的可控关系为：

1. software/serializer 只能提出 `tx_pulse_req`；
2. per-module guard 对连续高和 exact rolling duty 做最终准入；
3. reset、shutdown、sticky safety fault、endpoint disarm/kill 均只能缩短 Txd；
4. package 输出还经过 `endpoint_armed_q && !tx_kill` 的最终 AND；软件不能绕过该路径直接驱动包脚。

当前 P10.1R frozen artifacts 重新计算的 SHA256 与内容寻址路径一致：

- fixed functional bitstream：`c13706860a003721d45e9a6fd90f444825aaa1b342a74a095079eceffa856a27`
- rotating functional bitstream：`bfb1c51d639188ea60392c8ceb39b25276e12b819c8e2ee0c5ae3ef63497639f`
- fixed shutdown bitstream：`6ca0c42b93cdac8785a89948cfa14bc8c366d7a514394bd4a8dd9ae3becb3fdf`
- rotating shutdown bitstream：`66da73c6310887d6617ccb010f9804bb879aad0fe781e952ba713e31232fc6c6`

这能证明冻结设计中存在并启用了数字保护，不能证明 FPGA package pin、TFDU pin 或光输出在所有电源状态下都严格跟随 RTL。

## 当前故障时间线与隔离边界

| 时间/run | 直接结果 | 证据 SHA256 |
|---|---|---|
| `20260803T053211Z` | F0→R0、R0→F0、F1→R1、R1→F1 各 1000/1000 raw PASS | stage `afebdcc5121df41e0a28fb7fa261ff1cc6e16fe50539d98ffcb6a05e9b705235` |
| `20260803T060521Z` | 之后的 crosstalk remediation 在 F1→R1 1 MiB 对象中失败；raw telemetry 显示已接收/接受部分数据，最终未完成 | stage `7d3f6e323a49903be21b0ac8b9dfed63abacdbf9f898b6839412b18239182964` |
| `20260803T062846Z` | F0→R0、R0→F0、R1→F1 各 1000/1000；F1→R1 在 sample 0 失败 | stage `8fe86f27675bdcbef74a41607e6be187a675d27df18d347e19c33891ac6b9ae1` |
| `20260803T064202Z` | 增加 receiver settle 后结果不变；F1 最终 TX counter 增加，R1 raw counter 未增加 | stage `a73d0af266ae4d614db4342e47bb14a2a3333fae80c6e7209d93369b8a3ffd51` |

最新失败样本的直接事实：

- fixed F1 physical TX count 增加 1；
- fixed 侧 `sender_raw=1`、`sender_raw_while_tx=1`、`sender_blanked_raw=1`；
- rotating R1 `receiver_raw=0`；
- final-Txd timestamp：rise `33803829`，fall `33803834`，差 5 cycles = 78.125 ns；
- 原始 snapshot SHA256：`6f915a46480e09d8e361db02c296ebbd3277ba04030512f3f60bd5c85e9f5bb3`。

`sender_raw_while_tx` 可能来自模块本地光回授或数字/电气串扰，只能证明 fixed 侧观测到与本地 TX 同时的 Rxd 事件，不能单独证明外部发射光功率合格。R1→F1 仍通过，说明 fixed F1 receiver 和 rotating R1 transmitter 在该次测试中可形成链路；它不能区分 fixed F1 emitter、rotating R1 receiver、F1→R1 光路或电源/接触问题。

## 发现的诊断代码问题

当前 `rtl/p9_optical_transport_core.sv` 的 raw generator 使用：

`raw_pulse_request = raw_busy_q && raw_cycle_q < 5`

在 64 MHz 下为 78.125 ns。Vishay 表格对一般跟随行为给出的下限是 `0.1 us`，4 Mbit/s 标准输入脉冲是 125 ns。结论：

- 该 raw pulse 不符合器件表征区间，不能作为稳健的物理连通性验收激励；
- 它可能解释边缘路径中“有时 1000/1000、有时首脉冲即丢失”的一部分现象；
- 它比标准脉冲更短，不能支持“长发射造成热损伤”的假设；
- 在任何后续硬件运行前，应把 raw diagnostic 改为至少 8 cycles/125 ns，冻结新 artifacts，并重新执行离线和外部波形校验。旧硬件结果不得继承到新 bitstream。

## shutdown 审计与一个历史缺口

| 范围 | orchestrator runs | 最终双板 shutdown 非 PASS | shutdown attempt result files | 非 PASS attempts |
|---|---:|---:|---:|---:|
| P10 | 16 | 1 | 121 | 4 |
| P10.1 | 20 | 0 | 104 | 0 |
| P10.1R | 21 | 0 | 143 | 0 |

P10 唯一的非 PASS 来自 `p10_diag_a_20260730T141200Z_01`：fixed shutdown 成功，但 rotating target canonical-match 检查失败；P10-A 没有运行，随后 run 才完成双板 shutdown。该 run 的 orchestrator SHA256 为 `874010846d052e9cf85e13a7ea22fe8194c3a70b0fc48f4dea1fbf2dc7252e2c`。

这不是长 Txd 的正证据，因为该 run 没有 program functional image 或执行发射 stage；但 rotating 板在该间隔内缺少可验证 shutdown marker，所以必须作为历史安全证据缺口保留，不能改写成 PASS。

## 仍无法排除的原因

1. fixed F1 emitter、rotating R1 receiver 或其小板已经发生损伤；没有外部光功率/电流测试，状态未知。
2. F1→R1 光路、模块位置、接触或局部供电不稳定；本轮禁止移动、换板和重接线，尚未隔离。
3. VCC1/VCC2 实际电压、极性、纹波、上电顺序和温度未被记录。小板原理图显示 VCC2 经 0 ohm 直连、VCC1 经 47 ohm；实际供电值必须外测。
4. AX7020/TFDU 部分上电和 FPGA unconfigured interval 没有外部 Txd/SD 测量。普通配置期间 PUDC_B 内部 pull-up 预计使 Txd、SD 同时为高，数据手册 truth table 表明 SD 抑制发射；但无离散 Txd pull-down/SD pull-up，partial-power fail-safe 仍是 `PENDING_D17`。
5. 包脚波形与内部 telemetry 不一致、器件内部异常或 ESD 等板外故障。

## 因果判断表

| 假设 | 当前判断 | 理由 |
|---|---|---|
| 代码让 Txd 长时间连续高并烧毁器件 | `NOT_SUPPORTED_BY_RECORDED_DIGITAL_EVIDENCE` | 最大记录 250 ns；最大 rolling duty 17.975%；无 sticky safety fault。 |
| fixed F1 发射器已经损坏 | `POSSIBLE_NOT_PROVEN` | F1→R1 失败与此兼容，但 fixed 本地 Rxd 事件和无外部光功率测量不能确认。 |
| rotating R1 接收器或 F1→R1 路径异常 | `POSSIBLE_NOT_PROVEN` | rotating R1 未见 raw pulse；反向 R1→F1 通过不验证 R1 receiver。 |
| 5-cycle raw diagnostic 太短造成假阴性 | `CREDIBLE_DIAGNOSTIC_DEFECT` | 78.125 ns 低于数据手册表征下限和 125 ns 标称脉冲。 |
| 供电、部分上电、接触、温度或 ESD 原因 | `UNRESOLVED` | 缺少直接电气/温度/光学证据。 |

## 安全的下一步

在以下人工检查完成前，保持 `HARDWARE_HOLD`，不再执行任何 TFDU 发射：

1. 断电检查四个模块和两块板是否有异常温升痕迹、变色、裂纹、气味、反接或短路；不要带电移动或重插。
2. 由用户使用限流电源/万用表确认四个模块的 VCC1、VCC2、GND、极性和静态电流；记录真实数值，不能用配置默认值代替。
3. 使用示波器在 shutdown image 下直接测量 F0/F1/R0/R1 的 Txd 与 SD，并覆盖 program transition；确认 SD=HIGH、Txd=LOW，以及 functional pulse 宽度、rolling duty 和退出 shutdown 后至少 500 us 的等待。
4. 使用光电探头或已校准接收器分别验证 fixed F1 emitter 与 rotating R1 receiver；内部 `raw`/LED 不能作为外部光功率证据。
5. 完成人工安全检查并明确确认硬件状况后，才可创建新的 current-run authorization；应先修复 5-cycle raw pulse、冻结新 SHA256，并从最低占空比、单脉冲、单方向开始。

本审计本身不构成新的硬件授权，也不构成 component PASS、P10.1R PASS 或产品验收。
