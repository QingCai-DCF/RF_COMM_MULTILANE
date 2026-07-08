from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass(frozen=True)
class PromotionSpec:
    item_id: str
    mode: str
    requirement: str
    validation_command: str
    real_evidence_needed: str
    shutdown_required: int


@dataclass
class PromotionRow:
    item_id: str
    mode: str
    status: str
    promotable_to_real_pass: int
    matrix_status: str
    readiness_status: str
    readiness_ready: int
    validator_status: str
    validator_real_evidence: int
    blockers: str
    validation_command: str
    real_evidence_needed: str
    shutdown_required: int
    note: str


SPECS = [
    PromotionSpec(
        "N03",
        "ps_pc_tcp_dhcp",
        "Real board PS-to-PC TCP/DHCP acceptance passes on hardware.",
        r"python .\tools\validate_real_acceptance_evidence.py --mode ps_pc_tcp_dhcp --summary <real_summary.txt>",
        "non-dry-run real board TCP/DHCP summary with BOARD_TCP_DHCP_ACCEPTANCE_PASS=1 and reconnect/DHCP-or-static evidence",
        0,
    ),
    PromotionSpec(
        "N04",
        "two_ax7010",
        "Two complete AX7010 systems exchange PC traffic through the infrared link.",
        r"python .\tools\validate_real_acceptance_evidence.py --mode two_ax7010 --summary <real_summary.txt> --criteria <criteria.csv>",
        "two-AX7010 real summary plus criteria proving smoke, reconnect, bidirectional traffic, raw/effective rate separation, duration cap, and shutdown-after-run",
        1,
    ),
    PromotionSpec(
        "S05",
        "rotating_shaft",
        "Real 20 cm / 600 rpm rotating-shaft communication is physically validated.",
        r"python .\tools\validate_rotating_fixture_log.py --input <fixture_log.csv>; python .\tools\validate_real_acceptance_evidence.py --mode rotating_shaft --summary <real_summary.txt> --criteria <criteria.csv> --fixture-validation <fixture_validation.json>",
        "rotating-shaft real summary plus criteria plus non-template 200 mm / 600 rpm fixture validation",
        1,
    ),
    PromotionSpec(
        "A01",
        "product_loop",
        "Full PC - PS - PL IR - external IR loop is closed on real hardware.",
        r"python .\tools\validate_real_acceptance_evidence.py --mode product_loop --summary <real_summary.txt> --criteria <criteria.csv>",
        "product-loop real summary plus criteria proving PC-PS-PL-IR-external-IR traffic, rate separation, duration cap, and shutdown-after-run",
        1,
    ),
    PromotionSpec(
        "A02",
        "eight_lane",
        "Up to 8 TFDU lanes are physically wired and validated.",
        r"python .\tools\validate_real_acceptance_evidence.py --mode eight_lane --summary <real_summary.txt> --criteria <criteria.csv>",
        "8-lane hardware real summary plus criteria proving shutdown-before-run, 8-lane traffic, rate separation, duration cap, and shutdown-after-run",
        1,
    ),
]


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


def read_json(path: Path | None) -> dict[str, Any]:
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


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def by_key(rows: list[dict[str, str]], key: str) -> dict[str, dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key)}


def validator_mode_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = payload.get("results")
    if not isinstance(results, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in results:
        if isinstance(item, dict) and isinstance(item.get("mode"), str):
            out[item["mode"]] = item
    return out


def build_rows() -> tuple[list[PromotionRow], dict[str, str]]:
    constraint = find_hard_constraint()
    matrix_csv = REPORTS / "target_acceptance_matrix_current.csv"
    readiness_csv = REPORTS / "remaining_acceptance_readiness_current.csv"
    validator_json = REPORTS / "real_acceptance_evidence_validation_current.json"
    validator_md = REPORTS / "real_acceptance_evidence_validation_current.md"
    validator_selftest_md = REPORTS / "real_acceptance_validator_selftest_current.md"
    validator_selftest_json = REPORTS / "real_acceptance_validator_selftest_current.json"
    fixture_validation_md = REPORTS / "rotating_fixture_log_validation_current.md"

    matrix = by_key(read_csv(matrix_csv), "item_id")
    readiness = by_key(read_csv(readiness_csv), "item_id")
    validator_payload = read_json(validator_json)
    validation_by_mode = validator_mode_map(validator_payload)
    validator_text = read_text(validator_md)
    selftest_text = read_text(validator_selftest_md)
    selftest_payload = read_json(validator_selftest_json)
    fixture_text = read_text(fixture_validation_md)

    hard_constraint_ok = sha256(constraint) == EXPECTED_CONSTRAINT_SHA256
    selftest_ok = (
        "RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall=PASS_VALIDATOR_REJECTS_FALSE_REAL_EVIDENCE cases=12 failures=0"
        in selftest_text
        and selftest_payload.get("overall") == "PASS_VALIDATOR_REJECTS_FALSE_REAL_EVIDENCE"
        and selftest_payload.get("failures") == 0
        and selftest_payload.get("real_acceptance_evidence_produced") is False
    )
    validator_loaded = validator_payload.get("overall") is not None and validator_json.exists()

    rows: list[PromotionRow] = []
    for spec in SPECS:
        blockers: list[str] = []
        matrix_row = matrix.get(spec.item_id, {})
        readiness_row = readiness.get(spec.item_id, {})
        validation = validation_by_mode.get(spec.mode, {})
        validator_status = str(validation.get("status", "MISSING_VALIDATION_RESULT"))
        validator_real = bool(validation.get("real_acceptance_evidence", False))
        readiness_ready = readiness_row.get("ready_to_start_real_acceptance") == "1"

        if not hard_constraint_ok:
            blockers.append("hard_constraint_hash_mismatch")
        if not selftest_ok:
            blockers.append("validator_selftest_not_passed")
        if not validator_loaded:
            blockers.append("validator_report_missing")
        if not matrix_row:
            blockers.append("matrix_row_missing")
        if not readiness_row:
            blockers.append("readiness_row_missing")
        if not readiness_ready:
            blockers.extend(
                blocker
                for blocker in readiness_row.get("blockers", "").split(";")
                if blocker
            )
        if not validator_real:
            blockers.append(f"{spec.mode}_real_acceptance_evidence_missing")
        if validator_status != "PASS_REAL_ACCEPTANCE_EVIDENCE":
            blockers.append(f"{spec.mode}_validator_status_{validator_status}")
        if spec.item_id == "S05" and "RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall=PASS_FIXTURE_LOG_READY_FOR_REAL_ACCEPTANCE" not in fixture_text:
            blockers.append("rotating_fixture_real_validation_missing")

        promotable = not blockers
        status = "PROMOTABLE_TO_REAL_PASS" if promotable else "NOT_PROMOTABLE_CURRENTLY"
        if any(blocker in blockers for blocker in ("hard_constraint_hash_mismatch", "validator_selftest_not_passed", "validator_report_missing")):
            status = "BLOCKED_INTERNAL_GUARD"

        rows.append(
            PromotionRow(
                item_id=spec.item_id,
                mode=spec.mode,
                status=status,
                promotable_to_real_pass=int(promotable),
                matrix_status=matrix_row.get("status", "MISSING"),
                readiness_status=readiness_row.get("status", "MISSING"),
                readiness_ready=int(readiness_ready),
                validator_status=validator_status,
                validator_real_evidence=int(validator_real),
                blockers=";".join(dict.fromkeys(blockers)),
                validation_command=spec.validation_command,
                real_evidence_needed=spec.real_evidence_needed,
                shutdown_required=spec.shutdown_required,
                note=(
                    "All promotion guards are satisfied; this item may be changed to a real PASS only with the cited evidence."
                    if promotable
                    else "Current evidence is not sufficient to promote this item to real PASS."
                ),
            )
        )

    meta = {
        "constraint": rel(constraint),
        "constraint_sha256": sha256(constraint),
        "matrix_csv": rel(matrix_csv),
        "readiness_csv": rel(readiness_csv),
        "validator_md": rel(validator_md),
        "validator_json": rel(validator_json),
        "validator_selftest_md": rel(validator_selftest_md),
        "validator_selftest_json": rel(validator_selftest_json),
        "fixture_validation_md": rel(fixture_validation_md),
        "validator_overall": str(validator_payload.get("overall", "")),
        "validator_selftest_overall": str(selftest_payload.get("overall", "")),
    }
    return rows, meta


def md_table(rows: list[PromotionRow]) -> str:
    lines = [
        "| item | mode | status | promotable | matrix | readiness | validator | real evidence | blockers | evidence needed |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        cells = [
            row.item_id,
            row.mode,
            row.status,
            str(row.promotable_to_real_pass),
            row.matrix_status,
            row.readiness_status,
            row.validator_status,
            str(row.validator_real_evidence),
            row.blockers or "none",
            row.real_evidence_needed,
        ]
        lines.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "/") for cell in cells) + " |")
    return "\n".join(lines)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    rows, meta = build_rows()
    promoted = sum(row.promotable_to_real_pass for row in rows)
    if any(row.status == "BLOCKED_INTERNAL_GUARD" for row in rows):
        overall = "BLOCKED_INTERNAL_GUARD"
    elif promoted == len(rows):
        overall = "ALL_ITEMS_PROMOTABLE_TO_REAL_PASS"
    else:
        overall = "BLOCKED_NOT_PROMOTABLE"

    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "real_acceptance_promotion_gate_current.md"
    json_path = REPORTS / "real_acceptance_promotion_gate_current.json"
    csv_path = REPORTS / "real_acceptance_promotion_gate_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    md = [
        "# Real Acceptance Promotion Gate",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Items checked: `{len(rows)}`",
        f"- Promotable to real PASS now: `{promoted}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        "This gate decides whether the remaining real-acceptance items may be promoted from blocked/incomplete status to real PASS. It reads existing evidence only and does not execute hardware wrappers.",
        "",
        "## Items",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall={overall} items={len(rows)} promotable={promoted}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "PROMOTED_TO_REAL_PASS_BY_THIS_SCRIPT=0",
        "REAL_ACCEPTANCE_EVIDENCE_REQUIRED=1",
        "TEMPLATE_OR_DRY_RUN_PROMOTION_ALLOWED=0",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "items": len(rows),
        "promotable": promoted,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "promoted_to_real_pass_by_this_script": False,
        "meta": meta,
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_REAL_ACCEPTANCE_PROMOTION_GATE overall={overall} items={len(rows)} promotable={promoted}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("PROMOTED_TO_REAL_PASS_BY_THIS_SCRIPT=0")
    return 0 if overall != "BLOCKED_INTERNAL_GUARD" else 1


if __name__ == "__main__":
    raise SystemExit(main())
