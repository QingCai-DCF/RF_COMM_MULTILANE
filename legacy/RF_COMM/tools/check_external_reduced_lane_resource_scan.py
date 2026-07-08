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
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class ResourceOveruse:
    resource: str
    required: int
    available: int
    percent: float


@dataclass
class LaneResult:
    lane_count: int
    status: str
    synth_status: str
    impl_status: str
    drc_violations_found: int | None
    estimated_wns_ns: float | None
    resource_overuse: list[ResourceOveruse]
    evidence_dir: str
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
        REPORTS.glob("external_reduced_lane_resource_scan_*.meta.txt"),
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


def parse_log_markers(text: str, marker: str) -> dict[int, str]:
    pattern = re.compile(rf"{re.escape(marker)} lane=(\d+) status=(.+)")
    return {int(match.group(1)): match.group(2).strip() for match in pattern.finditer(text)}


def parse_drc_violations(text: str) -> int | None:
    match = re.search(r"Violations found:\s+(\d+)", text)
    return int(match.group(1)) if match else None


def parse_estimated_wns(text: str) -> float | None:
    matches = re.findall(r"Estimated Timing Summary\s+\|\s+WNS=([-0-9.]+)", text)
    if not matches:
        return None
    try:
        return float(matches[-1])
    except ValueError:
        return None


def parse_resource_overuse(text: str) -> list[ResourceOveruse]:
    pattern = re.compile(
        r"(?P<name>FDRE|LUT as Logic|Register as Flip Flop|Slice LUTs|Slice Registers) "
        r"over-utilized.*?requires\s+(?P<required>\d+)\s+of such cell types but only\s+"
        r"(?P<available>\d+)\s+compatible sites are available",
        re.IGNORECASE | re.DOTALL,
    )
    seen: set[str] = set()
    out: list[ResourceOveruse] = []
    for match in pattern.finditer(text):
        resource = match.group("name")
        if resource in seen:
            continue
        seen.add(resource)
        required = int(match.group("required"))
        available = int(match.group("available"))
        out.append(ResourceOveruse(resource, required, available, required / available * 100.0))
    return out


def resource_summary(resources: list[ResourceOveruse]) -> str:
    if not resources:
        return "none"
    return "; ".join(f"{item.resource}: {item.required}/{item.available} ({item.percent:.2f}%)" for item in resources)


def classify(synth_status: str, impl_status: str, impl_log: str, resources: list[ResourceOveruse]) -> tuple[str, str]:
    if "Complete" not in synth_status:
        return "SYNTH_MISSING_OR_FAIL", "synthesis did not complete cleanly"
    if resources or "place_design ERROR" in impl_status:
        return "PLACE_RESOURCE_BLOCKED", f"resource DRC blocked placement: {resource_summary(resources)}"
    if "place_design completed successfully" in impl_log:
        return "PLACE_PASS_REDUCED_PROFILE", "place_design completed for the reduced profile; this is not route/timing/bitstream/hardware acceptance"
    return "UNKNOWN", "unclassified reduced lane scan state"


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    constraint = find_hard_constraint()
    meta_file = latest_meta()
    if meta_file is None:
        raise FileNotFoundError("No external_reduced_lane_resource_scan_*.meta.txt found")
    meta = parse_meta(meta_file)
    scan_dir = meta_path(meta, "out_dir")
    vivado_log = meta_path(meta, "vivado_log")
    stdout_log = meta_path(meta, "stdout")
    stderr_log = meta_path(meta, "stderr")
    journal = meta_path(meta, "journal")
    vivado_text = read_text(vivado_log)
    synth_statuses = parse_log_markers(vivado_text, "EXTERNAL_RESOURCE_SCAN_SYNTH_STATUS")
    impl_statuses = parse_log_markers(vivado_text, "EXTERNAL_RESOURCE_SCAN_IMPL_STATUS")
    restored = "EXTERNAL_RESOURCE_SCAN_RESTORE_2LANE_DONE" in vivado_text
    scan_done = "EXTERNAL_RESOURCE_SCAN_DONE" in vivado_text

    results: list[LaneResult] = []
    for lane_dir in sorted((scan_dir or REPORTS).glob("lane_*")):
        match = re.fullmatch(r"lane_(\d+)", lane_dir.name)
        if not match:
            continue
        lane_count = int(match.group(1))
        drc_text = read_text(lane_dir / "drc_opted.rpt")
        impl_log = read_text(lane_dir / "impl_1_runme.log")
        resources = parse_resource_overuse(drc_text)
        status, note = classify(synth_statuses.get(lane_count, ""), impl_statuses.get(lane_count, ""), impl_log, resources)
        results.append(
            LaneResult(
                lane_count=lane_count,
                status=status,
                synth_status=synth_statuses.get(lane_count, ""),
                impl_status=impl_statuses.get(lane_count, ""),
                drc_violations_found=parse_drc_violations(drc_text),
                estimated_wns_ns=parse_estimated_wns(impl_log),
                resource_overuse=resources,
                evidence_dir=rel(lane_dir),
                note=note,
            )
        )

    pass_lanes = [item.lane_count for item in results if item.status == "PLACE_PASS_REDUCED_PROFILE"]
    blocked_lanes = [item.lane_count for item in results if item.status == "PLACE_RESOURCE_BLOCKED"]
    max_place_pass = max(pass_lanes) if pass_lanes else 0
    first_blocked = min(blocked_lanes) if blocked_lanes else None
    if results and len(pass_lanes) == len(results) and scan_done and restored:
        overall = f"PLACE_PASS_REDUCED_UP_TO_{max_place_pass}LANE"
    elif pass_lanes and first_blocked is not None:
        overall = "PLACE_PASS_REDUCED_PARTIAL_RESOURCE_BLOCKED"
    else:
        overall = "FAIL_OR_INCOMPLETE"

    md_path = REPORTS / "external_reduced_lane_resource_scan_current.md"
    json_path = REPORTS / "external_reduced_lane_resource_scan_current.json"
    csv_path = REPORTS / "external_reduced_lane_resource_scan_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "lane_count",
                "status",
                "synth_status",
                "impl_status",
                "drc_violations_found",
                "estimated_wns_ns",
                "resource_overuse",
                "evidence_dir",
                "note",
            ],
        )
        writer.writeheader()
        for item in results:
            row = asdict(item)
            row["resource_overuse"] = resource_summary(item.resource_overuse)
            writer.writerow(row)

    rows = [
        [
            str(item.lane_count),
            item.status,
            item.synth_status,
            item.impl_status,
            str(item.drc_violations_found) if item.drc_violations_found is not None else "",
            f"{item.estimated_wns_ns:.3f}" if item.estimated_wns_ns is not None else "",
            resource_summary(item.resource_overuse),
            item.evidence_dir,
            item.note,
        ]
        for item in results
    ]
    md = [
        "# External Reduced Lane Resource Scan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Profile: `lanes={meta.get('scan_lanes')}`, `fragment={meta.get('fragment_bytes')}`, `max_packet={meta.get('max_packet_bytes')}`, `TX/RX FIFO={meta.get('tx_async_fifo_depth')}/{meta.get('rx_async_fifo_depth')}`.",
        f"- Max reduced lane count that reached place_design: `{max_place_pass}`",
        f"- First reduced lane count blocked by resource DRC: `{first_blocked}`",
        "- This is offline place/resource evidence only. It is not route, timing, bitstream, TCP/DHCP, two-AX7010, or TFDU hardware acceptance.",
        "- The current board has no Ethernet cable, so real network acceptance remains deferred.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "",
        "## Lane Results",
        "",
        md_table(
            ["lane", "status", "synth", "impl", "drc", "est_wns", "resource_overuse", "evidence", "note"],
            rows,
        ),
        "",
        "## Files",
        "",
        f"- Meta: `{rel(meta_file)}`",
        f"- Vivado log: `{rel(vivado_log)}`",
        f"- Stdout: `{rel(stdout_log)}`",
        f"- Stderr: `{rel(stderr_log)}`",
        f"- Journal: `{rel(journal)}`",
        "",
        f"RF_COMM_EXTERNAL_REDUCED_LANE_RESOURCE_SCAN overall={overall} max_place_pass_lane={max_place_pass} first_blocked_lane={first_blocked}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "meta": meta,
        "meta_file": rel(meta_file),
        "scan_dir": rel(scan_dir),
        "vivado_log": rel(vivado_log),
        "stdout": rel(stdout_log),
        "stderr": rel(stderr_log),
        "journal": rel(journal),
        "scan_done": scan_done,
        "restored_2lane_stream_bidir": restored,
        "max_place_pass_lane_count": max_place_pass,
        "first_resource_blocked_lane_count": first_blocked,
        "no_hardware_programming": meta.get("no_hardware_programming") == "1",
        "no_uart_write": meta.get("no_uart_write") == "1",
        "no_tfdu_drive": meta.get("no_tfdu_drive") == "1",
        "current_board_ethernet": "not_connected",
        "real_tcp_dhcp_deferred": meta.get("ethernet_real_test_deferred") == "1",
        "lane_results": [asdict(item) for item in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_EXTERNAL_REDUCED_LANE_RESOURCE_SCAN overall={overall} max_place_pass_lane={max_place_pass} first_blocked_lane={first_blocked}")
    return 0 if overall != "FAIL_OR_INCOMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
