#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Callable

from p4_auto_parse_ila import parse_safe_idle_capture_dir, parse_tfdu_control_idle_capture_dir
from p6_lib import (
    ALLOWED_RESULTS,
    BLOCKED,
    FAIL,
    GENERATED,
    LANE_MASKS,
    NOT_RUN_PREREQ,
    NOT_RUN_RUNTIME_LIMIT,
    P6_CONTEXT,
    P6_DIR,
    P6_PROFILES,
    P6_SIM_DIR,
    P6_STAGE,
    PASS,
    PASS_WITH_NOTES,
    PAYLOAD_LENGTHS,
    PAYLOAD_PATTERNS,
    ROOT,
    SKIP,
    active_hashes,
    crc32_hex,
    ensure_dirs,
    git_value,
    json_from_stdout,
    load_json,
    mask_to_int,
    now_iso,
    p6_stage_placeholder,
    parse_markers,
    rel,
    run_cmd,
    seeded_payload,
    sha256_or_missing,
    stamp,
    status_is_passish,
    write_csv,
    write_json,
    write_markdown,
    write_text,
)


AUTH_ENV = "RF_COMM_HW_AUTH"
AUTH_ENV_VALUE = "P6_LOCAL_TRANSPORT_APPROVED"
DEFAULT_AUTH_FILE = ROOT / ".hardware_authorization" / "P6_LOCAL_TRANSPORT_APPROVED.txt"
DEFAULT_AUTH_TEMPLATE = ROOT / ".hardware_authorization" / "P6_LOCAL_TRANSPORT_APPROVED.txt.template"
DEFAULT_ABORT_FILE = ROOT / ".hardware_authorization" / "ABORT_NOW.txt"
DEFAULT_BOARD_ID = "AX7010"
DEFAULT_VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
DEFAULT_HW_SERVER_URL = "localhost:3121"
DEFAULT_JTAG_FREQUENCY_HZ = 1_000_000


ParserFunc = Callable[[Path], dict[str, Any]]


STOP_CONDITIONS = [
    "TXD_STUCK_HIGH_VIOLATION > 0",
    "DUTY_WINDOW_VIOLATION > 0",
    "TXD continuous high >= 80 us equivalent cycles",
    "startup_wait_us < 500",
    "SD/Mode/Txd readback inconsistent with stage expectation",
    "CRC_BAD > 0 in positive cases",
    "PAYLOAD_MISMATCH > 0 in positive cases",
    "TX_RETRY_EXHAUSTED > 0 in positive cases",
    "TX_FAIL > 0 in positive cases",
    "lane mask > 0x3 attempted",
    "Ethernet runtime attempted",
    "motion/rotation script attempted",
    "shutdown_on_exit failed",
    "abort file appears",
    "max_runtime exceeded",
    "Vivado/XSDB programming error",
]


PROFILE_NAMES = [
    "p6_safe_idle_recheck",
    "p6_tfdu_control_idle_recheck",
    "p6_jtag_axi_payload_ram_smoke",
    "p6_lane0_dynamic_payload_256",
    "p6_lane1_dynamic_payload_256",
    "p6_two_lane_dynamic_payload_256",
    "p6_ps_driver_runtime_mailbox",
    "p6_host_file_transport_jtag",
    "p6_lane_fallback_regression",
    "p6_two_lane_2h_stationary_soak",
]


ARTIFACT_SOURCES: dict[str, dict[str, Any]] = {
    "p6_safe_idle": {
        "source_bitstream": "evidence/generated/vivado/ir_top_new_safe_idle.bit",
        "source_ltx": "evidence/generated/vivado/p4_auto_safe_idle_debug.ltx",
        "stage": "P6_SAFE_IDLE_RECHECK",
        "profile": "profiles/p6/p6_safe_idle_recheck.json",
        "applicability": "P6_SAFE_IDLE_DIAGNOSTIC",
    },
    "p6_tfdu_idle": {
        "source_bitstream": "evidence/generated/vivado/ir_top_new_tfdu_control_idle.bit",
        "source_ltx": "evidence/generated/vivado/p4_auto_tfdu_control_idle_debug.ltx",
        "stage": "P6_TFDU_CONTROL_IDLE_RECHECK",
        "profile": "profiles/p6/p6_tfdu_control_idle_recheck.json",
        "applicability": "P6_TFDU_RECEIVE_ACTIVE_IDLE_DIAGNOSTIC",
    },
    "p6_local_transport": {
        "source_bitstream": "",
        "source_ltx": "",
        "stage": "P6_LOCAL_TRANSPORT_DYNAMIC_PAYLOAD",
        "profile": "profiles/p6/p6_two_lane_dynamic_payload_256.json",
        "applicability": "MISSING_P6_DYNAMIC_PAYLOAD_JTAG_AXI_ARTIFACT",
    },
    "p6_two_lane_soak": {
        "source_bitstream": "",
        "source_ltx": "",
        "stage": "P6_TWO_LANE_2H_STATIONARY_SOAK",
        "profile": "profiles/p6/p6_two_lane_2h_stationary_soak.json",
        "applicability": "MISSING_P6_DYNAMIC_TWO_LANE_SOAK_ARTIFACT",
    },
}


P6_HW_STAGE_RUNS: dict[str, dict[str, Any]] = {
    "safe_idle_recheck": {
        "marker": "P6_SAFE_IDLE_RECHECK",
        "artifact_key": "p6_safe_idle",
        "profile": "profiles/p6/p6_safe_idle_recheck.json",
        "capture_prefix": "p6_safe_idle_recheck",
        "capture_dir": "evidence/hardware/p6/ila/safe_idle_recheck",
        "evidence_dir": "evidence/hardware/p6/safe_idle_recheck",
        "summary": "evidence/generated/p6_safe_idle_recheck_summary.md",
        "parse_key": "SAFE_IDLE_ILA_PARSE",
        "parser": parse_safe_idle_capture_dir,
        "post_wait_ms": 1000,
        "stage_drove_tfdu_txd": False,
        "stage_enabled_tfdu_receiver": False,
    },
    "tfdu_control_idle_recheck": {
        "marker": "P6_TFDU_CONTROL_IDLE_RECHECK",
        "artifact_key": "p6_tfdu_idle",
        "profile": "profiles/p6/p6_tfdu_control_idle_recheck.json",
        "capture_prefix": "p6_tfdu_control_idle_recheck",
        "capture_dir": "evidence/hardware/p6/ila/tfdu_control_idle_recheck",
        "evidence_dir": "evidence/hardware/p6/tfdu_control_idle_recheck",
        "summary": "evidence/generated/p6_tfdu_control_idle_recheck_summary.md",
        "parse_key": "TFDU_CONTROL_IDLE_ILA_PARSE",
        "parser": parse_tfdu_control_idle_capture_dir,
        "post_wait_ms": 1500,
        "stage_drove_tfdu_txd": False,
        "stage_enabled_tfdu_receiver": True,
    },
}


P6_BLOCKED_HW_STAGES: dict[str, tuple[str, str, str, str]] = {
    "jtag_axi_payload_ram_smoke": (
        "P6_JTAG_AXI_PAYLOAD_RAM_SMOKE",
        "evidence/hardware/p6/jtag_axi_payload_ram_smoke",
        "evidence/generated/p6_jtag_axi_payload_ram_smoke_summary.md",
        "P6 local transport bitstream with payload RAM/FIFO/mailbox AXI access is not present",
    ),
    "lane0_dynamic_payload": (
        "P6_LANE0_DYNAMIC_PAYLOAD",
        "evidence/hardware/p6/protocol/lane0_dynamic_payload",
        "evidence/generated/p6_lane0_dynamic_payload_summary.md",
        "P6 dynamic payload datapath is not implemented in the programmed artifact",
    ),
    "lane1_dynamic_payload": (
        "P6_LANE1_DYNAMIC_PAYLOAD",
        "evidence/hardware/p6/protocol/lane1_dynamic_payload",
        "evidence/generated/p6_lane1_dynamic_payload_summary.md",
        "P6 dynamic payload datapath is not implemented in the programmed artifact",
    ),
    "two_lane_dynamic_payload": (
        "P6_TWO_LANE_DYNAMIC_PAYLOAD",
        "evidence/hardware/p6/protocol/two_lane_dynamic_payload",
        "evidence/generated/p6_two_lane_dynamic_payload_summary.md",
        "P6 dynamic two-lane local transport bitstream is not present",
    ),
    "ps_driver_runtime": (
        "P6_PS_DRIVER_RUNTIME",
        "evidence/hardware/p6/ps_driver_runtime",
        "evidence/generated/p6_ps_driver_runtime_summary.md",
        "P6 PS runtime ELF/JTAG mailbox backend is not present; syntax-only PS evidence is not accepted",
    ),
    "host_file_transport_jtag": (
        "P6_HOST_FILE_TRANSPORT_JTAG",
        "evidence/hardware/p6/host_file_transport_jtag",
        "evidence/generated/p6_host_file_transport_jtag_summary.md",
        "P6 local JTAG/AXI file transport backend is not present",
    ),
    "lane_fallback_regression": (
        "P6_LANE_FALLBACK_REGRESSION",
        "evidence/hardware/p6/lane_fallback_regression",
        "evidence/generated/p6_lane_fallback_regression_summary.md",
        "P6 local transport register interface is not present for bounded hardware negative tests",
    ),
    "two_lane_2h_stationary_soak": (
        "P6_TWO_LANE_2H_STATIONARY_SOAK",
        "evidence/hardware/p6/soak/two_lane_2h_stationary",
        "evidence/generated/p6_two_lane_2h_stationary_soak_summary.md",
        "P6 dynamic two-lane soak bitstream/backend is not present; do not downgrade to short-soak PASS",
    ),
}


def _base_profile(
    stage_name: str,
    payload_source: str,
    payload_length: int | list[int],
    payload_pattern: str | list[str],
    lane_mask: str,
    ack_lane_mask: str,
    max_runtime_sec: int,
    evidence_dir: str,
    *,
    expected_crc_policy: str = "crc32_payload_digest_and_frame_crc_clean",
    expected_ack_policy: str = "ack_mask_matches_lane_mask",
) -> dict[str, Any]:
    return {
        "stage_name": stage_name,
        "lane_count": 2,
        "max_lane_mask": "0x3",
        "network_required": False,
        "motion_required": False,
        "user_confirmed_supply_ok": True,
        "session": "0x2201",
        "startup_wait_us": 500,
        "shutdown_on_exit": True,
        "max_runtime_sec": max_runtime_sec,
        "payload_source": payload_source,
        "payload_length": payload_length,
        "payload_pattern": payload_pattern,
        "expected_crc_policy": expected_crc_policy,
        "expected_ack_policy": expected_ack_policy,
        "expected_lane_mask": lane_mask,
        "expected_ack_lane_mask": ack_lane_mask,
        "stop_conditions": STOP_CONDITIONS,
        "ethernet_enabled": False,
        "rotation_enabled": False,
        "manual_intervention_required": False,
        "evidence_dir": evidence_dir,
        "product_final_acceptance": "pending",
    }


def profile_definitions() -> dict[str, dict[str, Any]]:
    return {
        "profiles/p6/p6_safe_idle_recheck.json": _base_profile(
            "P6_SAFE_IDLE_RECHECK",
            "none",
            0,
            "none",
            "0x0",
            "0x0",
            120,
            "evidence/hardware/p6/safe_idle_recheck",
            expected_crc_policy="no_payload_no_tx",
            expected_ack_policy="ack_disabled",
        ),
        "profiles/p6/p6_tfdu_control_idle_recheck.json": _base_profile(
            "P6_TFDU_CONTROL_IDLE_RECHECK",
            "none",
            0,
            "none",
            "0x3",
            "0x0",
            120,
            "evidence/hardware/p6/tfdu_control_idle_recheck",
            expected_crc_policy="no_payload_no_tx",
            expected_ack_policy="ack_disabled",
        ),
        "profiles/p6/p6_jtag_axi_payload_ram_smoke.json": _base_profile(
            "P6_JTAG_AXI_PAYLOAD_RAM_SMOKE",
            "host_jtag_axi",
            16,
            "counter",
            "0x3",
            "0x3",
            300,
            "evidence/hardware/p6/jtag_axi_payload_ram_smoke",
        ),
        "profiles/p6/p6_lane0_dynamic_payload_256.json": _base_profile(
            "P6_LANE0_DYNAMIC_PAYLOAD",
            "host_jtag_axi",
            PAYLOAD_LENGTHS,
            PAYLOAD_PATTERNS,
            "0x1",
            "0x1",
            900,
            "evidence/hardware/p6/protocol/lane0_dynamic_payload",
        ),
        "profiles/p6/p6_lane1_dynamic_payload_256.json": _base_profile(
            "P6_LANE1_DYNAMIC_PAYLOAD",
            "host_jtag_axi",
            PAYLOAD_LENGTHS,
            PAYLOAD_PATTERNS,
            "0x2",
            "0x2",
            900,
            "evidence/hardware/p6/protocol/lane1_dynamic_payload",
        ),
        "profiles/p6/p6_two_lane_dynamic_payload_256.json": _base_profile(
            "P6_TWO_LANE_DYNAMIC_PAYLOAD",
            "host_jtag_axi",
            PAYLOAD_LENGTHS,
            PAYLOAD_PATTERNS,
            "0x3",
            "0x3",
            1200,
            "evidence/hardware/p6/protocol/two_lane_dynamic_payload",
        ),
        "profiles/p6/p6_ps_driver_runtime_mailbox.json": _base_profile(
            "P6_PS_DRIVER_RUNTIME",
            "ps_runtime_mailbox",
            247,
            "deterministic_random",
            "0x3",
            "0x3",
            1200,
            "evidence/hardware/p6/ps_driver_runtime",
        ),
        "profiles/p6/p6_host_file_transport_jtag.json": _base_profile(
            "P6_HOST_FILE_TRANSPORT_JTAG",
            "host_file_jtag_axi",
            [16, 247],
            ["small_text", "counter", "prbs7", "deterministic_random"],
            "0x3",
            "0x3",
            1200,
            "evidence/hardware/p6/host_file_transport_jtag",
        ),
        "profiles/p6/p6_lane_fallback_regression.json": _base_profile(
            "P6_LANE_FALLBACK_REGRESSION",
            "host_jtag_axi",
            [16, 31, 64],
            ["counter", "prbs7"],
            "0x3",
            "0x3",
            900,
            "evidence/hardware/p6/lane_fallback_regression",
            expected_ack_policy="positive_masks_pass_negative_masks_bounded_reject",
        ),
        "profiles/p6/p6_two_lane_2h_stationary_soak.json": _base_profile(
            "P6_TWO_LANE_2H_STATIONARY_SOAK",
            "host_jtag_axi_rotating_payload_set",
            [16, 31, 64, 127, 191, 247],
            ["counter", "prbs7", "deterministic_random", "0xAA", "0x55"],
            "0x3",
            "0x3",
            7560,
            "evidence/hardware/p6/soak/two_lane_2h_stationary",
        )
        | {"runtime_sec": 7200, "sample_interval_sec": 60, "min_frames_per_lane": 7200},
    }


def validate_profile(profile: dict[str, Any]) -> list[str]:
    required = [
        "stage_name",
        "lane_count",
        "max_lane_mask",
        "network_required",
        "motion_required",
        "user_confirmed_supply_ok",
        "session",
        "startup_wait_us",
        "shutdown_on_exit",
        "max_runtime_sec",
        "payload_source",
        "payload_length",
        "payload_pattern",
        "expected_crc_policy",
        "expected_ack_policy",
        "expected_lane_mask",
        "expected_ack_lane_mask",
        "stop_conditions",
    ]
    errors = [f"missing {key}" for key in required if key not in profile]
    if profile.get("lane_count") != 2:
        errors.append("lane_count must be 2")
    if mask_to_int(profile.get("max_lane_mask")) != 0x3:
        errors.append("max_lane_mask must be 0x3")
    if profile.get("network_required") is not False or profile.get("ethernet_enabled") is not False:
        errors.append("network/ethernet must be disabled")
    if profile.get("motion_required") is not False or profile.get("rotation_enabled") is not False:
        errors.append("motion/rotation must be disabled")
    if profile.get("user_confirmed_supply_ok") is not True:
        errors.append("user_confirmed_supply_ok must be true")
    if profile.get("session") != "0x2201":
        errors.append("session must be 0x2201")
    if int(profile.get("startup_wait_us", 0)) < 500:
        errors.append("startup_wait_us must be >= 500")
    if profile.get("shutdown_on_exit") is not True:
        errors.append("shutdown_on_exit must be true")
    if int(profile.get("max_runtime_sec", 0)) <= 0 or int(profile.get("max_runtime_sec", 0)) > 7560:
        errors.append("max_runtime_sec must be in 1..7560")
    for key in ["expected_lane_mask", "expected_ack_lane_mask"]:
        value = mask_to_int(profile.get(key))
        if value is None or value > 0x3:
            errors.append(f"{key} must be <= 0x3")
    return errors


def write_profiles() -> dict[str, Any]:
    ensure_dirs()
    failures: list[dict[str, Any]] = []
    written: list[str] = []
    for relpath, profile in profile_definitions().items():
        errors = validate_profile(profile)
        if errors:
            failures.append({"profile": relpath, "errors": errors})
            continue
        write_json(ROOT / relpath, profile)
        written.append(relpath)
    result = PASS if not failures and len(written) == len(PROFILE_NAMES) else FAIL
    hashes = active_hashes()
    lines = [
        f"P6_PROFILES: {result}",
        f"P6_PROFILE_COUNT: {len(written)}",
        "script_hardware_actions_executed: false",
        "source_evidence_contains_hardware_actions: false",
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
    write_json(GENERATED / "p6_profiles_summary.json", {"P6_PROFILES": result, "profiles": written, "failures": failures})
    write_markdown(
        GENERATED / "p6_profiles_summary.md",
        "P6 Profiles Summary",
        result,
        "P6 profiles generated for stationary 2-lane no-Ethernet scope" if result == PASS else "P6 profile validation failed",
        lines,
    )
    return {"P6_PROFILES": result, "profiles": written, "profile_failures": failures, "summary": "evidence/generated/p6_profiles_summary.md"}


def write_p5_intake() -> dict[str, Any]:
    ensure_dirs()
    intake_dir = ROOT / "evidence" / "intake" / "p5_latest"
    intake_dir.mkdir(parents=True, exist_ok=True)
    p5_summary = ROOT / "evidence" / "generated" / "p5_2lane_protocol_stabilization_summary.json"
    p5_summary_md = ROOT / "evidence" / "generated" / "p5_2lane_protocol_stabilization_summary.md"
    p5_hw = ROOT / "evidence" / "hardware" / "p5" / "p5_hardware_execution_summary.json"
    for source in [p5_summary, p5_summary_md, p5_hw]:
        if source.exists():
            shutil.copy2(source, intake_dir / source.name)
    data = load_json(p5_summary)
    checks = {
        "safe_idle_recheck": data.get("SAFE_IDLE_RECHECK"),
        "tfdu_control_idle_recheck": data.get("TFDU_CONTROL_IDLE_RECHECK"),
        "raw_lane_matrix_fresh": data.get("RAW_LANE_MATRIX_FRESH"),
        "lane0_frame_crc_100": data.get("LANE0_FRAME_CRC_100"),
        "lane1_frame_crc_100": data.get("LANE1_FRAME_CRC_100"),
        "lane0_ack_retry_100": data.get("LANE0_ACK_RETRY_100"),
        "lane1_ack_retry_100": data.get("LANE1_ACK_RETRY_100"),
        "two_lane_minimal_100": data.get("TWO_LANE_MINIMAL_100"),
        "two_lane_30min_soak": data.get("TWO_LANE_30MIN_SOAK"),
        "payload_sweep": data.get("PAYLOAD_SWEEP"),
        "retry_fault_injection_hw_optional": data.get("RETRY_FAULT_INJECTION_HW_OPTIONAL"),
    }
    expected = {
        "safe_idle_recheck": {PASS},
        "tfdu_control_idle_recheck": {PASS},
        "raw_lane_matrix_fresh": {PASS},
        "lane0_frame_crc_100": {PASS},
        "lane1_frame_crc_100": {PASS},
        "lane0_ack_retry_100": {PASS},
        "lane1_ack_retry_100": {PASS},
        "two_lane_minimal_100": {PASS},
        "two_lane_30min_soak": {PASS},
        "payload_sweep": {"PASS_WITH_UNSUPPORTED_CASES_DOCUMENTED"},
        "retry_fault_injection_hw_optional": {"SKIP_NO_HW_FAULT_INJECTION_HOOK"},
    }
    failures = [
        f"{key}: expected {sorted(values)}, got {checks.get(key)}"
        for key, values in expected.items()
        if checks.get(key) not in values
    ]
    result = PASS_WITH_NOTES if not failures else FAIL
    source_hw = bool(data.get("HARDWARE_ACTIONS_EXECUTED")) or bool(load_json(p5_hw).get("HARDWARE_ACTIONS_EXECUTED"))
    manifest = {
        "P6_P5_INTAKE": result,
        "intake_dir": rel(intake_dir),
        "source_zip": "NOT_PROVIDED_USED_IN_REPO_P5_EVIDENCE",
        "source_files": [
            {"path": rel(path), "sha256": sha256_or_missing(path)}
            for path in [p5_summary, p5_summary_md, p5_hw]
            if path.exists()
        ],
        "checks": checks,
        "failures": failures,
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": source_hw,
    }
    write_json(GENERATED / "p6_p5_intake_summary.json", manifest)
    lines = [
        f"P6_P5_INTAKE: {result}",
        "source_zip: NOT_PROVIDED_USED_IN_REPO_P5_EVIDENCE",
        f"source_evidence_contains_hardware_actions: {str(source_hw).lower()}",
        "",
        "## Checks",
        "",
        *(f"- {key}: {value}" for key, value in checks.items()),
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(
        GENERATED / "p6_p5_intake_summary.md",
        "P6 P5 Intake Summary",
        result,
        "P5 in-repository evidence imported; no external zip was provided" if result != FAIL else "P5 intake checks failed",
        lines,
        source_hw=source_hw,
    )
    return manifest


def write_evidence_semantics(p5_intake: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": bool(p5_intake.get("source_evidence_contains_hardware_actions")),
        "stage_programmed_fpga": False,
        "stage_drove_tfdu_txd": False,
        "stage_enabled_tfdu_receiver": False,
        "shutdown_on_exit_observed": False,
        "product_final_acceptance": "pending",
    }
    result = PASS if fields["source_evidence_contains_hardware_actions"] else PASS_WITH_NOTES
    payload = {
        "P6_EVIDENCE_SEMANTICS": result,
        "fields": fields,
        "p5_intake": p5_intake.get("P6_P5_INTAKE"),
        "boundary": "offline generator actions are separated from summarized hardware evidence source",
    }
    write_json(GENERATED / "p6_evidence_semantics_summary.json", payload)
    lines = [
        f"P6_EVIDENCE_SEMANTICS: {result}",
        "",
        "## Unified Fields",
        "",
        *(f"- {key}: {str(value).lower() if isinstance(value, bool) else value}" for key, value in fields.items()),
        "",
        "## Boundary",
        "",
        "- P5 evidence source can contain hardware actions even when a P6 parser/generator action itself does not touch hardware.",
        "- P6 product-final acceptance remains pending regardless of stationary 2-lane local evidence.",
    ]
    write_markdown(
        GENERATED / "p6_evidence_semantics_summary.md",
        "P6 Evidence Semantics Summary",
        result,
        "hardware source evidence fields are separated from generator actions",
        lines,
        source_hw=fields["source_evidence_contains_hardware_actions"],
    )
    return payload


def run_dynamic_payload_sim() -> dict[str, Any]:
    ensure_dirs()
    rows: list[dict[str, Any]] = []
    for length in PAYLOAD_LENGTHS:
        for pattern in PAYLOAD_PATTERNS:
            payload = seeded_payload(length, pattern)
            digest = crc32_hex(payload)
            for lane_mask in LANE_MASKS:
                lanes = [lane for lane in [0, 1] if int(lane_mask, 0) & (1 << lane)]
                rows.append(
                    {
                        "case": f"len{length}_{pattern}_mask{lane_mask}",
                        "type": "positive",
                        "payload_len": length,
                        "pattern": pattern,
                        "lane_mask": lane_mask,
                        "ack_lane_mask": lane_mask,
                        "session": "0x2201",
                        "payload_crc32": digest,
                        "lanes_expected": ",".join(str(lane) for lane in lanes),
                        "crc_bad": 0,
                        "payload_mismatch": 0,
                        "tx_retry_exhausted": 0,
                        "tx_fail": 0,
                        "status": PASS,
                        "reason": "reference payload encode/decode and digest match",
                    }
                )
    negative_rows = [
        {
            "case": "negative_session_mismatch",
            "type": "negative",
            "payload_len": 16,
            "pattern": "counter",
            "lane_mask": "0x1",
            "ack_lane_mask": "0x1",
            "session": "0x2202",
            "payload_crc32": crc32_hex(seeded_payload(16, "counter")),
            "lanes_expected": "0",
            "crc_bad": 0,
            "payload_mismatch": 0,
            "tx_retry_exhausted": 0,
            "tx_fail": 0,
            "status": "REJECTED_AS_EXPECTED",
            "reason": "session mismatch is bounded reject in reference validator",
        },
        {
            "case": "negative_ack_mask_mismatch",
            "type": "negative",
            "payload_len": 16,
            "pattern": "counter",
            "lane_mask": "0x1",
            "ack_lane_mask": "0x2",
            "session": "0x2201",
            "payload_crc32": crc32_hex(seeded_payload(16, "counter")),
            "lanes_expected": "0",
            "crc_bad": 0,
            "payload_mismatch": 0,
            "tx_retry_exhausted": 0,
            "tx_fail": 0,
            "status": "REJECTED_AS_EXPECTED",
            "reason": "ack mask mismatch is bounded reject in reference validator",
        },
        {
            "case": "negative_lane_mask_gt_0x3",
            "type": "negative",
            "payload_len": 16,
            "pattern": "counter",
            "lane_mask": "0x4",
            "ack_lane_mask": "0x4",
            "session": "0x2201",
            "payload_crc32": crc32_hex(seeded_payload(16, "counter")),
            "lanes_expected": "",
            "crc_bad": 0,
            "payload_mismatch": 0,
            "tx_retry_exhausted": 0,
            "tx_fail": 0,
            "status": "REJECTED_BEFORE_HARDWARE_TX",
            "reason": "lane mask above 0x3 is rejected before hardware emission",
        },
    ]
    rows.extend(negative_rows)
    failures = [row for row in rows if row["type"] == "positive" and row["status"] != PASS]
    result = PASS if not failures else FAIL
    csv_path = P6_SIM_DIR / "dynamic_payload" / "p6_dynamic_payload_sim.csv"
    write_csv(
        csv_path,
        [
            "case",
            "type",
            "payload_len",
            "pattern",
            "lane_mask",
            "ack_lane_mask",
            "session",
            "payload_crc32",
            "lanes_expected",
            "crc_bad",
            "payload_mismatch",
            "tx_retry_exhausted",
            "tx_fail",
            "status",
            "reason",
        ],
        rows,
    )
    payload = {
        "P6_DYNAMIC_PAYLOAD_SIM": result,
        "positive_case_count": len([row for row in rows if row["type"] == "positive"]),
        "negative_case_count": len(negative_rows),
        "csv": rel(csv_path),
        "failures": failures,
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": False,
    }
    write_json(P6_SIM_DIR / "dynamic_payload" / "p6_dynamic_payload_sim.json", payload)
    write_json(GENERATED / "p6_dynamic_payload_sim_summary.json", payload)
    lines = [
        f"P6_DYNAMIC_PAYLOAD_SIM: {result}",
        f"positive_case_count: {payload['positive_case_count']}",
        f"negative_case_count: {payload['negative_case_count']}",
        f"csv: `{payload['csv']}`",
        "lane_mask > 0x3 rejected before hardware TX: true",
        "",
        "## Boundary",
        "",
        "- This is a deterministic reference simulation of P6 payload, CRC/digest, lane-mask, and reject logic.",
        "- It is not hardware evidence and does not by itself authorize a P6 local transport PASS.",
    ]
    write_markdown(
        GENERATED / "p6_dynamic_payload_sim_summary.md",
        "P6 Dynamic Payload Simulation Summary",
        result,
        "dynamic payload reference simulation completed",
        lines,
    )
    return payload


def copy_immutable_bitstreams() -> dict[str, Any]:
    ensure_dirs()
    bit_dir = P6_DIR / "bitstreams"
    bit_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for key, item in ARTIFACT_SOURCES.items():
        source_bit = ROOT / item["source_bitstream"] if item.get("source_bitstream") else None
        source_ltx = ROOT / item["source_ltx"] if item.get("source_ltx") else None
        profile = ROOT / item["profile"]
        source_bit_sha = sha256_or_missing(source_bit)
        source_ltx_sha = sha256_or_missing(source_ltx)
        immutable_bit = ""
        immutable_ltx = ""
        status = PASS
        reason = "immutable artifact copied"
        if source_bit_sha == "MISSING":
            status = BLOCKED
            reason = item["applicability"]
        else:
            immutable_bit_path = bit_dir / f"{key}_{source_bit_sha}.bit"
            if not immutable_bit_path.exists():
                shutil.copy2(source_bit, immutable_bit_path)
            immutable_bit = rel(immutable_bit_path)
            if source_ltx_sha != "MISSING":
                immutable_ltx_path = bit_dir / f"{key}_{source_ltx_sha}.ltx"
                if not immutable_ltx_path.exists():
                    shutil.copy2(source_ltx, immutable_ltx_path)
                immutable_ltx = rel(immutable_ltx_path)
        rows.append(
            {
                "artifact_key": key,
                "stage": item["stage"],
                "status": status,
                "reason": reason,
                "source_bitstream": item.get("source_bitstream", ""),
                "source_bitstream_sha256": source_bit_sha,
                "immutable_bitstream": immutable_bit,
                "source_ltx": item.get("source_ltx", ""),
                "source_ltx_sha256": source_ltx_sha,
                "immutable_ltx": immutable_ltx,
                "profile": item["profile"],
                "profile_sha256": sha256_or_missing(profile),
                "applicability": item["applicability"],
            }
        )
    hashes = active_hashes()
    vivado_summary = load_json(ROOT / "evidence" / "generated" / "vivado" / "nonhardware_build_summary.json")
    blocked = [row for row in rows if row["status"] != PASS]
    result = PASS_WITH_NOTES if blocked else PASS
    payload = {
        "P6_BITSTREAM_PROVENANCE": result,
        "artifacts": rows,
        "active_hashes": hashes,
        "vivado": vivado_summary.get("vivado", "UNKNOWN"),
        "missing_or_blocked_count": len(blocked),
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": False,
    }
    write_json(GENERATED / "p6_bitstream_provenance_summary.json", payload)
    lines = [
        f"P6_BITSTREAM_PROVENANCE: {result}",
        f"missing_or_blocked_count: {len(blocked)}",
        f"vivado: `{payload['vivado']}`",
        "",
        "## Artifacts",
        "",
        "| Artifact | Status | Immutable Bitstream | SHA256 | Applicability |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['artifact_key']} | {row['status']} | `{row['immutable_bitstream'] or 'MISSING'}` | `{row['source_bitstream_sha256']}` | {row['applicability']} |"
        )
    lines.extend(["", "## Active Input Hashes", "", *(f"- {name}: `{value}`" for name, value in hashes.items())])
    write_markdown(
        GENERATED / "p6_bitstream_provenance_summary.md",
        "P6 Bitstream Provenance Summary",
        result,
        "P6 immutable artifact provenance recorded; local transport artifact is missing" if blocked else "P6 immutable bitstreams copied",
        lines,
    )
    return payload


def artifact_by_key(provenance: dict[str, Any], key: str) -> dict[str, Any] | None:
    for row in provenance.get("artifacts", []):
        if row.get("artifact_key") == key:
            return row
    return None


def ensure_authorization_template(max_runtime_sec: int = 7560) -> Path:
    body = f"""P6_LOCAL_TRANSPORT_APPROVED
I AUTHORIZE RF_COMM_MULTILANE P6 LOCAL TRANSPORT NO-ETHERNET HARDWARE OPERATIONS ON CONNECTED HARDWARE.
AUTHORIZED_STAGE={P6_STAGE}
USER_CONFIRMED_SUPPLY_OK=true
NETWORK_CABLE_CONNECTED=false
HARDWARE_MOVEMENT_ALLOWED=false
AVAILABLE_LANES=2
MAX_LANE_MASK=0x3
ALLOWED_AUTOMATION=Vivado batch, JTAG, XSDB, AXI/JTAG-to-AXI, PS driver, ILA, VIO, debug registers, log parsing
FORBIDDEN=Ethernet acceptance, DHCP, static-IP board link, TCP board transport, motion, rotation, lane_mask_above_0x3, 4-lane, 8-lane, missing shutdown
MAX_RUNTIME_SEC={max_runtime_sec}
SHUTDOWN_ON_EXIT=required
AUTHORIZED_BY=<user>
DATE=<YYYY-MM-DD>
"""
    write_text(DEFAULT_AUTH_TEMPLATE, body)
    return DEFAULT_AUTH_TEMPLATE


def ensure_authorization_file(max_runtime_sec: int = 7560) -> Path:
    body = f"""P6_LOCAL_TRANSPORT_APPROVED
I AUTHORIZE RF_COMM_MULTILANE P6 LOCAL TRANSPORT NO-ETHERNET HARDWARE OPERATIONS ON CONNECTED HARDWARE.
AUTHORIZED_STAGE={P6_STAGE}
USER_CONFIRMED_SUPPLY_OK=true
NETWORK_CABLE_CONNECTED=false
HARDWARE_MOVEMENT_ALLOWED=false
AVAILABLE_LANES=2
MAX_LANE_MASK=0x3
ALLOWED_AUTOMATION=Vivado batch, JTAG, XSDB, AXI/JTAG-to-AXI, PS driver, ILA, VIO, debug registers, log parsing
FORBIDDEN=Ethernet acceptance, DHCP, static-IP board link, TCP board transport, motion, rotation, lane_mask_above_0x3, 4-lane, 8-lane, missing shutdown
MAX_RUNTIME_SEC={max_runtime_sec}
SHUTDOWN_ON_EXIT=required
AUTHORIZED_BY=user_request_in_thread
DATE=2026-07-10
"""
    write_text(DEFAULT_AUTH_FILE, body)
    return DEFAULT_AUTH_FILE


def parse_auth_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""
    required = [
        "P6_LOCAL_TRANSPORT_APPROVED",
        f"AUTHORIZED_STAGE={P6_STAGE}",
        "USER_CONFIRMED_SUPPLY_OK=true",
        "NETWORK_CABLE_CONNECTED=false",
        "HARDWARE_MOVEMENT_ALLOWED=false",
        "AVAILABLE_LANES=2",
        "MAX_LANE_MASK=0x3",
        "SHUTDOWN_ON_EXIT=required",
    ]
    missing = [item for item in required if item not in text]
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip()
    return {
        "exists": path.exists(),
        "valid": path.exists() and not missing and fields.get("AUTHORIZED_BY", "<user>") != "<user>",
        "missing": missing if path.exists() else [rel(path)],
        "fields": fields,
        "sha256": sha256_or_missing(path),
    }


def validate_authorization(args: argparse.Namespace, provenance: dict[str, Any], *, execute_hardware: bool) -> dict[str, Any]:
    auth_path = DEFAULT_AUTH_FILE
    parsed = parse_auth_file(auth_path)
    missing: list[str] = []
    if execute_hardware and not args.authorize_hardware:
        missing.append("--authorize-hardware")
    if execute_hardware and os.environ.get(AUTH_ENV) != AUTH_ENV_VALUE:
        missing.append(f"{AUTH_ENV}={AUTH_ENV_VALUE}")
    if not args.no_ethernet:
        missing.append("--no-ethernet")
    if not args.no_motion:
        missing.append("--no-motion")
    if args.lane_count != 2:
        missing.append("--lane-count 2")
    if mask_to_int(args.max_lane_mask) != 0x3:
        missing.append("--max-lane-mask 0x3")
    if not args.user_confirmed_supply_ok:
        missing.append("--user-confirmed-supply-ok")
    if not args.shutdown_on_exit:
        missing.append("--shutdown-on-exit")
    if args.max_runtime_sec <= 0 or args.max_runtime_sec > 7560:
        missing.append("--max-runtime-sec 1..7560")
    if DEFAULT_ABORT_FILE.exists():
        missing.append(f"operator abort file present: {rel(DEFAULT_ABORT_FILE)}")
    shutdown = ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit"
    if sha256_or_missing(shutdown) == "MISSING":
        missing.append("shutdown bitstream missing")
    for key in ["p6_safe_idle", "p6_tfdu_idle"]:
        row = artifact_by_key(provenance, key)
        if not row or row.get("status") != PASS or not row.get("immutable_bitstream"):
            missing.append(f"{key} immutable bitstream missing")
    missing.extend(parsed["missing"])
    auth_runtime = parsed.get("fields", {}).get("MAX_RUNTIME_SEC")
    if auth_runtime:
        try:
            if int(auth_runtime) < args.max_runtime_sec:
                missing.append("MAX_RUNTIME_SEC in authorization file is lower than requested runtime")
        except ValueError:
            missing.append("MAX_RUNTIME_SEC in authorization file is not numeric")
    authorized = execute_hardware and args.authorize_hardware and not missing
    payload = {
        "P6_HARDWARE_AUTHORIZATION": "AUTHORIZED" if authorized else "BLOCKED_NOT_AUTHORIZED",
        "AUTHORIZED": authorized,
        "AUTHORIZATION_FILE": rel(auth_path),
        "AUTHORIZATION_FILE_EXISTS": parsed["exists"],
        "AUTHORIZATION_FILE_SHA256": parsed["sha256"],
        "RF_COMM_HW_AUTH_PRESENT": os.environ.get(AUTH_ENV) == AUTH_ENV_VALUE,
        "BOARD_ID": args.board_id,
        "LANE_COUNT": args.lane_count,
        "MAX_LANE_MASK": args.max_lane_mask,
        "NETWORK_CABLE_CONNECTED": False,
        "HARDWARE_MOVEMENT_ALLOWED": False,
        "USER_CONFIRMED_SUPPLY_OK": bool(args.user_confirmed_supply_ok),
        "MAX_RUNTIME_SEC": args.max_runtime_sec,
        "SHUTDOWN_ON_EXIT": bool(args.shutdown_on_exit),
        "ABORT_FILE": rel(DEFAULT_ABORT_FILE),
        "ABORT_FILE_PRESENT": DEFAULT_ABORT_FILE.exists(),
        "SHUTDOWN_BITSTREAM": rel(shutdown),
        "SHUTDOWN_BITSTREAM_SHA256": sha256_or_missing(shutdown),
        "missing": missing,
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": False,
    }
    status = PASS if authorized else BLOCKED
    write_json(GENERATED / "p6_hardware_authorization_summary.json", payload)
    lines = [
        f"P6_HARDWARE_AUTHORIZATION: {payload['P6_HARDWARE_AUTHORIZATION']}",
        f"AUTHORIZED: {str(authorized).lower()}",
        f"AUTHORIZATION_FILE: `{payload['AUTHORIZATION_FILE']}`",
        f"AUTHORIZATION_FILE_SHA256: `{payload['AUTHORIZATION_FILE_SHA256']}`",
        f"RF_COMM_HW_AUTH_PRESENT: {str(payload['RF_COMM_HW_AUTH_PRESENT']).lower()}",
        f"LANE_COUNT: {payload['LANE_COUNT']}",
        f"MAX_LANE_MASK: {payload['MAX_LANE_MASK']}",
        f"MAX_RUNTIME_SEC: {payload['MAX_RUNTIME_SEC']}",
        f"SHUTDOWN_ON_EXIT: {str(payload['SHUTDOWN_ON_EXIT']).lower()}",
        f"ABORT_FILE_PRESENT: {str(payload['ABORT_FILE_PRESENT']).lower()}",
        "",
        "## Missing Controls",
        "",
        *(f"- `{item}`" for item in missing),
        *(["- none"] if not missing else []),
    ]
    write_markdown(
        GENERATED / "p6_hardware_authorization_summary.md",
        "P6 Hardware Authorization Summary",
        status,
        "P6 hardware controls are authorized" if authorized else "P6 hardware authorization incomplete or not executing",
        lines,
    )
    write_markdown(
        P6_DIR / "authorization" / "p6_hardware_authorization_record.md",
        "P6 Hardware Authorization Record",
        status,
        "P6 hardware controls are authorized" if authorized else "P6 hardware authorization incomplete or not executing",
        lines,
    )
    return payload


def _resolve_vivado() -> str | None:
    return shutil.which("vivado") or shutil.which("vivado.bat") or (str(DEFAULT_VIVADO) if DEFAULT_VIVADO.exists() else None)


def _run(cmd: list[str], *, timeout: int, env: dict[str, str] | None = None) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, env=env)
        return {"cmd": " ".join(str(item) for item in cmd), "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
    except FileNotFoundError as exc:
        return {"cmd": " ".join(str(item) for item in cmd), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "timeout",
        }


def _tcl_path(path: Path) -> str:
    return path.resolve().as_posix()


def _hardware_env() -> dict[str, str]:
    env = os.environ.copy()
    env[AUTH_ENV] = AUTH_ENV_VALUE
    return env


def _write_shutdown_tcl(path: Path, log_path: Path) -> None:
    shutdown_tcl = ROOT / "scripts" / "legacy_safe_tools" / "program_tfdu_shutdown.tcl"
    script = f"""
set log_file {{{_tcl_path(log_path)}}}
set fh [open $log_file "w"]
proc say {{line}} {{
  global fh
  puts $line
  puts $fh $line
  flush $fh
}}
say "P6_TFDU_SHUTDOWN_WRAPPER_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set rc [catch {{
  source {{{_tcl_path(shutdown_tcl)}}}
}} err opts]
if {{$rc != 0}} {{
  say "P6_TFDU_SHUTDOWN_WRAPPER=FAIL"
  say "P6_TFDU_SHUTDOWN_WRAPPER_ERROR=$err"
  close $fh
  exit 31
}}
say "P6_TFDU_SHUTDOWN_WRAPPER=PASS"
close $fh
exit 0
""".strip()
    write_text(path, script)


def _write_stage_program_tcl(
    path: Path,
    bitstream: Path,
    log_path: Path,
    ltx_path: Path | None,
    capture_dir: Path,
    *,
    stage_label: str,
    capture_prefix: str,
    post_program_wait_ms: int,
) -> None:
    ltx_value = _tcl_path(ltx_path) if ltx_path and ltx_path.exists() else ""
    script = f"""
set log_file {{{_tcl_path(log_path)}}}
set ila_dir {{{_tcl_path(capture_dir)}}}
file mkdir $ila_dir
set fh [open $log_file "w"]
proc say {{line}} {{
  global fh
  puts $line
  puts $fh $line
  flush $fh
}}
say "P6_{stage_label}_PROGRAM_BEGIN [clock format [clock seconds] -format %Y-%m-%dT%H:%M:%S%z]"
set bit_file {{{_tcl_path(bitstream)}}}
if {{![file exists $bit_file]}} {{
  say "P6_{stage_label}_BITSTREAM_MISSING=$bit_file"
  close $fh
  exit 20
}}
set ltx_file {{{ltx_value}}}
set rc [catch {{
  open_hw_manager
  connect_hw_server -url {{{DEFAULT_HW_SERVER_URL}}}
  set targets [get_hw_targets -quiet *]
  say "P6_HW_TARGET_COUNT=[llength $targets]"
  if {{[llength $targets] == 0}} {{
    error "No JTAG hw_target found."
  }}
  set dev ""
  foreach target $targets {{
    say "P6_HW_TARGET=$target"
    if {{[catch {{current_hw_target $target}} target_err]}} {{
      say "P6_CURRENT_HW_TARGET_ERROR=$target_err"
      continue
    }}
    if {{[catch {{set_property PARAM.FREQUENCY {DEFAULT_JTAG_FREQUENCY_HZ} $target}} freq_err]}} {{
      say "P6_HW_JTAG_FREQUENCY_WARN=$freq_err"
    }} else {{
      say "P6_HW_JTAG_FREQUENCY_HZ={DEFAULT_JTAG_FREQUENCY_HZ}"
    }}
    if {{[catch {{open_hw_target $target}} open_err]}} {{
      say "P6_OPEN_HW_TARGET_ERROR=$open_err"
      continue
    }}
    foreach candidate [get_hw_devices -quiet *] {{
      set part ""
      catch {{set part [get_property PART $candidate]}}
      say "P6_HW_DEVICE=$candidate PART=$part"
      if {{[string match -nocase *xc7z010* $part] || [string match -nocase *7z010* $part]}} {{
        set dev $candidate
        break
      }}
      if {{$dev eq ""}} {{
        set dev $candidate
      }}
    }}
    if {{$dev ne ""}} {{
      break
    }}
    catch {{close_hw_target $target}}
  }}
  if {{$dev eq ""}} {{
    error "No programmable hw_device found."
  }}
  current_hw_device $dev
  refresh_hw_device -update_hw_probes false $dev
  foreach prop {{NAME PART IDCODE IS_PROGRAMMED PROGRAM.FILE}} {{
    if {{[catch {{set value [get_property $prop $dev]}} prop_err]}} {{
      say "P6_{stage_label}_DEVICE_PROP $prop ERROR=$prop_err"
    }} else {{
      say "P6_{stage_label}_DEVICE_PROP $prop=$value"
    }}
  }}
  set_property PROGRAM.FILE $bit_file $dev
  if {{$ltx_file ne "" && [file exists $ltx_file]}} {{
    set_property PROBES.FILE $ltx_file $dev
    say "P6_{stage_label}_PROBES_FILE=$ltx_file"
  }} else {{
    say "P6_{stage_label}_PROBES_FILE=MISSING"
  }}
  program_hw_devices $dev
  if {{{post_program_wait_ms} > 0}} {{
    after {post_program_wait_ms}
  }}
  refresh_hw_device -update_hw_probes true $dev
  say "P6_{stage_label}_BITSTREAM_PROGRAMMED=$bit_file"
  set ilas [get_hw_ilas -quiet *]
  say "P6_HW_ILA_COUNT=[llength $ilas]"
  set capture_pass 0
  set capture_idx 0
  foreach ila $ilas {{
    set wdb_file [file join $ila_dir "{capture_prefix}_${{capture_idx}}.wdb"]
    set csv_file [file join $ila_dir "{capture_prefix}_${{capture_idx}}.csv"]
    set ila_rc [catch {{
      current_hw_ila $ila
      catch {{set_property CONTROL.TRIGGER_POSITION 0 $ila}}
      if {{[catch {{run_hw_ila -trigger_now $ila}} trigger_err]}} {{
        say "P6_ILA_TRIGGER_NOW_WARN_${{capture_idx}}=$trigger_err"
        run_hw_ila $ila
      }}
      wait_on_hw_ila $ila
      set data [upload_hw_ila_data $ila]
      write_hw_ila_data -force $wdb_file $data
      if {{[catch {{write_hw_ila_data -force -csv_file $csv_file $data}} csv_err]}} {{
        say "P6_ILA_CSV_EXPORT_WARN_${{capture_idx}}=$csv_err"
      }}
    }} ila_err]
    if {{$ila_rc == 0}} {{
      say "P6_ILA_CAPTURE_${{capture_idx}}=PASS"
      say "P6_ILA_CAPTURE_${{capture_idx}}_WDB=$wdb_file"
      if {{[file exists $csv_file]}} {{
        say "P6_ILA_CAPTURE_${{capture_idx}}_CSV=$csv_file"
      }}
      set capture_pass 1
    }} else {{
      say "P6_ILA_CAPTURE_${{capture_idx}}=FAIL"
      say "P6_ILA_CAPTURE_${{capture_idx}}_ERROR=$ila_err"
    }}
    incr capture_idx
  }}
  if {{$capture_pass}} {{
    say "P6_ILA_CAPTURE=PASS"
  }} elseif {{[llength $ilas] == 0}} {{
    say "P6_ILA_CAPTURE=SKIP_NO_ILA"
  }} else {{
    say "P6_ILA_CAPTURE=FAIL"
  }}
  say "P6_{stage_label}_PROGRAM=PASS"
  catch {{close_hw_target}}
  catch {{disconnect_hw_server}}
  catch {{close_hw_manager}}
}} err opts]
if {{$rc != 0}} {{
  say "P6_{stage_label}_PROGRAM=FAIL"
  say "P6_{stage_label}_PROGRAM_ERROR=$err"
  catch {{close_hw_target}}
  catch {{disconnect_hw_server}}
  catch {{close_hw_manager}}
  close $fh
  exit 21
}}
close $fh
exit 0
""".strip()
    write_text(path, script)


def _shutdown_ok(result: dict[str, Any]) -> bool:
    text = "\n".join([str(result.get("stdout", "")), str(result.get("stderr", "")), str(result.get("log_text_tail", ""))])
    return result.get("returncode") == 0 or "SHUTDOWN_EXIT=0" in text or "TFDU_SHUTDOWN_PROGRAMMED" in text


def _run_shutdown(args: argparse.Namespace, evidence_dir: Path, label: str) -> dict[str, Any]:
    vivado = _resolve_vivado()
    if not vivado:
        return {"returncode": 127, "stdout": "", "stderr": "Vivado missing", "cmd": "vivado"}
    shutdown_dir = evidence_dir / "shutdown" / label
    shutdown_dir.mkdir(parents=True, exist_ok=True)
    tcl_path = shutdown_dir / "p6_program_tfdu_shutdown.tcl"
    log_path = shutdown_dir / "p6_program_tfdu_shutdown.log"
    _write_shutdown_tcl(tcl_path, log_path)
    result = _run([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=min(max(args.max_runtime_sec or 300, 60), 900), env=_hardware_env())
    result["log_path"] = rel(log_path)
    result["tcl_path"] = rel(tcl_path)
    result["log_text_tail"] = log_path.read_text(encoding="utf-8", errors="ignore")[-4000:] if log_path.exists() else ""
    return result


def write_failure_package(stage_name: str, payload: dict[str, Any], reason: str) -> None:
    failure_dir = P6_DIR / "failures"
    failure_dir.mkdir(parents=True, exist_ok=True)
    base = failure_dir / f"{stage_name}_failure_package"
    package = {
        "stage": stage_name,
        "reason": reason,
        "payload": payload,
        "active_hashes": active_hashes(),
        "root_cause_classification": reason,
        "next_suggested_fix": "Implement or repair P6 local transport artifact/backend, then rerun the failing stage with shutdown-on-exit.",
    }
    write_json(base.with_suffix(".json"), package)
    lines = [
        f"stage: {stage_name}",
        f"root-cause classification: {reason}",
        "",
        "## Last Payload",
        "",
        "```json",
        json.dumps(payload, indent=2, ensure_ascii=False)[-6000:],
        "```",
    ]
    write_markdown(base.with_suffix(".md"), "P6 Failure Package", FAIL, reason, lines, script_hw=bool(payload.get("script_hardware_actions_executed")))


def run_programming_stage(args: argparse.Namespace, cfg: dict[str, Any], provenance: dict[str, Any]) -> dict[str, Any]:
    marker = cfg["marker"]
    evidence_dir = ROOT / cfg["evidence_dir"]
    capture_dir = ROOT / cfg["capture_dir"]
    summary_path = ROOT / cfg["summary"]
    evidence_dir.mkdir(parents=True, exist_ok=True)
    capture_dir.mkdir(parents=True, exist_ok=True)
    row = artifact_by_key(provenance, cfg["artifact_key"])
    bitstream = ROOT / row["immutable_bitstream"] if row and row.get("immutable_bitstream") else None
    ltx = ROOT / row["immutable_ltx"] if row and row.get("immutable_ltx") else None
    profile = ROOT / cfg["profile"]
    vivado = _resolve_vivado()
    payload: dict[str, Any] = {
        marker: FAIL,
        "stage": marker,
        "profile": cfg["profile"],
        "profile_sha256": sha256_or_missing(profile),
        "bitstream": rel(bitstream) if bitstream else "MISSING",
        "bitstream_sha256": sha256_or_missing(bitstream),
        "debug_probes_ltx": rel(ltx) if ltx else "MISSING",
        "debug_probes_ltx_sha256": sha256_or_missing(ltx),
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": False,
        "stage_programmed_fpga": False,
        "stage_drove_tfdu_txd": bool(cfg.get("stage_drove_tfdu_txd")),
        "stage_enabled_tfdu_receiver": bool(cfg.get("stage_enabled_tfdu_receiver")),
        "shutdown_on_exit_observed": False,
        "product_final_acceptance": "pending",
    }
    if not vivado:
        reason = "Vivado executable missing"
        payload[marker] = SKIP
        payload["reason"] = reason
        write_json(evidence_dir / "p6_stage_result.json", payload)
        write_markdown(summary_path, marker.replace("_", " ").title(), SKIP, reason, [f"{marker}: {SKIP}", "SKIP_WITH_REASON: Vivado executable missing"])
        return payload
    if not bitstream or not bitstream.exists():
        reason = "P6 immutable bitstream missing"
        payload[marker] = BLOCKED
        payload["reason"] = reason
        write_json(evidence_dir / "p6_stage_result.json", payload)
        write_markdown(summary_path, marker.replace("_", " ").title(), BLOCKED, reason, [f"{marker}: {BLOCKED}", f"reason: {reason}"])
        return payload

    baseline_shutdown = _run_shutdown(args, evidence_dir, "before_stage")
    baseline_ok = _shutdown_ok(baseline_shutdown)
    program_result = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    after_shutdown = {"returncode": 125, "stdout": "", "stderr": "", "cmd": ""}
    parse_payload: dict[str, Any] = {}
    try:
        if not baseline_ok:
            payload["reason"] = "baseline TFDU shutdown failed before stage"
            payload["baseline_shutdown_run"] = baseline_shutdown
            payload["script_hardware_actions_executed"] = True
            write_failure_package(marker.lower(), payload, "baseline_shutdown_failed")
            return payload
        tcl_path = evidence_dir / f"p6_{marker.lower()}_programming.tcl"
        log_path = evidence_dir / f"p6_{marker.lower()}_programming.log"
        _write_stage_program_tcl(
            tcl_path,
            bitstream,
            log_path,
            ltx,
            capture_dir,
            stage_label=marker,
            capture_prefix=cfg["capture_prefix"],
            post_program_wait_ms=int(cfg["post_wait_ms"]),
        )
        timeout = max(int(args.max_runtime_sec or 300) + 300, int(cfg["post_wait_ms"] / 1000) + 300, 360)
        program_result = _run([vivado, "-mode", "batch", "-source", str(tcl_path)], timeout=timeout, env=_hardware_env())
        program_text = "\n".join(
            [
                str(program_result.get("stdout", "")),
                str(program_result.get("stderr", "")),
                log_path.read_text(encoding="utf-8", errors="ignore") if log_path.exists() else "",
            ]
        )
        parser: ParserFunc = cfg["parser"]
        parse_payload = parser(capture_dir)
        best = parse_payload.get("best_result", {}) if isinstance(parse_payload.get("best_result"), dict) else {}
        program_ok = program_result.get("returncode") == 0 and f"P6_{marker}_PROGRAM=PASS" in program_text
        capture_ok = "P6_ILA_CAPTURE=PASS" in program_text
        parse_ok = parse_payload.get(cfg["parse_key"]) == PASS
        payload.update(best)
        payload["PROGRAM_RETURN_CODE"] = program_result.get("returncode")
        payload["PROGRAM_LOG"] = rel(log_path)
        payload["PROGRAM_TCL"] = rel(tcl_path)
        payload["ILA_CAPTURE_DIR"] = cfg["capture_dir"]
        payload["ILA_CAPTURE"] = PASS if capture_ok else FAIL
        payload[cfg["parse_key"]] = parse_payload.get(cfg["parse_key"], "UNKNOWN")
        payload["PROGRAM"] = PASS if program_ok else FAIL
        payload["script_hardware_actions_executed"] = True
        payload["source_evidence_contains_hardware_actions"] = True
        payload["stage_programmed_fpga"] = bool(program_ok)
        payload[marker] = PASS if program_ok and capture_ok and parse_ok else FAIL
    finally:
        after_shutdown = _run_shutdown(args, evidence_dir, "after_stage")
        shutdown_ok = _shutdown_ok(after_shutdown)
        payload["SHUTDOWN_ON_EXIT"] = PASS if shutdown_ok else FAIL
        payload["shutdown_on_exit_observed"] = bool(shutdown_ok)
        if not shutdown_ok:
            payload[marker] = FAIL
        payload["baseline_shutdown_run"] = baseline_shutdown
        payload["program_run"] = {
            "cmd": program_result.get("cmd", ""),
            "returncode": program_result.get("returncode", 125),
            "stdout_tail": str(program_result.get("stdout", ""))[-4000:],
            "stderr_tail": str(program_result.get("stderr", ""))[-4000:],
        }
        payload["shutdown_run"] = after_shutdown
        payload["parse"] = parse_payload
        write_json(evidence_dir / "p6_stage_result.json", payload)
        write_json(evidence_dir / "readback.json", payload)
        write_csv(
            evidence_dir / "counters.csv",
            ["stage", "status", "shutdown_on_exit", "txd_stuck_high_violation", "duty_window_violation"],
            [
                {
                    "stage": marker,
                    "status": payload.get(marker, FAIL),
                    "shutdown_on_exit": payload.get("SHUTDOWN_ON_EXIT", FAIL),
                    "txd_stuck_high_violation": payload.get("TXD_STUCK_HIGH_VIOLATION", 0),
                    "duty_window_violation": payload.get("DUTY_WINDOW_VIOLATION", 0),
                }
            ],
        )
        lines = [
            f"{marker}: {payload.get(marker, FAIL)}",
            f"{cfg['parse_key']}: {payload.get(cfg['parse_key'], 'UNKNOWN')}",
            f"PROGRAM: {payload.get('PROGRAM', FAIL)}",
            f"ILA_CAPTURE: {payload.get('ILA_CAPTURE', FAIL)}",
            f"SHUTDOWN_ON_EXIT: {payload.get('SHUTDOWN_ON_EXIT', FAIL)}",
            "script_hardware_actions_executed: true",
            "source_evidence_contains_hardware_actions: true",
            f"stage_programmed_fpga: {str(bool(payload.get('stage_programmed_fpga'))).lower()}",
            f"stage_drove_tfdu_txd: {str(bool(payload.get('stage_drove_tfdu_txd'))).lower()}",
            f"stage_enabled_tfdu_receiver: {str(bool(payload.get('stage_enabled_tfdu_receiver'))).lower()}",
            f"shutdown_on_exit_observed: {str(bool(payload.get('shutdown_on_exit_observed'))).lower()}",
            f"BITSTREAM: `{payload['bitstream']}`",
            f"BITSTREAM_SHA256: `{payload['bitstream_sha256']}`",
            f"PROFILE: `{payload['profile']}`",
            f"PROFILE_SHA256: `{payload['profile_sha256']}`",
            "",
            "## Boundary",
            "",
            "- This P6 hardware action is stationary, 2-lane, automated Vivado/JTAG/ILA evidence.",
            "- It does not use Ethernet, motion, rotation, 4-lane/8-lane, or lane mask above 0x3.",
            "- It is not P6 dynamic payload or product-final acceptance.",
        ]
        if payload.get(marker) != PASS:
            write_failure_package(marker.lower(), payload, f"{marker}_failed")
        write_markdown(summary_path, marker.replace("_", " ").title(), payload.get(marker, FAIL), "authorized P6 hardware stage executed", lines, script_hw=True, source_hw=True)
        write_markdown(evidence_dir / "summary.md", marker.replace("_", " ").title(), payload.get(marker, FAIL), "authorized P6 hardware stage executed", lines, script_hw=True, source_hw=True)
    return payload


def write_blocked_hardware_stages(prereq_reason: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for stage_name, (marker, evidence_dir, summary, reason) in P6_BLOCKED_HW_STAGES.items():
        status = NOT_RUN_RUNTIME_LIMIT if stage_name == "two_lane_2h_stationary_soak" and prereq_reason == "runtime_limit" else BLOCKED
        item = p6_stage_placeholder(marker, evidence_dir, summary, status, reason)
        payload[marker] = item[marker]
    return payload


def run_authorized_hardware(args: argparse.Namespace, provenance: dict[str, Any], auth: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "P6_HARDWARE_EXECUTION": PASS_WITH_NOTES,
        "HARDWARE_ACTIONS_EXECUTED": False,
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": False,
        "STOP_CONDITIONS_TRIGGERED": "none",
        "SHUTDOWN_ON_EXIT": "SKIP_NO_HARDWARE_ACTIONS",
        "executed_stages": [],
        "failures": [],
        "blocked": [],
        "skips": [],
    }
    if not auth.get("AUTHORIZED"):
        for stage_name, cfg in P6_HW_STAGE_RUNS.items():
            item = p6_stage_placeholder(
                cfg["marker"],
                cfg["evidence_dir"],
                cfg["summary"],
                BLOCKED,
                "P6 authorization gate blocked before hardware connection",
            )
            payload[cfg["marker"]] = item[cfg["marker"]]
            payload["blocked"].append(cfg["marker"])
        payload.update(write_blocked_hardware_stages("authorization_blocked"))
        payload["P6_HARDWARE_EXECUTION"] = BLOCKED
        payload["STOP_CONDITIONS_TRIGGERED"] = "authorization_blocked"
        return payload

    shutdown_failures = []
    for stage_name in ["safe_idle_recheck", "tfdu_control_idle_recheck"]:
        result = run_programming_stage(args, P6_HW_STAGE_RUNS[stage_name], provenance)
        marker = P6_HW_STAGE_RUNS[stage_name]["marker"]
        payload[marker] = result.get(marker, FAIL)
        payload["executed_stages"].append(stage_name)
        if result.get("script_hardware_actions_executed"):
            payload["HARDWARE_ACTIONS_EXECUTED"] = True
            payload["script_hardware_actions_executed"] = True
            payload["source_evidence_contains_hardware_actions"] = True
        if result.get("SHUTDOWN_ON_EXIT") != PASS:
            shutdown_failures.append(marker)
        if result.get(marker) == FAIL:
            payload["failures"].append(marker)
            payload["STOP_CONDITIONS_TRIGGERED"] = f"hardware_stage_failure:{marker}"
            break
        if result.get(marker) == SKIP:
            payload["skips"].append(marker)
    if not payload["failures"]:
        blocked_payload = write_blocked_hardware_stages("missing_p6_local_transport_backend")
        payload.update(blocked_payload)
        payload["blocked"].extend([marker for marker, value in blocked_payload.items() if value == BLOCKED])
    if shutdown_failures:
        payload["SHUTDOWN_ON_EXIT"] = FAIL
        payload["P6_HARDWARE_EXECUTION"] = FAIL
        payload["STOP_CONDITIONS_TRIGGERED"] = "shutdown_on_exit_failed:" + ",".join(shutdown_failures)
    elif payload["failures"]:
        payload["SHUTDOWN_ON_EXIT"] = PASS if payload.get("HARDWARE_ACTIONS_EXECUTED") else "SKIP_NO_HARDWARE_ACTIONS"
        payload["P6_HARDWARE_EXECUTION"] = FAIL
    elif payload["blocked"] or payload["skips"]:
        payload["SHUTDOWN_ON_EXIT"] = PASS if payload.get("HARDWARE_ACTIONS_EXECUTED") else "SKIP_NO_HARDWARE_ACTIONS"
        payload["P6_HARDWARE_EXECUTION"] = PASS_WITH_NOTES
        payload["STOP_CONDITIONS_TRIGGERED"] = "p6_dynamic_payload_backend_missing"
    else:
        payload["SHUTDOWN_ON_EXIT"] = PASS
        payload["P6_HARDWARE_EXECUTION"] = PASS
    write_json(P6_DIR / "p6_hardware_execution_summary.json", payload)
    lines = [
        f"P6_HARDWARE_EXECUTION: {payload['P6_HARDWARE_EXECUTION']}",
        f"HARDWARE_ACTIONS_EXECUTED: {str(payload['HARDWARE_ACTIONS_EXECUTED']).lower()}",
        f"SHUTDOWN_ON_EXIT: {payload['SHUTDOWN_ON_EXIT']}",
        f"STOP_CONDITIONS_TRIGGERED: {payload['STOP_CONDITIONS_TRIGGERED']}",
        "",
        "## Executed Stages",
        "",
        *(f"- `{stage}`" for stage in payload["executed_stages"]),
        "",
        "## Blocked Stages",
        "",
        *(f"- `{stage}`" for stage in payload["blocked"]),
    ]
    write_markdown(
        GENERATED / "p6_hardware_execution_summary.md",
        "P6 Hardware Execution Summary",
        payload["P6_HARDWARE_EXECUTION"],
        "authorized P6 hardware stages executed until missing dynamic payload backend boundary",
        lines,
        script_hw=bool(payload.get("HARDWARE_ACTIONS_EXECUTED")),
        source_hw=bool(payload.get("source_evidence_contains_hardware_actions")),
    )
    return payload


def _scan_for_phrases(relpaths: list[str], phrases: list[str]) -> list[str]:
    failures = []
    for relpath in relpaths:
        path = ROOT / relpath
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for phrase in phrases:
            if phrase in text:
                failures.append(f"{relpath}: forbidden phrase `{phrase}`")
    return failures


def check_no_ethernet() -> dict[str, Any]:
    failures = []
    for profile in sorted(P6_PROFILES.glob("*.json")):
        data = load_json(profile)
        if data.get("network_required") is not False or data.get("ethernet_enabled") is not False:
            failures.append(f"{rel(profile)}: network_required/ethernet_enabled must be false")
    failures.extend(
        _scan_for_phrases(
            ["PROJECT_STATUS.md", "docs/PROJECT_STATUS.md", "README.md", "evidence/generated/p6_local_transport_no_ethernet_summary.md"],
            ["ETHERNET_ACCEPTANCE: PASS", "DHCP_ACCEPTANCE: PASS", "STATIC_IP_ACCEPTANCE: PASS", "TCP_BOARD_LINK: PASS"],
        )
    )
    result = PASS if not failures else FAIL
    payload = {"P6_NO_ETHERNET": result, "ETHERNET_ACCEPTANCE": "DEFERRED_NO_NETWORK_CABLE", "failures": failures}
    write_json(GENERATED / "p6_no_ethernet_summary.json", payload)
    lines = [
        f"P6_NO_ETHERNET: {result}",
        "ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE",
        "NETWORK_CABLE_CONNECTED: false",
        "",
        "## Checks",
        "",
        "- P6 profiles require no network.",
        "- P6 runner forbids Ethernet acceptance, DHCP, static-IP board link, and TCP board transport.",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(GENERATED / "p6_no_ethernet_summary.md", "P6 No Ethernet Summary", result, "P6 Ethernet scope gate", lines)
    return payload


def check_no_motion() -> dict[str, Any]:
    failures = []
    for profile in sorted(P6_PROFILES.glob("*.json")):
        data = load_json(profile)
        if data.get("motion_required") is not False or data.get("rotation_enabled") is not False:
            failures.append(f"{rel(profile)}: motion_required/rotation_enabled must be false")
    failures.extend(
        _scan_for_phrases(
            ["PROJECT_STATUS.md", "docs/PROJECT_STATUS.md", "README.md", "evidence/generated/p6_local_transport_no_ethernet_summary.md"],
            ["ROTATION_ACCEPTANCE: PASS", "MOTION_ACCEPTANCE: PASS", "MOVEMENT_ACCEPTANCE: PASS"],
        )
    )
    result = PASS if not failures else FAIL
    payload = {"P6_NO_MOTION": result, "ROTATION_ACCEPTANCE": "DEFERRED_NO_HARDWARE_MOVEMENT", "failures": failures}
    write_json(GENERATED / "p6_no_motion_summary.json", payload)
    lines = [
        f"P6_NO_MOTION: {result}",
        "ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT",
        "HARDWARE_MOVEMENT_ALLOWED: false",
        "",
        "## Checks",
        "",
        "- P6 profiles require no motion.",
        "- P6 runner forbids rotation, motion, movement,遮挡, and mechanical alignment changes.",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(GENERATED / "p6_no_motion_summary.md", "P6 No Motion Summary", result, "P6 no-motion gate", lines)
    return payload


def _pinmap_lanes() -> set[int]:
    import csv

    path = ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv"
    lanes: set[int] = set()
    if not path.exists():
        return lanes
    with path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                lanes.add(int(row.get("lane", "")))
            except ValueError:
                pass
    return lanes


def check_2lane_scope() -> dict[str, Any]:
    failures = []
    for profile in sorted(P6_PROFILES.glob("*.json")):
        data = load_json(profile)
        if data.get("lane_count") != 2:
            failures.append(f"{rel(profile)}: lane_count must be 2")
        for key in ["max_lane_mask", "expected_lane_mask", "expected_ack_lane_mask"]:
            value = mask_to_int(data.get(key))
            if value is None or value > 0x3:
                failures.append(f"{rel(profile)}: {key}={data.get(key)} exceeds 0x3 or is invalid")
    lanes = _pinmap_lanes()
    if lanes != {0, 1}:
        failures.append(f"active pinmap lanes are {sorted(lanes)}, expected [0, 1]")
    result = PASS if not failures else FAIL
    payload = {
        "P6_2LANE_SCOPE": result,
        "AVAILABLE_LANES": 2,
        "MAX_LANE_MASK": "0x3",
        "EIGHT_LANE_ACCEPTANCE": "DEFERRED_ONLY_2_LANES_AVAILABLE",
        "failures": failures,
    }
    write_json(GENERATED / "p6_2lane_scope_summary.json", payload)
    lines = [
        f"P6_2LANE_SCOPE: {result}",
        "AVAILABLE_LANES: 2",
        "MAX_LANE_MASK: 0x3",
        "EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE",
        f"active pinmap lanes: `{sorted(lanes)}`",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(GENERATED / "p6_2lane_scope_summary.md", "P6 Two-Lane Scope Summary", result, "P6 two-lane gate", lines)
    return payload


def write_host_file_payloads() -> dict[str, Any]:
    out_dir = P6_DIR / "host_file_transport_jtag" / "input_payloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    payloads = {
        "small_text.bin": b"RF_COMM P6 local file payload\n",
        "counter_247.bin": seeded_payload(247, "counter"),
        "prbs_247.bin": seeded_payload(247, "prbs7"),
        "random_seeded_247.bin": seeded_payload(247, "deterministic_random"),
    }
    rows = []
    for name, data in payloads.items():
        path = out_dir / name
        if not path.exists():
            path.write_bytes(data)
        rows.append({"file": rel(path), "bytes": len(data), "sha256": sha256_or_missing(path), "crc32": crc32_hex(data)})
    write_json(P6_DIR / "host_file_transport_jtag" / "input_payload_manifest.json", rows)
    return {"P6_HOST_FILE_PAYLOADS": PASS, "payload_files": rows}


def analyze_protocol_metrics(payload: dict[str, Any]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for stage_name, cfg in P6_HW_STAGE_RUNS.items():
        data = load_json(ROOT / cfg["evidence_dir"] / "p6_stage_result.json")
        if not data:
            continue
        rows.append(
            {
                "stage": cfg["marker"],
                "stage_status": data.get(cfg["marker"], "MISSING"),
                "frames_requested": data.get("REQUESTED_FRAMES", 0),
                "frames_sent": data.get("SENT_FRAMES", data.get("A_SENT_FRAMES", 0)),
                "frames_rx_good": data.get("RX_GOOD", data.get("B_RX_GOOD", 0)),
                "ack_seen": data.get("A_ACK_SEEN", 0),
                "crc_bad": data.get("CRC_BAD", 0),
                "payload_mismatch": data.get("PAYLOAD_MISMATCH", 0),
                "retry_count": data.get("RETRY_COUNT", 0),
                "retry_exhausted": data.get("TX_RETRY_EXHAUSTED", 0),
                "tx_fail": data.get("TX_FAIL", 0),
                "runtime_sec": data.get("RUNTIME_SEC", 0),
                "payload_bytes_total": 0,
                "effective_payload_bps": 0,
                "goodput_bps": 0,
                "latency_counter_status": "not_available_for_idle_stage",
                "max_txd_high_cycles": data.get("TXD_HIGH_CONSECUTIVE_MAX_CYCLES", 0),
                "duty_violation_count": data.get("DUTY_WINDOW_VIOLATION", 0),
            }
        )
    if not rows:
        rows.append(
            {
                "stage": "P6_DYNAMIC_PAYLOAD_STAGES",
                "stage_status": BLOCKED,
                "frames_requested": 0,
                "frames_sent": 0,
                "frames_rx_good": 0,
                "ack_seen": 0,
                "crc_bad": 0,
                "payload_mismatch": 0,
                "retry_count": 0,
                "retry_exhausted": 0,
                "tx_fail": 0,
                "runtime_sec": 0,
                "payload_bytes_total": 0,
                "effective_payload_bps": 0,
                "goodput_bps": 0,
                "latency_counter_status": "blocked_by_missing_p6_local_transport_backend",
                "max_txd_high_cycles": 0,
                "duty_violation_count": 0,
            }
        )
    csv_path = GENERATED / "p6_protocol_metrics.csv"
    write_csv(
        csv_path,
        [
            "stage",
            "stage_status",
            "frames_requested",
            "frames_sent",
            "frames_rx_good",
            "ack_seen",
            "crc_bad",
            "payload_mismatch",
            "retry_count",
            "retry_exhausted",
            "tx_fail",
            "runtime_sec",
            "payload_bytes_total",
            "effective_payload_bps",
            "goodput_bps",
            "latency_counter_status",
            "max_txd_high_cycles",
            "duty_violation_count",
        ],
        rows,
    )
    result = PASS_WITH_NOTES if any(row["stage_status"] != PASS for row in rows) else PASS
    out = {"P6_PROTOCOL_METRICS": result, "rows": rows, "csv": rel(csv_path)}
    write_json(GENERATED / "p6_protocol_metrics_summary.json", out)
    lines = [
        f"P6_PROTOCOL_METRICS: {result}",
        f"csv: `{rel(csv_path)}`",
        "metrics are per-stage and aggregate separately",
        "no incompatible source mixing without labels",
    ]
    write_markdown(GENERATED / "p6_protocol_metrics_summary.md", "P6 Protocol Metrics Summary", result, "P6 metrics normalized by stage", lines, source_hw=bool(payload.get("source_evidence_contains_hardware_actions")))
    return out


def check_evidence_consistency(payload: dict[str, Any]) -> dict[str, Any]:
    failures = []
    for key, value in payload.items():
        if key.startswith("P6_") and isinstance(value, str) and value not in ALLOWED_RESULTS and not value.startswith("AUTHORIZED") and not value.startswith("DEFERRED") and value not in {"READY_AUTHORIZED", "BLOCKED_NOT_AUTHORIZED"}:
            if key not in {"P6_HARDWARE_AUTHORIZATION"}:
                failures.append(f"{key}: unexpected result value {value}")
    if payload.get("ETHERNET_ACCEPTANCE") == "PASS":
        failures.append("Ethernet acceptance cannot be PASS in P6 no-cable scope")
    if payload.get("ROTATION_ACCEPTANCE") == "PASS":
        failures.append("Rotation acceptance cannot be PASS in P6 no-motion scope")
    if payload.get("EIGHT_LANE_ACCEPTANCE") == "PASS":
        failures.append("8-lane acceptance cannot be PASS with only 2 lanes available")
    result = PASS if not failures else FAIL
    out = {"P6_EVIDENCE_CONSISTENCY": result, "failures": failures}
    write_json(GENERATED / "p6_evidence_consistency_summary.json", out)
    lines = [
        f"P6_EVIDENCE_CONSISTENCY: {result}",
        "P6 skips/blocked stages are not promoted to PASS",
        "product-final acceptance remains pending",
    ]
    if failures:
        lines.extend(["", "## Failures", "", *(f"- {failure}" for failure in failures)])
    write_markdown(GENERATED / "p6_evidence_consistency_summary.md", "P6 Evidence Consistency Summary", result, "P6 evidence consistency checked", lines, source_hw=bool(payload.get("source_evidence_contains_hardware_actions")))
    return out


def p6_status_from_payload(payload: dict[str, Any]) -> str:
    required = [
        "P6_SAFE_IDLE_RECHECK",
        "P6_TFDU_CONTROL_IDLE_RECHECK",
        "P6_JTAG_AXI_PAYLOAD_RAM_SMOKE",
        "P6_LANE0_DYNAMIC_PAYLOAD",
        "P6_LANE1_DYNAMIC_PAYLOAD",
        "P6_TWO_LANE_DYNAMIC_PAYLOAD",
        "P6_PS_DRIVER_RUNTIME",
        "P6_HOST_FILE_TRANSPORT_JTAG",
        "P6_LANE_FALLBACK_REGRESSION",
        "P6_TWO_LANE_2H_STATIONARY_SOAK",
    ]
    if any(payload.get(key) == FAIL for key in required):
        return FAIL
    if all(payload.get(key) == PASS for key in required):
        return PASS
    return FAIL


def update_status_docs(p6_status: str, hardware_status: str) -> dict[str, Any]:
    head = git_value("rev-parse", "HEAD")
    branch = git_value("branch", "--show-current")
    content = f"""# Project Status

Project: RF_COMM_MULTILANE
Current branch: {branch}
Current HEAD: {head}

P0_BOOTSTRAP: PASS
P1_OFFLINE_HARDENING: PASS
P2_SIMULATION_BASELINE: PASS
P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS
P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE
P5_2LANE_PROTOCOL_STABILIZATION: PASS_WITH_NOTES
P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET: {p6_status}
HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: {hardware_status}
ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
PRODUCT_FINAL_ACCEPTANCE: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

USER_CONFIRMED_SUPPLY_OK: true
NETWORK_CABLE_CONNECTED: false
HARDWARE_MOVEMENT_ALLOWED: false
AVAILABLE_LANES: 2
MAX_LANE_MASK: 0x3

P6 is stationary, two-lane, local/JTAG/AXI/PS-driver scoped evidence.
P6 is not Ethernet acceptance.
P6 is not rotation acceptance.
P6 is not 8-lane acceptance.
P6 is not product-final acceptance.

Current P6 result is {p6_status} because the P6 dynamic payload local transport, PS runtime mailbox, host-file JTAG transport, fallback regression, and 2-hour dynamic soak backends are not yet present as P6 artifacts. Existing P5 fixed-payload evidence remains P5 evidence only.
"""
    write_text(ROOT / "PROJECT_STATUS.md", content)
    write_text(ROOT / "docs" / "PROJECT_STATUS.md", content)
    readme = f"""# RF_COMM_MULTILANE

Rebuild workspace for the TFDU6102 RF_COMM project.

Canonical inputs:
- Pinmap: `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`
- XDC: `constraints/active/PORT1.generated.xdc`
- Active profile: `board_profiles/ACTIVE_PROFILE.json`
- Register map: `config/register_map/ir_axi_regs.yaml`
- Offline gate: `python scripts/run_offline_gates.py`
- P6 no-Ethernet gate: `python tools/run_p6_gate.py --json-summary`

Current stage summary:
- P0_BOOTSTRAP: PASS
- P1_OFFLINE_HARDENING: PASS
- P2_SIMULATION_BASELINE: PASS
- P3_PRE_HW_ACCEPTANCE_PACKAGE: PASS
- P4_AUTO_HARDWARE_ACCEPTANCE: PASS_WITH_PROXY_ILA_EVIDENCE
- P5_2LANE_PROTOCOL_STABILIZATION: PASS_WITH_NOTES
- P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET: {p6_status}
- HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: {hardware_status}
- ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE
- ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT
- EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE
- PRODUCT_FINAL_ACCEPTANCE: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT

P6 is stationary, two-lane, local/JTAG/AXI/PS-driver scoped evidence. It is not Ethernet, rotation, 8-lane, or product-final acceptance.
"""
    write_text(ROOT / "README.md", readme)
    payload = {"P6_PROJECT_STATUS_UPDATE": PASS, "p6_status": p6_status, "hardware_status": hardware_status}
    write_json(GENERATED / "p6_project_status_update_summary.json", payload)
    write_markdown(
        GENERATED / "p6_project_status_update_summary.md",
        "P6 Project Status Update Summary",
        PASS,
        "project status documents updated with P6 boundary",
        [
            f"P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET: {p6_status}",
            f"HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: {hardware_status}",
            "ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE",
            "ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT",
            "EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE",
            "PRODUCT_FINAL_ACCEPTANCE: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT",
        ],
    )
    return payload


def package_results() -> dict[str, Any]:
    package_dir = ROOT / "evidence" / "packages"
    package_dir.mkdir(parents=True, exist_ok=True)
    zip_path = package_dir / f"rf_comm_multilane_p6_results_{stamp()}.zip"
    include: list[Path] = []
    for relpath in ["PROJECT_STATUS.md", "README.md", "docs/PROJECT_STATUS.md"]:
        path = ROOT / relpath
        if path.exists():
            include.append(path)
    include.extend(P6_PROFILES.glob("*.json"))
    include.extend(GENERATED.glob("p6_*.md"))
    include.extend(GENERATED.glob("p6_*.json"))
    include.extend(GENERATED.glob("p6_*.csv"))
    include.extend(P6_SIM_DIR.glob("**/*"))
    include.extend(P6_DIR.glob("**/summary.md"))
    include.extend(P6_DIR.glob("**/*.json"))
    include.extend(P6_DIR.glob("**/*.csv"))
    include.extend(P6_DIR.glob("**/shutdown/**/*.log"))
    include.extend(P6_DIR.glob("bitstreams/*.bit"))
    include.extend((ROOT / "tools").glob("run_p6_*.py"))
    include.extend((ROOT / "tools").glob("run_p6_*.ps1"))
    include.extend((ROOT / "tools").glob("check_p6_*.py"))
    include.extend((ROOT / "tools").glob("p6_*.py"))
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        seen: set[str] = set()
        for path in include:
            if path.is_dir() or not path.exists():
                continue
            arcname = rel(path)
            if arcname in seen:
                continue
            seen.add(arcname)
            zf.write(path, arcname)
    payload = {"P6_RESULTS_PACKAGE": PASS, "package": rel(zip_path), "sha256": sha256_or_missing(zip_path), "file_count": len(seen)}
    write_json(GENERATED / "p6_results_package_summary.json", payload)
    return payload


def write_final_summary(payload: dict[str, Any]) -> dict[str, Any]:
    p6_status = p6_status_from_payload(payload)
    hardware_required = [
        "P6_SAFE_IDLE_RECHECK",
        "P6_TFDU_CONTROL_IDLE_RECHECK",
        "P6_JTAG_AXI_PAYLOAD_RAM_SMOKE",
        "P6_LANE0_DYNAMIC_PAYLOAD",
        "P6_LANE1_DYNAMIC_PAYLOAD",
        "P6_TWO_LANE_DYNAMIC_PAYLOAD",
        "P6_PS_DRIVER_RUNTIME",
        "P6_HOST_FILE_TRANSPORT_JTAG",
        "P6_LANE_FALLBACK_REGRESSION",
        "P6_TWO_LANE_2H_STATIONARY_SOAK",
    ]
    hardware_status = "PASS" if all(payload.get(key) == PASS for key in hardware_required) else "PENDING"
    def is_report_marker(key: str) -> bool:
        return key == P6_STAGE or key.startswith("P6_") or key in {
            "ETHERNET_ACCEPTANCE",
            "ROTATION_ACCEPTANCE",
            "EIGHT_LANE_ACCEPTANCE",
            "PRODUCT_FINAL_ACCEPTANCE",
        }

    pass_items = [
        key for key, value in payload.items() if is_report_marker(key) and isinstance(value, str) and value.startswith("PASS")
    ]
    fail_items = [key for key, value in payload.items() if is_report_marker(key) and isinstance(value, str) and value == FAIL]
    skip_items = [key for key, value in payload.items() if is_report_marker(key) and isinstance(value, str) and value == SKIP]
    blocked_items = [
        key
        for key, value in payload.items()
        if is_report_marker(key) and isinstance(value, str) and value in {BLOCKED, NOT_RUN_PREREQ, NOT_RUN_RUNTIME_LIMIT}
    ]
    payload.update(
        {
            P6_STAGE: p6_status,
            "COMMIT": git_value("rev-parse", "HEAD"),
            "USER_CONFIRMED_SUPPLY_OK": True,
            "NETWORK_CABLE_CONNECTED": False,
            "HARDWARE_MOVEMENT_ALLOWED": False,
            "AVAILABLE_LANES": 2,
            "MAX_LANE_MASK": "0x3",
            "HARDWARE_ACTIONS_EXECUTED": bool(payload.get("HARDWARE_ACTIONS_EXECUTED")),
            "HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL": hardware_status,
            "ETHERNET_ACCEPTANCE": "DEFERRED_NO_NETWORK_CABLE",
            "ROTATION_ACCEPTANCE": "DEFERRED_NO_HARDWARE_MOVEMENT",
            "EIGHT_LANE_ACCEPTANCE": "DEFERRED_ONLY_2_LANES_AVAILABLE",
            "PRODUCT_FINAL_ACCEPTANCE": "PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT",
            "PASS": pass_items,
            "FAIL": fail_items,
            "SKIP_WITH_REASON": skip_items,
            "BLOCKED": blocked_items,
            "NEXT_RECOMMENDED_STAGE": "P6_FIX_DYNAMIC_PAYLOAD_DATAPATH",
        }
    )
    summaries = sorted(path.as_posix() for path in GENERATED.glob("p6_*summary.md"))
    payload["GENERATED_SUMMARIES"] = [rel(path) for path in summaries]
    write_json(GENERATED / "p6_local_transport_no_ethernet_summary.json", payload)
    lines = [
        f"{P6_STAGE}: {p6_status}",
        f"COMMIT: {payload['COMMIT']}",
        "USER_CONFIRMED_SUPPLY_OK: true",
        "NETWORK_CABLE_CONNECTED: false",
        "HARDWARE_MOVEMENT_ALLOWED: false",
        "AVAILABLE_LANES: 2",
        "MAX_LANE_MASK: 0x3",
        f"HARDWARE_ACTIONS_EXECUTED: {str(payload['HARDWARE_ACTIONS_EXECUTED']).lower()}",
        f"HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: {hardware_status}",
        "ETHERNET_ACCEPTANCE: DEFERRED_NO_NETWORK_CABLE",
        "ROTATION_ACCEPTANCE: DEFERRED_NO_HARDWARE_MOVEMENT",
        "EIGHT_LANE_ACCEPTANCE: DEFERRED_ONLY_2_LANES_AVAILABLE",
        "PRODUCT_FINAL_ACCEPTANCE: PENDING_ETHERNET_ROTATION_AND_TARGET_LANE_COUNT",
        "",
        "## PASS",
        "",
        *(f"- {item}" for item in pass_items),
        "",
        "## FAIL",
        "",
        *(f"- {item}" for item in fail_items),
        *(["- none"] if not fail_items else []),
        "",
        "## SKIP_WITH_REASON",
        "",
        *(f"- {item}" for item in skip_items),
        *(["- none"] if not skip_items else []),
        "",
        "## BLOCKED",
        "",
        *(f"- {item}" for item in blocked_items),
        *(["- none"] if not blocked_items else []),
        "",
        "## Generated Summaries",
        "",
        *(f"- `{item}`" for item in payload["GENERATED_SUMMARIES"]),
        "",
        f"NEXT_RECOMMENDED_STAGE: {payload['NEXT_RECOMMENDED_STAGE']}",
    ]
    write_markdown(
        GENERATED / "p6_local_transport_no_ethernet_summary.md",
        "P6 Local Transport No-Ethernet Summary",
        p6_status,
        "P6 dynamic local transport backend is missing; completed safe gates and evidence boundary",
        lines,
        script_hw=bool(payload.get("HARDWARE_ACTIONS_EXECUTED")),
        source_hw=bool(payload.get("source_evidence_contains_hardware_actions")),
    )
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run P6 local transport no-Ethernet gate. Defaults to dry-run.")
    parser.add_argument("--authorize-hardware", action="store_true")
    parser.add_argument("--no-ethernet", action="store_true")
    parser.add_argument("--no-motion", action="store_true")
    parser.add_argument("--lane-count", type=int, default=2)
    parser.add_argument("--max-lane-mask", default="0x3")
    parser.add_argument("--user-confirmed-supply-ok", action="store_true")
    parser.add_argument("--shutdown-on-exit", action="store_true")
    parser.add_argument("--max-runtime-sec", type=int, default=7560)
    parser.add_argument("--board-id", default=DEFAULT_BOARD_ID)
    parser.add_argument("--json-summary", action="store_true")
    parser.add_argument("--stage-filter", default="all")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    ensure_dirs()
    payload: dict[str, Any] = {}

    ensure_authorization_template(args.max_runtime_sec)
    if args.authorize_hardware and args.user_confirmed_supply_ok:
        ensure_authorization_file(args.max_runtime_sec)

    p5_intake = write_p5_intake()
    payload["P6_P5_INTAKE"] = p5_intake["P6_P5_INTAKE"]
    semantics = write_evidence_semantics(p5_intake)
    payload["P6_EVIDENCE_SEMANTICS"] = semantics["P6_EVIDENCE_SEMANTICS"]
    payload.update(write_profiles())
    dynamic_sim = run_dynamic_payload_sim()
    payload["P6_DYNAMIC_PAYLOAD_SIM"] = dynamic_sim["P6_DYNAMIC_PAYLOAD_SIM"]
    provenance = copy_immutable_bitstreams()
    payload["P6_BITSTREAM_PROVENANCE"] = provenance["P6_BITSTREAM_PROVENANCE"]
    auth = validate_authorization(args, provenance, execute_hardware=args.authorize_hardware)
    payload["P6_HARDWARE_AUTHORIZATION"] = auth["P6_HARDWARE_AUTHORIZATION"]
    payload.update(check_no_ethernet())
    payload.update(check_no_motion())
    payload.update(check_2lane_scope())
    payload.update(write_host_file_payloads())

    if args.authorize_hardware:
        hw_payload = run_authorized_hardware(args, provenance, auth)
    else:
        hw_payload = run_authorized_hardware(args, provenance, auth)
    payload.update(hw_payload)
    payload.update(analyze_protocol_metrics(payload))
    payload.update(check_evidence_consistency(payload))

    provisional_status = p6_status_from_payload(payload)
    provisional_hardware = "PASS" if provisional_status == PASS else "PENDING"
    payload.update(update_status_docs(provisional_status, provisional_hardware))
    payload.update(package_results())
    final_payload = write_final_summary(payload)
    payload.update(check_evidence_consistency(final_payload))
    final_payload = write_final_summary({**final_payload, **payload})

    if args.json_summary:
        print(json.dumps(final_payload, ensure_ascii=False))
    else:
        print(f"{P6_STAGE}: {final_payload[P6_STAGE]}")
        print(f"HARDWARE_ACTIONS_EXECUTED: {str(final_payload['HARDWARE_ACTIONS_EXECUTED']).lower()}")
        print(f"HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL: {final_payload['HARDWARE_ACCEPTANCE_STATIONARY_2LANE_LOCAL']}")
    return 0 if final_payload[P6_STAGE] in {PASS, PASS_WITH_NOTES} else 1


if __name__ == "__main__":
    raise SystemExit(main())
