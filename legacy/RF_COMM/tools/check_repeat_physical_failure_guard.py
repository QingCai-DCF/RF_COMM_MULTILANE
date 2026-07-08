#!/usr/bin/env python3
"""Guard against repeating the same physical-link hardware test without adjustment.

This is a read-only safety gate. It looks at recent 2-lane ILA matrix JSON
evidence and blocks real TFDU retests when the same required physical link has
already failed repeatedly with the same far-end RX-missing signature.
"""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from classify_2lane_physical_matrix import classify_one


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


@dataclass(frozen=True)
class GuardRow:
    link: str
    selected: bool
    latest_status: str
    latest_classification: str
    consecutive_same_failures: int
    threshold: int
    status: str
    evidence: str
    action: str


def rel(path: Path | str | None) -> str:
    if path is None:
        return ""
    p = Path(path)
    try:
        return str(p.resolve().relative_to(ROOT)).replace("\\", "/")
    except (OSError, ValueError):
        return str(path).replace("\\", "/")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_matrix_jsons(max_files: int) -> list[Path]:
    return sorted(
        REPORTS.glob("2lane_matrix_safe_*.ila_matrix.json"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )[:max_files]


def classify_items(path: Path) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(payload, list):
        return out
    for item in payload:
        if not isinstance(item, dict):
            continue
        row = classify_one(item)
        expected = str(row.get("expected", "")).upper()
        if expected:
            row["source_json"] = rel(path)
            out[expected] = row
    return out


def is_same_far_rx_missing(row: dict[str, Any]) -> bool:
    classification = str(row.get("classification", ""))
    tx = int(row.get("tx_pulses") or 0)
    rx = int(row.get("rx_pulses") or 0)
    near = int(row.get("near_rx_pulses") or 0)
    return classification == "FAIL_PHYSICAL_RX_MISSING" and tx > 0 and rx == 0 and near > 0


def load_selected_links(snapshot_path: Path, cli_links: list[str]) -> list[str]:
    if cli_links:
        return [link.strip().upper() for item in cli_links for link in item.split(",") if link.strip()]
    payload = read_json(snapshot_path)
    rows = payload.get("rows") if isinstance(payload, dict) else []
    links: list[str] = []
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            if str(row.get("status", "")) != "PASS":
                link = str(row.get("link", "")).upper()
                if link:
                    links.append(link)
    return links


def build_rows(snapshot_path: Path, selected_links: list[str], threshold: int, max_files: int) -> list[GuardRow]:
    matrix_paths = latest_matrix_jsons(max_files)
    classified_by_path = [(path, classify_items(path)) for path in matrix_paths]
    rows: list[GuardRow] = []

    for link in selected_links:
        consecutive = 0
        latest_status = "MISSING"
        latest_classification = "MISSING"
        evidence_parts: list[str] = []
        seen = False
        for path, classified in classified_by_path:
            row = classified.get(link)
            if row is None:
                continue
            seen = True
            classification = str(row.get("classification", ""))
            if latest_status == "MISSING":
                latest_classification = classification
                latest_status = "FAIL" if classification.startswith("FAIL") else "PASS" if classification.startswith("PASS") else "REVIEW"
            if is_same_far_rx_missing(row):
                consecutive += 1
                evidence_parts.append(
                    f"{rel(path)}:{classification}:tx={row.get('tx_pulses')}:rx={row.get('rx_pulses')}:near={row.get('near_rx_pulses')}"
                )
                continue
            break

        if not seen:
            rows.append(
                GuardRow(
                    link=link,
                    selected=True,
                    latest_status="MISSING",
                    latest_classification="MISSING",
                    consecutive_same_failures=0,
                    threshold=threshold,
                    status="PASS_NO_RECENT_EVIDENCE",
                    evidence="no recent matrix evidence for selected link",
                    action="Allow the safe wrapper to collect evidence.",
                )
            )
            continue

        blocked = consecutive >= threshold
        rows.append(
            GuardRow(
                link=link,
                selected=True,
                latest_status=latest_status,
                latest_classification=latest_classification,
                consecutive_same_failures=consecutive,
                threshold=threshold,
                status="BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT" if blocked else "PASS_RETEST_ALLOWED",
                evidence="; ".join(evidence_parts),
                action=(
                    "Declare a physical adjustment before repeating this real TFDU test: verify optical pairing/alignment, TFDU board orientation, and A-TX-to-B-RX lane mapping."
                    if blocked
                    else "Retest is allowed by the repeat-failure guard."
                ),
            )
        )
    return rows


def md_table(rows: list[GuardRow]) -> str:
    lines = [
        "| link | status | consecutive_same_failures | threshold | latest_classification | evidence | action |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.link,
                    row.status,
                    str(row.consecutive_same_failures),
                    str(row.threshold),
                    row.latest_classification,
                    row.evidence,
                    row.action,
                ]
            ).replace("|", "/")
            + " |"
        )
    return "\n".join(lines)


def write_outputs(rows: list[GuardRow], out_prefix: Path) -> tuple[Path, Path, Path, str]:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)
    generated = datetime.now().isoformat(timespec="seconds")
    failures = [row for row in rows if row.status.startswith("BLOCK_")]
    overall = "PASS_RETEST_ALLOWED" if not failures else "BLOCK_REPEAT_FAILURE_REQUIRES_PHYSICAL_ADJUSTMENT"
    md_path = out_prefix.with_suffix(".md")
    json_path = out_prefix.with_suffix(".json")
    csv_path = out_prefix.with_suffix(".csv")

    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(rows[0]).keys()) if rows else list(GuardRow.__dataclass_fields__.keys()))
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))

    payload = {
        "generated": generated,
        "overall": overall,
        "rows": [asdict(row) for row in rows],
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    md = [
        "# Repeat Physical Failure Guard",
        "",
        f"Generated: {generated}",
        "",
        f"- Overall: `{overall}`",
        f"- Selected links: `{len(rows)}`",
        f"- Blocked links: `{len(failures)}`",
        "- No hardware programming: `1`",
        "- No UART write: `1`",
        "- No TFDU drive: `1`",
        "",
        md_table(rows),
        "",
        "```text",
        f"RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall={overall} selected={len(rows)} blocked={len(failures)}",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        "```",
    ]
    md_path.write_text("\n".join(md) + "\n", encoding="utf-8")
    return md_path, json_path, csv_path, overall


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, default=REPORTS / "2lane_physical_failure_snapshot_current.json")
    parser.add_argument("--links", action="append", default=[])
    parser.add_argument("--threshold", type=int, default=3)
    parser.add_argument("--max-files", type=int, default=12)
    parser.add_argument("--out-prefix", type=Path, default=REPORTS / "repeat_physical_failure_guard_current")
    args = parser.parse_args()

    REPORTS.mkdir(parents=True, exist_ok=True)
    selected_links = load_selected_links(args.snapshot, args.links)
    rows = build_rows(args.snapshot, selected_links, args.threshold, args.max_files)
    md_path, json_path, csv_path, overall = write_outputs(rows, args.out_prefix)

    print(f"WROTE_MARKDOWN={md_path}")
    print(f"WROTE_JSON={json_path}")
    print(f"WROTE_CSV={csv_path}")
    print(f"RF_COMM_REPEAT_PHYSICAL_FAILURE_GUARD overall={overall} selected={len(rows)} blocked={len([r for r in rows if r.status.startswith('BLOCK_')])}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if overall == "PASS_RETEST_ALLOWED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
