from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


RUN_ORDER = ["N03", "N04", "A01", "S05", "A02"]
VALIDATOR_MODES = {
    "N03": "ps_pc_tcp_dhcp",
    "N04": "two_ax7010",
    "A01": "product_loop",
    "S05": "rotating_shaft",
    "A02": "eight_lane",
}
STAGE_NAMES = {
    "N03": "Real board PS-to-PC TCP/DHCP",
    "N04": "Two complete AX7010 systems",
    "A01": "Full PC-PS-PL-IR product loop",
    "S05": "Real 20 cm / 600 rpm rotating shaft",
    "A02": "Real 8-lane TFDU hardware",
}


@dataclass
class RunbookStage:
    item_id: str
    name: str
    current_status: str
    current_blocker: str
    readiness: str
    current_preflight_blockers: str
    safe_command: str
    validation_command: str
    shutdown_requirement: str
    evidence_patterns: str
    safety_guard: str


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_csv(path: Path, rows: list[RunbookStage]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def md_table(rows: list[RunbookStage]) -> str:
    out = [
        "| id | readiness | current blocker | command | validation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        out.append(
            "| "
            + " | ".join(
                cell.replace("\n", " ").replace("|", "/")
                for cell in [
                    row.item_id,
                    row.readiness,
                    row.current_blocker,
                    f"`{row.safe_command}`",
                    f"`{row.validation_command}`",
                ]
            )
            + " |"
        )
    return "\n".join(out)


def stage_readiness(item_id: str, preflight_blockers: list[str], item: dict[str, Any]) -> tuple[str, list[str]]:
    blockers = list(preflight_blockers)
    if item.get("current_status") in {"MISSING_HARDWARE", "PARTIAL_G1_ONLY"}:
        blockers.append(str(item.get("current_status")))
    if item_id in {"N04", "A01", "S05", "A02"} and "tcp_quick_probe_two_ax7010" not in blockers:
        blockers.append("two_ax7010_real_hardware_not_proven")
    if item_id == "S05":
        blockers.append("rotating_fixture_log_not_real")
    if item_id == "A02":
        blockers.append("real_8lane_pinmap_and_tfdu_wiring_not_validated")
    if blockers:
        if "ethernet_link" in blockers:
            return "BLOCKED_NO_ETHERNET", blockers
        return "BLOCKED_EXTERNAL_HARDWARE", blockers
    return "READY_TO_RUN_SAFE_WRAPPER"


def validation_command(item_id: str) -> str:
    mode = VALIDATOR_MODES[item_id]
    if item_id == "S05":
        return (
            "python .\\tools\\validate_rotating_fixture_log.py --input <fixture_log.csv> "
            "; if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }; "
            "python .\\tools\\validate_real_acceptance_evidence.py --mode rotating_shaft "
            "--summary <real_summary.txt> --criteria <criteria.csv> --fixture-validation <fixture_validation.json>"
        )
    if item_id in {"N04", "A01", "A02"}:
        return (
            f"python .\\tools\\validate_real_acceptance_evidence.py --mode {mode} "
            "--summary <real_summary.txt> --criteria <criteria.csv>"
        )
    return "python .\\tools\\validate_real_acceptance_evidence.py --mode ps_pc_tcp_dhcp --summary <real_summary.txt>"


def make_stage(item_id: str, item: dict[str, Any], preflight_blockers: list[str]) -> RunbookStage:
    readiness, blockers = stage_readiness(item_id, preflight_blockers, item)
    return RunbookStage(
        item_id=item_id,
        name=STAGE_NAMES[item_id],
        current_status=str(item.get("current_status", "")),
        current_blocker=str(item.get("current_blocker", "")),
        readiness=readiness,
        current_preflight_blockers=", ".join(blockers) if blockers else "none",
        safe_command=str(item.get("safe_command", "")),
        validation_command=validation_command(item_id),
        shutdown_requirement=str(item.get("shutdown_requirement", "")),
        evidence_patterns="\n".join(str(v) for v in item.get("evidence_patterns", [])),
        safety_guard="\n".join(str(v) for v in item.get("safety_guard", [])),
    )


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    plan = read_json(REPORTS / "remaining_hardware_acceptance_plan_current.json")
    preflight = read_json(REPORTS / "external_preconditions_current.json")
    plan_items = {item.get("item_id"): item for item in plan.get("items", []) if isinstance(item, dict)}
    preflight_blockers = [str(v) for v in preflight.get("blockers", [])]

    rows = [make_stage(item_id, plan_items.get(item_id, {}), preflight_blockers) for item_id in RUN_ORDER]
    generated = datetime.now().isoformat(timespec="seconds")
    overall = "WAITING_FOR_ETHERNET" if "ethernet_link" in preflight_blockers else "WAITING_FOR_REAL_HARDWARE"
    if all(row.readiness == "READY_TO_RUN_SAFE_WRAPPER" for row in rows):
        overall = "READY_FOR_ORDERED_REAL_ACCEPTANCE"

    md_path = REPORTS / "real_acceptance_runbook_current.md"
    json_path = REPORTS / "real_acceptance_runbook_current.json"
    csv_path = REPORTS / "real_acceptance_runbook_current.csv"
    write_csv(csv_path, rows)

    md = [
        "# Real Acceptance Runbook",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Current external preflight: `{preflight.get('overall', 'MISSING')}`",
        f"- Current preflight blockers: `{', '.join(preflight_blockers) if preflight_blockers else 'none'}`",
        "- Continuous physical run cap: `600 seconds`",
        "- No hardware programming by this generator: `1`",
        "- No UART write by this generator: `1`",
        "- No TFDU drive by this generator: `1`",
        "",
        "This runbook is generated from the remaining hardware acceptance plan and current external preflight. It is not real acceptance evidence; it is the ordered entry checklist for future real tests.",
        "",
        "## Ordered Stages",
        "",
        md_table(rows),
        "",
        "## Stage Details",
        "",
    ]
    for row in rows:
        md.extend(
            [
                f"### {row.item_id} - {row.name}",
                "",
                f"- Readiness: `{row.readiness}`",
                f"- Current status: `{row.current_status}`",
                f"- Current blockers: `{row.current_preflight_blockers}`",
                f"- Shutdown requirement: {row.shutdown_requirement}",
                "",
                "Safe command:",
                "",
                "```powershell",
                row.safe_command,
                "```",
                "",
                "Validation command:",
                "",
                "```powershell",
                row.validation_command,
                "```",
                "",
                "Safety guard:",
                "",
                "```text",
                row.safety_guard,
                "```",
                "",
                "Evidence patterns:",
                "",
                "```text",
                row.evidence_patterns,
                "```",
                "",
            ]
        )
    md.extend(
        [
            "## Acceptance Boundary",
            "",
            "Real PASS can only be claimed after the corresponding safe wrapper produces real, non-dry-run hardware evidence and `tools/validate_real_acceptance_evidence.py` accepts that evidence. Offline models, dry-runs, templates, and this runbook are not substitutes for real acceptance.",
            "",
            "```text",
            f"RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall={overall} stages={len(rows)}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "```",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    json_payload = {
        "generated": generated,
        "overall": overall,
        "preflight_overall": preflight.get("overall", "MISSING"),
        "preflight_blockers": preflight_blockers,
        "stages": [asdict(row) for row in rows],
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
    }
    json_path.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_REAL_ACCEPTANCE_RUNBOOK overall={overall} stages={len(rows)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
