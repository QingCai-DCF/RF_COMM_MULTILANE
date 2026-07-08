#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTIVE_XDC = ROOT / "TFDU_VFIR_Client_Array" / "TFDU_VFIR_Client.srcs" / "constrs_1" / "new" / "PORT1.xdc"
IP_COPY_XDC = ROOT / "IPs" / "ip_ir_array" / "src" / "PORT1.xdc"
EXPECTED_BASELINE_ZIP_NAME = "consult_single_board_2lane_loopback_20260706_193943.zip"
EXPECTED_BASELINE_ZIP_SHA256 = "EDCDF2EE6E6C61451D058F67F3A60989D52082E1F19AB45C40AA30F41C4116B2"

REQUIRED_MANUAL_FIELDS = [
    "board_id",
    "operator",
    "observation_time",
    "board_power_current_limit_A",
    "board_current_idle_A",
    "board_temperature_start_C",
    "board_temperature_after_shutdown_C",
    "photo_board",
    "photo_tfdu_lanes",
    "photo_power_limit",
    "no_abnormal_current",
    "no_abnormal_heating",
    "hardware_not_moved",
    "ethernet_disconnected",
    "rotation_fixture_unavailable",
    "no_tx_data_sent_during_manual_observation",
]

TRUE_VALUES = {"1", "true", "yes", "pass", "ok"}
PLACEHOLDER_VALUES = {"", "<fill>", "<todo>", "todo", "tbd", "unknown", "na", "n/a"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check RF_COMM physical 2-lane static gate evidence.")
    parser.add_argument("report_dir", type=Path)
    parser.add_argument("--out", type=Path)
    return parser.parse_args()


def read_text(path: Path) -> str:
    try:
        data = path.read_bytes()
    except FileNotFoundError:
        return ""
    if not data:
        return ""
    encodings = ["utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "gb18030", "latin-1"]
    for encoding in encodings:
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        if "\x00" not in text[:200]:
            return text
    return data.decode("utf-8", errors="replace")


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest().upper()
    except FileNotFoundError:
        return "MISSING"


def parse_xdc_pins(path: Path) -> dict[str, str]:
    text = read_text(path)
    pins: dict[str, str] = {}
    pattern = re.compile(r"set_property\s+PACKAGE_PIN\s+(\S+)\s+\[get_ports\s+\{([^}]+)\}\]")
    for pin, port in pattern.findall(text):
        pins[port] = pin
    return pins


def add_pin_pair_lines(lines: list[str]) -> None:
    active_pins = parse_xdc_pins(ACTIVE_XDC)
    ip_copy_pins = parse_xdc_pins(IP_COPY_XDC)
    lines.append(f"ACTIVE_PROJECT_XDC={ACTIVE_XDC}")
    lines.append(f"ACTIVE_PROJECT_XDC_SHA256={sha256_file(ACTIVE_XDC)}")
    lines.append(f"NON_ACTIVE_IP_COPY_XDC={IP_COPY_XDC}")
    lines.append(f"NON_ACTIVE_IP_COPY_XDC_SHA256={sha256_file(IP_COPY_XDC)}")
    lines.append(f"XDC_ACTIVE_AND_IP_COPY_MATCH={int(active_pins == ip_copy_pins and bool(active_pins))}")
    if active_pins:
        lines.append(
            "ACTIVE_LANE0_A2B_PIN_PAIR="
            f"ir_tx_out_0[0]:{active_pins.get('ir_tx_out_0[0]', 'MISSING')}"
            f"->loop_rx_b0[0]:{active_pins.get('loop_rx_b0[0]', 'MISSING')}"
        )
        lines.append(
            "ACTIVE_LANE0_B2A_PIN_PAIR="
            f"loop_tx_b0[0]:{active_pins.get('loop_tx_b0[0]', 'MISSING')}"
            f"->ir_rx_in_0[0]:{active_pins.get('ir_rx_in_0[0]', 'MISSING')}"
        )
        lines.append(
            "ACTIVE_LANE1_A2B_PIN_PAIR="
            f"ir_tx_out_0[1]:{active_pins.get('ir_tx_out_0[1]', 'MISSING')}"
            f"->loop_rx_b0[1]:{active_pins.get('loop_rx_b0[1]', 'MISSING')}"
        )
        lines.append(
            "ACTIVE_LANE1_B2A_PIN_PAIR="
            f"loop_tx_b0[1]:{active_pins.get('loop_tx_b0[1]', 'MISSING')}"
            f"->ir_rx_in_0[1]:{active_pins.get('ir_rx_in_0[1]', 'MISSING')}"
        )


def parse_key_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = read_text(path)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    return value.strip().lower() in PLACEHOLDER_VALUES


def parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def check_contains(path: Path, patterns: list[str], label: str, lines: list[str], blockers: list[str]) -> None:
    text = read_text(path)
    if not text:
        blockers.append(f"{label}=MISSING:{path.name}")
        lines.append(f"{label}=MISSING")
        return
    missing = [pattern for pattern in patterns if pattern not in text]
    if missing:
        blockers.append(f"{label}=MISSING_PATTERN:{','.join(missing)}")
        lines.append(f"{label}=FAIL missing={','.join(missing)}")
        return
    lines.append(f"{label}=PASS")


def check_regex(path: Path, patterns: list[str], label: str, lines: list[str], blockers: list[str]) -> None:
    text = read_text(path)
    if not text:
        blockers.append(f"{label}=MISSING:{path.name}")
        lines.append(f"{label}=MISSING")
        return
    missing = [pattern for pattern in patterns if re.search(pattern, text, flags=re.MULTILINE) is None]
    if missing:
        blockers.append(f"{label}=MISSING_REGEX:{','.join(missing)}")
        lines.append(f"{label}=FAIL missing_regex={','.join(missing)}")
        return
    lines.append(f"{label}=PASS")


def check_baseline_zip_hash(report_dir: Path, lines: list[str], blockers: list[str]) -> None:
    path = report_dir / "baseline_zip_sha256.txt"
    text = read_text(path).strip()
    if not text:
        blockers.append("BASELINE_ZIP_HASH=MISSING:baseline_zip_sha256.txt")
        lines.append("BASELINE_ZIP_HASH=MISSING")
        return

    if "MISSING" in text.upper():
        blockers.append("BASELINE_ZIP_HASH=ZIP_MISSING:" + EXPECTED_BASELINE_ZIP_NAME)
        lines.append("BASELINE_ZIP_HASH=FAIL zip_missing")
        return

    match = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if match is None:
        blockers.append("BASELINE_ZIP_HASH=HASH_MISSING:baseline_zip_sha256.txt")
        lines.append("BASELINE_ZIP_HASH=FAIL hash_missing")
        return

    actual_hash = match.group(1).upper()
    if EXPECTED_BASELINE_ZIP_NAME not in text:
        blockers.append("BASELINE_ZIP_HASH=WRONG_ZIP_NAME:" + EXPECTED_BASELINE_ZIP_NAME)
        lines.append(f"BASELINE_ZIP_HASH=FAIL wrong_zip_name expected={EXPECTED_BASELINE_ZIP_NAME}")
        return

    if actual_hash != EXPECTED_BASELINE_ZIP_SHA256:
        blockers.append(
            "BASELINE_ZIP_HASH=MISMATCH:"
            + f"expected={EXPECTED_BASELINE_ZIP_SHA256},actual={actual_hash}"
        )
        lines.append(
            "BASELINE_ZIP_HASH=FAIL "
            + f"expected={EXPECTED_BASELINE_ZIP_SHA256} actual={actual_hash}"
        )
        return

    lines.append(f"BASELINE_ZIP_HASH=PASS hash={actual_hash}")


def check_manual(report_dir: Path, lines: list[str], blockers: list[str]) -> None:
    manual_path = report_dir / "manual_observation.txt"
    values = parse_key_values(manual_path)
    if not values:
        blockers.append("MANUAL_OBSERVATION=MISSING_OR_EMPTY")
        lines.append("MANUAL_OBSERVATION=BLOCKED_MISSING")
        return

    missing_fields = [field for field in REQUIRED_MANUAL_FIELDS if is_placeholder(values.get(field))]
    if missing_fields:
        blockers.append("MANUAL_OBSERVATION=MISSING_FIELDS:" + ",".join(missing_fields))
        lines.append("MANUAL_OBSERVATION=BLOCKED_MISSING_FIELDS fields=" + ",".join(missing_fields))
        return

    bool_fields = [
        "no_abnormal_current",
        "no_abnormal_heating",
        "hardware_not_moved",
        "ethernet_disconnected",
        "rotation_fixture_unavailable",
        "no_tx_data_sent_during_manual_observation",
    ]
    bad_bool_fields = [field for field in bool_fields if values.get(field, "").strip().lower() not in TRUE_VALUES]
    if bad_bool_fields:
        blockers.append("MANUAL_OBSERVATION=BAD_BOOLEAN_FIELDS:" + ",".join(bad_bool_fields))
        lines.append("MANUAL_OBSERVATION=BLOCKED_BAD_BOOLEAN fields=" + ",".join(bad_bool_fields))
        return

    numeric_fields = [
        "board_power_current_limit_A",
        "board_current_idle_A",
        "board_temperature_start_C",
        "board_temperature_after_shutdown_C",
    ]
    bad_numeric_fields = [field for field in numeric_fields if parse_float(values.get(field)) is None]
    if bad_numeric_fields:
        blockers.append("MANUAL_OBSERVATION=BAD_NUMERIC_FIELDS:" + ",".join(bad_numeric_fields))
        lines.append("MANUAL_OBSERVATION=BLOCKED_BAD_NUMERIC fields=" + ",".join(bad_numeric_fields))
        return

    missing_photos: list[str] = []
    for field in ("photo_board", "photo_tfdu_lanes", "photo_power_limit"):
        photo_path = report_dir / values[field]
        if not photo_path.exists() or photo_path.stat().st_size == 0:
            missing_photos.append(field)
    if missing_photos:
        blockers.append("MANUAL_OBSERVATION=MISSING_PHOTOS:" + ",".join(missing_photos))
        lines.append("MANUAL_OBSERVATION=BLOCKED_MISSING_PHOTOS fields=" + ",".join(missing_photos))
        return

    temp_start = parse_float(values.get("board_temperature_start_C"))
    temp_after = parse_float(values.get("board_temperature_after_shutdown_C"))
    temp_delta = 0.0 if temp_start is None or temp_after is None else temp_after - temp_start
    lines.append("MANUAL_OBSERVATION=PASS")
    lines.append(f"MANUAL_TEMP_DELTA_C={temp_delta:.2f}")


def main() -> int:
    args = parse_args()
    report_dir = args.report_dir.resolve()
    lines: list[str] = [
        "PHYSICAL_2LANE_STATIC_GATE_BEGIN",
        f"REPORT_DIR={report_dir}",
        "NO_HARDWARE_ACTION_BY_THIS_CHECK=1",
    ]
    blockers: list[str] = []
    add_pin_pair_lines(lines)

    if not report_dir.exists():
        lines.append("REPORT_DIR_EXISTS=0")
        blockers.append("REPORT_DIR_MISSING")
    else:
        lines.append("REPORT_DIR_EXISTS=1")

    required_files = [
        "target_plan.md",
        "project_constraints_snapshot.txt",
        "git_status_before_hw.txt",
        "worktree_before_hw.diff",
        "baseline_zip_sha256.txt",
    ]
    for name in required_files:
        path = report_dir / name
        if path.exists() and path.stat().st_size > 0:
            lines.append(f"FILE_{name}=PASS")
        else:
            lines.append(f"FILE_{name}=MISSING")
            blockers.append(f"FILE_MISSING:{name}")

    check_baseline_zip_hash(report_dir, lines, blockers)
    check_contains(
        report_dir / "01_preflight_jtag_uart.log",
        ["COM_PORT_PRESENT=1", "VIVADO_PREFLIGHT_EXIT=0", "HW_PREFLIGHT_ZYNQ", "HW_PREFLIGHT_RESULT PASS"],
        "PREFLIGHT_GATE",
        lines,
        blockers,
    )
    check_contains(
        report_dir / "08_final_shutdown.log",
        ["TFDU_SHUTDOWN_PROGRAMMED"],
        "FINAL_SHUTDOWN_GATE",
        lines,
        blockers,
    )
    check_contains(
        report_dir / "lane0_remap_dry_run.log",
        ["DRY_RUN_NO_XDC_REPLACED=1", "DRY_RUN_NO_BUILD_DONE=1", "DRY_RUN_NO_HARDWARE_PROGRAMMING=1", "LANE_REMAP_PROBE_RESULT=DRY_RUN_READY"],
        "LANE0_REMAP_DRY_RUN_GATE",
        lines,
        blockers,
    )
    check_contains(
        report_dir / "lane1_remap_dry_run.log",
        ["DRY_RUN_NO_XDC_REPLACED=1", "DRY_RUN_NO_BUILD_DONE=1", "DRY_RUN_NO_HARDWARE_PROGRAMMING=1", "LANE_REMAP_PROBE_RESULT=DRY_RUN_READY"],
        "LANE1_REMAP_DRY_RUN_GATE",
        lines,
        blockers,
    )
    check_contains(
        report_dir / "03_register_status_readonly_wrapper_dry_run.summary.txt",
        ["DRY_RUN_HOST_EXIT=0", "DRY_RUN_NO_FPGA_PROGRAMMING=1", "DRY_RUN_NO_PS_ELF_STARTED=1", "DRY_RUN_NO_TFDU_DRIVE=1", "P2_REGISTER_STATUS_READONLY_RESULT=DRY_RUN_READY"],
        "P2_READONLY_DRY_RUN_GATE",
        lines,
        blockers,
    )
    check_manual(report_dir, lines, blockers)

    if blockers:
        lines.append("SAFE_HW_BRINGUP_GATE=BLOCKED")
        lines.append("SAFE_HW_BRINGUP_PASS=0")
        for blocker in blockers:
            lines.append(f"BLOCKER={blocker}")
        rc = 20
    else:
        lines.append("SAFE_HW_BRINGUP_GATE=PASS")
        lines.append("SAFE_HW_BRINGUP_PASS=1")
        rc = 0

    lines.append("PHYSICAL_2LANE_STATIC_GATE_END")
    output = "\n".join(lines) + "\n"
    print(output, end="")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
