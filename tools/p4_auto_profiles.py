#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from p4_auto_lib import GENERATED, ROOT, active_hashes, rel, sha256_or_missing, write_json, write_markdown


PROFILE_NAMES = [
    "p4_auto_safe_idle_proxy",
    "p4_auto_tfdu_control_idle",
    "p4_auto_raw_pulse_l0",
    "p4_auto_raw_lane_matrix",
    "p4_auto_lane0_frame_crc",
    "p4_auto_lane0_ack_retry",
    "p4_auto_lane1_frame_crc",
    "p4_auto_lane1_ack_retry",
    "p4_auto_two_lane_minimal",
    "p4_auto_lane0_300s_soak",
    "p4_auto_two_lane_300s_soak",
]


def _base(stage: str, max_runtime: int, evidence_dir: str) -> dict:
    return {
        "stage": stage,
        "lane_mask": "0x0",
        "rx_lane_mask": "0x0",
        "ack_lane_mask": "0x0",
        "session": "0x2201",
        "max_runtime_sec": max_runtime,
        "shutdown_on_exit": True,
        "startup_wait_us": 500,
        "txd_stuck_high_max_us": 10,
        "absolute_txd_stuck_high_datasheet_us": 80,
        "low_duty_mode": True,
        "manual_intervention_required": False,
        "user_confirmed_supply_ok": True,
        "forbid_external_scope_claim": True,
        "ethernet_enabled": False,
        "rotation_enabled": False,
        "hardware_acceptance": "PENDING_HW_UNTIL_AUTHORIZED_P4_AUTO_RUN",
        "evidence_dir": evidence_dir,
    }


def profile_definitions() -> dict[str, dict]:
    profiles: dict[str, dict] = {}
    profiles["p4_auto_safe_idle_proxy"] = {
        **_base("SAFE_IDLE_DIRECT_PROXY", 300, "evidence/hardware/p4_auto/safe_idle_direct_proxy"),
        "mode_cmd": 1,
        "sd_cmd": 1,
        "txd_cmd": 0,
        "lane_enable": "0x0",
        "tx_enabled": False,
    }
    profiles["p4_auto_tfdu_control_idle"] = {
        **_base("TFDU_CONTROL_IDLE", 60, "evidence/hardware/p4_auto/tfdu_control_idle"),
        "lane_mask": "0x1",
        "rx_lane_mask": "0x1",
        "mode_cmd": 1,
        "sd_cmd": 0,
        "txd_cmd": 0,
        "tx_enabled": False,
    }
    profiles["p4_auto_raw_pulse_l0"] = {
        **_base("RAW_PULSE_SMOKE_L0", 30, "evidence/hardware/p4_auto/raw_pulse_smoke"),
        "lane_mask": "0x1",
        "rx_lane_mask": "0x1",
        "pulse_width_ns": 125,
        "pulse_gap_us": 10000,
        "pulse_count_start": 16,
        "pulse_count_max": 256,
        "ack_enabled": False,
    }
    profiles["p4_auto_raw_lane_matrix"] = {
        **_base("RAW_LANE_MATRIX", 60, "evidence/hardware/p4_auto/raw_lane_matrix"),
        "lane_mask": "0x3",
        "rx_lane_mask": "0x3",
        "directions": ["AB_L0", "BA_L0", "AB_L1", "BA_L1"],
        "pulse_width_ns": 125,
        "pulse_gap_us": 1000,
        "pulse_count_start": 64,
        "pulse_count_max": 1024,
        "ack_enabled": False,
        "lane1_reliable_enabled": False,
        "known_bad_raw_direction": "AB_L1",
    }
    profiles["p4_auto_lane0_frame_crc"] = {
        **_base("LANE0_FRAME_CRC", 60, "evidence/hardware/p4_auto/protocol_smoke"),
        "lane_mask": "0x1",
        "rx_lane_mask": "0x1",
        "ack_lane_mask": "0x0",
        "payload_lengths": [16, 64, 256],
        "fragment_retry_enabled": False,
    }
    profiles["p4_auto_lane0_ack_retry"] = {
        **_base("LANE0_ACK_RETRY", 120, "evidence/hardware/p4_auto/protocol_smoke"),
        "lane_mask": "0x1",
        "rx_lane_mask": "0x1",
        "ack_lane_mask": "0x1",
        "b_expected_a_lane_mask": "0x1",
        "max_retry_start": 2,
    }
    profiles["p4_auto_lane1_frame_crc"] = {
        **_base("LANE1_FRAME_CRC", 60, "evidence/hardware/p4_auto/protocol_smoke"),
        "lane_mask": "0x2",
        "rx_lane_mask": "0x2",
        "ack_lane_mask": "0x0",
        "requires": ["AB_L1_RAW_PASS", "BA_L1_RAW_PASS"],
    }
    profiles["p4_auto_lane1_ack_retry"] = {
        **_base("LANE1_ACK_RETRY", 120, "evidence/hardware/p4_auto/protocol_smoke"),
        "lane_mask": "0x2",
        "rx_lane_mask": "0x2",
        "ack_lane_mask": "0x2",
        "b_expected_a_lane_mask": "0x2",
        "requires": ["LANE1_FRAME_CRC_PASS"],
    }
    profiles["p4_auto_two_lane_minimal"] = {
        **_base("TWO_LANE_MINIMAL", 120, "evidence/hardware/p4_auto/protocol_smoke"),
        "lane_mask": "0x3",
        "rx_lane_mask": "0x3",
        "ack_lane_mask": "0x3",
        "b_expected_a_lane_mask": "0x3",
        "requires": ["LANE0_ACK_RETRY_PASS", "LANE1_ACK_RETRY_PASS"],
    }
    profiles["p4_auto_lane0_300s_soak"] = {
        **_base("LANE0_300S_SOAK", 360, "evidence/hardware/p4_auto/soak"),
        "lane_mask": "0x1",
        "rx_lane_mask": "0x1",
        "ack_lane_mask": "0x1",
        "test_duration_sec": 300,
        "requires": ["LANE0_ACK_RETRY_PASS"],
    }
    profiles["p4_auto_two_lane_300s_soak"] = {
        **_base("TWO_LANE_300S_SOAK", 360, "evidence/hardware/p4_auto/soak"),
        "lane_mask": "0x3",
        "rx_lane_mask": "0x3",
        "ack_lane_mask": "0x3",
        "test_duration_sec": 300,
        "requires": ["TWO_LANE_MINIMAL_PASS"],
    }
    return {f"profiles/{name}.json": payload for name, payload in profiles.items()}


def validate_profile(profile: dict) -> list[str]:
    required = [
        "stage",
        "lane_mask",
        "rx_lane_mask",
        "ack_lane_mask",
        "session",
        "max_runtime_sec",
        "shutdown_on_exit",
        "startup_wait_us",
        "txd_stuck_high_max_us",
        "low_duty_mode",
        "manual_intervention_required",
        "user_confirmed_supply_ok",
        "evidence_dir",
    ]
    errors: list[str] = [f"missing {key}" for key in required if key not in profile]
    if int(profile.get("startup_wait_us", 0)) < 500:
        errors.append("startup_wait_us must be >= 500")
    if int(profile.get("txd_stuck_high_max_us", 999)) > 80:
        errors.append("txd_stuck_high_max_us must be <= 80")
    if profile.get("shutdown_on_exit") is not True:
        errors.append("shutdown_on_exit must be true")
    if profile.get("manual_intervention_required") is not False:
        errors.append("manual_intervention_required must be false")
    if profile.get("user_confirmed_supply_ok") is not True:
        errors.append("user_confirmed_supply_ok must be true")
    if profile.get("ethernet_enabled") is not False:
        errors.append("ethernet_enabled must be false")
    if profile.get("rotation_enabled") is not False:
        errors.append("rotation_enabled must be false")
    if int(profile.get("max_runtime_sec", 0)) <= 0:
        errors.append("max_runtime_sec must be positive")
    return errors


def write_profiles() -> dict:
    failures = []
    written = []
    for relpath, profile in profile_definitions().items():
        errors = validate_profile(profile)
        if errors:
            failures.append({"profile": relpath, "errors": errors})
            continue
        write_json(ROOT / relpath, profile)
        written.append(relpath)
    result = "PASS" if not failures else "FAIL"
    hashes = active_hashes()
    lines = [
        f"P4_AUTO_PROFILES: {result}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
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
        lines.extend(["", "## Failures", "", "```json", json.dumps(failures, indent=2), "```"])
    write_markdown(
        GENERATED / "p4_auto_profiles_summary.md",
        "P4 Auto Profiles Summary",
        result,
        "P4_AUTO profiles satisfy bounded runtime and TFDU safety defaults" if result == "PASS" else "P4_AUTO profile validation failed",
        lines,
    )
    return {"P4_AUTO_PROFILES": result, "profiles": written, "failures": failures, "summary": rel(GENERATED / "p4_auto_profiles_summary.md")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate P4_AUTO profiles without touching hardware.")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = write_profiles()
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    return 0 if payload["P4_AUTO_PROFILES"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
