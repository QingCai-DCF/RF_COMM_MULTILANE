#!/usr/bin/env python3
"""Generate evidence/config lock files for RF_COMM bring-up reports."""

from __future__ import annotations

import csv
import hashlib
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"

EVIDENCE_CSV = ROOT / "evidence_lock_20260625.csv"
DIFF_MD = ROOT / "config_diff_known_good_vs_current.md"

KEYVAL_RE = re.compile(r"([A-Za-z0-9_]+)=([^\s]+)")
DEFINE_RE = re.compile(r"-D([A-Za-z0-9_]+)=([^\s]+)")
TS_RE = re.compile(r"(20\d{6})(?:_(\d{4,6}))?")


CONFIG_FIELDS = [
    "CNT_CHIP_MAX",
    "CNT_PREAMBLE",
    "RX_DETECT_WINDOW",
    "RX_DATA_PHASE_DELAY_CYCLES",
    "RX_PREAMBLE_REALIGN_EDGE",
    "IR_LANE_COUNT",
    "IR_B_MODE",
    "IR_PARALLEL_2LANE_MODE",
    "B_SESSION_ID",
    "IR_B_TX_LANE_MASK",
    "IR_B_RX_LANE_MASK",
    "IR_B_ACK_LANE_MASK",
    "IR_B_EXPECTED_A_LANE_MASK",
    "MAX_PACKET_BYTES",
    "FRAGMENT_BYTES",
    "MAX_FRAGS",
    "MAX_FRAME_BYTES",
    "GUARD_CYCLES",
    "B_BACKOFF_SLOT_CYCLES",
    "B_START_IDLE_CYCLES",
    "B_RECOVERY_RESET_CYCLES",
    "B2A_ENABLE",
    "B2A_FREE_RUN",
    "TX_ONLY_ACK_MODE",
    "STREAM_FULL_MODE",
    "MAX_RETRY",
    "FRAG_TIMEOUT_CYCLES",
]

PS_FIELDS = [
    "PSPS_PAYLOAD_BYTES",
    "PSPS_TX_ONLY",
    "PSPS_TDM_BIDIR",
    "PSPS_RX_ONLY",
    "PSPS_INTER_PACKET_US",
    "PSPS_STAGE_SECONDS",
    "PSPS_MAX_OUTSTANDING",
    "PSPS_WINDOW_START_GAP_US",
    "PSPS_2LANE_ONLY",
    "PSPS_STAGE_LANE_MASK",
    "PSPS_STAGE_SESSION_ID",
    "PSPS_PAYLOAD_LANE_MASK",
    "PSPS_RX_LANE_MASK",
    "PSPS_POLL_SLEEP_US",
    "IR_TX_POLL_US",
]

METRIC_FIELDS = [
    "sent",
    "rx_ok",
    "tx_fail",
    "rx_timeout",
    "rx_bad",
    "rx_mismatch",
    "loss",
    "win_rx_mbps",
    "status",
    "sticky",
    "tx_lane",
    "rx_good",
    "rx_crc",
    "rx_err",
    "phy0",
    "rec",
    "txp",
    "txi",
    "txa",
    "rxb",
    "last_error",
]

RAW_FIELDS = [
    "raw_a_tx0_edges",
    "raw_a_tx1_edges",
    "raw_a_rx0_edges",
    "raw_a_rx1_edges",
    "raw_b_tx0_edges",
    "raw_b_tx1_edges",
    "raw_b_rx0_edges",
    "raw_b_rx1_edges",
    "raw_a_tx0_high",
    "raw_a_tx1_high",
    "raw_a_rx0_low",
    "raw_a_rx1_low",
    "raw_b_tx0_high",
    "raw_b_tx1_high",
    "raw_b_rx0_low",
    "raw_b_rx1_low",
]


def parse_name_ts(path: Path) -> datetime | None:
    match = TS_RE.search(path.name)
    if not match:
        return None
    date, time = match.groups()
    if not time:
        time = "000000"
    if len(time) == 4:
        time = f"{time}00"
    try:
        return datetime.strptime(f"{date}_{time}", "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def sha256_file(path: Path) -> str:
    if not path.exists():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text_any(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def parse_keyvals(text: str) -> dict[str, str]:
    return {k: v.rstrip(",;") for k, v in KEYVAL_RE.findall(text)}


def parse_hwloop_log(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    text = read_text_any(path)
    for line in text.splitlines():
        if "HWLOOP:" not in line:
            continue
        payload = line.split("HWLOOP:", 1)[1].strip()
        for key, value in parse_keyvals(payload).items():
            data[key] = value
    return data


def parse_vitis_log(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    text = read_text_any(path)
    for line in text.splitlines():
        if "Using compile flags:" in line:
            for key, value in DEFINE_RE.findall(line):
                data[key] = value.rstrip("uUL")
        elif line.startswith("Built ELF:"):
            data["built_elf"] = line.split(":", 1)[1].strip()
    return data


def nearest_prior(entries: list[dict], ts: datetime | None) -> dict | None:
    if not entries:
        return None
    entries = [entry for entry in entries if entry.get("data")] or entries
    if ts is None:
        return entries[-1]
    prior = [entry for entry in entries if entry.get("ts") and entry["ts"] <= ts]
    if prior:
        return prior[-1]
    return entries[0]


def normalize_abs_path(value: str) -> Path | None:
    if not value:
        return None
    p = Path(value)
    if not p.is_absolute():
        p = ROOT / value
    return p


def parse_int(value: str | None) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value, 0)
    except ValueError:
        return None


def parse_float(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value.rstrip("%"))
    except ValueError:
        return None


def infer_direction(run_id: str, trigger: str) -> str:
    name = run_id.lower()
    trig = trigger.lower()
    if "a_tx" in name or "a_tx" in trig:
        return "A_TO_B"
    if "b_tx" in name or "b_tx" in trig:
        return "B_TO_A"
    if "b_rx" in name or "b_rx" in trig:
        return "A_TO_B_RX_OBSERVE"
    if "lane0_hw_loopback" in name:
        return "A_TO_B_ACK_LOOP"
    if name.startswith("ila_"):
        return "RAW_ILA"
    return "UNKNOWN"


def analyze_ila_csv(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8", errors="ignore", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
            next(reader, None)
        except StopIteration:
            return {}

        index = {name: i for i, name in enumerate(header)}

        def find_col(token: str) -> int | None:
            matches = [i for name, i in index.items() if token in name]
            return matches[0] if matches else None

        cols = {
            "a_tx": find_col("ir_array_top_axi_0_ir_tx_out"),
            "a_rx": find_col("ir_rx_in_0_1"),
            "b_tx": find_col("ir_loopback_b0_ir_tx_out"),
            "b_rx": find_col("loop_rx_b0_1"),
        }
        values: dict[str, list[int]] = {name: [] for name in cols if cols[name] is not None}
        for row in reader:
            for name, col in cols.items():
                if col is None or col >= len(row):
                    continue
                raw = row[col].strip()
                if not raw:
                    continue
                try:
                    values[name].append(int(raw, 16))
                except ValueError:
                    try:
                        values[name].append(int(raw, 0))
                    except ValueError:
                        pass

    out: dict[str, str] = {}
    for sig_name, vec in values.items():
        for lane in (0, 1):
            bits = [(v >> lane) & 1 for v in vec]
            if not bits:
                continue
            edges = sum(1 for a, b in zip(bits, bits[1:]) if a != b)
            high = sum(bits)
            low = len(bits) - high
            out[f"raw_{sig_name}{lane}_edges"] = str(edges)
            if sig_name in ("a_rx", "b_rx"):
                out[f"raw_{sig_name}{lane}_low"] = str(low)
            else:
                out[f"raw_{sig_name}{lane}_high"] = str(high)
    return out


def parse_uart_header(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    text = read_text_any(path)
    out: dict[str, str] = {}
    for line in text.splitlines()[:80]:
        if line.startswith("mode="):
            for key, value in parse_keyvals(line).items():
                out[f"uart_{key}"] = value
        elif line.startswith("payload_bytes="):
            for key, value in parse_keyvals(line).items():
                out[f"uart_{key}"] = value
    return out


def parse_summary(path: Path, configs: list[dict], vitis_logs: list[dict]) -> dict[str, str]:
    text = read_text_any(path)
    lines = text.splitlines()
    run_id = path.name.replace(".summary.txt", "")
    ts = parse_name_ts(path)

    row: dict[str, str] = {
        "run_id": run_id,
        "date": ts.isoformat(sep=" ") if ts else "",
        "summary_path": str(path.relative_to(ROOT)),
    }

    top_kv: dict[str, str] = {}
    metric_candidates: list[str] = []
    stage_begins: list[str] = []
    for line in lines:
        if "=" in line and not line.startswith("UART_MATCH="):
            key, value = line.split("=", 1)
            top_kv[key.strip()] = value.strip()
        if line.startswith("UART_MATCH="):
            payload = line.split("=", 1)[1]
            if "PSPS_STAGE_BEGIN" in payload:
                stage_begins.append(payload)
            if "PSPS_STATS" in payload or "PSPS_STAGE_SUMMARY" in payload or "PSPS_TDM_STATS" in payload or "PSPS_TDM_STAGE_SUMMARY" in payload:
                metric_candidates.append(payload)

    row.update({k.lower(): v for k, v in top_kv.items() if k in ("UART_LOG", "ILA_CSV", "ILA_SUMMARY", "SHUTDOWN_LOG", "TRIGGER_MODE")})
    trigger = top_kv.get("TRIGGER_MODE", "")
    row["direction"] = infer_direction(run_id, trigger)

    if stage_begins:
        begin_kv = parse_keyvals(stage_begins[-1])
        row["stage"] = begin_kv.get("name", "")
        row["lane_mask"] = begin_kv.get("lane_mask", "")
        row["session"] = begin_kv.get("session", "")

    if metric_candidates:
        metric_line = next((m for m in reversed(metric_candidates) if "STAGE_SUMMARY" in m), metric_candidates[-1])
        metric = parse_keyvals(metric_line)
        row.update(metric)
        row["stage"] = metric.get("stage", row.get("stage", ""))
        row["lane_mask"] = metric.get("mask", row.get("lane_mask", ""))
    else:
        row.setdefault("stage", "")
        row.setdefault("lane_mask", "")
        row.setdefault("session", "")

    uart_path = normalize_abs_path(top_kv.get("UART_LOG", ""))
    row.update(parse_uart_header(uart_path))
    if not row.get("session") and uart_path and uart_path.exists():
        for line in read_text_any(uart_path).splitlines():
            if "PSPS_STAGE_BEGIN" in line:
                row.update({k if k != "lane_mask" else "lane_mask": v for k, v in parse_keyvals(line).items() if k in ("session", "lane_mask")})
                break

    ila_csv = normalize_abs_path(top_kv.get("ILA_CSV", ""))
    row.update(analyze_ila_csv(ila_csv))

    config = nearest_prior(configs, ts)
    if config:
        row["vivado_config_log"] = config["path"]
        for key in CONFIG_FIELDS:
            if key in config["data"]:
                row[key] = config["data"][key]

    vitis = nearest_prior(vitis_logs, ts)
    if vitis:
        row["vitis_build_log"] = vitis["path"]
        for key in PS_FIELDS:
            if key in vitis["data"]:
                row[key] = vitis["data"][key]

    shutdown_ok = (
        top_kv.get("SHUTDOWN_EXIT") == "0"
        or top_kv.get("SHUTDOWN_EXIT_INFERRED") == "0"
        or "SHUTDOWN_EXIT_INFERRED=0" in text
    )
    row["shutdown_ok"] = "1" if shutdown_ok else "0"

    sent = parse_int(row.get("sent"))
    rx_ok = parse_int(row.get("rx_ok"))
    tx_fail = parse_int(row.get("tx_fail"))
    loss = parse_float(row.get("loss"))
    last_error = row.get("last_error", "")
    if sent is not None:
        if sent >= 1000 and (tx_fail or 0) == 0 and (loss == 0.0 or (rx_ok is not None and rx_ok >= sent - 1)) and last_error in ("none", ""):
            verdict = "PASS"
        elif sent > 0 and ((tx_fail or 0) > 0 or (loss is not None and loss >= 99.0) or last_error not in ("none", "")):
            verdict = "FAIL"
        else:
            verdict = "INCONCLUSIVE"
    elif "ILA2_CAPTURE_DONE" in text:
        verdict = "RAW_CAPTURE"
    else:
        verdict = "INCONCLUSIVE"
    row["verdict"] = verdict
    return row


def collect_logs(patterns: list[str], parser) -> list[dict]:
    entries = []
    for pattern in patterns:
        for path in REPORTS.glob(pattern):
            ts = parse_name_ts(path)
            entries.append(
                {
                    "path": str(path.relative_to(ROOT)),
                    "ts": ts,
                    "data": parser(path),
                }
            )
    entries.sort(key=lambda item: item["ts"] or datetime.min)
    return entries


def current_hashes_for(row: dict[str, str], latest_hash_run_ids: set[str]) -> dict[str, str]:
    if row["run_id"] not in latest_hash_run_ids:
        marker = "UNKNOWN_MUTABLE_ARTIFACT"
        return {
            "bit_sha256": marker,
            "ltx_sha256": marker,
            "xsa_sha256": marker,
            "elf_sha256": marker,
        }
    paths = {
        "bit_sha256": ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1" / "design_shiboqi_wrapper.bit",
        "ltx_sha256": ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.runs" / "impl_1" / "design_shiboqi_wrapper.ltx",
        "xsa_sha256": ROOT / "TFDU_VFIR_Client_Array" / "design_shiboqi_wrapper.xsa",
        "elf_sha256": ROOT / "software" / "_vitis_ws_ps_ps_loopback" / "rf_comm_ps_ps_loopback" / "Debug" / "rf_comm_ps_ps_loopback.elf",
    }
    hashes = {key: sha256_file(path) for key, path in paths.items()}
    if hashes["bit_sha256"] == "MISSING":
        hashes["bit_sha256"] = sha256_file(ROOT / "TFDU_VFIR_Client_Array" / "design_shiboqi_wrapper.bit")
    return hashes


def write_csv(rows: list[dict[str, str]]) -> None:
    columns = [
        "run_id",
        "date",
        "stage",
        "direction",
        "lane_mask",
        "session",
        "bit_sha256",
        "ltx_sha256",
        "xsa_sha256",
        "elf_sha256",
        *CONFIG_FIELDS,
        *PS_FIELDS,
        "uart_mode",
        "uart_payload_bytes",
        "uart_rx_timeout_us",
        "uart_stage_seconds",
        *METRIC_FIELDS,
        *RAW_FIELDS,
        "shutdown_ok",
        "uart_log",
        "ila_csv",
        "ila_summary",
        "vivado_config_log",
        "vitis_build_log",
        "summary_path",
        "verdict",
    ]
    hw_rows = [row for row in rows if row.get("date") and row.get("uart_log")]
    latest_hash_run_ids: set[str] = set()
    if hw_rows:
        latest_date = max(row["date"] for row in hw_rows)
        latest_stamp = ""
        latest_rows = [row for row in hw_rows if row["date"] == latest_date]
        if latest_rows:
            match = TS_RE.search(latest_rows[0]["run_id"])
            if match:
                latest_stamp = "_".join(part for part in match.groups() if part)
        latest_hash_run_ids = {row["run_id"] for row in latest_rows}
        if latest_stamp:
            latest_hash_run_ids.update(
                row["run_id"] for row in rows if latest_stamp in row["run_id"]
            )
    for row in rows:
        row.update(current_hashes_for(row, latest_hash_run_ids))
    with EVIDENCE_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})


def select_row(rows: list[dict[str, str]], run_id: str) -> dict[str, str]:
    for row in rows:
        if row["run_id"] == run_id:
            return row
    return {"run_id": run_id, "verdict": "MISSING"}


def select_latest(rows: list[dict[str, str]], predicate) -> dict[str, str]:
    matches = [row for row in rows if predicate(row)]
    if not matches:
        return {"run_id": "MISSING", "verdict": "MISSING"}
    return sorted(matches, key=lambda row: row.get("date", ""))[-1]


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def compact_value(row: dict[str, str], key: str) -> str:
    value = row.get(key, "")
    return value if value != "" else "UNKNOWN"


def write_diff(rows: list[dict[str, str]]) -> None:
    known_lane0 = select_row(rows, "lane0_hw_loopback_safe_20260605_115655")
    known_2lane = select_row(rows, "2lane_prearmed_b_tx_nonzero_20260606_103701")
    current_lane0 = select_row(rows, "lane0_hw_loopback_safe_20260625_161733")
    current_pin33 = select_row(rows, "2lane_prearmed_a_tx_lane1_20260625_225024")
    p0_lane0 = select_latest(
        rows,
        lambda row: row.get("run_id", "").startswith("lane0_hw_loopback_safe_20260625")
        and row.get("session") == "0x2201"
        and row.get("verdict") == "PASS",
    )

    comparison_keys = [
        "CNT_CHIP_MAX",
        "CNT_PREAMBLE",
        "RX_DETECT_WINDOW",
        "RX_DATA_PHASE_DELAY_CYCLES",
        "IR_LANE_COUNT",
        "IR_B_MODE",
        "IR_PARALLEL_2LANE_MODE",
        "B_SESSION_ID",
        "IR_B_TX_LANE_MASK",
        "IR_B_RX_LANE_MASK",
        "IR_B_ACK_LANE_MASK",
        "IR_B_EXPECTED_A_LANE_MASK",
        "B_BACKOFF_SLOT_CYCLES",
        "B_START_IDLE_CYCLES",
        "B2A_ENABLE",
        "B2A_FREE_RUN",
        "FRAGMENT_BYTES",
        "MAX_PACKET_BYTES",
        "PSPS_STAGE_LANE_MASK",
        "PSPS_STAGE_SESSION_ID",
        "PSPS_PAYLOAD_LANE_MASK",
        "PSPS_RX_LANE_MASK",
        "uart_payload_bytes",
        "uart_stage_seconds",
    ]

    def metric_row(label: str, row: dict[str, str]) -> list[str]:
        return [
            label,
            compact_value(row, "run_id"),
            compact_value(row, "direction"),
            compact_value(row, "lane_mask"),
            compact_value(row, "session"),
            compact_value(row, "sent"),
            compact_value(row, "rx_ok"),
            compact_value(row, "tx_fail"),
            compact_value(row, "loss"),
            compact_value(row, "last_error"),
            compact_value(row, "verdict"),
        ]

    def raw_row(label: str, row: dict[str, str]) -> list[str]:
        return [
            label,
            compact_value(row, "raw_a_tx0_edges"),
            compact_value(row, "raw_a_tx1_edges"),
            compact_value(row, "raw_b_rx0_edges"),
            compact_value(row, "raw_b_rx1_edges"),
            compact_value(row, "raw_b_tx0_edges"),
            compact_value(row, "raw_b_tx1_edges"),
            compact_value(row, "raw_a_rx0_edges"),
            compact_value(row, "raw_a_rx1_edges"),
        ]

    config_rows = []
    for key in comparison_keys:
        config_rows.append(
            [
                key,
                compact_value(known_lane0, key),
                compact_value(known_2lane, key),
                compact_value(current_lane0, key),
                compact_value(current_pin33, key),
            ]
        )

    pass_count = sum(1 for row in rows if row.get("verdict") == "PASS")
    fail_count = sum(1 for row in rows if row.get("verdict") == "FAIL")
    raw_count = sum(1 for row in rows if row.get("verdict") == "RAW_CAPTURE")

    content = f"""# RF_COMM evidence/config diff 2026-06-25

Generated by `tools/generate_evidence_lock.py`.

## Scope

- Evidence CSV: `evidence_lock_20260625.csv`
- Parsed hardware summaries: {len(rows)}
- PASS rows: {pass_count}
- FAIL rows: {fail_count}
- RAW_CAPTURE rows: {raw_count}

Historical bit/ELF files were mostly mutable Vivado/Vitis output paths and were not frozen per run. Artifact hash columns are therefore marked `UNKNOWN_MUTABLE_ARTIFACT` except for the latest hardware run at generation time, where the current mutable paths still correspond to the run just executed.

Vivado/Vitis config association is based on the nearest parsed prior log timestamp. Logs that only contain a date but no time are useful for recipe recovery but should be treated as lower-confidence than timestamped logs.

## Selected run result comparison

{md_table(
    ["case", "run_id", "direction", "lane_mask", "session", "sent", "rx_ok", "tx_fail", "loss", "last_error", "verdict"],
    [
        metric_row("known-good lane0", known_lane0),
        metric_row("known-good 2lane", known_2lane),
        metric_row("current lane0 fail", current_lane0),
        metric_row("current PIN33 lane1 fail", current_pin33),
        metric_row("P0 replay lane0", p0_lane0),
    ],
)}

## Selected raw ILA comparison

{md_table(
    ["case", "A_TX0_edges", "A_TX1_edges", "B_RX0_edges", "B_RX1_edges", "B_TX0_edges", "B_TX1_edges", "A_RX0_edges", "A_RX1_edges"],
    [
        raw_row("known-good 2lane", known_2lane),
        raw_row("current PIN33 lane1", current_pin33),
    ],
)}

## Config field comparison

{md_table(
    ["field", "known lane0", "known 2lane", "current lane0", "current PIN33 lane1"],
    config_rows,
)}

## Immediate interpretation

1. The 2026-06-05 lane0 record remains a strong known-good baseline: `loss=0.0%`, `tx_fail=0`, and UART shows `payload_bytes=247` at about `2.8 Mbps` payload receive rate.
2. The 2026-06-06 2-lane record is also a valid baseline for multi-lane/TDM behavior: `tx_fail=0`, `loss=0.0%`, and `PSPS_TDM_STAGE_SUMMARY` reaches `sent=2733`, `rx_ok=2733`.
3. The current 2026-06-25 lane0 and PIN33 lane1 records fail at protocol level (`rx_ok=0`, `loss=100%`, `last_error=tx_retry_exhausted` or `tx_done_timeout`).
4. The current PIN33 lane1 ILA record shows A side TX activity but no B_RX1 edge after moving B_RX1 to J11-PIN33/G15. That makes a single bad original D19 FPGA pin less likely and keeps the B-side physical receive chain/mapping/alignment high on the suspect list.
5. The current lane0 failure is especially suspicious because UART reports `lane_mask=0x00000001` with `session=0x2203`, while the associated B-side config expects the 2-lane mask `3`. That is a concrete session/mask mismatch candidate.
6. The P0 lane0 replay proves the current hardware/JTAG/UART environment can still reproduce the single-lane known-good path when lane mask/session and B endpoint mode are restored.
7. The current failing configs differ materially from the known-good configs in speed timing, parallel-lane mode, B TX/ACK lane enable, start/backoff timing, and lane/session/mask assumptions. These variables should be replayed one at a time.

## Known-good replay recipe candidates

### Lane0 single-lane replay

- `IR_LANE_COUNT=1`
- `IR_B_MODE=sink` for the selected known-good 2.8 Mbps tx-only half-duplex run, or replay the exact historical stream build only if its config log is explicitly selected
- `CNT_CHIP_MAX=7`
- `CNT_PREAMBLE=64`
- `lane_mask=0x00000001`
- `session=0x2201`
- `payload_bytes=247`
- target pass gate: `sent >= 1000`, `rx_ok == sent`, `tx_fail = 0`, `loss = 0.0%`

### 2-lane replay

- `IR_LANE_COUNT=2`
- `B_SESSION_ID=0x2203`
- `B_RX_LANE_MASK=3`
- `B_EXPECTED_A_LANE_MASK=3`
- `B_TX_LANE_MASK`/`B_ACK_LANE_MASK` non-zero for ACK-capable closed-loop testing
- target pass gate: `sent >= 1000`, `loss = 0.0%`, `tx_fail = 0`

## Evidence gaps to close next

1. Freeze bit/LTX/XSA/ELF into per-run artifact copies or hash logs before each hardware run.
2. Add B-side RX microscope probes so `rx_good=0` can be classified as PHY, CRC/frame, session/mask, payload, or ACK-gate failure.
3. Before protocol debugging on lane1, repeat a raw physical pulse matrix because latest B_RX1 stayed idle even after remapping to PIN33/G15.
"""
    DIFF_MD.write_text(content, encoding="utf-8")


def main() -> None:
    configs = collect_logs(["vivado_config*.log", "vivado_configure*.log"], parse_hwloop_log)
    vitis = collect_logs(["vitis_build*.log"], parse_vitis_log)

    summaries = [
        path
        for path in REPORTS.glob("*.summary.txt")
        if re.search(r"202606(05|06|25)", path.name)
    ]
    rows = [parse_summary(path, configs, vitis) for path in sorted(summaries)]
    rows.sort(key=lambda row: row.get("date", ""))
    write_csv(rows)
    write_diff(rows)
    print(f"Wrote {EVIDENCE_CSV}")
    print(f"Wrote {DIFF_MD}")
    print(f"Rows: {len(rows)}")


if __name__ == "__main__":
    main()
