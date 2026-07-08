from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"
REPORTS = ROOT / "reports"
EXPECTED_CONSTRAINT_SHA256 = "CFF1A17EE77BBAF90080CF4F97E5920E961AEFAE3B6752F080E35FCF4D4B1F11"


@dataclass
class Check:
    name: str
    status: str
    path: str
    detail: str


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


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def find_constraint() -> Path | None:
    for path in ROOT.glob("*.txt"):
        if path.is_file() and sha256(path) == EXPECTED_CONSTRAINT_SHA256:
            return path
    return None


def require_file(checks: list[Check], name: str, path: Path, needles: list[str] | None = None) -> None:
    needles = needles or []
    if not path.exists():
        checks.append(Check(name, "FAIL", rel(path), "missing"))
        return
    text = read_text(path)
    missing = [needle for needle in needles if needle not in text]
    checks.append(Check(name, "PASS" if not missing else "FAIL", rel(path), "ok" if not missing else "missing markers: " + ";".join(missing)))


def main() -> int:
    checks: list[Check] = []
    constraint = find_constraint()
    constraint_hash = sha256(constraint)
    checks.append(
        Check(
            "root_constraint_unchanged",
            "PASS" if constraint_hash == EXPECTED_CONSTRAINT_SHA256 else "FAIL",
            rel(constraint),
            f"sha256={constraint_hash}",
        )
    )

    require_file(
        checks,
        "final_matrix",
        EVIDENCE / "final" / "constrained_acceptance_matrix.md",
        [
            "overall=CONSTRAINED_2LANE_STATIC_BASELINE_PASS",
            "CONSTRAINED_2LANE_STATIC_BASELINE_PASS=1",
            "REAL_TCP_DHCP_PASS=0",
            "REAL_ROTATION_PASS=0",
            "REAL_8LANE_TFDU_PASS=0",
        ],
    )
    require_file(
        checks,
        "bad_dir_fault_report",
        EVIDENCE / "final" / "BAD_DIR_fault_report.md",
        ["RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE", "BAD_DIR_FINAL=AB_L1", "BAD_DIR_LAYER=NO_RX_RAW_PULSE", "ACK_PROTOCOL_PASS=1", "DEGRADED_RELIABLE_MODE_PASS=1"],
    )
    require_file(
        checks,
        "current_usable_configuration",
        EVIDENCE / "final" / "current_usable_configuration.md",
        ["LANE0_DEGRADED_RELIABLE_2LANE_STATIC", "ACK_PROTOCOL_PASS=1", "DEGRADED_RELIABLE_MODE_PASS=1", "G1_FROZEN_BASELINE_AVAILABLE=1"],
    )
    require_file(
        checks,
        "n03_deferred",
        EVIDENCE / "deferred" / "N03_ethernet_deferred.md",
        ["DEFERRED_NO_ETHERNET", "NO_REAL_BOARD_TCP_DHCP=1", "NOT_FAILED=1"],
    )
    require_file(
        checks,
        "s05_deferred",
        EVIDENCE / "deferred" / "S05_rotation_deferred.md",
        ["DEFERRED_NO_ROTATION_FIXTURE", "REAL_ROTATION_PASS=0", "NOT_FAILED=1"],
    )
    require_file(
        checks,
        "host_mock_summary",
        EVIDENCE / "software_offline" / "host_mock_test_summary.md",
        ["PASS_OFFLINE_MOCK_NOT_REAL_ETHERNET", "HELLO mock", "STATUS mock", "CONFIG mock", "TX_DATA mock", "RX_DATA mock", "ERROR mock", "reconnect mock"],
    )
    require_file(
        checks,
        "host_mock_log",
        EVIDENCE / "software_offline" / "host_mock_test.log",
        ["NO_ETHERNET_NETWORK_OFFLINE_ACCEPTANCE_PASS=1", "NO_REAL_BOARD_TCP_DHCP=1"],
    )
    require_file(
        checks,
        "rotation_offline_summary",
        EVIDENCE / "rotation_offline" / "rotating_model_summary.md",
        ["ROTATION_MODEL_PASS", "REAL_ROTATION_PASS=0", "SHAFT_DIAMETER_MM=200", "RPM=600"],
    )
    require_file(
        checks,
        "ackonly_matrix_boundary",
        EVIDENCE / "lane_matrix" / "ackonly_matrix.md",
        ["ACK_ONLY_PASS", "ACK_ONLY_RUN_COMPLETE=1", "ACK_PHYSICAL_RAW_PASS=1", "ACK_PROTOCOL_PASS=1", "ACK_HARDWARE_PASS=1", "SOURCE_RUN_SHUTDOWN_AFTER_EACH_RUN=1"],
    )
    require_file(
        checks,
        "bad_dir_classification",
        EVIDENCE / "bad_dir_debug" / "BAD_DIR_failure_classification.md",
        ["RAW_LAYER_CLASSIFIED_DEGRADED_LANE0_AVAILABLE", "BAD_DIR_FINAL=AB_L1", "P1_MATRIX_COMPLETE=1", "ACK_PROTOCOL_PASS=1", "DEGRADED_RELIABLE_MODE_PASS=1"],
    )
    require_file(
        checks,
        "degraded_mode",
        EVIDENCE / "degraded_mode" / "current_degraded_mode.md",
        ["MODE = LANE0_DEGRADED_RELIABLE_2LANE_STATIC", "ACK_PROTOCOL_PASS=1", "DEGRADED_SMOKE_PASS=1", "DEGRADED_SOAK_PASS=1"],
    )
    require_file(
        checks,
        "rxonly_matrix_complete",
        EVIDENCE / "lane_matrix" / "rxonly_matrix.md",
        ["P1_MATRIX_COMPLETE=1", "BAD_DIR_RAW_LAYER=AB_L1", "AB_L0=PASS", "BA_L0=PASS", "AB_L1=NO_RX_RAW_PULSE", "BA_L1=PASS"],
    )
    require_file(
        checks,
        "uart_control_boundary",
        EVIDENCE / "software_uart" / "uart_control_acceptance.md",
        ["PASS_PS_LOCAL_UART_OBSERVED_WITH_OFFLINE_CONTROL_PROTOCOL", "PS_LOCAL_START_STOP_READ_SHUTDOWN_PASS=1", "OFFLINE_STATUS_CONFIG_CLEAR_PROTOCOL_PASS=1", "DOCUMENT_GENERATION_NO_UART_WRITE=1", "DOCUMENT_GENERATION_NO_TFDU_DRIVE=1"],
    )
    require_file(
        checks,
        "evidence_index",
        EVIDENCE / "constrained_target_evidence_index.json",
        ['"no_hardware_programming": true', '"no_uart_write": true', '"no_tfdu_drive": true'],
    )

    overall = "PASS_CONSTRAINED_TARGET_EVIDENCE_READY" if all(check.status == "PASS" for check in checks) else "FAIL"
    REPORTS.mkdir(parents=True, exist_ok=True)
    out_json = REPORTS / "constrained_target_evidence_files_gate_current.json"
    out_md = REPORTS / "constrained_target_evidence_files_gate_current.md"
    generated = datetime.now().astimezone().isoformat(timespec="seconds")
    payload = {
        "generated": generated,
        "overall": overall,
        "target_pass": overall == "PASS_CONSTRAINED_TARGET_EVIDENCE_READY",
        "constraint_sha256": constraint_hash,
        "checks": [asdict(check) for check in checks],
    }
    out_json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = [
        "| check | status | path | detail |",
        "| --- | --- | --- | --- |",
    ]
    for check in checks:
        rows.append(f"| {check.name} | {check.status} | {check.path} | {check.detail.replace('|', '/')} |")
    out_md.write_text(
        "\n".join(
            [
                "# Constrained Target Evidence Files Gate",
                "",
                f"Generated: {generated}",
                "",
                f"- Overall: `{overall}`",
                f"- Target pass: `{1 if overall == 'PASS_CONSTRAINED_TARGET_EVIDENCE_READY' else 0}`",
                "- Scope: `status evidence only, no hardware action`",
                "",
                *rows,
                "",
                "```text",
                f"RF_COMM_CONSTRAINED_TARGET_EVIDENCE_FILES_GATE overall={overall} checks={len(checks)}",
                f"CONSTRAINED_2LANE_STATIC_BASELINE_PASS={1 if overall == 'PASS_CONSTRAINED_TARGET_EVIDENCE_READY' else 0}",
                "NO_HARDWARE_PROGRAMMING=1",
                "NO_UART_WRITE=1",
                "NO_TFDU_DRIVE=1",
                "```",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"RF_COMM_CONSTRAINED_TARGET_EVIDENCE_FILES_GATE overall={overall} checks={len(checks)}")
    print(f"CONSTRAINED_2LANE_STATIC_BASELINE_PASS={1 if overall == 'PASS_CONSTRAINED_TARGET_EVIDENCE_READY' else 0}")
    print("NO_HARDWARE_PROGRAMMING=1")
    print("NO_UART_WRITE=1")
    print("NO_TFDU_DRIVE=1")
    print(f"WROTE={out_md}")
    print(f"WROTE={out_json}")
    return 0 if overall == "PASS_CONSTRAINED_TARGET_EVIDENCE_READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
