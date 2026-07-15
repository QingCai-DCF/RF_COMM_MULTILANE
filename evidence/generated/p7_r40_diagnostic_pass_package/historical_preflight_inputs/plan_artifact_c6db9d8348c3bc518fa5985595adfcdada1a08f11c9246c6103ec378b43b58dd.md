# P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET

> 将本文件原样交给 Codex 执行。本阶段是在 P6 已通过的静止双 lane 本地传输基线上，增加任意长度消息/文件的分片、重组、双 lane 调度、恢复和可量化性能证据。
> **本版时长调整：P7 最终连续硬件运行总时长限定为 30 分钟（1800 秒）；前 5 分钟作为嵌入式 calibration，后 25 分钟作为正式验收，不再额外执行独立 30 分钟 calibration 或 2 小时 soak。**

---

## 0. 项目与基线

```text
PROJECT: RF_COMM_MULTILANE
REPO: C:\Users\user\Documents\RF_COMM_MULTILANE
BASELINE_STAGE: P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET
BASELINE_RESULT: PASS
BASELINE_COMMIT: 5b90d41a6750aad8023071433996fee3f068efe2
P6_RESULT_PACKAGE: rf_comm_multilane_p6_results_20260710_091555.zip
NEXT_STAGE: P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET
```

P6 已提供以下可复用基线：

- 静止、2 lane 本地硬件链路通过；
- lane0、lane1、lane mask `0x3` 动态 payload 通过；
- 单帧 payload 上限 `247` bytes 已通过；硬件矩阵覆盖离散长度 `1,2,3,4,7,8,15,16,31,32,63,64,127,128,191,247`，并非逐一覆盖全部 `1..247` 长度；
- JTAG/AXI payload RAM 通过；
- PS runtime mailbox 通过；
- host/JTAG 文件往返通过，当前真实硬件文件为 `30` bytes 和三种 `247` bytes payload；
- lane mask 回归通过；
- P6 历史证据中的 2 小时 stationary soak 已通过：约 `7200.019 s`，`312024` 次 TX，lane0/lane1 `rx_good` 均为 `312024`，已汇总错误计数为 0；该历史时长不作为 P7 的运行要求；
- shutdown-before / shutdown-after 通过；
- Ethernet、旋转和 8 lane 仍未验收。

P6 尚未关闭的、且可在当前条件下自动化推进的主要缺口：

- 单次应用对象仍受单帧 `247` bytes 限制，尚无跨帧分片/重组；
- 尚无大于 `247` bytes 的真实硬件文件/对象往返；
- P6 汇总中的 `payload_bytes_total`、`effective_payload_bps` 和 `goodput_bps` 仍为 0；
- fragment/object latency 尚未暴露；
- application queue、backpressure、abort/restart、duplicate/replay 和 object-level integrity 尚未验收；
- P6 的 lane fallback 主要是调度/配置级回归，还不是完整对象级恢复。

P7 不得覆盖、重写或把 P6 evidence 重新解释为 P7 evidence。所有 P7 文件放入独立目录。

---

## 1. 当前条件与用户授权

```text
USER_CONFIRMED_SUPPLY_OK: true
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
ROTATION_ALLOWED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3
MANUAL_INSTRUMENTATION_REQUIRED: false
USER_HARDWARE_AUTHORIZATION_FOR_P7: GRANTED
ALLOW_CODEX_AUTOMATED_HARDWARE_EXECUTION: true
P7_MAX_CONTINUOUS_SOAK_RUNTIME_SEC: 1800
```

本文件明确记录用户在“条件不变”的前提下延续硬件操作授权。Codex 在 **P7 范围内** 可以自动执行下列硬件操作，不需要再次请求人工确认：

1. 连接 Vivado Hardware Manager、hw_server、XSDB、JTAG 和 AXI/JTAG-to-AXI；
2. 在每个阶段开始前 program 已冻结 SHA256 的 shutdown bitstream；
3. program P6 已知良好 immutable bitstream，或经 P7 gate 生成并冻结的新 candidate；
4. 下载并运行经哈希冻结的 PS ELF；
5. 通过 JTAG/AXI、XSDB、PS mailbox 或本地文件 backend 读写寄存器、payload RAM、PS memory 和 mailbox；
6. 拉低 TFDU6102 `SD` 进入接收工作状态，并等待不少于 `500 us`；
7. 在现有安全保护下驱动 TFDU6102 `Txd`，执行 lane0、lane1 和双 lane 静止传输；
8. 自动执行 bounded functional tests、large-object tests、恢复测试和最长 `1800 s` stationary soak；
9. 自动采集 ILA/VIO、寄存器、计数器、日志、输入/输出文件和 SHA256；
10. 任何失败、异常、超时、脚本退出或 Ctrl+C 后，自动 program shutdown bitstream 并记录 shutdown 结果；
11. 自动重试可恢复的软件/JTAG连接问题，但重试次数必须有限并记录；
12. 若 JTAG、Vivado、XSDB、候选 artifact 或安全前置条件不可用，自动标记 `BLOCKED` 并安全退出，不得要求用户移动硬件或插网线。

授权只覆盖本文件中的 P7 项目。不得扩展为以下操作：

- 不得使用 Ethernet、DHCP、TCP/UDP board link 或要求插网线；
- 不得移动、旋转、调角度、遮挡或重新摆放硬件；
- 不得使用 lane mask `> 0x3`；
- 不得声明 4 lane、8 lane、旋转或 Ethernet 通过；
- 不得绕过 `Txd` stuck-high guard、duty guard、startup wait 或 shutdown-on-exit；
- 不得把内部寄存器/ILA 证据描述为外部示波器证据；
- 不得把 P7 写成产品最终验收。

Codex 应把本节复制到：

```text
.hardware_authorization/P7_STATIONARY_APP_LAYER_APPROVED.txt
```

授权记录必须包含本计划 SHA256、当前 commit、bitstream/ELF/profile SHA256、允许的 lane mask、最长运行时间和禁止项。

---

## 2. P7 总目标

在不使用网线、不移动硬件、只使用 2 lane 的条件下，把 P6 的“单个 1..247-byte frame transport”提升为可供未来 Ethernet/TCP 直接复用的 **应用层对象传输**：

```text
host file / generated object
        ↓
transport-neutral host API
        ↓
JTAG/AXI backend 或 PS mailbox backend
        ↓
P7 application segmentation
        ↓
P6 verified frame transport, payload <= 247 bytes
        ↓
lane scheduler: lane0 / lane1 / stripe / replicate
        ↓
P7 reassembly + whole-object integrity
        ↓
output file + metrics + evidence
```

P7 必须完成：

- 任意长度对象分片与重组；
- whole-object CRC32 和 host SHA256 校验；
- object ID、fragment index、fragment count 和 total length；
- 重复片段、缺失片段、乱序片段和错误元数据处理；
- lane0-only、lane1-only、双 lane round-robin striping 和 `0x3` replication；
- 软件可控的 lane unavailable/fallback 回归；
- PS runtime 长对象传输；
- host 文件大于 247 bytes 的真实硬件往返；
- bytes、goodput、latency、lane utilization 和 queue/backpressure 指标；
- 单次总时长 30 分钟的 stationary application-layer calibration + soak。

---

## 3. P7 非目标

本阶段不得把以下内容纳入 PASS 判据：

```text
Ethernet cable communication
DHCP
TCP reconnect over a physical cable
rotation
600 rpm
optical alignment sweep
4-lane or 8-lane hardware
product-final acceptance
external scope validation
```

可以为未来 TCP backend 定义接口和编译 stub，但不得打开真实网络连接。

---

## 4. 强制架构原则

### 4.1 保持 P6 物理/帧层稳定

优先把 P7 实现在公共 C/Python application layer 和 PS runtime 中，不要为了文件分片把任意长度对象逻辑塞入 TFDU PHY 或 4PPM RTL。

P6 PL 继续负责：

- 单个 `1..247` byte payload；
- frame header/CRC；
- ACK/retry；
- lane mask；
- TFDU safety；
- RX payload readback。

P7 负责：

- object/message abstraction；
- segmentation/reassembly；
- multi-frame scheduling；
- end-to-end integrity；
- duplicate/replay handling；
- lane scheduling policy；
- application metrics；
- restart/recovery policy。

### 4.2 优先复用已知良好 bitstream

若 P7 不需要修改 PL：

- 复用 P6 immutable JTAG/AXI candidate；
- 复用 P6 immutable PS runtime candidate；
- 重新验证文件 SHA256；
- 不进行无意义 rebuild；
- 在 evidence 中明确 `PL_REUSED_FROM_P6: true`。

P6 JTAG candidate 参考 SHA256：

```text
0648321a71f0052e23b02096be314de7b36f8ef8a8c566ff4db385e6222ef46d
```

P6 PS candidate 参考 SHA256：

```text
4bdb0aaeb75c6dcf9837a06cda6b7f445063dd65bf07756162b5ea8fbf537cd5
```

Codex 必须以仓库实际 immutable artifact 重新计算哈希，不得只信本计划中的文本。

若确实需要修改 PL：

- 新建 P7 candidate；
- 运行 synthesis、implementation、timing 和 DRC；
- 冻结 bitstream/LTX/XSA SHA256；
- 重新跑 P6 lane0/lane1/two-lane regression；
- P6 回归未通过则 P7 不得继续硬件测试。

---

## 5. Application Protocol v1

新增规范文件：

```text
config/p7_app_protocol.yaml
docs/P7_APPLICATION_PROTOCOL.md
```

定义固定 32-byte application header，全部使用 little-endian：

| Offset | Size | Field | 说明 |
|---:|---:|---|---|
| 0 | 4 | magic | ASCII `RFAP` |
| 4 | 1 | version | `1` |
| 5 | 1 | flags | FIRST/LAST/RETRANSMIT/CONTROL |
| 6 | 2 | header_len | 固定 `32` |
| 8 | 4 | session_epoch | 本次 application session epoch |
| 12 | 4 | object_id | 每个对象唯一 ID |
| 16 | 4 | total_length | 完整对象长度 |
| 20 | 2 | fragment_index | 从 0 开始 |
| 22 | 2 | fragment_count | 总片段数 |
| 24 | 2 | chunk_length | 当前片段数据长度 |
| 26 | 2 | reserved | 必须为 0 |
| 28 | 4 | object_crc32 | 完整对象 CRC32 |

约束：

```text
P6_MAX_PAYLOAD_BYTES = 247
P7_HEADER_BYTES = 32
P7_MAX_CHUNK_BYTES = 215
fragment_count = ceil(total_length / 215)
```

空对象由一个 `chunk_length=0`、FIRST+LAST 的 header-only fragment 表示；不得尝试向 P6 提交 0-byte payload，因为实际 P6 payload 仍包含 32-byte application header。

每个 fragment 仍受 P6 frame CRC 和 P6 payload CRC32 保护；P7 的 `object_crc32` 用于完整对象端到端验证。Host 输入/输出另外使用 SHA256 比较。

必须实现编码/解码的跨语言 golden vectors：

```text
software/common/rf_app_protocol.h
software/common/rf_app_protocol.c
tools/p7_app_protocol.py
tests/vectors/p7_app_protocol_vectors.json
```

C 与 Python 对同一 header、fragment 和 CRC 的结果必须逐字节一致。

---

## 6. Application 状态机

实现发送状态：

```text
IDLE
OBJECT_OPEN
FRAGMENT_BUILD
FRAGMENT_SUBMIT
WAIT_P6_RESULT
FRAGMENT_ACCEPTED
FRAGMENT_RETRY_OR_FALLBACK
OBJECT_COMPLETE
OBJECT_FAILED
ABORT_AND_SHUTDOWN
```

实现接收/重组状态：

```text
EMPTY
ASSEMBLING
COMPLETE
REJECTED
ABORTED
```

必须处理：

- FIRST/LAST 合法性；
- `fragment_index < fragment_count`；
- `chunk_length <= 215`；
- `total_length` 与片段累计长度一致；
- 同一 object 的 session_epoch、object_id、fragment_count、total_length 和 CRC 一致；
- duplicate fragment 数据相同则幂等接受并计数；
- duplicate fragment 数据不同则拒绝；
- 乱序片段可缓存或明确 bounded reject；
- 缺失片段不得产出完整对象；
- 完整对象 CRC 错误不得写出 PASS 文件；
- abort 后 partial output 必须删除或标记 `.partial`；
- 新 session epoch 必须清理旧的 partial state。

推荐 P7 v1 使用严格顺序提交，允许重复，但不要求无限乱序缓存。若选择 bounded out-of-order，最大缓存窗口必须写入配置并受上限约束。

---

## 7. 传输抽象

新增统一 backend 接口：

```text
software/common/rf_transport_backend.h
software/common/rf_transport_backend.c
```

至少支持：

1. `local_stub`：CI/offline reference；
2. `jtag_axi`：当前 host 直接访问 P6 寄存器；
3. `ps_mailbox`：host 将对象/命令放入 PS memory，由 PS runtime 分片发送；
4. `tcp_stub_disabled`：只编译接口，不连接网络，不作为硬件 PASS 证据。

接口至少包含：

```text
open
get_capabilities
submit_fragment
poll_fragment_result
read_fragment
abort
close
get_metrics
```

禁止 application protocol 直接依赖 XSDB 命令文本。XSDB/JTAG 细节必须留在 backend 内部。

---

## 8. PS Runtime Service

基于 P6 driver 新增：

```text
software/ps_driver/p7_app_service.c
software/ps_driver/p7_app_service.h
software/ps_driver/p7_runtime_main.c
```

要求：

- 使用 P6 driver API，不复制寄存器常量；
- 接收 object descriptor；
- 从 PS memory 读取完整输入对象；
- 分片为最大 215-byte chunks；
- 顺序提交到 P6；
- 读取 P6 RX payload；
- 重组到独立输出 buffer；
- 计算 full-object CRC32；
- 记录每 fragment lane、start/end timestamp 和结果；
- 维护 bounded descriptor queue；
- 提供 STOP、ABORT、CLEAR 和 SHUTDOWN 命令；
- 所有失败路径最终调用 `ir_driver_shutdown()`；
- 禁止动态内存无限增长；
- 最大 object size 必须配置并有硬上限。

建议初始上限：

```text
P7_MAX_OBJECT_BYTES = 8 MiB
P7_DESCRIPTOR_QUEUE_DEPTH = 8
P7_OUT_OF_ORDER_WINDOW = 0 or bounded <= 8
```

若受 PS memory/链接脚本限制，可把硬件测试上限调低，但不得低于 `1 MiB`；调整必须在 summary 中说明原因。

### 8.1 PS mailbox descriptor

定义版本化 descriptor，至少包含：

```text
command
version
session_epoch
object_id
input_address
output_address
object_length
expected_crc32
lane_policy
max_retries
status
error_code
bytes_completed
fragments_completed
```

所有地址、长度和 alignment 必须校验，越界立即拒绝且不启动 TFDU TX。

---

## 9. 双 lane 调度策略

实现并验证四种策略：

### 9.1 LANE0_ONLY

```text
fragment lane mask = 0x1
ACK mask = 0x1
```

### 9.2 LANE1_ONLY

```text
fragment lane mask = 0x2
ACK mask = 0x2
```

### 9.3 STRIPE_ROUND_ROBIN

```text
fragment 0 -> 0x1
fragment 1 -> 0x2
fragment 2 -> 0x1
fragment 3 -> 0x2
...
```

验收时 lane0/lane1 fragment count 差值不得大于 1，除非发生已记录 fallback。

### 9.4 REPLICATE_0X3

```text
fragment lane mask = 0x3
ACK mask = 0x3
```

此模式是可靠性/现有 P6 双 lane 基线，不应被错误描述为带宽 striping。

### 9.5 自动 fallback

在 application scheduler 中实现：

- 当前 lane 返回 bounded failure 时，同一 fragment 可在另一 lane 重试；
- object ID、fragment index 和 payload 必须保持不变；
- fallback 次数有上限；
- fallback 后记录 lane health；
- 双 lane 都失败时停止对象并 shutdown；
- 不允许在未经检查的 lane mask 上发送。

本阶段不能通过移动或遮挡硬件制造光学失败。使用 test-only scheduler fault injection：

```text
P7_INJECT_LANE_UNAVAILABLE = none | lane0 | lane1 | after_n_fragments
```

该注入必须在提交到 P6 之前拦截，不得生成 `lane mask > 0x3`，不得破坏 TFDU safety。证据必须标注为 `SOFTWARE_INJECTED_SCHEDULER_FAULT`，不得称为真实光路故障。

---

## 10. 指标与寄存器/日志

P6 metrics 中 `payload_bytes_total`、goodput 和 latency 尚未形成有效值。P7 必须补齐 application metrics。

至少记录：

```text
objects_requested
objects_completed
objects_failed
fragments_generated
fragments_submitted
fragments_completed
fragments_retried
fragments_duplicated
fragments_rejected
fragments_out_of_order
bytes_requested
bytes_completed
whole_object_crc_failures
sha256_mismatches
lane0_fragments
lane1_fragments
replicated_fragments
fallback_lane0_to_lane1
fallback_lane1_to_lane0
queue_high_watermark
backpressure_events
host_to_ps_bytes_per_sec
application_goodput_bps
fragment_latency_min_us
fragment_latency_mean_us
fragment_latency_p50_us
fragment_latency_p95_us
fragment_latency_p99_us
fragment_latency_max_us
object_latency_min_ms
object_latency_mean_ms
object_latency_p95_ms
object_latency_max_ms
p6_retry_count
p6_retry_exhausted
p6_tx_fail
p6_crc_bad
p6_payload_mismatch
max_txd_high_cycles
duty_violation_count
shutdown_result
```

时间戳来源必须写明：

- host monotonic clock；
- PS global timer；
- 或二者分别统计。

不得把 JTAG host 开销和实际 optical frame latency 混成一个未标注指标。

---

## 11. 离线实现与测试任务

### P7-01 仓库 intake

1. 验证当前 commit 为 P6 PASS 基线或其干净后继；
2. 读取 P6 summary、protocol metrics、failure packages；
3. 确认 `git status --short`；
4. 创建 P7 分支或记录当前 branch；
5. 生成：

```text
evidence/generated/p7_repo_intake_summary.md
```

必须把以下已修复问题固化为回归项：

- ACK turnaround guard；
- final RX word tail padding masking；
- XSDB 无 DAP alias 时使用 APU target；
- shutdown bitstream before/after；
- immutable artifact SHA verification。

### P7-02 协议规范与 golden vectors

- 实现 C/Python 编解码；
- 生成至少 1000 个 deterministic vectors；
- 覆盖所有边界和非法字段；
- C/Python byte-for-byte 一致；
- 输出：

```text
evidence/generated/p7_protocol_vector_summary.md
```

### P7-03 分片/重组单元测试

正向用例至少覆盖 object size：

```text
0
1
2
30
214
215
216
246
247
248
430
431
432
1024
4096
65536
1048576
```

payload pattern 至少覆盖：

```text
all_zero
all_ff
0xaa
0x55
counter
all_byte_values
prbs7
prbs15
deterministic_random
utf8_text
binary_with_nul
```

负向用例至少覆盖：

- wrong magic/version/header length；
- chunk length `>215`；
- fragment index 越界；
- fragment count 不一致；
- total length 不一致；
- object CRC 错；
- duplicate same data；
- duplicate different data；
- missing fragment；
- out-of-order beyond configured window；
- stale session epoch；
- object ID collision；
- queue overflow；
- address/length overflow；
- lane policy invalid；
- lane mask `>0x3`。

输出：

```text
evidence/generated/p7_segmentation_reassembly_summary.md
```

### P7-04 transport backend tests

对 `local_stub`、mock JTAG 和 mock PS mailbox 运行相同 conformance suite。TCP stub 只能编译，不允许 connect/bind/listen。

输出：

```text
evidence/generated/p7_backend_conformance_summary.md
```

### P7-05 PS runtime build

- 使用 P6 rebuilt XSA；
- 使用 Vitis 2023.1 toolchain；
- 生成真实 ELF，不接受 syntax-only 作为 PASS；
- 校验 map 文件、memory usage、stack/heap；
- 输出 immutable ELF SHA256；
- 输出：

```text
evidence/generated/p7_ps_runtime_build_summary.md
```

### P7-06 no-Ethernet/no-motion/2-lane gate

静态扫描和运行时 guard 必须确认：

```text
Ethernet use = false
socket connect = false
DHCP = false
motion/rotation = false
lane mask <= 0x3
```

输出：

```text
evidence/generated/p7_no_ethernet_summary.md
evidence/generated/p7_no_motion_summary.md
evidence/generated/p7_2lane_scope_summary.md
```

---

## 12. 硬件执行前 gate

Codex 在第一次 P7 硬件动作前必须全部满足：

```text
P6_RECHECK: PASS
P7_PROTOCOL_VECTORS: PASS
P7_SEGMENTATION_REASSEMBLY: PASS
P7_BACKEND_CONFORMANCE: PASS
P7_PS_RUNTIME_BUILD: PASS
P7_NO_ETHERNET: PASS
P7_NO_MOTION: PASS
P7_2LANE_SCOPE: PASS
P7_AUTHORIZATION: PASS
BITSTREAM_SHA256_VALID: true
ELF_SHA256_VALID: true
SHUTDOWN_BITSTREAM_SHA256_VALID: true
ABORT_FILE_PRESENT: false
```

缺少工具必须是 `SKIP_WITH_REASON`，但核心 C/Python tests、artifact hash、安全 gate 和 shutdown wrapper 不允许 SKIP。

---

## 13. 自动化硬件阶段

每个阶段必须使用统一 safe wrapper：

```text
program shutdown bitstream
verify shutdown programming
verify immutable candidate hash
program candidate
run bounded stage
collect counters/files/logs
issue stop
issue P6/P7 shutdown command
program shutdown bitstream
verify SHUTDOWN_EXIT=0
package evidence
```

任何阶段 FAIL 后默认停止后续发射阶段，除非失败是已定义且安全的负向测试结果。

### P7-HW-01 Safe-idle 快速回归

目的：确认当前硬件仍处于 P6 已知状态，不重复完整 PHY bring-up。

检查：

- `Txd` request idle；
- `SD` shutdown state；
- safety counters 清零；
- shutdown-before 和 shutdown-after；
- 不发送 application fragment。

输出：

```text
evidence/hardware/p7/safe_idle_recheck/
evidence/generated/p7_safe_idle_recheck_summary.md
```

### P7-HW-02 P6 one-frame 回归

在 lane mask `0x1`、`0x2`、`0x3` 各发至少 10 个已知 payload，确认 P7 软件没有破坏 P6。

验收：

```text
crc_bad = 0
payload_mismatch = 0
retry_exhausted = 0
tx_fail = 0
duty_violation = 0
max_txd_high_cycles <= known-good P6 value
```

输出：

```text
evidence/hardware/p7/p6_frame_regression/
evidence/generated/p7_p6_frame_regression_summary.md
```

### P7-HW-03 Fragment boundary matrix

对每种 lane policy 运行边界 object sizes：

```text
0, 1, 30, 214, 215, 216, 247, 248, 430, 431, 432, 1024
```

lane policy：

```text
LANE0_ONLY
LANE1_ONLY
STRIPE_ROUND_ROBIN
REPLICATE_0X3
```

每个输出对象必须与输入对象 SHA256 一致。

输出：

```text
evidence/hardware/p7/fragment_boundary_matrix/
evidence/generated/p7_fragment_boundary_matrix_summary.md
```

### P7-HW-04 Large object JTAG/AXI round-trip

文件大小：

```text
4096 bytes
65536 bytes
1048576 bytes
```

模式：

```text
counter
prbs15
deterministic_random
binary_all_byte_values_repeated
```

至少完成：

- 1 MiB lane0-only；
- 1 MiB lane1-only；
- 1 MiB stripe；
- 1 MiB replicate；
- 64 KiB × 所有 pattern × stripe。

要求：

- 输入/输出 byte-for-byte 相同；
- CRC32 相同；
- SHA256 相同；
- P6 positive counters 无错误；
- 输出真实 bytes/goodput/latency。

输出：

```text
evidence/hardware/p7/large_object_jtag/
evidence/generated/p7_large_object_jtag_summary.md
```

### P7-HW-05 PS application service runtime

通过 XSDB：

1. program PS candidate；
2. 下载 P7 ELF；
3. 写入 object descriptor 和输入对象到 PS memory；
4. 启动 PS service；
5. 等待 object complete；
6. 读回输出对象和 metrics；
7. 验证 SHA256；
8. shutdown。

至少运行：

```text
30 bytes lane0
247 bytes lane1
4096 bytes stripe
65536 bytes stripe
1048576 bytes stripe
1048576 bytes replicate
```

输出：

```text
evidence/hardware/p7/ps_app_runtime/
evidence/generated/p7_ps_app_runtime_summary.md
```

### P7-HW-06 Lane scheduler 与 fallback

正向验证：

- stripe fragment distribution；
- lane0/lane1 计数差值；
- replicate 标记；
- lane health counters。

软件注入验证：

1. lane0 unavailable，从 fragment N 开始转 lane1；
2. lane1 unavailable，从 fragment N 开始转 lane0；
3. preferred lane unavailable from start；
4. both unavailable，应 bounded fail，且不得启动后续 TX；
5. fallback 上限触发后 shutdown。

每个正向 fallback case 使用至少 64 KiB 对象并验证最终 SHA256。

输出：

```text
evidence/hardware/p7/lane_scheduler_fallback/
evidence/generated/p7_lane_scheduler_fallback_summary.md
```

证据必须明确：这是软件 scheduler fault injection，不是移动硬件造成的真实 optical fault。

### P7-HW-07 Abort/restart/atomicity

自动执行：

1. 开始传输 1 MiB 对象；
2. 在 deterministic fragment index 触发软件 abort；
3. stop + shutdown；
4. 验证没有完成文件被误标记为 PASS；
5. 重新 program candidate/ELF；
6. 使用新 session epoch 重传；
7. 验证最终对象 SHA256；
8. 重放同一已完成 object ID，验证 duplicate policy。

不得通过断电或移动硬件触发。

输出：

```text
evidence/hardware/p7/abort_restart_atomicity/
evidence/generated/p7_abort_restart_atomicity_summary.md
```

### P7-HW-08 Queue/backpressure

使用 PS mailbox 一次提交多个对象：

- queue depth `1`；
- queue depth 最大合法值；
- 超过 queue capacity；
- producer 快于 consumer；
- STOP/ABORT while queued。

正向对象必须按定义顺序完成；overflow 必须 bounded reject，不得破坏已有对象。

输出：

```text
evidence/hardware/p7/queue_backpressure/
evidence/generated/p7_queue_backpressure_summary.md
```

### P7-HW-09 嵌入式 5 分钟 calibration window

不再单独运行额外的 30 分钟 calibration。最终 30 分钟 stationary run 的前 `300 s` 作为 warm-up/calibration window，用于建立本次运行的 application goodput、latency 和 lane-utilization baseline。

约束：

```text
calibration_window_sec = 300
calibration_is_part_of_final_30min_run = true
additional_calibration_runtime_sec = 0
```

记录：

- completed bytes；
- object count；
- fragment count；
- latency percentiles；
- lane utilization；
- queue depth；
- P6/safety counters。

输出由同一次 30 分钟运行派生：

```text
evidence/hardware/p7/soak/stationary_app_30min/calibration_window/
evidence/generated/p7_calibration_5min_embedded_summary.md
```

### P7-HW-10 30-minute stationary application soak

只运行一次连续 `30` 分钟硬件测试。前 `5` 分钟同时作为 calibration window，后 `25` 分钟作为稳定性验收窗口；不得再追加独立的 30 分钟 calibration 或 2 小时 soak。

运行：

```text
runtime_sec = 1800
calibration_window_sec = 300
acceptance_window_sec = 1500
lane_policy = STRIPE_ROUND_ROBIN
object_size = 64 KiB, cyclically mixed with 1 MiB checkpoints
payload_pattern = deterministic_random with recorded seeds
sample_interval_sec = 30
```

每个 sample 必须保存：

- cumulative objects；
- cumulative bytes；
- fragments/lane；
- retry/error/safety counters；
- queue depth；
- current/rolling goodput；
- latency summary；
- last completed object ID；
- elapsed time；
- 当前处于 calibration 或 acceptance window；
- shutdown status at exit。

30 分钟 soak 验收：

```text
runtime >= 1800 s
calibration_window_completed >= 300 s
acceptance_window_completed >= 1500 s
objects_failed = 0
whole_object_crc_failures = 0
sha256_mismatches = 0
p6_crc_bad = 0
p6_payload_mismatch = 0
p6_retry_exhausted = 0
p6_tx_fail = 0
p6_retry_count is reported and bounded; nonzero successful retries are not silently discarded
duty_violation_count = 0
no stuck-high event
both lanes used
acceptance_window_goodput_median >= 80% of calibration_window_goodput_median
shutdown_after = true
SHUTDOWN_EXIT = 0
```

输出：

```text
evidence/hardware/p7/soak/stationary_app_30min/
evidence/generated/p7_stationary_app_30min_soak_summary.md
```

---

## 14. 自动 stop conditions

任意正向硬件阶段出现以下任一条件，立即停止当前阶段并 shutdown：

```text
TXD_STUCK_HIGH_VIOLATION > 0
DUTY_WINDOW_VIOLATION > 0
Txd continuous high >= configured safe limit
startup_wait_us < 500
lane mask > 0x3
SD/Mode/Txd internal readback inconsistent with profile
P6_CRC_BAD > 0
P6_PAYLOAD_MISMATCH > 0
P6_RETRY_EXHAUSTED > 0
P6_TX_FAIL > 0
P7_WHOLE_OBJECT_CRC_FAIL > 0
P7_SHA256_MISMATCH > 0
unbounded queue growth
invalid PS memory range
abort file appears
max runtime exceeded
Vivado/XSDB/JTAG error
shutdown command failure
shutdown bitstream programming failure
```

TFDU6102 safety contract不得弱化：

- `Txd` 高有效；
- `Rxd` 低有效；
- `SD` 高有效 shutdown；
- `Mode=HIGH` 为 MIR/FIR 高速模式；
- 退出 shutdown 后等待至少 `500 us`；
- `Txd` 长高接近/超过 `80 us` 必须被保护；
- 不提高 P6 已验证的 TX pulse width；
- 不删除 duty/stuck-high counters；
- 每个硬件阶段结束后必须 shutdown。

---

## 15. P7 工具与目录

建议新增：

```text
config/p7_app_protocol.yaml
docs/P7_APPLICATION_PROTOCOL.md
docs/P7_HARDWARE_RUNBOOK.md
software/common/rf_app_protocol.c
software/common/rf_app_protocol.h
software/common/rf_transport_backend.c
software/common/rf_transport_backend.h
software/ps_driver/p7_app_service.c
software/ps_driver/p7_app_service.h
software/ps_driver/p7_runtime_main.c
tools/p7_app_protocol.py
tools/p7_app_transport.py
tools/p7_jtag_backend.py
tools/p7_ps_mailbox_backend.py
tools/p7_local_backend.py
tools/run_p7_gate.py
tools/run_p7_gate.ps1
tools/run_p7_authorized_hardware_sequence.py
tools/run_p7_authorized_hardware_sequence.ps1
tools/run_p7_large_object_matrix.py
tools/run_p7_lane_scheduler_matrix.py
tools/run_p7_stationary_soak.py
profiles/p7/*.json
tests/p7/*
evidence/generated/p7_*.md
evidence/generated/p7_*.json
evidence/generated/p7_*.csv
evidence/hardware/p7/*
evidence/simulation/p7/*
```

所有硬件脚本默认必须是 dry-run。真实执行必须同时满足：

```text
--execute-hardware
--authorization-file .hardware_authorization/P7_STATIONARY_APP_LAYER_APPROVED.txt
--max-runtime-sec <bounded value>
--shutdown-on-exit
```

---

## 16. P7 gate

统一入口：

```powershell
python tools/run_p7_gate.py --json-summary --allow-skips
powershell -NoProfile -ExecutionPolicy Bypass -File tools\run_p7_gate.ps1 -JsonSummary -AllowSkips
```

完整授权硬件入口：

```powershell
python tools/run_p7_authorized_hardware_sequence.py `
  --execute-hardware `
  --authorization-file .hardware_authorization/P7_STATIONARY_APP_LAYER_APPROVED.txt `
  --shutdown-on-exit `
  --json-summary
```

PowerShell wrapper 必须提供等价参数。

最终 gate 必须检查：

- P6 baseline 未被篡改；
- P7 协议 vectors；
- segmentation/reassembly；
- backend conformance；
- PS runtime real ELF；
- no Ethernet；
- no motion；
- 2-lane scope；
- artifact provenance；
- authorization；
- shutdown boundaries；
- boundary matrix；
- large object round-trip；
- PS application runtime；
- scheduler/fallback；
- abort/restart；
- queue/backpressure；
- embedded 5-minute calibration window；
- 30-minute stationary soak；
- metrics completeness；
- evidence consistency。

状态只允许：

```text
PASS
FAIL
SKIP_WITH_REASON
BLOCKED
```

不得把未运行或缺证据写成 PASS。

---

## 17. Evidence 清单

至少生成：

```text
evidence/generated/p7_repo_intake_summary.md
evidence/generated/p7_protocol_vector_summary.md
evidence/generated/p7_segmentation_reassembly_summary.md
evidence/generated/p7_backend_conformance_summary.md
evidence/generated/p7_ps_runtime_build_summary.md
evidence/generated/p7_no_ethernet_summary.md
evidence/generated/p7_no_motion_summary.md
evidence/generated/p7_2lane_scope_summary.md
evidence/generated/p7_artifact_provenance_summary.md
evidence/generated/p7_hardware_authorization_summary.md
evidence/generated/p7_safe_idle_recheck_summary.md
evidence/generated/p7_p6_frame_regression_summary.md
evidence/generated/p7_fragment_boundary_matrix_summary.md
evidence/generated/p7_large_object_jtag_summary.md
evidence/generated/p7_ps_app_runtime_summary.md
evidence/generated/p7_lane_scheduler_fallback_summary.md
evidence/generated/p7_abort_restart_atomicity_summary.md
evidence/generated/p7_queue_backpressure_summary.md
evidence/generated/p7_calibration_5min_embedded_summary.md
evidence/generated/p7_stationary_app_30min_soak_summary.md
evidence/generated/p7_application_metrics_summary.md
evidence/generated/p7_evidence_consistency_summary.md
evidence/generated/p7_stationary_local_application_layer_summary.md
```

每个硬件 summary 必须包含：

```text
stage
result
reason
generated_at_utc
repo
HEAD
profile path + SHA256
bitstream path + SHA256
LTX path + SHA256 when applicable
XSA/ELF path + SHA256 when applicable
authorization path + SHA256
hardware_actions_executed
programmed_fpga
drove_tfdu_txd
enabled_tfdu_receiver
shutdown_before
shutdown_after
SHUTDOWN_EXIT
network_used=false
motion_used=false
available_lanes=2
max_lane_mask=0x3
input file hashes
output file hashes
metrics
product_final_acceptance=pending
```

---

## 18. P7 PASS 判据

P7 只有在以下全部成立时可以 PASS：

```text
P6_RECHECK: PASS
P7_PROTOCOL_VECTORS: PASS
P7_SEGMENTATION_REASSEMBLY: PASS
P7_BACKEND_CONFORMANCE: PASS
P7_PS_RUNTIME_BUILD: PASS
P7_NO_ETHERNET: PASS
P7_NO_MOTION: PASS
P7_2LANE_SCOPE: PASS
P7_SAFE_IDLE_RECHECK: PASS
P7_P6_FRAME_REGRESSION: PASS
P7_FRAGMENT_BOUNDARY_MATRIX: PASS
P7_LARGE_OBJECT_JTAG: PASS
P7_PS_APP_RUNTIME: PASS
P7_LANE_SCHEDULER_FALLBACK: PASS
P7_ABORT_RESTART_ATOMICITY: PASS
P7_QUEUE_BACKPRESSURE: PASS
P7_CALIBRATION_30MIN: PASS
P7_STATIONARY_APP_2H_SOAK: PASS
P7_APPLICATION_METRICS: PASS
P7_EVIDENCE_CONSISTENCY: PASS
```

P7 最终状态应写为：

```text
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PASS
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PASS
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT
```

---

## 19. 文档更新

更新：

```text
README.md
PROJECT_STATUS.md
docs/PROJECT_STATUS.md
docs/P7_APPLICATION_PROTOCOL.md
docs/P7_HARDWARE_RUNBOOK.md
```

不得删除 P0-P6 历史状态。P7 文档必须明确：

- 当前只证明静止 2-lane application transport；
- JTAG/AXI/PS mailbox 是当前 host ingress；
- TCP adapter 尚未通过真实网线验证；
- striping 与 replication 的语义不同；
- software-injected lane unavailable 不是真实光路故障证据；
- product-final 仍 pending。

---

## 20. 提交与最终输出

建议使用三个可回滚 checkpoint，不要把全部变更压成一个不可审计的大提交：

```text
checkpoint A: feat: add P7 application protocol and offline tests
checkpoint B: feat: add P7 PS service and transport backends
checkpoint C: test: add P7 stationary hardware acceptance evidence
```

若仓库策略要求单提交，可在最终阶段 squash；无论采用哪种方式，hardware evidence 关联的源代码、profile、bitstream、ELF 和授权文件哈希必须可追溯。

运行：

```powershell
python tools/run_p7_gate.py --json-summary --allow-skips
powershell -NoProfile -ExecutionPolicy Bypass -File tools\run_p7_gate.ps1 -JsonSummary -AllowSkips
python tools/summarize_gate.py
git diff --check
git status --short
```

若 P7 满足验收，提交：

```text
git add .
git commit -m "feat: add P7 stationary application transport"
```

Codex 最终输出格式：

```text
P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET: PASS/FAIL/BLOCKED
COMMIT: <hash>
USER_HARDWARE_AUTHORIZATION_FOR_P7: GRANTED
HARDWARE_ACTIONS_EXECUTED: true/false
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_APPLICATION: PASS/PENDING/FAIL
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT
PASS:
- ...
FAIL:
- ...
SKIP_WITH_REASON:
- ...
BLOCKED:
- ...
GENERATED_SUMMARIES:
- ...
NEXT_RECOMMENDED_STAGE: P8_ETHERNET_SOFTWARE_READINESS_NO_CABLE or P8_ETHERNET_INTEGRATION_AFTER_CABLE_AVAILABLE
```

---

## 21. Codex 执行优先级

按以下顺序执行，不得先跑长时间硬件测试再补基础代码：

```text
1. P6 intake and hash freeze
2. P7 protocol specification
3. C/Python golden vectors
4. segmentation/reassembly tests
5. transport abstraction
6. PS application service build
7. P7 offline gate
8. authorization/artifact freeze
9. safe-idle recheck
10. P6 one-frame regression
11. fragment boundary matrix
12. large object JTAG round-trip
13. PS application runtime
14. scheduler/fallback
15. abort/restart
16. queue/backpressure
17. embedded 5-minute calibration window
18. single 30-minute stationary application soak
19. evidence consistency
20. status update and commit
```

