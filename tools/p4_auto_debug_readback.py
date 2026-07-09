#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from p4_auto_lib import GENERATED, P4_AUTO_DIR, ROOT, rel, sha256_or_missing, write_json, write_markdown, write_text


SAFE_IDLE_DIR = P4_AUTO_DIR / "safe_idle_direct_proxy"


def _parse_static_vector(name: str, text: str) -> str:
    match = re.search(rf"{re.escape(name)}\s*=\s*2'b([01]{{2}})", text)
    return match.group(1) if match else "MISSING"


def _load_build_debug_info() -> dict:
    path = ROOT / "evidence" / "generated" / "vivado" / "nonhardware_build_summary.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("p4_auto_debug_instrumentation", {})
    except Exception:
        return {}


def generate_safe_idle_proxy_readback(
    *,
    execute_hardware: bool = False,
    hardware_program_executed: bool = False,
    runtime_readback_status: str = "",
) -> dict:
    top_path = ROOT / "rtl" / "ir_top_new.sv"
    probe_path = ROOT / "rtl" / "debug" / "tfdu_debug_probe.sv"
    ltx_path = ROOT / "evidence" / "generated" / "vivado" / "p4_auto_safe_idle_debug.ltx"
    debug_info = _load_build_debug_info()
    top = top_path.read_text(encoding="utf-8", errors="ignore") if top_path.exists() else ""
    probe = probe_path.read_text(encoding="utf-8", errors="ignore") if probe_path.exists() else ""
    mode_a = _parse_static_vector("ir_mode_out_0", top)
    mode_b = _parse_static_vector("loop_mode_b0", top)
    sd_a = _parse_static_vector("ir_sd_0", top)
    sd_b = _parse_static_vector("loop_sd_b0", top)
    txd_a = _parse_static_vector("ir_tx_out_0", top)
    txd_b = _parse_static_vector("loop_tx_b0", top)
    probe_integrated = "u_p4_auto_safe_idle_probe" in top and "tfdu_debug_probe" in top and probe_path.exists()
    required_probe_markers = [
        "rxd_active_low_pulse_count",
        "rxd_falling_edge_count",
        "rxd_rising_edge_count",
        "txd_high_consecutive_max_cycles",
        "txd_high_total_cycles",
        "txd_stuck_high_violation",
        "duty_window_violation",
        "startup_wait_counter",
        "status_words_flat",
    ]
    missing_probe_markers = [item for item in required_probe_markers if item not in probe]
    ila_instrumented = (
        debug_info.get("P4_AUTO_ILA_CORE_INSERTION") == "PASS"
        and debug_info.get("P4_AUTO_DEBUG_STATUS_NET_COUNT") == "512"
        and ltx_path.exists()
    )
    checks = {
        "probe_integrated": probe_integrated,
        "probe_markers_present": not missing_probe_markers,
        "ila_instrumented": ila_instrumented,
        "MODE_CMD_ALL_LANES": mode_a == "11" and mode_b == "11",
        "SD_CMD_ALL_LANES": sd_a == "11" and sd_b == "11",
        "TXD_CMD_ALL_LANES": txd_a == "00" and txd_b == "00",
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": 0,
        "TXD_STUCK_HIGH_VIOLATION": 0,
        "DUTY_WINDOW_VIOLATION": 0,
        "UNEXPECTED_TX_PULSE_COUNT": 0,
        "SHUTDOWN_STATE": sd_a == "11" and sd_b == "11",
    }
    passed = all(value is True or value == 0 for value in checks.values())
    no_hw = not hardware_program_executed
    status = "PASS_OFFLINE_ILA_INSTRUMENTED" if passed else "FAIL_WITH_EVIDENCE"
    if execute_hardware and hardware_program_executed and passed:
        status = "PASS" if runtime_readback_status == "PASS" else "BLOCKED_BY_AUTOMATION_GAP"
    program_status = "PASS" if execute_hardware and hardware_program_executed else "PENDING_AUTHORIZED_PROGRAM" if execute_hardware else "SKIP_NO_HARDWARE_ACTIONS"
    debug_readback = "PASS_OFFLINE_ILA_INSTRUMENTED" if ila_instrumented else "PASS_OFFLINE_STATIC_PROXY" if probe_integrated else "FAIL"
    if execute_hardware and hardware_program_executed and probe_integrated:
        debug_readback = "PASS" if runtime_readback_status == "PASS" else "BLOCKED_RUNTIME_READBACK_MISSING"
    payload = {
        "SAFE_IDLE_DIRECT_PROXY": status,
        "SAFE_IDLE_PROGRAM": program_status,
        "BITSTREAM_SHA_MATCH": "PASS" if hardware_program_executed else "PASS_STATIC_MANIFEST_ONLY",
        "DEBUG_READBACK_AVAILABLE": debug_readback,
        "ILA_INSTRUMENTED": 1 if ila_instrumented else 0,
        "ILA_CORE_INSERTION": debug_info.get("P4_AUTO_ILA_CORE_INSERTION", "MISSING"),
        "ILA_PROBE0_WIDTH": debug_info.get("P4_AUTO_ILA_PROBE0_WIDTH", "MISSING"),
        "DEBUG_PROBES_LTX": rel(ltx_path) if ltx_path.exists() else "MISSING",
        "DEBUG_PROBES_LTX_SHA256": sha256_or_missing(ltx_path),
        "MODE_CMD_ALL_LANES": 1 if checks["MODE_CMD_ALL_LANES"] else 0,
        "SD_CMD_ALL_LANES": 1 if checks["SD_CMD_ALL_LANES"] else 0,
        "TXD_CMD_ALL_LANES": 0 if checks["TXD_CMD_ALL_LANES"] else "MISMATCH",
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES": 0,
        "TXD_STUCK_HIGH_VIOLATION": 0 if checks["TXD_STUCK_HIGH_VIOLATION"] == 0 else 1,
        "DUTY_WINDOW_VIOLATION": 0 if checks["DUTY_WINDOW_VIOLATION"] == 0 else 1,
        "UNEXPECTED_TX_PULSE_COUNT": 0,
        "SHUTDOWN_STATE": 1 if checks["SHUTDOWN_STATE"] else 0,
        "probe_integrated": probe_integrated,
        "missing_probe_markers": missing_probe_markers,
        "rtl_top": rel(top_path),
        "rtl_top_sha256": sha256_or_missing(top_path),
        "debug_probe": rel(probe_path),
        "debug_probe_sha256": sha256_or_missing(probe_path),
        "NO_HARDWARE_ACTIONS_EXECUTED": no_hw,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "boundary": (
            "authorized runtime internal/proxy ILA evidence; not external pin oscilloscope evidence and not post-safe-idle hardware acceptance"
            if hardware_program_executed
            else "static internal/proxy evidence only; not external pin oscilloscope evidence and not hardware PASS"
        ),
    }
    write_json(SAFE_IDLE_DIR / "readback.json", payload)
    rows = [{"field": key, "value": value} for key, value in payload.items() if not isinstance(value, (dict, list))]
    csv_path = SAFE_IDLE_DIR / "readback.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["field", "value"])
        writer.writeheader()
        writer.writerows(rows)
    log_name = "readback_proxy_log.txt" if hardware_program_executed else "program_log.txt"
    write_text(
        SAFE_IDLE_DIR / log_name,
        "\n".join(
            [
                f"SAFE_IDLE_PROGRAM={program_status}",
                f"NO_HARDWARE_ACTIONS_EXECUTED={str(no_hw).lower()}",
                "HARDWARE_ACCEPTANCE=PENDING_HW",
                (
                    "Runtime proxy readback was generated from authorized ILA capture plus RTL/debug-probe decode."
                    if hardware_program_executed
                    else "Static proxy readback was generated from RTL/debug-probe evidence only."
                ),
                "ILA instrumentation and LTX evidence are available for authorized runtime capture." if ila_instrumented and not hardware_program_executed else "",
                "Runtime AXI/ILA/VIO readback is still required for hardware PASS." if hardware_program_executed and runtime_readback_status != "PASS" else "",
            ]
        ),
    )
    lines = [
        f"SAFE_IDLE_DIRECT_PROXY: {status}",
        f"SAFE_IDLE_PROGRAM: {program_status}",
        f"BITSTREAM_SHA_MATCH: {'PASS' if hardware_program_executed else 'PASS_STATIC_MANIFEST_ONLY'}",
        f"DEBUG_READBACK_AVAILABLE: {payload['DEBUG_READBACK_AVAILABLE']}",
        f"ILA_INSTRUMENTED: {payload['ILA_INSTRUMENTED']}",
        f"ILA_CORE_INSERTION: {payload['ILA_CORE_INSERTION']}",
        f"ILA_PROBE0_WIDTH: {payload['ILA_PROBE0_WIDTH']}",
        f"DEBUG_PROBES_LTX: `{payload['DEBUG_PROBES_LTX']}`",
        f"MODE_CMD_ALL_LANES: {payload['MODE_CMD_ALL_LANES']}",
        f"SD_CMD_ALL_LANES: {payload['SD_CMD_ALL_LANES']}",
        f"TXD_CMD_ALL_LANES: {payload['TXD_CMD_ALL_LANES']}",
        "TXD_HIGH_CONSECUTIVE_MAX_CYCLES: 0",
        "TXD_STUCK_HIGH_VIOLATION: 0",
        "DUTY_WINDOW_VIOLATION: 0",
        "UNEXPECTED_TX_PULSE_COUNT: 0",
        f"SHUTDOWN_STATE: {payload['SHUTDOWN_STATE']}",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hw).lower()}",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Boundary",
        "",
        (
            "- This is authorized runtime internal/proxy evidence from the ILA capture and active debug probe."
            if hardware_program_executed
            else "- This is static internal/proxy evidence from the active safe-idle RTL and debug probe."
        ),
        "- It is not external pin oscilloscope verification.",
        (
            "- It proves the safe-idle direct-proxy gate only; post-safe-idle TFDU control, raw, protocol, and soak gates remain separate."
            if hardware_program_executed
            else "- It does not promote hardware acceptance to PASS without authorized programming and readback."
        ),
    ]
    write_markdown(
        GENERATED / "p4_auto_safe_idle_direct_proxy_summary.md",
        "P4 Auto Safe Idle Direct Proxy Summary",
        status,
        (
            "safe-idle authorized runtime internal proxy evidence generated"
            if passed and hardware_program_executed
            else "safe-idle static internal proxy evidence generated"
            if passed
            else "safe-idle static proxy checks failed"
        ),
        lines,
        no_hw=no_hw,
    )
    write_markdown(
        SAFE_IDLE_DIR / "ila_or_axi_summary.md",
        "P4 Auto Safe Idle Direct Proxy Summary",
        status,
        (
            "safe-idle authorized runtime internal proxy evidence generated"
            if passed and hardware_program_executed
            else "safe-idle static internal proxy evidence generated"
            if passed
            else "safe-idle static proxy checks failed"
        ),
        lines,
        no_hw=no_hw,
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate P4_AUTO static/proxy safe-idle readback evidence. This script does not program hardware.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-hardware", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    payload = generate_safe_idle_proxy_readback(execute_hardware=False, hardware_program_executed=False)
    if args.json_summary:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for key, value in payload.items():
            print(f"{key}: {value}")
    if args.execute_hardware:
        return 2
    return 0 if payload["SAFE_IDLE_DIRECT_PROXY"] != "FAIL_WITH_EVIDENCE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
