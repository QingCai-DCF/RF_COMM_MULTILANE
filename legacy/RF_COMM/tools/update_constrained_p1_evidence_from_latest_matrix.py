from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EVIDENCE = ROOT / "evidence"

EXPECTED = {
    "A_TO_B_LANE0": "AB_L0",
    "B_TO_A_LANE0": "BA_L0",
    "A_TO_B_LANE1": "AB_L1",
    "B_TO_A_LANE1": "BA_L1",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(cell).replace("|", "/").replace("\n", " ") for cell in row) + " |")
    return "\n".join(lines)


def latest_complete_matrix_json() -> Path:
    for path in sorted(REPORTS.glob("2lane_matrix_safe_*.ila_matrix.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        found = {item.get("expected") for item in data if isinstance(item, dict)}
        if set(EXPECTED) <= found:
            return path
    raise FileNotFoundError("No complete 2lane ILA matrix JSON found")


def matching_summary(json_path: Path) -> Path | None:
    return json_path.with_name(json_path.name.replace(".ila_matrix.json", ".summary.txt"))


def matching_md(json_path: Path) -> Path | None:
    path = json_path.with_name(json_path.name.replace(".json", ".md"))
    return path if path.exists() else None


def classify(item: dict) -> tuple[str, dict]:
    expected = item["expected"]
    link = item.get("links", {}).get(expected, {})
    tx = int(link.get("tx_pulses") or 0)
    rx = int(link.get("rx_pulses") or 0)
    verdict = link.get("verdict") or item.get("verdict") or "UNKNOWN"
    if tx <= 0:
        status = "NO_TX_PULSE"
    elif rx <= 0:
        status = "NO_RX_RAW_PULSE"
    elif verdict == "PASS_RAW_PULSE" or item.get("verdict") == "PASS_EXPECTED_RAW":
        status = "PASS"
    else:
        status = str(verdict)
    return status, {
        "direction": EXPECTED[expected],
        "expected": expected,
        "trigger": item.get("trigger_mode", ""),
        "source_csv": Path(item.get("csv_path", "")) if item.get("csv_path") else None,
        "tx_pulses": tx,
        "rx_pulses": rx,
        "tx_edges": int(link.get("tx_edges") or 0),
        "rx_edges": int(link.get("rx_edges") or 0),
        "first_delay_samples": "" if link.get("first_delay_samples") is None else str(link.get("first_delay_samples")),
        "near_rx_pulses": int(link.get("near_rx_pulses") or 0),
        "verdict": status,
        "analyzer_verdict": item.get("verdict", ""),
        "reason": item.get("verdict_reason", ""),
    }


def build_rows(data: list[dict]) -> list[dict]:
    by_expected = {item.get("expected"): item for item in data if isinstance(item, dict)}
    rows: list[dict] = []
    for expected in ["A_TO_B_LANE0", "B_TO_A_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE1"]:
        if expected not in by_expected:
            raise KeyError(f"missing expected link {expected}")
        _status, row = classify(by_expected[expected])
        rows.append(row)
    return rows


def copy_csvs(rows: list[dict]) -> list[Path]:
    out_paths: list[Path] = []
    lane_dir = EVIDENCE / "lane_matrix"
    lane_dir.mkdir(parents=True, exist_ok=True)
    for row in rows:
        src = row["source_csv"]
        if src is None or not src.exists():
            continue
        dst = lane_dir / f"rxonly_{row['direction']}.csv"
        shutil.copy2(src, dst)
        row["evidence_csv"] = dst
        row["evidence_csv_sha256"] = sha256(dst)
        out_paths.append(dst)
    return out_paths


def write_rx_matrix(rows: list[dict], json_path: Path, md_path: Path | None, summary_path: Path | None) -> Path:
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    bad_dirs = [row["direction"] for row in rows if row["verdict"] != "PASS"]
    table_rows = []
    for row in rows:
        table_rows.append(
            [
                row["direction"],
                row["tx_pulses"],
                row["rx_pulses"],
                "N/A_RAW_ONLY",
                "N/A_RAW_ONLY",
                "N/A_RAW_ONLY",
                row["verdict"],
                rel(row.get("evidence_csv")),
                row["reason"],
            ]
        )
    out = EVIDENCE / "lane_matrix" / "rxonly_matrix.md"
    write_text(
        out,
        f"""# P1.1 RX-Only Raw-Pulse Matrix

Generated: {generated}

Status: `COMPLETE_WITH_BAD_DIR`

This is a raw-pulse physical matrix for the current constrained 2-lane static target. It proves pin-level pulse arrival only; it does not prove ACK, CRC, payload integrity, degraded-mode stability, Ethernet, or rotating operation.

## Source

- Analyzer report: `{rel(md_path)}`
- Analyzer JSON: `{rel(json_path)}`
- Matrix summary: `{rel(summary_path)}`

## Matrix

{md_table(["direction", "tx_pulse_seen", "rx_raw_pulse_seen", "preamble_seen", "crc_ok", "rx_good", "verdict", "evidence_csv", "reason"], table_rows)}

## Interpretation

- Complete directions captured: `AB_L0,BA_L0,AB_L1,BA_L1`
- Raw-pulse passing directions: `{",".join(row["direction"] for row in rows if row["verdict"] == "PASS")}`
- Raw-pulse failing directions: `{",".join(bad_dirs) if bad_dirs else "none"}`
- Current BAD_DIR at raw-pulse layer: `{",".join(bad_dirs) if bad_dirs else "none"}`

```text
RF_COMM_RXONLY_MATRIX status=COMPLETE_WITH_BAD_DIR
P1_MATRIX_COMPLETE=1
BAD_DIR_RAW_LAYER={",".join(bad_dirs) if bad_dirs else "none"}
AB_L0={next(row["verdict"] for row in rows if row["direction"] == "AB_L0")}
BA_L0={next(row["verdict"] for row in rows if row["direction"] == "BA_L0")}
AB_L1={next(row["verdict"] for row in rows if row["direction"] == "AB_L1")}
BA_L1={next(row["verdict"] for row in rows if row["direction"] == "BA_L1")}
ACK_HARDWARE_PASS=0
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
""",
    )
    return out


def write_csv_summary(rows: list[dict]) -> Path:
    out = EVIDENCE / "lane_matrix" / "rxonly_matrix.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "direction",
        "expected",
        "trigger",
        "tx_pulses",
        "rx_pulses",
        "tx_edges",
        "rx_edges",
        "first_delay_samples",
        "near_rx_pulses",
        "verdict",
        "analyzer_verdict",
        "reason",
        "evidence_csv",
        "evidence_csv_sha256",
    ]
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            payload = {field: row.get(field, "") for field in fields}
            payload["evidence_csv"] = rel(row.get("evidence_csv"))
            writer.writerow(payload)
    return out


def main() -> int:
    json_path = latest_complete_matrix_json()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    rows = build_rows(data)
    copied = copy_csvs(rows)
    md_path = matching_md(json_path)
    summary_path = matching_summary(json_path)
    rx_md = write_rx_matrix(rows, json_path, md_path, summary_path)
    rx_csv = write_csv_summary(rows)
    bad_dirs = [row["direction"] for row in rows if row["verdict"] != "PASS"]
    print(f"RF_COMM_UPDATE_CONSTRAINED_P1_EVIDENCE source={json_path}")
    print("P1_MATRIX_COMPLETE=1")
    print(f"BAD_DIR_RAW_LAYER={','.join(bad_dirs) if bad_dirs else 'none'}")
    print(f"WROTE={rx_md}")
    print(f"WROTE={rx_csv}")
    for path in copied:
        print(f"COPIED={path}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
