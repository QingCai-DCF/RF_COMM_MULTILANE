# N03-0 Scope Switch Note

Generated: 2026-06-30 23:32 +08:00

Stage: `N03_NETWORK_FIRST_STATIC_DIRECT_BASELINE`

## Decision

The current project thread is switched from 2-lane IR physical bring-up to a network-first baseline:

```text
PC Ethernet
  -> Zynq PS lwIP / TCP
  -> PS software protocol
  -> AXI-Lite / DMA / synthetic PL path
  -> PS return
  -> PC payload compare
```

Required N03 boundary statements:

```text
2 lane physical unavailable is DEFERRED for network-first phase.
Network tests must not depend on TFDU traffic.
IR TX pins should be idle or TFDU shutdown unless explicitly stated.
```

## Reason

The hard project constraint remains unchanged: the final RF_COMM target is still a reliable ZYNQ-7010 / TFDU-6102 IR data communication system with recovery, status feedback, TCP PC-side control, and later expansion toward multi-lane operation. N03 does not replace that target. It builds the PC-to-PS and PS-to-synthetic-PL software/network baseline first, so physical IR failures do not block TCP protocol, payload compare, DHCP fallback, reconnect, and error handling work.

## Current Physical Baseline

Latest physical report: `reports/P7_01_2lane_raw_matrix_report.md`

```text
P7_2LANE_REMOTE_RAW_MATRIX_PASS = 0
P7_01_2LANE_RAW_MATRIX_RESULT = BLOCK_REQUIRED_LINK_EVIDENCE_MISSING
```

Main physical rows from the latest P7 report:

| Direction | Latest status | N03 interpretation |
| --- | --- | --- |
| `A_TO_B_LANE0` | `PASS_RAW_PULSE` | Diagnostic raw pulse only; not N03 network evidence. |
| `A_TO_B_LANE1` | `FAIL_NO_RX_ACTIVITY` | Physical issue deferred for N03. |
| `B_TO_A_LANE0` | `FAIL_NO_RX_ACTIVITY` | Physical issue deferred for N03. |
| `B_TO_A_LANE1` | `MISSING_EVIDENCE_REQUIRED_LINK` | Physical evidence missing; deferred for N03. |

## Artifact Trace

| Artifact | SHA-256 / status |
| --- | --- |
| `TFDU_VFIR_Client_Array/design_shiboqi_wrapper.bit` | `42458B3B1DC81D090B703DEB937EE00412F5C7A39DBE6DE40B8B75AB1D33284D` |
| `TFDU_VFIR_Client_Array/design_shiboqi_wrapper.xsa` | `AE674988CDC4662E63B85320EC48D629609138D42D0ED97A79A18F16FEF3228B` |
| `software/_vitis_ws/rf_comm_ps_bridge/Debug/rf_comm_ps_bridge.elf` | `0BC5F1C1CAF19CA9B6E8E037D95AB202218290C9C29FE82EE05F45ED30E38D79` |
| `software/_vitis_ws_ps_ps_loopback/rf_comm_ps_ps_loopback/Debug/rf_comm_ps_ps_loopback.elf` | `76B335E06C611B50FAC8B4818CEBEC44CC8F390345C93D1F2D11E4D6F56C0392` |
| Git source base before this package update | `e8384871bb1f171a28e1c6908ee5e9f72b34fb05` |

N03 source file hashes at generation:

| File | SHA-256 |
| --- | --- |
| `software/ps_lwip_bridge/src/main.c` | `0D44475D029A46D52F13E949A20B38EAA89FB320050BB397930D26C2C54FB358` |
| `software/ps_lwip_bridge/src/tcp_bridge.c` | `8E6A28A6C86FBD578FD268BA17EEB0758D074EE4549F46863468E5DD1ABF6FE8` |
| `software/ps_lwip_bridge/src/rf_protocol.h` | `0D3F13AF4A99A4D99A46EC5184C112DED4032EE88035B7C0FA4B319660B831C0` |
| `software/host_client/rf_comm_client.py` | `369F71E23D3C54C90A4170F6C3A688DBB9F7E8622BB152F6E7A5EE0D0DF4BEEA` |
| `software/host_client/run_acceptance.ps1` | `393E500A57D7EF19FF8F7442965D50EBE31CF0DFE1B09EF2048AA81736B073A9` |
| `tools/run_ps_pc_offline_gates.ps1` | `FD1DF24F710EFF91DF5708481FAF2A6AC2C42D1BADE8973EEB9D7688D95FFB8A` |

## N03 Software Baseline Added

- Static fallback IP is aligned to the N03 direct-cable plan: board `192.168.10.2/24`, gateway `192.168.10.1`.
- TCP bridge protocol supports N03 modes:
  - `network_memory_echo`
  - `pspl_synth_loopback`
  - `ir_physical` rejected as deferred with `ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE`.
- TCP bridge protocol also supports an N03 ASCII `COMMAND` frame for safe command coverage:
  - `PING`, `GET_VERSION`, `GET_BUILD_ID`, `READ ...`, `CONFIG payload_bytes ...`, `CONFIG mode ...`, `CLEAR ...`, `START`, `STOP`, and `SHUTDOWN_SAFE`.
  - IR physical starts such as `START ir_tx` and `START 2lane` return `ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE`.
- `software/host_client/run_acceptance.ps1` now exposes:
  - `-Mode n03_commands`
  - `-Mode n03_memory_echo`
  - `-Mode n03_pspl_synth`
  - `-Mode n03_negative`
- `-Mode offline_mock` now covers N03 command protocol, memory echo, PS/PL synthetic loopback, and IR-deferred negative behavior.

## Offline Evidence

Latest N03 offline gate summary: `reports/ps_pc_offline_gates_20260630_233111.summary.txt`

```text
PS_BRIDGE_STATIC_CHECKS_PASS checks=80 dhcp=1 tcp=1 protocol=1 reconnect=1
RF_COMM_PROTOCOL_CONTRACT overall=PASS checks=31 status_fields=16 frame_types=10 config_bits=5 modes=3
Ran 26 tests OK
N03_TCP_PROTOCOL_COMMAND_PASS=1
N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=1
N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=1
N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=1
PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1 n03_commands=1 n03_modes=1
```

This is source/offline/mock evidence only. It does not replace a real board Ethernet run.

## Explicit Non-Claims

The following are not claimed by this N03-0 note:

```text
IR_PHYSICAL_PASS
2LANE_PASS
REAL_IR_DATA_ROUNDTRIP_PASS
ROTATION_PASS
4LANE_PASS
8LANE_PASS
FINAL_TARGET_PASS
```
