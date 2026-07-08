#!/usr/bin/env python3
"""Summarize the current JTAG blocker from diagnostic evidence.

This script is read-only for hardware and design sources. It consumes the latest
JTAG USB diagnostic/preflight/driver dry-run summaries and writes a concise
machine-readable report that can be referenced by plan gates.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


@dataclass
class Finding:
    key: str
    value: str
    evidence: str


def read_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    data = path.read_bytes()
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="ignore")
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="ignore")
    if data[:4096].count(b"\x00") > max(4, len(data[:4096]) // 10):
        return data.decode("utf-16le", errors="ignore")
    return data.decode("utf-8", errors="ignore")


def latest(pattern: str) -> Path | None:
    paths = list(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def latest_any(*patterns: str) -> Path | None:
    paths: list[Path] = []
    for pattern in patterns:
        paths.extend(ROOT.glob(pattern))
    if not paths:
        return None
    return max(paths, key=lambda path: path.stat().st_mtime)


def rel(path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def contains(text: str, pattern: str) -> bool:
    return re.search(pattern, text, re.MULTILINE | re.DOTALL) is not None


def capture_first(text: str, pattern: str, default: str = "") -> str:
    match = re.search(pattern, text, re.MULTILINE)
    return match.group(1).strip() if match else default


def count_matches(text: str, pattern: str) -> int:
    return len(re.findall(pattern, text, re.MULTILINE))


def strict_hw_pass(text: str) -> bool:
    prefix = r"(?:PREFLIGHT_MATCH=|PREFLIGHT_AFTER_MATCH=|VIVADO_PREFLIGHT_MATCH freq=\d+ )?VIVADO_MATCH="
    return (
        contains(text, rf"(?m)^{prefix}HW_PREFLIGHT_RESULT PASS\b")
        and contains(text, rf"(?m)^{prefix}HW_PREFLIGHT_ZYNQ\b")
    )


def strict_fail_no_target_count(text: str) -> int:
    prefix = r"(?:PREFLIGHT_MATCH=|PREFLIGHT_AFTER_MATCH=|VIVADO_PREFLIGHT_MATCH freq=\d+ )?VIVADO_MATCH="
    return count_matches(text, rf"(?m)^{prefix}HW_PREFLIGHT_RESULT FAIL_NO_TARGET\b")


def md_table(headers: list[str], rows: list[list[object]]) -> str:
    out = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    for row in rows:
        out.append("| " + " | ".join("" if cell is None else str(cell).replace("\n", " ") for cell in row) + " |")
    return "\n".join(out)


def collect() -> dict[str, object]:
    diag = latest("reports/jtag_usb_diag_*.summary.txt")
    repair = latest("reports/jtag_driver_repair_*.summary.txt")
    recovery = latest("reports/jtag_recovery_then_resume_*.summary.txt")
    p1 = latest("reports/p1_lane_mapping_matrix_safe_*.summary.txt")
    preflight = latest_any(
        "reports/hw_target_preflight*.summary.txt",
        "reports/hw_target_preflight*.out.log",
        "reports/run_p2_remaining_hardware_sequence_safe_*.summary.txt",
        "reports/run_p2_uart_operator_control_safe_*.summary.txt",
        "reports/jtag_usb_soft_recover_*.summary.txt",
    )

    diag_text = read_text(diag)
    repair_text = read_text(repair)
    recovery_text = read_text(recovery)
    p1_text = read_text(p1)
    preflight_text = read_text(preflight)
    current_text = preflight_text or diag_text
    current_evidence = rel(preflight or diag)
    historical_text = "\n".join([diag_text, repair_text, recovery_text, p1_text])
    all_text = "\n".join([diag_text, repair_text, recovery_text, p1_text, preflight_text])

    current_pass_evidence = strict_hw_pass(current_text)
    historical_pass_evidence = strict_hw_pass(historical_text)
    fail_no_target_count = strict_fail_no_target_count(all_text)
    current_fail_no_target_count = strict_fail_no_target_count(current_text)
    historical_fail_no_target_count = strict_fail_no_target_count(historical_text)
    freq_fail_count = count_matches(diag_text, r"VIVADO_PREFLIGHT_FREQ=\d+ EXIT=2")
    freq_pass_count = count_matches(diag_text, r"VIVADO_PREFLIGHT_FREQ=\d+ EXIT=0")

    com_present = contains(all_text, r"(?m)COM_PORT_PRESENT=1\b")
    cp210_present = contains(all_text, r"CP210x USB to UART Bridge \(COM3\)")
    ftdi_present = contains(all_text, r"(?m)FTDI6014_PRESENT=1\b") or contains(all_text, r"VID_0403&PID_6014")
    ftdi_bound_ftdibus = contains(all_text, r"(?m)FTDI6014_BOUND_TO_FTDIBUS=1\b")
    driver_root_present = contains(all_text, r"(?m)XILINX_DRIVER_ROOT_PRESENT=1\b")
    pcusb_present = contains(all_text, r"(?m)(XILINX_PCUSB_INSTALL_CMD_PRESENT|INSTALL_DRIVERS_CMD_PRESENT)=1\b")
    digilent_present = contains(all_text, r"(?m)DIGILENT_INSTALLER_PRESENT=1\b")
    dry_run_repair = contains(all_text, r"(?m)DRY_RUN=1\b") and contains(all_text, r"NO_SYSTEM_DRIVER_CHANGE_DONE=1")
    not_admin = contains(all_text, r"(?m)IS_ADMIN=0\b")
    p1_guard_pass = contains(p1_text, r"(?m)ARTIFACT_GUARD_PASS_PARSED=1\b")
    p1_no_programming = contains(p1_text, r"(?m)P1_LANE_MAPPING_BLOCKED_NO_PROGRAMMING=1\b")

    if current_pass_evidence:
        status = "JTAG_READY"
        blocker = "NONE"
        next_action = "JTAG is currently visible; continue only through the active P2/P1 safety gates."
    elif current_fail_no_target_count >= 1 or (not preflight_text and freq_fail_count >= 2):
        status = "BLOCKED_NO_HW_TARGET"
        blocker = "Vivado hw_server enumerates zero hw targets at all tested JTAG frequencies."
        next_action = (
            "Current non-elevated soft recovery did not restore JTAG. Check board power/JTAG connector/J13 first; "
            "if physical checks pass, run the elevated recovery command captured in the recovery dry-run report."
        )
    elif not_admin and dry_run_repair:
        status = "WAITING_ELEVATED_DRIVER_REPAIR"
        blocker = "Driver repair recipe is prepared, but current shell is not elevated."
        next_action = "Run tools/run_jtag_driver_recovery_then_resume.ps1 -LaunchElevated -InstallPcUsb -InstallDigilent."
    else:
        status = "UNKNOWN_JTAG_STATE"
        blocker = "Insufficient or mixed JTAG evidence."
        next_action = "Re-run tools/diagnose_jtag_usb.ps1 with multiple frequencies."

    findings = [
        Finding("com_port_present", str(int(com_present)), rel(diag or preflight)),
        Finding("cp210_uart_present", str(int(cp210_present)), rel(diag or preflight)),
        Finding("ftdi6014_present", str(int(ftdi_present)), rel(diag)),
        Finding("ftdi6014_bound_to_ftdibus", str(int(ftdi_bound_ftdibus)), rel(diag)),
        Finding("xilinx_driver_root_present", str(int(driver_root_present)), rel(diag or repair)),
        Finding("xilinx_pcusb_installer_present", str(int(pcusb_present)), rel(repair or diag)),
        Finding("digilent_installer_present", str(int(digilent_present)), rel(repair or diag)),
        Finding("current_shell_not_admin", str(int(not_admin)), rel(diag or repair)),
        Finding("repair_dry_run_no_system_change", str(int(dry_run_repair)), rel(repair or recovery)),
        Finding("vivado_freq_pass_count", str(freq_pass_count), rel(diag)),
        Finding("vivado_freq_fail_no_target_count", str(freq_fail_count), rel(diag)),
        Finding("current_fail_no_target_count", str(current_fail_no_target_count), current_evidence),
        Finding("current_hw_pass_evidence", str(int(current_pass_evidence)), current_evidence),
        Finding("historical_fail_no_target_count", str(historical_fail_no_target_count), "; ".join(filter(None, [rel(diag), rel(p1), rel(recovery)]))),
        Finding("stale_or_historical_hw_pass_evidence", str(int(historical_pass_evidence)), "; ".join(filter(None, [rel(recovery), rel(p1)]))),
        Finding("fail_no_target_total", str(fail_no_target_count), "; ".join(filter(None, [rel(diag), rel(p1), rel(preflight)]))),
        Finding("p1_artifact_guard_passed", str(int(p1_guard_pass)), rel(p1)),
        Finding("p1_no_programming_gate_hit", str(int(p1_no_programming)), rel(p1)),
    ]

    return {
        "status": status,
        "blocker": blocker,
        "next_action": next_action,
        "diag": diag,
        "repair": repair,
        "recovery": recovery,
        "p1": p1,
        "preflight": preflight,
        "findings": findings,
        "frequencies": capture_first(diag_text, r"(?m)^JTAG_FREQUENCIES_HZ=(.+)$", ""),
    }


def render(report: dict[str, object]) -> str:
    findings: list[Finding] = report["findings"]  # type: ignore[assignment]
    evidence_rows = [
        ["jtag_usb_diag", rel(report["diag"]), ""],
        ["driver_repair_dry_run", rel(report["repair"]), ""],
        ["recovery_then_resume_dry_run", rel(report["recovery"]), ""],
        ["p1_safe_retry", rel(report["p1"]), ""],
        ["latest_hw_preflight", rel(report["preflight"]), ""],
    ]

    return "\n".join(
        [
            "# RF_COMM JTAG Blocker Analysis",
            "",
            f"Generated: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Verdict",
            "",
            f"- Status: `{report['status']}`",
            f"- Blocker: {report['blocker']}",
            f"- Tested frequencies: `{report['frequencies']}`",
            f"- Next action: {report['next_action']}",
            "",
            "## Findings",
            "",
            md_table(["key", "value", "evidence"], [[f.key, f.value, f.evidence] for f in findings]),
            "",
            "## Evidence Files",
            "",
            md_table(["type", "path", "note"], evidence_rows),
            "",
            "JTAG_BLOCKER_ANALYSIS "
            f"status={report['status']} "
            f"freqs={report['frequencies']} "
            "hardware_action=none programming=none tfdu_drive=none",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPORTS / "jtag_blocker_analysis_current_20260626.md")
    parser.add_argument("--json", type=Path, default=REPORTS / "jtag_blocker_analysis_current_20260626.json")
    args = parser.parse_args()

    report = collect()
    out = args.out if args.out.is_absolute() else ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(report), encoding="utf-8")

    json_out = args.json if args.json.is_absolute() else ROOT / args.json
    json_payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "status": report["status"],
        "blocker": report["blocker"],
        "tested_frequencies": report["frequencies"],
        "next_action": report["next_action"],
        "evidence": {
            "diag": rel(report["diag"]),
            "repair": rel(report["repair"]),
            "recovery": rel(report["recovery"]),
            "p1": rel(report["p1"]),
            "preflight": rel(report["preflight"]),
        },
        "findings": [asdict(finding) for finding in report["findings"]],  # type: ignore[index]
        "hardware_action": "none",
        "programming": "none",
        "tfdu_drive": "none",
    }
    json_out.write_text(json.dumps(json_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"JTAG_BLOCKER_STATUS={report['status']}")
    print(f"JTAG_BLOCKER_NEXT_ACTION={report['next_action']}")
    print(f"JTAG_BLOCKER_MARKDOWN={out}")
    print(f"JTAG_BLOCKER_JSON={json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
