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
class LaneScanResult:
    lane_count: int
    status: str
    synth_status: str
    impl_status: str
    drc_violations_found: int | None
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


def latest_scan_dir() -> Path | None:
    scans = [
        path
        for path in REPORTS.glob("external_lane_resource_scan_*")
        if path.is_dir() and re.fullmatch(r"external_lane_resource_scan_\d{8}_\d{6}", path.name)
    ]
    scans.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return scans[0] if scans else None


def parse_log_markers(text: str, marker: str) -> dict[int, str]:
    pattern = re.compile(rf"{re.escape(marker)} lane=(\d+) status=(.+)")
    return {int(match.group(1)): match.group(2).strip() for match in pattern.finditer(text)}


def parse_resource_overuse(text: str) -> list[ResourceOveruse]:
    pattern = re.compile(
        r"(?P<name>FDRE|LUT as Logic|Register as Flip Flop|Slice LUTs|Slice Registers) "
        r"over-utilized.*?requires\s+(?P<required>\d+)\s+of such cell types but only\s+"
        r"(?P<available>\d+)\s+compatible sites are available",
        re.IGNORECASE | re.DOTALL,
    )
    seen: set[str] = set()
    resources: list[ResourceOveruse] = []
    for match in pattern.finditer(text):
        resource = match.group("name")
        if resource in seen:
            continue
        seen.add(resource)
        required = int(match.group("required"))
        available = int(match.group("available"))
        resources.append(ResourceOveruse(resource, required, available, required / available * 100.0))
    return resources


def parse_drc_violations(text: str) -> int | None:
    match = re.search(r"Violations found:\s+(\d+)", text)
    return int(match.group(1)) if match else None


def resource_summary(resources: list[ResourceOveruse]) -> str:
    if not resources:
        return "none"
    return "; ".join(f"{item.resource}: {item.required}/{item.available} ({item.percent:.2f}%)" for item in resources)


def classify_lane(
    lane_count: int,
    synth_status: str,
    impl_status: str,
    impl_log: str,
    resource_overuse: list[ResourceOveruse],
) -> tuple[str, str]:
    if "Complete" not in synth_status:
        return "SYNTH_MISSING_OR_FAIL", "synthesis did not complete cleanly"
    if resource_overuse or "ERROR" in impl_status:
        return "PLACE_RESOURCE_BLOCKED", f"resource DRC blocked placement: {resource_summary(resource_overuse)}"
    if "place_design completed successfully" in impl_log:
        return "PLACE_PASS", "place_design completed; this is not routed/timing/bitstream acceptance"
    return "UNKNOWN", f"unclassified lane scan state for lane_count={lane_count}"


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
        raise FileNotFoundError("No external_lane_resource_scan_* directory found")

    stem = scan_dir.name
    vivado_log = REPORTS / f"{stem}.vivado.log"
    stdout_log = REPORTS / f"{stem}.out.log"
    stderr_log = REPORTS / f"{stem}.err.log"
    meta_file = REPORTS / f"{stem}.meta.txt"
    journal = REPORTS / f"{stem}.vivado.jou"
    vivado_text = read_text(vivado_log)
    synth_statuses = parse_log_markers(vivado_text, "EXTERNAL_RESOURCE_SCAN_SYNTH_STATUS")
    impl_statuses = parse_log_markers(vivado_text, "EXTERNAL_RESOURCE_SCAN_IMPL_STATUS")
    restored = "EXTERNAL_RESOURCE_SCAN_RESTORE_2LANE_DONE" in vivado_text
    scan_done = "EXTERNAL_RESOURCE_SCAN_DONE lanes=1 2 3 4 5 6 7 8" in vivado_text

    results: list[LaneScanResult] = []
    for lane_dir in sorted(scan_dir.glob("lane_*")):
        match = re.fullmatch(r"lane_(\d+)", lane_dir.name)
        if not match:
            continue
        lane_count = int(match.group(1))
        drc_text = read_text(lane_dir / "drc_opted.rpt")
        impl_log = read_text(lane_dir / "impl_1_runme.log")
        resources = parse_resource_overuse(drc_text)
        synth_status = synth_statuses.get(lane_count, "")
        impl_status = impl_statuses.get(lane_count, "")
        status, note = classify_lane(lane_count, synth_status, impl_status, impl_log, resources)
        results.append(
            LaneScanResult(
                lane_count=lane_count,
                status=status,
                synth_status=synth_status,
                impl_status=impl_status,
                drc_violations_found=parse_drc_violations(drc_text),
                resource_overuse=resources,
                evidence_dir=rel(lane_dir),
                note=note,
            )
        )

    pass_lanes = [item.lane_count for item in results if item.status == "PLACE_PASS"]
    blocked_lanes = [item.lane_count for item in results if item.status == "PLACE_RESOURCE_BLOCKED"]
    max_place_pass_lane = max(pass_lanes) if pass_lanes else 0
    first_resource_blocked_lane = min(blocked_lanes) if blocked_lanes else None
    if max_place_pass_lane == 1 and first_resource_blocked_lane == 2 and scan_done and restored:
        overall = "PLACE_PASS_ONLY_1LANE"
    elif first_resource_blocked_lane is not None:
        overall = "PARTIAL_PLACE_RESOURCE_BLOCKED"
    elif results and len(pass_lanes) == len(results):
        overall = "ALL_SCANNED_LANES_PLACE_PASS"
    else:
        overall = "INCOMPLETE_OR_UNKNOWN"

    md_path = REPORTS / "external_lane_resource_scan_current.md"
    json_path = REPORTS / "external_lane_resource_scan_current.json"
    csv_path = REPORTS / "external_lane_resource_scan_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "lane_count",
                "status",
                "synth_status",
                "impl_status",
                "drc_violations_found",
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
            resource_summary(item.resource_overuse),
            item.evidence_dir,
            item.note,
        ]
        for item in results
    ]
    md = [
        "# External A-Only Lane Resource Scan",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        f"- Overall: `{overall}`",
        f"- Max lane count that reached `place_design`: `{max_place_pass_lane}`",
        f"- First lane count blocked by resource DRC: `{first_resource_blocked_lane}`",
        "- Profile: `IR_B_MODE=external`, scanned `IR_LANE_COUNT=1..8`, `IR_FRAGMENT_BYTES=255`, `IR_MAX_PACKET_BYTES=255`.",
        "- The current board has no Ethernet cable; real TCP/DHCP and two-AX7010 Ethernet acceptance are deferred.",
        "- No FPGA was programmed; no UART was written; no TFDU was driven.",
        "- After the scan, the active Vivado project was restored to the 2-lane `stream_bidir` working shape.",
        "",
        "## Lane Results",
        "",
        md_table(
            [
                "lane_count",
                "status",
                "synth_status",
                "impl_status",
                "drc_violations",
                "resource_overuse",
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
        f"RF_COMM_EXTERNAL_LANE_RESOURCE_SCAN overall={overall} first_blocked_lane={first_resource_blocked_lane} max_place_pass_lane={max_place_pass_lane}",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": overall,
        "hard_constraint_sha256": sha256(constraint),
        "scan_dir": rel(scan_dir),
        "meta": rel(meta_file),
        "vivado_log": rel(vivado_log),
        "stdout_log": rel(stdout_log),
        "stderr_log": rel(stderr_log),
        "journal": rel(journal),
        "scan_done": scan_done,
        "restored_2lane_stream_bidir": restored,
        "max_place_pass_lane_count": max_place_pass_lane,
        "first_resource_blocked_lane_count": first_resource_blocked_lane,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "current_board_ethernet": "not_connected",
        "lane_results": [asdict(item) for item in results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_EXTERNAL_LANE_RESOURCE_SCAN "
        f"overall={overall} first_blocked_lane={first_resource_blocked_lane} max_place_pass_lane={max_place_pass_lane}"
    )
    return 0 if overall != "INCOMPLETE_OR_UNKNOWN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
