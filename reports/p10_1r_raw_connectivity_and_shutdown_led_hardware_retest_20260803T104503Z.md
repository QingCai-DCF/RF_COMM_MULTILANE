# P10.1R raw 连通性与 shutdown LED 复测审计

## 结论

本次受限 `echo_tail` 硬件运行通过。四个物理方向均收到 1000/1000 个 raw 脉冲观测，总计 4000/4000：

| 物理方向 | 结果 | 接收计数 |
|---|---:|---:|
| F0 → R0 | PASS | 1000/1000 |
| R0 → F0 | PASS | 1000/1000 |
| F1 → R1 | PASS | 1000/1000 |
| R1 → F1 | PASS | 1000/1000 |

证据等级严格限定为 `RAW_PHYSICAL_ONLY`。该结果证明本次脉冲级四方向物理连通，不证明有效帧、CRC、应用吞吐、streaming、串扰或完整 P10.1R 验收。

## 本次修复后的 raw 脉冲

- PL 时钟：64 MHz。
- 最终物理 Txd 离线断言宽度：8 clocks，即 125 ns。
- 请求间隔：1024 clocks。
- 请求占空比：8/1024 = 0.78125%。
- raw 请求仍经过原有 arm、单一 `GLOBAL_PERMIT`、TX kill、one-hot、连续高电平、stuck-high 与精确滑动占空比保护链。

本次硬件统计证明四个方向均接收到 raw 活动；125 ns 的精确脉宽由 exact-source XSIM 的最终物理 Txd 断言证明，并非外部示波器测量。

## 板卡与 artifact 绑定

- fixed：AX7020-F，JTAG `210249855178`。
- rotating-role：AX7020-R，JTAG `210512180081`。
- artifact source commit：`39df17155ce82e38366fbdac00c79584f0fe1afa`。
- fixed functional bitstream：`565337987c949bb65b57a088eb1038144714b867d8ebf6d5115e7346b11d44ea`。
- rotating functional bitstream：`df0c60f6e3826c358fd2ca562ee4807b28a935c354bda535e98c59313e6471b0`。
- fixed shutdown bitstream：`0d0f4fbf2b35518094aec58728461f505c225a5f1aef647d3917259564fc279a`。
- rotating shutdown bitstream：`a0abfef77d566a6baaf51242d95cae679e63cb9e34f423595f3faae7bcfbac27`。

用户在本次运行前自行更换 fixed 侧 F1 TFDU 小板；未提供模块序列号，因此未猜测其身份。Codex 在运行期间没有移动、交换或重接任何板卡/模块。

## Shutdown 与四个 PL LED

shutdown top 已将四个低有效 LED 输出固定为 `pl_activity_led_n_o=4'b1111`。离线 XSIM、独立 fixed/rotating implementation 与构建 marker 均通过；本次运行实际加载了上述两个内容寻址 shutdown bitstream。

初始、stage-before、stage-after、final 以及 finally-emergency 共 5 次双板 shutdown 均为 PASS，且每次均记录：

- `SHUTDOWN_FIXED=PASS`
- `SHUTDOWN_ROTATING=PASS`
- `TFDU_SHUTDOWN_PROGRAMMED=1`
- `SHUTDOWN_EXIT=0`

这证明全灭设计意图已构建并将对应 bitstream 成功配置到两块 FPGA。Codex 没有摄像头或 LED 引脚外部测量通道，因此“板上四灯肉眼确实熄灭”仍需用户直接观察确认；在该观察完成前，不把配置/编程证据误写成物理 LED 测量 PASS。

## 安全边界

- 仅运行 `echo_tail`；未运行 framed objects、performance、streaming 或 crosstalk。
- 未使用 Ethernet。
- lane mask 未超过 `0x3`。
- 未移动、旋转、调角、遮挡、交换模块或重接线。
- 运行结束后两块板均处于已验证 shutdown 状态。

## 证据

- `evidence/generated/p10_1r_echo_tail.json`
- `evidence/generated/p10_1r_shutdown.json`
- `evidence/hardware/p10_1r/p10_1r_20260803T103315Z_39df1715_56533798_df0c60f6/final/orchestrator_result.json`
- `evidence/hardware/p10_1r/p10_1r_20260803T103315Z_39df1715_56533798_df0c60f6/final/run_evidence_sha256_manifest.json`

