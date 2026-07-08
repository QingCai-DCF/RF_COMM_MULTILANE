from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


@dataclass
class FixtureRow:
    row_number: int
    timestamp: str
    segment_id: str
    shaft_diameter_mm: float | None
    rpm: float | None
    sample_seconds: float | None
    is_template: bool
    note: str
    status: str
    detail: str


def parse_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "template"}


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def get_value(row: dict[str, str], *names: str) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return ""


def write_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp",
        "run_segment_id",
        "shaft_diameter_mm",
        "rpm",
        "sample_seconds",
        "is_template",
        "note",
    ]
    rows = [
        {
            "timestamp": "2026-06-27T00:00:00+08:00",
            "run_segment_id": "segment_001",
            "shaft_diameter_mm": "200.0",
            "rpm": "600.0",
            "sample_seconds": "60",
            "is_template": "1",
            "note": "template row only; replace with measured fixture data before real acceptance",
        },
        {
            "timestamp": "2026-06-27T00:01:00+08:00",
            "run_segment_id": "segment_001",
            "shaft_diameter_mm": "200.0",
            "rpm": "600.0",
            "sample_seconds": "60",
            "is_template": "1",
            "note": "template row only; sample_seconds per continuous segment must not exceed 600",
        },
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validate_rows(
    raw_rows: list[dict[str, str]],
    target_diameter_mm: float,
    diameter_tolerance_mm: float,
    target_rpm: float,
    rpm_tolerance: float,
    max_continuous_seconds: float,
) -> tuple[list[FixtureRow], dict[str, float]]:
    rows: list[FixtureRow] = []
    segment_seconds: dict[str, float] = {}

    for idx, raw in enumerate(raw_rows, start=2):
        timestamp = get_value(raw, "timestamp", "time")
        segment_id = get_value(raw, "run_segment_id", "segment", "segment_id") or "segment_001"
        diameter = parse_float(get_value(raw, "shaft_diameter_mm", "diameter_mm"))
        rpm = parse_float(get_value(raw, "rpm", "speed_rpm", "rotation_rpm"))
        seconds = parse_float(get_value(raw, "sample_seconds", "duration_seconds", "seconds"))
        is_template = parse_bool(get_value(raw, "is_template", "template"))
        note = get_value(raw, "note", "notes")

        problems: list[str] = []
        if not timestamp:
            problems.append("missing timestamp")
        if diameter is None:
            problems.append("missing shaft_diameter_mm")
        elif abs(diameter - target_diameter_mm) > diameter_tolerance_mm:
            problems.append("shaft_diameter_mm out of tolerance")
        if rpm is None:
            problems.append("missing rpm")
        elif abs(rpm - target_rpm) > rpm_tolerance:
            problems.append("rpm out of tolerance")
        if seconds is None:
            problems.append("missing sample_seconds")
        elif seconds <= 0:
            problems.append("sample_seconds must be positive")
        elif seconds > max_continuous_seconds:
            problems.append("single sample exceeds continuous cap")

        if seconds is not None and seconds > 0:
            segment_seconds[segment_id] = segment_seconds.get(segment_id, 0.0) + seconds

        status = "PASS" if not problems else "FAIL"
        rows.append(
            FixtureRow(
                row_number=idx,
                timestamp=timestamp,
                segment_id=segment_id,
                shaft_diameter_mm=diameter,
                rpm=rpm,
                sample_seconds=seconds,
                is_template=is_template,
                note=note,
                status=status,
                detail="; ".join(problems) if problems else "within configured bounds",
            )
        )

    for segment_id, total_seconds in segment_seconds.items():
        if total_seconds > max_continuous_seconds:
            for row in rows:
                if row.segment_id == segment_id:
                    row.status = "FAIL"
                    row.detail = (
                        row.detail
                        + f"; segment {segment_id} totals {total_seconds:g}s > {max_continuous_seconds:g}s cap"
                    )

    return rows, segment_seconds


def csv_escape(text: object) -> str:
    value = "" if text is None else str(text)
    return '"' + value.replace('"', '""') + '"'


def write_reports(
    prefix: Path,
    overall: str,
    input_path: Path | None,
    template_path: Path | None,
    rows: list[FixtureRow],
    segment_seconds: dict[str, float],
    args: argparse.Namespace,
) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    md_path = prefix.with_suffix(".md")
    json_path = prefix.with_suffix(".json")
    csv_path = prefix.with_suffix(".csv")
    generated = datetime.now().astimezone().isoformat(timespec="seconds")

    md_lines = [
        "# Rotating Fixture Log Validation",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Input log: `{input_path if input_path else 'not provided'}`",
        f"- Template path: `{template_path if template_path else 'not written'}`",
        f"- Target diameter: `{args.target_diameter_mm}` mm",
        f"- Diameter tolerance: `+/-{args.diameter_tolerance_mm}` mm",
        f"- Target RPM: `{args.target_rpm}`",
        f"- RPM tolerance: `+/-{args.rpm_tolerance}`",
        f"- Continuous segment cap: `{args.max_continuous_seconds}` seconds",
        "- Real acceptance evidence: `0` when overall is TEMPLATE_READY_NOT_REAL_EVIDENCE",
        "- No hardware programming, UART write, or TFDU drive is performed by this validator.",
        "",
        "## Rows",
        "",
        "| row | segment | diameter_mm | rpm | sample_seconds | template | status | detail |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        md_lines.append(
            "| "
            + " | ".join(
                [
                    str(row.row_number),
                    row.segment_id,
                    "" if row.shaft_diameter_mm is None else f"{row.shaft_diameter_mm:g}",
                    "" if row.rpm is None else f"{row.rpm:g}",
                    "" if row.sample_seconds is None else f"{row.sample_seconds:g}",
                    "1" if row.is_template else "0",
                    row.status,
                    row.detail.replace("|", "/"),
                ]
            )
            + " |"
        )
    md_lines.extend(
        [
            "",
            "## Segment Seconds",
            "",
            "| segment | seconds |",
            "| --- | --- |",
        ]
    )
    for segment_id, seconds in sorted(segment_seconds.items()):
        md_lines.append(f"| {segment_id} | {seconds:g} |")
    md_lines.extend(
        [
            "",
            "```text",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            f"REAL_ACCEPTANCE_EVIDENCE={0 if overall == 'TEMPLATE_READY_NOT_REAL_EVIDENCE' else 1 if overall == 'PASS_FIXTURE_LOG_READY_FOR_REAL_ACCEPTANCE' else 0}",
            f"RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall={overall} rows={len(rows)}",
            "```",
        ]
    )
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "input_log": str(input_path) if input_path else "",
        "template_path": str(template_path) if template_path else "",
        "target_diameter_mm": args.target_diameter_mm,
        "diameter_tolerance_mm": args.diameter_tolerance_mm,
        "target_rpm": args.target_rpm,
        "rpm_tolerance": args.rpm_tolerance,
        "max_continuous_seconds": args.max_continuous_seconds,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "real_acceptance_evidence": overall == "PASS_FIXTURE_LOG_READY_FOR_REAL_ACCEPTANCE",
        "segment_seconds": segment_seconds,
        "rows": [asdict(row) for row in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "row_number,timestamp,segment_id,shaft_diameter_mm,rpm,sample_seconds,is_template,status,detail,note"
    ]
    for row in rows:
        lines.append(
            ",".join(
                [
                    str(row.row_number),
                    csv_escape(row.timestamp),
                    csv_escape(row.segment_id),
                    "" if row.shaft_diameter_mm is None else f"{row.shaft_diameter_mm:g}",
                    "" if row.rpm is None else f"{row.rpm:g}",
                    "" if row.sample_seconds is None else f"{row.sample_seconds:g}",
                    "1" if row.is_template else "0",
                    csv_escape(row.status),
                    csv_escape(row.detail),
                    csv_escape(row.note),
                ]
            )
        )
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def decide_overall(rows: list[FixtureRow], template_only_ok: bool) -> str:
    if not rows:
        return "FAIL_EMPTY_LOG"
    any_fail = any(row.status != "PASS" for row in rows)
    all_template = all(row.is_template for row in rows)
    any_template = any(row.is_template for row in rows)
    if any_fail:
        return "FAIL_FIXTURE_LOG_INVALID"
    if all_template and template_only_ok:
        return "TEMPLATE_READY_NOT_REAL_EVIDENCE"
    if any_template:
        return "FAIL_TEMPLATE_ROWS_IN_REAL_LOG"
    return "PASS_FIXTURE_LOG_READY_FOR_REAL_ACCEPTANCE"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate rotating-shaft fixture log CSV files.")
    parser.add_argument("--input", type=Path, default=None, help="Fixture CSV to validate.")
    parser.add_argument("--write-template", type=Path, default=None, help="Write a fixture CSV template.")
    parser.add_argument("--template-only-ok", action="store_true", help="Treat template rows as a successful template readiness report.")
    parser.add_argument("--report-prefix", type=Path, default=REPORTS / "rotating_fixture_log_validation_current")
    parser.add_argument("--target-diameter-mm", type=float, default=200.0)
    parser.add_argument("--diameter-tolerance-mm", type=float, default=20.0)
    parser.add_argument("--target-rpm", type=float, default=600.0)
    parser.add_argument("--rpm-tolerance", type=float, default=30.0)
    parser.add_argument("--max-continuous-seconds", type=float, default=600.0)
    args = parser.parse_args()

    template_path = args.write_template
    if template_path is not None:
        write_template(template_path)

    input_path = args.input
    if input_path is None and template_path is not None:
        input_path = template_path

    if input_path is None:
        rows: list[FixtureRow] = []
        segment_seconds: dict[str, float] = {}
        overall = "FAIL_NO_INPUT_LOG"
    else:
        raw_rows = load_rows(input_path)
        rows, segment_seconds = validate_rows(
            raw_rows,
            target_diameter_mm=args.target_diameter_mm,
            diameter_tolerance_mm=args.diameter_tolerance_mm,
            target_rpm=args.target_rpm,
            rpm_tolerance=args.rpm_tolerance,
            max_continuous_seconds=args.max_continuous_seconds,
        )
        overall = decide_overall(rows, args.template_only_ok)

    prefix = args.report_prefix
    if not prefix.is_absolute():
        prefix = ROOT / prefix
    write_reports(prefix, overall, input_path, template_path, rows, segment_seconds, args)

    print(f"RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall={overall} rows={len(rows)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print(f"REPORT_PREFIX={prefix}")
    return 0 if overall in {"TEMPLATE_READY_NOT_REAL_EVIDENCE", "PASS_FIXTURE_LOG_READY_FOR_REAL_ACCEPTANCE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
