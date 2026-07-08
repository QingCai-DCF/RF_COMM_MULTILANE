from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
SOURCE_CSV = REPORTS / "8lane_a_only_candidate_xdc_current.csv"
OUT_DIR = REPORTS / "external_lane_scan_xdcs"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class ScanXdc:
    lane_count: int
    path: str
    assignment_count: int
    sha256: str


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


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def load_rows() -> list[dict[str, str]]:
    with SOURCE_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rows = [row for row in rows if row["endpoint"] == "A"]
    rows.sort(key=lambda row: (int(row["lane"]), {"MODE": 0, "RX": 1, "SD": 2, "TX": 3}[row["signal"]]))
    return rows


def write_xdc(rows: list[dict[str, str]], lane_count: int, generated: str) -> Path:
    selected = [row for row in rows if int(row["lane"]) < lane_count]
    if len(selected) != lane_count * 4:
        raise RuntimeError(f"lane_count={lane_count} selected={len(selected)} expected={lane_count * 4}")
    out = OUT_DIR / f"target_ir_array_external_{lane_count}lane_scan.xdc"
    lines = [
        "###############################################################################",
        f"# External A-only {lane_count}-lane resource-scan constraints",
        "# Candidate/scan only: not an active hardware constraint file.",
        f"# Generated: {generated}",
        "# Source: reports/8lane_a_only_candidate_xdc_current.csv",
        "# Intended profile: IR_B_MODE=external.",
        "# This file deliberately excludes loop_* B endpoint ports and lanes above the scan count.",
        "###############################################################################",
        "",
        "set_false_path -to [get_pins -of_objects [get_cells -hierarchical -filter {NAME =~ *sync_ff1_reg*}] -filter {NAME =~ *D}]",
        "",
    ]
    for row in selected:
        lines.append(
            f"# lane={row['lane']} signal={row['signal']} {row['port']} -> {row['board_signal']} / {row['package_pin']} / {row['origin']}"
        )
        lines.append(f"set_property PACKAGE_PIN {row['package_pin']} [get_ports {{{row['port']}}}]")
        lines.append(f"set_property IOSTANDARD LVCMOS33 [get_ports {{{row['port']}}}]")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main() -> int:
    generated = datetime.now().isoformat(timespec="seconds")
    REPORTS.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows = load_rows()
    outputs: list[ScanXdc] = []
    for lane_count in range(1, 9):
        path = write_xdc(rows, lane_count, generated)
        outputs.append(
            ScanXdc(
                lane_count=lane_count,
                path=rel(path),
                assignment_count=lane_count * 4,
                sha256=sha256(path),
            )
        )

    md_path = REPORTS / "external_lane_scan_xdcs_current.md"
    json_path = REPORTS / "external_lane_scan_xdcs_current.json"
    csv_path = REPORTS / "external_lane_scan_xdcs_current.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["lane_count", "path", "assignment_count", "sha256"])
        writer.writeheader()
        for item in outputs:
            writer.writerow(asdict(item))
    md = [
        "# External Lane Resource-Scan XDCs",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        "- Overall: `PASS_SCAN_XDCS_GENERATED`",
        "- Generated lane-count-specific A-only external scan constraints for lanes 1..8.",
        "- These files are for offline Vivado resource scanning only and are not promoted to active constraints.",
        "",
        "| lane_count | assignments | path | sha256 |",
        "| --- | --- | --- | --- |",
    ]
    for item in outputs:
        md.append(f"| {item.lane_count} | {item.assignment_count} | {item.path} | {item.sha256} |")
    md.extend(
        [
            "",
            "RF_COMM_EXTERNAL_LANE_SCAN_XDCS overall=PASS_SCAN_XDCS_GENERATED lane_counts=1..8",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    payload = {
        "generated": generated,
        "overall": "PASS_SCAN_XDCS_GENERATED",
        "hard_constraint_sha256": sha256(find_hard_constraint()),
        "source_csv": rel(SOURCE_CSV),
        "out_dir": rel(OUT_DIR),
        "scan_xdcs": [asdict(item) for item in outputs],
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print("RF_COMM_EXTERNAL_LANE_SCAN_XDCS overall=PASS_SCAN_XDCS_GENERATED lane_counts=1..8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
