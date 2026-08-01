# P10.1R 串扰阶段失败诊断

状态：`FAIL_PRESERVED_REMEDIATION_REQUIRED`

当前 run `p10_1r_20260801T221620Z_60581a20_ac128032_4b8f569c` 已原样保留。`preflight` 与四模块 1000 次 `echo_tail` 通过；`crosstalk` 失败，后续阶段未运行。失败和正常退出路径均完成双板 shutdown。

直接证据表明，lane0/1 在两个方向均各接收 4248 个正确 DATA 帧和 136 个 ACK 帧。lane1 的 `cross_lane_accepted` 恰好为 136，而 DATA 全部落在所选物理 lane；lane0 对应计数为零。

根因是 ACK 解码固定输出 lane ID 0，而 cross-lane 计数器同时检查 DATA 与 ACK。因此，每个合法 lane1 ACK 都被误记为 cross-lane acceptance。修复将在 ACK header byte 11 的既有保留 bit 1 中编码逻辑 lane，不增加字节或 airtime，并在接收端解码。

`local_source_rejected_frame_count=0` 并非抑制失效：四个方向分别记录了 4,454,233、4,455,316、4,450,433、4,454,173 个 sender-side blanked raw pulses，且 same-module accepted DATA 为零。per-module quarantine 在 frame decode 前已阻断回波。Goal 第 20 节允许 local-source reject 计数大于零，但并未要求它必须大于零；后续 runner 将继续强制硬件配置 readback 证明该 defense-in-depth 过滤已启用。

权威机器可读内容见相邻 JSON；现有失败 evidence 不会改写为 PASS。
