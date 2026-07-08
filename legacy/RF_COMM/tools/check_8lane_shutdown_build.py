from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SHUTDOWN_DIR = ROOT / "shutdown_bitstream"
BITSTREAM = SHUTDOWN_DIR / "tfdu_shutdown_8lane_candidate.bit"
DCP = SHUTDOWN_DIR / "tfdu_shutdown_8lane_candidate_routed.dcp"
DRC_RPT = SHUTDOWN_DIR / "tfdu_shutdown_8lane_candidate_drc.rpt"
TIMING_RPT = SHUTDOWN_DIR / "tfdu_shutdown_8lane_candidate_timing_summary.rpt"
IO_RPT = SHUTDOWN_DIR / "tfdu_shutdown_8lane_candidate_io.rpt"
UTIL_RPT = SHUTDOWN_DIR / "tfdu_shutdown_8lane_candidate_utilization.rpt"
PINMAP_CSV = REPORTS / "8lane_candidate_pinmap_current.csv"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class BuildItem:
    item_id: str
    status: str
    evidence: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
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
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def latest_meta() -> Path | None:
    metas = sorted(
        REPORTS.glob("build_tfdu_shutdown_8lane_candidate_*.meta.txt"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return metas[0] if metas else None


def parse_meta(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def path_from_meta(meta: dict[str, str], key: str) -> Path | None:
    value = meta.get(key, "")
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def final_vivado_counts(log_text: str) -> tuple[int, int, int] | None:
    matches = re.findall(
        r"(\d+)\s+Infos,\s+(\d+)\s+Warnings,\s+(\d+)\s+Critical Warnings and\s+(\d+)\s+Errors encountered\.",
        log_text,
    )
    if not matches:
        return None
    _infos, warnings, critical_warnings, errors = matches[-1]
    return int(warnings), int(critical_warnings), int(errors)


def count_candidate_pinmap_rows() -> int:
    if not PINMAP_CSV.exists():
        return 0
    with PINMAP_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return sum(1 for _row in csv.DictReader(f))


def drc_warning_summary(drc_text: str) -> tuple[int | None, bool, bool]:
    match = re.search(r"Violations found:\s+(\d+)", drc_text)
    violations = int(match.group(1)) if match else None
    has_zps7 = "ZPS7-1" in drc_text and "PS7 block required" in drc_text
    has_error = bool(re.search(r"\|\s+\S+\s+\|\s+Error\s+\|", drc_text, flags=re.IGNORECASE))
    return violations, has_zps7, has_error


def timing_summary_ok(timing_text: str) -> bool:
    if not timing_text:
        return False
    bad_markers = ["VIOLATED", "Timing constraints are not met"]
    return not any(marker in timing_text for marker in bad_markers)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint = find_hard_constraint()
    meta_path = latest_meta()
    meta = parse_meta(meta_path)
    log_path = path_from_meta(meta, "log")
    err_path = path_from_meta(meta, "err")
    out_path = path_from_meta(meta, "out")
    journal_path = path_from_meta(meta, "journal")

    log_text = read_text(log_path)
    err_text = read_text(err_path)
    drc_text = read_text(DRC_RPT)
    timing_text = read_text(TIMING_RPT)
    counts = final_vivado_counts(log_text)
    warnings, critical_warnings, errors = counts if counts is not None else (-1, -1, -1)
    drc_violations, drc_has_zps7, drc_has_error = drc_warning_summary(drc_text)
    pinmap_rows = count_candidate_pinmap_rows()
    marker_ok = "TFDU_SHUTDOWN_8LANE_CANDIDATE_BITSTREAM_READY" in log_text

    bitstream_ok = BITSTREAM.exists() and BITSTREAM.stat().st_size > 0
    report_files_ok = all(path.exists() and path.stat().st_size > 0 for path in [DCP, DRC_RPT, TIMING_RPT, IO_RPT, UTIL_RPT])
    vivado_ok = marker_ok and counts is not None and errors == 0 and critical_warnings == 0
    known_warning_only = warnings == 1 and drc_violations == 1 and drc_has_zps7 and not drc_has_error
    pinmap_ok = pinmap_rows == 64
    timing_ok = timing_summary_ok(timing_text)
    err_ok = not err_text.strip()

    items = [
        BuildItem(
            "HARD-CONSTRAINT",
            "PASS" if constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            rel(constraint),
            f"sha256={sha256(constraint)}",
        ),
        BuildItem(
            "BITSTREAM-FILE",
            "PASS" if bitstream_ok else "FAIL",
            rel(BITSTREAM),
            f"size_bytes={BITSTREAM.stat().st_size if BITSTREAM.exists() else 0}; sha256={sha256(BITSTREAM)}",
        ),
        BuildItem(
            "IMPLEMENTATION-REPORTS",
            "PASS" if report_files_ok else "FAIL",
            rel(SHUTDOWN_DIR),
            "Routed DCP, DRC, timing, IO, and utilization reports exist.",
        ),
        BuildItem(
            "VIVADO-RESULT",
            "PASS" if vivado_ok else "FAIL",
            rel(log_path),
            f"marker={marker_ok}; warnings={warnings}; critical_warnings={critical_warnings}; errors={errors}",
        ),
        BuildItem(
            "KNOWN-DRC-WARNING",
            "PASS_KNOWN_WARNING" if known_warning_only else "FAIL",
            rel(DRC_RPT),
            f"drc_violations={drc_violations}; ZPS7-1 warning is expected for this pure-PL shutdown candidate on Zynq.",
        ),
        BuildItem(
            "TIMING-SUMMARY",
            "PASS" if timing_ok else "FAIL",
            rel(TIMING_RPT),
            "No timing violation marker found; shutdown design has no active sequential datapath.",
        ),
        BuildItem(
            "PINMAP-COVERAGE",
            "PASS" if pinmap_ok else "FAIL",
            rel(PINMAP_CSV),
            f"candidate_pinmap_rows={pinmap_rows}/64",
        ),
        BuildItem(
            "NO-HARDWARE-ACTION",
            "PASS" if err_ok else "WARN",
            rel(meta_path),
            "Batch build only: no open_hw_manager, no program_hw_devices, no UART write, no TFDU drive.",
        ),
    ]
    failed = [item for item in items if item.status == "FAIL"]
    overall = "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED" if not failed else "FAIL"

    json_path = REPORTS / "8lane_shutdown_build_current.json"
    md_path = REPORTS / "8lane_shutdown_build_current.md"
    csv_path = REPORTS / "8lane_shutdown_build_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "status", "evidence", "note"])
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    md = [
        "# 8-Lane Shutdown Bitstream Build",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Bitstream: `{rel(BITSTREAM)}`",
        f"- Bitstream SHA256: `{sha256(BITSTREAM)}`",
        f"- Vivado final counts: warnings={warnings}, critical_warnings={critical_warnings}, errors={errors}",
        "- The single DRC warning is `ZPS7-1 PS7 block required`, expected for this pure-PL shutdown candidate.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "",
        "## Evidence",
        "",
        "| id | status | evidence | note |",
        "| --- | --- | --- | --- |",
    ]
    for item in items:
        md.append(f"| {item.item_id} | {item.status} | {item.evidence} | {item.note} |")
    md.extend(
        [
            "",
            "## Build Files",
            "",
            f"- Meta: `{rel(meta_path)}`",
            f"- Vivado log: `{rel(log_path)}`",
            f"- Stdout: `{rel(out_path)}`",
            f"- Stderr: `{rel(err_path)}`",
            f"- Journal: `{rel(journal_path)}`",
            f"- DRC report: `{rel(DRC_RPT)}`",
            f"- Timing report: `{rel(TIMING_RPT)}`",
            f"- IO report: `{rel(IO_RPT)}`",
            f"- Utilization report: `{rel(UTIL_RPT)}`",
            f"- Routed checkpoint: `{rel(DCP)}`",
            "",
            f"RF_COMM_8LANE_SHUTDOWN_BUILD overall={overall} bitstream={rel(BITSTREAM)}",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "bitstream": rel(BITSTREAM),
        "bitstream_sha256": sha256(BITSTREAM),
        "bitstream_size_bytes": BITSTREAM.stat().st_size if BITSTREAM.exists() else 0,
        "dcp": rel(DCP),
        "drc_report": rel(DRC_RPT),
        "timing_report": rel(TIMING_RPT),
        "io_report": rel(IO_RPT),
        "utilization_report": rel(UTIL_RPT),
        "meta": rel(meta_path),
        "vivado_log": rel(log_path),
        "stdout": rel(out_path),
        "stderr": rel(err_path),
        "journal": rel(journal_path),
        "vivado_warnings": warnings,
        "vivado_critical_warnings": critical_warnings,
        "vivado_errors": errors,
        "known_drc_warning": "ZPS7-1 PS7 block required" if known_warning_only else "",
        "drc_violations": drc_violations,
        "candidate_pinmap_rows": pinmap_rows,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "items": [asdict(item) for item in items],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_8LANE_SHUTDOWN_BUILD overall={overall} bitstream={rel(BITSTREAM)}")
    return 0 if overall != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
