from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"
PLAN_PATH = Path.home() / "Downloads" / "constrained_2lane_static_plan.md"

MANIFEST_MD = REPORTS / "constrained_2lane_static_baseline_manifest_current.md"
MANIFEST_JSON = REPORTS / "constrained_2lane_static_baseline_manifest_current.json"
MANIFEST_CSV = REPORTS / "constrained_2lane_static_baseline_manifest_current.csv"
MATRIX_MD = REPORTS / "constrained_2lane_static_acceptance_matrix_current.md"
MATRIX_JSON = REPORTS / "constrained_2lane_static_acceptance_matrix_current.json"
MATRIX_CSV = REPORTS / "constrained_2lane_static_acceptance_matrix_current.csv"
SUMMARY = REPORTS / "constrained_2lane_static_baseline_current.summary.txt"


@dataclass
class ManifestRow:
    artifact_id: str
    role: str
    status: str
    path: str
    sha256: str
    note: str


@dataclass
class AcceptanceRow:
    item_id: str
    requirement: str
    status: str
    evidence: str
    note: str


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
    return path.read_text(encoding="utf-8", errors="replace")


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def latest(pattern: str) -> Path | None:
    matches = [p for p in ROOT.glob(pattern) if p.is_file()]
    if not matches:
        return None
    return max(matches, key=lambda p: p.stat().st_mtime)


def latest_containing(pattern: str, needles: Iterable[str]) -> Path | None:
    for path in sorted(ROOT.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        text = read_text(path)
        if all(needle in text for needle in needles):
            return path
    return None


def find_hard_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def contains_all(text: str, needles: Iterable[str]) -> bool:
    return all(needle in text for needle in needles)


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


def float_marker(text: str, key: str, default: float = 0.0) -> float:
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


def classify_ack_safe(summary: Path | None) -> tuple[str, str]:
    text = read_text(summary)
    if not text:
        return "MISSING_TOOLING", "No ACK-only safe summary found."
    if "DRY_RUN_NO_HARDWARE_DONE=1" in text:
        return "TOOL_READY_ONLY", "Dry-run/tooling evidence exists, not ACK hardware PASS."
    if not contains_all(text, ["DRY_RUN=0", "MATRIX_EXIT=0", "P0_ACK_ONLY_SAFE_END"]):
        return "ACK_RUN_INCOMPLETE_OR_BLOCKED", "Latest ACK-only run did not complete a full matrix."

    matrix_json_path = Path(kv_value(text, "MATRIX_ANALYSIS_JSON"))
    if not matrix_json_path.is_absolute():
        matrix_json_path = ROOT / matrix_json_path
    json_rows: list[dict[str, object]] = []
    if matrix_json_path.exists():
        try:
            json_rows = json.loads(read_text(matrix_json_path))
        except json.JSONDecodeError:
            json_rows = []
    raw_by_trigger = {str(row.get("trigger_mode", "")): row for row in json_rows}
    ab_raw = str(raw_by_trigger.get("a_tx_lane0", {}).get("verdict", "")).startswith("PASS")
    ba_raw = str(raw_by_trigger.get("b_tx_lane0", {}).get("verdict", "")).startswith("PASS")
    b_debug = json.dumps(raw_by_trigger.get("b_tx_lane0", {}).get("b_debug_class_counts", {}), ensure_ascii=False)
    b_ack_seen = "ack_lane0=1" in b_debug

    prefix = matrix_json_path.name.replace(".ila_matrix.json", "")
    run_logs = sorted(REPORTS.glob(f"{prefix}.*.run.log"))
    protocol_ok = bool(run_logs) and ab_raw and ba_raw
    shutdown_ok = bool(run_logs)
    for run_log in run_logs:
        run_text = read_text(run_log)
        stats_line = last_line_containing(run_text, "UART_MATCH=PSPS_STAGE_SUMMARY")
        if not stats_line:
            stats_line = last_line_containing(run_text, "UART_MATCH=PSPS_STATS")
        values = parse_key_values(stats_line)
        sent = int_value(values, "sent")
        rx_ok = int_value(values, "rx_ok")
        clean = (
            sent > 0
            and rx_ok == sent
            and int_value(values, "tx_fail") == 0
            and int_value(values, "rx_timeout") == 0
            and int_value(values, "rx_bad") == 0
            and int_value(values, "rx_mismatch") == 0
            and values.get("last_error", "MISSING") == "none"
        )
        if not clean:
            protocol_ok = False
        if "SHUTDOWN_EXIT_INFERRED=0" not in run_text and "SHUTDOWN_EXIT=0" not in run_text:
            shutdown_ok = False

    if protocol_ok and shutdown_ok:
        ack_note = "B-side ACK debug was also observed." if b_ack_seen else "ILA B debug rx_good is auxiliary only; UART end-to-end stats are the protocol gate."
        return "ACK_ONLY_PASS", f"ACK-only raw and UART protocol evidence pass. {ack_note}"
    if ab_raw and ba_raw:
        return "ACK_ONLY_RUN_FAILED_PROTOCOL", "ACK-only run completed and lane0 raw pulses are present, but UART protocol stats show rx_ok=0 or tx_fail>0."
    return "ACK_ONLY_RUN_FAILED_RAW", "ACK-only run completed but raw lane0 pulse evidence is missing."


def latest_degraded_soak_summary() -> Path | None:
    for path in sorted(ROOT.glob("reports/lane0_hw_loopback_safe_*.summary.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if "UART_MATCH=PSPS_STAGE_SUMMARY" in text and "SHUTDOWN_EXIT=0" in text:
            return path
    return None


def degraded_soak_info(summary: Path | None = None) -> dict[str, object]:
    summary = summary or latest_degraded_soak_summary()
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
    config_line = last_line_containing(uart_text, "payload_bytes=")
    config = parse_key_values(config_line)
    sent = int_value(values, "sent")
    rx_ok = int_value(values, "rx_ok")
    tx_fail = int_value(values, "tx_fail")
    rx_timeout = int_value(values, "rx_timeout")
    rx_bad = int_value(values, "rx_bad")
    rx_mismatch = int_value(values, "rx_mismatch")
    payload = int_value(config, "payload_bytes")
    stage_seconds = int_value(config, "stage_seconds")
    window_s = float_marker(text, "HW_WINDOW_TO_SHUTDOWN_END_SECONDS")
    shutdown_ok = "SHUTDOWN_EXIT=0" in text
    run_once_done = "PSPS_RUN_ONCE_DONE link_disabled=1" in uart_text or "UART_MATCH=PSPS_RUN_ONCE_DONE link_disabled=1" in text
    clean_stats = (
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
    smoke_pass = int(clean_stats)
    soak_pass = int(clean_stats and stage_seconds >= 300 and shutdown_ok and run_once_done and 0 < window_s <= 600.0)
    return {
        "summary": summary,
        "uart_log": uart_log,
        "smoke_pass": smoke_pass,
        "soak_pass": soak_pass,
        "payload_bytes": payload,
        "stage_seconds": stage_seconds,
        "sent": sent,
        "rx_ok": rx_ok,
        "tx_fail": tx_fail,
        "rx_timeout": rx_timeout,
        "rx_bad": rx_bad,
        "rx_mismatch": rx_mismatch,
        "win_rx_mbps": values.get("win_rx_mbps", "MISSING"),
        "window_s": window_s,
        "last_error": values.get("last_error", "MISSING"),
    }


def latest_ps_pc_offline_gate() -> Path | None:
    return latest_containing(
        "reports/ps_pc_offline_gates_*.summary.txt",
        ["PS_PC_OFFLINE_GATES_PASS static=1 unittest=1 offline_mock=1"],
    )


def add_manifest(
    rows: list[ManifestRow],
    artifact_id: str,
    role: str,
    path: Path | None,
    note: str,
    status_override: str | None = None,
) -> None:
    exists = path is not None and path.exists()
    status = status_override or ("PRESENT" if exists else "MISSING")
    rows.append(
        ManifestRow(
            artifact_id=artifact_id,
            role=role,
            status=status,
            path=rel(path),
            sha256=sha256(path),
            note=note,
        )
    )


def md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join(cell.replace("\n", " ").replace("|", "/") for cell in row) + " |")
    return "\n".join(out)


def latest_actual_p1_summary() -> Path | None:
    for path in sorted(ROOT.glob("reports/p1_lane_mapping_matrix_safe_*.summary.txt"), key=lambda p: p.stat().st_mtime, reverse=True):
        text = read_text(path)
        if "DRY_RUN=0" in text:
            return path
    return None


def classify_p1(summary: Path | None) -> tuple[str, str]:
    text = read_text(summary)
    if not text:
        return "NEEDS_FRESH_RUN", "No non-dry-run P1 lane mapping summary found."
    if "RUN_ILA_TIMEOUT" in text or "RUN_MISSING_ILA_CSV" in text:
        return "NEEDS_REFRESH_TIMEOUT_OR_MISSING_CSV", "Latest non-dry P1 matrix attempt did not produce a complete four-direction matrix."
    required = ["a_tx_lane0", "a_tx_lane1", "b_tx_lane0", "b_tx_lane1"]
    expected = ["A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1"]
    has_all_runs = all(f"trigger={trigger}" in text for trigger in required)
    has_all_expected = all(link in text for link in expected)
    if has_all_runs and has_all_expected and "MATRIX_ANALYSIS_JSON_EXIT=0" in text:
        if "FAIL_EXPECTED_RAW" in text or "FAIL_NO_RX_ACTIVITY" in text:
            return "FRESH_MATRIX_COMPLETE_WITH_LINK_FAILURES", "All four P1.1 directions were captured; one or more raw links failed and must feed BAD_DIR/degraded-mode work."
        return "FRESH_MATRIX_COMPLETE_ALL_RAW_PASS", "All four P1.1 directions were captured and no raw-link failure marker appears."
    return "NEEDS_REFRESH_INCOMPLETE_TRIGGER_SET", "Latest non-dry P1 summary does not prove all four directions."


def build() -> tuple[list[ManifestRow], list[AcceptanceRow], dict[str, str]]:
    constraint = find_hard_constraint()
    constraint_ok = constraint is not None and sha256(constraint) == EXPECTED_CONSTRAINT_SHA256

    plan_review = REPORTS / "constrained_2lane_static_plan_review_current.md"
    g1_report = REPORTS / "G1_acceptance_report.md"
    g1_hashes = REPORTS / "G1_artifacts_hashes.txt"
    duration_cap = REPORTS / "duration_cap_compliance_current.md"
    safe_wrapper = REPORTS / "safe_wrapper_guard_contract_current.md"
    external_preconditions = REPORTS / "external_preconditions_current.md"
    remaining_readiness = REPORTS / "remaining_acceptance_readiness_current.md"
    full_target_audit = REPORTS / "full_target_audit_current_20260626.md"
    status_consistency = REPORTS / "full_target_status_consistency_current.md"
    plan_readiness = REPORTS / "plan_readiness_current_20260626.md"
    plan_snapshot = REPORTS / "plan_execution_snapshot_current_20260626.md"
    plan_completion = REPORTS / "plan_completion_audit_current_20260626.md"
    p1_wrapper = ROOT / "tools" / "run_p1_lane_mapping_matrix_safe.ps1"
    matrix_wrapper = ROOT / "tools" / "run_2lane_matrix_safe.ps1"
    prearmed_wrapper = ROOT / "tools" / "run_2lane_hw_prearmed_ila_safe.ps1"
    post_g1_summary = latest_containing(
        "reports/post_g1_target_sim_gate_*.summary.txt",
        ["POST_G1_TARGET_SIM_GATE_PASS=1", "POST_G1_TARGET_SIM_GATE_PASS_COUNT=23"],
    )
    post_g1_cases = None if post_g1_summary is None else post_g1_summary.with_name(post_g1_summary.name.replace(".summary.txt", ".cases.csv"))
    no_eth_summary = latest_containing(
        "reports/no_ethernet_network_offline_acceptance_*.summary.txt",
        ["NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1", "NO_REAL_BOARD_TCP_DHCP=1"],
    )
    p1_actual = latest_actual_p1_summary()
    p1_status, p1_note = classify_p1(p1_actual)
    lane0_raw = latest_containing(
        "reports/2lane_matrix_safe_*.ila_matrix.md",
        ["A_TO_B_LANE0", "A_TO_B_LANE1", "B_TO_A_LANE0", "B_TO_A_LANE1"],
    )
    rxonly_matrix = ROOT / "evidence" / "lane_matrix" / "rxonly_matrix.md"
    ack_safe = latest("reports/p0_ack_only_safe_*.summary.txt")
    ack_build = latest("reports/p0_ack_only_build_*.summary.txt")
    degraded_soak = latest_degraded_soak_summary()
    ps_pc_offline_gate = latest_ps_pc_offline_gate()
    rx_root = latest("reports/p0_rx_root_cause_safe_*.summary.txt")

    manifest: list[ManifestRow] = []
    add_manifest(manifest, "ROOT_CONSTRAINT", "hard project constraint", constraint, "Must remain unchanged.")
    add_manifest(manifest, "INPUT_PLAN", "candidate constrained 2lane plan", PLAN_PATH, "User-supplied constrained plan.")
    add_manifest(manifest, "PLAN_REVIEW", "compatibility review", plan_review, "Manual review of the constrained plan.")
    add_manifest(manifest, "G1_REPORT", "single-lane G1 frozen baseline evidence", g1_report, "G1 single-lane capped hardware soak and simulation/offline report.")
    add_manifest(manifest, "G1_HASHES", "G1 artifact traceability", g1_hashes, "G1 bit/ltx/xsa/elf/evidence hash manifest.")
    add_manifest(manifest, "DURATION_CAP", "physical runtime cap proof", duration_cap, "600 s physical continuous-run cap evidence.")
    add_manifest(manifest, "SAFE_WRAPPERS", "safe wrapper guard proof", safe_wrapper, "Future TFDU traffic requires explicit guards and shutdown-after-run.")
    add_manifest(manifest, "EXTERNAL_PRECONDITIONS", "current external state", external_preconditions, "Read-only no-Ethernet snapshot.")
    add_manifest(manifest, "REMAINING_READINESS", "remaining real acceptance blockers", remaining_readiness, "N03/N04/S05/A01/A02 external blockers.")
    add_manifest(manifest, "POST_G1_SIM", "post-G1 simulation/offline gate", post_g1_summary, "Includes 2-lane perf, autoroute, full-system offline models.")
    add_manifest(manifest, "POST_G1_CASES", "post-G1 case table", post_g1_cases, "Structured post-G1 gate cases.")
    add_manifest(manifest, "NO_ETHERNET_OFFLINE", "no-Ethernet offline acceptance", no_eth_summary, "Offline host/network/model proof while no board Ethernet exists.")
    add_manifest(manifest, "P1_LATEST_ACTUAL", "latest non-dry P1 lane matrix attempt", p1_actual, p1_note, status_override=p1_status)
    add_manifest(manifest, "P1_WRAPPER", "P1 lane-mapping safe wrapper", p1_wrapper, "Requires artifact/preflight gates and emergency shutdown on matrix timeout.")
    add_manifest(manifest, "MATRIX_WRAPPER", "2lane matrix safe wrapper", matrix_wrapper, "Runs lane-specific captures and emergency shutdown on single-run timeout.")
    add_manifest(manifest, "PREARMED_WRAPPER", "single 2lane prearmed ILA wrapper", prearmed_wrapper, "Programs shutdown in finally and limits shutdown wait time.")
    add_manifest(manifest, "P1_RAW_MATRIX_REPORT", "fresh P1.1 four-direction raw matrix report", lane0_raw, "Latest complete analyzer report with all four expected raw links.")
    add_manifest(manifest, "P1_RXONLY_EVIDENCE", "target P1.1 rxonly evidence", rxonly_matrix, "Evidence-normalized P1.1 raw-pulse matrix.")
    add_manifest(manifest, "ACK_SAFE_TOOL", "ACK-only safe orchestration", ack_safe, "Latest ACK-only safe wrapper summary; may be dry-run or hardware depending on DRY_RUN marker.")
    add_manifest(manifest, "ACK_BUILD_TOOL", "ACK-only build recipe", ack_build, "ACK-only build summary and artifact traceability.")
    add_manifest(manifest, "DEGRADED_SOAK", "lane0 degraded capped soak", degraded_soak, "Physical lane0 degraded 256B payload smoke/soak evidence under the 600 s cap.")
    add_manifest(manifest, "PS_PC_OFFLINE_GATE", "PS/PC control protocol offline gate", ps_pc_offline_gate, "Static/unit/offline mock evidence for STATUS/CONFIG/READ/CLEAR protocol behavior.")
    add_manifest(manifest, "RX_ROOT_TOOL", "RX root-cause orchestration", rx_root, "Tooling/dry-run evidence for BAD_DIR classification.")
    add_manifest(manifest, "PLAN_READINESS", "older staged readiness gate", plan_readiness, "Records G2 lane mapping as the next blocking gate.")
    add_manifest(manifest, "PLAN_SNAPSHOT", "older execution snapshot", plan_snapshot, "Records active 2-lane ILA baseline and next commands.")
    add_manifest(manifest, "PLAN_COMPLETION", "older plan completion audit", plan_completion, "Records P1 hardware failure and waiting hardware rows.")
    add_manifest(manifest, "FULL_TARGET_AUDIT", "strict full-target audit", full_target_audit, "Preserves full target as incomplete.")
    add_manifest(manifest, "STATUS_CONSISTENCY", "full-target status consistency", status_consistency, "Current evidence chain consistency gate.")

    g1_text = read_text(g1_report)
    duration_text = read_text(duration_cap)
    safe_text = read_text(safe_wrapper)
    external_text = read_text(external_preconditions)
    no_eth_text = read_text(no_eth_summary)
    post_text = read_text(post_g1_summary)
    plan_review_text = read_text(plan_review)
    full_audit_text = read_text(full_target_audit)
    plan_readiness_text = read_text(plan_readiness)
    ack_text = read_text(ack_safe)

    g1_ok = contains_all(g1_text, ["SIM_OFFLINE_CAPPED_10MIN_SOAK_PASS", "sent=267892", "rx_ok=267892", "tx_fail=0", "HW_WINDOW_TO_SHUTDOWN_END_SECONDS=582.2"])
    duration_ok = contains_all(duration_text, ["RF_COMM_DURATION_CAP_COMPLIANCE overall=PASS_DURATION_CAP_600S", "MAX_CONTINUOUS_RUN_SECONDS=600", "REAL_PHYSICAL_RUN_GT_600_ALLOWED=0"])
    safe_ok = contains_all(safe_text, ["RF_COMM_SAFE_WRAPPER_GUARD_CONTRACT overall=PASS_SAFE_WRAPPER_GUARDS", "REAL_TFDU_TRAFFIC_REQUIRES_SHUTDOWN_AFTER=1", "CURRENT_NO_ETHERNET_EXECUTES_ZERO_WRAPPERS=1"])
    no_eth_ok = contains_all(external_text, ["RF_COMM_EXTERNAL_PRECONDITIONS overall=BLOCKED_NO_ETHERNET", "NO_HARDWARE_PROGRAMMING=1", "NO_TFDU_DRIVE=1"]) and contains_all(no_eth_text, ["NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1", "NO_REAL_BOARD_TCP_DHCP=1"])
    post_2lane_sim_ok = contains_all(post_text, ["IR_STREAM_BIDIR_B0_2LANE_PERF_PASS", "IR_STREAM_PARALLEL_ASYM_2LANE_PERF_PASS", "POST_G1_TARGET_SIM_GATE_PASS_COUNT=23"])
    review_ok = "CONSTRAINED_2LANE_STATIC_PLAN_REVIEW overall=COMPATIBLE_WITH_HARD_CONSTRAINT_NEEDS_EVIDENCE_REFRESH" in plan_review_text
    full_target_boundary_ok = contains_all(full_audit_text, ["RF_COMM_FULL_TARGET_AUDIT overall=INCOMPLETE_SIM_OFFLINE_PROGRESS", "BOARD-TCP-DHCP", "MISSING_HARDWARE"])
    plan_gate_records_p1 = contains_all(
        plan_readiness_text,
        [
            "Next blocking gate: `G2_LANE_MAPPING`",
            "Fresh lane0/lane1 A->B and B->A physical matrix must be captured and classified by self-tested analyzer/gate tooling.",
        ],
    )
    ack_status, ack_note = classify_ack_safe(ack_safe)
    ack_pass = ack_status == "ACK_ONLY_PASS"
    degraded = degraded_soak_info(degraded_soak)
    degraded_smoke_pass = bool(degraded["smoke_pass"])
    degraded_soak_pass = bool(degraded["soak_pass"])
    ps_pc_offline_ok = ps_pc_offline_gate is not None
    ps_local_control_pass = bool(ack_pass and degraded_soak_pass and ps_pc_offline_ok)

    acceptance: list[AcceptanceRow] = [
        AcceptanceRow("C01", "Root project constraint remains unchanged.", "PASS" if constraint_ok else "FAIL", rel(constraint), f"sha256={sha256(constraint)}"),
        AcceptanceRow("C02", "Constrained 2lane static plan is compatible with hard target boundaries.", "PASS" if review_ok else "MISSING_REVIEW", rel(plan_review), "Review preserves final-target boundary and no-overclaim rules."),
        AcceptanceRow("C03", "G1 single-lane frozen baseline is available as the constrained-stage recovery point.", "PASS" if g1_ok else "MISSING_OR_WEAK", rel(g1_report), "Requires capped G1 evidence with sent=rx_ok and shutdown."),
        AcceptanceRow("C04", "Physical TFDU/TX continuous runs are capped at 600 seconds.", "PASS" if duration_ok else "FAIL_OR_MISSING", rel(duration_cap), "Applies to all future physical P1/P2/P3/P4 runs."),
        AcceptanceRow("C05", "Safe wrappers require explicit guards before real TFDU traffic.", "PASS" if safe_ok else "FAIL_OR_MISSING", rel(safe_wrapper), "Real traffic requires AllowTraffic and shutdown-after-run."),
        AcceptanceRow("C06", "2lane behavior has simulation/offline coverage.", "PASS_SIM_OFFLINE" if post_2lane_sim_ok else "MISSING", rel(post_g1_summary), "Not hardware evidence; covers 2lane perf models only."),
        AcceptanceRow("C07", "No-Ethernet boundary is recorded and offline replacements pass.", "PASS_DEFERRED_NO_ETHERNET" if no_eth_ok else "FAIL_OR_MISSING", rel(external_preconditions), "Real N03 stays deferred until a board Ethernet link exists."),
        AcceptanceRow("C08", "Fresh 2lane four-direction raw-pulse matrix is complete.", "NEEDS_REFRESH" if p1_status.startswith("NEEDS") else p1_status, rel(p1_actual), p1_note),
        AcceptanceRow("C09", "BAD_DIR is classified from fresh current evidence.", "PASS_RAW_LAYER_CLASSIFIED" if not p1_status.startswith("NEEDS") else "WAIT_P1_MATRIX", rel(rxonly_matrix), "Current raw-layer BAD_DIR is AB_L1 / NO_RX_RAW_PULSE; lane0 degraded operation is a workaround, not a fix for AB_L1."),
        AcceptanceRow("C10", "ACK-only matrix is validated with an ACK-only build manifest.", ack_status, rel(ack_safe), ack_note),
        AcceptanceRow(
            "C11",
            "Current degraded mode is selected from P1/P2 evidence.",
            "PASS_LANE0_DEGRADED_SELECTED" if ack_pass and degraded_smoke_pass else "WAIT_ACK_SMOKE_SOAK",
            rel(degraded["summary"] if isinstance(degraded["summary"], Path) else None),
            "Use lane0 only: payload lane mask 0x1, ACK lane mask 0x1; AB_L1 remains excluded by raw-layer BAD_DIR.",
        ),
        AcceptanceRow(
            "C12",
            "Degraded mode smoke sends >=10000 frames with zero unrecovered loss.",
            "PASS_DEGRADED_SMOKE" if degraded_smoke_pass else "NOT_STARTED",
            rel(degraded["summary"] if isinstance(degraded["summary"], Path) else None),
            f"Latest parsed stage sent={degraded['sent']} rx_ok={degraded['rx_ok']} tx_fail={degraded['tx_fail']} last_error={degraded['last_error']}.",
        ),
        AcceptanceRow(
            "C13",
            "At least one degraded stationary capped soak segment passes.",
            "PASS_CAPPED_STATIONARY_DEGRADED_SOAK" if degraded_soak_pass else "G1_ONLY_2LANE_PENDING",
            rel(degraded["summary"] if isinstance(degraded["summary"], Path) else None),
            f"stage_seconds={degraded['stage_seconds']} window_to_shutdown_end_s={degraded['window_s']} payload_bytes={degraded['payload_bytes']}.",
        ),
        AcceptanceRow(
            "C14",
            "UART/PS local control covers STATUS/CONFIG/START/STOP/READ/CLEAR/SHUTDOWN.",
            "PASS_PS_LOCAL_UART_OBSERVED_WITH_OFFLINE_CONTROL_PROTOCOL" if ps_local_control_pass else "PARTIAL_NEEDS_CONTROL_ACCEPTANCE",
            rel(ps_pc_offline_gate),
            "PS local run provides START/STOP/READ/SHUTDOWN UART-observed evidence; offline PS/PC gates cover STATUS/CONFIG/CLEAR protocol behavior. No real Ethernet or interactive UART shell is claimed.",
        ),
        AcceptanceRow("C15", "Constrained acceptance matrix and manifest exist.", "PASS_BASELINE_RECORDED", f"{rel(MATRIX_MD)}; {rel(MANIFEST_MD)}", "Generated baseline evidence for the constrained 2-lane stage; full target remains separately bounded."),
        AcceptanceRow("C16", "Full target remains incomplete until real network/hardware/rotation evidence exists.", "PASS_BOUNDARY_PRESERVED" if full_target_boundary_ok else "FAIL_OR_MISSING", rel(full_target_audit), "Prevents constrained baseline from replacing final target."),
        AcceptanceRow("C17", "Older stage gate has been superseded by the fresh P1.1 matrix.", "PASS_SUPERSEDED_BY_P1_MATRIX" if not p1_status.startswith("NEEDS") else ("PASS" if plan_gate_records_p1 else "MISSING"), rel(plan_readiness), "Fresh P1.1 evidence is now the authoritative lane-mapping record."),
    ]

    blockers = [
        row.item_id
        for row in acceptance
        if row.status
        in {
            "NEEDS_REFRESH",
            "WAIT_P1_MATRIX",
            "WAIT_P1_P2",
            "WAIT_ACK_SMOKE_SOAK",
            "ACK_FAILED_WAIT_PROTOCOL_FIX_SMOKE_SOAK",
            "ACK_ONLY_RUN_FAILED_PROTOCOL",
            "ACK_ONLY_RUN_FAILED_RAW",
            "ACK_RUN_INCOMPLETE_OR_BLOCKED",
            "NOT_STARTED",
            "G1_ONLY_2LANE_PENDING",
            "PARTIAL_NEEDS_CONTROL_ACCEPTANCE",
            "MISSING_TOOLING",
            "FAIL_OR_MISSING",
            "FAIL",
        }
    ]
    overall = "CONSTRAINED_2LANE_STATIC_BASELINE_PASS" if not blockers else "INCOMPLETE_EVIDENCE_REFRESH_REQUIRED"

    meta = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "overall": overall,
        "constraint_sha256": sha256(constraint),
        "constraint_unchanged": "1" if constraint_ok else "0",
        "input_plan": rel(PLAN_PATH),
        "input_plan_sha256": sha256(PLAN_PATH),
        "no_hardware_programming": "1",
        "no_uart_write": "1",
        "no_tfdu_drive": "1",
        "constrained_baseline_pass": "1" if overall == "CONSTRAINED_2LANE_STATIC_BASELINE_PASS" else "0",
        "fresh_p1_matrix_complete": "0" if p1_status.startswith("NEEDS") else "1",
        "blockers": ",".join(blockers),
    }
    return manifest, acceptance, meta


def write_outputs(manifest: list[ManifestRow], acceptance: list[AcceptanceRow], meta: dict[str, str]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)

    with MANIFEST_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(manifest[0]).keys()))
        writer.writeheader()
        for row in manifest:
            writer.writerow(asdict(row))

    with MATRIX_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(acceptance[0]).keys()))
        writer.writeheader()
        for row in acceptance:
            writer.writerow(asdict(row))

    payload = {
        "meta": meta,
        "manifest": [asdict(row) for row in manifest],
        "acceptance": [asdict(row) for row in acceptance],
    }
    MANIFEST_JSON.write_text(json.dumps({"meta": meta, "manifest": payload["manifest"]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    MATRIX_JSON.write_text(json.dumps({"meta": meta, "acceptance": payload["acceptance"]}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    manifest_md = [
        "# Constrained 2lane Static Baseline Manifest",
        "",
        f"Generated: {meta['generated']}",
        "",
        "This manifest is a no-hardware, no-UART, no-TFDU evidence index for the current constrained 2lane static baseline. It does not claim final target completion.",
        "",
        "## Verdict",
        "",
        f"- Overall: `{meta['overall']}`",
        f"- Constrained baseline pass: `{meta['constrained_baseline_pass']}`",
        f"- Fresh P1 matrix complete: `{meta['fresh_p1_matrix_complete']}`",
        f"- No hardware programming: `{meta['no_hardware_programming']}`",
        f"- No UART write: `{meta['no_uart_write']}`",
        f"- No TFDU drive: `{meta['no_tfdu_drive']}`",
        "",
        "## Artifacts",
        "",
        md_table(
            ["artifact_id", "role", "status", "path", "sha256", "note"],
            [[row.artifact_id, row.role, row.status, row.path, row.sha256, row.note] for row in manifest],
        ),
        "",
        "```text",
        f"RF_COMM_CONSTRAINED_2LANE_STATIC_BASELINE overall={meta['overall']}",
        f"CONSTRAINED_BASELINE_PASS={meta['constrained_baseline_pass']}",
        f"FRESH_P1_MATRIX_COMPLETE={meta['fresh_p1_matrix_complete']}",
        f"NO_HARDWARE_PROGRAMMING={meta['no_hardware_programming']}",
        f"NO_UART_WRITE={meta['no_uart_write']}",
        f"NO_TFDU_DRIVE={meta['no_tfdu_drive']}",
        f"ROOT_CONSTRAINT_UNCHANGED={meta['constraint_unchanged']}",
        f"ROOT_CONSTRAINT_SHA256={meta['constraint_sha256']}",
        f"INPUT_PLAN_SHA256={meta['input_plan_sha256']}",
        "```",
    ]
    MANIFEST_MD.write_text("\n".join(manifest_md) + "\n", encoding="utf-8")

    matrix_md = [
        "# Constrained 2lane Static Acceptance Matrix",
        "",
        f"Generated: {meta['generated']}",
        "",
        "This matrix tracks only the current constrained static 2lane baseline. It does not claim real Ethernet, real rotation, or real 4/8-lane TFDU acceptance.",
        "",
        "## Verdict",
        "",
        f"- Overall: `{meta['overall']}`",
        f"- Blockers: `{meta['blockers']}`",
        f"- No hardware programming: `{meta['no_hardware_programming']}`",
        f"- No UART write: `{meta['no_uart_write']}`",
        f"- No TFDU drive: `{meta['no_tfdu_drive']}`",
        "",
        "## Matrix",
        "",
        md_table(
            ["item_id", "requirement", "status", "evidence", "note"],
            [[row.item_id, row.requirement, row.status, row.evidence, row.note] for row in acceptance],
        ),
        "",
        "## Next Safe Work",
        "",
        "1. Keep lane0-only degraded operation as the constrained-stage safe configuration until AB_L1 is repaired.",
        "2. Treat real Ethernet, real rotation, and real 4/8-lane TFDU acceptance as deferred external/full-target work.",
        "3. Any future physical run must keep the 600 s cap, preflight gates, and shutdown-after-run discipline.",
        "",
        "```text",
        f"RF_COMM_CONSTRAINED_2LANE_STATIC_MATRIX overall={meta['overall']} items={len(acceptance)} blockers={len(meta['blockers'].split(',')) if meta['blockers'] else 0}",
        f"CONSTRAINED_BASELINE_PASS={meta['constrained_baseline_pass']}",
        f"FRESH_P1_MATRIX_COMPLETE={meta['fresh_p1_matrix_complete']}",
        f"NO_HARDWARE_PROGRAMMING={meta['no_hardware_programming']}",
        f"NO_UART_WRITE={meta['no_uart_write']}",
        f"NO_TFDU_DRIVE={meta['no_tfdu_drive']}",
        "REAL_TCP_DHCP_PASS=0",
        "REAL_ROTATION_PASS=0",
        "FINAL_TARGET_PASS=0",
        "```",
    ]
    MATRIX_MD.write_text("\n".join(matrix_md) + "\n", encoding="utf-8")

    summary_lines = [
        f"RF_COMM_CONSTRAINED_2LANE_STATIC_BASELINE overall={meta['overall']}",
        f"MANIFEST_MD={MANIFEST_MD}",
        f"MANIFEST_JSON={MANIFEST_JSON}",
        f"MANIFEST_CSV={MANIFEST_CSV}",
        f"MATRIX_MD={MATRIX_MD}",
        f"MATRIX_JSON={MATRIX_JSON}",
        f"MATRIX_CSV={MATRIX_CSV}",
        f"CONSTRAINED_BASELINE_PASS={meta['constrained_baseline_pass']}",
        f"FRESH_P1_MATRIX_COMPLETE={meta['fresh_p1_matrix_complete']}",
        f"BLOCKERS={meta['blockers']}",
        f"NO_HARDWARE_PROGRAMMING={meta['no_hardware_programming']}",
        f"NO_UART_WRITE={meta['no_uart_write']}",
        f"NO_TFDU_DRIVE={meta['no_tfdu_drive']}",
        "REAL_TCP_DHCP_PASS=0",
        "REAL_ROTATION_PASS=0",
        "FINAL_TARGET_PASS=0",
    ]
    SUMMARY.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def main() -> int:
    manifest, acceptance, meta = build()
    write_outputs(manifest, acceptance, meta)
    print(f"WROTE={MANIFEST_MD}")
    print(f"WROTE={MATRIX_MD}")
    print(f"WROTE={SUMMARY}")
    print(f"RF_COMM_CONSTRAINED_2LANE_STATIC_BASELINE overall={meta['overall']}")
    print(f"CONSTRAINED_BASELINE_PASS={meta['constrained_baseline_pass']}")
    print(f"FRESH_P1_MATRIX_COMPLETE={meta['fresh_p1_matrix_complete']}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    return 0 if meta["constraint_unchanged"] == "1" else 1


if __name__ == "__main__":
    raise SystemExit(main())
