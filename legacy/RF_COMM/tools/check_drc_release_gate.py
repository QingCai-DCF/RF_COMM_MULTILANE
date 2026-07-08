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

RELEASE_BLOCKING_DISPOSITIONS = {
    "BLOCK_RELEASE",
    "FIX_CONSTRAINTS_BEFORE_RELEASE",
    "OPTIMIZE_BEFORE_4_OR_8_LANE",
    "REVIEW_DMA_FIFO_COLLISION",
    "REVIEW_REQUIRED",
}

DEBUG_CONTINUE_DISPOSITIONS = {
    "WAIVER_CANDIDATE_DEBUG_OR_IP",
    "WAIVER_CANDIDATE_DEBUG_OR_GENERATED_IP",
    "FIX_CONSTRAINTS_BEFORE_RELEASE",
    "OPTIMIZE_BEFORE_4_OR_8_LANE",
    "REVIEW_DMA_FIFO_COLLISION",
}


@dataclass(frozen=True)
class GateRow:
    item: str
    status: str
    expected: str
    actual: str
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


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def latest(pattern: str) -> Path | None:
    paths = [p for p in ROOT.glob(pattern) if p.is_file()]
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def add(rows: list[GateRow], item: str, ok: bool, expected: str, actual: str, evidence: Path | None, note: str) -> None:
    rows.append(
        GateRow(
            item=item,
            status="PASS" if ok else "FAIL",
            expected=expected,
            actual=actual,
            evidence=rel(evidence),
            note=note,
        )
    )


def rule_names(rules: list[dict[str, Any]], disposition: str | None = None) -> list[str]:
    out: list[str] = []
    for rule in rules:
        if disposition is not None and rule.get("disposition") != disposition:
            continue
        out.append(f"{rule.get('rule')}:{rule.get('disposition')}:{rule.get('violations')}")
    return out


def as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_rows() -> tuple[list[GateRow], dict[str, Any]]:
    constraint = find_constraint()
    triage_json = latest("reports/drc_triage_current_*.json")
    triage_md = latest("reports/drc_triage_current_*.md")
    action_map_json = REPORTS / "drc_release_action_map_current.json"
    action_map = read_json(action_map_json)
    action_rows_raw = action_map.get("actions") if isinstance(action_map.get("actions"), list) else action_map.get("rows")
    action_rows = [row for row in action_rows_raw if isinstance(row, dict)] if isinstance(action_rows_raw, list) else []
    triage = read_json(triage_json)
    rules_raw = triage.get("rules") if isinstance(triage.get("rules"), list) else []
    rules = [rule for rule in rules_raw if isinstance(rule, dict)]
    build = triage.get("build") if isinstance(triage.get("build"), dict) else {}

    critical_or_error = [
        rule
        for rule in rules
        if str(rule.get("severity", "")).lower() in {"critical", "critical warning", "error"}
        or rule.get("disposition") == "BLOCK_RELEASE"
    ]
    release_blocking = [rule for rule in rules if str(rule.get("disposition", "")) in RELEASE_BLOCKING_DISPOSITIONS]
    unknown_or_forbidden = [
        rule
        for rule in rules
        if str(rule.get("disposition", "")) not in DEBUG_CONTINUE_DISPOSITIONS
        and str(rule.get("disposition", "")) not in {"BLOCK_RELEASE"}
    ]
    debug_waiver_candidates = [
        rule
        for rule in rules
        if str(rule.get("disposition", "")).startswith("WAIVER_CANDIDATE_DEBUG")
    ]
    prerelease_actions = [rule for rule in release_blocking if rule.get("disposition") != "BLOCK_RELEASE"]

    wns = as_float(build.get("timing_wns_ns"))
    whs = as_float(build.get("timing_whs_ns"))
    route_errors = build.get("route_errors")
    try:
        route_errors_int = int(route_errors)
    except (TypeError, ValueError):
        route_errors_int = -1

    timing_actions = [
        rule for rule in rules if str(rule.get("disposition")) == "FIX_CONSTRAINTS_BEFORE_RELEASE"
    ]
    dma_actions = [rule for rule in rules if str(rule.get("disposition")) == "REVIEW_DMA_FIFO_COLLISION"]
    control_set_actions = [rule for rule in rules if str(rule.get("disposition")) == "OPTIMIZE_BEFORE_4_OR_8_LANE"]
    cleared_control_set_actions = [
        row
        for row in action_rows
        if row.get("blocker") == "ULMTCS-2" and str(row.get("status", "")).startswith("CLEARED_")
    ]
    effective_release_blocking = [
        rule
        for rule in release_blocking
        if not (
            rule.get("rule") == "ULMTCS-2"
            and rule.get("disposition") == "OPTIMIZE_BEFORE_4_OR_8_LANE"
            and cleared_control_set_actions
        )
    ]
    effective_prerelease_actions = [rule for rule in effective_release_blocking if rule.get("disposition") != "BLOCK_RELEASE"]

    rows: list[GateRow] = []
    add(
        rows,
        "hard_constraint_unchanged",
        constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256,
        EXPECTED_CONSTRAINT_SHA256,
        sha256(constraint),
        constraint,
        "Gate is tied to the hard project target and did not edit it.",
    )
    add(
        rows,
        "triage_json_available",
        triage_json is not None and bool(rules),
        "current DRC triage JSON with parsed rules",
        f"path={rel(triage_json)} rules={len(rules)}",
        triage_json,
        "Uses the existing routed DRC/methodology triage as source evidence.",
    )
    add(
        rows,
        "debug_build_timing_routed",
        route_errors_int == 0 and wns is not None and whs is not None and wns >= 0.0 and whs >= 0.0,
        "route_errors=0, WNS>=0, WHS>=0",
        f"route_errors={route_errors} WNS={build.get('timing_wns_ns')} WHS={build.get('timing_whs_ns')}",
        triage_json,
        "Current build remains usable for debug/bring-up evidence while release blockers stay open.",
    )
    add(
        rows,
        "no_drc_error_or_critical_release_block",
        not critical_or_error,
        "no DRC ERROR/CRITICAL/BLOCK_RELEASE entries",
        ", ".join(rule_names(critical_or_error)) or "none",
        triage_json,
        "There is no immediate critical DRC release blocker in the parsed triage.",
    )
    add(
        rows,
        "debug_waiver_candidates_separated",
        len(debug_waiver_candidates) > 0 and all(str(rule.get("disposition", "")).startswith("WAIVER_CANDIDATE_DEBUG") for rule in debug_waiver_candidates),
        "debug/generated-IP waiver candidates are separated from release blockers",
        ", ".join(rule_names(debug_waiver_candidates)) or "none",
        triage_json,
        "Debug/IP warnings are not silently counted as release-ready.",
    )
    add(
        rows,
        "timing_constraint_actions_cleared_or_block_release",
        all(rule.get("rule") in {"TIMING-24", "TIMING-28"} for rule in timing_actions),
        "TIMING-24/TIMING-28 either cleared, or classified as pre-release constraint actions",
        ", ".join(rule_names(timing_actions)) or "cleared",
        triage_json,
        "Broad clock exception interactions must not be silently accepted; cleared rules are recorded as cleared.",
    )
    add(
        rows,
        "dma_writefirst_review_blocks_release",
        len(dma_actions) > 0,
        "REQP-181 DMA FIFO WRITE_FIRST review remains required",
        ", ".join(rule_names(dma_actions)) or "none",
        triage_json,
        "AXI DMA FIFO advisory must be validated by DMA/PS traffic before release.",
    )
    add(
        rows,
        "control_set_action_blocks_expansion",
        bool(cleared_control_set_actions) or len(control_set_actions) > 0,
        "ULMTCS-2 is either cleared by release-personality evidence or remains a controlled pre-release action",
        (
            "cleared_by_action_map"
            if cleared_control_set_actions
            else ", ".join(rule_names(control_set_actions)) or "none"
        ),
        action_map_json if cleared_control_set_actions else triage_json,
        (
            "Release-personality DCP clears the control-set guideline; keep the remap hook in the release flow."
            if cleared_control_set_actions
            else "Control-set usage is below device limit but still blocks release expansion until resolved or justified."
        ),
    )
    add(
        rows,
        "release_not_ready_is_enforced",
        len(effective_release_blocking) > 0,
        "gate must block release while pre-release actions remain",
        ", ".join(rule_names(effective_release_blocking)) or "none",
        action_map_json if cleared_control_set_actions else triage_json,
        "This is a positive guard check: the project must not be marked release-ready yet.",
    )
    add(
        rows,
        "unknown_rules_not_silently_accepted",
        not unknown_or_forbidden,
        "no unclassified non-blocking DRC dispositions",
        ", ".join(rule_names(unknown_or_forbidden)) or "none",
        triage_json,
        "Any future unclassified rule should fail this gate until triaged.",
    )
    add(
        rows,
        "no_hardware_side_effects",
        True,
        "no FPGA programming, UART write, TFDU drive, Vivado run, or bitstream generation",
        "read-only Python report generation",
        triage_md,
        "This gate only reads reports and writes reports/drc_release_gate_current.*.",
    )

    row_failures = sum(1 for row in rows if row.status != "PASS")
    if row_failures:
        overall = "FAIL_DRC_RELEASE_GATE"
    elif effective_release_blocking:
        overall = "BLOCK_RELEASE_NOT_READY_DEBUG_CAN_CONTINUE"
    else:
        overall = "PASS_RELEASE_READY_FROM_DRC_GATE"

    metadata: dict[str, Any] = {
        "overall": overall,
        "release_ready": int(overall == "PASS_RELEASE_READY_FROM_DRC_GATE"),
        "debug_can_continue": int(row_failures == 0 and not critical_or_error),
        "row_failures": row_failures,
        "rule_count": len(rules),
        "release_blocking_count": sum(int(rule.get("violations", 0)) for rule in effective_release_blocking),
        "prerelease_action_count": sum(int(rule.get("violations", 0)) for rule in effective_prerelease_actions),
        "debug_waiver_candidate_count": sum(int(rule.get("violations", 0)) for rule in debug_waiver_candidates),
        "triage_json": rel(triage_json),
        "triage_markdown": rel(triage_md),
        "no_hardware_programming": 1,
        "no_uart_write": 1,
        "no_tfdu_drive": 1,
        "no_vivado_run": 1,
        "release_blocking_rules": rule_names(effective_release_blocking),
        "action_map_json": rel(action_map_json),
        "ulmtcs_cleared_by_action_map": int(bool(cleared_control_set_actions)),
    }
    return rows, metadata


def md_table(rows: list[GateRow]) -> str:
    lines = [
        "| item | status | expected | actual | evidence | note |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        cells = [row.item, row.status, row.expected, row.actual, row.evidence, row.note]
        lines.append("| " + " | ".join(str(cell).replace("\n", " ").replace("|", "/") for cell in cells) + " |")
    return "\n".join(lines)


def write_reports(rows: list[GateRow], metadata: dict[str, Any]) -> tuple[Path, Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "drc_release_gate_current.md"
    json_path = REPORTS / "drc_release_gate_current.json"
    csv_path = REPORTS / "drc_release_gate_current.csv"

    md = "\n".join(
        [
            "# DRC Release Gate",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{metadata['overall']}`",
            f"- Release ready: `{metadata['release_ready']}`",
            f"- Debug can continue: `{metadata['debug_can_continue']}`",
            f"- Release-blocking violation count: `{metadata['release_blocking_count']}`",
            f"- Pre-release action count: `{metadata['prerelease_action_count']}`",
            f"- Debug waiver-candidate violation count: `{metadata['debug_waiver_candidate_count']}`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "- No Vivado run: `1`",
            "",
            "This gate is intentionally conservative: debug bring-up can continue when timing routes cleanly and no critical/error DRC exists, but release and 4/8-lane expansion remain blocked until the listed pre-release actions are fixed, validated, or formally waived.",
            "",
            "## Checks",
            "",
            md_table(rows),
            "",
            "## Blocking Rules",
            "",
            "```text",
            "\n".join(metadata["release_blocking_rules"]) or "none",
            "```",
            "",
            "```text",
            f"RF_COMM_DRC_RELEASE_GATE overall={metadata['overall']} release_ready={metadata['release_ready']} debug_can_continue={metadata['debug_can_continue']} release_blocking={metadata['release_blocking_count']} row_failures={metadata['row_failures']}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "NO_VIVADO_RUN=1",
            "```",
            "",
        ]
    )
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(
        json.dumps({"metadata": metadata, "rows": [asdict(row) for row in rows]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))
    return md_path, json_path, csv_path


def main() -> int:
    rows, metadata = build_rows()
    md_path, json_path, csv_path = write_reports(rows, metadata)
    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_DRC_RELEASE_GATE "
        f"overall={metadata['overall']} "
        f"release_ready={metadata['release_ready']} "
        f"debug_can_continue={metadata['debug_can_continue']} "
        f"release_blocking={metadata['release_blocking_count']} "
        f"row_failures={metadata['row_failures']}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_VIVADO_RUN=1")
    return 0 if metadata["row_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
