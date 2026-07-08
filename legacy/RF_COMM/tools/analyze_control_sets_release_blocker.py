from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

CONTROL_RPT = REPORTS / "active_2lane_route_methodology_20260627_202314" / "control_sets_post_route.rpt"
METHODOLOGY_RPT = REPORTS / "active_2lane_route_methodology_20260627_202314" / "methodology_post_route.rpt"
UTIL_RPT = REPORTS / "active_2lane_route_methodology_20260627_202314" / "utilization_post_route.rpt"


@dataclass(frozen=True)
class CheckRow:
    check: str
    status: str
    expected: str
    actual: str
    note: str


@dataclass(frozen=True)
class CategoryRow:
    category: str
    control_sets: int
    slice_load: int
    bel_load: int
    has_enable: int
    has_set_reset: int
    has_enable_and_set_reset: int
    single_bel_sets: int
    note: str


@dataclass(frozen=True)
class ClockRow:
    clock: str
    control_sets: int
    slice_load: int
    bel_load: int


@dataclass(frozen=True)
class ControlSetRow:
    clock: str
    enable: str
    set_reset: str
    slice_load: int
    bel_load: int
    bels_per_slice: float
    category: str


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


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def extract_int(pattern: str, text: str) -> int | None:
    match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def categorize(*signals: str) -> str:
    blob = " ".join(signal for signal in signals if signal)
    if "ila_2lane_phy" in blob:
        return "debug_ila"
    if "dbg_hub/" in blob:
        return "debug_hub"
    if "ir_array_top_axi_0" in blob:
        return "user_ir_array_axi"
    if "ir_loopback_b0" in blob:
        return "user_ir_loopback_partner"
    if "axi_dma_0" in blob:
        return "axi_dma"
    if "axi_mem_intercon" in blob or "ps7_0_axi_periph" in blob:
        return "axi_interconnect"
    if "axis_data_fifo_0" in blob or "axis_dwidth_converter" in blob:
        return "axis_infrastructure"
    if "proc_sys_reset" in blob or "rst_ps7" in blob:
        return "reset_ip"
    if "clk_wiz_0" in blob:
        return "clock_wizard_or_pl_clock"
    if "processing_system7_0" in blob:
        return "processing_system_clock_domain"
    return "other_or_generated"


def parse_control_rows(text: str) -> list[ControlSetRow]:
    rows: list[ControlSetRow] = []
    for line in text.splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.split("|")[1:-1]]
        if len(cells) != 6:
            continue
        try:
            slice_load = int(cells[3])
            bel_load = int(cells[4])
            bels_per_slice = float(cells[5])
        except ValueError:
            continue
        clock, enable, set_reset = cells[0], cells[1], cells[2]
        rows.append(
            ControlSetRow(
                clock=clock,
                enable=enable,
                set_reset=set_reset,
                slice_load=slice_load,
                bel_load=bel_load,
                bels_per_slice=bels_per_slice,
                category=categorize(clock, enable, set_reset),
            )
        )
    return rows


def build_category_rows(rows: list[ControlSetRow]) -> list[CategoryRow]:
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = buckets.setdefault(
            row.category,
            {
                "control_sets": 0,
                "slice_load": 0,
                "bel_load": 0,
                "has_enable": 0,
                "has_set_reset": 0,
                "has_enable_and_set_reset": 0,
                "single_bel_sets": 0,
            },
        )
        bucket["control_sets"] += 1
        bucket["slice_load"] += row.slice_load
        bucket["bel_load"] += row.bel_load
        bucket["has_enable"] += int(bool(row.enable))
        bucket["has_set_reset"] += int(bool(row.set_reset))
        bucket["has_enable_and_set_reset"] += int(bool(row.enable) and bool(row.set_reset))
        bucket["single_bel_sets"] += int(row.bel_load == 1)

    notes = {
        "debug_ila": "Release build should remove or sharply limit ILA probes.",
        "debug_hub": "Usually disappears when debug cores are removed for release.",
        "user_ir_array_axi": "Final IR datapath; optimize only with simulation coverage.",
        "user_ir_loopback_partner": "Board-internal loopback/test partner; likely separable from final two-AX7010 release personality.",
        "axi_dma": "Generated IP; prefer traffic proof/config review over RTL edits.",
        "axi_interconnect": "Generated AXI fabric; can shrink if unused test paths or debug paths are removed.",
        "axis_infrastructure": "Generated stream infrastructure.",
        "reset_ip": "Generated reset sequencing; avoid unnecessary extra reset domains.",
        "clock_wizard_or_pl_clock": "Mostly clock-domain context, not necessarily an optimization target by itself.",
        "processing_system_clock_domain": "Clock-domain-only rows without a clearer component owner.",
        "other_or_generated": "Generated or uncategorized logic; inspect only after larger categories are handled.",
    }
    result = [
        CategoryRow(
            category=category,
            control_sets=values["control_sets"],
            slice_load=values["slice_load"],
            bel_load=values["bel_load"],
            has_enable=values["has_enable"],
            has_set_reset=values["has_set_reset"],
            has_enable_and_set_reset=values["has_enable_and_set_reset"],
            single_bel_sets=values["single_bel_sets"],
            note=notes.get(category, ""),
        )
        for category, values in buckets.items()
    ]
    return sorted(result, key=lambda row: (row.control_sets, row.bel_load), reverse=True)


def build_clock_rows(rows: list[ControlSetRow]) -> list[ClockRow]:
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = buckets.setdefault(row.clock or "<blank>", {"control_sets": 0, "slice_load": 0, "bel_load": 0})
        bucket["control_sets"] += 1
        bucket["slice_load"] += row.slice_load
        bucket["bel_load"] += row.bel_load
    result = [
        ClockRow(clock=clock, control_sets=values["control_sets"], slice_load=values["slice_load"], bel_load=values["bel_load"])
        for clock, values in buckets.items()
    ]
    return sorted(result, key=lambda row: (row.control_sets, row.bel_load), reverse=True)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def build_report() -> tuple[list[CheckRow], list[CategoryRow], list[ClockRow], list[ControlSetRow], dict[str, Any]]:
    constraint = find_hard_constraint()
    control_text = read_text(CONTROL_RPT)
    methodology_text = read_text(METHODOLOGY_RPT)
    util_text = read_text(UTIL_RPT)
    detailed_rows = parse_control_rows(control_text)
    categories = build_category_rows(detailed_rows)
    clocks = build_clock_rows(detailed_rows)

    total_control_sets = extract_int(r"Total control sets\s*\|\s*(\d+)", control_text)
    minimum_control_sets = extract_int(r"Minimum number of control sets\s*\|\s*(\d+)", control_text)
    available_limit = extract_int(r"available limit of\s+(\d+)", methodology_text)
    if available_limit is None:
        available_limit = extract_int(r"Unique Control Sets\s*\|\s*\d+\s*\|[^\n|]*\|[^\n|]*\|\s*(\d+)\s*\|", util_text)
    guideline_limit = int((available_limit or 0) * 0.15) if available_limit else None
    reduction_to_guideline = (
        max(0, (total_control_sets or 0) - guideline_limit) if guideline_limit is not None else None
    )
    pct_of_available = ((total_control_sets or 0) / available_limit * 100.0) if available_limit else None
    top_debug_sets = sum(row.control_sets for row in categories if row.category in {"debug_ila", "debug_hub"})
    top_user_test_sets = sum(row.control_sets for row in categories if row.category == "user_ir_loopback_partner")

    checks = [
        CheckRow(
            "hard_constraint_unchanged",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            EXPECTED_CONSTRAINT_SHA256,
            sha256(constraint),
            "This analysis does not modify the hard target constraint.",
        ),
        CheckRow(
            "control_set_report_present",
            "PASS" if CONTROL_RPT.exists() and total_control_sets == 1053 else "FAIL",
            "active route control_sets_post_route.rpt with total=1053",
            f"{rel(CONTROL_RPT)} total={total_control_sets}",
            "Uses the route-only active 2-lane evidence already archived under reports/.",
        ),
        CheckRow(
            "detailed_rows_parse",
            "PASS" if total_control_sets == len(detailed_rows) else "FAIL",
            "detailed row count equals total control sets",
            f"rows={len(detailed_rows)} total={total_control_sets}",
            "Each detailed row is one unique control set.",
        ),
        CheckRow(
            "ulmtcs_release_blocker_quantified",
            "PASS" if guideline_limit is not None and reduction_to_guideline is not None and reduction_to_guideline > 0 else "FAIL",
            "current control sets exceed 15 percent guideline",
            f"current={total_control_sets} guideline_limit={guideline_limit} reduction_needed={reduction_to_guideline}",
            "This confirms ULMTCS-2 remains a release/expansion blocker.",
        ),
        CheckRow(
            "actionable_categories_identified",
            "PASS" if len(categories) >= 6 and top_debug_sets > 0 and top_user_test_sets > 0 else "FAIL",
            "debug and test/release-separable categories identified",
            f"categories={len(categories)} debug_sets={top_debug_sets} loopback_partner_sets={top_user_test_sets}",
            "Largest safe first move is to separate release from debug/board-internal loopback personality before hand-optimizing RTL.",
        ),
        CheckRow(
            "no_hardware_side_effects",
            "PASS",
            "no FPGA programming, UART write, TFDU drive, Vivado run, or bitstream generation",
            "read-only report parsing",
            "This script reads existing reports and writes reports/control_sets_release_blocker_current.*.",
        ),
    ]
    row_failures = sum(1 for row in checks if row.status != "PASS")
    metadata = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "overall": "PASS_CONTROL_SET_BLOCKER_EVIDENCE_RELEASE_STILL_BLOCKED" if row_failures == 0 else "FAIL_CONTROL_SET_BLOCKER_EVIDENCE",
        "release_ready": 0,
        "expansion_ready": 0,
        "debug_can_continue": int(row_failures == 0),
        "row_failures": row_failures,
        "constraint_sha256": sha256(constraint),
        "control_report": rel(CONTROL_RPT),
        "methodology_report": rel(METHODOLOGY_RPT),
        "utilization_report": rel(UTIL_RPT),
        "total_control_sets": total_control_sets,
        "minimum_control_sets": minimum_control_sets,
        "available_limit": available_limit,
        "guideline_percent": 15,
        "guideline_limit": guideline_limit,
        "control_sets_over_guideline": reduction_to_guideline,
        "pct_of_available": pct_of_available,
        "category_count": len(categories),
        "clock_count": len(clocks),
        "debug_control_sets": top_debug_sets,
        "loopback_partner_control_sets": top_user_test_sets,
        "no_hardware_programming": 1,
        "no_uart_write": 1,
        "no_tfdu_drive": 1,
        "no_vivado_run": 1,
    }
    return checks, categories, clocks, detailed_rows, metadata


def write_reports(
    checks: list[CheckRow],
    categories: list[CategoryRow],
    clocks: list[ClockRow],
    details: list[ControlSetRow],
    metadata: dict[str, Any],
) -> tuple[Path, Path, Path]:
    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "control_sets_release_blocker_current.md"
    json_path = REPORTS / "control_sets_release_blocker_current.json"
    csv_path = REPORTS / "control_sets_release_blocker_current.csv"

    top_details = sorted(details, key=lambda row: (row.bel_load, row.slice_load), reverse=True)[:20]
    md = "\n".join(
        [
            "# Control Sets Release Blocker Evidence",
            "",
            f"Generated: {metadata['generated']}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{metadata['overall']}`",
            "- Release ready: `0`",
            "- Expansion ready: `0`",
            f"- Debug can continue: `{metadata['debug_can_continue']}`",
            f"- Total control sets: `{metadata['total_control_sets']}`",
            f"- 15 percent guideline limit: `{metadata['guideline_limit']}`",
            f"- Reduction needed to meet guideline: `{metadata['control_sets_over_guideline']}`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "- No Vivado run: `1`",
            "",
            "This is internal engineering evidence for ULMTCS-2. It does not clear the release blocker and it is not a consulting bundle.",
            "",
            "## Checks",
            "",
            table(
                ["check", "status", "expected", "actual", "note"],
                [[row.check, row.status, row.expected, row.actual, row.note] for row in checks],
            ),
            "",
            "## Category Summary",
            "",
            table(
                [
                    "category",
                    "control_sets",
                    "slice_load",
                    "bel_load",
                    "has_enable",
                    "has_set_reset",
                    "enable_and_reset",
                    "single_bel_sets",
                    "note",
                ],
                [
                    [
                        row.category,
                        row.control_sets,
                        row.slice_load,
                        row.bel_load,
                        row.has_enable,
                        row.has_set_reset,
                        row.has_enable_and_set_reset,
                        row.single_bel_sets,
                        row.note,
                    ]
                    for row in categories
                ],
            ),
            "",
            "## Clock Summary",
            "",
            table(
                ["clock", "control_sets", "slice_load", "bel_load"],
                [[row.clock, row.control_sets, row.slice_load, row.bel_load] for row in clocks],
            ),
            "",
            "## Top High-Load Control Sets",
            "",
            table(
                ["category", "clock", "slice_load", "bel_load", "enable", "set_reset"],
                [
                    [
                        row.category,
                        row.clock,
                        row.slice_load,
                        row.bel_load,
                        row.enable,
                        row.set_reset,
                    ]
                    for row in top_details
                ],
            ),
            "",
            "```text",
            f"RF_COMM_CONTROL_SETS_RELEASE_BLOCKER overall={metadata['overall']} release_ready={metadata['release_ready']} expansion_ready={metadata['expansion_ready']} total={metadata['total_control_sets']} guideline={metadata['guideline_limit']} reduction_needed={metadata['control_sets_over_guideline']} row_failures={metadata['row_failures']}",
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
        json.dumps(
            {
                "metadata": metadata,
                "checks": [asdict(row) for row in checks],
                "categories": [asdict(row) for row in categories],
                "clocks": [asdict(row) for row in clocks],
                "top_details": [asdict(row) for row in top_details],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(categories[0]).keys()))
        writer.writeheader()
        for row in categories:
            writer.writerow(asdict(row))
    return md_path, json_path, csv_path


def main() -> int:
    checks, categories, clocks, details, metadata = build_report()
    md_path, json_path, csv_path = write_reports(checks, categories, clocks, details, metadata)
    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_CONTROL_SETS_RELEASE_BLOCKER "
        f"overall={metadata['overall']} "
        f"release_ready={metadata['release_ready']} "
        f"expansion_ready={metadata['expansion_ready']} "
        f"total={metadata['total_control_sets']} "
        f"guideline={metadata['guideline_limit']} "
        f"reduction_needed={metadata['control_sets_over_guideline']} "
        f"row_failures={metadata['row_failures']}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_VIVADO_RUN=1")
    return 0 if metadata["row_failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
