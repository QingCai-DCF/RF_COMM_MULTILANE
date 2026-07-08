from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DEFAULT_TEMPLATE_DIR = REPORTS / "real_acceptance_template"
MAX_CONTINUOUS_SECONDS = 600.0
PHYSICAL_MATRIX_REQUIRED_MARKERS = (
    "PHYSICAL_MATRIX_GATE_EXIT=0",
    "PHYSICAL_MATRIX_GATE_RESULT=PASS",
)
PHYSICAL_MATRIX_FORBIDDEN_MARKERS = (
    "physical_matrix_not_passing",
    "PHYSICAL_MATRIX_GATE_RESULT=BLOCK",
    "PHYSICAL_MATRIX_GATE_EXIT=2",
    "PHYSICAL_MATRIX_GATE_EXIT=22",
)


@dataclass(frozen=True)
class ModeSpec:
    mode: str
    description: str
    summary_markers: tuple[str, ...]
    forbidden_markers: tuple[str, ...] = ()
    max_duration_required: bool = True
    criteria_pass: tuple[str, ...] = ()
    optional_real_shutdown_marker: str = ""
    throughput_required: bool = False
    physical_matrix_gate_required: bool = False


@dataclass
class ModeResult:
    mode: str
    description: str
    status: str
    summary_path: str
    criteria_path: str
    fixture_validation_path: str
    real_acceptance_evidence: bool
    issues: list[str]


SPECS: dict[str, ModeSpec] = {
    "ps_pc_tcp_dhcp": ModeSpec(
        mode="ps_pc_tcp_dhcp",
        description="real board PS-to-PC TCP/DHCP/reconnect acceptance",
        summary_markers=(
            "BOARD_TCP_DHCP_ACCEPTANCE_PASS=1",
            "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=0",
            "SMOKE_OK=1",
            "RECONNECT_OK=1",
            "DHCP_OR_STATIC_EVIDENCE_OK=1",
            "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=1",
            "NO_TX_DATA_DONE_BY_THIS_SCRIPT=1",
        ),
        forbidden_markers=(
            "BOARD_TCP_DHCP_DRY_RUN=1",
            "BOARD_TCP_DHCP_ACCEPTANCE_BLOCKED=1",
            "BOARD_TCP_DHCP_BLOCKED_REASON=",
            "REAL_ACCEPTANCE_TEMPLATE=1",
        ),
        max_duration_required=False,
    ),
    "two_ax7010": ModeSpec(
        mode="two_ax7010",
        description="two complete AX7010 systems with bidirectional real traffic",
        summary_markers=(
            "TWO_AX7010_REAL_ACCEPTANCE_PASS=1",
            "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=0",
            "SMOKE_BOTH_OK=1",
            "RECONNECT_BOTH_OK=1",
            "BIDIRECTIONAL_TRAFFIC_OK=1",
            "TWO_AX7010_SHUTDOWN_AFTER_RUN_PASS=1",
            "RAW_HALF_MBPS=32.0",
            "RAW_FDX_PER_DIR_MBPS=16.0",
            "RATE_CLAIM=raw_phy_only",
            "EFFECTIVE_PAYLOAD_REPORTED=1",
            "PAYLOAD_HALF_MBPS=",
            "PAYLOAD_FDX_PER_DIR_MBPS=",
            "NO_FPGA_PROGRAMMING_DONE_BY_THIS_SCRIPT=1",
            "NO_UART_WRITE_DONE_BY_THIS_SCRIPT=1",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
        ),
        forbidden_markers=(
            "TWO_AX7010_DRY_RUN=1",
            "TWO_AX7010_OFFLINE_MODEL_PASS=1",
            "TWO_AX7010_REAL_ACCEPTANCE_BLOCKED=1",
            "TWO_AX7010_BLOCKED_REASON=",
            "REAL_ACCEPTANCE_TEMPLATE=1",
        ),
        criteria_pass=(
            "smoke_both",
            "reconnect_both",
            "bidirectional_traffic",
            "raw_payload_rate_separation",
            "payload_throughput_reported",
            "shutdown_after_run",
            "duration_cap",
        ),
        throughput_required=True,
        physical_matrix_gate_required=True,
    ),
    "product_loop": ModeSpec(
        mode="product_loop",
        description="real PC-PS-PL-IR-external-IR product loop",
        summary_markers=(
            "PRODUCT_LOOP_REAL_ACCEPTANCE_PASS=1",
            "PRODUCT_LOOP_REAL_ACCEPTANCE_BLOCKED=0",
            "PRODUCT_LOOP_TRAFFIC_PASS=1",
            "PRODUCT_LOOP_SHUTDOWN_AFTER_RUN_PASS=1",
            "RAW_HALF_MBPS=32.0",
            "RAW_FDX_PER_DIR_MBPS=16.0",
            "RATE_CLAIM=raw_phy_only",
            "EFFECTIVE_PAYLOAD_REPORTED=1",
            "PAYLOAD_HALF_MBPS=",
            "PAYLOAD_FDX_PER_DIR_MBPS=",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
        ),
        forbidden_markers=(
            "PRODUCT_LOOP_DRY_RUN=1",
            "PRODUCT_LOOP_REAL_ACCEPTANCE_BLOCKED=1",
            "PRODUCT_LOOP_BLOCKED_REASON=",
            "REAL_ACCEPTANCE_TEMPLATE=1",
        ),
        criteria_pass=(
            "product_loop_traffic",
            "raw_payload_rate_separation",
            "payload_throughput_reported",
            "shutdown_after_run",
            "duration_cap",
        ),
        throughput_required=True,
        physical_matrix_gate_required=True,
    ),
    "rotating_shaft": ModeSpec(
        mode="rotating_shaft",
        description="real 200 mm / 600 rpm rotating-shaft communication",
        summary_markers=(
            "ROTATING_SHAFT_REAL_ACCEPTANCE_PASS=1",
            "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=0",
            "ROTATING_SHAFT_TRAFFIC_PASS=1",
            "ROTATING_SHAFT_SHUTDOWN_AFTER_RUN_PASS=1",
            "TARGET_DIAMETER_OK=1",
            "TARGET_RPM_OK=1",
            "FIXTURE_LOG_PROVIDED=1",
            "FIXTURE_LOG_EXISTS=1",
            "FIXTURE_LOG_DIAMETER_OK=1",
            "FIXTURE_LOG_RPM_OK=1",
            "SHAFT_DIAMETER_MM=200",
            "RPM=600",
            "RAW_HALF_MBPS=32.0",
            "RAW_FDX_PER_DIR_MBPS=16.0",
            "RATE_CLAIM=raw_phy_only",
            "EFFECTIVE_PAYLOAD_REPORTED=1",
            "PAYLOAD_HALF_MBPS=",
            "PAYLOAD_FDX_PER_DIR_MBPS=",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
        ),
        forbidden_markers=(
            "ROTATING_SHAFT_DRY_RUN=1",
            "ROTATING_SHAFT_REAL_ACCEPTANCE_BLOCKED=1",
            "ROTATING_SHAFT_BLOCKED_REASON=",
            "REAL_ACCEPTANCE_TEMPLATE=1",
        ),
        criteria_pass=(
            "fixture_log",
            "two_ax7010_traffic",
            "raw_payload_rate_separation",
            "payload_throughput_reported",
            "shutdown_after_run",
            "duration_cap",
        ),
        throughput_required=True,
        physical_matrix_gate_required=True,
    ),
    "eight_lane": ModeSpec(
        mode="eight_lane",
        description="real 8-lane TFDU hardware acceptance",
        summary_markers=(
            "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_PASS=1",
            "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=0",
            "EIGHT_LANE_HARDWARE_SHUTDOWN_BEFORE_RUN_PASS=1",
            "EIGHT_LANE_HARDWARE_TRAFFIC_PASS=1",
            "EIGHT_LANE_HARDWARE_SHUTDOWN_AFTER_RUN_PASS=1",
            "LANE_COUNT_REQUESTED=8",
            "CANDIDATE_A_LANE_COUNT=8",
            "CANDIDATE_B_LANE_COUNT=8",
            "REDUCED_8LANE_FRAG16_BITSTREAM_READY_FOR_REVIEW=1",
            "REDUCED_8LANE_FRAG16_RAW_HALF_MBPS=32.0",
            "REDUCED_8LANE_FRAG16_RAW_FDX_PER_DIR_MBPS=16.0",
            "RAW_HALF_MBPS=32.0",
            "RAW_FDX_PER_DIR_MBPS=16.0",
            "RATE_CLAIM=raw_phy_only",
            "EFFECTIVE_PAYLOAD_REPORTED=1",
            "PAYLOAD_HALF_MBPS=",
            "PAYLOAD_FDX_PER_DIR_MBPS=",
            "NO_TX_DATA_TO_REAL_BOARDS=0",
            "NO_TFDU_DRIVE_DONE_BY_THIS_SCRIPT=0",
        ),
        forbidden_markers=(
            "EIGHT_LANE_HARDWARE_DRY_RUN=1",
            "EIGHT_LANE_HARDWARE_REAL_ACCEPTANCE_BLOCKED=1",
            "EIGHT_LANE_HARDWARE_BLOCKED_REASON=",
            "REAL_ACCEPTANCE_TEMPLATE=1",
        ),
        criteria_pass=(
            "shutdown_before_run",
            "product_loop_traffic",
            "raw_payload_rate_separation",
            "payload_throughput_reported",
            "shutdown_after_run",
            "duration_cap",
        ),
        throughput_required=True,
        physical_matrix_gate_required=True,
    ),
}


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def csv_escape(value: object) -> str:
    text = "" if value is None else str(value)
    return '"' + text.replace('"', '""') + '"'


def parse_path_map(entries: list[str] | None, selected_modes: list[str], label: str) -> tuple[dict[str, Path], list[str]]:
    paths: dict[str, Path] = {}
    issues: list[str] = []
    if not entries:
        return paths, issues
    for entry in entries:
        if "=" in entry:
            mode, raw = entry.split("=", 1)
            mode = mode.strip()
            if mode not in SPECS:
                issues.append(f"{label} uses unknown mode {mode!r}")
                continue
            paths[mode] = Path(raw.strip())
            continue
        if len(selected_modes) == 1:
            paths[selected_modes[0]] = Path(entry.strip())
        else:
            issues.append(f"{label} path without mode is ambiguous when mode=all: {entry}")
    return paths, issues


def parse_duration(text: str) -> float | None:
    match = re.search(r"^DURATION_SECONDS_EFFECTIVE=([0-9]+(?:\.[0-9]+)?)$", text, re.MULTILINE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_float_marker(text: str, name: str) -> float | None:
    match = re.search(rf"^{re.escape(name)}=([0-9]+(?:\.[0-9]+)?)$", text, re.MULTILINE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def validate_throughput_markers(text: str) -> list[str]:
    issues: list[str] = []
    raw_half = parse_float_marker(text, "RAW_HALF_MBPS")
    raw_fdx = parse_float_marker(text, "RAW_FDX_PER_DIR_MBPS")
    payload_half = parse_float_marker(text, "PAYLOAD_HALF_MBPS")
    payload_fdx = parse_float_marker(text, "PAYLOAD_FDX_PER_DIR_MBPS")
    if raw_half is None:
        issues.append("missing numeric RAW_HALF_MBPS")
    elif raw_half < 32.0:
        issues.append(f"RAW_HALF_MBPS={raw_half:g} is below required raw 32 Mbit/s")
    if raw_fdx is None:
        issues.append("missing numeric RAW_FDX_PER_DIR_MBPS")
    elif raw_fdx < 16.0:
        issues.append(f"RAW_FDX_PER_DIR_MBPS={raw_fdx:g} is below required raw 16 Mbit/s per direction")
    if payload_half is None:
        issues.append("missing numeric PAYLOAD_HALF_MBPS")
    elif payload_half < 0:
        issues.append("PAYLOAD_HALF_MBPS must be non-negative")
    if payload_fdx is None:
        issues.append("missing numeric PAYLOAD_FDX_PER_DIR_MBPS")
    elif payload_fdx < 0:
        issues.append("PAYLOAD_FDX_PER_DIR_MBPS must be non-negative")
    if raw_half is not None and payload_half is not None and payload_half > raw_half:
        issues.append(f"PAYLOAD_HALF_MBPS={payload_half:g} exceeds RAW_HALF_MBPS={raw_half:g}")
    if raw_fdx is not None and payload_fdx is not None and payload_fdx > raw_fdx:
        issues.append(f"PAYLOAD_FDX_PER_DIR_MBPS={payload_fdx:g} exceeds RAW_FDX_PER_DIR_MBPS={raw_fdx:g}")
    if "RATE_CLAIM=raw_phy_only" not in text:
        issues.append("RATE_CLAIM must be raw_phy_only for current 32/16 target interpretation")
    if "EFFECTIVE_PAYLOAD_REPORTED=1" not in text:
        issues.append("EFFECTIVE_PAYLOAD_REPORTED=1 marker is missing")
    return issues


def validate_physical_matrix_gate_markers(text: str) -> list[str]:
    issues: list[str] = []
    for marker in PHYSICAL_MATRIX_REQUIRED_MARKERS:
        if marker not in text:
            issues.append(f"missing physical matrix gate pass marker: {marker}")
    for marker in PHYSICAL_MATRIX_FORBIDDEN_MARKERS:
        if marker in text:
            issues.append(f"forbidden physical matrix gate marker present: {marker}")
    return issues


def load_criteria(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        out: dict[str, str] = {}
        for row in csv.DictReader(f):
            criterion = (row.get("criterion") or "").strip()
            status = (row.get("status") or "").strip()
            if criterion:
                out[criterion] = status
        return out


def validate_fixture_validation(path: Path | None) -> list[str]:
    if path is None:
        return ["rotating fixture validation report was not provided"]
    text = read_text(path)
    issues: list[str] = []
    if not text:
        issues.append("rotating fixture validation report is missing or empty")
    if "RF_COMM_ROTATING_FIXTURE_LOG_VALIDATION overall=PASS_FIXTURE_LOG_READY_FOR_REAL_ACCEPTANCE" not in text:
        issues.append("rotating fixture validation did not pass with real non-template rows")
    if "REAL_ACCEPTANCE_EVIDENCE=1" not in text:
        issues.append("rotating fixture validation is not marked as real evidence")
    if "NO_TFDU_DRIVE=1" not in text:
        issues.append("fixture validator no-TFDU marker missing")
    return issues


def validate_mode(
    spec: ModeSpec,
    summary_path: Path | None,
    criteria_path: Path | None,
    fixture_validation_path: Path | None,
    max_continuous_seconds: float,
    template_only_ok: bool,
) -> ModeResult:
    issues: list[str] = []
    if summary_path is None:
        status = "TEMPLATE_READY" if template_only_ok else "FAIL_MISSING_SUMMARY"
        if not template_only_ok:
            issues.append("summary log was not provided")
        return ModeResult(
            mode=spec.mode,
            description=spec.description,
            status=status,
            summary_path="",
            criteria_path=rel(criteria_path),
            fixture_validation_path=rel(fixture_validation_path),
            real_acceptance_evidence=False,
            issues=issues,
        )

    text = read_text(summary_path)
    if not text:
        issues.append("summary log is missing or empty")
    for marker in spec.summary_markers:
        if marker not in text:
            issues.append(f"missing required marker: {marker}")
    for marker in spec.forbidden_markers:
        if marker in text:
            issues.append(f"forbidden marker present: {marker}")
    universal_forbidden_markers = (
        "SYNTHETIC_VALIDATOR_SELFTEST=1",
        "NO_HARDWARE_PROGRAMMING_BY_VALIDATOR=1",
        "NO_UART_WRITE_BY_VALIDATOR=1",
        "NO_TFDU_DRIVE_BY_VALIDATOR=1",
    )
    for marker in universal_forbidden_markers:
        if marker in text:
            issues.append(f"forbidden synthetic/template marker present: {marker}")

    if spec.max_duration_required:
        duration = parse_duration(text)
        if duration is None:
            issues.append("missing DURATION_SECONDS_EFFECTIVE")
        elif duration > max_continuous_seconds:
            issues.append(f"DURATION_SECONDS_EFFECTIVE={duration:g} exceeds cap {max_continuous_seconds:g}")

    if spec.throughput_required:
        issues.extend(validate_throughput_markers(text))

    if spec.physical_matrix_gate_required:
        issues.extend(validate_physical_matrix_gate_markers(text))

    if spec.optional_real_shutdown_marker and spec.optional_real_shutdown_marker not in text:
        issues.append(
            f"missing supplemental shutdown confirmation marker after TFDU-driving run: {spec.optional_real_shutdown_marker}"
        )

    criteria = load_criteria(criteria_path)
    if spec.criteria_pass and criteria_path is not None:
        for criterion in spec.criteria_pass:
            if criteria.get(criterion) != "PASS":
                issues.append(f"criteria {criterion!r} is not PASS")
    elif spec.criteria_pass:
        issues.append("criteria CSV was not provided")

    if spec.mode == "rotating_shaft":
        issues.extend(validate_fixture_validation(fixture_validation_path))

    status = "PASS_REAL_ACCEPTANCE_EVIDENCE" if not issues else "FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE"
    return ModeResult(
        mode=spec.mode,
        description=spec.description,
        status=status,
        summary_path=rel(summary_path),
        criteria_path=rel(criteria_path),
        fixture_validation_path=rel(fixture_validation_path),
        real_acceptance_evidence=not issues,
        issues=issues,
    )


def write_templates(template_dir: Path) -> list[Path]:
    template_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for spec in SPECS.values():
        summary_path = template_dir / f"{spec.mode}_summary_template.txt"
        lines = [
            "REAL_ACCEPTANCE_TEMPLATE=1",
            f"MODE={spec.mode}",
            f"DESCRIPTION={spec.description}",
            "NOTE=replace this file with a real safe-wrapper summary before claiming real acceptance",
            f"MAX_CONTINUOUS_SECONDS={MAX_CONTINUOUS_SECONDS:g}",
            "NO_HARDWARE_PROGRAMMING_BY_VALIDATOR=1",
            "NO_UART_WRITE_BY_VALIDATOR=1",
            "NO_TFDU_DRIVE_BY_VALIDATOR=1",
            "",
            "Required markers in a real summary:",
        ]
        lines.extend(f"REQUIRED_MARKER={marker}" for marker in spec.summary_markers)
        if spec.optional_real_shutdown_marker:
            lines.append(f"REQUIRED_MARKER={spec.optional_real_shutdown_marker}")
        if spec.physical_matrix_gate_required:
            lines.extend(f"REQUIRED_MARKER={marker}" for marker in PHYSICAL_MATRIX_REQUIRED_MARKERS)
        forbidden_markers = list(spec.forbidden_markers)
        if spec.physical_matrix_gate_required:
            forbidden_markers.extend(PHYSICAL_MATRIX_FORBIDDEN_MARKERS)
        if forbidden_markers:
            lines.append("")
            lines.append("Forbidden markers in a real summary:")
            lines.extend(f"FORBIDDEN_MARKER={marker}" for marker in forbidden_markers)
        if spec.criteria_pass:
            lines.append("")
            lines.append("Required PASS criteria when a criteria CSV is supplied:")
            lines.extend(f"REQUIRED_CRITERION_PASS={criterion}" for criterion in spec.criteria_pass)
        summary_path.write_text("\n".join(lines) + "\n", encoding="ascii")
        written.append(summary_path)

        if spec.criteria_pass:
            criteria_path = template_dir / f"{spec.mode}_criteria_template.csv"
            rows = ["criterion,status,value,note"]
            rows.extend(
                f"{csv_escape(criterion)},PASS,{csv_escape('replace_with_real_value')},{csv_escape('template row only')}"
                for criterion in spec.criteria_pass
            )
            criteria_path.write_text("\n".join(rows) + "\n", encoding="ascii")
            written.append(criteria_path)

    manifest_path = template_dir / "real_acceptance_template_manifest.csv"
    manifest = ["mode,description,summary_template,criteria_template"]
    for spec in SPECS.values():
        criteria_name = f"{spec.mode}_criteria_template.csv" if spec.criteria_pass else ""
        manifest.append(
            ",".join(
                [
                    csv_escape(spec.mode),
                    csv_escape(spec.description),
                    csv_escape(f"{spec.mode}_summary_template.txt"),
                    csv_escape(criteria_name),
                ]
            )
        )
    manifest_path.write_text("\n".join(manifest) + "\n", encoding="ascii")
    written.append(manifest_path)
    return written


def write_reports(
    prefix: Path,
    overall: str,
    results: list[ModeResult],
    template_paths: list[Path],
    args: argparse.Namespace,
) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    md_path = prefix.with_suffix(".md")
    json_path = prefix.with_suffix(".json")
    csv_path = prefix.with_suffix(".csv")

    md = [
        "# Real Acceptance Evidence Validation",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Modes checked: `{len(results)}`",
        f"- Template files written: `{len(template_paths)}`",
        f"- Continuous physical run cap: `{args.max_continuous_seconds:g}` seconds",
        "- This validator reads logs only. It does not program hardware, write UART, send TX data, or drive TFDU boards.",
        "",
        "## Results",
        "",
        "| mode | status | real evidence | summary | issues |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        issue_text = "; ".join(result.issues) if result.issues else "none"
        md.append(
            "| "
            + " | ".join(
                [
                    result.mode,
                    result.status,
                    "1" if result.real_acceptance_evidence else "0",
                    result.summary_path or "not provided",
                    issue_text.replace("|", "/"),
                ]
            )
            + " |"
        )

    if template_paths:
        md.extend(["", "## Templates", "", "| path |", "| --- |"])
        for path in template_paths:
            md.append(f"| {rel(path)} |")

    md.extend(
        [
            "",
            "```text",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            f"REAL_ACCEPTANCE_EVIDENCE={1 if overall == 'PASS_REAL_ACCEPTANCE_EVIDENCE' else 0}",
            f"RF_COMM_REAL_ACCEPTANCE_EVIDENCE_VALIDATION overall={overall} modes={len(results)}",
            "```",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "mode_count": len(results),
        "template_paths": [rel(path) for path in template_paths],
        "max_continuous_seconds": args.max_continuous_seconds,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "real_acceptance_evidence": overall == "PASS_REAL_ACCEPTANCE_EVIDENCE",
        "results": [asdict(result) for result in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = ["mode,description,status,real_acceptance_evidence,summary_path,criteria_path,fixture_validation_path,issues"]
    for result in results:
        lines.append(
            ",".join(
                [
                    csv_escape(result.mode),
                    csv_escape(result.description),
                    csv_escape(result.status),
                    "1" if result.real_acceptance_evidence else "0",
                    csv_escape(result.summary_path),
                    csv_escape(result.criteria_path),
                    csv_escape(result.fixture_validation_path),
                    csv_escape("; ".join(result.issues)),
                ]
            )
        )
    csv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def decide_overall(results: list[ModeResult], template_paths: list[Path], template_only_ok: bool) -> str:
    if template_only_ok and template_paths and all(result.status == "TEMPLATE_READY" for result in results):
        return "TEMPLATE_READY_NOT_REAL_EVIDENCE"
    if results and all(result.real_acceptance_evidence for result in results):
        return "PASS_REAL_ACCEPTANCE_EVIDENCE"
    return "FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE"


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate real hardware acceptance evidence logs.")
    parser.add_argument("--mode", choices=["all", *SPECS.keys()], default="all")
    parser.add_argument("--summary", action="append", default=[], help="Summary path, or mode=summary_path when mode=all.")
    parser.add_argument("--criteria", action="append", default=[], help="Criteria CSV path, or mode=criteria_path when mode=all.")
    parser.add_argument(
        "--fixture-validation",
        action="append",
        default=[],
        help="Rotating fixture validator report, or rotating_shaft=path.",
    )
    parser.add_argument("--write-template", type=Path, default=None)
    parser.add_argument("--template-only-ok", action="store_true")
    parser.add_argument("--report-prefix", type=Path, default=REPORTS / "real_acceptance_evidence_validation_current")
    parser.add_argument("--max-continuous-seconds", type=float, default=MAX_CONTINUOUS_SECONDS)
    args = parser.parse_args()

    selected_modes = list(SPECS.keys()) if args.mode == "all" else [args.mode]
    summary_map, summary_issues = parse_path_map(args.summary, selected_modes, "summary")
    criteria_map, criteria_issues = parse_path_map(args.criteria, selected_modes, "criteria")
    fixture_map, fixture_issues = parse_path_map(args.fixture_validation, selected_modes, "fixture-validation")

    template_dir = args.write_template or (DEFAULT_TEMPLATE_DIR if args.template_only_ok else None)
    template_paths = write_templates(template_dir if template_dir is not None else DEFAULT_TEMPLATE_DIR) if template_dir else []

    results: list[ModeResult] = []
    setup_issues = summary_issues + criteria_issues + fixture_issues
    for mode in selected_modes:
        result = validate_mode(
            SPECS[mode],
            summary_map.get(mode),
            criteria_map.get(mode),
            fixture_map.get(mode),
            args.max_continuous_seconds,
            args.template_only_ok and not summary_map,
        )
        if setup_issues:
            result.issues.extend(setup_issues)
            result.status = "FAIL_REAL_ACCEPTANCE_EVIDENCE_INCOMPLETE"
            result.real_acceptance_evidence = False
        results.append(result)

    prefix = args.report_prefix
    if not prefix.is_absolute():
        prefix = ROOT / prefix
    overall = decide_overall(results, template_paths, args.template_only_ok and not summary_map)
    write_reports(prefix, overall, results, template_paths, args)

    print(f"RF_COMM_REAL_ACCEPTANCE_EVIDENCE_VALIDATION overall={overall} modes={len(results)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print(f"REAL_ACCEPTANCE_EVIDENCE={1 if overall == 'PASS_REAL_ACCEPTANCE_EVIDENCE' else 0}")
    print(f"REPORT_PREFIX={prefix}")
    return 0 if overall in {"TEMPLATE_READY_NOT_REAL_EVIDENCE", "PASS_REAL_ACCEPTANCE_EVIDENCE"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
