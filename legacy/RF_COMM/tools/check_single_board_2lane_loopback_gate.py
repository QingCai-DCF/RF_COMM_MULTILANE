#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path


READY_VALUES = {"1", "DRY_RUN_READY"}
BLOCKED_OR_SCOPED = {
    "BLOCKED_MISSING_PL_INTERNAL_INTERFACE",
    "BLOCKED_MISSING_FAULT_INJECTION_INTERFACE",
    "NOT_RUN_EXISTING_PATH_SCOPE",
    "NOT_CLAIMED",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check single-board 2-lane existing-path evidence without final-target overclaim."
    )
    parser.add_argument("report_dir", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError:
        return ""


def parse_flags(path: Path) -> dict[str, str]:
    flags: dict[str, str] = {}
    for raw in read_text(path).splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        flags[key.strip()] = value.strip()
    return flags


def value_ready(value: str | None) -> bool:
    return value in READY_VALUES


def main() -> int:
    args = parse_args()
    report_dir = args.report_dir.resolve()
    flags_path = report_dir / "10_result_flags.txt"
    flags = parse_flags(flags_path)
    blockers: list[str] = []
    lines: list[str] = [
        "SINGLE_BOARD_2LANE_EXISTING_PATH_GATE_BEGIN",
        f"REPORT_DIR={report_dir}",
        "NO_MANUAL_GATE_REQUIRED_BY_THIS_CHECK=1",
    ]

    if not report_dir.exists():
        blockers.append("REPORT_DIR_MISSING")
    if not flags:
        blockers.append("RESULT_FLAGS_MISSING_OR_EMPTY")

    mode = flags.get("SINGLE_BOARD_ACCEPTANCE_MODE", "UNKNOWN")
    lines.append(f"SINGLE_BOARD_ACCEPTANCE_MODE={mode}")

    required_files = (
        "00_environment.json",
        "01_safe_gate.log",
        "02_register_status_no_tx.log",
        "03_lane0_existing_path_roundtrip.log",
        "04_lane1_existing_path_roundtrip.log",
        "05_2lane_existing_path_roundtrip.log",
        "06_2lane_existing_path_short_stress.log",
        "07_fault_injection.log",
        "08_scope_boundary.log",
        "09_final_shutdown.log",
        "10_result_flags.txt",
        "12_counters.csv",
        "13_payload_matrix.csv",
        "14_fault_matrix.csv",
        "15_capability_scan.txt",
        "SHA256SUMS.txt",
        "summary.json",
        "next_step_report.md",
    )
    for name in required_files:
        path = report_dir / name
        ok = path.exists() and path.stat().st_size > 0
        lines.append(f"FILE_{name}={'PASS' if ok else 'MISSING'}")
        if not ok:
            blockers.append(f"FILE_MISSING:{name}")

    for key in ("NO_MANUAL_GATE_USED", "MANUAL_OBSERVATION_NOT_REQUIRED"):
        if flags.get(key) != "1":
            blockers.append(f"{key}_NOT_1")

    for key in (
        "SINGLE_BOARD_AUTO_SAFE_GATE_PASS",
        "PS_PL_REGISTER_STATUS_AUTO_PASS",
        "SINGLE_BOARD_LANE0_EXISTING_PATH_PASS",
        "SINGLE_BOARD_LANE1_EXISTING_PATH_PASS",
        "SINGLE_BOARD_2LANE_EXISTING_PATH_PASS",
        "SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS",
    ):
        if not value_ready(flags.get(key)):
            blockers.append(f"{key}_NOT_READY:{flags.get(key)}")

    if flags.get("SINGLE_BOARD_2LANE_SHORT_STRESS_PASS") not in READY_VALUES:
        blockers.append(f"SINGLE_BOARD_2LANE_SHORT_STRESS_PASS_NOT_READY:{flags.get('SINGLE_BOARD_2LANE_SHORT_STRESS_PASS')}")

    if flags.get("SINGLE_BOARD_2LANE_PL_INTERNAL_LOOPBACK_PASS") == "1":
        blockers.append("PL_INTERNAL_LOOPBACK_OVERCLAIMED")
    elif flags.get("SINGLE_BOARD_2LANE_PL_INTERNAL_LOOPBACK_PASS") not in BLOCKED_OR_SCOPED:
        blockers.append(
            "PL_INTERNAL_LOOPBACK_STATUS_UNEXPECTED:"
            + str(flags.get("SINGLE_BOARD_2LANE_PL_INTERNAL_LOOPBACK_PASS"))
        )

    if flags.get("SINGLE_BOARD_FAULT_INJECTION_PASS") == "1":
        blockers.append("FAULT_INJECTION_OVERCLAIMED")
    elif flags.get("SINGLE_BOARD_FAULT_INJECTION_PASS") not in BLOCKED_OR_SCOPED:
        blockers.append("FAULT_INJECTION_STATUS_UNEXPECTED:" + str(flags.get("SINGLE_BOARD_FAULT_INJECTION_PASS")))

    boundary_expected = {
        "REAL_BOARD_TCP_DHCP_PASS": "BLOCKED_NO_ETHERNET",
        "REAL_TWO_BOARD_END_TO_END_PASS": "NOT_APPLICABLE_SINGLE_BOARD",
        "REAL_EXTERNAL_TFDU_OPTICAL_LINK_PASS": "NOT_CLAIMED",
        "ROTATION_600RPM_2H_PASS": "BLOCKED_NO_ROTATION_TEST",
        "8LANE_RATE_ACCEPTANCE_PASS": "NOT_CLAIMED_2LANE_ONLY",
        "FINAL_TARGET_PASS": "0",
    }
    for key, expected in boundary_expected.items():
        value = flags.get(key)
        if value != expected:
            blockers.append(f"INVALID_FINAL_CLAIM:{key}={value}")

    final_shutdown = flags.get("FINAL_SHUTDOWN_EXIT")
    if mode == "APPLY":
        if final_shutdown != "0":
            blockers.append(f"FINAL_SHUTDOWN_EXIT_NOT_0:{final_shutdown}")
        shutdown_text = read_text(report_dir / "09_final_shutdown.log")
        if "TFDU_SHUTDOWN_PROGRAMMED" not in shutdown_text:
            blockers.append("FINAL_SHUTDOWN_MARKER_MISSING")
    else:
        if flags.get("DRY_RUN_NO_HARDWARE_ACTION") != "1":
            blockers.append("DRY_RUN_NO_HARDWARE_ACTION_NOT_1")

    all_apply_pass = (
        mode == "APPLY"
        and flags.get("SINGLE_BOARD_AUTO_SAFE_GATE_PASS") == "1"
        and flags.get("PS_PL_REGISTER_STATUS_AUTO_PASS") == "1"
        and flags.get("SINGLE_BOARD_LANE0_EXISTING_PATH_PASS") == "1"
        and flags.get("SINGLE_BOARD_LANE1_EXISTING_PATH_PASS") == "1"
        and flags.get("SINGLE_BOARD_2LANE_EXISTING_PATH_PASS") == "1"
        and flags.get("SINGLE_BOARD_2LANE_EXISTING_PATH_STRESS_PASS") == "1"
        and final_shutdown == "0"
    )
    dry_ready = mode == "DRY_RUN" and not blockers

    if all_apply_pass and not blockers:
        lines.append("SINGLE_BOARD_2LANE_EXISTING_PATH_GATE=PASS")
        lines.append("SINGLE_BOARD_2LANE_EXISTING_PATH_ACCEPTANCE_PASS=1")
        rc = 0
    elif dry_ready:
        lines.append("SINGLE_BOARD_2LANE_EXISTING_PATH_GATE=DRY_RUN_READY")
        lines.append("SINGLE_BOARD_2LANE_EXISTING_PATH_ACCEPTANCE_PASS=0")
        rc = 0
    else:
        lines.append("SINGLE_BOARD_2LANE_EXISTING_PATH_GATE=FAIL_OR_BLOCKED")
        for blocker in blockers:
            lines.append(f"BLOCKER={blocker}")
        lines.append("SINGLE_BOARD_2LANE_EXISTING_PATH_ACCEPTANCE_PASS=0")
        rc = 20

    lines.append("SINGLE_BOARD_2LANE_EXISTING_PATH_GATE_END")
    output = "\n".join(lines) + "\n"
    print(output, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8", newline="\n")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
