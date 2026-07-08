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
class OptionScanResult:
    lane_count: int
    status: str
    fragment_bytes: int | None
    max_packet_bytes: int | None
    tx_async_fifo_depth: int | None
    rx_async_fifo_depth: int | None
    synth_status: str
    impl_status: str
    drc_violations_found: int | None
    estimated_wns_ns: float | None
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


def latest_scan_dir() -> Path | None:
    scans = [
        path
        for path in REPORTS.glob("external_resource_option_scan_*")
        if path.is_dir() and re.fullmatch(r"external_resource_option_scan_\d{8}_\d{6}", path.name)
    ]
    scans.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return scans[0] if scans else None


def parse_meta(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def parse_log_markers(text: str, marker: str) -> dict[int, str]:
    pattern = re.compile(rf"{re.escape(marker)} lane=(\d+) status=(.+)")
    return {int(match.group(1)): match.group(2).strip() for match in pattern.finditer(text)}


def parse_drc_violations(text: str) -> int | None:
    match = re.search(r"Violations found:\s+(\d+)", text)
    return int(match.group(1)) if match else None


def parse_estimated_wns(text: str) -> float | None:
    match = re.search(r"Estimated Timing Summary\s+\|\s+WNS=([-0-9.]+)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def has_resource_drc_error(text: str) -> bool:
    return bool(re.search(r"over-utilized.*?requires\s+\d+.*?available", text, re.IGNORECASE | re.DOTALL))


def classify_lane(synth_status: str, impl_status: str, impl_log: str, drc_text: str) -> tuple[str, str]:
    if "Complete" not in synth_status:
        return "SYNTH_MISSING_OR_FAIL", "synthesis did not complete cleanly"
    if has_resource_drc_error(drc_text) or "place_design ERROR" in impl_status:
        return "PLACE_RESOURCE_BLOCKED", "resource DRC blocked placement"
    if "place_design completed successfully" in impl_log:
        return "PLACE_PASS_REDUCED_PROFILE", "reduced 2-lane external profile reached place_design; this is not routed/timing/bitstream/hardware acceptance"
    return "UNKNOWN", "unclassified option scan state"


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
    scan_dir = latest_scan_dir()
    if scan_dir is None:
        raise FileNotFoundError("No external_resource_option_scan_* directory found")

    stem = scan_dir.name
    meta_file = REPORTS / f"{stem}.meta.txt"
    vivado_log = REPORTS / f"{stem}.vivado.log"
    stdout_log = REPORTS / f"{stem}.out.log"
    stderr_log = REPORTS / f"{stem}.err.log"
    journal = REPORTS / f"{stem}.vivado.jou"
    meta = parse_meta(read_text(meta_file))
    vivado_text = read_text(vivado_log)
    synth_statuses = parse_log_markers(vivado_text, "EXTERNAL_RESOURCE_SCAN_SYNTH_STATUS")
    impl_statuses = parse_log_markers(vivado_text, "EXTERNAL_RESOURCE_SCAN_IMPL_STATUS")
    scan_done = "EXTERNAL_RESOURCE_SCAN_DONE lanes=2" in vivado_text
    restored = "EXTERNAL_RESOURCE_SCAN_RESTORE_2LANE_DONE" in vivado_text

    results: list[OptionScanResult] = []
    for lane_dir in sorted(scan_dir.glob("lane_*")):
        match = re.fullmatch(r"lane_(\d+)", lane_dir.name)
        if not match:
            continue
        lane_count = int(match.group(1))
        drc_text = read_text(lane_dir / "drc_opted.rpt")
        impl_log = read_text(lane_dir / "impl_1_runme.log")
        synth_status = synth_statuses.get(lane_count, "")
        impl_status = impl_statuses.get(lane_count, "")
        status, note = classify_lane(synth_status, impl_status, impl_log, drc_text)
        results.append(
            OptionScanResult(
                lane_count=lane_count,
                status=status,
                fragment_bytes=parse_int(meta.get("fragment_bytes")),
                max_packet_bytes=parse_int(meta.get("max_packet_bytes")),
                tx_async_fifo_depth=parse_int(meta.get("tx_async_fifo_depth")),
                rx_async_fifo_depth=parse_int(meta.get("rx_async_fifo_depth")),
                synth_status=synth_status,
                impl_status=impl_status,
                drc_violations_found=parse_drc_violations(drc_text),
                estimated_wns_ns=parse_estimated_wns(impl_log),
                evidence_dir=rel(lane_dir),
                note=note,
            )
        )

    pass_lanes = [item.lane_count for item in results if item.status == "PLACE_PASS_REDUCED_PROFILE"]
    if pass_lanes == [2] and scan_done and restored:
        overall = "PLACE_PASS_REDUCED_2LANE"
    elif pass_lanes:
        overall = "PARTIAL_PLACE_PASS_REDUCED_PROFILE"
    else:
        overall = "INCOMPLETE_OR_BLOCKED"

    md_path = REPORTS / "external_resource_option_scan_current.md"
    json_path = REPORTS / "external_resource_option_scan_current.json"
    csv_path = REPORTS / "external_resource_option_scan_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(OptionScanResult.__dataclass_fields__.keys()))
        writer.writeheader()
        for item in results:
            writer.writerow(asdict(item))

    rows = [
        [
            str(item.lane_count),
            item.status,
            str(item.fragment_bytes),
            str(item.max_packet_bytes),
            str(item.tx_async_fifo_depth),
            str(item.rx_async_fifo_depth),
            item.synth_status,
            item.impl_status,
            str(item.drc_violations_found) if item.drc_violations_found is not None else "",
            f"{item.estimated_wns_ns:.3f}" if item.estimated_wns_ns is not None else "",
            item.evidence_dir,
            item.note,
        ]
        for item in results
    ]
    md = [
        "# External A-Only Reduced-Resource Option Scan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Scanned lane count: `{meta.get('scan_lanes', 'unknown')}`",
        f"- Reduced profile: `IR_FRAGMENT_BYTES={meta.get('fragment_bytes', 'unknown')}`, `IR_MAX_PACKET_BYTES={meta.get('max_packet_bytes', 'unknown')}`, `TX_ASYNC_FIFO_DEPTH={meta.get('tx_async_fifo_depth', 'unknown')}`, `RX_ASYNC_FIFO_DEPTH={meta.get('rx_async_fifo_depth', 'unknown')}`.",
        "- This is an offline Vivado place-design result only; it is not route, timing, bitstream, TCP/DHCP, two-AX7010, or TFDU hardware acceptance.",
        "- The current board has no Ethernet cable, so real TCP/DHCP and real two-AX7010 network acceptance are deferred.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "- After the scan, the active Vivado project was restored to the 2-lane `stream_bidir` working shape.",
        "",
        "## Lane Results",
        "",
        md_table(
            [
                "lane_count",
                "status",
                "fragment",
                "max_packet",
                "tx_fifo",
                "rx_fifo",
                "synth_status",
                "impl_status",
                "drc_violations",
                "est_wns_ns",
                "evidence",
                "note",
            ],
            rows,
        ),
        "",
        "## Scan Files",
        "",
        f"- Meta: `{rel(meta_file)}`",
        f"- Vivado log: `{rel(vivado_log)}`",
        f"- Stdout: `{rel(stdout_log)}`",
        f"- Stderr: `{rel(stderr_log)}`",
        f"- Journal: `{rel(journal)}`",
        "",
        f"RF_COMM_EXTERNAL_RESOURCE_OPTION_SCAN overall={overall} lane=2 fragment_bytes={meta.get('fragment_bytes', 'unknown')} max_packet_bytes={meta.get('max_packet_bytes', 'unknown')} tx_fifo={meta.get('tx_async_fifo_depth', 'unknown')} rx_fifo={meta.get('rx_async_fifo_depth', 'unknown')}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "scan_dir": rel(scan_dir),
        "meta_file": rel(meta_file),
        "meta": meta,
        "vivado_log": rel(vivado_log),
        "stdout_log": rel(stdout_log),
        "stderr_log": rel(stderr_log),
        "journal": rel(journal),
        "scan_done": scan_done,
        "restored_2lane_stream_bidir": restored,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "current_board_ethernet": "not_connected",
        "results": [asdict(item) for item in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_EXTERNAL_RESOURCE_OPTION_SCAN "
        f"overall={overall} lane=2 fragment_bytes={meta.get('fragment_bytes', 'unknown')} "
        f"max_packet_bytes={meta.get('max_packet_bytes', 'unknown')} "
        f"tx_fifo={meta.get('tx_async_fifo_depth', 'unknown')} rx_fifo={meta.get('rx_async_fifo_depth', 'unknown')}"
    )
    return 0 if overall != "INCOMPLETE_OR_BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
