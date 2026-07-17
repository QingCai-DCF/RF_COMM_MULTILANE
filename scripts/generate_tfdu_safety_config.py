#!/usr/bin/env python3
"""Validate the canonical P8C safety configuration and generate consumers."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tfdu_safety.yaml"
GENERATED_JSON = ROOT / "config" / "generated" / "tfdu_safety_constants.json"
GENERATED_SVH = ROOT / "rtl" / "generated" / "tfdu_safety_config.svh"
GENERATED_PKG = ROOT / "rtl" / "generated" / "tfdu_safety_pkg.sv"
GENERATED_DOC = ROOT / "docs" / "generated" / "TFDU_SAFETY_CONSTANTS.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_and_validate() -> tuple[dict[str, Any], dict[str, int | str | bool | dict[str, Any]]]:
    data = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("config/tfdu_safety.yaml must contain a mapping")

    required = {
        "schema_version",
        "configuration_id",
        "canonical_clock_hz",
        "mode_strategy",
        "receiver_startup_us",
        "rolling_duty_window_us",
        "rolling_duty_hard_percent_strict_lt",
        "rolling_duty_design_percent_max",
        "long_term_duty_window_ms",
        "long_term_duty_target_percent_max",
        "max_continuous_txd_high_us",
        "kill_reasons",
        "global_permit",
        "physical_profiles",
        "hardware_followup",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"missing safety configuration keys: {missing}")

    if data["schema_version"] != 1:
        raise ValueError("unsupported TFDU safety schema_version")
    if data["mode_strategy"] != "static_high_speed":
        raise ValueError("P8C requires static_high_speed mode strategy")

    clock_hz = int(data["canonical_clock_hz"])
    startup_us = int(data["receiver_startup_us"])
    window_us = int(data["rolling_duty_window_us"])
    max_high_us = int(data["max_continuous_txd_high_us"])
    hard_percent = int(data["rolling_duty_hard_percent_strict_lt"])
    target_percent = int(data["rolling_duty_design_percent_max"])
    long_term_ms = int(data["long_term_duty_window_ms"])
    long_term_target_percent = int(data["long_term_duty_target_percent_max"])

    for label, product in {
        "WINDOW_CYCLES": clock_hz * window_us,
        "STARTUP_CYCLES": clock_hz * startup_us,
        "MAX_CONTINUOUS_CYCLES": clock_hz * max_high_us,
    }.items():
        if product % 1_000_000:
            raise ValueError(f"{label} conversion is not exactly divisible by 1_000_000")

    window_cycles = clock_hz * window_us // 1_000_000
    startup_cycles = clock_hz * startup_us // 1_000_000
    max_high_cycles = clock_hz * max_high_us // 1_000_000
    hard_max = (window_cycles * hard_percent - 1) // 100
    target_max = window_cycles * target_percent // 100
    long_term_cycles = clock_hz * long_term_ms // 1000

    if not (0 < target_percent < hard_percent < 100):
        raise ValueError("duty target must be positive and strictly below the hard percentage")
    if hard_max * 100 >= window_cycles * hard_percent:
        raise ValueError("strict hard-limit integer threshold is invalid")
    if target_max * 100 > window_cycles * target_percent:
        raise ValueError("target integer threshold is invalid")
    if max_high_us > 1:
        raise ValueError("max_continuous_txd_high_us must be <= 1")
    if long_term_target_percent > target_percent:
        raise ValueError("long-term target cannot exceed the rolling target")

    kill_reasons = data["kill_reasons"]
    expected_kill_names = [
        "NONE", "RESET_OR_FULL_SHUTDOWN", "GLOBAL_PERMIT_LOW", "NOT_ARMED",
        "FATAL_FAULT", "ILLEGAL_ONE_HOT", "INVALID_SELECTED_MODULE",
        "STALE_OR_INVALID_PATH_EPOCH", "STARTUP_NOT_COMPLETE",
        "DUTY_TARGET_THROTTLE", "DUTY_HARD_FAULT", "STUCK_HIGH_FAULT",
        "FRAME_NOT_ADMITTED", "SD_ACTIVE", "HISTORY_COOLDOWN",
        "PARTIAL_FRAME_ABORTED",
    ]
    if not isinstance(kill_reasons, dict) or list(kill_reasons) != expected_kill_names:
        raise ValueError("kill_reasons must contain the stable ordered P8C reason names")
    kill_reason_values = [int(kill_reasons[name]) for name in expected_kill_names]
    if kill_reason_values != list(range(len(expected_kill_names))) or max(kill_reason_values) > 31:
        raise ValueError("kill_reasons must use unique stable 5-bit values 0..15")

    permit = data["global_permit"]
    expected_permit = {
        "active_level": "high",
        "count_per_endpoint": 1,
        "power_up_default": "low",
        "reset_default": "low",
        "open_circuit_default": "low",
        "undriven_default": "low",
        "fpga_unconfigured_default": "low",
        "partial_power_default": "low",
        "reassert_auto_resume": False,
        "rtl_deassert_kill": "asynchronous_or_combinational",
        "software_writable": False,
    }
    for key, expected in expected_permit.items():
        if permit.get(key) != expected:
            raise ValueError(f"global_permit.{key} must be {expected!r}")
    assert_filter_cycles = int(permit.get("assert_filter_cycles", 0))
    if assert_filter_cycles < 2:
        raise ValueError("global_permit.assert_filter_cycles must be >= 2")

    profiles = data["physical_profiles"]
    expected_counts = {
        "Z7010_2LANE_DEV": 2,
        "Z7020_ROTATING_8LANE_MODEL": 8,
        "Z7020_FIXED_32MODULE_ACCOUNTING_MODEL": 32,
    }
    for name, count in expected_counts.items():
        if int(profiles.get(name, {}).get("physical_module_count", -1)) != count:
            raise ValueError(f"{name} must define {count} physical modules")
    hardware_followup = data["hardware_followup"]
    expected_followup = {
        "global_permit_board_pulldown_contract": "DEFINED",
        "z7010_global_permit_pin_freeze": "PENDING_P9_PIN_FREEZE",
        "global_permit_physical_fail_low": "PENDING_D17",
        "global_permit_external_buffer_kill_latency": "PENDING_D17",
        "global_permit_partial_power": "PENDING_D17",
        "tfdu_duty_external_measurement": "PENDING_P9_OR_LATER",
    }
    for name, expected in expected_followup.items():
        if hardware_followup.get(name) != expected:
            raise ValueError(f"hardware_followup.{name} must be {expected}")

    constants: dict[str, Any] = {
        "schema_version": 1,
        "configuration_id": data["configuration_id"],
        "source_path": "config/tfdu_safety.yaml",
        "source_sha256": sha256(CONFIG_PATH),
        "canonical_clock_hz": clock_hz,
        "receiver_startup_us": startup_us,
        "rolling_duty_window_us": window_us,
        "rolling_duty_hard_percent_strict_lt": hard_percent,
        "rolling_duty_design_percent_max": target_percent,
        "long_term_duty_window_ms": long_term_ms,
        "long_term_duty_target_percent_max": long_term_target_percent,
        "max_continuous_txd_high_us": max_high_us,
        "assert_filter_cycles": assert_filter_cycles,
        "window_cycles": window_cycles,
        "startup_cycles": startup_cycles,
        "max_continuous_cycles": max_high_cycles,
        "hard_max_high_cycles": hard_max,
        "target_max_high_cycles": target_max,
        "long_term_window_cycles": long_term_cycles,
        "kill_reasons": {name: int(value) for name, value in kill_reasons.items()},
        "physical_profiles": profiles,
        "hardware_followup": hardware_followup,
        "no_hardware": True,
    }
    return data, constants


def render_json(constants: dict[str, Any]) -> str:
    return json.dumps(constants, indent=2, sort_keys=True) + "\n"


def render_svh(constants: dict[str, Any]) -> str:
    return "\n".join(
        [
            "// Auto-generated from config/tfdu_safety.yaml; do not edit.",
            "`ifndef TFDU_SAFETY_CONFIG_SVH",
            "`define TFDU_SAFETY_CONFIG_SVH",
            f"`define TFDU_SAFETY_CANONICAL_CLOCK_HZ {constants['canonical_clock_hz']}",
            f"`define TFDU_SAFETY_RECEIVER_STARTUP_US {constants['receiver_startup_us']}",
            f"`define TFDU_SAFETY_ROLLING_WINDOW_US {constants['rolling_duty_window_us']}",
            f"`define TFDU_SAFETY_HARD_PERCENT_STRICT_LT {constants['rolling_duty_hard_percent_strict_lt']}",
            f"`define TFDU_SAFETY_TARGET_PERCENT_MAX {constants['rolling_duty_design_percent_max']}",
            f"`define TFDU_SAFETY_LONG_TERM_WINDOW_MS {constants['long_term_duty_window_ms']}",
            f"`define TFDU_SAFETY_LONG_TERM_TARGET_PERCENT_MAX {constants['long_term_duty_target_percent_max']}",
            f"`define TFDU_SAFETY_MAX_CONTINUOUS_HIGH_US {constants['max_continuous_txd_high_us']}",
            f"`define TFDU_SAFETY_ASSERT_FILTER_CYCLES {constants['assert_filter_cycles']}",
            f"`define TFDU_SAFETY_CANONICAL_WINDOW_CYCLES {constants['window_cycles']}",
            f"`define TFDU_SAFETY_CANONICAL_STARTUP_CYCLES {constants['startup_cycles']}",
            f"`define TFDU_SAFETY_CANONICAL_MAX_HIGH_CYCLES {constants['max_continuous_cycles']}",
            f"`define TFDU_SAFETY_CANONICAL_HARD_MAX_HIGH_CYCLES {constants['hard_max_high_cycles']}",
            f"`define TFDU_SAFETY_CANONICAL_TARGET_MAX_HIGH_CYCLES {constants['target_max_high_cycles']}",
            "`endif",
            "",
        ]
    )


def render_pkg(constants: dict[str, Any]) -> str:
    lines = [
            "// Auto-generated from config/tfdu_safety.yaml; do not edit.",
            "`timescale 1ns/1ps",
            "package tfdu_safety_pkg;",
            f"  localparam int unsigned CANONICAL_CLOCK_HZ = {constants['canonical_clock_hz']};",
            f"  localparam int unsigned RECEIVER_STARTUP_US = {constants['receiver_startup_us']};",
            f"  localparam int unsigned ROLLING_DUTY_WINDOW_US = {constants['rolling_duty_window_us']};",
            f"  localparam int unsigned HARD_PERCENT_STRICT_LT = {constants['rolling_duty_hard_percent_strict_lt']};",
            f"  localparam int unsigned TARGET_PERCENT_MAX = {constants['rolling_duty_design_percent_max']};",
            f"  localparam int unsigned LONG_TERM_WINDOW_MS = {constants['long_term_duty_window_ms']};",
            f"  localparam int unsigned LONG_TERM_TARGET_PERCENT_MAX = {constants['long_term_duty_target_percent_max']};",
            f"  localparam int unsigned MAX_CONTINUOUS_TXD_HIGH_US = {constants['max_continuous_txd_high_us']};",
            f"  localparam int unsigned GLOBAL_PERMIT_ASSERT_FILTER_CYCLES = {constants['assert_filter_cycles']};",
            f"  localparam int unsigned CANONICAL_WINDOW_CYCLES = {constants['window_cycles']};",
            f"  localparam int unsigned CANONICAL_STARTUP_CYCLES = {constants['startup_cycles']};",
            f"  localparam int unsigned CANONICAL_MAX_CONTINUOUS_CYCLES = {constants['max_continuous_cycles']};",
            f"  localparam int unsigned CANONICAL_HARD_MAX_HIGH_CYCLES = {constants['hard_max_high_cycles']};",
            f"  localparam int unsigned CANONICAL_TARGET_MAX_HIGH_CYCLES = {constants['target_max_high_cycles']};",
            "",
            "  typedef enum logic [4:0] {",
        ]
    reason_items = list(constants["kill_reasons"].items())
    for index, (name, value) in enumerate(reason_items):
        comma = "," if index + 1 < len(reason_items) else ""
        lines.append(f"    TX_KILL_{name} = 5'd{value}{comma}")
    lines += ["  } tx_kill_reason_t;", "endpackage", ""]
    return "\n".join(lines)


def render_doc(constants: dict[str, Any]) -> str:
    profiles = constants["physical_profiles"]
    lines = [
        "# Generated TFDU Safety Constants",
        "",
        "> Generated from `config/tfdu_safety.yaml`; do not edit by hand.",
        "",
        "```text",
        f"CONFIGURATION_ID: {constants['configuration_id']}",
        f"SOURCE_SHA256: {constants['source_sha256']}",
        f"CANONICAL_CLOCK_HZ: {constants['canonical_clock_hz']}",
        f"WINDOW_CYCLES: {constants['window_cycles']}",
        f"STARTUP_CYCLES: {constants['startup_cycles']}",
        f"MAX_CONTINUOUS_CYCLES: {constants['max_continuous_cycles']}",
        f"HARD_MAX_HIGH_CYCLES_STRICT_LT_20_PERCENT: {constants['hard_max_high_cycles']}",
        f"TARGET_MAX_HIGH_CYCLES_LE_18_PERCENT: {constants['target_max_high_cycles']}",
        f"GLOBAL_PERMIT_ASSERT_FILTER_CYCLES: {constants['assert_filter_cycles']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION: false",
        "HARDWARE_SCOPE_PROMOTED: false",
        "```",
        "",
        "| Profile | Physical modules | Banks | Modules per bank |",
        "|---|---:|---:|---:|",
    ]
    for name, profile in profiles.items():
        lines.append(
            f"| `{name}` | {profile['physical_module_count']} | {profile['bank_count']} | {profile['modules_per_bank']} |"
        )
    lines += ["", "| Kill reason | Value |", "|---|---:|"]
    for name, value in constants["kill_reasons"].items():
        lines.append(f"| `TX_KILL_{name}` | {value} |")
    lines += ["", "| Hardware follow-up | Status |", "|---|---|"]
    for name, value in constants["hardware_followup"].items():
        lines.append(f"| `{name}` | `{value}` |")
    return "\n".join(lines) + "\n"


def write_or_verify(path: Path, content: str, verify: bool) -> None:
    if verify:
        if not path.exists() or path.read_text(encoding="utf-8") != content:
            raise SystemExit(f"generated safety artifact is stale: {path.relative_to(ROOT)}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args(argv)
    _, constants = load_and_validate()
    outputs = {
        GENERATED_JSON: render_json(constants),
        GENERATED_SVH: render_svh(constants),
        GENERATED_PKG: render_pkg(constants),
        GENERATED_DOC: render_doc(constants),
    }
    for path, content in outputs.items():
        write_or_verify(path, content, args.verify)
    print("TFDU_SAFETY_CONFIG_STATUS=PASS")
    print(f"TFDU_SAFETY_CONFIG_SHA256={constants['source_sha256']}")
    print(f"TFDU_SAFETY_WINDOW_CYCLES={constants['window_cycles']}")
    print(f"TFDU_SAFETY_HARD_MAX_HIGH_CYCLES={constants['hard_max_high_cycles']}")
    print(f"TFDU_SAFETY_TARGET_MAX_HIGH_CYCLES={constants['target_max_high_cycles']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
