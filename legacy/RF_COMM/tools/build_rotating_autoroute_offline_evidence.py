from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class EvidenceRow:
    check: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
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


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def latest_containing(pattern: str, needles: Iterable[str]) -> Path | None:
    for path in sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if all(needle in text for needle in needles):
            return path
    return None


def contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def first_line(text: str, marker: str) -> str:
    for line in text.splitlines():
        if marker in line:
            return line.strip()
    return "MISSING"


def extract(pattern: str, text: str, default: str = "MISSING") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        return default
    if match.groups():
        return match.group(1)
    return match.group(0)


def add(rows: list[EvidenceRow], check: str, ok: bool, evidence: Path | None, pass_note: str, fail_note: str) -> None:
    rows.append(EvidenceRow(check, "PASS" if ok else "FAIL", rel(evidence), pass_note if ok else fail_note))


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def build() -> tuple[str, list[EvidenceRow], dict[str, str]]:
    constraint = find_constraint()
    post_summary = latest_containing(
        "reports/post_g1_target_sim_gate_*.summary.txt",
        ["POST_G1_TARGET_SIM_GATE_PASS=1", "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS"],
    )
    post_cases = latest_containing(
        "reports/post_g1_target_sim_gate_*.cases.csv",
        ["rotating_autoroute", "rotating_8lane_soak_model", "full_system_capped_digital_twin"],
    )
    full_twin = REPORTS / "full_system_capped_digital_twin_current.md"
    two_ax = REPORTS / "two_ax7010_end_to_end_model_current.md"
    network_fault = REPORTS / "network_fault_recovery_model_current.md"
    real_acceptance = REPORTS / "real_acceptance_evidence_validation_current.md"
    dynamic_perm = REPORTS / "rotating_dynamic_permutation_autoroute_current.md"
    dynamic_perm_json = REPORTS / "rotating_dynamic_permutation_autoroute_current.json"
    dynamic_perm_csv = REPORTS / "rotating_dynamic_permutation_autoroute_current.csv"

    post_text = read_text(post_summary)
    cases_text = read_text(post_cases)
    full_twin_text = read_text(full_twin)
    two_ax_text = read_text(two_ax)
    network_fault_text = read_text(network_fault)
    real_acceptance_text = read_text(real_acceptance)
    dynamic_perm_text = read_text(dynamic_perm)
    dynamic_perm_json_text = read_text(dynamic_perm_json)
    dynamic_perm_csv_text = read_text(dynamic_perm_csv)

    rows: list[EvidenceRow] = []
    add(
        rows,
        "hard_constraint_unchanged",
        constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256,
        constraint,
        f"sha256={sha256(constraint)}",
        "hard constraint file is missing or changed",
    )
    add(
        rows,
        "latest_post_g1_gate",
        contains_all(post_text, ["POST_G1_TARGET_SIM_GATE_PASS=1", "POST_G1_TARGET_SIM_GATE_FAIL_COUNT=0"]),
        post_summary,
        "latest post-G1 simulation/offline gate passes with zero failed cases",
        "latest post-G1 simulation/offline gate is missing or failed",
    )
    add(
        rows,
        "four_lane_rotating_stress",
        contains_all(
            post_text,
            [
                "LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS",
                "rpm=600",
                "rev_per_s=10",
                "shaft_diameter_mm=200",
                "rotations=10",
                "good_src_coverage=1111",
                "tx_attempt_coverage=1111",
                "failed_route_packets=40",
            ],
        ),
        post_summary,
        first_line(post_text, "LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS"),
        "4-lane rotating autoroute stress evidence is incomplete",
    )
    add(
        rows,
        "eight_lane_autoroute",
        contains_all(
            post_text,
            [
                "LOOPBACK_8LANE_AUTOROUTE_PASS",
                "good_src_coverage=11111111",
                "tx_attempt_coverage=11111111",
                "failed_route_packets=8",
            ],
        ),
        post_summary,
        first_line(post_text, "LOOPBACK_8LANE_AUTOROUTE_PASS"),
        "8-lane autoroute source/attempt coverage evidence is incomplete",
    )
    add(
        rows,
        "eight_lane_capped_rotating_model",
        contains_all(
            post_text,
            [
                "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS",
                "original_target_seconds=7200",
                "runtime_cap_seconds=600",
                "seconds=600",
                "rpm=600",
                "shaft_diameter_mm=200",
                "rotations=6000",
                "sectors=48000",
                "lane_count=8",
                "success_slots=48000",
                "success_fragments=384000",
                "good_lane_coverage=11111111",
                "attempted_lane_coverage=11111111",
                "rx_lane_coverage=11111111",
                "route_map_coverage=11111111",
            ],
        ),
        post_summary,
        first_line(post_text, "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS"),
        "8-lane capped rotating model evidence is incomplete",
    )
    add(
        rows,
        "two_hour_equivalent_model",
        contains_all(
            post_text,
            [
                "ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS",
                "seconds=7200",
                "rotations=72000",
                "sectors=288000",
                "ack_loss_events=70",
                "route_map_coverage=1111",
            ],
        ),
        post_summary,
        first_line(post_text, "ROTATING_AUTOROUTE_2H_SOAK_MODEL_PASS"),
        "2-hour equivalent model evidence is incomplete",
    )
    add(
        rows,
        "full_system_capped_twin",
        contains_all(
            post_text,
            [
                "FULL_SYSTEM_CAPPED_DIGITAL_TWIN_PASS",
                "runtime_cap_seconds=600",
                "seconds=600",
                "lane_count=8",
                "route_map_coverage=0xff",
                "source_lane_coverage=0xff",
                "route_probe_events=",
                "max_route_probe_observed=",
                "fdx_a_to_b_rx_lane_coverage=0x0f",
                "fdx_b_to_a_rx_lane_coverage=0xf0",
                "tcp_reconnect_events=30",
                "dhcp_static_fallback_events=22",
                "unrecovered_errors=0",
                "deadlock_events=0",
                "raw_half_8lane_mbps=32.000000",
                "raw_fdx_4lane_per_dir_mbps=16.000000",
                "rate_claim=raw_phy_only",
            ],
        )
        and contains_all(
            full_twin_text,
            [
                "- Overall: `PASS`",
                "OFFLINE_MODEL_NOT_HARDWARE",
                "fdx_a_to_b_rx_lane_coverage",
                "`0x0f`",
                "fdx_b_to_a_rx_lane_coverage",
                "`0xf0`",
                "deadlock_events",
                "`0`",
            ],
        ),
        full_twin,
        first_line(post_text, "FULL_SYSTEM_CAPPED_DIGITAL_TWIN_PASS"),
        "full-system capped digital twin evidence is incomplete",
    )
    add(
        rows,
        "two_ax7010_offline_route_reconnect",
        contains_all(
            post_text,
            [
                "TWO_AX7010_END_TO_END_OFFLINE_PASS",
                "endpoints=2",
                "lane_count=8",
                "route_changes=",
                "failed_route_events=",
                "route_probe_events=",
                "queued_reconnect_rx=1",
                "tx_lane_coverage=0xff",
                "rx_lane_coverage=0xff",
            ],
        )
        and contains_all(two_ax_text, ["- Overall: `PASS`", "OFFLINE_MODEL_NOT_HARDWARE", "fdx_a_to_b_tx_lane_coverage", "`0x0f`", "fdx_b_to_a_tx_lane_coverage", "`0xf0`"]),
        two_ax,
        first_line(post_text, "TWO_AX7010_END_TO_END_OFFLINE_PASS"),
        "two-AX7010 offline route/reconnect evidence is incomplete",
    )
    add(
        rows,
        "dynamic_permutation_autoroute",
        contains_all(
            dynamic_perm_text,
            [
                "RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE overall=PASS_OFFLINE_DYNAMIC_PERMUTATION_AUTOROUTE",
                "seconds=600",
                "rpm=600",
                "shaft_diameter_mm=200",
                "half_pairs=64/64",
                "fdx_a_to_b_pairs=16/16",
                "fdx_b_to_a_pairs=16/16",
                "stale_cache_events=",
                "unrecovered_errors=0",
                "deadlock_events=0",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
                "REAL_ROTATING_SHAFT_ACCEPTANCE=0",
            ],
        )
        and '"overall": "PASS_OFFLINE_DYNAMIC_PERMUTATION_AUTOROUTE"' in dynamic_perm_json_text
        and "half_pair_coverage_count,64" in dynamic_perm_csv_text
        and "fdx_a_to_b_pair_coverage_count,16" in dynamic_perm_csv_text
        and "fdx_b_to_a_pair_coverage_count,16" in dynamic_perm_csv_text
        and ",FAIL," not in dynamic_perm_csv_text,
        dynamic_perm,
        first_line(dynamic_perm_text, "RF_COMM_ROTATING_DYNAMIC_PERMUTATION_AUTOROUTE"),
        "dynamic TX/RX permutation autoroute evidence is incomplete",
    )
    add(
        rows,
        "network_fault_recovery",
        contains_all(
            network_fault_text,
            [
                "RF_COMM_NETWORK_FAULT_RECOVERY_MODEL overall=PASS scenarios=7",
                "tcp_reset_reconnect",
                "host_restart",
                "cable_replug_reconnect",
                "dhcp_address_change",
                "dhcp_timeout_static_fallback",
                "queued_rx_after_reconnect",
            ],
        ),
        network_fault,
        "network fault model covers reconnect, host restart, DHCP rebind/fallback, and queued RX",
        "network fault recovery evidence is incomplete",
    )
    add(
        rows,
        "no_side_effects",
        contains_all(post_text, ["NO_HARDWARE_PROGRAMMING=1", "NO_TFDU_DRIVE=1"])
        and contains_all(full_twin_text, ["No hardware programming: `1`", "No UART write: `1`", "No TFDU drive: `1`"])
        and contains_all(network_fault_text, ["FPGA programming: `not performed`", "UART write: `not performed`", "TFDU drive: `not performed`"]),
        post_summary,
        "all aggregated evidence is offline/read-only and records no FPGA programming, no UART write, and no TFDU drive",
        "one or more evidence files lack no-side-effect markers",
    )

    rows.append(
        EvidenceRow(
            "real_hardware_boundary",
            "DEFERRED",
            rel(real_acceptance),
            "This is offline/model evidence only; real 20 cm / 600 rpm rotating-shaft, two-AX7010, TFDU hardware, and Ethernet/TCP-DHCP acceptance remain required.",
        )
    )
    add(
        rows,
        "real_acceptance_not_overclaimed",
        contains_all(real_acceptance_text, ["TEMPLATE_READY_NOT_REAL_EVIDENCE", "REAL_ACCEPTANCE_EVIDENCE=0"]),
        real_acceptance,
        "real-acceptance validator still marks template-only output as not real evidence",
        "real-acceptance boundary evidence is missing or overclaimed",
    )

    overall = "PASS_OFFLINE_ROTATING_AUTOROUTE_EVIDENCE"
    if any(row.status == "FAIL" for row in rows):
        overall = "FAIL_ROTATING_AUTOROUTE_EVIDENCE"

    meta = {
        "post_summary": rel(post_summary),
        "post_cases": rel(post_cases),
        "full_system_twin": rel(full_twin),
        "two_ax7010_model": rel(two_ax),
        "network_fault_recovery": rel(network_fault),
        "dynamic_permutation_autoroute": rel(dynamic_perm),
        "dynamic_permutation_autoroute_json": rel(dynamic_perm_json),
        "dynamic_permutation_autoroute_csv": rel(dynamic_perm_csv),
        "real_acceptance_evidence": rel(real_acceptance),
        "rotating_stress_line": first_line(post_text, "LOOPBACK_ROTATING_AUTOROUTE_STRESS_PASS"),
        "rotating_8lane_capped_line": first_line(post_text, "ROTATING_AUTOROUTE_8LANE_CAPPED_SOAK_MODEL_PASS"),
        "full_twin_line": first_line(post_text, "FULL_SYSTEM_CAPPED_DIGITAL_TWIN_PASS"),
        "post_case_count": extract(r"POST_G1_TARGET_SIM_GATE_PASS_COUNT=([0-9]+)", post_text),
        "post_fail_count": extract(r"POST_G1_TARGET_SIM_GATE_FAIL_COUNT=([0-9]+)", post_text),
        "no_hardware_programming": "1",
        "no_uart_write": "1",
        "no_tfdu_drive": "1",
        "real_rotating_acceptance": "0",
    }
    return overall, rows, meta


def write_reports(overall: str, rows: list[EvidenceRow], meta: dict[str, str]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    md_path = REPORTS / "rotating_autoroute_offline_evidence_current.md"
    json_path = REPORTS / "rotating_autoroute_offline_evidence_current.json"
    csv_path = REPORTS / "rotating_autoroute_offline_evidence_current.csv"

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md = [
        "# Rotating Autoroute Offline Evidence",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        "- Evidence type: `OFFLINE_MODEL_NOT_HARDWARE`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Real rotating-shaft acceptance: `0`",
        "",
        "This report consolidates existing simulation/model evidence for rotating-shaft automatic route finding under the current no-Ethernet condition. It is deliberately not real hardware acceptance.",
        "",
        "## Key Evidence",
        "",
        f"- Rotating stress: `{meta['rotating_stress_line']}`",
        f"- 8-lane capped model: `{meta['rotating_8lane_capped_line']}`",
        f"- Full-system twin: `{meta['full_twin_line']}`",
        "",
        "## Checks",
        "",
        md_table(["check", "status", "evidence", "note"], [[r.check, r.status, r.evidence, r.note] for r in rows]),
        "",
        "```text",
        f"RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE overall={overall} checks={len(rows)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "REAL_ROTATING_SHAFT_ACCEPTANCE=0",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "evidence_type": "OFFLINE_MODEL_NOT_HARDWARE",
        "meta": meta,
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    overall, rows, meta = build()
    write_reports(overall, rows, meta)
    print(f"RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE overall={overall} checks={len(rows)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("REAL_ROTATING_SHAFT_ACCEPTANCE=0")
    return 0 if overall.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
