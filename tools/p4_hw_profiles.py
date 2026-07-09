#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from p4_hw_evidence import GENERATED, ROOT, active_hashes, rel, sha256_or_missing, write_json, write_markdown


REQUIRED_PROFILE_KEYS = [
    "profile_name",
    "lane_count",
    "enabled_lanes",
    "mode_strategy",
    "startup_wait_us",
    "txd_stuck_high_trip_us",
    "pulse_width_ns",
    "pulse_period_us",
    "max_burst_pulses",
    "max_runtime_sec",
    "shutdown_on_exit",
    "ack_enabled",
    "ethernet_enabled",
    "rotation_enabled",
]


def _common() -> dict:
    return {
        "mode_strategy": "static_mode_high",
        "startup_wait_us": 500,
        "txd_stuck_high_trip_us": 10,
        "absolute_datasheet_guard_us": 80,
        "pulse_width_ns": 125,
        "pulse_period_us": 1000,
        "max_burst_pulses": 100,
        "max_runtime_sec": 300,
        "shutdown_on_exit": True,
        "ethernet_enabled": False,
        "rotation_enabled": False,
        "no_autonomous_tx": True,
        "safe_idle_txd": 0,
        "safe_idle_sd": 1,
        "safe_idle_mode": 1,
        "hardware_acceptance": "PENDING_HW_UNTIL_AUTHORIZED_RUN",
    }


def profile_definitions() -> dict[str, dict]:
    safe_idle = {
        **_common(),
        "profile_name": "p4_safe_idle",
        "lane_count": 2,
        "enabled_lanes": [],
        "planned_lanes": [0, 1],
        "ack_enabled": False,
        "raw_pulse_enabled": False,
        "protocol_frame_crc_enabled": False,
        "protocol_ack_retry_enabled": False,
        "purpose": "Program or audit the safe-idle candidate only; no intentional TX.",
    }
    lane0 = {
        **_common(),
        "profile_name": "p4_lane0_safe_smoke",
        "lane_count": 1,
        "enabled_lanes": [0],
        "planned_lanes": [0],
        "ack_enabled": False,
        "raw_pulse_enabled": True,
        "protocol_frame_crc_enabled": True,
        "protocol_ack_retry_enabled": False,
        "payload_lane_mask": "0x00000001",
        "ack_lane_mask": "0x00000000",
        "rx_lane_mask": "0x00000001",
        "session": "0x2201",
        "payload_lengths": [16, 64, 255],
        "purpose": "Lane0 low-duty raw pulse and frame/CRC smoke; ACK remains disabled.",
    }
    lane_matrix = {
        **_common(),
        "profile_name": "p4_lane_matrix_safe_smoke",
        "lane_count": 2,
        "enabled_lanes": [0],
        "planned_lanes": [0, 1],
        "ack_enabled": False,
        "raw_pulse_enabled": True,
        "protocol_frame_crc_enabled": False,
        "protocol_ack_retry_enabled": False,
        "payload_lane_mask": "0x00000001",
        "ack_lane_mask": "0x00000000",
        "rx_lane_mask": "0x00000001",
        "lane1_policy": "blocked_pending_fresh_raw_pulse_frame_crc_ack_and_mask_readback",
        "known_bad_direction": "AB_L1",
        "purpose": "Raw matrix staging. Lane1 is planned but not enabled as reliable evidence.",
    }
    return {
        "profiles/p4_safe_idle.json": safe_idle,
        "profiles/p4_lane0_safe_smoke.json": lane0,
        "profiles/p4_lane_matrix_safe_smoke.json": lane_matrix,
    }


def validate_profile(profile: dict) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_PROFILE_KEYS:
        if key not in profile:
            errors.append(f"missing {key}")
    if profile.get("mode_strategy") != "static_mode_high":
        errors.append("mode_strategy must be static_mode_high")
    if int(profile.get("startup_wait_us", 0)) < 500:
        errors.append("startup_wait_us must be >= 500")
    if int(profile.get("txd_stuck_high_trip_us", 999)) > 10:
        errors.append("txd_stuck_high_trip_us must be <= 10")
    if int(profile.get("absolute_datasheet_guard_us", 999)) > 80:
        errors.append("absolute_datasheet_guard_us must be <= 80")
    if int(profile.get("pulse_width_ns", 999)) > 125:
        errors.append("pulse_width_ns must be <= 125")
    if int(profile.get("pulse_period_us", 0)) < 1000:
        errors.append("pulse_period_us must be >= 1000")
    if int(profile.get("max_burst_pulses", 9999)) > 100:
        errors.append("max_burst_pulses must be <= 100")
    if int(profile.get("max_runtime_sec", 9999)) > 300:
        errors.append("max_runtime_sec must be <= 300")
    if profile.get("shutdown_on_exit") is not True:
        errors.append("shutdown_on_exit must be true")
    if profile.get("ethernet_enabled") is not False:
        errors.append("ethernet_enabled must be false")
    if profile.get("rotation_enabled") is not False:
        errors.append("rotation_enabled must be false")
    if profile.get("safe_idle_txd") != 0:
        errors.append("safe_idle_txd must be 0")
    if profile.get("safe_idle_sd") != 1:
        errors.append("safe_idle_sd must be 1")
    if profile.get("safe_idle_mode") != 1:
        errors.append("safe_idle_mode must be 1")
    if 1 in profile.get("enabled_lanes", []) and "fresh_raw" not in profile.get("lane1_policy", ""):
        errors.append("lane1 cannot be enabled as reliable without fresh lane1 evidence policy")
    return errors


def write_profiles() -> dict:
    written = []
    failures = []
    for relpath, profile in profile_definitions().items():
        errors = validate_profile(profile)
        if errors:
            failures.append({"profile": relpath, "errors": errors})
            continue
        path = ROOT / relpath
        write_json(path, profile)
        written.append(relpath)
    return {
        "result": "PASS" if not failures else "FAIL",
        "written": written,
        "failures": failures,
    }


def safe_idle_audit() -> dict:
    profile_result = write_profiles()
    hashes = active_hashes()
    checks = {
        "profiles_valid": profile_result["result"] == "PASS",
        "active_xdc_present": (ROOT / "constraints" / "active" / "PORT1.generated.xdc").exists(),
        "pinmap_present": (ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv").exists(),
        "tfdu_contract_present": (ROOT / "docs" / "tfdu6102_safety_contract.md").exists(),
        "active_rtl_txd_guard_10us": "TX_STUCK_HIGH_LIMIT_US = 10" in (ROOT / "rtl" / "tfdu_lane_phy.sv").read_text(encoding="utf-8", errors="ignore"),
        "ps_profile_txd_guard_10us": ".stuck_high_limit_us = 10u" in (ROOT / "software" / "ps_driver" / "ir_profile.c").read_text(encoding="utf-8", errors="ignore"),
    }
    failures = [name for name, ok in checks.items() if not ok]
    result = "PASS" if not failures else "FAIL"
    lines = [
        f"P4_SAFE_IDLE_PROFILE_AUDIT: {result}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Profile Files",
        "",
        *(f"- `{item}` sha256=`{sha256_or_missing(ROOT / item)}`" for item in profile_result["written"]),
        "",
        "## Checks",
        "",
        *(f"- {name}: {'PASS' if ok else 'FAIL'}" for name, ok in checks.items()),
        "",
        "## Active Hashes",
        "",
        *(f"- {name}: `{value}`" for name, value in hashes.items()),
    ]
    if profile_result["failures"]:
        lines.extend(["", "## Profile Failures", "", "```json", json.dumps(profile_result["failures"], indent=2), "```"])
    write_markdown(
        GENERATED / "p4_safe_idle_profile_audit.md",
        "P4 Safe Idle Profile Audit",
        result,
        "P4 dry-run profiles satisfy safe-idle constraints" if result == "PASS" else "P4 profile or active source audit failed",
        lines,
    )
    return {
        "P4_SAFE_IDLE_PROFILE_AUDIT": result,
        "generated_profiles": profile_result["written"],
        "failures": failures + [failure["profile"] for failure in profile_result["failures"]],
        "summary": rel(GENERATED / "p4_safe_idle_profile_audit.md"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate and audit P4 safe hardware profiles without touching hardware.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = safe_idle_audit()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload["P4_SAFE_IDLE_PROFILE_AUDIT"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
