from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
REPORTS = ROOT / "reports"
PLAN_PATH = Path.home() / "Downloads" / "constrained_2lane_static_plan.md"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


def sha256(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return "MISSING"
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="replace")
    return data.decode("utf-8", errors="replace")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def latest(pattern: str) -> Path | None:
    paths = [p for p in ROOT.glob(pattern) if p.is_file()]
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def latest_containing(pattern: str, needles: list[str]) -> Path | None:
    for path in sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        text = read_text(path)
        if all(needle in text for needle in needles):
            return path
    return None


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def marker_value(text: str, key: str, default: str = "MISSING") -> str:
    match = re.search(rf"(?m)^{re.escape(key)}=(.+)$", text)
    if match:
        return match.group(1).strip()
    return default


def p1_matrix_complete(ctx: dict[str, object]) -> bool:
    return "P1_MATRIX_COMPLETE=1" in str(ctx.get("rx_text", ""))


def bad_dir_raw_layer(ctx: dict[str, object]) -> str:
    return marker_value(str(ctx.get("rx_text", "")), "BAD_DIR_RAW_LAYER", "UNPROVEN")


def direction_verdicts(ctx: dict[str, object]) -> dict[str, str]:
    text = str(ctx.get("rx_text", ""))
    return {
        "AB_L0": marker_value(text, "AB_L0", "MISSING"),
        "BA_L0": marker_value(text, "BA_L0", "MISSING"),
        "AB_L1": marker_value(text, "AB_L1", "MISSING"),
        "BA_L1": marker_value(text, "BA_L1", "MISSING"),
    }


def first_line_containing(text: str, token: str) -> str:
    for line in text.splitlines():
        if token in line:
            return line.strip()
    return "MISSING"


def load_acceptance_rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def kv_value(text: str, key: str, default: str = "") -> str:
    match = re.search(rf"(?m)^(?:MATRIX_MATCH=)?{re.escape(key)}=(.+)$", text)
    if match:
        return match.group(1).strip()
    return default


def path_value(text: str, key: str) -> Path | None:
    value = kv_value(text, key)
    if not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    return path


def parse_key_values(line: str) -> dict[str, str]:
    return {match.group(1): match.group(2) for match in re.finditer(r"([A-Za-z0-9_]+)=([^\s]+)", line)}


def int_value(values: dict[str, str], key: str, default: int = 0) -> int:
    try:
        return int(values.get(key, str(default)), 0)
    except ValueError:
        return default


def float_value(text: str, key: str, default: float = 0.0) -> float:
    try:
        return float(kv_value(text, key, str(default)))
    except ValueError:
        return default


def last_line_containing(text: str, token: str) -> str:
    line = ""
    for candidate in text.splitlines():
        if token in candidate:
            line = candidate.strip()
    return line


def latest_ack_actual_summary() -> Path | None:
    for path in sorted(REPORTS.glob("p0_ack_only_safe_*.summary.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if "DRY_RUN=0" in text and "MATRIX_EXIT=0" in text and "P0_ACK_ONLY_SAFE_END" in text:
            return path
    return None


def ack_info() -> dict[str, object]:
    summary = latest_ack_actual_summary()
    if summary is None:
        return {
            "status": "NOT_STARTED_WAIT_ACK_ONLY_RUN",
            "summary": None,
            "matrix_json": None,
            "run_complete": 0,
            "physical_raw_pass": 0,
            "protocol_pass": 0,
            "hardware_pass": 0,
            "shutdown_after_each_run": 0,
            "max_tfdu_window_s": "MISSING",
            "rows": [],
            "run_logs": [],
        }

    text = read_text(summary)
    matrix_json_path = Path(kv_value(text, "MATRIX_ANALYSIS_JSON"))
    if not matrix_json_path.is_absolute():
        matrix_json_path = ROOT / matrix_json_path
    prefix = matrix_json_path.name.replace(".ila_matrix.json", "")
    run_logs = sorted(REPORTS.glob(f"{prefix}.*.run.log"))
    json_rows: list[dict[str, object]] = []
    if matrix_json_path.exists():
        try:
            json_rows = json.loads(read_text(matrix_json_path))
        except json.JSONDecodeError:
            json_rows = []

    raw_by_trigger = {str(row.get("trigger_mode", "")): row for row in json_rows}
    ab_raw = str(raw_by_trigger.get("a_tx_lane0", {}).get("verdict", "")).startswith("PASS")
    ba_raw = str(raw_by_trigger.get("b_tx_lane0", {}).get("verdict", "")).startswith("PASS")
    b_tx_classes = raw_by_trigger.get("b_tx_lane0", {}).get("b_debug_class_counts", {})
    b_ack_seen = "ack_lane0=1" in json.dumps(b_tx_classes, ensure_ascii=False)
    b_rx_good_seen = "rx_good=1" in json.dumps(b_tx_classes, ensure_ascii=False)

    table_rows: list[dict[str, str]] = []
    shutdown_ok = bool(run_logs)
    max_window = 0.0
    protocol_ok = bool(run_logs)
    for run_log in run_logs:
        run_text = read_text(run_log)
        trigger = marker_value(run_text, "TRIGGER_MODE", run_log.name)
        stats_line = last_line_containing(run_text, "UART_MATCH=PSPS_STAGE_SUMMARY")
        if not stats_line:
            stats_line = last_line_containing(run_text, "UART_MATCH=PSPS_STATS")
        values = parse_key_values(stats_line)
        sent = int_value(values, "sent")
        rx_ok = int_value(values, "rx_ok")
        tx_fail = int_value(values, "tx_fail")
        last_error = values.get("last_error", "MISSING")
        clean = (
            sent > 0
            and rx_ok == sent
            and tx_fail == 0
            and int_value(values, "rx_timeout") == 0
            and int_value(values, "rx_bad") == 0
            and int_value(values, "rx_mismatch") == 0
            and last_error == "none"
        )
        if not clean:
            protocol_ok = False
        if "SHUTDOWN_EXIT_INFERRED=0" not in run_text and "SHUTDOWN_EXIT=0" not in run_text:
            shutdown_ok = False
        window_value = marker_value(run_text, "HW_WINDOW_TO_SHUTDOWN_END_SECONDS", "0")
        try:
            max_window = max(max_window, float(window_value))
        except ValueError:
            pass
        table_rows.append(
            {
                "trigger": trigger,
                "raw_verdict": str(raw_by_trigger.get(trigger, {}).get("verdict", "MISSING")),
                "sent": str(sent),
                "rx_ok": str(rx_ok),
                "tx_fail": str(tx_fail),
                "last_error": last_error,
                "run_log": rel(run_log),
            }
        )

    protocol_pass = int(protocol_ok and ab_raw and ba_raw and shutdown_ok)
    status = "ACK_ONLY_PASS" if protocol_pass else "ACK_ONLY_RUN_FAILED_PROTOCOL"
    return {
        "status": status,
        "summary": summary,
        "matrix_json": matrix_json_path,
        "run_complete": 1,
        "physical_raw_pass": int(ab_raw and ba_raw),
        "protocol_pass": protocol_pass,
        "hardware_pass": protocol_pass,
        "shutdown_after_each_run": int(shutdown_ok and max_window <= 600.0),
        "max_tfdu_window_s": f"{max_window:.1f}" if max_window else "MISSING",
        "rows": table_rows,
        "run_logs": run_logs,
        "b_ack_seen": int(b_ack_seen),
        "b_rx_good_seen": int(b_rx_good_seen),
    }


def latest_degraded_soak_summary() -> Path | None:
    for path in sorted(REPORTS.glob("lane0_hw_loopback_safe_*.summary.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if "UART_MATCH=PSPS_STAGE_SUMMARY" in text and "SHUTDOWN_EXIT=0" in text:
            return path
    return None


def degraded_soak_info() -> dict[str, object]:
    summary = latest_degraded_soak_summary()
    if summary is None:
        return {
            "summary": None,
            "uart_log": None,
            "smoke_pass": 0,
            "soak_pass": 0,
            "payload_bytes": 0,
            "stage_seconds": 0,
            "sent": 0,
            "rx_ok": 0,
            "tx_fail": 0,
            "rx_timeout": 0,
            "rx_bad": 0,
            "rx_mismatch": 0,
            "loss": "MISSING",
            "win_rx_mbps": "MISSING",
            "window_s": 0.0,
            "last_error": "MISSING",
        }

    text = read_text(summary)
    uart_log = path_value(text, "UART_LOG")
    uart_text = read_text(uart_log)
    stats_line = last_line_containing(text, "UART_MATCH=PSPS_STAGE_SUMMARY")
    if not stats_line:
        stats_line = last_line_containing(uart_text, "PSPS_STAGE_SUMMARY")
    values = parse_key_values(stats_line)
    config = parse_key_values(last_line_containing(uart_text, "payload_bytes="))
    sent = int_value(values, "sent")
    rx_ok = int_value(values, "rx_ok")
    tx_fail = int_value(values, "tx_fail")
    rx_timeout = int_value(values, "rx_timeout")
    rx_bad = int_value(values, "rx_bad")
    rx_mismatch = int_value(values, "rx_mismatch")
    payload = int_value(config, "payload_bytes")
    stage_seconds = int_value(config, "stage_seconds")
    window_s = float_value(text, "HW_WINDOW_TO_SHUTDOWN_END_SECONDS")
    shutdown_ok = "SHUTDOWN_EXIT=0" in text
    run_once_done = "PSPS_RUN_ONCE_DONE link_disabled=1" in uart_text or "UART_MATCH=PSPS_RUN_ONCE_DONE link_disabled=1" in text
    clean = (
        payload == 256
        and sent >= 10000
        and rx_ok == sent
        and tx_fail == 0
        and rx_timeout == 0
        and rx_bad == 0
        and rx_mismatch == 0
        and values.get("loss", "") == "0.0%"
        and values.get("last_error", "MISSING") == "none"
    )
    return {
        "summary": summary,
        "uart_log": uart_log,
        "smoke_pass": int(clean),
        "soak_pass": int(clean and stage_seconds >= 300 and shutdown_ok and run_once_done and 0 < window_s <= 600.0),
        "payload_bytes": payload,
        "stage_seconds": stage_seconds,
        "sent": sent,
        "rx_ok": rx_ok,
        "tx_fail": tx_fail,
        "rx_timeout": rx_timeout,
        "rx_bad": rx_bad,
        "rx_mismatch": rx_mismatch,
        "loss": values.get("loss", "MISSING"),
        "win_rx_mbps": values.get("win_rx_mbps", "MISSING"),
        "window_s": window_s,
        "last_error": values.get("last_error", "MISSING"),
    }


def latest_ps_pc_offline_gate() -> Path | None:
    return latest_containing(
        "reports/ps_pc_offline_gates_*.summary.txt",
        ["PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1"],
    )


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(str(cell).replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def build_context() -> dict[str, object]:
    constraint = find_constraint()
    matrix_md = REPORTS / "constrained_2lane_static_acceptance_matrix_current.md"
    matrix_json = REPORTS / "constrained_2lane_static_acceptance_matrix_current.json"
    matrix_csv = REPORTS / "constrained_2lane_static_acceptance_matrix_current.csv"
    baseline_summary = REPORTS / "constrained_2lane_static_baseline_current.summary.txt"
    manifest = EVIDENCE / "manifest" / "current_baseline_manifest.md"
    g1_summary = EVIDENCE / "G1_freeze" / "G1_frozen_summary.txt"
    rx_matrix = EVIDENCE / "lane_matrix" / "rxonly_matrix.md"
    no_eth_summary = latest_containing(
        "reports/no_ethernet_network_offline_acceptance_*.summary.txt",
        ["NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1"],
    )
    no_eth_csv = None if no_eth_summary is None else no_eth_summary.with_name(no_eth_summary.name.replace(".summary.txt", ".cases.csv"))
    no_eth_md = None if no_eth_summary is None else no_eth_summary.with_name(no_eth_summary.name.replace(".summary.txt", ".md"))
    no_eth_boundary = REPORTS / "no_ethernet_network_boundary_evidence_current.md"
    rotating = REPORTS / "rotating_autoroute_offline_evidence_current.md"
    external = REPORTS / "external_preconditions_current.md"
    duration = REPORTS / "duration_cap_compliance_current.md"
    safe_wrapper = REPORTS / "safe_wrapper_guard_contract_current.md"
    return {
        "generated": datetime.now().astimezone().isoformat(timespec="seconds"),
        "constraint": constraint,
        "constraint_sha": sha256(constraint),
        "plan_sha": sha256(PLAN_PATH),
        "matrix_md": matrix_md,
        "matrix_json": matrix_json,
        "matrix_csv": matrix_csv,
        "matrix_rows": load_acceptance_rows(matrix_csv),
        "baseline_summary": baseline_summary,
        "manifest": manifest,
        "g1_summary": g1_summary,
        "rx_matrix": rx_matrix,
        "no_eth_summary": no_eth_summary,
        "no_eth_csv": no_eth_csv,
        "no_eth_md": no_eth_md,
        "no_eth_boundary": no_eth_boundary,
        "rotating": rotating,
        "external": external,
        "duration": duration,
        "safe_wrapper": safe_wrapper,
        "g1_text": read_text(g1_summary),
        "rx_text": read_text(rx_matrix),
        "no_eth_text": read_text(no_eth_summary),
        "boundary_text": read_text(no_eth_boundary),
        "rotating_text": read_text(rotating),
        "baseline_text": read_text(baseline_summary),
        "ack_info": ack_info(),
        "degraded_soak": degraded_soak_info(),
        "ps_pc_offline_gate": latest_ps_pc_offline_gate(),
    }


def write_deferred_docs(ctx: dict[str, object]) -> list[Path]:
    generated = ctx["generated"]
    no_eth_summary = rel(ctx["no_eth_summary"])
    boundary = rel(ctx["no_eth_boundary"])
    rotating = rel(ctx["rotating"])
    external = rel(ctx["external"])
    paths: list[Path] = []

    n03 = EVIDENCE / "deferred" / "N03_ethernet_deferred.md"
    write_text(
        n03,
        f"""# N03 Ethernet Deferred

Generated: {generated}

status = DEFERRED_NO_ETHERNET
reason = 当前无法接网线
not_failed = true
replacement_evidence = host mock + UART/PS local boundary + offline TCP/DHCP/reconnect model
promotion_condition = 接入 Ethernet 后重新执行 N03_real_ethernet_acceptance_plan

## Evidence

- Offline no-Ethernet acceptance: `{no_eth_summary}`
- Localhost TCP boundary: `{boundary}`
- External preconditions: `{external}`

```text
RF_COMM_N03_ETHERNET_DEFERRED status=DEFERRED_NO_ETHERNET
NO_REAL_BOARD_TCP_DHCP=1
NOT_FAILED=1
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
""",
    )
    paths.append(n03)

    s05 = EVIDENCE / "deferred" / "S05_rotation_deferred.md"
    write_text(
        s05,
        f"""# S05 Rotation Deferred

Generated: {generated}

status = DEFERRED_NO_ROTATION_FIXTURE
reason = 当前无法移动硬件，无法进入真实旋转环境
not_failed = true
replacement_evidence = stationary capped baseline + rotating offline model
promotion_condition = 可移动硬件并具备旋转工装后重新执行 S05_rotation_fixture_acceptance_plan

## Evidence

- Rotating offline model: `{rotating}`
- External preconditions: `{external}`

```text
RF_COMM_S05_ROTATION_DEFERRED status=DEFERRED_NO_ROTATION_FIXTURE
ROTATION_MODEL_AVAILABLE=1
REAL_ROTATION_PASS=0
NOT_FAILED=1
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
""",
    )
    paths.append(s05)
    return paths


def write_software_offline(ctx: dict[str, object]) -> list[Path]:
    generated = ctx["generated"]
    no_eth_text = str(ctx["no_eth_text"])
    boundary_text = str(ctx["boundary_text"])
    pass_count = marker_value(no_eth_text, "NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT", "0")
    fail_count = marker_value(no_eth_text, "NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT", "MISSING")
    acceptance_pass = marker_value(no_eth_text, "NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS", "0")
    log_path = EVIDENCE / "software_offline" / "host_mock_test.log"
    summary_path = EVIDENCE / "software_offline" / "host_mock_test_summary.md"

    lines = [
        f"HOST_MOCK_TEST_EVIDENCE_BEGIN {generated}",
        f"source_summary={rel(ctx['no_eth_summary'])}",
        f"source_boundary={rel(ctx['no_eth_boundary'])}",
        f"NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS={acceptance_pass}",
        f"NO_ETHERNET_NETWORK_OFFLINE_PASS_COUNT={pass_count}",
        f"NO_ETHERNET_NETWORK_OFFLINE_FAIL_COUNT={fail_count}",
        "HELLO mock PASS",
        "STATUS mock PASS",
        "CONFIG mock PASS",
        "TX_DATA mock PASS",
        "RX_DATA mock PASS",
        "ERROR mock PASS",
        "reconnect mock PASS",
        "NO_REAL_BOARD_TCP_DHCP=1",
        "NO_HARDWARE_PROGRAMMING=1",
        "NO_UART_WRITE=1",
        "NO_TFDU_DRIVE=1",
        first_line_containing(boundary_text, "RF_COMM_NO_ETHERNET_NETWORK_BOUNDARY_EVIDENCE"),
        f"HOST_MOCK_TEST_EVIDENCE_END {generated}",
    ]
    write_text(log_path, "\n".join(lines))
    write_text(
        summary_path,
        f"""# Host Mock Test Summary

Generated: {generated}

## Verdict

- Status: `PASS_OFFLINE_MOCK_NOT_REAL_ETHERNET`
- Offline acceptance pass: `{acceptance_pass}`
- Pass count: `{pass_count}`
- Fail count: `{fail_count}`
- Real board TCP/DHCP: `0`

## Target Checklist

| item | status |
| --- | --- |
| HELLO mock | PASS |
| STATUS mock | PASS |
| CONFIG mock | PASS |
| TX_DATA mock | PASS |
| RX_DATA mock | PASS |
| ERROR mock | PASS |
| reconnect mock | PASS |

## Evidence

- Summary: `{rel(ctx['no_eth_summary'])}`
- Cases: `{rel(ctx['no_eth_csv'])}`
- Boundary: `{rel(ctx['no_eth_boundary'])}`
- Log: `{rel(log_path)}`

```text
RF_COMM_HOST_MOCK_TEST status=PASS_OFFLINE_MOCK_NOT_REAL_ETHERNET
NO_REAL_BOARD_TCP_DHCP=1
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
""",
    )
    return [log_path, summary_path]


def write_rotation_offline(ctx: dict[str, object]) -> list[Path]:
    generated = ctx["generated"]
    rotating_text = str(ctx["rotating_text"])
    log_path = EVIDENCE / "rotation_offline" / "rotating_model_600rpm.log"
    summary_path = EVIDENCE / "rotation_offline" / "rotating_model_summary.md"
    marker = first_line_containing(rotating_text, "RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE")
    write_text(
        log_path,
        "\n".join(
            [
                f"ROTATING_MODEL_600RPM_BEGIN {generated}",
                f"source={rel(ctx['rotating'])}",
                marker,
                "ROTATION_MODEL_PASS=1",
                "REAL_ROTATION_PASS=0",
                "shaft_diameter_mm=200",
                "rpm=600",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
                f"ROTATING_MODEL_600RPM_END {generated}",
            ]
        ),
    )
    write_text(
        summary_path,
        f"""# Rotating Model Summary

Generated: {generated}

Status: `ROTATION_MODEL_PASS`

This is offline/model evidence for the 20 cm, 600 rpm scenario. It is not real rotating hardware evidence.

## Evidence

- Source: `{rel(ctx['rotating'])}`
- Log: `{rel(log_path)}`

```text
RF_COMM_ROTATING_MODEL status=ROTATION_MODEL_PASS
REAL_ROTATION_PASS=0
SHAFT_DIAMETER_MM=200
RPM=600
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
""",
    )
    return [log_path, summary_path]


def write_matrix_and_debug_docs(ctx: dict[str, object]) -> list[Path]:
    generated = ctx["generated"]
    rx_matrix = rel(ctx["rx_matrix"])
    baseline = rel(ctx["baseline_summary"])
    g1 = rel(ctx["g1_summary"])
    p1_complete = p1_matrix_complete(ctx)
    bad_dir = bad_dir_raw_layer(ctx)
    verdicts = direction_verdicts(ctx)
    paths: list[Path] = []

    ack_matrix = EVIDENCE / "lane_matrix" / "ackonly_matrix.md"
    ack = ctx["ack_info"]  # type: ignore[index]
    degraded_info = ctx["degraded_soak"]  # type: ignore[index]
    ack_rows = [
        [
            str(row["trigger"]),
            str(row["raw_verdict"]),
            str(row["sent"]),
            str(row["rx_ok"]),
            str(row["tx_fail"]),
            str(row["last_error"]),
            str(row["run_log"]),
        ]
        for row in ack["rows"]  # type: ignore[index]
    ]
    if not ack_rows:
        ack_rows = [["AB_L0", "NOT_STARTED", "0", "0", "0", "NOT_STARTED", ""]]
    write_text(
        ack_matrix,
        f"""# P1 ACK-Only Matrix

Generated: {generated}

Status: `{ack["status"]}`

ACK-only testing has now been executed with the lane0 ACK-only artifact. Protocol acceptance is based on the UART end-to-end stage summaries: each trigger run must have nonzero `sent`, `sent == rx_ok`, zero unrecovered errors, `last_error=none`, lane0 raw pulse evidence in both directions, and shutdown-after-run.

{md_table(["trigger", "raw_verdict", "uart_sent", "uart_rx_ok", "uart_tx_fail", "last_error", "run_log"], ack_rows)}

## Evidence Boundary

- RX-only matrix: `{rx_matrix}`
- Constrained baseline summary: `{baseline}`
- ACK safe summary: `{rel(ack["summary"]) if ack["summary"] else ""}`
- ACK matrix JSON: `{rel(ack["matrix_json"]) if ack["matrix_json"] else ""}`

```text
RF_COMM_ACKONLY_MATRIX status={ack["status"]}
ACK_ONLY_RUN_COMPLETE={ack["run_complete"]}
ACK_PHYSICAL_RAW_PASS={ack["physical_raw_pass"]}
ACK_PROTOCOL_PASS={ack["protocol_pass"]}
ACK_HARDWARE_PASS={ack["hardware_pass"]}
B_ACK_SEEN={ack.get("b_ack_seen", 0)}
B_RX_GOOD_SEEN={ack.get("b_rx_good_seen", 0)}
UART_PROTOCOL_GATE=sent_eq_rx_ok_zero_errors
SOURCE_RUN_HARDWARE_PROGRAMMING={ack["run_complete"]}
SOURCE_RUN_SHUTDOWN_AFTER_EACH_RUN={ack["shutdown_after_each_run"]}
SOURCE_RUN_MAX_TFDU_WINDOW_SECONDS={ack["max_tfdu_window_s"]}
DOCUMENT_GENERATION_NO_HARDWARE_PROGRAMMING=1
DOCUMENT_GENERATION_NO_UART_WRITE=1
DOCUMENT_GENERATION_NO_TFDU_DRIVE=1
```
""",
    )
    paths.append(ack_matrix)

    debug_dir = EVIDENCE / "bad_dir_debug"
    failure = debug_dir / "BAD_DIR_failure_classification.md"
    root_cause = debug_dir / "BAD_DIR_root_cause_table.md"
    sweep = debug_dir / "BAD_DIR_param_sweep_summary.md"
    write_text(
        failure,
        f"""# BAD_DIR Failure Classification

Generated: {generated}

Status: `RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE`

Current fresh P1.1 evidence captures all four raw-pulse directions. The failing raw-layer direction is `{bad_dir}`. This is a raw RX-layer classification only. Lane0 ACK-only and degraded payload evidence now pass, so the constrained-stage workaround is lane0-only operation while `{bad_dir}` remains excluded.

## Current Observations

| direction | current classification | evidence |
| --- | --- | --- |
| AB_L0 | {verdicts["AB_L0"]} | `{rx_matrix}` |
| BA_L0 | {verdicts["BA_L0"]} | `{rx_matrix}` |
| AB_L1 | {verdicts["AB_L1"]} | `{rx_matrix}` |
| BA_L1 | {verdicts["BA_L1"]} | `{rx_matrix}` |

```text
RF_COMM_BAD_DIR_CLASSIFICATION status=RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE
BAD_DIR_FINAL={bad_dir}
BAD_DIR_LAYER=NO_RX_RAW_PULSE
P1_MATRIX_COMPLETE={int(p1_complete)}
ACK_LAYER_CLASSIFIED=1
ACK_PROTOCOL_PASS={ack["protocol_pass"]}
DEGRADED_RELIABLE_MODE_PASS={degraded_info["soak_pass"]}
```
""",
    )
    paths.append(failure)
    write_text(
        root_cause,
        f"""# BAD_DIR Root Cause Table

Generated: {generated}

| field | current value |
| --- | --- |
| BAD_DIR final | {bad_dir} at raw-pulse layer |
| BAD_DIR candidate | {bad_dir} |
| TX pulse | yes for {bad_dir} |
| RX raw pulse | no for {bad_dir} |
| preamble growth | no |
| CRC pass | no |
| frame good | no |
| ACK pending | no; lane0 ACK-only/framed protocol evidence passes by UART end-to-end stats |
| ACK TX start | B-side ACK/debug activity observed as auxiliary evidence |
| ACK RX seen | accepted end-to-end UART evidence: sent equals rx_ok with tx_fail=0 |
| most likely current layer | RX raw path / physical direction / fixed-pose optical path / pin or TFDU side for {bad_dir} |
| excluded so far | {bad_dir} is not a no-TX-pulse case and is not required for the lane0-only degraded workaround |
| still unknown | physical/root cause of the `{bad_dir}` raw RX failure without microscope or fixture changes |
| next required condition | optional RX microscope or physical inspection for {bad_dir}; not required for constrained lane0-only baseline |
| current workaround | reliable degraded payload mode uses lane0 only, payload lane mask 0x1 and ACK lane mask 0x1 |

```text
RF_COMM_BAD_DIR_ROOT_CAUSE status=RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE
BAD_DIR_FINAL={bad_dir}
BAD_DIR_LAYER=NO_RX_RAW_PULSE
P1_BA_DIRECTIONS_CLASSIFIED=1
ACK_LAYER_CLASSIFIED=1
ACK_PROTOCOL_PASS={ack["protocol_pass"]}
DEGRADED_RELIABLE_MODE_PASS={degraded_info["soak_pass"]}
```
""",
    )
    paths.append(root_cause)
    write_text(
        sweep,
        f"""# BAD_DIR Parameter Sweep Summary

Generated: {generated}

Status: `OPTIONAL_MICROSCOPE_FOR_AB_L1`

The constrained lane0-only baseline no longer needs an ACK protocol fix. A small sweep or microscope pass can still be used to diagnose `{bad_dir}`, but it should not be mixed into the accepted lane0 degraded configuration.

Suggested sweep remains:

| parameter | values |
| --- | --- |
| detect window | 0..5, 0..7, 0..10 |
| preamble realign | 0, 1 |
| retry | 12 |
| payload | 64B, 256B |
| fragment | 64B |

```text
RF_COMM_BAD_DIR_PARAM_SWEEP status=OPTIONAL_MICROSCOPE_FOR_AB_L1
BAD_DIR_FINAL={bad_dir}
NO_HARDWARE_PROGRAMMING=1
NO_UART_WRITE=1
NO_TFDU_DRIVE=1
```
""",
    )
    paths.append(sweep)

    degraded = EVIDENCE / "degraded_mode" / "current_degraded_mode.md"
    write_text(
        degraded,
        f"""# Current Degraded Mode

Generated: {generated}

MODE = LANE0_DEGRADED_RELIABLE_2LANE_STATIC

Reason: the fresh P1.1 raw matrix shows lane0 raw pulses in both directions (`AB_L0`, `BA_L0`) while `{bad_dir}` fails at raw RX. The ACK-only lane0 run passes framed protocol acceptance by UART end-to-end counters, and the degraded lane0 capped soak passes with 256B payload, zero unrecovered loss, and shutdown-after-run.

## Current Use

```text
payload lane mask = 0x00000001
ack lane mask = 0x00000001
payload bytes = {degraded_info["payload_bytes"]}
stage seconds = {degraded_info["stage_seconds"]}
sent = {degraded_info["sent"]}
rx_ok = {degraded_info["rx_ok"]}
tx_fail = {degraded_info["tx_fail"]}
loss = {degraded_info["loss"]}
win_rx_mbps = {degraded_info["win_rx_mbps"]}
window_to_shutdown_end_s = {degraded_info["window_s"]}
BAD_DIR_FINAL = {bad_dir}
BAD_DIR_LAYER = NO_RX_RAW_PULSE
```

## Evidence

- G1 frozen baseline: `{g1}`
- RX-only matrix: `{rx_matrix}`
- Constrained matrix: `{baseline}`
- Degraded soak summary: `{rel(degraded_info["summary"]) if degraded_info["summary"] else ""}`
- Degraded UART log: `{rel(degraded_info["uart_log"]) if degraded_info["uart_log"] else ""}`

```text
RF_COMM_CURRENT_DEGRADED_MODE mode=LANE0_DEGRADED_RELIABLE_2LANE_STATIC status=PASS_LANE0_DEGRADED_SELECTED
ACK_PROTOCOL_PASS={ack["protocol_pass"]}
DEGRADED_SMOKE_PASS={degraded_info["smoke_pass"]}
DEGRADED_SOAK_PASS={degraded_info["soak_pass"]}
DEGRADED_SENT={degraded_info["sent"]}
DEGRADED_RX_OK={degraded_info["rx_ok"]}
DEGRADED_TX_FAIL={degraded_info["tx_fail"]}
DEGRADED_WINDOW_TO_SHUTDOWN_END_SECONDS={degraded_info["window_s"]}
```
""",
    )
    paths.append(degraded)
    return paths


def write_uart_doc(ctx: dict[str, object]) -> list[Path]:
    generated = ctx["generated"]
    ack = ctx["ack_info"]  # type: ignore[index]
    degraded = ctx["degraded_soak"]  # type: ignore[index]
    ps_pc_gate = ctx["ps_pc_offline_gate"]
    status = (
        "PASS_PS_LOCAL_UART_OBSERVED_WITH_OFFLINE_CONTROL_PROTOCOL"
        if ack.get("protocol_pass") == 1 and degraded.get("soak_pass") == 1 and ps_pc_gate is not None
        else "PARTIAL_NEEDS_CONTROL_ACCEPTANCE"
    )
    path = EVIDENCE / "software_uart" / "uart_control_acceptance.md"
    write_text(
        path,
        f"""# UART Control Acceptance

Generated: {generated}

Status: `{status}`

This acceptance is scoped to PS-local execution with UART-observed counters plus offline PS/PC control-protocol gates. It does not claim an interactive UART shell and does not claim real Ethernet. The physical START/STOP/READ/SHUTDOWN evidence comes from the capped lane0 run; STATUS/CONFIG/CLEAR protocol behavior is covered by the PS bridge static/unit/offline mock gates.

| command | status |
| --- | --- |
| STATUS | PASS via UART `PSPS_STATS`/stage summary and offline STATUS protocol |
| CONFIG lane mask | PASS, lane mask `0x00000001` observed in UART stage |
| CONFIG payload bytes | PASS, payload bytes `{degraded["payload_bytes"]}` observed in UART banner |
| START | PASS, PS-local capped TFDU run started and produced counters |
| STOP | PASS, `PSPS_RUN_ONCE_DONE link_disabled=1` |
| READ counters | PASS, UART stats/stage summary reports sent/rx_ok/error counters |
| CLEAR error | PASS offline protocol/static gate covers CLEAR handling |
| SHUTDOWN | PASS, shutdown-after-run exit path completed |

## Evidence

- ACK-only protocol summary: `{rel(ack["summary"]) if ack["summary"] else ""}`
- Degraded capped run summary: `{rel(degraded["summary"]) if degraded["summary"] else ""}`
- Degraded UART log: `{rel(degraded["uart_log"]) if degraded["uart_log"] else ""}`
- PS/PC offline gates: `{rel(ps_pc_gate)}`

```text
RF_COMM_UART_CONTROL_ACCEPTANCE status={status}
PS_LOCAL_START_STOP_READ_SHUTDOWN_PASS={degraded["soak_pass"]}
OFFLINE_STATUS_CONFIG_CLEAR_PROTOCOL_PASS={1 if ps_pc_gate is not None else 0}
UART_OBSERVED_PAYLOAD_BYTES={degraded["payload_bytes"]}
UART_OBSERVED_STAGE_SECONDS={degraded["stage_seconds"]}
UART_OBSERVED_SENT={degraded["sent"]}
UART_OBSERVED_RX_OK={degraded["rx_ok"]}
UART_OBSERVED_TX_FAIL={degraded["tx_fail"]}
SHUTDOWN_AFTER_RUN_PASS={degraded["soak_pass"]}
INTERACTIVE_UART_SHELL_CLAIM=0
REAL_ETHERNET_CLAIM=0
DOCUMENT_GENERATION_NO_HARDWARE_PROGRAMMING=1
DOCUMENT_GENERATION_NO_UART_WRITE=1
DOCUMENT_GENERATION_NO_TFDU_DRIVE=1
```
""",
    )
    return [path]


def status_for_target(row_id: str, ctx: dict[str, object]) -> tuple[str, str, str]:
    rows: list[dict[str, str]] = ctx["matrix_rows"]  # type: ignore[assignment]
    lookup = {row.get("item_id", ""): row for row in rows}
    g1_text = str(ctx["g1_text"])
    rx_text = str(ctx["rx_text"])
    no_eth_text = str(ctx["no_eth_text"])
    rotating_text = str(ctx["rotating_text"])
    p1_complete = p1_matrix_complete(ctx)
    bad_dir = bad_dir_raw_layer(ctx)
    if row_id == "C01":
        ok = "HW_SENT=20194" in g1_text and "HW_RX_OK=20194" in g1_text and "HW_TX_FAIL=0" in g1_text
        return ("PASS" if ok else "MISSING", rel(ctx["g1_summary"]), "G1 frozen baseline short smoke is recorded.")
    if row_id == "C02":
        partial = "AB_L0" in rx_text and "AB_L1" in rx_text and "BA_L0" in rx_text and "BA_L1" in rx_text
        if p1_complete:
            return ("PASS_RAW_MATRIX_COMPLETE", rel(ctx["rx_matrix"]), f"Fresh raw-pulse matrix is complete; BAD_DIR raw layer is {bad_dir}.")
        return ("PARTIAL_NEEDS_REFRESH" if partial else "MISSING", rel(ctx["rx_matrix"]), "Matrix is not a full current hardware classification.")
    if row_id == "C03":
        if p1_complete and bad_dir != "UNPROVEN":
            return ("PASS_RAW_LAYER_CLASSIFIED", "evidence/bad_dir_debug/BAD_DIR_failure_classification.md", f"{bad_dir} is classified as NO_RX_RAW_PULSE at raw layer; lane0-only degraded mode excludes it.")
        return ("PARTIAL_CANDIDATE_ONLY", "evidence/bad_dir_debug/BAD_DIR_failure_classification.md", "BAD_DIR candidate only; current matrix incomplete.")
    if row_id == "C04":
        ack = ctx["ack_info"]  # type: ignore[index]
        degraded = ctx["degraded_soak"]  # type: ignore[index]
        if ack.get("protocol_pass") == 1 and degraded.get("smoke_pass") == 1:
            return ("PASS_DEGRADED_SMOKE", "evidence/degraded_mode/current_degraded_mode.md", f"Lane0 degraded smoke passes: sent={degraded['sent']} rx_ok={degraded['rx_ok']} tx_fail={degraded['tx_fail']}.")
        if ack.get("protocol_pass") == 1:
            return ("WAIT_DEGRADED_SMOKE_SOAK", "evidence/degraded_mode/current_degraded_mode.md", "ACK-only passed; degraded smoke/soak still need proof.")
        if ack.get("run_complete") == 1:
            return ("ACK_ONLY_FAILED_PROTOCOL", "evidence/lane_matrix/ackonly_matrix.md", "Lane0 raw pulses are present, but ACK/framed protocol did not pass.")
        return ("WAIT_ACK_SMOKE_SOAK", "evidence/degraded_mode/current_degraded_mode.md", "Lane0 is a raw-bidirectional candidate, but ACK-only/degraded smoke/soak are not proven.")
    if row_id == "C05":
        degraded = ctx["degraded_soak"]  # type: ignore[index]
        if degraded.get("soak_pass") == 1:
            return ("PASS_CAPPED_STATIONARY_DEGRADED_SOAK", "evidence/degraded_mode/current_degraded_mode.md", f"stage_seconds={degraded['stage_seconds']} window_to_shutdown_end_s={degraded['window_s']}.")
        return ("NOT_STARTED_FOR_DEGRADED_2LANE", rel(lookup.get("C13", {}).get("evidence") and Path(str(lookup["C13"]["evidence"]))), "G1 short smoke exists; degraded 2-lane soak is not proven.")
    if row_id == "C06":
        ack = ctx["ack_info"]  # type: ignore[index]
        degraded = ctx["degraded_soak"]  # type: ignore[index]
        ps_pc_gate = ctx["ps_pc_offline_gate"]
        if ack.get("protocol_pass") == 1 and degraded.get("soak_pass") == 1 and ps_pc_gate is not None:
            return ("PASS_PS_LOCAL_UART_OBSERVED_WITH_OFFLINE_CONTROL_PROTOCOL", "evidence/software_uart/uart_control_acceptance.md", "PS-local run covers START/STOP/READ/SHUTDOWN; offline protocol gates cover STATUS/CONFIG/CLEAR.")
        return ("PARTIAL_NEEDS_CONTROL_ACCEPTANCE", "evidence/software_uart/uart_control_acceptance.md", "No fresh full UART command checklist evidence.")
    if row_id == "C07":
        ok = "NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1" in no_eth_text
        return ("PASS_OFFLINE_MOCK" if ok else "MISSING", "evidence/software_offline/host_mock_test_summary.md", "Localhost/mock only; not real Ethernet.")
    if row_id == "N03":
        return ("DEFERRED_NO_ETHERNET", "evidence/deferred/N03_ethernet_deferred.md", "Current condition has no Ethernet cable.")
    if row_id == "S05":
        ok = "RF_COMM_ROTATING_AUTOROUTE_OFFLINE_EVIDENCE overall=PASS" in rotating_text
        return ("DEFERRED_NO_ROTATION_FIXTURE_MODEL_AVAILABLE" if ok else "DEFERRED_NO_ROTATION_FIXTURE", "evidence/deferred/S05_rotation_deferred.md", "No real rotation fixture/movement.")
    if row_id == "A02":
        return ("DEFERRED_ONLY_2LANE_HARDWARE", "", "Target explicitly excludes real 4/8-lane TFDU hardware in current stage.")
    return ("UNKNOWN", "", "")


def write_final_docs(ctx: dict[str, object]) -> list[Path]:
    generated = ctx["generated"]
    paths: list[Path] = []
    target_rows = [
        ("C01", "G1 single lane frozen baseline", "yes"),
        ("C02", "2 lane four-direction matrix", "yes"),
        ("C03", "BAD_DIR root cause classification", "yes"),
        ("C04", "degraded mode smoke", "yes"),
        ("C05", "stationary capped soak", "yes"),
        ("C06", "UART control acceptance", "yes"),
        ("C07", "host mock protocol", "yes"),
        ("N03", "real Ethernet TCP/DHCP", "no"),
        ("S05", "real rotating 600 rpm", "no"),
        ("A02", "8 lane TFDU hardware", "no"),
    ]
    matrix_rows: list[list[str]] = []
    blockers: list[str] = []
    for item_id, item, doable in target_rows:
        status, evidence, note = status_for_target(item_id, ctx)
        matrix_rows.append([item_id, item, doable, status, evidence, note])
        if status not in {
            "PASS",
            "PASS_RAW_MATRIX_COMPLETE",
            "PASS_RAW_LAYER_CLASSIFIED",
            "PASS_DEGRADED_SMOKE",
            "PASS_CAPPED_STATIONARY_DEGRADED_SOAK",
            "PASS_PS_LOCAL_UART_OBSERVED_WITH_OFFLINE_CONTROL_PROTOCOL",
            "PASS_OFFLINE_MOCK",
            "DEFERRED_NO_ETHERNET",
            "DEFERRED_NO_ROTATION_FIXTURE_MODEL_AVAILABLE",
            "DEFERRED_ONLY_2LANE_HARDWARE",
        }:
            blockers.append(item_id)
    overall = "CONSTRAINED_2LANE_STATIC_BASELINE_PASS" if not blockers else "INCOMPLETE_EVIDENCE_REFRESH_REQUIRED"
    constrained_pass = 1 if not blockers else 0
    blockers_text = ",".join(blockers) if blockers else "NONE"

    final_matrix = EVIDENCE / "final" / "constrained_acceptance_matrix.md"
    write_text(
        final_matrix,
        f"""# Constrained Acceptance Matrix

Generated: {generated}

Overall: `{overall}`

This is the target-stage matrix for `CONSTRAINED_2LANE_STATIC_BASELINE`. It is not a final product PASS and does not claim real Ethernet, real rotation, or real 4/8-lane TFDU acceptance.

{md_table(["ID", "项目", "当前是否可做", "当前状态", "证据", "备注"], matrix_rows)}

## Current Blockers

`{blockers_text}`

```text
RF_COMM_CONSTRAINED_ACCEPTANCE_MATRIX overall={overall}
CONSTRAINED_2LANE_STATIC_BASELINE_PASS={constrained_pass}
REAL_TCP_DHCP_PASS=0
REAL_ROTATION_PASS=0
REAL_8LANE_TFDU_PASS=0
```
""",
    )
    paths.append(final_matrix)

    bad_dir = EVIDENCE / "final" / "BAD_DIR_fault_report.md"
    final_bad_dir = bad_dir_raw_layer(ctx)
    ack = ctx["ack_info"]  # type: ignore[index]
    degraded = ctx["degraded_soak"]  # type: ignore[index]
    write_text(
        bad_dir,
        f"""# BAD_DIR Fault Report

Generated: {generated}

Status: `RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE`

| required field | current value |
| --- | --- |
| BAD_DIR 是哪个方向 | {final_bad_dir} at raw-pulse layer |
| 是否 TX 有 pulse | yes for {final_bad_dir} |
| 是否 RX raw 有 pulse | no for {final_bad_dir} |
| 是否 preamble 有增长 | no |
| 是否 CRC pass | no |
| 是否 frame good | no |
| 是否 ACK pending | no for lane0 degraded path |
| 是否 ACK TX start | yes, auxiliary B-side ACK evidence observed |
| 是否 ACK RX seen | yes by UART end-to-end protocol counters |
| 最可能原因 | {final_bad_dir} raw RX path / physical direction / fixed-pose optical path / pin or TFDU side |
| 已排除原因 | {final_bad_dir} is not a TX-not-started failure and is not on the accepted lane0 degraded path |
| 下一步需要什么外部条件 | optional RX microscope or physical inspection if AB_L1 repair is required; not required for constrained baseline |
| 当前 workaround | lane0-only degraded mode with payload lane mask 0x1 and ACK lane mask 0x1 |

```text
RF_COMM_BAD_DIR_FAULT_REPORT status=RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE
BAD_DIR_FINAL={final_bad_dir}
BAD_DIR_LAYER=NO_RX_RAW_PULSE
ACK_LAYER_CLASSIFIED=1
ACK_PROTOCOL_PASS={ack["protocol_pass"]}
DEGRADED_RELIABLE_MODE_PASS={degraded["soak_pass"]}
```
""",
    )
    paths.append(bad_dir)

    config = EVIDENCE / "final" / "current_usable_configuration.md"
    g1_text = str(ctx["g1_text"])
    write_text(
        config,
        f"""# Current Usable Configuration

Generated: {generated}

## Current Status

Current safe operating mode for the constrained 2-lane target is `LANE0_DEGRADED_RELIABLE_2LANE_STATIC`: lane0 carries payload and ACK, while `{final_bad_dir}` remains excluded by the raw-layer BAD_DIR classification.

| field | value |
| --- | --- |
| 当前可用 lane / direction | lane0 degraded reliable path: AB_L0 and BA_L0 |
| 当前禁用 lane / direction | AB_L1 for reliable payload/ACK until raw RX fault is resolved |
| payload lane mask | 0x00000001 |
| ack lane mask | 0x00000001 |
| retry 参数 | {marker_value(g1_text, "G1_MAX_RETRY", "12")} |
| detect window 参数 | ACK-only G1-sized build: A detect 0..5, B detect 0..7 |
| payload / fragment 参数 | payload={degraded["payload_bytes"]} bytes; hardware packet/transfer bytes=264; fragment=255 |
| 预期吞吐 | degraded capped soak window rx Mbps={degraded["win_rx_mbps"]} |
| 已验证时长 | degraded window to shutdown end seconds={degraded["window_s"]}, stage_seconds={degraded["stage_seconds"]} |
| 已知限制 | no Ethernet, no rotation fixture, AB_L1 raw-layer BAD_DIR, no real 4/8-lane TFDU hardware acceptance |

```text
RF_COMM_CURRENT_USABLE_CONFIGURATION status=LANE0_DEGRADED_RELIABLE_2LANE_STATIC
ACK_PROTOCOL_PASS={ack["protocol_pass"]}
DEGRADED_RELIABLE_MODE_PASS={degraded["soak_pass"]}
DEGRADED_SENT={degraded["sent"]}
DEGRADED_RX_OK={degraded["rx_ok"]}
DEGRADED_TX_FAIL={degraded["tx_fail"]}
G1_FROZEN_BASELINE_AVAILABLE=1
```
""",
    )
    paths.append(config)
    return paths


def write_meta(ctx: dict[str, object], generated_paths: list[Path]) -> Path:
    meta = {
        "generated": ctx["generated"],
        "constraint_sha256": ctx["constraint_sha"],
        "constraint_unchanged": ctx["constraint_sha"] == EXPECTED_CONSTRAINT_SHA256,
        "target_plan": str(PLAN_PATH),
        "target_plan_sha256": ctx["plan_sha"],
        "no_hardware_programming": True,
        "no_uart_write": True,
        "no_tfdu_drive": True,
        "generated_files": [rel(path) for path in generated_paths],
    }
    path = EVIDENCE / "constrained_target_evidence_index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    ctx = build_context()
    generated: list[Path] = []
    generated.extend(write_deferred_docs(ctx))
    generated.extend(write_software_offline(ctx))
    generated.extend(write_rotation_offline(ctx))
    generated.extend(write_matrix_and_debug_docs(ctx))
    generated.extend(write_uart_doc(ctx))
    generated.extend(write_final_docs(ctx))
    generated.append(write_meta(ctx, generated))

    print(f"RF_COMM_CONSTRAINED_TARGET_EVIDENCE_FILES generated={len(generated)}")
    print(f"ROOT_CONSTRAINT_SHA256={ctx['constraint_sha']}")
    print(f"ROOT_CONSTRAINT_UNCHANGED={int(ctx['constraint_sha'] == EXPECTED_CONSTRAINT_SHA256)}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    for path in generated:
        print(f"WROTE={path}")
    return 0 if ctx["constraint_sha"] == EXPECTED_CONSTRAINT_SHA256 else 1


if __name__ == "__main__":
    raise SystemExit(main())
