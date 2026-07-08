# N03-0 IR Physical Deferred Matrix

Generated: 2026-06-30 23:20 +08:00

Stage: `N03_NETWORK_FIRST_STATIC_DIRECT_BASELINE`

## Boundary

```text
2 lane physical unavailable is DEFERRED for network-first phase.
Network tests must not depend on TFDU traffic.
IR TX pins should be idle or TFDU shutdown unless explicitly stated.
```

## Deferred Matrix

| Item | Current evidence | N03 status | Rationale |
| --- | --- | --- | --- |
| 2-lane raw physical matrix | `reports/P7_01_2lane_raw_matrix_report.md` reports `P7_2LANE_REMOTE_RAW_MATRIX_PASS = 0` | `DEFERRED_PHYSICAL_NOT_N03_FAIL` | N03 network-first can proceed without proving 2-lane physical links. |
| `A_TO_B_LANE0` physical raw pulse | `PASS_RAW_PULSE` in latest P7 raw matrix | `DIAGNOSTIC_ONLY` | Raw pulse evidence is not TCP, payload echo, or IR data roundtrip evidence. |
| `A_TO_B_LANE1` physical raw pulse | `FAIL_NO_RX_ACTIVITY` | `DEFERRED_PHYSICAL` | Physical RX issue remains for later IR bring-up. |
| `B_TO_A_LANE0` physical raw pulse | `FAIL_NO_RX_ACTIVITY` | `DEFERRED_PHYSICAL` | Physical RX issue remains for later IR bring-up. |
| `B_TO_A_LANE1` physical raw pulse | `MISSING_EVIDENCE_REQUIRED_LINK` | `DEFERRED_PHYSICAL_EVIDENCE_MISSING` | Missing physical evidence is not promoted to PASS or used as N03 network blocker. |
| TCP `CONFIG mode ir_physical` | Host negative test receives `ERR_DEFERRED_IR_PHYSICAL_UNAVAILABLE` | `PASS_DEFERRED_GUARD` | N03 TCP command surface must not accidentally start TFDU traffic. |
| TCP `CONFIG mode network_memory_echo` | Offline/mock acceptance reports `N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=1` | `PASS_SOURCE_OFFLINE` | Validates PC-side protocol and payload compare without PL/TFDU dependency. |
| TCP `CONFIG mode pspl_synth_loopback` | Offline/mock acceptance reports `N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=1` | `PASS_SOURCE_OFFLINE` | Validates N03 mode plumbing and expected payload compare path; real board PS/PL run remains required. |
| DHCP timeout static fallback | Source static check PASS; board fallback IP now `192.168.10.2` | `SOURCE_READY_REAL_BOARD_PENDING` | Real DHCP timeout/fallback still requires board Ethernet/UART evidence. |
| PC-hosted DHCP lease | No PC DHCP server run recorded in this N03-0 evidence | `DEFERRED_NO_PC_DHCP_SERVER` | Allowed by the N03 plan when no PC DHCP server evidence is available. |
| TFDU traffic during N03 network tests | N03 modes force IR enable off; `ir_physical` mode is rejected | `FORBIDDEN_UNLESS_EXPLICIT` | Network tests must not depend on TFDU traffic. |

## Claim Gate

| Claim | Allowed now? | Status |
| --- | --- | --- |
| `N03_TCP_PROTOCOL_COMMAND_PASS` | Partial | Source/offline command coverage is present; real board command coverage still pending. |
| `N03_TCP_PAYLOAD_MEMORY_ECHO_PASS` | Partial | Offline/mock PASS only; real board run pending. |
| `N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS` | Partial | Offline/mock PASS only; real board PS/PL run pending. |
| `N03_DHCP_FALLBACK_PASS` | Partial | Source ready; real board fallback run pending. |
| `N03_PC_HOSTED_DHCP_LEASE_PASS` | No | `DEFERRED_NO_PC_DHCP_SERVER`. |
| `N03_LINK_RECOVERY_PASS` | Partial | Offline reconnect coverage present; real link interruption/reconnect pending. |
| `IR_PHYSICAL_PASS` | No | Deferred. |
| `2LANE_PASS` | No | Deferred. |
| `REAL_IR_DATA_ROUNDTRIP_PASS` | No | Deferred. |
| `ROTATION_PASS` | No | Out of N03 scope. |
| `FINAL_TARGET_PASS` | No | Out of N03 scope. |

## N03 Advancement Rule

N03 network-first work can continue when the network and software tests keep these properties true:

```text
NO_TFDU_DRIVE=1
NO_IR_PHYSICAL_PASS_CLAIM=1
NO_2LANE_PASS_CLAIM=1
PAYLOAD_MISMATCH=0 for accepted network/synthetic payload tests
IR_PHYSICAL_MODE_RETURNS_ERR_DEFERRED=1
```
