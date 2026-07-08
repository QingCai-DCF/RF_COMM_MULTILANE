from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import validate_real_acceptance_evidence as validator


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
OUT_DIR = REPORTS / "real_acceptance_validator_selftest_current"
MAX_SECONDS = validator.MAX_CONTINUOUS_SECONDS


@dataclass
class SelfTestCase:
    name: str
    mode: str
    expected_real_evidence: int
    actual_real_evidence: int
    expected_status_prefix: str
    actual_status: str
    status: str
    summary_path: str
    criteria_path: str
    fixture_validation_path: str
    expected_issue_fragment: str
    actual_issues: str
    note: str


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def csv_escape(value: object) -> str:
    text = "" if value is None else str(value)
    return '"' + text.replace('"', '""') + '"'


def write_summary(path: Path, lines: Iterable[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="ascii")
    return path


def write_criteria(path: Path, criteria: Iterable[str], fail: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["criterion,status,value,note"]
    for criterion in criteria:
        status = "FAIL" if criterion == fail else "PASS"
        rows.append(",".join([csv_escape(criterion), status, csv_escape("synthetic"), csv_escape("validator self-test")]))
    path.write_text("\n".join(rows) + "\n", encoding="ascii")
    return path


def all_required_summary(spec: validator.ModeSpec, extra: Iterable[str] = (), omit: Iterable[str] = ()) -> list[str]:
    omit_set = set(omit)
    lines = [
        "SYNTHETIC_VALIDATOR_SELFTEST=1",
        f"MODE={spec.mode}",
        "DURATION_SECONDS_EFFECTIVE=600",
    ]
    lines.extend(marker for marker in spec.summary_markers if marker not in omit_set)
    lines.extend(extra)
    return lines


def physical_gate_pass_lines() -> tuple[str, str]:
    return (
        "PHYSICAL_MATRIX_GATE_OUTPUT=PHYSICAL_MATRIX_GATE_RESULT=PASS",
        "PHYSICAL_MATRIX_GATE_EXIT=0",
    )


def validate_case(
    name: str,
    spec: validator.ModeSpec,
    summary_path: Path | None,
    criteria_path: Path | None,
    fixture_validation_path: Path | None,
    expected_real_evidence: bool,
    expected_status_prefix: str,
    expected_issue_fragment: str,
    note: str,
) -> SelfTestCase:
    result = validator.validate_mode(
        spec,
        summary_path,
        criteria_path,
        fixture_validation_path,
        MAX_SECONDS,
        template_only_ok=False,
    )
    issue_text = "; ".join(result.issues)
    ok = (
        result.real_acceptance_evidence == expected_real_evidence
        and result.status.startswith(expected_status_prefix)
        and (not expected_issue_fragment or expected_issue_fragment in issue_text)
    )
    return SelfTestCase(
        name=name,
        mode=spec.mode,
        expected_real_evidence=int(expected_real_evidence),
        actual_real_evidence=int(result.real_acceptance_evidence),
        expected_status_prefix=expected_status_prefix,
        actual_status=result.status,
        status="PASS" if ok else "FAIL",
        summary_path=rel(summary_path),
        criteria_path=rel(criteria_path),
        fixture_validation_path=rel(fixture_validation_path),
        expected_issue_fragment=expected_issue_fragment,
        actual_issues=issue_text or "none",
        note=note,
    )


def template_summary_path(mode: str) -> Path:
    return REPORTS / "real_acceptance_template" / f"{mode}_summary_template.txt"


def template_criteria_path(mode: str) -> Path | None:
    path = REPORTS / "real_acceptance_template" / f"{mode}_criteria_template.csv"
    return path if path.exists() else None


def build_cases() -> list[SelfTestCase]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cases: list[SelfTestCase] = []

    for mode, spec in validator.SPECS.items():
        cases.append(
            validate_case(
                f"template_summary_rejected_{mode}",
                spec,
                template_summary_path(mode),
                template_criteria_path(mode),
                None,
                expected_real_evidence=False,
                expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
                expected_issue_fragment="REAL_ACCEPTANCE_TEMPLATE=1",
                note="A template file must never become real acceptance evidence when supplied as a summary.",
            )
        )

    two_ax = validator.SPECS["two_ax7010"]
    two_ax_criteria = write_criteria(OUT_DIR / "two_ax7010_pass_criteria.csv", two_ax.criteria_pass)
    cases.append(
        validate_case(
            "dry_run_blocked_rejected",
            two_ax,
            write_summary(
                OUT_DIR / "two_ax7010_dry_run_blocked.summary.txt",
                all_required_summary(
                    two_ax,
                    extra=(
                        *physical_gate_pass_lines(),
                        "TWO_AX7010_DRY_RUN=1",
                        "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1",
                        "TWO_AX7010_BLOCKED_REASON=ethernet_link_not_up",
                        "PAYLOAD_HALF_MBPS=28.0",
                        "PAYLOAD_FDX_PER_DIR_MBPS=14.0",
                    ),
                ),
            ),
            two_ax_criteria,
            None,
            expected_real_evidence=False,
            expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
            expected_issue_fragment="forbidden marker present: TWO_AX7010_DRY_RUN=1",
            note="Dry-run/no-Ethernet blocker logs cannot be promoted to real two-AX7010 acceptance.",
        )
    )
    cases.append(
        validate_case(
            "missing_physical_matrix_gate_rejected",
            two_ax,
            write_summary(
                OUT_DIR / "two_ax7010_missing_physical_matrix_gate.summary.txt",
                all_required_summary(
                    two_ax,
                    extra=("PAYLOAD_HALF_MBPS=28.0", "PAYLOAD_FDX_PER_DIR_MBPS=14.0"),
                ),
            ),
            two_ax_criteria,
            None,
            expected_real_evidence=False,
            expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
            expected_issue_fragment="missing physical matrix gate pass marker: PHYSICAL_MATRIX_GATE_EXIT=0",
            note="TFDU-driving real acceptance cannot pass unless the physical matrix gate passed first.",
        )
    )
    cases.append(
        validate_case(
            "missing_shutdown_marker_rejected",
            two_ax,
            write_summary(
                OUT_DIR / "two_ax7010_missing_shutdown.summary.txt",
                all_required_summary(
                    two_ax,
                    extra=(*physical_gate_pass_lines(), "PAYLOAD_HALF_MBPS=28.0", "PAYLOAD_FDX_PER_DIR_MBPS=14.0"),
                    omit=("TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=1",),
                ),
            ),
            two_ax_criteria,
            None,
            expected_real_evidence=False,
            expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
            expected_issue_fragment="missing required marker: TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=1",
            note="Any TFDU-driving real two-board run must prove shutdown-after-run.",
        )
    )
    cases.append(
        validate_case(
            "payload_over_raw_rejected",
            two_ax,
            write_summary(
                OUT_DIR / "two_ax7010_payload_over_raw.summary.txt",
                all_required_summary(
                    two_ax,
                    extra=(*physical_gate_pass_lines(), "PAYLOAD_HALF_MBPS=33.0", "PAYLOAD_FDX_PER_DIR_MBPS=17.0"),
                ),
            ),
            two_ax_criteria,
            None,
            expected_real_evidence=False,
            expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
            expected_issue_fragment="PAYLOAD_HALF_MBPS=33 exceeds RAW_HALF_MBPS=32",
            note="Effective payload claims cannot exceed the raw PHY budget.",
        )
    )

    product = validator.SPECS["product_loop"]
    product_criteria = write_criteria(OUT_DIR / "product_loop_pass_criteria.csv", product.criteria_pass)
    cases.append(
        validate_case(
            "duration_over_cap_rejected",
            product,
            write_summary(
                OUT_DIR / "product_loop_duration_over_cap.summary.txt",
                [
                    line if not line.startswith("DURATION_SECONDS_EFFECTIVE=") else "DURATION_SECONDS_EFFECTIVE=601"
                    for line in all_required_summary(
                        product,
                        extra=(*physical_gate_pass_lines(), "PAYLOAD_HALF_MBPS=28.0", "PAYLOAD_FDX_PER_DIR_MBPS=14.0"),
                    )
                ],
            ),
            product_criteria,
            None,
            expected_real_evidence=False,
            expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
            expected_issue_fragment="DURATION_SECONDS_EFFECTIVE=601 exceeds cap 600",
            note="Physical continuous-run evidence above 600 s must be rejected under the active cap.",
        )
    )

    rotating = validator.SPECS["rotating_shaft"]
    rotating_criteria = write_criteria(OUT_DIR / "rotating_shaft_pass_criteria.csv", rotating.criteria_pass)
    cases.append(
        validate_case(
            "rotating_template_fixture_rejected",
            rotating,
            write_summary(
                OUT_DIR / "rotating_shaft_template_fixture.summary.txt",
                all_required_summary(
                    rotating,
                    extra=(*physical_gate_pass_lines(), "PAYLOAD_HALF_MBPS=28.0", "PAYLOAD_FDX_PER_DIR_MBPS=14.0"),
                ),
            ),
            rotating_criteria,
            REPORTS / "rotating_fixture_log_validation_current.md",
            expected_real_evidence=False,
            expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
            expected_issue_fragment="rotating fixture validation did not pass with real non-template rows",
            note="Rotating-shaft acceptance needs a real non-template fixture validation report.",
        )
    )

    eight = validator.SPECS["eight_lane"]
    eight_criteria_missing_shutdown = write_criteria(
        OUT_DIR / "eight_lane_missing_shutdown_before.criteria.csv",
        eight.criteria_pass,
        fail="shutdown_before_run",
    )
    cases.append(
        validate_case(
            "eight_lane_shutdown_before_criterion_rejected",
            eight,
            write_summary(
                OUT_DIR / "eight_lane_shutdown_before_missing.summary.txt",
                all_required_summary(
                    eight,
                    extra=(*physical_gate_pass_lines(), "PAYLOAD_HALF_MBPS=28.0", "PAYLOAD_FDX_PER_DIR_MBPS=14.0"),
                ),
            ),
            eight_criteria_missing_shutdown,
            None,
            expected_real_evidence=False,
            expected_status_prefix="FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE",
            expected_issue_fragment="criteria 'shutdown_before_run' is not PASS",
            note="8-lane real hardware evidence must prove shutdown-before-run as well as shutdown-after-run.",
        )
    )

    return cases


def md_table(cases: list[SelfTestCase]) -> str:
    lines = [
        "| case | mode | status | actual validator status | expected issue | actual issues |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        cells = [
            case.name,
            case.mode,
            case.status,
            case.actual_status,
            case.expected_issue_fragment,
            case.actual_issues,
        ]
        lines.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "/") for cell in cells) + " |")
    return "\n".join(lines)


def write_reports(cases: list[SelfTestCase]) -> str:
    failures = [case for case in cases if case.status != "PASS"]
    overall = "PASS_VALIDATOR_REJECTS_FALSE_REAL_EVIDENCE" if not failures else "FAIL"
    generated = datetime.now().isoformat(timespec="seconds")
    md_path = REPORTS / "real_acceptance_validator_selftest_current.md"
    json_path = REPORTS / "real_acceptance_validator_selftest_current.json"
    csv_path = REPORTS / "real_acceptance_validator_selftest_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(cases[0]).keys()))
        writer.writeheader()
        for case in cases:
            writer.writerow(asdict(case))

    md = [
        "# Real Acceptance Validator Self-Test",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Cases: `{len(cases)}`",
        f"- Failures: `{len(failures)}`",
        "- Evidence type: `SYNTHETIC_NEGATIVE_VALIDATOR_TESTS_NOT_REAL_HARDWARE`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "- Real acceptance evidence produced: `0`",
        "",
        "These self-tests intentionally feed synthetic false-real evidence to the validator and require it to reject every case.",
        "",
        "## Cases",
        "",
        md_table(cases),
        "",
        "```text",
        f"RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall={overall} cases={len(cases)} failures={len(failures)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "REAL_ACCEPTANCE_EVIDENCE_PRODUCED=0",
        "TEMPLATE_SUMMARY_REJECTION=1",
        "DRY_RUN_REJECTION=1",
        "DURATION_CAP_REJECTION=1",
        "SHUTDOWN_GATING_REJECTION=1",
        "PHYSICAL_MATRIX_GATE_REJECTION=1",
        "RAW_PAYLOAD_OVERCLAIM_REJECTION=1",
        "ROTATING_TEMPLATE_FIXTURE_REJECTION=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "case_count": len(cases),
        "failures": len(failures),
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "real_acceptance_evidence_produced": False,
        "synthetic_case_dir": rel(OUT_DIR),
        "cases": [asdict(case) for case in cases],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return overall


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    cases = build_cases()
    overall = write_reports(cases)
    failures = sum(1 for case in cases if case.status != "PASS")
    print(f"RF_COMM_REAL_ACCEPTANCE_VALIDATOR_SELFTEST overall={overall} cases={len(cases)} failures={failures}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("REAL_ACCEPTANCE_EVIDENCE_PRODUCED=0")
    print(f"SYNTHETIC_CASE_DIR={OUT_DIR}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
