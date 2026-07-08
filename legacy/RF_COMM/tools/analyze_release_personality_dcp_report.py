from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from analyze_control_sets_release_blocker import build_category_rows, parse_control_rows  # noqa: E402
from check_external_reduced_2lane_route import parse_drc, parse_route_status, parse_timing_summary, parse_utilization  # noqa: E402


@dataclass(frozen=True)
class CheckRow:
    check: str
    status: str
    expected: str
    actual: str
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


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def latest_meta() -> Path | None:
    metas = sorted(REPORTS.glob("release_personality_dcp_report_*.meta.txt"), key=lambda path: path.stat().st_mtime, reverse=True)
    return metas[0] if metas else None


def parse_meta(path: Path | None) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in read_text(path).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def meta_path(meta: dict[str, str], key: str) -> Path | None:
    value = meta.get(key, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def parse_methodology_rules(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for match in re.finditer(r"\|\s*([A-Z0-9-]+)\s*\|\s*(Warning|Advisory|Critical Warning|Error)\s*\|[^|]*\|\s*(\d+)\s*\|", text):
        rows.append({"rule": match.group(1), "severity": match.group(2), "violations": int(match.group(3))})
    return rows


def rule_count(rows: list[dict[str, Any]], name: str) -> int:
    return sum(int(row.get("violations", 0)) for row in rows if row.get("rule") == name)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def build_report() -> tuple[list[CheckRow], list[dict[str, Any]], dict[str, Any]]:
    constraint = find_hard_constraint()
    meta_file = latest_meta()
    meta = parse_meta(meta_file)
    out_dir = meta_path(meta, "out_dir")
    dcp = meta_path(meta, "dcp")
    vivado_log = meta_path(meta, "vivado_log")
    stderr_log = meta_path(meta, "stderr")

    timing_rpt = out_dir / "timing_summary_post_route.rpt" if out_dir else None
    util_rpt = out_dir / "utilization_post_route.rpt" if out_dir else None
    route_rpt = out_dir / "route_status_post_route.rpt" if out_dir else None
    drc_rpt = out_dir / "drc_post_route.rpt" if out_dir else None
    methodology_rpt = out_dir / "methodology_post_route.rpt" if out_dir else None
    control_rpt = out_dir / "control_sets_post_route.rpt" if out_dir else None

    timing = parse_timing_summary(read_text(timing_rpt))
    route = parse_route_status(read_text(route_rpt))
    drc = parse_drc(read_text(drc_rpt))
    methodology_text = read_text(methodology_rpt)
    methodology_rules = parse_methodology_rules(methodology_text)
    control_rows = parse_control_rows(read_text(control_rpt))
    category_rows = build_category_rows(control_rows)
    categories = [asdict(row) for row in category_rows]
    category_map = {row["category"]: row for row in categories}
    active_payload = read_json(REPORTS / "control_sets_release_blocker_current.json")
    active_meta = active_payload.get("metadata") if isinstance(active_payload.get("metadata"), dict) else {}
    active_total = int(active_meta.get("total_control_sets", 0))
    candidate_total = len(control_rows)
    guideline_limit = int(active_meta.get("guideline_limit", 660))
    reduction_vs_active = active_total - candidate_total
    remaining_over_guideline = max(0, candidate_total - guideline_limit)
    debug_sets = int(category_map.get("debug_hub", {}).get("control_sets", 0)) + int(category_map.get("debug_ila", {}).get("control_sets", 0))
    loopback_sets = int(category_map.get("user_ir_loopback_partner", {}).get("control_sets", 0))
    timing_clean = bool(timing.get("constraints_met")) and float(timing.get("wns_ns") or -1.0) >= 0.0 and float(timing.get("whs_ns") or -1.0) >= 0.0
    route_clean = route.get("routing_errors") == 0
    no_hw = all(meta.get(key) == "1" for key in ["no_hardware_programming", "no_uart_write", "no_tfdu_drive"])
    no_build = all(meta.get(key) == "1" for key in ["no_synthesis", "no_implementation", "no_bitstream"])
    reports_present = all(path is not None and path.exists() and path.stat().st_size > 0 for path in [timing_rpt, util_rpt, route_rpt, drc_rpt, methodology_rpt, control_rpt])
    stale_timing_constraints = rule_count(methodology_rules, "TIMING-24") + rule_count(methodology_rules, "TIMING-28")
    ulmtcs_count = rule_count(methodology_rules, "ULMTCS-2")
    control_set_ready = int(candidate_total > 0 and candidate_total <= guideline_limit and remaining_over_guideline == 0 and ulmtcs_count == 0)
    control_set_status_note = (
        "Candidate clears the release control-set guideline and the DCP methodology report no longer reports ULMTCS-2."
        if control_set_ready
        else "Candidate still needs more reset/enable reduction or a formal waiver."
    )

    checks = [
        CheckRow("hard_constraint_unchanged", "PASS" if sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL", EXPECTED_CONSTRAINT_SHA256, sha256(constraint), "This analysis does not modify the hard target constraint."),
        CheckRow("reports_present", "PASS" if reports_present else "FAIL", "DCP-derived timing/util/route/DRC/methodology/control-set reports", rel(out_dir), "Reports are generated from an existing checkpoint only."),
        CheckRow("profile_is_release_external_8lane", "PASS" if "external_reduced_8lane_frag16" in rel(dcp) else "WARN", "external reduced 8-lane fragment=16 routed checkpoint", rel(dcp), "This candidate maps to the raw 32/16 Mbit/s target envelope but is still offline-only."),
        CheckRow("timing_and_route_clean", "PASS" if timing_clean and route_clean else "FAIL", "timing met and route_errors=0", f"WNS={timing.get('wns_ns')} WHS={timing.get('whs_ns')} route_errors={route.get('routing_errors')}", "Timing/route remain clean for this checkpoint."),
        CheckRow("control_set_improved_vs_active", "PASS" if reduction_vs_active > 0 else "FAIL", "candidate control sets lower than active debug/loopback build", f"active={active_total} candidate={candidate_total} reduction={reduction_vs_active}", "External release personality reduces control sets versus the active debug/loopback build."),
        CheckRow("debug_and_loopback_removed", "PASS" if debug_sets == 0 and loopback_sets == 0 else "FAIL", "debug_hub/debug_ila and loopback partner categories absent in candidate control-set rows", f"debug_sets={debug_sets} loopback_sets={loopback_sets}", "This proves the candidate removed the largest release-separable categories from the active build."),
        CheckRow(
            "ulmtcs_control_set_status",
            "PASS" if ((control_set_ready == 1) or (ulmtcs_count == 1 and remaining_over_guideline > 0)) else "FAIL",
            "ULMTCS-2 either cleared by the release DCP or explicitly remains a release blocker",
            f"ULMTCS-2={ulmtcs_count} candidate={candidate_total} guideline={guideline_limit} remaining={remaining_over_guideline}",
            control_set_status_note,
        ),
        CheckRow(
            "timing_24_28_cleared_in_current_dcp",
            "PASS" if stale_timing_constraints == 0 else "WARN",
            "TIMING-24/TIMING-28 absent in the current release-personality DCP methodology report",
            f"TIMING-24/28={stale_timing_constraints}",
            (
                "The release-personality candidate has been regenerated after the XDC fix; stale timing-override warnings are cleared."
                if stale_timing_constraints == 0
                else "This DCP still carries stale timing-override warnings and must be regenerated under the current XDC before release."
            ),
        ),
        CheckRow("no_hardware_side_effects", "PASS" if no_hw and no_build and not read_text(stderr_log).strip() else "FAIL", "no hardware, UART, TFDU, synth, implementation, or bitstream", f"no_hw={int(no_hw)} no_build={int(no_build)} stderr_empty={int(not read_text(stderr_log).strip())}", "This was a DCP report-only run."),
    ]
    row_failures = sum(1 for row in checks if row.status == "FAIL")
    metadata = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "overall": (
            "PASS_RELEASE_PERSONALITY_DCP_EVIDENCE_CONTROL_SET_CLEARED_RELEASE_STILL_BLOCKED"
            if row_failures == 0 and control_set_ready
            else "PASS_RELEASE_PERSONALITY_DCP_EVIDENCE_RELEASE_STILL_BLOCKED"
            if row_failures == 0
            else "FAIL_RELEASE_PERSONALITY_DCP_EVIDENCE"
        ),
        "release_ready": 0,
        "control_set_ready": control_set_ready,
        "debug_can_continue": int(row_failures == 0),
        "row_failures": row_failures,
        "constraint_sha256": sha256(constraint),
        "meta": rel(meta_file),
        "out_dir": rel(out_dir),
        "dcp": rel(dcp),
        "vivado_log": rel(vivado_log),
        "active_control_sets": active_total,
        "candidate_control_sets": candidate_total,
        "control_set_reduction_vs_active": reduction_vs_active,
        "guideline_limit": guideline_limit,
        "remaining_over_guideline": remaining_over_guideline,
        "debug_control_sets": debug_sets,
        "loopback_partner_control_sets": loopback_sets,
        "timing_wns_ns": timing.get("wns_ns"),
        "timing_whs_ns": timing.get("whs_ns"),
        "route_errors": route.get("routing_errors"),
        "methodology_rules": methodology_rules,
        "timing_24_28_count": stale_timing_constraints,
        "drc_rules": drc.get("rules", []),
        "no_hardware_programming": 1,
        "no_uart_write": 1,
        "no_tfdu_drive": 1,
        "no_synthesis": 1,
        "no_implementation": 1,
        "no_bitstream": 1,
    }
    return checks, categories, metadata


def write_reports(checks: list[CheckRow], categories: list[dict[str, Any]], metadata: dict[str, Any]) -> tuple[Path, Path, Path]:
    md_path = REPORTS / "release_personality_dcp_evidence_current.md"
    json_path = REPORTS / "release_personality_dcp_evidence_current.json"
    csv_path = REPORTS / "release_personality_dcp_evidence_current.csv"
    md = "\n".join(
        [
            "# Release Personality DCP Evidence",
            "",
            f"Generated: {metadata['generated']}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{metadata['overall']}`",
            "- Release ready: `0`",
            f"- Active control sets: `{metadata['active_control_sets']}`",
            f"- Candidate control sets: `{metadata['candidate_control_sets']}`",
            f"- Reduction vs active: `{metadata['control_set_reduction_vs_active']}`",
            f"- Guideline limit: `{metadata['guideline_limit']}`",
            f"- Remaining over guideline: `{metadata['remaining_over_guideline']}`",
            f"- Debug control sets in candidate: `{metadata['debug_control_sets']}`",
            f"- Loopback-partner control sets in candidate: `{metadata['loopback_partner_control_sets']}`",
            f"- Timing: `WNS={metadata['timing_wns_ns']} ns`, `WHS={metadata['timing_whs_ns']} ns`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "- No synthesis/implementation/bitstream in this run: `1`",
            "",
            "This is internal engineering evidence from an existing external 8-lane routed checkpoint. It is not a consulting bundle and does not clear release blockers.",
            "",
            "## Checks",
            "",
            table(
                ["check", "status", "expected", "actual", "note"],
                [[row.check, row.status, row.expected, row.actual, row.note] for row in checks],
            ),
            "",
            "## Control-Set Categories",
            "",
            table(
                ["category", "control_sets", "slice_load", "bel_load", "has_enable", "has_set_reset", "enable_and_reset"],
                [
                    [
                        row.get("category"),
                        row.get("control_sets"),
                        row.get("slice_load"),
                        row.get("bel_load"),
                        row.get("has_enable"),
                        row.get("has_set_reset"),
                        row.get("has_enable_and_set_reset"),
                    ]
                    for row in categories
                ],
            ),
            "",
            "```text",
            f"RF_COMM_RELEASE_PERSONALITY_DCP_EVIDENCE overall={metadata['overall']} release_ready={metadata['release_ready']} active_control_sets={metadata['active_control_sets']} candidate_control_sets={metadata['candidate_control_sets']} reduction={metadata['control_set_reduction_vs_active']} remaining_over_guideline={metadata['remaining_over_guideline']} row_failures={metadata['row_failures']}",
            "NO_HARDWARE_PROGRAMMING=1",
            "NO_UART_WRITE=1",
            "NO_TFDU_DRIVE=1",
            "NO_SYNTHESIS=1",
            "NO_IMPLEMENTATION=1",
            "NO_BITSTREAM=1",
            "```",
            "",
        ]
    )
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps({"metadata": metadata, "checks": [asdict(row) for row in checks], "categories": categories}, indent=2, ensure_ascii=False), encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["check", "status", "expected", "actual", "note"])
        writer.writeheader()
        for row in checks:
            writer.writerow(asdict(row))
    return md_path, json_path, csv_path


def main() -> int:
    checks, categories, metadata = build_report()
    md_path, json_path, csv_path = write_reports(checks, categories, metadata)
    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_RELEASE_PERSONALITY_DCP_EVIDENCE "
        f"overall={metadata['overall']} "
        f"release_ready={metadata['release_ready']} "
        f"active_control_sets={metadata['active_control_sets']} "
        f"candidate_control_sets={metadata['candidate_control_sets']} "
        f"reduction={metadata['control_set_reduction_vs_active']} "
        f"remaining_over_guideline={metadata['remaining_over_guideline']} "
        f"row_failures={metadata['row_failures']}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_SYNTHESIS=1")
    print("NO_IMPLEMENTATION=1")
    print("NO_BITSTREAM=1")
    return 0 if metadata["row_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
