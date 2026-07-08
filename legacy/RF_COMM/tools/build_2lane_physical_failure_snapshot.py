#!/usr/bin/env python3
"""Build a current 2-lane physical-link failure snapshot.

This is an offline evidence reducer. It joins the latest ILA matrix CSV
evidence with the active PORT1.xdc pin map so G2 lane-mapping failures point to
the exact far-end RX package pins that need physical inspection.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from analyze_2lane_ila_csv import analyze_capture, to_jsonable
from classify_2lane_physical_matrix import classify_one


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
XDC = ROOT / "TFDU_VFIR_Client_Array/TFDU_VFIR_Client.srcs/constrs_1/new/PORT1.xdc"
REQUIRED_LINKS = ["A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1"]


@dataclass(frozen=True)
class EndpointPin:
    endpoint: str
    lane: int
    signal: str
    port: str
    package_pin: str
    connector: str
    board_side: str


@dataclass(frozen=True)
class LinkSnapshot:
    link: str
    status: str
    source: str
    lane: int
    tx_port: str
    tx_pin: str
    far_rx_port: str
    far_rx_pin: str
    near_rx_port: str
    near_rx_pin: str
    tx_pulses: int | None
    far_rx_pulses: int | None
    near_rx_pulses: int | None
    first_delay_samples: int | None
    first_near_delay_samples: int | None
    classification: str
    reason: str
    next_check: str
    cross_evidence: str
    evidence_csv: str
    evidence_json: str


def rel(path: Path | str | None) -> str:
    if path is None:
        return ""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(ROOT)).replace("\\", "/")
    except (ValueError, OSError):
        return str(path).replace("\\", "/")


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    return data.decode("utf-8", errors="replace")


def is_transient_file_lock(exc: OSError) -> bool:
    return isinstance(exc, PermissionError) or getattr(exc, "winerror", None) in (32, 33)


def write_text_with_retry(path: Path, text: str, encoding: str = "utf-8", max_wait_seconds: int = 120) -> None:
    start = time.monotonic()
    announced = False
    while True:
        try:
            path.write_text(text, encoding=encoding)
            if announced:
                elapsed = int(time.monotonic() - start)
                print(f"WAIT_FILE_CLEAR path={path} elapsed_s={elapsed}")
            return
        except OSError as exc:
            if not is_transient_file_lock(exc):
                raise
            elapsed = time.monotonic() - start
            if elapsed >= max_wait_seconds:
                print(f"WAIT_FILE_TIMEOUT path={path} elapsed_s={int(elapsed)} error={exc}")
                raise
            if not announced:
                print(f"WAIT_FILE_LOCK path={path} error={exc}")
                announced = True
            time.sleep(1)


def parse_xdc_pins(path: Path) -> dict[str, str]:
    text = read_text(path)
    pins: dict[str, str] = {}
    pattern = re.compile(r"set_property\s+PACKAGE_PIN\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]")
    for pin, port in pattern.findall(text):
        pins[port] = pin
    return pins


def endpoint_from_signal(signal: str, lane: int, pins: dict[str, str]) -> EndpointPin:
    if signal == "a_tx":
        endpoint, sig, port = "A", "TX", f"ir_tx_out_0[{lane}]"
    elif signal == "a_rx":
        endpoint, sig, port = "A", "RX", f"ir_rx_in_0[{lane}]"
    elif signal == "b_tx":
        endpoint, sig, port = "B", "TX", f"loop_tx_b0[{lane}]"
    elif signal == "b_rx":
        endpoint, sig, port = "B", "RX", f"loop_rx_b0[{lane}]"
    else:
        endpoint, sig, port = "?", signal.upper(), f"{signal}[{lane}]"

    connector = "J10" if lane == 0 else "J11" if lane == 1 else f"lane{lane}"
    if endpoint == "A":
        board_side = f"L{lane}-B"
    elif endpoint == "B":
        board_side = f"L{lane}-A"
    else:
        board_side = ""
    return EndpointPin(endpoint, lane, sig, port, pins.get(port, "MISSING"), connector, board_side)


def latest_matrix_jsons(max_files: int) -> list[Path]:
    return sorted(
        REPORTS.glob("2lane_matrix_safe_*.ila_matrix.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:max_files]


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def selected_latest_analyses(json_paths: list[Path]) -> list[tuple[Path, dict[str, Any], dict[str, Any]]]:
    by_link: dict[str, tuple[Path, dict[str, Any], dict[str, Any], float]] = {}
    for json_path in json_paths:
        payload = load_json(json_path)
        if not isinstance(payload, list):
            continue
        for item in payload:
            if not isinstance(item, dict):
                continue
            expected = str(item.get("expected", "")).upper()
            if expected not in REQUIRED_LINKS:
                continue
            csv_raw = item.get("csv_path")
            csv_path = Path(str(csv_raw)) if csv_raw else None
            if csv_path is not None and csv_path.exists():
                try:
                    refreshed = to_jsonable(analyze_capture(csv_path))
                except Exception:
                    refreshed = item
            else:
                refreshed = item
            classified = classify_one(refreshed)
            mtime = json_path.stat().st_mtime
            previous = by_link.get(expected)
            if previous is None or mtime > previous[3]:
                by_link[expected] = (json_path, refreshed, classified, mtime)
    return [(path, analysis, classified) for path, analysis, classified, _ in by_link.values()]


def next_check_for(classification: str, tx_pin: EndpointPin, far_rx_pin: EndpointPin, near_rx_pulses: int | None) -> str:
    if classification == "PASS_PHYSICAL_RAW_PULSE":
        return "No immediate physical check required for this link; keep it as a known-good reference."
    if classification == "FAIL_PHYSICAL_RX_MISSING" and (near_rx_pulses or 0) > 0:
        return (
            f"TX is active and near-end RX echo exists; inspect far-end RX path {far_rx_pin.connector} "
            f"{far_rx_pin.board_side} {far_rx_pin.port}/{far_rx_pin.package_pin}: TFDU RX wiring, optical alignment, "
            "receiver power, SD/MODE level, and continuity to the FPGA pin."
        )
    if classification == "FAIL_PHYSICAL_RX_MISSING":
        return (
            f"TX is active but no far-end RX was captured; inspect TX output {tx_pin.port}/{tx_pin.package_pin} "
            f"and far-end RX {far_rx_pin.port}/{far_rx_pin.package_pin}."
        )
    if classification == "FAIL_TEST_OR_TX_MISSING":
        return "The selected test did not exercise TX; verify trigger mode, PS ELF build, and ILA capture setup before changing wiring."
    if classification == "EVIDENCE_MISSING_REQUIRED_LINK":
        return "Capture this required link with the safe P1/2-lane matrix wrapper before making a hardware conclusion."
    return "Review the raw ILA CSV and analyzer output before changing hardware."


def resolve_json_paths(raw_paths: list[str]) -> list[Path]:
    paths: list[Path] = []
    for raw_group in raw_paths:
        for raw in re.split(r"[,;]", raw_group):
            item = raw.strip()
            if not item:
                continue
            path = Path(item)
            if not path.is_absolute():
                path = ROOT / path
            paths.append(path)
    return paths


def build_rows(max_json_files: int, json_paths: list[Path] | None = None) -> tuple[list[LinkSnapshot], list[str]]:
    pins = parse_xdc_pins(XDC)
    selected_paths = list(json_paths) if json_paths else latest_matrix_jsons(max_json_files)
    selected = selected_latest_analyses(selected_paths)
    by_link = {str(classified.get("expected", "")).upper(): (json_path, analysis, classified) for json_path, analysis, classified in selected}
    rows: list[LinkSnapshot] = []
    used_sources: list[str] = []

    for link_name in REQUIRED_LINKS:
        triple = by_link.get(link_name)
        if triple is None:
            rows.append(
                LinkSnapshot(
                    link=link_name,
                    status="MISSING_EVIDENCE",
                    source="",
                    lane=int(link_name[-1]),
                    tx_port="",
                    tx_pin="",
                    far_rx_port="",
                    far_rx_pin="",
                    near_rx_port="",
                    near_rx_pin="",
                    tx_pulses=None,
                    far_rx_pulses=None,
                    near_rx_pulses=None,
                    first_delay_samples=None,
                    first_near_delay_samples=None,
                    classification="EVIDENCE_MISSING_REQUIRED_LINK",
                    reason="required link is absent from the latest matrix evidence",
                    next_check="Capture this required link with the safe P1/2-lane matrix wrapper.",
                    cross_evidence="",
                    evidence_csv="",
                    evidence_json="",
                )
            )
            continue

        json_path, analysis, classified = triple
        used_sources.append(rel(json_path))
        links = analysis.get("links", {}) if isinstance(analysis.get("links"), dict) else {}
        link = links.get(link_name, {}) if isinstance(links.get(link_name), dict) else {}
        tx_signal = str(link.get("tx_signal", "") or "")
        rx_signal = str(link.get("rx_signal", "") or "")
        near_rx_signal = str(link.get("near_rx_signal", "") or "")
        tx_lane = int(link.get("tx_lane") if link.get("tx_lane") is not None else int(link_name[-1]))
        rx_lane = int(link.get("rx_lane") if link.get("rx_lane") is not None else int(link_name[-1]))
        near_rx_lane = int(link.get("near_rx_lane") if link.get("near_rx_lane") is not None else tx_lane)

        tx_pin = endpoint_from_signal(tx_signal, tx_lane, pins)
        far_rx_pin = endpoint_from_signal(rx_signal, rx_lane, pins)
        near_rx_pin = endpoint_from_signal(near_rx_signal, near_rx_lane, pins)
        classification = str(classified.get("classification", "UNKNOWN"))
        status = "PASS" if classification == "PASS_PHYSICAL_RAW_PULSE" else "FAIL" if classification.startswith("FAIL") else "REVIEW"
        near_rx_pulses = int(classified.get("near_rx_pulses") or link.get("near_rx_pulses") or 0)
        rows.append(
            LinkSnapshot(
                link=link_name,
                status=status,
                source=Path(str(analysis.get("csv_path", ""))).name,
                lane=tx_lane,
                tx_port=tx_pin.port,
                tx_pin=tx_pin.package_pin,
                far_rx_port=far_rx_pin.port,
                far_rx_pin=far_rx_pin.package_pin,
                near_rx_port=near_rx_pin.port,
                near_rx_pin=near_rx_pin.package_pin,
                tx_pulses=int(classified.get("tx_pulses") or 0),
                far_rx_pulses=int(classified.get("rx_pulses") or 0),
                near_rx_pulses=near_rx_pulses,
                first_delay_samples=link.get("first_delay_samples"),
                first_near_delay_samples=link.get("first_near_delay_samples"),
                classification=classification,
                reason=str(classified.get("reason", "")),
                next_check=next_check_for(classification, tx_pin, far_rx_pin, near_rx_pulses),
                cross_evidence="",
                evidence_csv=rel(str(analysis.get("csv_path", ""))),
                evidence_json=rel(json_path),
            )
        )
    if not used_sources:
        used_sources = [rel(path) for path in selected_paths]
    return attach_cross_evidence(rows), sorted(set(used_sources))


def attach_cross_evidence(rows: list[LinkSnapshot]) -> list[LinkSnapshot]:
    enriched: list[LinkSnapshot] = []
    for row in rows:
        notes: list[str] = []
        if row.status != "PASS" and row.far_rx_port:
            same_far_as_near = [
                other
                for other in rows
                if other.link != row.link
                and other.near_rx_port == row.far_rx_port
                and other.near_rx_pin == row.far_rx_pin
                and (other.near_rx_pulses or 0) > 0
            ]
            same_far_as_pass_rx = [
                other
                for other in rows
                if other.link != row.link
                and other.far_rx_port == row.far_rx_port
                and other.far_rx_pin == row.far_rx_pin
                and other.status == "PASS"
                and (other.far_rx_pulses or 0) > 0
            ]
            for other in same_far_as_near:
                notes.append(
                    f"{row.far_rx_port}/{row.far_rx_pin} observed {other.near_rx_pulses} near-echo pulses during {other.link}"
                )
            for other in same_far_as_pass_rx:
                notes.append(
                    f"{row.far_rx_port}/{row.far_rx_pin} observed {other.far_rx_pulses} far-end pulses during {other.link}"
                )
            if row.classification == "FAIL_PHYSICAL_RX_MISSING" and (row.near_rx_pulses or 0) > 0:
                notes.append(
                    f"{row.tx_port}/{row.tx_pin} is active and local echo on {row.near_rx_port}/{row.near_rx_pin} is present"
                )
        if notes:
            next_check = (
                row.next_check
                + " Cross-evidence narrows this away from a simple FPGA input-dead diagnosis; prioritize optical pairing/alignment, TFDU board orientation, and the actual A-TX-to-B-RX lane mapping."
            )
            enriched.append(replace(row, cross_evidence="; ".join(notes), next_check=next_check))
        else:
            enriched.append(row)
    return enriched


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join("" if item is None else str(item).replace("|", "/") for item in row) + " |")
    return "\n".join(out)


def write_outputs(rows: list[LinkSnapshot], sources: list[str]) -> None:
    generated = datetime.now().isoformat(timespec="seconds")
    failures = [row for row in rows if row.status != "PASS"]
    far_rx_missing_with_near_echo = [
        row for row in rows if row.classification == "FAIL_PHYSICAL_RX_MISSING" and (row.near_rx_pulses or 0) > 0
    ]
    missing_required = [row for row in rows if row.classification == "EVIDENCE_MISSING_REQUIRED_LINK"]
    if not failures:
        overall = "PASS_ALL_REQUIRED_LINKS"
    elif missing_required:
        overall = "BLOCK_REQUIRED_LINK_EVIDENCE_MISSING"
    else:
        overall = "BLOCK_FAR_END_RX_MISSING"

    json_path = REPORTS / "2lane_physical_failure_snapshot_current.json"
    md_path = REPORTS / "2lane_physical_failure_snapshot_current.md"
    csv_path = REPORTS / "2lane_physical_failure_snapshot_current.csv"

    payload = {
        "generated": generated,
        "overall": overall,
        "required_links": REQUIRED_LINKS,
        "failures": len(failures),
        "far_rx_missing_with_near_echo": len(far_rx_missing_with_near_echo),
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "xdc": rel(XDC),
        "sources": sources,
        "rows": [asdict(row) for row in rows],
    }
    write_text_with_retry(json_path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    csv_buffer = io.StringIO(newline="")
    writer = csv.DictWriter(csv_buffer, fieldnames=list(asdict(rows[0]).keys()))
    writer.writeheader()
    for row in rows:
        writer.writerow(asdict(row))
    write_text_with_retry(csv_path, csv_buffer.getvalue(), encoding="utf-8-sig")

    summary_rows = [
        [
            row.link,
            row.status,
            row.tx_port,
            row.tx_pin,
            row.far_rx_port,
            row.far_rx_pin,
            row.near_rx_port,
            row.near_rx_pin,
            row.tx_pulses,
            row.far_rx_pulses,
            row.near_rx_pulses,
            row.classification,
            row.cross_evidence,
        ]
        for row in rows
    ]
    check_rows = [
        [row.link, row.next_check, row.cross_evidence, row.evidence_csv]
        for row in rows
        if row.status != "PASS"
    ]
    md_lines = [
        "# 2-Lane Physical Failure Snapshot",
        "",
        f"Generated: {generated}",
        "",
        f"- Overall: `{overall}`",
        f"- Failures: `{len(failures)}`",
        f"- Far-end RX missing with near-end echo: `{len(far_rx_missing_with_near_echo)}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        f"- Active XDC: `{rel(XDC)}`",
        "",
        "## Link Summary",
        "",
        md_table(
            [
                "link",
                "status",
                "tx_port",
                "tx_pin",
                "far_rx_port",
                "far_rx_pin",
                "near_rx_port",
                "near_rx_pin",
                "tx_pulses",
                "far_rx_pulses",
                "near_rx_pulses",
                "classification",
                "cross_evidence",
            ],
            summary_rows,
        ),
        "",
        "## Next Checks",
        "",
        md_table(["link", "check", "cross_evidence", "evidence_csv"], check_rows),
        "",
        "## Sources",
        "",
        "\n".join(f"- `{source}`" for source in sources) or "-",
        "",
        "```text",
        f"RF_COMM_2LANE_PHYSICAL_FAILURE_SNAPSHOT overall={overall} failures={len(failures)} far_rx_missing_with_near_echo={len(far_rx_missing_with_near_echo)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "```",
    ]
    write_text_with_retry(md_path, "\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(
        "RF_COMM_2LANE_PHYSICAL_FAILURE_SNAPSHOT "
        f"overall={overall} failures={len(failures)} "
        f"far_rx_missing_with_near_echo={len(far_rx_missing_with_near_echo)}"
    )
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-json-files", type=int, default=16)
    parser.add_argument(
        "--json-paths",
        nargs="+",
        default=[],
        help="Explicit matrix JSON evidence to use instead of the latest files. Comma/semicolon separated values are accepted.",
    )
    args = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    explicit_json_paths = resolve_json_paths(args.json_paths)
    for path in explicit_json_paths:
        if not path.exists():
            raise SystemExit(f"JSON evidence path is missing: {path}")
    rows, sources = build_rows(args.max_json_files, explicit_json_paths or None)
    write_outputs(rows, sources)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
