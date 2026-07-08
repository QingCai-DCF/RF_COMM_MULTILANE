# IR array link package

这是一套面向 **1~16 lane 红外阵列链路** 的 SystemVerilog RTL 参考实现，目标是：

- 单上层包在途的可靠分片发送
- 多 lane 并行发送 fragment
- 接收端重组
- bitmap ACK + 最终 complete ACK
- 选择重传
- 4PPM 物理层收发
- 直接控制顶层 `ir_array_top.sv`
- AXI-Lite 包装顶层 `ir_array_top_axi.sv`

## 文件说明

### 协议与基础模块
- `ir_protocol_pkg.sv`：协议常量、CRC16/CRC32 函数
- `cdc_sync.sv`：参数化位宽 CDC 同步器
- `crc32_gen.sv`：按字节 CRC32 更新模块

### 单 lane 物理链路
- `ir_lane_frame_source.sv`：宽 frame -> AXIS byte stream
- `ir_lane_frame_sink.sv`：AXIS byte stream -> 宽 frame
- `ir_tx_4ppm_frame.sv`：可变长 frame 发送器，自动追加 CRC32
- `ir_rx_4ppm_frame.sv`：可变长 frame 接收器，按 silence 结束并校验 CRC32
- `ir_comm_lane.sv`：单 lane 收发封装

### 阵列层
- `ir_array_tx_mgr.sv`：包缓存、分片、超时、重传、ACK 跟踪
- `ir_array_rx_mgr.sv`：frame 解析、重组、ACK 生成、ACK 解析
- `ir_array_top.sv`：直接控制顶层

### AXI-Lite 包装
- `ir_axi_regs.sv`：AXI-Lite 寄存器与 sticky 状态
- `ir_array_top_axi.sv`：AXI-Lite + DMA AXIS 包装顶层，包含 CDC

### 仿真
- `tb_ir_array_loopback.sv`：双节点 loopback testbench

---

## 当前实现边界

为了优先保证结构自洽和可调试性，这一版采用：

- **单方向单包在途**：发送侧一次只管理一个上层包
- 接收侧一次只维护一个 active reassembly context
- `LANE_COUNT=1..16` 可配
- `MAX_PACKET_BYTES`、`FRAGMENT_BYTES` 可配
- ACK 分为：
  - **过程 ACK**：bitmap 有效，但 `complete=0`
  - **最终 ACK**：在接收端包已经完整交付给上层后发出，`complete=1`

这意味着：

- 发送端不会因为“只是收到全 bitmap”就提前开始下一包
- 接收端可以在本地还在 flush 给 DMA 时，避免对端过早进入下一包
- 不是多包乱序协议栈，但比初版框架更接近可落地实现

---

## 协议

### DATA frame

| byte | meaning |
|---:|---|
| 0 | SOF = `0xA5` |
| 1 | `{version, type}`，type=1 |
| 2..3 | `session_id` little-endian |
| 4..5 | `pkt_seq` little-endian |
| 6 | `frag_idx` |
| 7 | `frag_count` |
| 8..9 | `total_len` |
| 10 | `payload_len` |
| 11 | `retry_count` |
| 12..13 | `header_crc16` |
| 14.. | fragment payload |

`ir_tx_4ppm_frame.sv` 会对整个协议 frame 再追加物理层 `CRC32`。

### ACK frame

| byte | meaning |
|---:|---|
| 0 | SOF = `0xA5` |
| 1 | `{version, type}`，type=2 |
| 2..3 | `session_id` |
| 4..5 | `pkt_seq` |
| 6 | `frag_count` |
| 7 | `bitmap_len_bytes` |
| 8 | flags，bit0=`complete` |
| 9 | reserved |
| 10..11 | `header_crc16` |
| 12.. | bitmap |

### ACK 语义

- `bitmap` 表示当前已经接收成功的 fragment 集合
- `complete=0`：只是接收端当前 bitmap 的反馈，还没有完成最终上交
- `complete=1`：接收端已经把完整包交给上层，发送端可以结束该包并开始下一包

---

## 顶层建议

### 1. 直接控制顶层
使用 `ir_array_top.sv`：

- `enable`：总使能
- `session_id`：建议链路两端一致
- `lane_enable_mask`：启用哪些 lane
- `s_axis_tx_*`：待发送完整包
- `m_axis_rx_*`：接收端重组后的完整包

### 2. AXI 包装顶层
使用 `ir_array_top_axi.sv`：

- AXI-Lite 配置在 `s_axi_aclk` 域
- PHY 与阵列逻辑在 `clk_phy` 域
- 顶层已经补了配置 CDC 和 sticky 事件 CDC

寄存器映射：

- `0x00` control，bit0=`enable`
- `0x04` session_id
- `0x08` lane_enable_mask
- `0x0C` live status
- `0x10` sticky status，W1C
- `0x18` pending bitmap
- `0x1C` inflight bitmap
- `0x20` acked bitmap
- `0x24` rx recv bitmap

建议的软件写入顺序：

1. `enable=0`
2. 写 `session_id`
3. 写 `lane_enable_mask`
4. 最后写 `enable=1`

---

## 调试建议

### 发送侧先看
- `tx_packet_active`
- `tx_packet_loading`
- `tx_frag_pending_dbg`
- `tx_frag_inflight_dbg`
- `tx_frag_acked_dbg`
- `tx_done_pulse`
- `tx_error_retry_exhausted`

### 接收侧先看
- `rx_ctx_valid`
- `rx_ctx_complete`
- `rx_recv_bitmap_dbg`
- `rx_done_pulse`
- `rx_header_error`
- `rx_protocol_error`

### lane 级别
- `lane_tx_busy_dbg`
- `lane_rx_frame_valid`
- `lane_rx_crc_error`
- `lane_rx_overrun_error`
- `lane_rx_frame_overflow`

### ACK 闭环
- `ack_issue_valid`
- `ack_update_valid`
- `ack_update_complete`

---

## Vivado 使用提示

- 这些 RTL 是 **SystemVerilog (`.sv`)**
- Vivado 可以直接用，但要按 **SystemVerilog** 源文件加入
- `ir_protocol_pkg.sv` 要排在编译顺序最前面
- `tb_ir_array_loopback.sv` 只放到 Simulation Sources，不要综合

---

## 联调顺序建议

1. `LANE_COUNT=1`
2. 跑 `tb_ir_array_loopback.sv`
3. 再扩到 `LANE_COUNT=2/4`
4. 最后开到 `LANE_COUNT=16`
5. 如果不通，优先抓：
   - 单 lane `ir_tx_out`
   - 对端 `ir_rx_in`
   - `lane_rx_frame_valid`
   - `ack_issue_valid`
   - `ack_update_valid`
   - `ack_update_complete`
   - `tx_frag_*` / `rx_recv_bitmap_dbg`

---

## 说明

这版代码已经把最关键的结构性问题补上了：

- lane source -> tx core 的握手更稳
- 配置与 sticky 事件做了 CDC
- ACK 引入了 `complete` 语义
- 顶层 lane 选择改成轮转仲裁

它仍然不是“多包乱序网络栈”，但作为你当前这类红外阵列分片系统的第一版工程骨架，已经比初始框架更接近能落地和联调的版本。
