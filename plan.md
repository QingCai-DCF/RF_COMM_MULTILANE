# RF_COMM 新项目自动化推进计划 / Codex Prompt

> 目的：把现有 `RF_COMM` 工程作为只读遗留来源，自动复制必要约束、文档、RTL、Vivado、PS/PC 软件、工具和证据到一个新项目中，然后在新项目内建立可重构、可仿真、可静态检查、可追踪的 TFDU6102 红外通信工程基线。
>
> 使用方式：在新项目根目录中，把本文件交给 Codex 执行。Codex 应按本计划自动化完成文件导入、目录重建、脚本生成、静态 gate、仿真 gate 和文档生成。不要要求人工复制文件。

---

## 0. Codex 执行角色

你是 Codex，当前工作目录是用户新建项目的根目录，不是旧项目 `RF_COMM` 根目录。

你的任务不是直接修旧工程，而是：

1. 自动定位旧工程 `RF_COMM`。
2. 从旧工程复制必要文件到新工程。
3. 生成新工程的规范目录、约束、pinmap、配置 profile、检查脚本和离线仿真框架。
4. 把旧工程内容保存在 `legacy/RF_COMM/` 下作为只读参考。
5. 在新工程中建立新的 canonical 源码入口，逐步替换旧工程混杂状态。
6. 所有步骤必须可由 Codex 自动执行。

禁止事项：

- 不要在旧项目 `RF_COMM` 中改文件。
- 不要使用 `git reset --hard`、`git clean`、`git push --force`、破坏性 checkout 或批量格式化。
- 不要运行会编程 FPGA、启动 PS ELF、驱动 TFDU、XSCT hardware target、Vivado hardware manager、ILA 抓取或 UART 写命令的步骤。
- 不要把硬件验收伪装成已完成。没有真实硬件自动运行证据时，一律标记为 `PENDING_HW`。
- 不要把当前 degraded lane0 证据扩展解释为 2-lane、8-lane、Ethernet 或旋转场景已通过。

默认运行模式：`NO_HARDWARE=1`。

---

## 1. 旧工程定位规则

Codex 必须自动定位旧工程，按优先级执行：

1. 若环境变量 `RF_COMM_SOURCE` 存在，使用该路径。
2. 否则检查新项目同级目录：`../RF_COMM`。
3. 否则向上两级查找目录名精确为 `RF_COMM` 的目录。
4. 否则检查是否存在用户提供的注释化包目录，目录名形如：`RF_COMM_annotated_source_package_*`。
5. 否则检查是否存在 zip 包，文件名包含 `RF_COMM` 或当前上传包名，自动解压到 `.cache/rf_comm_import/` 后使用其中的 `source/` 目录。

兼容两种旧工程形态：

- 直接旧工程根目录：包含 `IPs/`、`TFDU_VFIR_Client_Array/`、`software/`、`tools/`、`AGENTS.md`。
- 注释化交付包：包含 `source/` 子目录，实际旧工程源码在 `source/` 下，包级文档在包根目录下。

实现要求：生成脚本 `scripts/import_rf_comm.py`，自动完成上述定位、复制和 manifest 生成。

导入脚本基本命令：

```bash
python scripts/import_rf_comm.py --source auto --no-hardware
```

如果检测失败，Codex 应输出明确错误：

```text
RF_COMM_SOURCE_NOT_FOUND: set RF_COMM_SOURCE or place the old RF_COMM directory next to this new project.
```

---

## 2. 新项目目标目录结构

Codex 必须创建以下目录：

```text
./
  plan.md
  AGENTS.md
  agent.md
  项目约束(目标）.txt
  PROJECT_CONSTRAINTS.txt
  README.md
  .gitignore

  board_profiles/
    ax7010_tfdu_j10_j11_pinmap.csv
    ax7010_tfdu_j10_j11_pinmap.json
    ACTIVE_PROFILE.json

  config/
    profiles/
      G1_LANE0_BASELINE.json
      LANE0_DEGRADED_RELIABLE_2LANE_STATIC.json
      PENDING_2LANE_PROFILE.json
    register_map/
      ir_axi_regs.yaml
      generated/

  constraints/
    active/
      PORT1.generated.xdc
      async_clock_groups_impl.xdc
    legacy_conflicts/
      PORT1.top_active.original.xdc
      PORT1.ip_legacy_conflict.original.xdc
      xdc_conflict_report.md

  docs/
    constraints/
      PROJECT_CONSTRAINTS.original.txt
    datasheets/
      TFDU6102datasheet.pdf
    legacy/
      BUILD_AND_TEST_GUIDE.md
      DIRECTORY_USAGE.md
      HARDWARE_SAFETY.md
      SOURCE_STATE.md
      PACKAGE_MANIFEST.csv
      PACKAGE_MANIFEST.json
      SHA256SUMS.txt
    design/
      TFDU6102_CONSTRAINTS.md
      KNOWN_ISSUES_FROM_RF_COMM.md
      MIGRATION_NOTES.md
      REGISTER_CONTRACT.md
      ACCEPTANCE_MATRIX.md
      PENDING_HARDWARE_ACCEPTANCE.md

  legacy/
    RF_COMM/
      docs/
      evidence/
      IPs/
      software/
      TFDU_VFIR_Client_Array/
      tools/
      import_manifest.json
      import_manifest.csv
      import_sha256s.txt

  rtl/
    tfdu_lane_phy.sv
    tfdu_lane_phy_pkg.sv
    ir_4ppm_codec.sv
    ir_frame_l1.sv
    ir_arq_l2.sv
    ir_multilane_scheduler.sv
    ir_axi_regs_new.sv
    ir_top_new.sv

  sim/
    models/
      tfdu6102_behavior_model.sv
    tb/
      tb_tfdu_lane_phy_smoke.sv
      tb_tfdu_4ppm_codec.sv
      tb_lane0_frame_crc.sv
      tb_lane0_ack_only.sv
    legacy_tb/

  scripts/
    import_rf_comm.py
    generate_pinmap_from_xdc.py
    generate_xdc_from_pinmap.py
    check_xdc_conflicts.py
    check_project_integrity.py
    check_no_hardware_calls.py
    check_tfdu_safety_static.py
    extract_legacy_register_map.py
    generate_register_headers.py
    run_offline_gates.py
    run_offline_gates.ps1

  software/
    ps_driver/
    host_client/
    legacy_ps_ps_loopback/
    legacy_ps_lwip_bridge/
    legacy_host_client/
    legacy_host_uart_operator/

  evidence/
    imported/
    generated/
```

`legacy/RF_COMM/` 只作为参考快照。新工程 canonical 文件必须放在 `rtl/`、`constraints/`、`board_profiles/`、`config/`、`scripts/`、`software/ps_driver/` 等新目录中。

---

## 3. 必须复制的文件

### 3.1 根约束和 agent 文件

Codex 必须复制下列文件。若某个文件不存在，写入 `legacy/RF_COMM/import_manifest.json` 的 `missing_optional`，不要中断；但 `项目约束(目标）.txt` 和 `AGENTS.md` 缺失时必须中断。

| 旧工程来源 | 新工程目标 | 要求 |
|---|---|---|
| `项目约束(目标）.txt` | `./项目约束(目标）.txt` | 原样复制，禁止修改 |
| `项目约束(目标）.txt` | `./PROJECT_CONSTRAINTS.txt` | ASCII 别名，内容必须与原文件一致 |
| `项目约束(目标）.txt` | `docs/constraints/PROJECT_CONSTRAINTS.original.txt` | 原样归档 |
| `AGENTS.md` | `docs/legacy/AGENTS.RF_COMM.md` | 原样归档 |
| `AGENTS.md` | `./AGENTS.md` | 生成新项目版本，必须包含旧 AGENTS 的硬约束和本 plan 的新约束 |
| `AGENTS.md` | `./agent.md` | 兼容别名，内容写“see AGENTS.md”并摘要硬约束 |

新 `AGENTS.md` 必须包含：

- `项目约束(目标）.txt` 是硬约束，不得擅改。
- 所有硬件运行默认禁止，除非用户明确要求并确认。
- 任意硬件运行后必须自动执行 TFDU shutdown，并检查 `SHUTDOWN_EXIT=0` 或 `TFDU_SHUTDOWN_PROGRAMMED`。
- Codex 只能修改新项目，不能修改旧 `RF_COMM`。
- 旧工程中多个 XDC/wrapper 有冲突，新项目只能使用 canonical generated XDC。
- `AB_L1` 是旧工程 raw-layer BAD_DIR，不得在未重新验证前启用 lane1 作为可靠链路。

### 3.2 包级文档

从旧工程或注释化包根目录复制到 `docs/legacy/`：

```text
README.md
BUILD_AND_TEST_GUIDE.md
DIRECTORY_USAGE.md
HARDWARE_SAFETY.md
SOURCE_STATE.md
PACKAGE_MANIFEST.csv
PACKAGE_MANIFEST.json
PACKAGE_SUMMARY.json
SHA256SUMS.txt
MANIFEST_NOTES.md
EXCLUDED_GENERATED_ARTIFACTS.md
```

这些文档用于追溯，不作为新工程 canonical build input。

### 3.3 TFDU6102 datasheet

Codex 必须自动查找并复制 datasheet：

候选路径：

```text
$TFDU6102_DATASHEET
./TFDU6102datasheet.pdf
../TFDU6102datasheet.pdf
$RF_COMM_SOURCE/TFDU6102datasheet.pdf
$RF_COMM_SOURCE/docs/TFDU6102datasheet.pdf
```

目标路径：

```text
docs/datasheets/TFDU6102datasheet.pdf
```

若找不到 datasheet，不要阻塞导入，但必须生成：

```text
docs/design/TFDU6102_CONSTRAINTS.md
```

并标记：

```text
TFDU_DATASHEET_COPY=PENDING
```

### 3.4 关键 evidence

复制到 `legacy/RF_COMM/evidence/` 和 `evidence/imported/`：

```text
evidence/final/current_usable_configuration.md
evidence/final/BAD_DIR_fault_report.md
evidence/final/constrained_acceptance_matrix.md
evidence/G1_freeze/G1_frozen_config.md
evidence/G1_freeze/G1_frozen_summary.txt
evidence/lane_matrix/rxonly_matrix.md
evidence/lane_matrix/rxonly_matrix.csv
evidence/lane_matrix/rxonly_AB_L0.csv
evidence/lane_matrix/rxonly_AB_L1.csv
evidence/lane_matrix/rxonly_BA_L0.csv
evidence/lane_matrix/rxonly_BA_L1.csv
evidence/lane_matrix/ackonly_matrix.md
evidence/bad_dir_debug/BAD_DIR_failure_classification.md
evidence/bad_dir_debug/BAD_DIR_param_sweep_summary.md
evidence/bad_dir_debug/BAD_DIR_root_cause_table.md
baseline_current_failure.md
config_diff_known_good_vs_current.md
evidence_lock_20260625.csv
```

若 `evidence/n03_network_first/` 存在，复制该目录下所有 `.md`、`.csv`、`.json`、`.txt` 到：

```text
evidence/imported/n03_network_first/
```

但在 `docs/design/ACCEPTANCE_MATRIX.md` 中标记网络验收为 `PENDING_HW_OR_DEFERRED`，不得写成最终通过。

### 3.5 RTL/IP 参考源码

复制旧 `IPs/ip_ir_array/` 到：

```text
legacy/RF_COMM/IPs/ip_ir_array/
```

复制旧 `IPs/ir_array/` 到：

```text
legacy/RF_COMM/IPs/ir_array/
```

排除明显生成目录和缓存：

```text
.Xil/
runs/
cache/
sim_work/
*.jou
*.log
*.str
*.wdb
*.bit
*.ltx
*.xsa
*.elf
```

同时把旧核心 RTL 的 `.sv` 文件复制到：

```text
rtl/legacy_reference/
```

至少包括：

```text
cdc_sync.sv
crc32_gen.sv
ir_protocol_pkg.sv
ir_tx_4ppm_frame.sv
ir_rx_4ppm_frame.sv
ir_lane_frame_source.sv
ir_lane_frame_sink.sv
ir_comm_lane.sv
ir_array_tx_mgr.sv
ir_array_rx_mgr.sv
ir_array_top.sv
ir_array_top_axi.sv
ir_stream_array_top.sv
ir_stream_array_top_axi.sv
ir_axi_regs.sv
ir_axis_async_fifo.sv
ir_stream_bidir_b0_bd.sv
ir_stream_parallel_2lane_top.sv
ir_txonly_ack_axi.sv
```

`rtl/legacy_reference/` 仅供 diff 和参考；不要把它作为新工程默认综合入口。

### 3.6 Vivado 顶层与约束

复制旧 Vivado 工程到：

```text
legacy/RF_COMM/TFDU_VFIR_Client_Array/
```

至少保留：

```text
TFDU_VFIR_Client_Array/TFDU_VFIR_Client.xpr
TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/PORT1.xdc
TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/imports/hdl/design_shiboqi_wrapper.v
TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/sources_1/bd/design_shiboqi/design_shiboqi.bd
TFDU_VFIR_Client_Array/Packages/
```

另外复制两个 XDC 到冲突目录：

```text
旧 active top XDC:
  TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/PORT1.xdc
目标:
  constraints/legacy_conflicts/PORT1.top_active.original.xdc

旧 IP 内 XDC:
  IPs/ip_ir_array/src/PORT1.xdc
目标:
  constraints/legacy_conflicts/PORT1.ip_legacy_conflict.original.xdc
```

新工程 canonical XDC 不得直接手写；必须由 pinmap 自动生成：

```text
board_profiles/ax7010_tfdu_j10_j11_pinmap.csv
  -> constraints/active/PORT1.generated.xdc
```

### 3.7 软件和工具

复制旧软件目录到 legacy：

```text
software/ps_ps_loopback/      -> software/legacy_ps_ps_loopback/
software/ps_lwip_bridge/      -> software/legacy_ps_lwip_bridge/
software/host_client/         -> software/legacy_host_client/
software/host_uart_operator/  -> software/legacy_host_uart_operator/
```

复制旧工具目录到：

```text
legacy/RF_COMM/tools/
```

同时把以下安全相关工具复制到新项目 `scripts/legacy_safe_tools/`：

```text
tools/program_tfdu_shutdown.tcl
tools/build_tfdu_shutdown.tcl
tools/tfdu_shutdown_top.v
tools/tfdu_shutdown_j10_j11.xdc
tools/run_lane0_hw_once_safe.ps1
tools/run_lane_remap_probe_safe.ps1
tools/run_p2_register_status_readonly_safe.ps1
tools/uart_operator_readonly_no_tx.py
```

这些工具默认不得自动执行硬件动作。只允许作为后续用户明确授权硬件运行时的模板。

---

## 4. TFDU6102 固化约束

Codex 必须生成 `docs/design/TFDU6102_CONSTRAINTS.md`，并把以下约束写入新 RTL、仿真模型、静态检查和 profile：

| 项目 | 固定约束 |
|---|---|
| `Txd` | 高有效；默认 idle 必须为 0 |
| `Rxd` | 低有效；RTL 内部 raw pulse 应使用 `~rxd_sync` |
| `SD` | 高有效 shutdown；active 时为 0 |
| `Mode` | 静态高速模式时为 1；动态 mode programming 时必须可 Hi-Z，不得与静态驱动混用 |
| 默认模式 | TFDU6102 上电默认 SIR；本项目使用静态 `Mode=1` 进入 MIR/FIR 高速模式 |
| startup | `SD` 从 1 到 0 后，TX/RX FSM 必须等待至少 500 us 才允许进入有效工作 |
| long-high 保护 | `Txd` 连续高电平不得接近 80 us；RTL 必须有 stuck-high 检查 |
| TX duty | 必须有 rolling-window duty 计数和过限 shutdown 机制 |
| IRED 电流 | 典型/限制电流约 500-600 mA 量级；新工程不得假设普通弱 GPIO LED 负载 |
| 推荐去耦 | C1/C3 4.7 uF，C2 0.1 uF；软件/RTL 文档需提示这属于板级前提 |
| FIR pulse | 125 ns 输入光脉冲对应 Rxd 约 100-140 ns；250 ns 输入光脉冲对应 Rxd 约 225-275 ns |
| jitter | 4 Mbit/s 下 leading-edge jitter 量级约 20 ns；仿真模型必须可注入 jitter |

生成 `scripts/check_tfdu_safety_static.py`，至少检查：

- `Txd` reset/default 是否为 0。
- `SD` reset/default 是否为 1。
- `Mode` 策略是否唯一：静态 `Mode=1` 或动态 Hi-Z 二选一。
- 新 RTL 是否存在 startup timer 参数，且默认不少于 500 us。
- 新 RTL 是否存在 `tx_stuck_high` 或同等保护信号。
- 新 RTL 是否存在 `duty_limit` 或同等 rolling-window duty 保护。
- RX 极性是否明确转换为低有效 pulse。

---

## 5. XDC 和 pinmap 重建

### 5.1 旧工程已知问题

旧工程存在两个 `PORT1.xdc` 且内容不一致：

- active top XDC：`TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/PORT1.xdc`
- IP 内 legacy XDC：`IPs/ip_ir_array/src/PORT1.xdc`

这两个 XDC 对 lane0 A/B 映射不同，lane1 `loop_rx_b0[1]` 也不同：

- active top XDC 使用 `G15`
- IP legacy XDC 使用 `D19`

新工程必须把 active top XDC 视为旧工程最后使用的 canonical reference，但不得直接手写复制为新 active XDC。必须生成 pinmap CSV，再从 CSV 生成 XDC。

### 5.2 pinmap CSV 要求

生成：

```text
board_profiles/ax7010_tfdu_j10_j11_pinmap.csv
```

字段：

```csv
lane,side,logical_endpoint,signal,port,package_pin,iostandard,connector,notes
```

以旧 active top XDC 为默认 pinmap。必须包含：

```text
lane0 logical A:
  ir_mode_out_0[0] -> T12
  ir_rx_in_0[0]    -> B19
  ir_sd_0[0]       -> T11
  ir_tx_out_0[0]   -> C20

lane1 logical A:
  ir_mode_out_0[1] -> G17
  ir_rx_in_0[1]    -> H15
  ir_sd_0[1]       -> H16
  ir_tx_out_0[1]   -> K14

lane0 logical B:
  loop_mode_b0[0]  -> V17
  loop_rx_b0[0]    -> U13
  loop_sd_b0[0]    -> T14
  loop_tx_b0[0]    -> V12

lane1 logical B:
  loop_mode_b0[1]  -> L16
  loop_rx_b0[1]    -> G15
  loop_sd_b0[1]    -> M17
  loop_tx_b0[1]    -> E18
```

同时在 `constraints/legacy_conflicts/xdc_conflict_report.md` 记录：

```text
IP legacy PORT1.xdc differs from active top PORT1.xdc.
Do not use IP legacy PORT1.xdc in new builds.
D19 is legacy; G15 is active-top reference for loop_rx_b0[1].
```

### 5.3 自动检查

生成并运行：

```bash
python scripts/generate_pinmap_from_xdc.py \
  --xdc constraints/legacy_conflicts/PORT1.top_active.original.xdc \
  --out board_profiles/ax7010_tfdu_j10_j11_pinmap.csv

python scripts/generate_xdc_from_pinmap.py \
  --pinmap board_profiles/ax7010_tfdu_j10_j11_pinmap.csv \
  --out constraints/active/PORT1.generated.xdc

python scripts/check_xdc_conflicts.py \
  --active constraints/legacy_conflicts/PORT1.top_active.original.xdc \
  --legacy constraints/legacy_conflicts/PORT1.ip_legacy_conflict.original.xdc \
  --generated constraints/active/PORT1.generated.xdc \
  --report constraints/legacy_conflicts/xdc_conflict_report.md
```

pass 条件：

```text
XDC_GENERATED_FROM_PINMAP=1
XDC_GENERATED_MATCHES_ACTIVE_REFERENCE=1
XDC_LEGACY_CONFLICT_RECORDED=1
NO_LEGACY_PORT1_XDC_IN_BUILD=1
```

---

## 6. 配置 profile 固化

生成 `board_profiles/ACTIVE_PROFILE.json`：

```json
{
  "project": "RF_COMM_REBUILD",
  "source_project": "RF_COMM",
  "hardware_target": "Zynq-7010 / AX7010 class board",
  "tfdu_part": "TFDU6102",
  "vivado_version_reference": "2023.1",
  "default_no_hardware": true,
  "canonical_xdc": "constraints/active/PORT1.generated.xdc",
  "canonical_pinmap": "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
  "baseline_profile": "config/profiles/G1_LANE0_BASELINE.json",
  "known_bad_raw_direction": "AB_L1",
  "lane1_reliable_enabled": false
}
```

生成 `config/profiles/G1_LANE0_BASELINE.json`：

```json
{
  "name": "G1_LANE0_BASELINE",
  "status": "IMPORTED_KNOWN_GOOD_REFERENCE_PENDING_REBUILD_REPLAY",
  "lane_count_build": 2,
  "test_lane_mask": "0x00000001",
  "payload_lane_mask": "0x00000001",
  "ack_lane_mask": "0x00000001",
  "session": "0x2201",
  "app_payload_bytes": 256,
  "raw_packet_bytes": 264,
  "fragment_bytes": 255,
  "max_retry": 12,
  "guard_cycles": 4096,
  "cnt_preamble": 16,
  "cnt_chip_max": 7,
  "a_rx_detect_start": 0,
  "a_rx_detect_end": 5,
  "b_rx_detect_start": 0,
  "b_rx_detect_end": 7,
  "preamble_realign": 0,
  "ps_max_outstanding": 0,
  "b_expected_a_lane_mask": "0x00000001",
  "b_rx_lane_mask": "0x00000001",
  "b_ack_lane_mask": "0x00000001",
  "lane1_enabled": false,
  "ethernet_enabled": false,
  "rotation_claimed": false
}
```

生成 `config/profiles/LANE0_DEGRADED_RELIABLE_2LANE_STATIC.json`，内容与 G1 接近，但明确：

```json
{
  "name": "LANE0_DEGRADED_RELIABLE_2LANE_STATIC",
  "payload_lane_mask": "0x00000001",
  "ack_lane_mask": "0x00000001",
  "excluded_direction": "AB_L1",
  "reason": "Imported RF_COMM evidence classifies AB_L1 as raw-layer NO_RX_RAW_PULSE"
}
```

生成 `config/profiles/PENDING_2LANE_PROFILE.json`，并把 `enabled` 设为 false：

```json
{
  "name": "PENDING_2LANE_PROFILE",
  "enabled": false,
  "blocked_by": "AB_L1 raw pulse failure in imported RF_COMM evidence",
  "required_before_enable": [
    "AB_L1 raw-pulse matrix pass",
    "BA_L1 raw-pulse matrix pass",
    "lane1 frame CRC pass",
    "lane1 ACK-only pass",
    "session/mask readback match"
  ]
}
```

---

## 7. 新 RTL 重构任务

Codex 必须在 `rtl/` 下建立新模块，不要直接把旧 `ir_stream_array_top.sv` 当作新顶层。

### 7.1 `tfdu_lane_phy.sv`

职责：只处理 TFDU6102 物理管脚和安全状态。

必须实现：

- `Mode/SD/Txd/Rxd` 管脚控制。
- 静态高速模式：`Mode=1`。
- reset/shutdown：`SD=1`，`Txd=0`。
- enable 后 startup timer，默认不少于 500 us。
- `phy_ready` 只有 startup done 后为 1。
- TX pulse request 输入。
- TX stuck-high 检测。
- rolling-window duty counter。
- duty/stuck-high 违规后自动 shutdown。
- RX 双触发同步。
- `rx_pulse_active = ~rxd_sync`。
- RX raw edge count、pulse width min/max、last timestamp。
- 状态寄存器输出：`startup_done`、`shutdown_active`、`fault_stuck_high`、`fault_duty_limit`、`rx_raw_count`、`tx_pulse_count`。

### 7.2 `tfdu_lane_phy_pkg.sv`

放置参数：

```systemverilog
parameter int CLK_HZ = 64_000_000;
parameter int TFDU_STARTUP_US = 500;
parameter int TX_STUCK_HIGH_LIMIT_US = 20; // static guard; lower than 80 us device limit
parameter int DUTY_WINDOW_US = 1000;
parameter int DUTY_MAX_PERMILLE = 200;
```

### 7.3 `tfdu6102_behavior_model.sv`

仿真模型必须模拟：

- `Txd` 高有效。
- `Rxd` 低有效。
- `SD` 高 shutdown。
- shutdown 时 `Rxd` weak-high 行为用逻辑 high 近似。
- `SD` 退出后 500 us 内不产生有效 RX。
- 125 ns pulse 输出 100-140 ns RX low pulse。
- 250 ns pulse 输出 225-275 ns RX low pulse。
- jitter 可配置，默认 20 ns。
- pulse loss 可配置，默认 0。
- optional near-end echo。
- long-high protection：`Txd` high 超过阈值后关闭 optical output。

### 7.4 `ir_4ppm_codec.sv`

职责：只做 4PPM symbol 编码/解码，不知道 TFDU `SD/Mode`。

要求：

- 可独立仿真。
- 输入输出使用 abstract pulse stream。
- 参数化 `CNT_CHIP_MAX`、`CNT_PREAMBLE`、detect window。
- 与 `tfdu6102_behavior_model.sv` 联合仿真。

### 7.5 `ir_frame_l1.sv`

职责：frame/preamble/length/session/CRC。

要求：

- session mismatch 明确计数。
- lane mask mismatch 明确计数。
- CRC bad 明确计数。
- payload length mismatch 明确计数。
- 不处理 ACK/retry。

### 7.6 `ir_arq_l2.sv`

职责：ACK、retry、timeout、sequence number。

要求：

- ACK lane mask 和 payload lane mask 分开。
- retry exhausted 明确 sticky flag。
- timeout 参数 profile 化。
- 过期 ACK、重复 ACK、session mismatch ACK 必须可观测。

### 7.7 `ir_multilane_scheduler.sv`

职责：lane mask、lane health、fallback。

要求：

- 默认只启用 lane0。
- lane1 默认 disabled。
- 若 profile 中 `known_bad_raw_direction=AB_L1`，自动阻止 lane1 reliable enable。
- lane enable 必须有 readback。

### 7.8 `ir_axi_regs_new.sv`

职责：寄存器接口。

要求：

- 从 `config/register_map/ir_axi_regs.yaml` 生成或校验。
- 所有关键配置必须 write/readback/commit。
- 暴露 profile hash 或 profile id。
- 暴露 safety/fault counters。

最低寄存器类别：

```text
CONTROL: reset, enable_phy, start, stop, clear_sticky, commit
PROFILE: lane_mask, rx_lane_mask, ack_lane_mask, session, payload_len, fragment_bytes
TIMING: cnt_chip_max, cnt_preamble, detect_start/end, guard_cycles, retry_timeout
SAFETY: startup_us, duty_window, duty_max, stuck_high_limit, shutdown_reason
STATUS: phy_ready, busy, tx_done, rx_done, tx_fail, retry_count, crc_bad, session_bad, mask_bad
COUNTERS: tx_pulse, rx_raw_pulse, frame_good, frame_bad, ack_sent, ack_seen
```

---

## 8. 软件重建任务

### 8.1 Register map single source of truth

生成：

```text
config/register_map/ir_axi_regs.yaml
```

然后生成：

```text
config/register_map/generated/ir_regs.h
config/register_map/generated/ir_regs.py
config/register_map/generated/ir_regs.md
```

Codex 必须写 `scripts/generate_register_headers.py`，从 YAML 生成 C/Python/Markdown。不得手工维护多份寄存器地址。

### 8.2 PS driver

建立：

```text
software/ps_driver/
  ir_regs.h
  ir_driver.c
  ir_driver.h
  ir_profile.c
  ir_profile.h
  main_offline_stub.c
```

固定初始化顺序：

```text
reset core
write profile registers
write lane masks
write session
write payload length / fragment bytes
write retry / timeout / guard / detect windows
commit toggle
readback verify every critical register
enable PHY
wait startup_done or timeout
clear counters/sticky
start test or transaction
poll status
stop
shutdown
read final counters
```

### 8.3 Host client

建立：

```text
software/host_client/
  rfcm_protocol.py
  mock_ps_server.py
  test_protocol_contract.py
```

先做离线 mock，不接真实 Ethernet。目标：验证命令编码、状态返回、错误事件、重连状态机。

---

## 9. 自动化检查和 gates

Codex 必须生成并运行：

```bash
python scripts/check_project_integrity.py
python scripts/check_no_hardware_calls.py
python scripts/check_xdc_conflicts.py
python scripts/check_tfdu_safety_static.py
python scripts/run_offline_gates.py
```

PowerShell 入口：

```powershell
pwsh scripts/run_offline_gates.ps1 -NoHardware
```

### 9.1 `check_project_integrity.py`

检查：

- 当前目录不是旧 `RF_COMM`。
- `项目约束(目标）.txt` 存在。
- `PROJECT_CONSTRAINTS.txt` 与中文约束文件 SHA256 一致。
- `AGENTS.md` 存在且包含硬件 shutdown 规则。
- `legacy/RF_COMM/import_manifest.json` 存在。
- 必要 evidence 已导入。
- active profile 存在。
- canonical XDC 由 pinmap 生成。

### 9.2 `check_no_hardware_calls.py`

扫描脚本，默认 fail 条件：

- 自动执行 `open_hw`。
- 自动执行 `connect_hw_server`。
- 自动执行 `program_hw_devices`。
- 自动运行 `xsct` 下载 ELF。
- 自动运行 UART 写命令。
- 自动运行旧 safe wrapper 且未显式 `--allow-hardware`。

允许存在 hardware 模板脚本，但必须默认 `NO_HARDWARE=1`，并且需要用户显式参数 `--allow-hardware`。

### 9.3 `run_offline_gates.py`

顺序执行：

1. import manifest 校验。
2. XDC conflict check。
3. TFDU safety static check。
4. register map generation check。
5. Python unit tests。
6. SystemVerilog syntax check：优先使用可用工具，按顺序探测 `verilator`、`iverilog`、`vivado -mode batch -source scripts/xsim_compile.tcl`。
7. 仿真 gate：如果没有 SV 工具，标记 `SIM_TOOL_MISSING`，但不得伪造 pass。

输出：

```text
evidence/generated/offline_gate_summary.json
evidence/generated/offline_gate_summary.md
```

---

## 10. 仿真任务

生成以下 testbench：

### 10.1 `tb_tfdu_lane_phy_smoke.sv`

覆盖：

- reset 后 `SD=1`、`Txd=0`。
- enable 后 500 us 前 `phy_ready=0`。
- startup done 后 `phy_ready=1`。
- 发送短 pulse，`tx_pulse_count` 增长。
- 接收低有效 pulse，`rx_raw_count` 增长。
- long-high fault 触发 shutdown。
- duty-limit fault 触发 shutdown。

### 10.2 `tb_tfdu_4ppm_codec.sv`

覆盖：

- 4PPM encode/decode 在理想模型下通过。
- 加入 TFDU 模型 pulse width 和 jitter 后仍通过。
- detect window sweep 产生报告。

### 10.3 `tb_lane0_frame_crc.sv`

覆盖：

- `session=0x2201`。
- `lane_mask=0x1`。
- CRC ok。
- CRC bad 明确计数。
- session mismatch 明确计数。
- mask mismatch 明确计数。

### 10.4 `tb_lane0_ack_only.sv`

覆盖：

- payload lane mask `0x1`。
- ACK lane mask `0x1`。
- B expected A lane mask `0x1`。
- ACK seen。
- ACK lost 后 retry。
- retry exhausted 后 sticky fail。

仿真输出不得覆盖 `legacy/`；统一写入：

```text
evidence/generated/sim/
```

---

## 11. 文档生成

Codex 必须生成以下文档。

### 11.1 `docs/design/KNOWN_ISSUES_FROM_RF_COMM.md`

必须记录：

- 当前可用旧配置是 `LANE0_DEGRADED_RELIABLE_2LANE_STATIC`。
- payload lane mask 为 `0x1`。
- ACK lane mask 为 `0x1`。
- `AB_L1` raw-layer `NO_RX_RAW_PULSE`。
- 旧工程 active XDC 与 IP legacy XDC 冲突。
- 旧工程存在 wrapper/BD/IP 副本漂移风险。
- session/mask 混用会导致协议层假失败。
- B0 endpoint 是 test-only peer，不是最终远端协议设备。
- Ethernet、rotation、真实 8-lane 没有被旧证据证明。

### 11.2 `docs/design/MIGRATION_NOTES.md`

记录：

- 复制了哪些旧文件。
- 哪些旧文件只作为 reference。
- 哪些新文件成为 canonical。
- 新工程如何从 `G1_LANE0_BASELINE` 开始复现。

### 11.3 `docs/design/REGISTER_CONTRACT.md`

从 YAML 生成，不手写。

### 11.4 `docs/design/ACCEPTANCE_MATRIX.md`

至少包含：

| Stage | 状态 | 自动化口径 |
|---|---|---|
| Import RF_COMM | PASS/PENDING | manifest + sha256 |
| Constraint copy | PASS/PENDING | constraint hash equality |
| XDC canonicalization | PASS/PENDING | generated XDC equals active reference |
| TFDU safety static | PASS/PENDING | static rule checks |
| Lane PHY sim | PASS/PENDING | tb pass |
| 4PPM codec sim | PASS/PENDING | tb pass |
| Lane0 frame CRC sim | PASS/PENDING | tb pass |
| Lane0 ACK sim | PASS/PENDING | tb pass |
| Vivado build | PENDING_TOOL/PENDING_HW | no hardware by default |
| PS driver offline | PASS/PENDING | unit tests |
| Ethernet real board | PENDING_HW | not automated unless user authorizes |
| Rotation 600 rpm | PENDING_EXTERNAL_FIXTURE | not automated by Codex |
| 2-hour soak | PENDING_HW | not automated by default |
| 8-lane | PENDING_DESIGN | blocked until lane1 and power strategy resolved |

### 11.5 `docs/design/PENDING_HARDWARE_ACCEPTANCE.md`

明确写：

- 本 plan 默认不运行硬件。
- 所有硬件相关内容仅生成脚本和验收口径。
- `AB_L1` 需要后续在真实硬件上重新跑 raw matrix。
- 任何硬件运行必须使用 safe wrapper，并在运行后 shutdown。

---

## 12. Git 流程

如果新项目是 Git repo，Codex 执行：

```bash
git status -sb
```

导入和生成完成后，只 stage 本次生成/复制文件：

```bash
git add plan.md AGENTS.md agent.md 项目约束\(目标）.txt PROJECT_CONSTRAINTS.txt README.md .gitignore \
  board_profiles config constraints docs legacy rtl sim scripts software evidence
```

提交前运行：

```bash
python scripts/run_offline_gates.py
```

若 gate 失败，不提交，生成 `evidence/generated/offline_gate_summary.md` 并报告失败项。

若 gate 通过，提交信息：

```text
chore: bootstrap RF_COMM TFDU6102 rebuild project
```

不要 push，除非用户明确要求。

---

## 13. 一次性执行顺序

Codex 在新项目根目录中按顺序执行：

```bash
# 1. 创建基础目录和脚本
mkdir -p scripts docs/design docs/legacy docs/constraints docs/datasheets legacy/RF_COMM \
  board_profiles config/profiles config/register_map constraints/active constraints/legacy_conflicts \
  rtl sim/models sim/tb sim/legacy_tb software evidence/imported evidence/generated

# 2. 生成 scripts/import_rf_comm.py
# 3. 运行导入
python scripts/import_rf_comm.py --source auto --no-hardware

# 4. 生成 pinmap 和 canonical XDC
python scripts/generate_pinmap_from_xdc.py \
  --xdc constraints/legacy_conflicts/PORT1.top_active.original.xdc \
  --out board_profiles/ax7010_tfdu_j10_j11_pinmap.csv

python scripts/generate_xdc_from_pinmap.py \
  --pinmap board_profiles/ax7010_tfdu_j10_j11_pinmap.csv \
  --out constraints/active/PORT1.generated.xdc

python scripts/check_xdc_conflicts.py

# 5. 生成 profile、register map、文档和新 RTL skeleton
python scripts/check_project_integrity.py
python scripts/check_tfdu_safety_static.py

# 6. 运行离线 gate
python scripts/run_offline_gates.py
```

若任何一步失败：

1. 不要继续后续阶段。
2. 写入 `evidence/generated/bootstrap_failure.md`。
3. 报告失败命令、退出码、stdout/stderr 摘要和下一步自动修复建议。

---

## 14. 完成判据

本 plan 完成时，必须满足：

```text
PROJECT_BOOTSTRAP_DONE=1
RF_COMM_SOURCE_IMPORTED=1
PROJECT_CONSTRAINTS_COPIED=1
AGENTS_MD_CREATED=1
TFDU_DATASHEET_COPIED_OR_PENDING_RECORDED=1
LEGACY_EVIDENCE_IMPORTED=1
ACTIVE_XDC_ARCHIVED=1
LEGACY_XDC_CONFLICT_ARCHIVED=1
PINMAP_GENERATED=1
CANONICAL_XDC_GENERATED=1
G1_PROFILE_CREATED=1
LANE1_DEFAULT_DISABLED=1
TFDU_SAFETY_DOC_CREATED=1
NEW_RTL_SKELETON_CREATED=1
REGISTER_MAP_SINGLE_SOURCE_CREATED=1
OFFLINE_GATES_RAN=1
NO_HARDWARE_ACTIONS_EXECUTED=1
```

不得声称：

```text
REAL_HARDWARE_PASS
ETHERNET_PASS
ROTATION_PASS
TWO_HOUR_SOAK_PASS
EIGHT_LANE_PASS
AB_L1_FIXED
```

除非用户后续明确授权硬件运行，并产生可追溯日志。

---

## 15. 后续自动化里程碑

本 bootstrap 完成后，继续按以下里程碑推进；每个里程碑仍默认只做自动化离线任务。

### M1：TFDU lane PHY 完整实现

- 完成 `tfdu_lane_phy.sv`。
- 完成 `tfdu6102_behavior_model.sv`。
- 通过 `tb_tfdu_lane_phy_smoke.sv`。
- 通过 `check_tfdu_safety_static.py`。

### M2：4PPM codec 与 frame L1

- 完成 `ir_4ppm_codec.sv`。
- 完成 `ir_frame_l1.sv`。
- 通过 ideal loopback 和 TFDU behavior model loopback。
- 生成 detect-window sweep 报告。

### M3：lane0 ACK/retry

- 完成 `ir_arq_l2.sv`。
- 完成 lane0 ACK-only 仿真。
- 验证 ACK lost、CRC bad、session mismatch、mask mismatch、retry exhausted。

### M4：AXI register contract

- 完成 `ir_axi_regs_new.sv`。
- YAML 生成 C/Python/Markdown。
- PS driver offline stub 通过 readback/commit 测试。

### M5：Vivado non-hardware build

- 若本机有 Vivado，生成 batch Tcl，只做综合/实现/DRC/timing，不连接 hardware。
- 输出 build report 到 `evidence/generated/vivado/`。
- 失败时只修 source/constraints，不运行硬件。

### M6：用户授权后的硬件准备脚本

只生成，不自动运行：

```text
scripts/hw/run_lane0_raw_matrix_safe.ps1
scripts/hw/run_g1_lane0_replay_safe.ps1
scripts/hw/program_tfdu_shutdown_safe.ps1
```

这些脚本必须：

- 默认 refuse unless `-AllowHardware`。
- 运行前打印 profile hash。
- 运行后强制 shutdown。
- 检查 `SHUTDOWN_EXIT=0` 或 `TFDU_SHUTDOWN_PROGRAMMED`。
- 生成 hash manifest。

---

## 16. Codex 最终输出格式

Codex 执行本 plan 后，最终只输出：

```text
BOOTSTRAP_STATUS: PASS 或 FAIL
SOURCE_PROJECT: <detected path>
NEW_PROJECT: <current path>
NO_HARDWARE_ACTIONS_EXECUTED: true
GENERATED_SUMMARY: evidence/generated/offline_gate_summary.md
KEY_NEXT_STEP: <下一步自动化里程碑>
```

如果失败，输出：

```text
BOOTSTRAP_STATUS: FAIL
FAILED_STAGE: <stage>
FAILED_COMMAND: <command>
LOG: evidence/generated/bootstrap_failure.md
NO_HARDWARE_ACTIONS_EXECUTED: true
```
