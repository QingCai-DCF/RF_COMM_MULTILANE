#!/usr/bin/env python3
"""Generate a DRC/methodology triage report for the current RF_COMM build."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1"
REPORTS = ROOT / "reports"


@dataclass
class RuleSummary:
    source: str
    rule: str
    severity: str
    description: str
    violations: int
    disposition: str
    rationale: str


@dataclass
class BuildSummary:
    timing_wns_ns: float | None
    timing_tns_ns: float | None
    timing_whs_ns: float | None
    timing_ths_ns: float | None
    route_errors: int | None
    lut_percent: float | None
    register_percent: float | None
    bram_percent: float | None
    dsp_percent: float | None
    iob_percent: float | None


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def latest_active_route_dir() -> Path | None:
    candidates = [
        path
        for path in REPORTS.glob("active_2lane_route_methodology_*")
        if path.is_dir() and (path / "methodology_post_route.rpt").exists()
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def prefer_latest(active_dir: Path | None, active_name: str, impl_name: str) -> Path:
    if active_dir is not None:
        active_path = active_dir / active_name
        if active_path.exists():
            return active_path
    return IMPL / impl_name


def parse_rule_table(text: str, source: str) -> list[RuleSummary]:
    rules: list[RuleSummary] = []
    pattern = re.compile(r"^\|\s*([A-Z0-9-]+)\s*\|\s*([A-Za-z]+)\s*\|\s*(.*?)\s*\|\s*(\d+)\s*\|$", re.MULTILINE)
    seen: set[tuple[str, str]] = set()
    for match in pattern.finditer(text):
        rule, severity, description, count_raw = match.groups()
        if rule == "Rule":
            continue
        key = (source, rule)
        if key in seen:
            continue
        seen.add(key)
        disposition, rationale = classify_rule(source, rule, severity, description)
        rules.append(
            RuleSummary(
                source=source,
                rule=rule,
                severity=severity,
                description=" ".join(description.split()),
                violations=int(count_raw),
                disposition=disposition,
                rationale=rationale,
            )
        )
    return rules


def classify_rule(source: str, rule: str, severity: str, description: str) -> tuple[str, str]:
    if severity.lower() in {"error", "critical"}:
        return "BLOCK_RELEASE", "Error or critical DRC must be fixed before any hardware release."
    if rule in {"PDCN-1569", "RTSTAT-10"}:
        return "WAIVER_CANDIDATE_DEBUG_OR_IP", "Observed in dbg_hub, generated FIFO, or interconnect paths; keep for debug builds, re-check release build without ILA."
    if rule == "REQP-181":
        return "REVIEW_DMA_FIFO_COLLISION", "Advisory on AXI DMA FIFO WRITE_FIRST BRAM; validate by DMA/PS traffic tests before release."
    if rule in {"LUTAR-1", "PDRC-190"}:
        return "WAIVER_CANDIDATE_DEBUG_OR_GENERATED_IP", "Primarily debug hub or generated FIFO synchronizer placement/reset methodology; acceptable for bring-up only after documented waiver."
    if rule in {"TIMING-24", "TIMING-28"}:
        return "FIX_CONSTRAINTS_BEFORE_RELEASE", "Clock constraint interaction should be replaced with point-to-point CDC exceptions or pin-based generated clock references."
    if rule == "ULMTCS-2":
        return "OPTIMIZE_BEFORE_4_OR_8_LANE", "Control-set usage is below device limit but above guideline; resolve before expansion/release build."
    return "REVIEW_REQUIRED", f"Unclassified {source} {rule}: {description}"


def parse_timing(text: str) -> tuple[float | None, float | None, float | None, float | None]:
    lines = text.splitlines()
    for idx, line in enumerate(lines):
        if "WNS(ns)" in line and "TNS(ns)" in line and "WHS(ns)" in line:
            for candidate in lines[idx + 1 : idx + 5]:
                nums = re.findall(r"-?\d+\.\d+|-?\d+", candidate)
                if len(nums) >= 6:
                    return float(nums[0]), float(nums[1]), float(nums[4]), float(nums[5])
    return None, None, None, None


def parse_route_errors(text: str) -> int | None:
    match = re.search(r"# of nets with routing errors\.+\s*:\s*(\d+)\s*:", text)
    return int(match.group(1)) if match else None


def parse_util_percent(text: str, label: str) -> float | None:
    pattern = re.compile(r"^\|\s*" + re.escape(label) + r"\s*\|.*?\|\s*([0-9]+\.[0-9]+)\s*\|$", re.MULTILINE)
    match = pattern.search(text)
    return float(match.group(1)) if match else None


def collect() -> tuple[list[RuleSummary], BuildSummary, dict[str, str]]:
    active_dir = latest_active_route_dir()
    drc_path = prefer_latest(active_dir, "drc_post_route.rpt", "design_shiboqi_wrapper_drc_routed.rpt")
    methodology_path = prefer_latest(
        active_dir,
        "methodology_post_route.rpt",
        "design_shiboqi_wrapper_methodology_drc_routed.rpt",
    )
    timing_path = prefer_latest(active_dir, "timing_summary_post_route.rpt", "timing_summary_post_route.rpt")
    route_path = prefer_latest(active_dir, "route_status_post_route.rpt", "route_status_post_route.rpt")
    util_path = prefer_latest(active_dir, "utilization_post_route.rpt", "utilization_post_route.rpt")

    drc_text = read_text(drc_path)
    methodology_text = read_text(methodology_path)
    timing_text = read_text(timing_path)
    route_text = read_text(route_path)
    util_text = read_text(util_path)

    rules = parse_rule_table(drc_text, "DRC") + parse_rule_table(methodology_text, "METHODOLOGY")
    wns, tns, whs, ths = parse_timing(timing_text)
    build = BuildSummary(
        timing_wns_ns=wns,
        timing_tns_ns=tns,
        timing_whs_ns=whs,
        timing_ths_ns=ths,
        route_errors=parse_route_errors(route_text),
        lut_percent=parse_util_percent(util_text, "Slice LUTs"),
        register_percent=parse_util_percent(util_text, "Slice Registers"),
        bram_percent=parse_util_percent(util_text, "Block RAM Tile"),
        dsp_percent=parse_util_percent(util_text, "DSPs"),
        iob_percent=parse_util_percent(util_text, "Bonded IOB"),
    )
    hashes = {
        rel(path): sha256(path) if path.exists() else "MISSING"
        for path in (drc_path, methodology_path, timing_path, route_path, util_path)
    }
    return rules, build, hashes


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if cell is None else str(cell) for cell in row) + " |")
    return "\n".join(out)


def render_markdown(rules: list[RuleSummary], build: BuildSummary, hashes: dict[str, str]) -> str:
    severity_counts: dict[str, int] = {}
    disposition_counts: dict[str, int] = {}
    for rule in rules:
        severity_counts[rule.severity] = severity_counts.get(rule.severity, 0) + rule.violations
        disposition_counts[rule.disposition] = disposition_counts.get(rule.disposition, 0) + rule.violations

    blocking = [
        rule
        for rule in rules
        if rule.disposition in {"BLOCK_RELEASE", "FIX_CONSTRAINTS_BEFORE_RELEASE", "OPTIMIZE_BEFORE_4_OR_8_LANE", "REVIEW_DMA_FIFO_COLLISION"}
    ]
    release_ready = not blocking

    parts = [
        "# RF_COMM DRC and Methodology Triage",
        "",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        "## Verdict",
        "",
        f"- Release/expansion DRC status: `{'READY' if release_ready else 'TRIAGED_NOT_RELEASE_READY'}`",
        "- This report is a triage record, not a formal Vivado waiver file.",
        "- No RTL, XDC, block design, bitstream, or project constraint file was modified by this audit.",
        "",
        "## Build Summary",
        "",
        md_table(
            ["metric", "value"],
            [
                ["route_errors", build.route_errors],
                ["WNS(ns)", build.timing_wns_ns],
                ["TNS(ns)", build.timing_tns_ns],
                ["WHS(ns)", build.timing_whs_ns],
                ["THS(ns)", build.timing_ths_ns],
                ["Slice LUT %", build.lut_percent],
                ["Slice Register %", build.register_percent],
                ["BRAM Tile %", build.bram_percent],
                ["DSP %", build.dsp_percent],
                ["Bonded IOB %", build.iob_percent],
            ],
        ),
        "",
        "## Severity Counts",
        "",
        md_table(["severity", "violations"], [[key, value] for key, value in sorted(severity_counts.items())]),
        "",
        "## Disposition Counts",
        "",
        md_table(["disposition", "violations"], [[key, value] for key, value in sorted(disposition_counts.items())]),
        "",
        "## Rule Triage",
        "",
        md_table(
            ["source", "rule", "severity", "violations", "disposition", "description", "rationale"],
            [
                [
                    rule.source,
                    rule.rule,
                    rule.severity,
                    rule.violations,
                    rule.disposition,
                    rule.description,
                    rule.rationale,
                ]
                for rule in rules
            ],
        ),
        "",
        "## Required Before 4/8-Lane Or Release",
        "",
    ]

    if blocking:
        parts.append(
            md_table(
                ["rule", "required_action"],
                [
                    [
                        rule.rule,
                        rule.rationale,
                    ]
                    for rule in blocking
                ],
            )
        )
    else:
        parts.append("No blocking or pre-release action remains in this triage.")

    parts.extend(
        [
            "",
            "## Source Hashes",
            "",
            md_table(["path", "sha256"], [[path, digest] for path, digest in hashes.items()]),
            "",
        ]
    )
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPORTS / "drc_triage_current_20260626.md")
    parser.add_argument("--json", type=Path, default=REPORTS / "drc_triage_current_20260626.json")
    args = parser.parse_args()

    rules, build, hashes = collect()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_markdown(rules, build, hashes), encoding="utf-8")
    print(f"WROTE_MARKDOWN={out}")

    if args.json:
        json_out = args.json if args.json.is_absolute() else ROOT / args.json
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(
            json.dumps(
                {
                    "rules": [asdict(rule) for rule in rules],
                    "build": asdict(build),
                    "hashes": hashes,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"WROTE_JSON={json_out}")

    warning_count = sum(rule.violations for rule in rules if rule.severity.lower() == "warning")
    advisory_count = sum(rule.violations for rule in rules if rule.severity.lower() == "advisory")
    blocking_count = sum(
        rule.violations
        for rule in rules
        if rule.disposition in {"BLOCK_RELEASE", "FIX_CONSTRAINTS_BEFORE_RELEASE", "OPTIMIZE_BEFORE_4_OR_8_LANE", "REVIEW_DMA_FIFO_COLLISION"}
    )
    print(
        "DRC_TRIAGE_SUMMARY "
        f"rules={len(rules)} warnings={warning_count} advisories={advisory_count} "
        f"blocking_or_prerelease_actions={blocking_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
