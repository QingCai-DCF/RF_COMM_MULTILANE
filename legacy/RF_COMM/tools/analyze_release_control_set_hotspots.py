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

LEGACY_RELEASE_REPORT_DIR = REPORTS / "release_personality_dcp_report_20260627_205832"
RELEASE_EVIDENCE_JSON = REPORTS / "release_personality_dcp_evidence_current.json"


@dataclass(frozen=True)
class ControlSetRow:
    clock: str
    enable: str
    set_reset: str
    slice_load: int
    bel_load: int
    bels_per_slice: float


@dataclass(frozen=True)
class BucketRow:
    bucket: str
    control_sets: int
    slice_load: int
    bel_load: int
    has_enable: int
    has_set_reset: int
    enable_and_reset: int


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


def latest_release_report_dir() -> Path:
    candidates = [
        path
        for path in REPORTS.glob("release_personality_dcp_report_*")
        if path.is_dir()
        and (path / "control_sets_post_route.rpt").exists()
        and (path / "methodology_post_route.rpt").exists()
    ]
    if not candidates:
        return LEGACY_RELEASE_REPORT_DIR
    return max(candidates, key=lambda path: (path / "control_sets_post_route.rpt").stat().st_mtime)


def release_report_paths() -> tuple[Path, Path]:
    report_dir = latest_release_report_dir()
    return report_dir / "control_sets_post_route.rpt", report_dir / "methodology_post_route.rpt"


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


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
        rows.append(
            ControlSetRow(
                clock=cells[0],
                enable=cells[1],
                set_reset=cells[2],
                slice_load=slice_load,
                bel_load=bel_load,
                bels_per_slice=bels_per_slice,
            )
        )
    return rows


def extract_total(text: str) -> int:
    match = re.search(r"Total control sets\s*\|\s*(\d+)", text)
    return int(match.group(1)) if match else 0


def extract_guideline(methodology_text: str) -> tuple[int, int]:
    match = re.search(r"uses\s+(\d+)\s+control sets.*?guideline of 15 percent", methodology_text, re.I | re.S)
    if not match:
        return 0, 660
    total = int(match.group(1))
    return total, 660


def classify_component(row: ControlSetRow) -> str:
    blob = f"{row.clock} {row.enable} {row.set_reset}"
    patterns = [
        ("user_ir_tx_lane_phy", "/u_tx/"),
        ("user_ir_rx_lane_phy", "/u_rx/"),
        ("user_ir_lane_sink", "/u_sink/"),
        ("user_ir_tx_mgr", "/u_tx_mgr/"),
        ("user_ir_rx_mgr", "/u_rx_mgr/"),
        ("user_ir_tx_async_fifo", "/u_tx_async_fifo/"),
        ("user_ir_rx_async_fifo", "/u_rx_async_fifo/"),
        ("user_ir_top_scheduler", "/u_top/"),
        ("user_ir_axi_regs", "/u_regs/"),
        ("user_ir_array_axi_other", "ir_array_top_axi_0"),
        ("axi_dma", "axi_dma_0"),
        ("axi_interconnect", "axi_mem_intercon"),
        ("axi_interconnect", "ps7_0_axi_periph"),
        ("axis_infrastructure", "axis_data_fifo_0"),
        ("axis_infrastructure", "axis_dwidth_converter"),
        ("reset_ip", "proc_sys_reset"),
        ("reset_ip", "rst_ps7"),
        ("clock_wizard_or_pl_clock", "clk_wiz_0"),
        ("processing_system_clock_domain", "processing_system7_0"),
    ]
    for bucket, needle in patterns:
        if needle in blob:
            return bucket
    return "other_or_generated"


def lane_bucket(row: ControlSetRow) -> str:
    blob = f"{row.enable} {row.set_reset}"
    match = re.search(r"g_lane\[(\d+)\]", blob)
    if match:
        return f"lane_{match.group(1)}"
    if "/u_tx_mgr/" in blob:
        return "tx_mgr"
    if "/u_rx_mgr/" in blob:
        return "rx_mgr"
    if "ir_array_top_axi_0" in blob:
        return "ir_shared_or_axi"
    return "not_user_ir"


def signal_family(signal: str) -> str:
    if not signal:
        return "<none>"
    for marker in [
        "/u_tx/",
        "/u_rx/",
        "/u_sink/",
        "/u_tx_mgr/",
        "/u_rx_mgr/",
        "/u_tx_async_fifo/",
        "/u_rx_async_fifo/",
    ]:
        if marker in signal:
            tail = signal.split(marker, 1)[1]
            return marker.strip("/") + "/" + tail.split("/", 1)[0].split("[", 1)[0]
    tail = signal.rsplit("/", 1)[-1]
    return tail.split("[", 1)[0].split("_i_", 1)[0]


def build_buckets(rows: list[ControlSetRow], key_fn) -> list[BucketRow]:
    buckets: dict[str, dict[str, int]] = {}
    for row in rows:
        key = key_fn(row)
        data = buckets.setdefault(
            key,
            {
                "control_sets": 0,
                "slice_load": 0,
                "bel_load": 0,
                "has_enable": 0,
                "has_set_reset": 0,
                "enable_and_reset": 0,
            },
        )
        data["control_sets"] += 1
        data["slice_load"] += row.slice_load
        data["bel_load"] += row.bel_load
        data["has_enable"] += int(bool(row.enable))
        data["has_set_reset"] += int(bool(row.set_reset))
        data["enable_and_reset"] += int(bool(row.enable) and bool(row.set_reset))
    out = [
        BucketRow(
            bucket=key,
            control_sets=value["control_sets"],
            slice_load=value["slice_load"],
            bel_load=value["bel_load"],
            has_enable=value["has_enable"],
            has_set_reset=value["has_set_reset"],
            enable_and_reset=value["enable_and_reset"],
        )
        for key, value in buckets.items()
    ]
    return sorted(out, key=lambda row: (row.control_sets, row.bel_load), reverse=True)


def table(headers: list[str], rows: list[list[Any]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("|", "/").replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    constraint = find_hard_constraint()
    control_rpt, methodology_rpt = release_report_paths()
    control_text = read_text(control_rpt)
    methodology_text = read_text(methodology_rpt)
    release_meta = read_json(RELEASE_EVIDENCE_JSON).get("metadata", {})
    rows = parse_control_rows(control_text)
    total = extract_total(control_text)
    methodology_total, guideline = extract_guideline(methodology_text)
    component_rows = build_buckets(rows, classify_component)
    lane_rows = build_buckets(rows, lane_bucket)
    enable_rows = build_buckets(rows, lambda row: signal_family(row.enable))
    reset_rows = build_buckets(rows, lambda row: signal_family(row.set_reset))

    user_ir_rows = [row for row in rows if classify_component(row).startswith("user_ir")]
    user_ir_enable_reset = sum(1 for row in user_ir_rows if row.enable and row.set_reset)
    lane_control_sets = sum(row.control_sets for row in lane_rows if row.bucket.startswith("lane_"))
    manager_control_sets = sum(row.control_sets for row in lane_rows if row.bucket in {"tx_mgr", "rx_mgr"})
    control_set_ready = int(total > 0 and guideline > 0 and total <= guideline)
    hotspot_context_ok = bool(
        control_set_ready
        or (
            lane_control_sets > 0
            and manager_control_sets > 0
            and user_ir_enable_reset > 0
        )
    )

    checks = [
        CheckRow(
            "hard_constraint_unchanged",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            EXPECTED_CONSTRAINT_SHA256,
            sha256(constraint),
            "This hotspot analysis does not modify the hard target constraint.",
        ),
        CheckRow(
            "release_control_report_present",
            "PASS" if control_rpt.exists() and total > 0 and len(rows) == total else "FAIL",
            "latest release-personality control report has detail rows matching its total",
            f"{rel(control_rpt)} total={total} rows={len(rows)}",
            "Uses the latest regenerated 8-lane fragment=16 release-personality DCP report.",
        ),
        CheckRow(
            "timing_24_28_already_cleared",
            "PASS" if int(release_meta.get("timing_24_28_count", -1)) == 0 else "FAIL",
            "TIMING-24/TIMING-28 count is zero in current release DCP evidence",
            f"timing_24_28_count={release_meta.get('timing_24_28_count', 'MISSING')}",
            "The remaining focus is ULMTCS-2, not stale timing exception overrides.",
        ),
        CheckRow(
            "ulmtcs_gap_quantified",
            "PASS" if total > 0 and guideline == 660 and methodology_total in {0, total} else "FAIL",
            "latest total control-set count is parsed against the 660 guideline",
            f"control_report_total={total} methodology_total={methodology_total} guideline={guideline}",
            "If total is above guideline, release still needs fewer control sets or a formal waiver.",
        ),
        CheckRow(
            "user_ir_hotspots_identified",
            "PASS" if hotspot_context_ok else "FAIL",
            "lane PHY plus TX/RX managers are identified when control sets remain above guideline",
            f"lane_sets={lane_control_sets} manager_sets={manager_control_sets} user_ir_enable_reset={user_ir_enable_reset}",
            "The next aligned optimization should target state-machine enable/reset mapping or synthesis control-set remapping.",
        ),
        CheckRow(
            "no_hardware_side_effects",
            "PASS",
            "no FPGA programming, UART write, TFDU drive, Vivado run, or bitstream generation",
            "read-only report parsing",
            "This script only reads reports and writes hotspot evidence.",
        ),
    ]
    row_failures = sum(1 for row in checks if row.status != "PASS")
    if row_failures:
        overall = "FAIL_RELEASE_CONTROL_SET_HOTSPOTS"
    elif control_set_ready:
        overall = "PASS_RELEASE_CONTROL_SET_HOTSPOTS_CONTROL_SET_CLEARED"
    else:
        overall = "PASS_RELEASE_CONTROL_SET_HOTSPOTS_RELEASE_STILL_BLOCKED"

    metadata = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "release_ready": 0,
        "control_set_ready": control_set_ready,
        "row_failures": row_failures,
        "constraint_sha256": sha256(constraint),
        "control_report": rel(control_rpt),
        "methodology_report": rel(methodology_rpt),
        "total_control_sets": total,
        "guideline_limit": guideline,
        "remaining_over_guideline": max(0, total - guideline),
        "lane_control_sets": lane_control_sets,
        "manager_control_sets": manager_control_sets,
        "user_ir_enable_and_reset_sets": user_ir_enable_reset,
        "no_hardware_programming": 1,
        "no_uart_write": 1,
        "no_tfdu_drive": 1,
        "no_vivado_run": 1,
    }

    md_path = REPORTS / "release_control_set_hotspots_current.md"
    json_path = REPORTS / "release_control_set_hotspots_current.json"
    csv_path = REPORTS / "release_control_set_hotspots_current.csv"

    md = "\n".join(
        [
            "# Release Control-Set Hotspots",
            "",
            f"Generated: {metadata['generated']}",
            "",
            "## Verdict",
            "",
            f"- Overall: `{overall}`",
            "- Release ready: `0`",
            f"- Control-set ready: `{control_set_ready}`",
            f"- Total control sets: `{total}`",
            f"- Guideline limit: `{guideline}`",
            f"- Remaining over guideline: `{metadata['remaining_over_guideline']}`",
            f"- Lane-local control sets: `{lane_control_sets}`",
            f"- TX/RX manager control sets: `{manager_control_sets}`",
            f"- User IR control sets with both enable and reset: `{user_ir_enable_reset}`",
            "- No hardware programming: `1`",
            "- No UART write: `1`",
            "- No TFDU drive: `1`",
            "- No Vivado run: `1`",
            "",
            "This is internal engineering evidence for the ULMTCS-2 release blocker. It is not a consulting bundle and does not clear release.",
            "",
            "## Checks",
            "",
            table(["check", "status", "expected", "actual", "note"], [[row.check, row.status, row.expected, row.actual, row.note] for row in checks]),
            "",
            "## Component Buckets",
            "",
            table(["bucket", "control_sets", "slice_load", "bel_load", "has_enable", "has_set_reset", "enable_and_reset"], [[row.bucket, row.control_sets, row.slice_load, row.bel_load, row.has_enable, row.has_set_reset, row.enable_and_reset] for row in component_rows]),
            "",
            "## User IR Lane/Manager Buckets",
            "",
            table(["bucket", "control_sets", "slice_load", "bel_load", "has_enable", "has_set_reset", "enable_and_reset"], [[row.bucket, row.control_sets, row.slice_load, row.bel_load, row.has_enable, row.has_set_reset, row.enable_and_reset] for row in lane_rows if row.bucket != "not_user_ir"]),
            "",
            "## Top Enable Families",
            "",
            table(["bucket", "control_sets", "slice_load", "bel_load", "has_set_reset"], [[row.bucket, row.control_sets, row.slice_load, row.bel_load, row.has_set_reset] for row in enable_rows[:20]]),
            "",
            "## Top Reset Families",
            "",
            table(["bucket", "control_sets", "slice_load", "bel_load", "has_enable"], [[row.bucket, row.control_sets, row.slice_load, row.bel_load, row.has_enable] for row in reset_rows[:20]]),
            "",
            "```text",
            f"RF_COMM_RELEASE_CONTROL_SET_HOTSPOTS overall={overall} release_ready=0 control_set_ready={control_set_ready} total={total} guideline={guideline} remaining={metadata['remaining_over_guideline']} lane_sets={lane_control_sets} manager_sets={manager_control_sets} row_failures={row_failures}",
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
                "component_buckets": [asdict(row) for row in component_rows],
                "lane_buckets": [asdict(row) for row in lane_rows],
                "enable_families": [asdict(row) for row in enable_rows],
                "reset_families": [asdict(row) for row in reset_rows],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(component_rows[0]).keys()))
        writer.writeheader()
        for row in component_rows:
            writer.writerow(asdict(row))

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_RELEASE_CONTROL_SET_HOTSPOTS "
        f"overall={overall} release_ready=0 control_set_ready={control_set_ready} total={total} guideline={guideline} "
        f"remaining={metadata['remaining_over_guideline']} lane_sets={lane_control_sets} "
        f"manager_sets={manager_control_sets} row_failures={row_failures}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print("NO_VIVADO_RUN=1")
    return 0 if row_failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
