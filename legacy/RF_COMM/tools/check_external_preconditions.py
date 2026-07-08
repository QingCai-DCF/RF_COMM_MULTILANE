from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import json
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class CheckRow:
    item: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def latest_report(pattern: str) -> Path | None:
    matches = [path for path in REPORTS.glob(pattern) if path.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda path: path.stat().st_mtime)


def marker_value(text: str, key: str) -> str:
    prefix = key + "="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return ""


def uart_boot_probe_snapshot() -> dict[str, Any]:
    summary = latest_report("ps_uart_boot_probe_*.summary.txt")
    text = read_text(summary)
    log_bytes_text = marker_value(text, "UART_LOG_BYTES")
    try:
        log_bytes = int(log_bytes_text or "0")
    except ValueError:
        log_bytes = 0
    return {
        "summary": rel(summary),
        "verdict": marker_value(text, "UART_PROBE_VERDICT") if summary else "MISSING",
        "log_bytes": log_bytes,
        "board_ip_seen": marker_value(text, "BOARD_IP_SEEN"),
        "match_board_ip": marker_value(text, "MATCH_BOARD_IP"),
        "match_tcp_listen_5001": marker_value(text, "MATCH_TCP_LISTEN_5001"),
        "match_dhcp_static_fallback": marker_value(text, "MATCH_DHCP_STATIC_FALLBACK"),
    }


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def powershell_json(command: str) -> tuple[list[dict[str, Any]], str]:
    full_command = (
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$OutputEncoding=[System.Text.Encoding]::UTF8; "
        "$ErrorActionPreference='SilentlyContinue'; "
        + command
        + " | ConvertTo-Json -Compress -Depth 4"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", full_command],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=20,
    )
    text = proc.stdout.strip()
    if proc.returncode != 0:
        return [], proc.stderr.strip()
    if not text:
        return [], ""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        return [], f"json_parse_error={exc}"
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)], ""
    if isinstance(payload, dict):
        return [payload], ""
    return [], "unexpected_json_shape"


def tcp_probe(host: str, port: int, timeout_s: float) -> bool:
    if not host:
        return False
    try:
        with socket.create_connection((host, port), timeout=timeout_s):
            return True
    except OSError:
        return False


def discover_local_tcp_candidates(
    ipv4_rows: list[dict[str, Any]],
    port: int,
    timeout_s: float,
    max_hosts: int,
) -> dict[str, Any]:
    local_ips: set[str] = set()
    networks: list[ipaddress.IPv4Network] = []
    skipped: list[str] = []
    for row in ipv4_rows:
        ip = str(row.get("IPAddress", ""))
        if not ip or ip.startswith(("127.", "169.254.")):
            continue
        try:
            prefix = int(row.get("PrefixLength", 0))
            network = ipaddress.ip_network(f"{ip}/{prefix}", strict=False)
        except (TypeError, ValueError):
            continue
        if network.version != 4:
            continue
        host_count = max(0, network.num_addresses - 2) if network.num_addresses > 2 else network.num_addresses
        if host_count > max_hosts:
            skipped.append(f"{network}:hosts={host_count}")
            continue
        local_ips.add(ip)
        networks.append(network)

    candidates: set[str] = set()
    for network in networks:
        hosts = [str(host) for host in network.hosts() if str(host) not in local_ips]
        if not hosts:
            continue
        worker_count = min(96, len(hosts))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(tcp_probe, host, port, timeout_s): host for host in hosts}
            for future in as_completed(futures):
                host = futures[future]
                try:
                    if future.result():
                        candidates.add(host)
                except Exception:
                    continue

    return {
        "enabled": True,
        "subnets": [str(network) for network in networks],
        "skipped_subnets": skipped,
        "candidates": sorted(candidates, key=lambda value: ipaddress.ip_address(value)),
        "port": port,
        "timeout": timeout_s,
        "max_hosts": max_hosts,
    }


def classify_ethernet(adapters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for adapter in adapters:
        name = str(adapter.get("Name", ""))
        desc = str(adapter.get("InterfaceDescription", ""))
        joined = f"{name} {desc}".lower()
        if any(token in joined for token in ["wi-fi", "wifi", "wireless", "wlan", "802.11"]):
            continue
        if any(token in joined for token in ["ethernet", "realtek", "gbe", "2.5gbe", "lan"]):
            out.append(adapter)
    return out


def add(rows: list[CheckRow], item: str, status: str, evidence: str, note: str) -> None:
    rows.append(CheckRow(item, status, evidence, note))


def md_table(rows: list[CheckRow]) -> str:
    lines = [
        "| item | status | evidence | note |",
        "| --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                cell.replace("\n", " ").replace("|", "/")
                for cell in [row.item, row.status, row.evidence, row.note]
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only external precondition snapshot for RF_COMM acceptance.")
    parser.add_argument("--target-host", default="192.168.10.2", help="Single-board static fallback IP to probe.")
    parser.add_argument("--target-host-a", default="192.168.10.2", help="AX7010 A static fallback IP to probe.")
    parser.add_argument("--target-host-b", default="192.168.10.3", help="AX7010 B static fallback IP to probe.")
    parser.add_argument("--tcp-port", type=int, default=5001, help="RFCM TCP port.")
    parser.add_argument("--timeout", type=float, default=0.5, help="TCP probe timeout seconds.")
    parser.add_argument("--skip-tcp-probe", action="store_true", help="Do not attempt quick TCP connect probes.")
    parser.add_argument("--require-pc-ip", action="store_true", help="Require the selected PC Ethernet subnet IP.")
    parser.add_argument("--expected-pc-ip", default="192.168.10.1", help="Expected PC-side static IPv4 address.")
    parser.add_argument("--expected-pc-prefix", type=int, default=24, help="Expected PC-side IPv4 prefix length.")
    parser.add_argument("--discover-local-tcp", action="store_true", help="Scan small local Ethernet subnets for TCP candidates.")
    parser.add_argument("--discover-timeout", type=float, default=0.2, help="Per-host discovery TCP timeout seconds.")
    parser.add_argument("--discover-max-hosts", type=int, default=512, help="Maximum hosts per subnet for discovery.")
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)
    rows: list[CheckRow] = []

    constraint = find_constraint()
    xpr = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.xpr"
    wrapper = (
        ROOT
        / "TFDU_VFIR_Client_Array"
        / "TFDU_VFIR_Client.srcs"
        / "sources_1"
        / "imports"
        / "hdl"
        / "design_shiboqi_wrapper.v"
    )
    shutdown_bitstream = ROOT / "shutdown_bitstream" / "tfdu_shutdown_8lane_candidate.bit"
    reduced8_current = read_json(REPORTS / "external_reduced_8lane_frag16_bitstream_current.json")
    reduced8_value = str(reduced8_current.get("bitstream", ""))
    reduced8_bitstream = ROOT / reduced8_value if reduced8_value else None
    if reduced8_bitstream is None or not reduced8_bitstream.exists():
        reduced8_bitstream = REPORTS / "external_reduced_8lane_frag16_bitstream_20260627_065143" / "external_reduced_8lane_frag16_candidate.bit"
    status_consistency = REPORTS / "full_target_status_consistency_current.md"
    real_acceptance_template = REPORTS / "real_acceptance_template" / "real_acceptance_template_manifest.csv"

    adapters, adapter_err = powershell_json(
        "Get-NetAdapter -Physical | Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress,ifIndex"
    )
    ipv4_addresses, ipv4_err = powershell_json(
        "Get-NetIPAddress -AddressFamily IPv4 | Select-Object InterfaceAlias,InterfaceIndex,IPAddress,PrefixLength,AddressState,PrefixOrigin"
    )
    serial_ports, serial_err = powershell_json(
        "Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'COM[0-9]+' } | Select-Object Name,DeviceID,Status"
    )
    latest_uart = uart_boot_probe_snapshot()
    ethernet = classify_ethernet(adapters)
    ethernet_up = [a for a in ethernet if str(a.get("Status", "")).lower() == "up"]
    ethernet_names = {str(a.get("Name", "")) for a in ethernet}
    ethernet_ipv4 = [
        row
        for row in ipv4_addresses
        if str(row.get("InterfaceAlias", "")) in ethernet_names
    ]
    expected_pc_ip_present = any(
        str(row.get("IPAddress", "")) == args.expected_pc_ip
        and int(row.get("PrefixLength", -1)) == args.expected_pc_prefix
        for row in ethernet_ipv4
    )
    local_tcp_discovery: dict[str, Any] = {
        "enabled": False,
        "subnets": [],
        "skipped_subnets": [],
        "candidates": [],
        "port": args.tcp_port,
        "timeout": args.discover_timeout,
        "max_hosts": args.discover_max_hosts,
    }
    if args.discover_local_tcp:
        local_tcp_discovery = discover_local_tcp_candidates(
            ethernet_ipv4,
            args.tcp_port,
            args.discover_timeout,
            args.discover_max_hosts,
        )

    xpr_text = read_text(xpr)
    wrapper_text = read_text(wrapper)
    status_consistency_text = read_text(status_consistency)
    reduced8_hash = sha256(reduced8_bitstream)
    shutdown_hash = sha256(shutdown_bitstream)

    add(
        rows,
        "hard_constraint",
        "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
        sha256(constraint),
        "Project hard constraint file must remain unchanged.",
    )
    add(rows, "no_hardware_programming", "PASS", "NO_HARDWARE_PROGRAMMING=1", "This preflight is read-only.")
    add(rows, "no_uart_write", "PASS", "NO_UART_WRITE=1", "Serial devices are enumerated only.")
    add(rows, "no_tfdu_drive", "PASS", "NO_TFDU_DRIVE=1", "No TX_DATA, bitstream programming, or TFDU drive occurs.")
    add(
        rows,
        "windows_network_query",
        "PASS" if not adapter_err else "WARN",
        f"adapters={len(adapters)} ethernet_candidates={len(ethernet)}",
        adapter_err or "Read Windows physical network adapter list.",
    )
    add(
        rows,
        "ethernet_link",
        "PASS" if ethernet_up else "BLOCKED",
        "; ".join(f"{a.get('Name')}:{a.get('Status')}:{a.get('LinkSpeed')}" for a in ethernet) or "no ethernet adapters classified",
        "At least one physical Ethernet link must be Up before real TCP/DHCP acceptance.",
    )
    add(
        rows,
        "n03_static_pc_ip",
        ("PASS" if expected_pc_ip_present else "BLOCKED") if args.require_pc_ip else "SKIPPED",
        (
            f"expected={args.expected_pc_ip}/{args.expected_pc_prefix} "
            f"present={expected_pc_ip_present} "
            f"ethernet_ipv4="
            + (
                "; ".join(
                    f"{row.get('InterfaceAlias')}:{row.get('IPAddress')}/{row.get('PrefixLength')}"
                    for row in ethernet_ipv4
                )
                or "none"
            )
        ),
        ipv4_err
        or "N03 static direct acceptance requires the PC Ethernet adapter to own the expected static IPv4 address.",
    )
    add(
        rows,
        "serial_ports",
        "PASS" if serial_ports else "WARN",
        "; ".join(str(p.get("Name", "")) for p in serial_ports) or serial_err or "none",
        "UART is useful for IP/debug banners, but real TCP can use known static/DHCP IP.",
    )
    uart_board_ip = str(latest_uart.get("board_ip_seen", ""))
    uart_log_bytes = int(latest_uart.get("log_bytes", 0))
    add(
        rows,
        "latest_uart_boot_probe",
        "INFO_BOARD_IP_HINT"
        if uart_board_ip
        else ("INFO_UART_TEXT_NO_IP" if uart_log_bytes > 0 else "INFO_NO_UART_TEXT"),
        (
            f"summary={latest_uart.get('summary') or 'none'} "
            f"verdict={latest_uart.get('verdict') or 'MISSING'} "
            f"log_bytes={uart_log_bytes} "
            f"board_ip={uart_board_ip or 'none'} "
            f"tcp_5001_seen={latest_uart.get('match_tcp_listen_5001') or '0'} "
            f"dhcp_static_fallback_seen={latest_uart.get('match_dhcp_static_fallback') or '0'}"
        ),
        "Latest UART boot probe is a hint source only; real acceptance still requires TCP/DHCP evidence.",
    )
    add(
        rows,
        "vivado_2023_1_path",
        "PASS" if (Path("D:/Xilinx/Vivado/2023.1/bin/vivado.bat").exists()) else "WARN",
        "D:/Xilinx/Vivado/2023.1/bin/vivado.bat",
        "Vivado 2023.1 batch executable availability.",
    )
    add(
        rows,
        "active_project_safe_state",
        "PASS"
        if 'Path="$PSRCDIR/constrs_1/new/PORT1.xdc"' in xpr_text
        and 'Name="TargetConstrsFile" Val="$PSRCDIR/constrs_1/new/PORT1.xdc"' in xpr_text
        and "[1:0]ir_rx_in_0" in wrapper_text
        and "[1:0]loop_rx_b0" in wrapper_text
        else "FAIL",
        f"{rel(xpr)}; {rel(wrapper)}",
        "Current active project should remain restored to 2-lane/PORT1 unless intentionally changed later.",
    )
    add(
        rows,
        "shutdown_bitstream_available",
        "PASS" if shutdown_hash != "MISSING" else "BLOCKED",
        f"{rel(shutdown_bitstream)} sha256={shutdown_hash}",
        "Required for any future physical TFDU/TX run shutdown step.",
    )
    add(
        rows,
        "reduced_8lane_raw_candidate_available",
        "PASS" if reduced8_hash == "F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778" else "BLOCKED",
        f"{rel(reduced8_bitstream)} sha256={reduced8_hash}",
        "Offline raw 32/16 Mbit/s candidate bitstream is available for review, not real acceptance.",
    )
    add(
        rows,
        "real_acceptance_templates_available",
        "PASS" if real_acceptance_template.exists() else "BLOCKED",
        rel(real_acceptance_template),
        "Future real runs should be validated against structured evidence templates.",
    )
    add(
        rows,
        "status_consistency_gate",
        "PASS" if "RF_COMM_FULL_TARGET_STATUS_CONSISTENCY overall=PASS" in status_consistency_text else "BLOCKED",
        rel(status_consistency),
        "Latest status/matrix/audit/hash/project evidence chain should be internally consistent.",
    )

    tcp_results: dict[str, bool | str] = {}
    if args.skip_tcp_probe:
        tcp_results = {"single": "skipped", "a": "skipped", "b": "skipped"}
    else:
        tcp_results = {
            "single": tcp_probe(args.target_host, args.tcp_port, args.timeout),
            "a": tcp_probe(args.target_host_a, args.tcp_port, args.timeout),
            "b": tcp_probe(args.target_host_b, args.tcp_port, args.timeout),
        }
    add(
        rows,
        "tcp_quick_probe_single_board",
        "PASS" if tcp_results["single"] is True else "BLOCKED",
        f"{args.target_host}:{args.tcp_port}={tcp_results['single']}",
        "Real N03 acceptance needs the board PS bridge reachable over TCP.",
    )
    add(
        rows,
        "tcp_quick_probe_two_ax7010",
        "PASS" if tcp_results["a"] is True and tcp_results["b"] is True else "BLOCKED",
        f"{args.target_host_a}:{args.tcp_port}={tcp_results['a']}; {args.target_host_b}:{args.tcp_port}={tcp_results['b']}",
        "Real N04/A01/S05 acceptance needs both AX7010 endpoints reachable.",
    )
    discovery_candidates = [str(item) for item in local_tcp_discovery.get("candidates", [])]
    add(
        rows,
        "n03_local_tcp_discovery",
        "PASS_CANDIDATE_FOUND"
        if discovery_candidates
        else ("INFO_NO_CANDIDATE" if args.discover_local_tcp else "SKIPPED"),
        (
            f"port={args.tcp_port} "
            f"subnets={','.join(str(item) for item in local_tcp_discovery.get('subnets', [])) or 'none'} "
            f"candidates={','.join(discovery_candidates) if discovery_candidates else 'none'} "
            f"skipped={','.join(str(item) for item in local_tcp_discovery.get('skipped_subnets', [])) or 'none'}"
        ),
        "Read-only TCP connect discovery over small local Ethernet subnets; candidates are hints only, not PASS evidence.",
    )

    blockers = [row.item for row in rows if row.status == "BLOCKED"]
    fails = [row.item for row in rows if row.status == "FAIL"]
    if fails:
        overall = "FAIL"
    elif blockers:
        overall = "BLOCKED_NO_ETHERNET" if "ethernet_link" in blockers else "BLOCKED_EXTERNAL_PRECONDITIONS"
    else:
        overall = "READY_FOR_SAFE_REAL_ACCEPTANCE_PREFLIGHT"

    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "external_preconditions_current.md"
    json_path = REPORTS / "external_preconditions_current.json"
    csv_path = REPORTS / "external_preconditions_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md = [
        "# External Preconditions",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Blockers: `{', '.join(blockers) if blockers else 'none'}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "This is a read-only snapshot of external prerequisites for future real hardware acceptance. It does not replace real TCP/DHCP, two-AX7010, product-loop, rotating-shaft, or 8-lane hardware evidence.",
        "",
        "## Checks",
        "",
        md_table(rows),
        "",
        "## Adapter Snapshot",
        "",
        "```json",
        json.dumps({"ethernet": ethernet, "serial_ports": serial_ports}, indent=2, ensure_ascii=False),
        "```",
        "",
        "```text",
        f"RF_COMM_EXTERNAL_PRECONDITIONS overall={overall} blockers={len(blockers)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "blockers": blockers,
        "checks": [asdict(row) for row in rows],
        "adapters": adapters,
        "ethernet": ethernet,
        "serial_ports": serial_ports,
        "ipv4_addresses": ipv4_addresses,
        "tcp_results": tcp_results,
        "local_tcp_discovery": local_tcp_discovery,
        "latest_uart_boot_probe": latest_uart,
        "n03_expected_pc_ip": {
            "required": args.require_pc_ip,
            "expected_ip": args.expected_pc_ip,
            "expected_prefix": args.expected_pc_prefix,
            "present_on_ethernet": expected_pc_ip_present,
        },
        "artifacts": {
            "constraint": rel(constraint),
            "shutdown_bitstream": rel(shutdown_bitstream),
            "reduced_8lane_bitstream": rel(reduced8_bitstream),
            "status_consistency": rel(status_consistency),
        },
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_EXTERNAL_PRECONDITIONS overall={overall} blockers={len(blockers)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if overall != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
