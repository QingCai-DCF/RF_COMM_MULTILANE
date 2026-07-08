# N03-10 Network-first Acceptance Package

Generated: 2026-07-01T12:58:35

Verdict: `PACKAGE_PARTIAL_REAL_BOARD_PENDING`

This package is a current-state N03 deliverable bundle. It proves source/offline/mock progress, incorporates the latest safe real-board wrapper result when present, and preserves the remaining real-board blockers. It does not claim the final N03 baseline PASS.

## Stage Matrix

| item | title | status | evidence | next required evidence | allowed claim |
| --- | --- | --- | --- | --- | --- |
| N03-0 | scope switch and IR physical deferred matrix | PASS_DEFERRED_GATE | N03_00_scope_switch_note.md; N03_00_ir_physical_deferred_matrix.md | none for scope switch | IR physical is deferred, not failed for N03 |
| N03-1 | static IP direct smoke | BLOCKED_PC_STATIC_IP_NOT_CONFIGURED | reports/n03_static_direct_network_preflight_current.summary.txt; reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt; reports/external_preconditions_current.md; reports/external_preconditions_current.json; reports/external_preconditions_current.csv; external=BLOCKED_EXTERNAL_PRECONDITIONS; external_blockers=n03_static_pc_ip, tcp_quick_probe_single_board, tcp_quick_probe_two_ax7010; local_tcp_5001_candidates=none; target_hints=static_expected=192.168.10.2; PC Ethernet lacks 192.168.10.1/24 static direct IP | board UART/TCP transcript proving ETH link up and TCP connect to 192.168.10.2:5001, or a justified UART/local-discovery board IP with matching safe-wrapper evidence | real static TCP only if safe wrapper N03_STATIC_DIRECT_TCP_PASS=1 |
| N03-2 | TCP hello/status/build-id | PASS_OFFLINE_RECONNECT_10X_REAL_PENDING | reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt; reports/ps_pc_offline_gates_20260701_113607.summary.txt; reports/n03_offline_reconnect_matrix_current.md; reports/n03_offline_reconnect_matrix_current.csv | real board HELLO/STATUS/GET_BUILD_ID transcript | real HELLO covered only if safe wrapper static smoke passed |
| N03-3 | TCP command protocol coverage | PASS_OFFLINE_REAL_PENDING | reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt; reports/ps_pc_offline_gates_20260701_113607.summary.txt; reports/protocol_contract_current.md | real board command matrix with ACK/ERR for all N03 commands | N03_TCP_PROTOCOL_COMMAND_PASS is real only if safe wrapper marker is 1 |
| N03-4 | PC to PS memory echo | PASS_OFFLINE_REAL_PENDING | reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt; reports/n03_network_first_acceptance_safe_20260701_125709.matrix.csv; reports/ps_pc_offline_gates_20260701_113607.summary.txt | real board memory echo matrix with payload_mismatch=0 | N03_TCP_PAYLOAD_MEMORY_ECHO_PASS is real only if safe wrapper marker is 1 |
| N03-5 | PC to PS to PL synthetic loopback | PASS_OFFLINE_REAL_PENDING | reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt; reports/n03_network_first_acceptance_safe_20260701_125709.matrix.csv; reports/ps_pc_offline_gates_20260701_113607.summary.txt | real board PS/PL synthetic matrix with DMA counters and payload_mismatch=0 | N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS is real only if safe wrapper marker is 1 |
| N03-6 | DHCP timeout plus static fallback | SOURCE_READY_UART_INCONCLUSIVE_TCP_PENDING | reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt; reports/ps_lwip_bridge_static_current.md; reports/ps_uart_boot_probe_20260701_124132.summary.txt; target_hints=static_expected=192.168.10.2 | UART DHCP_TIMEOUT and STATIC_FALLBACK_IP=192.168.10.2 plus TCP reconnect evidence | N03_DHCP_FALLBACK_PASS is real only if safe wrapper marker is 1 with UART/TCP/memory evidence |
| N03-7 | PC-hosted DHCP lease | DEFERRED_NO_PC_DHCP_SERVER_PREFLIGHTED | reports/n03_pc_hosted_dhcp_preflight_current.summary.txt; reports/n03_pc_hosted_dhcp_preflight_current.md; reports/n03_pc_hosted_dhcp_preflight_current.json; status=DEFERRED_NO_PC_DHCP_SERVER; next_action=configure_windows_ics_or_standalone_dhcp_server; ics_query_requires_admin=1 | DHCP DISCOVER/OFFER/REQUEST/ACK and board IP in pool | PC DHCP preflight only; no DHCP lease pass |
| N03-8 | payload matrix and throughput | PASS_OFFLINE_LOCALHOST_MATRIX_REAL_THROUGHPUT_PENDING | reports/ps_pc_offline_gates_20260701_113607.summary.txt; reports/n03_offline_payload_matrix_current.md; reports/n03_offline_payload_matrix_current.csv | real board 16..8192 byte payload matrix and throughput CSV | offline localhost payload matrix/tooling only; no real throughput pass |
| N03-9 | link recovery and negative tests | PASS_OFFLINE_RECONNECT_20X_PAYLOAD_PROTOCOL_NEGATIVE_REAL_LINK_PENDING | reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt; reports/n03_network_first_acceptance_safe_20260701_125709.matrix.csv; reports/ps_pc_offline_gates_20260701_113607.summary.txt; reports/n03_offline_reconnect_matrix_current.md; reports/n03_offline_reconnect_matrix_current.csv; reports/no_ethernet_network_boundary_evidence_current.md; reports/ps_lwip_bridge_static_current.md | real reconnect/disconnect matrix and negative command matrix | offline 10x/20x reconnect, payload echo, bad-arg negatives, and source/boundary protocol-fault negatives only; real link recovery only if safe wrapper reconnect and negative markers are 1 |
| N03-10 | network-first acceptance package | PACKAGE_PARTIAL_REAL_BOARD_PENDING | evidence/n03_network_first; reports/n03_static_direct_network_preflight_current.md; reports/n03_network_first_acceptance_safe_20260701_125709.md; reports/n03_network_first_readiness_current.md; reports/n03_current_state_gate_current.md; reports/real_acceptance_runbook_current.md | N03-1..N03-6, N03-8, and N03-9 real board evidence | package is ready for review, not final N03 pass |

## Current Source/Offline Evidence

- Offline summary: `reports/ps_pc_offline_gates_20260701_113607.summary.txt`
- Offline app payload segmentation: `PASS` (`8192_bytes_over_512_byte_rfcm_frames` when present)
- Offline payload matrix: `PASS`
- Offline payload matrix report: `reports/n03_offline_payload_matrix_current.md`
- Offline payload matrix CSV: `reports/n03_offline_payload_matrix_current.csv`
- Offline payload matrix JSON: `reports/n03_offline_payload_matrix_current.json`
- Offline HELLO/STATUS reconnect 10x: `PASS`
- Offline payload reconnect 20x: `PASS`
- Offline reconnect matrix report: `reports/n03_offline_reconnect_matrix_current.md`
- Offline reconnect matrix CSV: `reports/n03_offline_reconnect_matrix_current.csv`
- Offline reconnect matrix JSON: `reports/n03_offline_reconnect_matrix_current.json`
- Offline reconnect payload echo: `PASS`
- Offline bad-argument negatives: `PASS`
- Offline/source protocol-fault negatives: `PASS`
- No-Ethernet boundary report: `reports/no_ethernet_network_boundary_evidence_current.md`
- No-Ethernet boundary CSV: `reports/no_ethernet_network_boundary_evidence_current.csv`
- No-Ethernet boundary JSON: `reports/no_ethernet_network_boundary_evidence_current.json`
- N03 static direct PC preflight summary: `reports/n03_static_direct_network_preflight_current.summary.txt`
- N03 static direct PC preflight report: `reports/n03_static_direct_network_preflight_current.md`
- N03 static direct PC preflight JSON: `reports/n03_static_direct_network_preflight_current.json`
- N03 static direct admin apply helper: `tools/apply_n03_static_direct_network_admin.ps1`
- N03 PC-hosted DHCP preflight summary: `reports/n03_pc_hosted_dhcp_preflight_current.summary.txt`
- N03 PC-hosted DHCP preflight report: `reports/n03_pc_hosted_dhcp_preflight_current.md`
- N03 PC-hosted DHCP preflight JSON: `reports/n03_pc_hosted_dhcp_preflight_current.json`
- N03 PC-hosted DHCP preflight status: `DEFERRED_NO_PC_DHCP_SERVER`
- N03 PC-hosted DHCP next action: `configure_windows_ics_or_standalone_dhcp_server`
- N03 PC-hosted DHCP ICS query requires admin: `1`
- N03 PC-hosted DHCP standalone IP command: `New-NetIPAddress -InterfaceAlias "以太网" -IPAddress 192.168.20.1 -PrefixLength 24 -SkipAsSource $false`
- N03 PC-hosted DHCP ICS GUI command: `control.exe ncpa.cpl`
- N03 readiness audit report: `reports/n03_network_first_readiness_current.md`
- N03 readiness audit CSV: `reports/n03_network_first_readiness_current.csv`
- N03 readiness audit JSON: `reports/n03_network_first_readiness_current.json`
- N03 current state gate summary: `reports/n03_current_state_gate_current.summary.txt`
- N03 current state gate report: `reports/n03_current_state_gate_current.md`
- N03 current state gate JSON: `reports/n03_current_state_gate_current.json`
- N03 real board handoff: `evidence/n03_network_first/N03_real_board_handoff.md`
- N03 real board handoff CSV: `evidence/n03_network_first/N03_real_board_handoff.csv`
- N03 real board handoff JSON: `evidence/n03_network_first/N03_real_board_handoff.json`
- Real acceptance runbook overall: `WAITING_FOR_REAL_HARDWARE`
- Real acceptance runbook report: `reports/real_acceptance_runbook_current.md`
- Real acceptance runbook JSON: `reports/real_acceptance_runbook_current.json`
- Real acceptance runbook CSV: `reports/real_acceptance_runbook_current.csv`
- Latest elevated static setup launch summary: `reports/n03_static_direct_network_preflight_20260701_123045.summary.txt`
- Latest elevated static setup launch pending or declined: `1`
- Latest non-admin static setup apply refusal summary: `reports/n03_static_direct_network_preflight_20260701_105835.summary.txt`
- Latest UART boot probe summary: `reports/ps_uart_boot_probe_20260701_124132.summary.txt`
- Latest UART boot probe verdict: `INCONCLUSIVE_NO_UART_TEXT`
- Latest UART captured bytes: `0`
- UART board IP hint: `none`
- Safe real-board wrapper summary: `reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt`
- Safe real-board wrapper report: `reports/n03_network_first_acceptance_safe_20260701_125709.md`
- Safe real-board wrapper matrix: `reports/n03_network_first_acceptance_safe_20260701_125709.matrix.csv`
- Static PS bridge report: `reports/ps_lwip_bridge_static_current.md`
- Protocol contract report: `reports/protocol_contract_current.md`
- External preconditions overall: `BLOCKED_EXTERNAL_PRECONDITIONS`
- External preconditions blockers: `n03_static_pc_ip, tcp_quick_probe_single_board, tcp_quick_probe_two_ax7010`
- Local TCP 5001 discovery subnets: `192.168.1.0/24`
- Local TCP 5001 discovery candidates: `none`
- N03 target hints: `static_expected=192.168.10.2`
- External preconditions report: `reports/external_preconditions_current.md`
- External preconditions JSON: `reports/external_preconditions_current.json`
- External preconditions CSV: `reports/external_preconditions_current.csv`
- P7 physical report: `reports/P7_01_2lane_raw_matrix_report.md`

## Final N03 Pass Gate

Do not mark the final N03 network-first baseline as passed until N03-1..N03-6, N03-8, and N03-9 have real board evidence with payload_mismatch=0 and reconnect/link recovery evidence. N03-7 may remain `DEFERRED_NO_PC_DHCP_SERVER_PREFLIGHTED` if no PC DHCP server is available, or `PC_DHCP_SERVER_READY_LEASE_PENDING` until a real lease and TCP HELLO/STATUS pass are captured.

## Non-Claims

```text
IR_PHYSICAL_PASS=0
2LANE_PASS=0
REAL_IR_DATA_ROUNDTRIP_PASS=0
ROTATION_PASS=0
4LANE_PASS=0
8LANE_PASS=0
FINAL_TARGET_PASS=0
```
