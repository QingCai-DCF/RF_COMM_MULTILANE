from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
OPEN_IDS = ("N03", "N04", "S05", "A01", "A02")
CURRENT_BOARD_ETHERNET_CABLE_AVAILABLE = False
CURRENT_BOARD_ETHERNET_CONDITION_CHANGEABLE_NOW = False
CURRENT_ETHERNET_CONDITION_NOTE = "Development board has no Ethernet cable; this cannot be changed right now."


@dataclass
class ReadinessRow:
    item_id: str
    status: str
    ready_to_start_real_acceptance: int
    blockers: str
    satisfied: str
    safe_command_source: str
    evidence_required: str
    shutdown_required: int
    start_when: str
    unlock_action: str
    safety_requirement: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def read_json(path: Path | None) -> dict:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def read_csv(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict(row) for row in csv.DictReader(f)]


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def by_key(rows: Iterable[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for row in rows:
        value = row.get(key, "")
        if value:
            out[value] = row
    return out


def has_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


def add_condition(ok: bool, name: str, satisfied: list[str], blockers: list[str]) -> None:
    if ok:
        satisfied.append(name)
    else:
        blockers.append(name)


def file_exists(path: Path) -> bool:
    return path.exists() and path.is_file()


def build_rows() -> tuple[list[ReadinessRow], dict[str, object]]:
    constraint = find_constraint()
    constraint_ok = sha256(constraint) == EXPECTED_CONSTRAINT_SHA256

    matrix_csv = REPORTS / "target_acceptance_matrix_current.csv"
    preflight_csv = REPORTS / "external_preconditions_current.csv"
    remaining_csv = REPORTS / "remaining_hardware_acceptance_plan_current.csv"
    sequence_csv = REPORTS / "real_acceptance_sequence_safe_current.stages.csv"
    sequence_summary = REPORTS / "real_acceptance_sequence_safe_current.summary.txt"
    status_consistency = REPORTS / "full_target_status_consistency_current.md"
    readiness_json = REPORTS / "8lane_hardware_readiness_current.json"
    real_evidence_validation = REPORTS / "real_acceptance_evidence_validation_current.md"
    rotating_fixture_validation = REPORTS / "rotating_fixture_log_validation_current.md"

    preflight = by_key(read_csv(preflight_csv), "item")
    matrix = by_key(read_csv(matrix_csv), "item_id")
    remaining = by_key(read_csv(remaining_csv), "item_id")
    sequence = by_key(read_csv(sequence_csv), "id")
    readiness = read_json(readiness_json)

    status_consistency_text = read_text(status_consistency)
    sequence_text = read_text(sequence_summary)
    real_validation_text = read_text(real_evidence_validation)
    fixture_validation_text = read_text(rotating_fixture_validation)

    wrappers = {
        "N03": ROOT / "tools" / "run_ps_pc_tcp_dhcp_acceptance_safe.ps1",
        "N04": ROOT / "tools" / "run_two_ax7010_end_to_end_acceptance_safe.ps1",
        "A01": ROOT / "tools" / "run_product_loop_acceptance_safe.ps1",
        "S05": ROOT / "tools" / "run_rotating_shaft_acceptance_safe.ps1",
        "A02": ROOT / "tools" / "run_8lane_hardware_acceptance_safe.ps1",
    }
    template_dir = REPORTS / "real_acceptance_template"
    template_files = {
        "N03": [template_dir / "ps_pc_tcp_dhcp_summary_template.txt"],
        "N04": [
            template_dir / "two_ax7010_summary_template.txt",
            template_dir / "two_ax7010_criteria_template.csv",
        ],
        "A01": [
            template_dir / "product_loop_summary_template.txt",
            template_dir / "product_loop_criteria_template.csv",
        ],
        "S05": [
            template_dir / "rotating_shaft_summary_template.txt",
            template_dir / "rotating_shaft_criteria_template.csv",
            REPORTS / "rotating_fixture_log_template.csv",
        ],
        "A02": [
            template_dir / "eight_lane_summary_template.txt",
            template_dir / "eight_lane_criteria_template.csv",
        ],
    }
    shutdown_bitstream = ROOT / "shutdown_bitstream" / "tfdu_shutdown_8lane_candidate.bit"
    reduced8_current = read_json(REPORTS / "external_reduced_8lane_frag16_bitstream_current.json")
    reduced8_value = str(reduced8_current.get("bitstream", ""))
    reduced8_bitstream = ROOT / reduced8_value if reduced8_value else None
    if reduced8_bitstream is None or not reduced8_bitstream.exists():
        reduced8_bitstream = (
            REPORTS
            / "external_reduced_8lane_frag16_bitstream_20260627_065143"
            / "external_reduced_8lane_frag16_candidate.bit"
        )
    validator = ROOT / "tools" / "validate_real_acceptance_evidence.py"
    fixture_validator = ROOT / "tools" / "validate_rotating_fixture_log.py"

    open_ids_ok = tuple(
        row.get("item_id")
        for row in read_csv(matrix_csv)
        if row.get("status") in {"DEFERRED_NO_ETHERNET", "MISSING_HARDWARE", "PARTIAL_G1_ONLY"}
    ) == OPEN_IDS

    common_ok = {
        "hard_constraint_unchanged": constraint_ok,
        "status_consistency_report_present": status_consistency.exists(),
        "matrix_open_set_matches_remaining_target": open_ids_ok,
        "real_evidence_validator_available": file_exists(validator),
        "real_acceptance_templates_are_template_only": (
            "RF_COMM_REAL_ACCEPTANCE_EVIDENCE_VALIDATION overall=TEMPLATE_READY_NOT_REAL_EVIDENCE" in real_validation_text
            and "REAL_ACCEPTANCE_EVIDENCE=0" in real_validation_text
        ),
        "safe_sequence_blocks_current_no_ethernet": (
            "RF_COMM_REAL_ACCEPTANCE_SEQUENCE overall=BLOCKED_NO_ETHERNET" in sequence_text
            and "EXECUTED_WRAPPERS=0" in sequence_text
        ),
    }

    rows: list[ReadinessRow] = []
    for item_id in OPEN_IDS:
        blockers: list[str] = []
        satisfied: list[str] = []
        matrix_row = matrix.get(item_id, {})
        remaining_row = remaining.get(item_id, {})
        wrapper = wrappers[item_id]
        wrapper_text = read_text(wrapper)

        for name, ok in common_ok.items():
            add_condition(ok, name, satisfied, blockers)

        add_condition(matrix_row.get("item_id") == item_id, "matrix_row_present", satisfied, blockers)
        add_condition(bool(remaining_row), "remaining_plan_row_present", satisfied, blockers)
        add_condition(file_exists(wrapper), "safe_wrapper_exists", satisfied, blockers)
        add_condition(all(file_exists(path) for path in template_files[item_id]), "evidence_templates_exist", satisfied, blockers)
        add_condition("NO_HARDWARE_PROGRAMMING=1" in read_text(REPORTS / "external_preconditions_current.md"), "preflight_is_read_only", satisfied, blockers)

        if item_id == "N03":
            add_condition(preflight.get("ethernet_link", {}).get("status") == "PASS", "ethernet_link_up", satisfied, blockers)
            add_condition(preflight.get("tcp_quick_probe_single_board", {}).get("status") == "PASS", "single_board_tcp_reachable", satisfied, blockers)
            add_condition(
                has_all(wrapper_text, ["BOARD_TCP_DHCP_ACCEPTANCE_PASS", "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1", "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1"]),
                "network_wrapper_has_no_tfdu_guard",
                satisfied,
                blockers,
            )
            shutdown_required = 0
            evidence_required = "ps_pc_tcp_dhcp summary with BOARD_TCP_DHCP_ACCEPTANCE_PASS=1"
            start_when = "ethernet_link_up;single_board_tcp_reachable"
            unlock_action = "Connect the board Ethernet path, boot the PS lwIP bridge, confirm DHCP or static IP reachability, then run the N03 safe TCP/DHCP wrapper."
            safety_requirement = "Network-only test: no FPGA programming, no UART write unless explicitly probing read-only logs, no TFDU drive, no IR TX data."
            note = "Network-only real acceptance can start only after Ethernet link and PS bridge TCP are reachable."
        else:
            add_condition(preflight.get("ethernet_link", {}).get("status") == "PASS", "ethernet_link_up", satisfied, blockers)
            add_condition(preflight.get("tcp_quick_probe_two_ax7010", {}).get("status") == "PASS", "two_ax7010_tcp_reachable", satisfied, blockers)
            add_condition(file_exists(shutdown_bitstream), "shutdown_bitstream_available", satisfied, blockers)
            add_condition("ProgramShutdownAfterRun" in wrapper_text, "wrapper_requires_shutdown_after_real_traffic", satisfied, blockers)
            add_condition("AllowTraffic" in wrapper_text, "wrapper_requires_explicit_traffic_enable", satisfied, blockers)
            shutdown_required = 1

            if item_id == "N04":
                evidence_required = "two_ax7010 summary/criteria with bidirectional traffic and shutdown-after-run pass"
                start_when = "ethernet_link_up;two_ax7010_tcp_reachable;two_complete_ax7010_systems_ready;optical_lanes_ready"
                unlock_action = "Connect both AX7010 Ethernet endpoints and the selected TFDU optical lanes, confirm both PS bridges are TCP reachable, then run the N04 safe wrapper with traffic and shutdown-after-run switches."
                safety_requirement = "Real TFDU traffic requires -AllowTraffic and -ProgramShutdownAfterRun; cap continuous run at 600 s and program shutdown immediately after the run."
                note = "Requires two complete AX7010 systems, optical link, Ethernet to both boards, and shutdown after TFDU traffic."
            elif item_id == "A01":
                evidence_required = "product_loop summary/criteria closing PC-PS-PL-IR-external-IR loop"
                start_when = "ethernet_link_up;two_ax7010_tcp_reachable;product_loop_topology_selected;real_ir_path_ready"
                unlock_action = "Choose the final single-board or two-AX7010 product-loop topology, confirm TCP reachability and real IR path alignment, then run the product-loop safe wrapper with evidence validation."
                safety_requirement = "Do not classify simulation, network-only, or G1-only evidence as product-loop acceptance; use -AllowTraffic and -ProgramShutdownAfterRun for real TFDU traffic."
                note = "Requires the full product loop on real hardware; current G1 evidence is only single-board/single-lane."
            elif item_id == "S05":
                add_condition(file_exists(fixture_validator), "rotating_fixture_validator_available", satisfied, blockers)
                add_condition(
                    "RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall=TEMPLATE_READY_NOT_REAL_EVIDENCE" in fixture_validation_text,
                    "fixture_template_ready_but_not_real",
                    satisfied,
                    blockers,
                )
                blockers.append("real_20cm_600rpm_fixture_log_missing")
                evidence_required = "rotating_shaft summary/criteria plus non-template 20cm/600rpm fixture log validation"
                start_when = "ethernet_link_up;two_ax7010_tcp_reachable;real_20cm_600rpm_fixture_log_valid;rotating_optical_path_ready"
                unlock_action = "Prepare the 20 cm / 600 rpm fixture, collect a non-template fixture log that passes validation, confirm both AX7010 TCP endpoints, then run the rotating-shaft safe wrapper."
                safety_requirement = "Real rotating TFDU traffic requires -AllowTraffic and -ProgramShutdownAfterRun; every continuous physical segment is capped at 600 s and shutdown programming is mandatory after the run."
                note = "Requires real rotating fixture evidence; template readiness is not physical shaft acceptance."
            else:
                add_condition(bool(readiness.get("external_reduced_8lane_frag16_bitstream_ok")), "reduced_8lane_raw_candidate_ready", satisfied, blockers)
                add_condition(sha256(reduced8_bitstream) == "F3661A68DB0F36FCAC96DE983538EA31B5AA2B50338B44A81DAB3E45999AC778", "reduced_8lane_bitstream_hash_matches", satisfied, blockers)
                add_condition("PinmapReviewed" in wrapper_text and "ShutdownBitstreamReviewed" in wrapper_text, "wrapper_requires_pinmap_and_shutdown_review", satisfied, blockers)
                blockers.append("real_8lane_tfdu_wiring_validation_missing")
                evidence_required = "8lane hardware summary/criteria with 8 TFDU lanes, shutdown-before/after, and raw 32/16 markers"
                start_when = "ethernet_link_up;two_ax7010_tcp_reachable;pinmap_reviewed;shutdown_bitstream_reviewed;real_8lane_tfdu_wiring_validated"
                unlock_action = "Review the 8-lane pinmap and shutdown bitstream, wire and inspect all 8 TFDU lanes, confirm both AX7010 TCP endpoints, then run the 8-lane hardware wrapper with pinmap/shutdown review switches."
                safety_requirement = "Real 8-lane TFDU use requires -AllowTraffic, -PinmapReviewed, -ShutdownBitstreamReviewed, -ProgramShutdownBeforeRun, and -ProgramShutdownAfterRun; cap continuous run at 600 s."
                note = "Offline raw 8-lane candidate exists, but real 8-TFDU wiring and pinmap review are still external prerequisites."

        stage = sequence.get(item_id, {})
        add_condition(stage.get("planned") == "1", "safe_sequence_stage_planned", satisfied, blockers)
        add_condition(stage.get("executed") == "0", "safe_sequence_executed_zero_under_current_blocker", satisfied, blockers)
        if CURRENT_BOARD_ETHERNET_CABLE_AVAILABLE:
            satisfied.append("current_board_ethernet_cable_available")
        else:
            blockers.append("current_board_ethernet_cable_unavailable")
        if CURRENT_BOARD_ETHERNET_CONDITION_CHANGEABLE_NOW:
            satisfied.append("current_board_ethernet_condition_changeable_now")
        else:
            blockers.append("current_board_ethernet_condition_not_changeable_now")

        current_external_blockers = [name for name in blockers if name in {
            "ethernet_link_up",
            "single_board_tcp_reachable",
            "two_ax7010_tcp_reachable",
            "real_20cm_600rpm_fixture_log_missing",
            "real_8lane_tfdu_wiring_validation_missing",
            "current_board_ethernet_cable_unavailable",
            "current_board_ethernet_condition_not_changeable_now",
        }]
        ready = not blockers
        status = "READY_TO_START_REAL_ACCEPTANCE" if ready else "BLOCKED_EXTERNAL_PRECONDITIONS"
        if any(name in blockers for name in ["hard_constraint_unchanged", "safe_wrapper_exists"]):
            status = "BLOCKED_INTERNAL_READINESS"

        rows.append(
            ReadinessRow(
                item_id=item_id,
                status=status,
                ready_to_start_real_acceptance=int(ready),
                blockers=";".join(blockers),
                satisfied=";".join(satisfied),
                safe_command_source=stage.get("command", rel(wrapper)),
                evidence_required=evidence_required,
                shutdown_required=shutdown_required,
                start_when=start_when,
                unlock_action=unlock_action,
                safety_requirement=safety_requirement,
                note=note + (f" Current external blockers: {', '.join(current_external_blockers)}." if current_external_blockers else ""),
            )
        )

    meta = {
        "constraint": rel(constraint),
        "constraint_sha256": sha256(constraint),
        "matrix_csv": rel(matrix_csv),
        "external_preconditions_csv": rel(preflight_csv),
        "remaining_plan_csv": rel(remaining_csv),
        "safe_sequence_csv": rel(sequence_csv),
        "status_consistency": rel(status_consistency),
        "readiness_json": rel(readiness_json),
        "shutdown_bitstream": rel(shutdown_bitstream),
        "reduced8_bitstream": rel(reduced8_bitstream),
        "open_ids": list(OPEN_IDS),
        "current_ethernet_condition": CURRENT_ETHERNET_CONDITION_NOTE,
        "current_board_ethernet_cable_available": CURRENT_BOARD_ETHERNET_CABLE_AVAILABLE,
        "current_board_ethernet_condition_changeable_now": CURRENT_BOARD_ETHERNET_CONDITION_CHANGEABLE_NOW,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
    }
    return rows, meta


def md_table(rows: list[ReadinessRow]) -> str:
    lines = [
        "| item | status | ready | blockers | start when | unlock action | evidence required | shutdown | safety requirement |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                str(cell).replace("\n", " ").replace("|", "/")
                for cell in [
                    row.item_id,
                    row.status,
                    row.ready_to_start_real_acceptance,
                    row.blockers or "none",
                    row.start_when,
                    row.unlock_action,
                    row.evidence_required,
                    row.shutdown_required,
                    row.safety_requirement,
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows, meta = build_rows()
    generated = datetime.now().isoformat(timespec="seconds")
    if any(row.status == "BLOCKED_INTERNAL_READINESS" for row in rows):
        overall = "BLOCKED_INTERNAL_READINESS"
    elif all(row.ready_to_start_real_acceptance for row in rows):
        overall = "READY_TO_START_REMAINING_REAL_ACCEPTANCE"
    else:
        overall = "BLOCKED_EXTERNAL_PRECONDITIONS"

    md_path = REPORTS / "remaining_acceptance_readiness_current.md"
    json_path = REPORTS / "remaining_acceptance_readiness_current.json"
    csv_path = REPORTS / "remaining_acceptance_readiness_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md = [
        "# Remaining Acceptance Readiness",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Remaining real-acceptance items: `{len(rows)}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Current board Ethernet cable available: `0`",
        "- Current board Ethernet condition changeable now: `0`",
        f"- Current Ethernet condition: {CURRENT_ETHERNET_CONDITION_NOTE}",
        "",
        "This read-only gate answers whether the five remaining target items can safely start real acceptance now. It does not execute wrappers, program hardware, write UART, or drive TFDU boards.",
        "",
        "## Items",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_REMAINING_ACCEPTANCE_READINESS overall={overall} items={len(rows)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "CURRENT_BOARD_ETHERNET_CABLE_AVAILABLE=0",
        "CURRENT_BOARD_ETHERNET_CONDITION_CHANGEABLE_NOW=0",
        "CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1",
        "REAL_ACCEPTANCE_EXECUTED=0",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "meta": meta,
        "items": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_REMAINING_ACCEPTANCE_READINESS overall={overall} items={len(rows)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("CURRENT_BOARD_ETHERNET_CABLE_AVAILABLE=0")
    print("CURRENT_BOARD_ETHERNET_CONDITION_CHANGEABLE_NOW=0")
    print("CURRENT_NO_ETHERNET_CABLE_UNCHANGEABLE_NOW=1")
    print("REAL_ACCEPTANCE_EXECUTED=0")
    return 0 if overall != "BLOCKED_INTERNAL_READINESS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
