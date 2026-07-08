from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_external_reduced_2lane_route import (  # noqa: E402
    final_counts,
    md_table,
    parse_drc,
    parse_route_status,
    parse_timing_summary,
    parse_utilization,
)


@dataclass
class BitstreamItem:
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


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def latest_meta() -> Path | None:
    metas = sorted(
        REPORTS.glob("external_reduced_4lane_bitstream_*.meta.txt"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
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


def has_critical_or_error_drc(drc_text: str) -> bool:
    return bool(re.search(r"\|\s*[^|]+\s*\|\s*(Critical Warning|Error)\s*\|", drc_text))


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint = find_hard_constraint()
    meta_file = latest_meta()
    if meta_file is None:
        raise FileNotFoundError("No external_reduced_4lane_bitstream_*.meta.txt found")

    meta = parse_meta(meta_file)
    out_dir = meta_path(meta, "out_dir")
    vivado_log = meta_path(meta, "vivado_log")
    stdout_log = meta_path(meta, "stdout")
    stderr_log = meta_path(meta, "stderr")
    journal = meta_path(meta, "journal")
    bitstream = meta_path(meta, "bitstream")

    timing_rpt = out_dir / "external_reduced_4lane_candidate_timing_summary.rpt" if out_dir else None
    util_rpt = out_dir / "external_reduced_4lane_candidate_utilization.rpt" if out_dir else None
    route_rpt = out_dir / "external_reduced_4lane_candidate_route_status.rpt" if out_dir else None
    drc_rpt = out_dir / "external_reduced_4lane_candidate_drc.rpt" if out_dir else None
    io_rpt = out_dir / "external_reduced_4lane_candidate_io.rpt" if out_dir else None
    dcp = out_dir / "external_reduced_4lane_candidate_post_route.dcp" if out_dir else None

    vivado_text = read_text(vivado_log)
    stderr_text = read_text(stderr_log)
    timing = parse_timing_summary(read_text(timing_rpt))
    route = parse_route_status(read_text(route_rpt))
    drc_text = read_text(drc_rpt)
    drc = parse_drc(drc_text)
    utilization = parse_utilization(read_text(util_rpt))
    counts = final_counts(vivado_text)
    warnings, critical_warnings, errors = counts if counts is not None else (-1, -1, -1)

    bit_ok = bitstream is not None and bitstream.exists() and bitstream.stat().st_size > 0
    report_ok = all(path is not None and path.exists() and path.stat().st_size > 0 for path in [timing_rpt, util_rpt, route_rpt, drc_rpt, io_rpt, dcp])
    marker_ok = "EXTERNAL_REDUCED_4LANE_BITSTREAM_READY" in vivado_text
    no_hw = all(
        marker in vivado_text
        for marker in [
            "EXTERNAL_REDUCED_4LANE_BITSTREAM_NO_HARDWARE_PROGRAMMING=1",
            "EXTERNAL_REDUCED_4LANE_BITSTREAM_NO_UART_WRITE=1",
            "EXTERNAL_REDUCED_4LANE_BITSTREAM_NO_TFDU_DRIVE=1",
        ]
    )
    safe_meta = all(meta.get(key) == "1" for key in ["no_hardware_programming", "no_uart_write", "no_tfdu_drive"])
    ethernet_deferred = "EXTERNAL_REDUCED_4LANE_BITSTREAM_ETHERNET_DEFERRED=1" in vivado_text
    timing_pass = bool(timing["constraints_met"]) and (timing["wns_ns"] is not None and timing["wns_ns"] >= 0.0) and (timing["whs_ns"] is not None and timing["whs_ns"] >= 0.0)
    routing_clean = route["routing_errors"] == 0
    drc_no_critical = not has_critical_or_error_drc(drc_text)
    vivado_ok = counts is not None and critical_warnings == 0 and errors == 0 and not stderr_text.strip()

    if bit_ok and report_ok and marker_ok and timing_pass and routing_clean and drc_no_critical and no_hw and safe_meta and vivado_ok:
        overall = "PASS_OFFLINE_BITSTREAM_READY_REVIEW_REQUIRED"
    else:
        overall = "FAIL_OR_INCOMPLETE"

    items = [
        BitstreamItem("HARD-CONSTRAINT", "PASS" if sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL", rel(constraint), f"sha256={sha256(constraint)}"),
        BitstreamItem("BITSTREAM-FILE", "PASS" if bit_ok else "FAIL", rel(bitstream), f"size_bytes={bitstream.stat().st_size if bitstream and bitstream.exists() else 0}; sha256={sha256(bitstream)}"),
        BitstreamItem("IMPLEMENTATION-REPORTS", "PASS" if report_ok else "FAIL", rel(out_dir), "Candidate bitstream DCP, timing, utilization, route, DRC, and IO reports exist."),
        BitstreamItem("VIVADO-RESULT", "PASS" if vivado_ok and marker_ok else "FAIL", rel(vivado_log), f"marker={marker_ok}; warnings={warnings}; critical_warnings={critical_warnings}; errors={errors}"),
        BitstreamItem("ROUTE", "PASS" if routing_clean else "FAIL", rel(route_rpt), f"routing_errors={route.get('routing_errors')} fully_routed={route.get('fully_routed_nets')}/{route.get('routable_nets')}"),
        BitstreamItem("TIMING", "PASS" if timing_pass else "FAIL", rel(timing_rpt), f"WNS={timing['wns_ns']} ns, WHS={timing['whs_ns']} ns, TNS_fail={timing['tns_failing_endpoints']}, THS_fail={timing['ths_failing_endpoints']}"),
        BitstreamItem("DRC", "PASS_WITH_WARNINGS" if drc_no_critical else "FAIL", rel(drc_rpt), f"violations={drc['violations_found']} rules={drc['rules']}"),
        BitstreamItem("NO-HARDWARE-ACTION", "PASS" if no_hw and safe_meta else "FAIL", rel(meta_file), "No FPGA programming, no UART write, no TFDU drive."),
        BitstreamItem("NO-ETHERNET-BOUNDARY", "DEFERRED" if ethernet_deferred else "WARN", rel(meta_file), "Development board has no Ethernet cable; real TCP/DHCP and two-AX7010 Ethernet acceptance remain deferred."),
    ]

    md_path = REPORTS / "external_reduced_4lane_bitstream_current.md"
    json_path = REPORTS / "external_reduced_4lane_bitstream_current.json"
    csv_path = REPORTS / "external_reduced_4lane_bitstream_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "status", "evidence", "note"])
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    item_rows = [[item.item_id, item.status, item.evidence, item.note] for item in items]
    util_rows = [[item.resource, f"{item.used:g}", f"{item.available:g}", f"{item.percent:.2f}%"] for item in utilization]
    md = [
        "# External Reduced 4-Lane Candidate Bitstream",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Bitstream: `{rel(bitstream)}`",
        f"- Bitstream SHA256: `{sha256(bitstream)}`",
        f"- Timing: `WNS={timing['wns_ns']} ns`, `WHS={timing['whs_ns']} ns`, constraints met `{timing['constraints_met']}`.",
        f"- Routing: `routing_errors={route.get('routing_errors')}`, fully routed nets `{route.get('fully_routed_nets')}/{route.get('routable_nets')}`.",
        f"- DRC: `{drc['violations_found']}` warning/advisory violations, no critical warning/error DRC rows.",
        f"- Vivado final counts: warnings={warnings}, critical_warnings={critical_warnings}, errors={errors}.",
        "- This is an offline candidate bitstream only. It has not been programmed, reviewed for physical pin use, or accepted on TFDU hardware.",
        "- The current board has no Ethernet cable, so real network acceptance remains deferred.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "",
        "## Items",
        "",
        md_table(["id", "status", "evidence", "note"], item_rows),
        "",
        "## Utilization",
        "",
        md_table(["resource", "used", "available", "percent"], util_rows),
        "",
        "## Files",
        "",
        f"- Meta: `{rel(meta_file)}`",
        f"- Vivado log: `{rel(vivado_log)}`",
        f"- Stdout: `{rel(stdout_log)}`",
        f"- Stderr: `{rel(stderr_log)}`",
        f"- Journal: `{rel(journal)}`",
        f"- Timing: `{rel(timing_rpt)}`",
        f"- Utilization: `{rel(util_rpt)}`",
        f"- Route status: `{rel(route_rpt)}`",
        f"- DRC: `{rel(drc_rpt)}`",
        f"- IO: `{rel(io_rpt)}`",
        f"- Checkpoint: `{rel(dcp)}`",
        "",
        f"RF_COMM_EXTERNAL_REDUCED_4LANE_BITSTREAM overall={overall} bitstream={rel(bitstream)} wns={timing['wns_ns']} whs={timing['whs_ns']} route_errors={route.get('routing_errors')}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "meta": meta,
        "meta_file": rel(meta_file),
        "vivado_log": rel(vivado_log),
        "stdout": rel(stdout_log),
        "stderr": rel(stderr_log),
        "journal": rel(journal),
        "out_dir": rel(out_dir),
        "bitstream": rel(bitstream),
        "bitstream_sha256": sha256(bitstream),
        "bitstream_size_bytes": bitstream.stat().st_size if bitstream and bitstream.exists() else 0,
        "timing_report": rel(timing_rpt),
        "utilization_report": rel(util_rpt),
        "route_status_report": rel(route_rpt),
        "drc_report": rel(drc_rpt),
        "io_report": rel(io_rpt),
        "dcp": rel(dcp),
        "timing": timing,
        "route": route,
        "drc": drc,
        "utilization": [asdict(item) for item in utilization],
        "vivado_warnings": warnings,
        "vivado_critical_warnings": critical_warnings,
        "vivado_errors": errors,
        "timing_pass": timing_pass,
        "routing_clean": routing_clean,
        "drc_no_critical_or_error": drc_no_critical,
        "no_hardware_programming": no_hw and safe_meta,
        "no_uart_write": no_hw and safe_meta,
        "no_tfdu_drive": no_hw and safe_meta,
        "current_board_ethernet": "not_connected",
        "real_tcp_dhcp_deferred": ethernet_deferred,
        "items": [asdict(item) for item in items],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_EXTERNAL_REDUCED_4LANE_BITSTREAM overall={overall} bitstream={rel(bitstream)} wns={timing['wns_ns']} whs={timing['whs_ns']} route_errors={route.get('routing_errors')}")
    return 0 if overall != "FAIL_OR_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
