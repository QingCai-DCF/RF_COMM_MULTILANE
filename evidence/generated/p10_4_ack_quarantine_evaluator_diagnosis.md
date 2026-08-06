# P10.4 ACK 邻道隔离评估器误判诊断

## 结论

运行 `p10_4_20260805T215824Z_6ff17d33_94506af9_2b2b37d4` 的硬件证据保持为不可变 `PARTIAL`，不追溯提升为 PASS。它在 `echo_crosstalk_8x8` 停止的唯一原因，是继承的 P10.3 主机评估器把 P10.4 明确定义的 J11 邻道 ACK 隔离计数误判为“其他 lane 被关闭”。

这不是 CRC、安全或非目标帧准入失败。该 run 的 `crc_bad`、`cross_lane_accepted_data`、`same_module_accepted_data`、占空比故障、连续高电平故障、SHA mismatch、超时和资源泄漏计数均为 0；102 条 shutdown 记录全部 PASS，两端最终 shutdown 均为 PASS。

## 直接证据

四条被拒绝的记录全部来自 `R2 -> F2` 的 command-13 帧窗口。此时 fixed 端在 lane2 发送物理 ACK；冻结的 P10.4 PHY 按 J11 的 lane2/lane3 配对，对 lane3 执行 ACK-only 接收隔离。四条记录的 fixed lane3 `blanked_raw` 分别为 1、1、1、4，而 lane3 的 `accepted_remote=0`、`crc_bad=0`，两端 `non_target_accepted=0`、`cross_lane_accepted=0`。

原始 stage summary：`evidence/hardware/p10_4/p10_4_20260805T215824Z_6ff17d33_94506af9_2b2b37d4/stages/echo_crosstalk_8x8/stage_summary.json`，SHA256 `1f0742826ebd1f455ef5058c95a750a94a1b6a51ca797a8a8c662fa7e67ba38d`。

## 修正规则

评估器只在 `echo_crosstalk_8x8` 的 one-hot、非 recovery、command-13 帧向量中，允许接收端 ACK 发射 lane 的同连接器配对 lane（`source_lane ^ 1`）出现 `blanked_raw`。同时新增显式审计并保存这些预期观察。

以下条件仍一律失败：

- command-2 RAW 向量出现任何非源 lane 隔离；
- sender 端配对 lane 被隔离；
- 接收端除源 lane 和同连接器配对 lane以外的 lane 被隔离；
- multi-lane 或 recovery 向量试图使用该例外；
- 任意 CRC bad、非目标/跨 lane 有效帧准入或安全计数非零。

归档 stage 用修正后的评估器只读重放为 PASS，观察到 4 条、合计 7 个预期配对 ACK 隔离计数。该重放仅验证评估器语义；必须使用新的 current-run authorization 完整重跑 P10.4，旧 `PARTIAL` 证据不继承为新 run 的硬件 PASS。
