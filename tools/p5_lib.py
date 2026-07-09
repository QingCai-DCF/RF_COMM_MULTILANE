#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence" / "generated"
P5_DIR = ROOT / "evidence" / "hardware" / "p5"
P5_SIM_DIR = ROOT / "evidence" / "simulation" / "p5"
P5_PROFILES = ROOT / "profiles" / "p5"

PASS = "PASS"
FAIL = "FAIL"
PASS_WITH_NOTES = "PASS_WITH_NOTES"
PASS_WITH_SKIPS = "PASS_WITH_SKIPS"
SKIP = "SKIP_WITH_REASON"
PENDING_HW_NOT_EXECUTED = "PENDING_HW_NOT_EXECUTED"
NOT_RUN_OPTIONAL = "NOT_RUN_OPTIONAL"

P5_STAGE = "P5_2LANE_PROTOCOL_STABILIZATION"
PENDING_HW_LINE = "HARDWARE_ACCEPTANCE: PENDING_HW"
NO_HW_LINE = "NO_HARDWARE_ACTIONS_EXECUTED: true"

P5_CONTEXT = {
    "P4_HEAD": "4768ef76c1d9bc6042d4058f52eef5fc0da5ca01",
    "P4_RESULT_PACKAGE": "p4_auto_acceptance_results_20260709_181930.zip",
    "USER_CONFIRMED_SUPPLY_OK": True,
    "NETWORK_CABLE_CONNECTED": False,
    "HARDWARE_MOVEMENT_ALLOWED": False,
    "AVAILABLE_LANES": 2,
    "MAX_LANE_MASK": "0x3",
    "SESSION": "0x2201",
}

PAYLOAD_LENGTHS = [0, 1, 2, 3, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 247, 255, 256]
PAYLOAD_PATTERNS = ["zero", "ff", "aa55", "55aa", "counter8", "counter16", "walking1", "walking0", "prbs15"]
ALLOWED_MASKS = {"0x0", "0x1", "0x2", "0x3", 0, 1, 2, 3}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path | str) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def write_text(path: Path | str, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def write_json(path: Path | str, payload: dict | list) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def write_csv(path: Path | str, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def read_text(path: Path | str) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def load_json(path: Path | str) -> Any:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def json_from_stdout(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_or_missing(path: Path | str | None) -> str:
    if not path:
        return "MISSING"
    path = Path(path)
    if not path.exists() or not path.is_file():
        return "MISSING"
    return sha256(path)


def run_cmd(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError as exc:
        return {"cmd": " ".join(str(item) for item in cmd), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "timeout",
        }


def git_value(*args: str) -> str:
    result = run_cmd(["git", *args], timeout=30)
    return (result["stdout"] if result["returncode"] == 0 else result["stderr"] or result["stdout"]).strip()


def parse_marker_text(text: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("|"):
            continue
        separator = ":" if ":" in line else "=" if "=" in line else ""
        if not separator:
            continue
        key, value = line.split(separator, 1)
        key = key.strip().strip("-").strip()
        if not key:
            continue
        normalized_key = key.upper().replace("-", "_").replace(" ", "_")
        if normalized_key.replace("_", "").isalnum():
            markers[normalized_key] = value.strip().split()[0] if value.strip() else ""
    return markers


def parse_markers(path: Path | str) -> dict[str, str]:
    return parse_marker_text(read_text(path))


def ensure_dirs() -> None:
    for path in [
        GENERATED,
        P5_DIR,
        P5_DIR / "safe_idle_recheck",
        P5_DIR / "tfdu_control_idle_recheck",
        P5_DIR / "raw_lane_matrix",
        P5_DIR / "protocol" / "lane0_frame_crc_100",
        P5_DIR / "protocol" / "lane1_frame_crc_100",
        P5_DIR / "protocol" / "lane0_ack_retry_100",
        P5_DIR / "protocol" / "lane1_ack_retry_100",
        P5_DIR / "protocol" / "two_lane_minimal_100",
        P5_DIR / "payload_sweep" / "lane0",
        P5_DIR / "payload_sweep" / "lane1",
        P5_DIR / "payload_sweep" / "two_lane",
        P5_DIR / "mask_regression",
        P5_DIR / "retry_fault_injection_optional",
        P5_DIR / "soak" / "two_lane_30min",
        P5_SIM_DIR / "retry_fault_injection",
        P5_PROFILES,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def project_paths() -> dict[str, Path]:
    constraint_file = ROOT / "PROJECT_CONSTRAINTS.txt"
    for candidate in ROOT.glob("*.txt"):
        if candidate.name.startswith("\u9879\u76ee"):
            constraint_file = candidate
            break
    return {
        "constraint_file": constraint_file,
        "active_profile": ROOT / "board_profiles" / "ACTIVE_PROFILE.json",
        "pinmap": ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv",
        "active_xdc": ROOT / "constraints" / "active" / "PORT1.generated.xdc",
        "register_map": ROOT / "config" / "register_map" / "ir_axi_regs.yaml",
        "tfdu_safety_contract": ROOT / "docs" / "tfdu6102_safety_contract.md",
        "tfdu_safety_summary": ROOT / "docs" / "TFDU6102_SAFETY_SUMMARY.md",
        "shutdown_bitstream": ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit",
    }


def active_hashes() -> dict[str, str]:
    return {name: sha256_or_missing(path) for name, path in project_paths().items()}


def markdown_header(title: str, result: str, reason: str, *, no_hw: bool = True) -> list[str]:
    return [
        f"# {title}",
        "",
        f"generated_at_utc: {now_iso()}",
        f"repo: `{ROOT}`",
        f"HEAD: `{git_value('rev-parse', 'HEAD')}`",
        f"stage: {P5_STAGE}",
        f"result: {result}",
        f"reason: {reason}",
        f"hardware_actions_executed: {str(not no_hw).lower()}",
        "user_confirmed_supply_ok: true",
        "network_cable_connected: false",
        "hardware_movement_allowed: false",
        "available_lanes: 2",
        "shutdown_on_exit: required",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hw).lower()}",
        PENDING_HW_LINE,
        "",
    ]


def write_markdown(path: Path | str, title: str, result: str, reason: str, lines: list[str] | None = None, *, no_hw: bool = True) -> None:
    body = markdown_header(title, result, reason, no_hw=no_hw)
    if lines:
        body.extend(lines)
        body.append("")
    write_text(path, "\n".join(body))


def _base_profile(component: str, lane_mask: str, ack_lane_mask: str, max_runtime_sec: int, evidence_dir: str) -> dict[str, Any]:
    return {
        "stage": P5_STAGE,
        "component": component,
        "user_confirmed_supply_ok": True,
        "no_manual_power_measurement_required_in_p5": True,
        "network_cable_connected": False,
        "hardware_movement_allowed": False,
        "available_lanes": 2,
        "max_lane_mask": "0x3",
        "lane_mask": lane_mask,
        "rx_lane_mask": lane_mask,
        "ack_lane_mask": ack_lane_mask,
        "session": "0x2201",
        "shutdown_on_exit": True,
        "startup_wait_us_min": 500,
        "txd_stuck_high_guard": True,
        "txd_stuck_high_max_us": 80,
        "duty_window_guard": True,
        "ethernet_enabled": False,
        "rotation_enabled": False,
        "external_scope_claim_allowed": False,
        "manual_intervention_required": False,
        "max_runtime_sec": max_runtime_sec,
        "hardware_acceptance": "PENDING_HW_UNTIL_AUTHORIZED_P5_RUN",
        "evidence_dir": evidence_dir,
    }


def profile_definitions() -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = {
        "p5_safe_idle_recheck": {
            **_base_profile("SAFE_IDLE_RECHECK", "0x0", "0x0", 120, "evidence/hardware/p5/safe_idle_recheck"),
            "mode_proxy_expected": "high_when_applicable",
            "sd_proxy_expected": "shutdown_high",
            "txd_proxy_expected": 0,
        },
        "p5_tfdu_control_idle_recheck": {
            **_base_profile("TFDU_CONTROL_IDLE_RECHECK", "0x3", "0x0", 120, "evidence/hardware/p5/tfdu_control_idle_recheck"),
            "mode_proxy_expected": "high_speed",
            "sd_proxy_expected": "active_low_for_receive_active_idle",
            "txd_proxy_expected": 0,
        },
        "p5_raw_lane_matrix_fresh": {
            **_base_profile("RAW_LANE_MATRIX_FRESH", "0x3", "0x0", 300, "evidence/hardware/p5/raw_lane_matrix"),
            "directions": ["AB_L0", "BA_L0", "AB_L1", "BA_L1"],
            "remote_active_low_pulse_count_min": 1,
        },
        "p5_lane0_frame_crc_100": {
            **_base_profile("LANE0_FRAME_CRC_100", "0x1", "0x0", 180, "evidence/hardware/p5/protocol/lane0_frame_crc_100"),
            "frames_min": 100,
            "payload_patterns": ["counter8", "aa55", "ff", "zero", "prbs15"],
            "payload_lengths": [1, 16, 64, 128, 247, 255, 256],
            "ack_enabled": False,
        },
        "p5_lane1_frame_crc_100": {
            **_base_profile("LANE1_FRAME_CRC_100", "0x2", "0x0", 180, "evidence/hardware/p5/protocol/lane1_frame_crc_100"),
            "frames_min": 100,
            "payload_patterns": ["counter8", "aa55", "ff", "zero", "prbs15"],
            "payload_lengths": [1, 16, 64, 128, 247, 255, 256],
            "ack_enabled": False,
        },
        "p5_lane0_ack_retry_100": {
            **_base_profile("LANE0_ACK_RETRY_100", "0x1", "0x1", 240, "evidence/hardware/p5/protocol/lane0_ack_retry_100"),
            "frames_min": 100,
            "normal_no_fault_path": True,
            "max_retry": "project_known_good_value",
            "ack_timeout_readback_required": True,
            "guard_cycles_readback_required": True,
        },
        "p5_lane1_ack_retry_100": {
            **_base_profile("LANE1_ACK_RETRY_100", "0x2", "0x2", 240, "evidence/hardware/p5/protocol/lane1_ack_retry_100"),
            "frames_min": 100,
            "normal_no_fault_path": True,
            "max_retry": "project_known_good_value",
            "ack_timeout_readback_required": True,
            "guard_cycles_readback_required": True,
        },
        "p5_two_lane_minimal_100": {
            **_base_profile("TWO_LANE_MINIMAL_100", "0x3", "0x3", 300, "evidence/hardware/p5/protocol/two_lane_minimal_100"),
            "frames_per_lane_min": 100,
        },
        "p5_lane0_payload_sweep": {
            **_base_profile("LANE0_PAYLOAD_SWEEP", "0x1", "0x1", 900, "evidence/hardware/p5/payload_sweep/lane0"),
            "payload_lengths": PAYLOAD_LENGTHS,
            "payload_patterns": PAYLOAD_PATTERNS,
        },
        "p5_lane1_payload_sweep": {
            **_base_profile("LANE1_PAYLOAD_SWEEP", "0x2", "0x2", 900, "evidence/hardware/p5/payload_sweep/lane1"),
            "payload_lengths": PAYLOAD_LENGTHS,
            "payload_patterns": PAYLOAD_PATTERNS,
        },
        "p5_two_lane_payload_sweep": {
            **_base_profile("TWO_LANE_PAYLOAD_SWEEP", "0x3", "0x3", 1200, "evidence/hardware/p5/payload_sweep/two_lane"),
            "payload_lengths": PAYLOAD_LENGTHS,
            "payload_patterns": PAYLOAD_PATTERNS,
        },
        "p5_two_lane_mask_regression": {
            **_base_profile("TWO_LANE_MASK_REGRESSION", "0x3", "0x3", 300, "evidence/hardware/p5/mask_regression"),
            "positive_cases": [
                {"lane_mask": "0x1", "expected_mask": "0x1"},
                {"lane_mask": "0x2", "expected_mask": "0x2"},
                {"lane_mask": "0x3", "expected_mask": "0x3"},
            ],
            "negative_cases": [
                {"lane_mask": "0x1", "expected_mask": "0x3"},
                {"lane_mask": "0x2", "expected_mask": "0x3"},
                {"case": "session_mismatch"},
                {"case": "ack_lane_mask_mismatch"},
            ],
            "negative_cases_bounded": True,
        },
        "p5_retry_fault_injection_sim": {
            **_base_profile("RETRY_FAULT_INJECTION_SIM", "0x3", "0x3", 300, "evidence/simulation/p5/retry_fault_injection"),
            "simulation_only": True,
            "fault_cases": [
                "drop_every_10th_ack",
                "drop_first_ack_only",
                "drop_first_data_only",
                "force_crc_error_simulation_only",
                "force_lane0_disable_via_register",
                "force_lane1_disable_via_register",
            ],
        },
        "p5_retry_fault_injection_hw_optional": {
            **_base_profile("RETRY_FAULT_INJECTION_HW_OPTIONAL", "0x3", "0x3", 300, "evidence/hardware/p5/retry_fault_injection_optional"),
            "hardware_optional": True,
            "skip_if_no_hook": "SKIP_NO_HW_FAULT_INJECTION_HOOK",
        },
        "p5_two_lane_30min_soak": {
            **_base_profile("TWO_LANE_30MIN_SOAK", "0x3", "0x3", 1860, "evidence/hardware/p5/soak/two_lane_30min"),
            "test_duration_sec": 1800,
            "payload_pattern": "prbs15",
            "payload_length_preference": [247, 255, 256],
        },
        "p5_two_lane_2h_soak_optional": {
            **_base_profile("TWO_LANE_2H_SOAK_OPTIONAL", "0x3", "0x3", 7260, "evidence/hardware/p5/soak/two_lane_2h_optional"),
            "test_duration_sec": 7200,
            "optional": True,
            "run_only_after": "TWO_LANE_30MIN_SOAK_PASS",
        },
    }
    return {f"profiles/p5/{name}.json": payload for name, payload in profiles.items()}


def _mask_ok(value: Any) -> bool:
    if value in ALLOWED_MASKS:
        return True
    if isinstance(value, str):
        try:
            return int(value, 0) <= 0x3
        except ValueError:
            return False
    if isinstance(value, int):
        return value <= 0x3
    return False


def validate_profile(profile: dict[str, Any]) -> list[str]:
    required = [
        "stage",
        "user_confirmed_supply_ok",
        "network_cable_connected",
        "hardware_movement_allowed",
        "available_lanes",
        "session",
        "shutdown_on_exit",
        "startup_wait_us_min",
        "txd_stuck_high_guard",
        "duty_window_guard",
        "lane_mask",
        "ack_lane_mask",
        "max_runtime_sec",
        "evidence_dir",
    ]
    errors = [f"missing {key}" for key in required if key not in profile]
    if profile.get("stage") != P5_STAGE:
        errors.append("stage must be P5_2LANE_PROTOCOL_STABILIZATION")
    if profile.get("user_confirmed_supply_ok") is not True:
        errors.append("user_confirmed_supply_ok must be true")
    if profile.get("network_cable_connected") is not False:
        errors.append("network_cable_connected must be false")
    if profile.get("hardware_movement_allowed") is not False:
        errors.append("hardware_movement_allowed must be false")
    if profile.get("available_lanes") != 2:
        errors.append("available_lanes must be 2")
    if profile.get("session") != "0x2201":
        errors.append("session must be 0x2201")
    if profile.get("shutdown_on_exit") is not True:
        errors.append("shutdown_on_exit must be true")
    if int(profile.get("startup_wait_us_min", 0)) < 500:
        errors.append("startup_wait_us_min must be >= 500")
    if profile.get("txd_stuck_high_guard") is not True:
        errors.append("txd_stuck_high_guard must be true")
    if profile.get("duty_window_guard") is not True:
        errors.append("duty_window_guard must be true")
    if profile.get("ethernet_enabled") is not False:
        errors.append("ethernet_enabled must be false")
    if profile.get("rotation_enabled") is not False:
        errors.append("rotation_enabled must be false")
    if not _mask_ok(profile.get("lane_mask")):
        errors.append("lane_mask must be within 0x0..0x3")
    if not _mask_ok(profile.get("rx_lane_mask")):
        errors.append("rx_lane_mask must be within 0x0..0x3")
    if not _mask_ok(profile.get("ack_lane_mask")):
        errors.append("ack_lane_mask must be within 0x0..0x3")
    if int(profile.get("max_runtime_sec", 0)) <= 0:
        errors.append("max_runtime_sec must be positive")
    if profile.get("component", "").endswith("PAYLOAD_SWEEP"):
        if set(profile.get("payload_lengths", [])) < set(PAYLOAD_LENGTHS):
            errors.append("payload_sweep profile missing required payload lengths")
        if set(profile.get("payload_patterns", [])) < set(PAYLOAD_PATTERNS):
            errors.append("payload_sweep profile missing required payload patterns")
    return errors


def write_profiles() -> dict[str, Any]:
    ensure_dirs()
    failures = []
    written = []
    for relpath, profile in profile_definitions().items():
        errors = validate_profile(profile)
        if errors:
            failures.append({"profile": relpath, "errors": errors})
            continue
        write_json(ROOT / relpath, profile)
        written.append(relpath)
    result = PASS if not failures else FAIL
    hashes = active_hashes()
    lines = [
        f"P5_PROFILE_VALIDATION: {result}",
        NO_HW_LINE,
        PENDING_HW_LINE,
        "",
        "## Profiles",
        "",
        *(f"- `{item}` sha256=`{sha256_or_missing(ROOT / item)}`" for item in written),
        "",
        "## Active Inputs",
        "",
        *(f"- {name}: `{value}`" for name, value in hashes.items()),
    ]
    if failures:
        lines.extend(["", "## Failures", "", "```json", json.dumps(failures, indent=2, ensure_ascii=False), "```"])
    write_markdown(
        GENERATED / "p5_profiles_summary.md",
        "P5 Profiles Summary",
        result,
        "P5 profiles satisfy 2-lane stationary safety defaults" if result == PASS else "P5 profile validation failed",
        lines,
    )
    return {"P5_PROFILE_VALIDATION": result, "profiles": written, "failures": failures, "summary": rel(GENERATED / "p5_profiles_summary.md")}


def status_is_passish(value: str | None) -> bool:
    return bool(value) and (
        value.startswith("PASS")
        or value in {"PASS_WITH_DIRECT_SUMMARY", "PASS_WITH_HARDWARE_SUBDIR_EVIDENCE", "PASS_WITH_HARDWARE_SUBDIR_EVIDENCE_AND_STALE_GENERATED_SUMMARY"}
    )


def p5_hardware_pending_payload(component: str, evidence_dir: Path | str, summary_path: Path | str, reason: str) -> dict[str, Any]:
    evidence_dir = ROOT / evidence_dir if not Path(evidence_dir).is_absolute() else Path(evidence_dir)
    summary_path = ROOT / summary_path if not Path(summary_path).is_absolute() else Path(summary_path)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    marker = component.upper()
    lines = [
        f"{marker}: {PENDING_HW_NOT_EXECUTED}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        PENDING_HW_LINE,
        f"reason: {reason}",
        "",
        "## Boundary",
        "",
        "- No P5 hardware action was executed by this dry-run gate.",
        "- Existing P4 evidence is historical intake only and is not promoted to fresh P5 PASS.",
    ]
    write_markdown(summary_path, component.replace("_", " ").title(), PENDING_HW_NOT_EXECUTED, reason, lines)
    payload = {
        marker: PENDING_HW_NOT_EXECUTED,
        "reason": reason,
        "summary": rel(summary_path),
        "evidence_dir": rel(evidence_dir),
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    write_json(evidence_dir / "p5_pending_hw.json", payload)
    return payload
