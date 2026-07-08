from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class RouteItem:
    item_id: str
    status: str
    evidence: str
    note: str


@dataclass
class UtilizationItem:
    resource: str
    used: float
    available: float
    percent: float


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


def latest_meta(pattern: str) -> Path | None:
    metas = sorted(
        ROOT.glob(pattern),
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


def parse_float(value: str) -> float:
    return float(value)


def parse_timing_summary(text: str) -> dict[str, float | int | bool | None]:
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if "WNS(ns)" not in line or "TNS Failing Endpoints" not in line:
            continue
        for candidate in lines[index + 1 : index + 8]:
            numbers = re.findall(r"-?\d+\.\d+|-?\d+", candidate)
            if len(numbers) >= 12:
                return {
                    "wns_ns": parse_float(numbers[0]),
                    "tns_ns": parse_float(numbers[1]),
                    "tns_failing_endpoints": int(numbers[2]),
                    "tns_total_endpoints": int(numbers[3]),
                    "whs_ns": parse_float(numbers[4]),
                    "ths_ns": parse_float(numbers[5]),
                    "ths_failing_endpoints": int(numbers[6]),
                    "ths_total_endpoints": int(numbers[7]),
                    "wpws_ns": parse_float(numbers[8]),
                    "tpws_ns": parse_float(numbers[9]),
                    "tpws_failing_endpoints": int(numbers[10]),
                    "tpws_total_endpoints": int(numbers[11]),
                    "constraints_met": "All user specified timing constraints are met." in text,
                }
    return {
        "wns_ns": None,
        "tns_ns": None,
        "tns_failing_endpoints": None,
        "tns_total_endpoints": None,
        "whs_ns": None,
        "ths_ns": None,
        "ths_failing_endpoints": None,
        "ths_total_endpoints": None,
        "wpws_ns": None,
        "tpws_ns": None,
        "tpws_failing_endpoints": None,
        "tpws_total_endpoints": None,
        "constraints_met": False,
    }


def parse_route_status(text: str) -> dict[str, int | None]:
    def find(label: str) -> int | None:
        match = re.search(rf"{re.escape(label)}\.*\s*:\s*(\d+)", text)
        return int(match.group(1)) if match else None

    return {
        "logical_nets": find("# of logical nets"),
        "routable_nets": find("# of routable nets"),
        "fully_routed_nets": find("# of fully routed nets"),
        "routing_errors": find("# of nets with routing errors"),
    }


def parse_drc(text: str) -> dict[str, object]:
    violations_match = re.search(r"Violations found:\s+(\d+)", text)
    rule_rows = []
    for match in re.finditer(r"\|\s*([A-Z0-9-]+)\s*\|\s*(Warning|Advisory|Critical Warning|Error)\s*\|[^|]*\|\s*(\d+)\s*\|", text):
        rule_rows.append(
            {
                "rule": match.group(1),
                "severity": match.group(2),
                "violations": int(match.group(3)),
            }
        )
    return {
        "violations_found": int(violations_match.group(1)) if violations_match else None,
        "rules": rule_rows,
        "critical_or_error": any(row["severity"] in {"Critical Warning", "Error"} for row in rule_rows),
    }


def parse_utilization(text: str) -> list[UtilizationItem]:
    wanted = ["Slice LUTs", "LUT as Logic", "Slice Registers", "Block RAM Tile", "DSPs", "Bonded IOB"]
    out: list[UtilizationItem] = []
    seen: set[str] = set()
    for line in text.splitlines():
        if "|" not in line:
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            continue
        resource = cells[0]
        if resource not in wanted or resource in seen:
            continue
        numbers = re.findall(r"\d+(?:\.\d+)?", line)
        if len(numbers) < 3:
            continue
        used = float(numbers[0])
        available = float(numbers[-2])
        percent = float(numbers[-1])
        seen.add(resource)
        out.append(UtilizationItem(resource, used, available, percent))
    return out


def final_counts(text: str) -> tuple[int, int, int] | None:
    matches = re.findall(
        r"(\d+)\s+Infos,\s+(\d+)\s+Warnings,\s+(\d+)\s+Critical Warnings and\s+(\d+)\s+Errors encountered\.",
        text,
    )
    if not matches:
        return None
    _infos, warnings, critical, errors = matches[-1]
    return int(warnings), int(critical), int(errors)


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check an offline reduced external route/timing build.")
    parser.add_argument("--meta-glob", default="reports/build_external_reduced_2lane_route_*.meta.txt")
    parser.add_argument("--output-stem", default="external_reduced_2lane_route_current")
    parser.add_argument("--title", default="External Reduced 2-Lane Route Check")
    parser.add_argument("--pass-overall", default="ROUTE_TIMING_PASS_REDUCED_2LANE")
    parser.add_argument("--marker-name", default="RF_COMM_EXTERNAL_REDUCED_2LANE_ROUTE")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint = find_hard_constraint()
    meta_file = latest_meta(args.meta_glob)
    if meta_file is None:
        raise FileNotFoundError(f"No route build meta file matched: {args.meta_glob}")
    meta = parse_meta(meta_file)
    out_dir = meta_path(meta, "out_dir")
    vivado_log = meta_path(meta, "vivado_log")
    stdout_log = meta_path(meta, "stdout")
    stderr_log = meta_path(meta, "stderr")
    journal = meta_path(meta, "journal")

    timing_rpt = out_dir / "timing_summary_post_route.rpt" if out_dir else None
    util_rpt = out_dir / "utilization_post_route.rpt" if out_dir else None
    route_rpt = out_dir / "route_status_post_route.rpt" if out_dir else None
    drc_rpt = out_dir / "drc_post_route.rpt" if out_dir else None
    synth_log = out_dir / "synth_1_runme.log" if out_dir else None
    impl_log = out_dir / "impl_1_runme.log" if out_dir else None

    vivado_text = read_text(vivado_log)
    timing = parse_timing_summary(read_text(timing_rpt))
    route = parse_route_status(read_text(route_rpt))
    drc = parse_drc(read_text(drc_rpt))
    utilization = parse_utilization(read_text(util_rpt))
    counts = final_counts(vivado_text)
    warnings, critical_warnings, errors = counts if counts is not None else (-1, -1, -1)

    synth_pass = "EXTERNAL_REDUCED_ROUTE_SYNTH_STATUS=synth_design Complete!" in vivado_text
    route_pass = "EXTERNAL_REDUCED_ROUTE_IMPL_STATUS=route_design Complete!" in vivado_text
    build_done = "EXTERNAL_REDUCED_ROUTE_BUILD_DONE" in vivado_text
    restored = "EXTERNAL_REDUCED_ROUTE_RESTORE_2LANE_DONE" in vivado_text
    no_hw = all(
        marker in vivado_text
        for marker in [
            "EXTERNAL_REDUCED_ROUTE_NO_HARDWARE_PROGRAMMING=1",
            "EXTERNAL_REDUCED_ROUTE_NO_UART_WRITE=1",
            "EXTERNAL_REDUCED_ROUTE_NO_TFDU_DRIVE=1",
        ]
    )
    ethernet_deferred = "EXTERNAL_REDUCED_ROUTE_ETHERNET_DEFERRED=1" in vivado_text
    timing_pass = bool(timing["constraints_met"]) and (timing["wns_ns"] is not None and timing["wns_ns"] >= 0.0) and (timing["whs_ns"] is not None and timing["whs_ns"] >= 0.0)
    routing_clean = route["routing_errors"] == 0
    drc_no_critical = not bool(drc["critical_or_error"])
    safe_meta = all(meta.get(key) == "1" for key in ["no_hardware_programming", "no_uart_write", "no_tfdu_drive"])

    if synth_pass and route_pass and build_done and timing_pass and routing_clean and drc_no_critical and restored and no_hw and safe_meta:
        overall = args.pass_overall
    elif synth_pass and route_pass:
        overall = "ROUTE_COMPLETE_WITH_GAPS"
    else:
        overall = "FAIL_OR_INCOMPLETE"

    items = [
        RouteItem("HARD-CONSTRAINT", "PASS" if sha256(constraint) == EXPECTED_CONSTRAINT_SHA256 else "FAIL", rel(constraint), f"sha256={sha256(constraint)}"),
        RouteItem("PROFILE", "PASS", rel(meta_file), f"lane={meta.get('lane_count')} fragment={meta.get('fragment_bytes')} max_packet={meta.get('max_packet_bytes')} tx_fifo={meta.get('tx_async_fifo_depth')} rx_fifo={meta.get('rx_async_fifo_depth')}"),
        RouteItem("AFFINITY", "PASS" if meta.get("affinity_set") == meta.get("affinity_mask") else "WARN", rel(meta_file), f"affinity={meta.get('affinity_set', 'not_set')} priority={meta.get('priority_set', 'not_set')}"),
        RouteItem("SYNTHESIS", "PASS" if synth_pass else "FAIL", rel(synth_log), "synth_design Complete!" if synth_pass else "synthesis did not complete"),
        RouteItem("ROUTE", "PASS" if route_pass and routing_clean else "FAIL", rel(route_rpt), f"route_design Complete; routing_errors={route.get('routing_errors')} fully_routed={route.get('fully_routed_nets')}/{route.get('routable_nets')}" if route_pass else "route did not complete"),
        RouteItem("TIMING", "PASS" if timing_pass else "FAIL", rel(timing_rpt), f"WNS={timing['wns_ns']} ns, WHS={timing['whs_ns']} ns, TNS_fail={timing['tns_failing_endpoints']}, THS_fail={timing['ths_failing_endpoints']}"),
        RouteItem("DRC", "PASS_WITH_WARNINGS" if drc_no_critical else "FAIL", rel(drc_rpt), f"violations={drc['violations_found']} rules={drc['rules']}"),
        RouteItem("RESTORE-ACTIVE-PROJECT", "PASS" if restored else "FAIL", rel(vivado_log), "PORT1.xdc restored, scan XDC removed, and active 2-lane stream_bidir BD restored."),
        RouteItem("NO-HARDWARE-ACTION", "PASS" if no_hw and safe_meta else "FAIL", rel(meta_file), "No FPGA programming, no UART write, no TFDU drive."),
        RouteItem("NO-ETHERNET-BOUNDARY", "DEFERRED" if ethernet_deferred else "WARN", rel(meta_file), "Development board has no Ethernet cable; real TCP/DHCP and two-AX7010 Ethernet acceptance remain deferred."),
    ]

    md_path = REPORTS / f"{args.output_stem}.md"
    json_path = REPORTS / f"{args.output_stem}.json"
    csv_path = REPORTS / f"{args.output_stem}.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["item_id", "status", "evidence", "note"])
        writer.writeheader()
        for item in items:
            writer.writerow(asdict(item))

    util_rows = [
        [item.resource, f"{item.used:g}", f"{item.available:g}", f"{item.percent:.2f}%"]
        for item in utilization
    ]
    item_rows = [[item.item_id, item.status, item.evidence, item.note] for item in items]
    md = [
        f"# {args.title}",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Profile: `lane={meta.get('lane_count')}`, `fragment={meta.get('fragment_bytes')}`, `max_packet={meta.get('max_packet_bytes')}`, `TX/RX FIFO={meta.get('tx_async_fifo_depth')}/{meta.get('rx_async_fifo_depth')}`.",
        f"- Timing: `WNS={timing['wns_ns']} ns`, `WHS={timing['whs_ns']} ns`, constraints met `{timing['constraints_met']}`.",
        f"- Routing: `routing_errors={route.get('routing_errors')}`, fully routed nets `{route.get('fully_routed_nets')}/{route.get('routable_nets')}`.",
        f"- DRC: `{drc['violations_found']}` warning/advisory violations, no critical warning/error DRC rows.",
        "- This is offline route/timing evidence only. It is not bitstream programming, TCP/DHCP, two-AX7010, or TFDU hardware acceptance.",
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
        "",
        f"{args.marker_name} overall={overall} wns={timing['wns_ns']} whs={timing['whs_ns']} route_errors={route.get('routing_errors')}",
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
        "timing_report": rel(timing_rpt),
        "utilization_report": rel(util_rpt),
        "route_status_report": rel(route_rpt),
        "drc_report": rel(drc_rpt),
        "synth_log": rel(synth_log),
        "impl_log": rel(impl_log),
        "timing": timing,
        "route": route,
        "drc": drc,
        "utilization": [asdict(item) for item in utilization],
        "vivado_warnings": warnings,
        "vivado_critical_warnings": critical_warnings,
        "vivado_errors": errors,
        "synthesis_pass": synth_pass,
        "route_pass": route_pass,
        "timing_pass": timing_pass,
        "routing_clean": routing_clean,
        "drc_no_critical_or_error": drc_no_critical,
        "restored_2lane_stream_bidir": restored,
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
    print(f"{args.marker_name} overall={overall} wns={timing['wns_ns']} whs={timing['whs_ns']} route_errors={route.get('routing_errors')}")
    return 0 if overall != "FAIL_OR_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
