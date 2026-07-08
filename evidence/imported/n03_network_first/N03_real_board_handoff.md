# N03 Real Board Handoff

Generated: 2026-07-01T12:58:35

This handoff is the ordered entry point for continuing the N03 network-first plan once the board Ethernet link is available. It does not configure networking, run hardware, or claim a real-board pass by itself.

- Current external preconditions: `BLOCKED_EXTERNAL_PRECONDITIONS`
- Current external blockers: `n03_static_pc_ip, tcp_quick_probe_single_board, tcp_quick_probe_two_ax7010`
- Local TCP 5001 discovery subnets: `192.168.1.0/24`
- Local TCP 5001 discovery candidates: `none`
- UART board IP hint: `none`
- Candidate target command: `powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_n03_network_first_acceptance_safe.ps1 -TargetHost <candidate-ip-from-uart-or-local-tcp> -Port 5001 -ComPort COM3 -UseLatestTargetHint -SkipStaticDirectPreflight -ReconnectCycles 20 -MatrixRepeat 100 -SustainedSeconds 60 -LongSeconds 300`
- N03 PC-hosted DHCP next action: `configure_windows_ics_or_standalone_dhcp_server`
- N03 PC-hosted DHCP ICS query requires admin: `1`
- N03 PC-hosted DHCP standalone IP command: `New-NetIPAddress -InterfaceAlias "以太网" -IPAddress 192.168.20.1 -PrefixLength 24 -SkipAsSource $false`
- N03 PC-hosted DHCP ICS GUI command: `control.exe ncpa.cpl`
- Current runbook: `WAITING_FOR_REAL_HARDWARE`
- Current blocker: `PC Ethernet lacks 192.168.10.1/24 static direct IP`
- Latest elevated static setup pending or declined: `1`
- Current gate report: `reports/n03_current_state_gate_current.md`
- Safe wrapper summary: `reports/n03_network_first_acceptance_safe_20260701_125709.summary.txt`

## Ordered Commands

| step | when | command | expected evidence | pass boundary |
| --- | --- | --- | --- | --- |
| 0_connect_and_prepare | Before any real N03 acceptance run | powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\apply_n03_static_direct_network_admin.ps1 | reports/n03_static_direct_network_preflight_current.summary.txt | PC_ETHERNET_LINK_UP=1 and PC_EXPECTED_STATIC_IP_PRESENT=1 only; no board TCP pass yet |
| 1_current_state_gate | After Ethernet is plugged in and static IP is configured | powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_n03_current_state_gate.ps1 -TimeoutSeconds 3 | reports/n03_current_state_gate_current.summary.txt | N03_CURRENT_STATE_GATE_STATUS remains authoritative; do not claim final pass from preflight alone |
| 2_real_static_direct_acceptance | Only after 192.168.10.2:5001 is reachable | powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_n03_network_first_acceptance_safe.ps1 -TargetHost 192.168.10.2 -Port 5001 -ComPort COM3 -ReconnectCycles 20 -MatrixRepeat 100 -SustainedSeconds 60 -LongSeconds 300 | reports/n03_network_first_acceptance_<stamp>.*/ and reports/n03_network_first_acceptance_safe_<stamp>.* | Real N03-1..N03-5/N03-9 claims require non-dry-run safe wrapper markers and clean logs |
| 2a_candidate_target_acceptance | Only if UART BOARD_IP_SEEN or local TCP discovery identifies a board IP different from 192.168.10.2 | powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\run_n03_network_first_acceptance_safe.ps1 -TargetHost <candidate-ip-from-uart-or-local-tcp> -Port 5001 -ComPort COM3 -UseLatestTargetHint -SkipStaticDirectPreflight -ReconnectCycles 20 -MatrixRepeat 100 -SustainedSeconds 60 -LongSeconds 300 | reports/external_preconditions_current.json plus safe-wrapper logs for the candidate target | Candidate IP evidence is only a routing hint until the safe wrapper records real TCP HELLO, payload, reconnect, and clean error counters |
| 3_dhcp_fallback_capture | After board boots with DHCP client and no PC DHCP server | capture UART DHCP_START/DHCP_TIMEOUT/STATIC_FALLBACK_IP=192.168.10.2/TCP_READY, then rerun the safe wrapper | reports/ps_uart_boot_probe_<stamp>.summary.txt plus N03 safe wrapper logs | DHCP timeout/static fallback pass also requires real TCP HELLO and memory echo after fallback |
| 4_optional_pc_hosted_dhcp | Only if N03-7 is required and PC DHCP service is intentionally configured | powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\check_n03_pc_hosted_dhcp_preflight.ps1 | reports/n03_pc_hosted_dhcp_preflight_current.summary.txt | Preflight is not a lease pass; next_action=configure_windows_ics_or_standalone_dhcp_server; lease pass requires DISCOVER/OFFER/REQUEST/ACK and TCP HELLO/STATUS |
| 5_rebuild_package | After any new real safe-wrapper evidence is captured | python .\tools\build_n03_network_first_package.py | evidence/n03_network_first/N03_10_network_first_acceptance_package.md | Package may claim final N03 only after required real-board gates pass; never claim IR/2-lane/rotation/final target here |

## Log Index

- PC logs: `reports/n03_network_first_acceptance_<stamp>/*.out.log` and `*.err.log` from the safe wrapper.
- UART logs: `reports/n03_network_first_acceptance_<stamp>/uart_probe.out.log` and `reports/ps_uart_boot_probe_<stamp>.*` when captured.
- CSV evidence: `reports/n03_network_first_acceptance_safe_<stamp>.matrix.csv`, `reports/n03_offline_payload_matrix_current.csv`, and `reports/n03_offline_reconnect_matrix_current.csv`.
- Vivado/Vitis build logs: attach only if the bit/ELF is rebuilt for N03; the current safe wrapper does not program FPGA or rebuild artifacts.

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
