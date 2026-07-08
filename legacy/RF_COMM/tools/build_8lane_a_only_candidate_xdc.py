from __future__ import annotations

import csv
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
PINMAP_CSV = REPORTS / "8lane_candidate_pinmap_current.csv"
OUT_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "target_ir_array_8lane_a_only_candidate.xdc"
PORT1_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "PORT1.xdc"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class AOnlyAssignment:
    endpoint: str
    lane: int
    signal: str
    port: str
    package_pin: str
    board_signal: str
    group: str
    origin: str
    note: str


def sha256(path: Path | None) -> str:
    if path is None or not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def load_assignments() -> list[AOnlyAssignment]:
    with PINMAP_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    out: list[AOnlyAssignment] = []
    for row in rows:
        if row["endpoint"] != "A":
            continue
        out.append(
            AOnlyAssignment(
                endpoint=row["endpoint"],
                lane=int(row["lane"]),
                signal=row["signal"],
                port=row["port"],
                package_pin=row["package_pin"],
                board_signal=row["board_signal"],
                group=row["connector_group"],
                origin=row["origin"],
                note="A-only external 8-lane candidate for two-AX7010 style topology; review before hardware use.",
            )
        )
    return sorted(out, key=lambda item: (item.lane, {"MODE": 0, "RX": 1, "SD": 2, "TX": 3}[item.signal]))


def validate(assignments: list[AOnlyAssignment]) -> None:
    if len(assignments) != 32:
        raise RuntimeError(f"Expected 32 A-only assignments, got {len(assignments)}")
    pins: dict[str, list[str]] = {}
    for item in assignments:
        pins.setdefault(item.package_pin, []).append(item.port)
    dupes = {pin: ports for pin, ports in pins.items() if len(ports) > 1}
    if dupes:
        raise RuntimeError(f"Duplicate pins in A-only XDC: {dupes}")
    for lane in range(8):
        got = {item.signal for item in assignments if item.lane == lane}
        if got != {"MODE", "RX", "SD", "TX"}:
            raise RuntimeError(f"Lane {lane} missing signals: {got}")
    if any(item.port.startswith("loop_") for item in assignments):
        raise RuntimeError("A-only assignment unexpectedly contains loop_* B endpoint ports")


def write_xdc(assignments: list[AOnlyAssignment], generated: str) -> None:
    lines = [
        "###############################################################################",
        "# 8-lane TFDU A-only external candidate constraints",
        "#",
        f"# Generated: {generated}",
        "# Source: reports/8lane_candidate_pinmap_current.csv",
        "#",
        "# Candidate only: build/review before hardware use.",
        "# Intended profile: IR_LANE_COUNT=8, IR_B_MODE=external.",
        "# This file deliberately excludes loop_* B-endpoint ports.",
        "###############################################################################",
        "",
        "# First synchronizer stage CDC path, preserved from PORT1.xdc.",
        "set_false_path -to [get_pins -of_objects [get_cells -hierarchical -filter {NAME =~ *sync_ff1_reg*}] -filter {NAME =~ *D}]",
        "",
    ]
    for item in assignments:
        lines.append(f"# Endpoint A lane={item.lane} signal={item.signal} {item.port} -> {item.board_signal} / {item.package_pin} / {item.origin}")
        lines.append(f"set_property PACKAGE_PIN {item.package_pin} [get_ports {{{item.port}}}]")
        lines.append(f"set_property IOSTANDARD LVCMOS33 [get_ports {{{item.port}}}]")
    OUT_XDC.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_reports(assignments: list[AOnlyAssignment], generated: str) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    md_path = REPORTS / "8lane_a_only_candidate_xdc_current.md"
    json_path = REPORTS / "8lane_a_only_candidate_xdc_current.json"
    csv_path = REPORTS / "8lane_a_only_candidate_xdc_current.csv"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(assignments[0]).keys()))
        writer.writeheader()
        for item in assignments:
            writer.writerow(asdict(item))

    md = [
        "# 8-Lane A-Only Candidate XDC",
        "",
        f"Generated: {generated}",
        "",
        "## Verdict",
        "",
        "- Overall: `CANDIDATE_A_ONLY_XDC_GENERATED_REVIEW_REQUIRED`",
        "- A-endpoint lane coverage: `8/8`",
        "- TFDU signal assignments: `32/32`",
        "- This is not real hardware acceptance and is not promoted to the active constraints.",
        "",
        "## Files",
        "",
        f"- XDC: `{rel(OUT_XDC)}`",
        f"- Source pinmap: `{rel(PINMAP_CSV)}`",
        f"- Active 2-lane XDC preserved separately: `{rel(PORT1_XDC)}`",
        "",
        "## Safety",
        "",
        "- No FPGA was programmed.",
        "- No UART was written.",
        "- No TFDU was driven.",
        "- The file excludes `loop_*` B-endpoint ports for `IR_B_MODE=external` builds.",
        "",
        "## Assignment Table",
        "",
        "| lane | signal | port | package_pin | board_signal | origin |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for item in assignments:
        md.append(f"| {item.lane} | {item.signal} | {item.port} | {item.package_pin} | {item.board_signal} | {item.origin} |")
    md.extend(
        [
            "",
            "RF_COMM_8LANE_A_ONLY_CANDIDATE_XDC overall=CANDIDATE_A_ONLY_XDC_GENERATED_REVIEW_REQUIRED assignments=32",
        ]
    )
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    payload = {
        "generated": generated,
        "overall": "CANDIDATE_A_ONLY_XDC_GENERATED_REVIEW_REQUIRED",
        "hard_constraint_sha256": sha256(find_hard_constraint()),
        "xdc": rel(OUT_XDC),
        "source_pinmap": rel(PINMAP_CSV),
        "assignment_count": len(assignments),
        "a_lanes": sorted({item.lane for item in assignments}),
        "excluded_b_endpoint": True,
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "assignments": [asdict(item) for item in assignments],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    generated = datetime.now().isoformat(timespec="seconds")
    assignments = load_assignments()
    validate(assignments)
    write_xdc(assignments, generated)
    write_reports(assignments, generated)
    print(f"WROTE_XDC={OUT_XDC}")
    print(f"WROTE_MARKDOWN={REPORTS / '8lane_a_only_candidate_xdc_current.md'}")
    print(f"WROTE_JSON={REPORTS / '8lane_a_only_candidate_xdc_current.json'}")
    print(f"WROTE_CSV={REPORTS / '8lane_a_only_candidate_xdc_current.csv'}")
    print("RF_COMM_8LANE_A_ONLY_CANDIDATE_XDC overall=CANDIDATE_A_ONLY_XDC_GENERATED_REVIEW_REQUIRED assignments=32")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
