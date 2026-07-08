#!/usr/bin/env python3
"""Audit current N03 network-first readiness against the plan gates."""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EVIDENCE = ROOT / "evidence" / "n03_network_first"


@dataclass
class ReadinessItem:
    item: str
    requirement: str
    status: str
    evidence: str
    blocker: str
    next_action: str


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="replace")
    return data.decode("utf-8", errors="replace")


def read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        payload = json.loads(read_text(path))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def latest(pattern: str) -> Path | None:
    matches = list(REPORTS.glob(pattern))
    if not matches:
        return None
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def current(name: str) -> Path | None:
    path = REPORTS / name
    return path if path.exists() else None


def rel(path: Path | None) -> str:
    if path is None:
        return "MISSING"
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def marker(text: str, value: str) -> bool:
    return value in text


def marker_value(text: str, key: str) -> str:
    prefix = key + "="
    for line in text.splitlines():
        if line.startswith(prefix):
            return line.split("=", 1)[1].strip()
    return ""


def read_stage_rows() -> list[dict[str, str]]:
    path = EVIDENCE / "N03_stage_matrix.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else ["item", "status"]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def md_table(rows: list[ReadinessItem]) -> str:
    out = [
        "| item | requirement | status | evidence | blocker | next action |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        out.append(
            "| "
            + " | ".join(
                str(value).replace("|", "/").replace("\n", " ")
                for value in (
                    row.item,
                    row.requirement,
                    row.status,
                    row.evidence,
                    row.blocker,
                    row.next_action,
                )
            )
            + " |"
        )
    return "\n".join(out)


def scan_forbidden_claims() -> list[str]:
    keys = [
        "N03_NETWORK_FIRST_STATIC_DIRECT_BASELINE_PASS",
        "IR_PHYSICAL_PASS",
        "2LANE_PASS",
        "FINAL_TARGET_PASS",
        "REAL_IR_DATA_ROUNDTRIP_PASS",
        "ROTATION_PASS",
        "4LANE_PASS",
        "8LANE_PASS",
        "N03_PC_HOSTED_DHCP_LEASE_PASS",
    ]
    roots = [
        EVIDENCE,
        ROOT / "software" / "host_client",
        ROOT / "software" / "ps_lwip_bridge",
        ROOT / "tools",
    ]
    suffixes = {".py", ".ps1", ".md", ".csv", ".txt", ".json", ".c", ".h"}
    hits: list[str] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in suffixes:
                continue
            text = read_text(path)
            for key in keys:
                if re.search(rf"{re.escape(key)}\s*=\s*1\b", text):
                    hits.append(f"{rel(path)}:{key}")
    return sorted(set(hits))


def external_next_action(blockers: list[str]) -> str:
    if not blockers:
        return "none"
    if "ethernet_link" in blockers:
        return "connect board Ethernet, confirm link up, then rerun current state gate"
    if "n03_static_pc_ip" in blockers:
        return "configure PC Ethernet static IP 192.168.10.1/24, then rerun current state gate"
    if "tcp_quick_probe_single_board" in blockers:
        return "confirm board PS TCP service is running on 192.168.10.2:5001, then rerun current state gate"
    return "clear external precondition blockers, then rerun current state gate"


def collect_items() -> list[ReadinessItem]:
    stage_rows = read_stage_rows()
    stage = {row.get("item", ""): row for row in stage_rows}

    safe_summary = latest("n03_network_first_acceptance_safe_*.summary.txt")
    safe_text = read_text(safe_summary)
    offline_summary = latest("ps_pc_offline_gates_*.summary.txt")
    offline_text = read_text(offline_summary)
    static_summary = current("n03_static_direct_network_preflight_current.summary.txt")
    static_text = read_text(static_summary)
    pc_dhcp_summary = current("n03_pc_hosted_dhcp_preflight_current.summary.txt")
    pc_dhcp_text = read_text(pc_dhcp_summary)
    payload_summary = current("n03_offline_payload_matrix_current.summary.txt")
    payload_text = read_text(payload_summary)
    reconnect_summary = current("n03_offline_reconnect_matrix_current.summary.txt")
    reconnect_text = read_text(reconnect_summary)
    uart_summary = latest("ps_uart_boot_probe_*.summary.txt")
    uart_text = read_text(uart_summary)
    external_md = current("external_preconditions_current.md")
    external_json = current("external_preconditions_current.json")
    external_csv = current("external_preconditions_current.csv")
    external = read_json(external_json)
    external_overall = str(external.get("overall") or "MISSING")
    external_blockers_raw = external.get("blockers", [])
    external_blockers = [str(item) for item in external_blockers_raw] if isinstance(external_blockers_raw, list) else []
    external_evidence = f"{rel(external_md)}; {rel(external_json)}; {rel(external_csv)}"

    safe_dry_run = marker(safe_text, "N03_DRY_RUN=1")
    static_real = marker(safe_text, "N03_STATIC_DIRECT_TCP_PASS=1") and not safe_dry_run
    command_real = marker(safe_text, "N03_TCP_PROTOCOL_COMMAND_PASS=1") and not safe_dry_run
    memory_real = marker(safe_text, "N03_TCP_PAYLOAD_MEMORY_ECHO_PASS=1") and not safe_dry_run
    synth_real = marker(safe_text, "N03_TCP_TO_PSPL_SYNTHETIC_LOOPBACK_PASS=1") and not safe_dry_run
    link_real = marker(safe_text, "N03_LINK_RECOVERY_PASS=1") and not safe_dry_run
    negative_real = marker(safe_text, "N03_IR_PHYSICAL_DEFERRED_NEGATIVE_PASS=1") and not safe_dry_run
    dhcp_fallback_real = marker(safe_text, "N03_DHCP_FALLBACK_PASS=1") and not safe_dry_run

    static_blockers = [
        line.split("=", 1)[1].strip()
        for line in static_text.splitlines()
        if line.startswith("N03_STATIC_DIRECT_NETWORK_BLOCKER=")
    ]
    combined_static_blockers = list(dict.fromkeys(static_blockers + [f"external:{item}" for item in external_blockers]))
    static_next = marker_value(static_text, "N03_STATIC_DIRECT_NETWORK_NEXT_ACTION")
    safe_blocker = marker_value(safe_text, "N03_BLOCKED_REASON")
    pc_dhcp_status = marker_value(pc_dhcp_text, "N03_PC_HOSTED_DHCP_PREFLIGHT_STATUS")
    pc_dhcp_ready = marker(pc_dhcp_text, "N03_PC_HOSTED_DHCP_SERVER_READY=1")
    pc_dhcp_lease = marker(pc_dhcp_text, "N03_PC_HOSTED_DHCP_LEASE_PASS" + "=1")
    offline_gate = marker(offline_text, "PS_PC_OFFLINE_GATES_PASS")
    payload_offline = marker(offline_text + "\n" + payload_text, "N03_OFFLINE_PAYLOAD_MATRIX_PASS=1")
    reconnect_offline = marker(reconnect_text + "\n" + offline_text, "N03_OFFLINE_RECONNECT_PAYLOAD_20X_PASS=1")

    items: list[ReadinessItem] = []
    items.append(
        ReadinessItem(
            "N03-0",
            "Scope switch and IR physical deferred matrix are present.",
            "PASS_DEFERRED_GATE" if stage.get("N03-0", {}).get("status") == "PASS_DEFERRED_GATE" else "MISSING",
            stage.get("N03-0", {}).get("evidence", "MISSING"),
            "",
            "none",
        )
    )
    items.append(
        ReadinessItem(
            "N03-ext",
            "Current external Ethernet/TCP preconditions are recorded before real N03 acceptance.",
            external_overall if external_overall != "MISSING" else "MISSING_EXTERNAL_PRECONDITIONS",
            external_evidence,
            ";".join(external_blockers),
            external_next_action(external_blockers),
        )
    )
    items.append(
        ReadinessItem(
            "N03-1",
            "Static direct PC-to-board Ethernet TCP smoke passes on real board.",
            "PASS_REAL_BOARD" if static_real else "BLOCKED_REAL_BOARD",
            f"{rel(static_summary)}; {rel(safe_summary)}; {external_evidence}",
            ";".join(combined_static_blockers) or safe_blocker or "real_static_tcp_missing",
            static_next or "connect board Ethernet, configure 192.168.10.1/24, rerun safe acceptance",
        )
    )
    items.append(
        ReadinessItem(
            "N03-2",
            "Real TCP HELLO/STATUS/GET_BUILD_ID and reconnect session evidence exists.",
            "PASS_REAL_BOARD" if static_real else "PASS_OFFLINE_REAL_PENDING",
            f"{rel(safe_summary)}; {rel(reconnect_summary)}",
            "" if static_real else "real_hello_status_build_id_missing",
            "rerun safe acceptance after N03-1 is reachable",
        )
    )
    items.append(
        ReadinessItem(
            "N03-3",
            "Real TCP command matrix returns explicit ACK/ERR for supported and negative commands.",
            "PASS_REAL_BOARD" if command_real else "PASS_OFFLINE_REAL_PENDING",
            f"{rel(safe_summary)}; {rel(offline_summary)}",
            "" if command_real else "real_command_matrix_missing",
            "rerun safe acceptance command mode on real board",
        )
    )
    items.append(
        ReadinessItem(
            "N03-4",
            "Real PC-to-PS memory echo matrix has payload_mismatch=0.",
            "PASS_REAL_BOARD" if memory_real else "PASS_OFFLINE_REAL_PENDING",
            f"{rel(safe_summary)}; {rel(offline_summary)}",
            "" if memory_real else "real_memory_echo_matrix_missing",
            "run real memory echo matrix after TCP reachability",
        )
    )
    items.append(
        ReadinessItem(
            "N03-5",
            "Real PC-to-PS-to-PL synthetic loopback matrix has clean DMA and payload counters.",
            "PASS_REAL_BOARD" if synth_real else "PASS_OFFLINE_REAL_PENDING",
            f"{rel(safe_summary)}; {rel(offline_summary)}",
            "" if synth_real else "real_pspl_synth_matrix_missing",
            "run real PS/PL synthetic loopback matrix after TCP reachability",
        )
    )
    items.append(
        ReadinessItem(
            "N03-6",
            "DHCP timeout is observed and static fallback IP reaches TCP on real board.",
            "PASS_REAL_BOARD" if dhcp_fallback_real else "SOURCE_READY_REAL_PENDING",
            f"{rel(safe_summary)}; {rel(uart_summary)}; reports/ps_lwip_bridge_static_current.md",
            "" if dhcp_fallback_real else "real_safe_wrapper_dhcp_fallback_missing",
            "run safe acceptance after UART shows DHCP_TIMEOUT/STATIC_FALLBACK_IP/TCP_READY and TCP is reachable",
        )
    )
    items.append(
        ReadinessItem(
            "N03-7",
            "Optional PC-hosted DHCP lease is either real-pass or explicitly deferred by preflight.",
            "PASS_OPTIONAL_REAL_BOARD" if pc_dhcp_lease else ("DEFERRED_PREFLIGHTED" if not pc_dhcp_ready else "READY_LEASE_PENDING"),
            rel(pc_dhcp_summary),
            "" if pc_dhcp_lease else pc_dhcp_status or "no_pc_dhcp_lease_evidence",
            "start/configure PC DHCP only if N03-7 is required, then capture DISCOVER/OFFER/REQUEST/ACK",
        )
    )
    items.append(
        ReadinessItem(
            "N03-8",
            "Real 16..8192 byte payload throughput matrix is captured with payload_mismatch=0.",
            "PASS_REAL_BOARD" if memory_real and synth_real and static_real else ("PASS_OFFLINE_REAL_THROUGHPUT_PENDING" if payload_offline else "MISSING"),
            f"{rel(payload_summary)}; {rel(offline_summary)}",
            "" if memory_real and synth_real and static_real else "real_payload_throughput_matrix_missing",
            "run real payload matrix after N03-1 TCP reachability",
        )
    )
    items.append(
        ReadinessItem(
            "N03-9",
            "Real reconnect/disconnect and negative command matrix passes.",
            "PASS_REAL_BOARD" if link_real and negative_real else ("PASS_OFFLINE_REAL_LINK_PENDING" if reconnect_offline else "MISSING"),
            f"{rel(reconnect_summary)}; {rel(safe_summary)}",
            "" if link_real and negative_real else "real_link_recovery_negative_matrix_missing",
            "run real 20x reconnect, cable/reconnect, and negative matrix after N03-1",
        )
    )

    required_real_ids = {"N03-1", "N03-2", "N03-3", "N03-4", "N03-5", "N03-6", "N03-8", "N03-9"}
    required_real = [item for item in items if item.item in required_real_ids]
    final_ready = all(item.status == "PASS_REAL_BOARD" for item in required_real)
    items.append(
        ReadinessItem(
            "N03-10",
            "Acceptance package can claim final N03 network-first baseline only when required real-board gates pass.",
            "READY_TO_CLAIM_FINAL" if final_ready else "PACKAGE_PARTIAL_REAL_BOARD_PENDING",
            "evidence/n03_network_first; reports/n03_network_first_readiness_current.md",
            "" if final_ready else "required_real_board_evidence_missing",
            "do not mark final N03 pass until N03-1..N03-6, N03-8, and N03-9 are PASS_REAL_BOARD",
        )
    )
    return items


def render_markdown(items: list[ReadinessItem], forbidden_hits: list[str]) -> str:
    blockers = [item for item in items if item.blocker]
    final_ready = items[-1].status == "READY_TO_CLAIM_FINAL" and not forbidden_hits
    external_item = next((item for item in items if item.item == "N03-ext"), None)
    external_status = external_item.status if external_item is not None else "MISSING"
    external_blocker_count = (
        len([part for part in external_item.blocker.split(";") if part])
        if external_item is not None
        else 0
    )
    return "\n".join(
        [
            "# N03 Network-first Readiness Audit",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            f"Verdict: `{'PASS_READY_TO_CLAIM_FINAL' if final_ready else 'BLOCKED_REAL_BOARD_EVIDENCE'}`",
            "",
            "This audit is read-only. It does not configure networking, program FPGA, write UART, drive TFDU, or send board TCP payloads.",
            "",
            "## Markers",
            "",
            "```text",
            f"N03_NETWORK_FIRST_READINESS_PASS={1 if final_ready else 0}",
            f"N03_NETWORK_FIRST_REAL_BOARD_BLOCKER_COUNT={len(blockers)}",
            f"N03_EXTERNAL_PRECONDITIONS_STATUS={external_status}",
            f"N03_EXTERNAL_PRECONDITION_BLOCKER_COUNT={external_blocker_count}",
            f"N03_FORBIDDEN_PASS_CLAIM_COUNT={len(forbidden_hits)}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "NO_FINAL_PASS_CLAIM=1",
            "```",
            "",
            "## Requirement Table",
            "",
            md_table(items),
            "",
            "## Forbidden Pass Claim Scan",
            "",
            "\n".join(f"- {hit}" for hit in forbidden_hits) if forbidden_hits else "- No forbidden pass claims found in scanned N03/tool/source paths.",
            "",
            "## Next Actions",
            "",
            "\n".join(f"- {item.item}: {item.next_action}" for item in blockers),
            "",
        ]
    )


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    md_path = REPORTS / f"n03_network_first_readiness_{stamp}.md"
    csv_path = REPORTS / f"n03_network_first_readiness_{stamp}.csv"
    json_path = REPORTS / f"n03_network_first_readiness_{stamp}.json"
    current_md = REPORTS / "n03_network_first_readiness_current.md"
    current_csv = REPORTS / "n03_network_first_readiness_current.csv"
    current_json = REPORTS / "n03_network_first_readiness_current.json"

    items = collect_items()
    forbidden_hits = scan_forbidden_claims()
    external_item = next((item for item in items if item.item == "N03-ext"), None)
    external_blocker_count = (
        len([part for part in external_item.blocker.split(";") if part])
        if external_item is not None
        else 0
    )
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "readiness_pass": items[-1].status == "READY_TO_CLAIM_FINAL" and not forbidden_hits,
        "external_preconditions_status": external_item.status if external_item is not None else "MISSING",
        "external_precondition_blocker_count": external_blocker_count,
        "forbidden_pass_claims": forbidden_hits,
        "items": [asdict(item) for item in items],
    }
    md_path.write_text(render_markdown(items, forbidden_hits), encoding="utf-8")
    write_csv(csv_path, [asdict(item) for item in items])
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    current_md.write_text(md_path.read_text(encoding="utf-8"), encoding="utf-8")
    current_csv.write_text(csv_path.read_text(encoding="utf-8"), encoding="utf-8")
    current_json.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")

    blocker_count = sum(1 for item in items if item.blocker)
    pass_ready = 1 if payload["readiness_pass"] else 0
    print(f"WROTE_N03_READINESS_MD={rel(md_path)}")
    print(f"WROTE_N03_READINESS_CSV={rel(csv_path)}")
    print(f"WROTE_N03_READINESS_JSON={rel(json_path)}")
    print(f"N03_NETWORK_FIRST_READINESS_PASS={pass_ready}")
    print(f"N03_NETWORK_FIRST_REAL_BOARD_BLOCKER_COUNT={blocker_count}")
    print(f"N03_EXTERNAL_PRECONDITIONS_STATUS={payload['external_preconditions_status']}")
    print(f"N03_EXTERNAL_PRECONDITION_BLOCKER_COUNT={external_blocker_count}")
    print(f"N03_FORBIDDEN_PASS_CLAIM_COUNT={len(forbidden_hits)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_FINAL_PASS_CLAIM=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
