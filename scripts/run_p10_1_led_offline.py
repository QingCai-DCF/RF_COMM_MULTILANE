#!/usr/bin/env python3
"""Run the dedicated no-hardware P10.1 AX7020 PL activity LED checks."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated/p10_1_led_offline"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
TOOLS = {name: VIVADO_BIN / f"{name}.bat" for name in ("xvlog", "xelab", "xsim")}
CONFIG = ROOT / "config/hardware/p10_1_ax7020_pl_activity_leds.yaml"
ROLE_XDCS = {
    "fixed": ROOT / "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
    "rotating": ROOT / "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
}
SOURCE_FILES = [
    "rtl/p10_lane_activity_leds.sv",
    "rtl/p9_optical_transport_core.sv",
    "rtl/p9_axi_dma_peripheral.sv",
    "rtl/p9_axi_dma_peripheral_bd.v",
    "rtl/p10_axi_dma_endpoint_peripheral_bd.v",
    "sim/tb/tb_p10_lane_activity_leds.sv",
    "scripts/run_p10_1_led_offline.py",
    "scripts/build_p10_ax7020_functional.py",
    "scripts/vivado/build_p10_ax7020_functional.tcl",
    "board_profiles/ax7020_fixed_2lane/profile.yaml",
    "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
    "board_profiles/ax7020_rotating_2lane/profile.yaml",
    "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
    "config/hardware/p10_1_ax7020_pl_activity_leds.yaml",
    "config/project_requirements.yaml",
    "docs/REQUIREMENT_TRACEABILITY_MATRIX.md",
    "docs/hardware/P10_1_AX7020_PL_ACTIVITY_LED_DESIGN.md",
]
INTEGRATION_RTL = [
    "rtl/ir_seq_math_pkg.sv",
    "rtl/ir_health_weighted_scheduler.sv",
    "rtl/ir_selective_repeat_tx.sv",
    "rtl/ir_selective_repeat_rx.sv",
    "rtl/ir_ack_aggregator.sv",
    "rtl/ir_data_plane_top.sv",
    "rtl/ir_tfdu_exact_duty_accountant.sv",
    "rtl/ir_tfdu_physical_module_safety.sv",
    "rtl/tfdu_lane_phy.sv",
    "rtl/ir_4ppm_codec.sv",
    "rtl/p9_rate_4ppm_rx.sv",
    "rtl/p9_4ppm_frame_tx.sv",
    "rtl/p9_4ppm_frame_rx.sv",
    "rtl/p10_1r_rx_admission.sv",
    "rtl/p9_optical_transport_core.sv",
    "rtl/p6_axi_lite_bridge.sv",
    "rtl/p10_1_metric_counter.sv",
    "rtl/p10_1_timer_snapshot.sv",
    "rtl/p10_1_event_fifo.sv",
    "rtl/p10_1_perf_monitor.sv",
    "rtl/p9_axi_dma_peripheral.sv",
    "rtl/p10_lane_activity_leds.sv",
    "rtl/p10_axi_dma_endpoint_peripheral_bd.v",
]
SOURCE_FILES = sorted(set([*SOURCE_FILES, *INTEGRATION_RTL]))


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def run_led_xsim(raw: Path) -> dict[str, Any]:
    work = raw / "xsim_work"
    work.mkdir(parents=True, exist_ok=False)
    log = raw / "p10_lane_activity_leds_xsim.log"
    commands = [
        [
            str(TOOLS["xvlog"]),
            "-sv",
            str(ROOT / "rtl/p10_lane_activity_leds.sv"),
            str(ROOT / "sim/tb/tb_p10_lane_activity_leds.sv"),
        ],
        [
            str(TOOLS["xelab"]),
            "tb_p10_lane_activity_leds",
            "-debug",
            "typical",
            "-s",
            "p10_lane_activity_leds_snapshot",
        ],
        [
            str(TOOLS["xsim"]),
            "p10_lane_activity_leds_snapshot",
            "-runall",
        ],
    ]
    chunks = [f"STARTED_UTC={now()}\n"]
    returncode = 0
    for command in commands:
        chunks.append("COMMAND=" + subprocess.list2cmdline(command) + "\n")
        result = subprocess.run(
            command,
            cwd=work,
            text=True,
            capture_output=True,
            timeout=300,
            shell=False,
            env={
                **os.environ,
                "NO_HARDWARE": "1",
                "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
            },
        )
        chunks.extend(
            [
                f"RETURN_CODE={result.returncode}\n",
                "STDOUT_BEGIN\n",
                result.stdout,
                "\nSTDOUT_END\n",
                "STDERR_BEGIN\n",
                result.stderr,
                "\nSTDERR_END\n",
            ]
        )
        returncode = result.returncode
        if returncode != 0:
            break
    content = "".join(chunks) + f"FINISHED_UTC={now()}\n"
    log.write_text(content, encoding="utf-8", errors="replace", newline="\n")
    marker = "TB_P10_LANE_ACTIVITY_LEDS=PASS"
    status = "PASS" if returncode == 0 and marker in content and "=FAIL" not in content else "FAIL"
    return {
        "test_id": "P10_1-LED-XSIM-001",
        "status": status,
        "returncode": returncode,
        "required_marker": marker,
        "log": rel(log),
        "log_sha256": sha256(log),
    }


def run_integration_elaboration(raw: Path) -> dict[str, Any]:
    work = raw / "integration_elaboration_work"
    work.mkdir(parents=True, exist_ok=False)
    log = raw / "p10_led_full_rtl_elaboration.log"
    commands = [
        [
            str(TOOLS["xvlog"]),
            "-sv",
            "-i",
            str(ROOT / "rtl"),
            *[str(ROOT / item) for item in INTEGRATION_RTL],
        ],
        [
            str(TOOLS["xelab"]),
            "p10_axi_dma_endpoint_peripheral_bd",
            "-s",
            "p10_led_full_rtl_snapshot",
        ],
    ]
    chunks = [f"STARTED_UTC={now()}\n"]
    returncode = 0
    for command in commands:
        chunks.append("COMMAND=" + subprocess.list2cmdline(command) + "\n")
        result = subprocess.run(
            command,
            cwd=work,
            text=True,
            capture_output=True,
            timeout=300,
            shell=False,
            env={
                **os.environ,
                "NO_HARDWARE": "1",
                "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
            },
        )
        chunks.extend(
            [
                f"RETURN_CODE={result.returncode}\n",
                "STDOUT_BEGIN\n",
                result.stdout,
                "\nSTDOUT_END\n",
                "STDERR_BEGIN\n",
                result.stderr,
                "\nSTDERR_END\n",
            ]
        )
        returncode = result.returncode
        if returncode != 0:
            break
    content = "".join(chunks) + f"FINISHED_UTC={now()}\n"
    log.write_text(content, encoding="utf-8", errors="replace", newline="\n")
    marker = "Built simulation snapshot p10_led_full_rtl_snapshot"
    status = "PASS" if returncode == 0 and marker in content else "FAIL"
    return {
        "test_id": "P10_1-LED-FULL-RTL-ELABORATION-001",
        "status": status,
        "returncode": returncode,
        "required_marker": marker,
        "log": rel(log),
        "log_sha256": sha256(log),
    }


def parse_xdc_ports(text: str) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    pattern = re.compile(
        r"set_property\s+(?P<property>\S+)\s+(?P<value>\S+)\s+"
        r"\[get_ports\s+\{(?P<port>[^}]+)\}\]"
    )
    for match in pattern.finditer(text):
        result.setdefault(match.group("port"), []).append(
            {"property": match.group("property"), "value": match.group("value")}
        )
    return result


def static_audit(raw: Path) -> dict[str, Any]:
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    errors: list[str] = []
    checks: dict[str, bool] = {}

    expected_pins = {
        int(item["rtl_bit"]): item["package_pin"] for item in config["pins"]
    }
    for role, xdc_path in ROLE_XDCS.items():
        ports = parse_xdc_ports(xdc_path.read_text(encoding="utf-8"))
        all_package_pins: dict[str, list[str]] = {}
        for port, properties in ports.items():
            for item in properties:
                if item["property"] == "PACKAGE_PIN":
                    all_package_pins.setdefault(item["value"], []).append(port)
        for bit, pin in expected_pins.items():
            port = f"pl_activity_led_n_o[{bit}]"
            props = ports.get(port, [])
            pin_ok = {"property": "PACKAGE_PIN", "value": pin} in props
            checks[f"{role}_{port}_pin"] = pin_ok
            checks[f"{role}_{port}_pin_unique"] = all_package_pins.get(pin) == [port]
            if not pin_ok:
                errors.append(f"{role} {port} is not constrained to {pin}")
            if all_package_pins.get(pin) != [port]:
                errors.append(f"{role} {pin} is absent, duplicated, or conflicts")
        wildcard = ports.get("pl_activity_led_n_o[*]", [])
        for prop, value in (
            ("IOSTANDARD", "LVCMOS33"),
            ("DRIVE", "4"),
            ("SLEW", "SLOW"),
        ):
            ok = {"property": prop, "value": value} in wildcard
            checks[f"{role}_{prop.lower()}"] = ok
            if not ok:
                errors.append(f"{role} LED bus lacks {prop}={value}")

    for source_name, source in config["source_documents"].items():
        path = Path(source["path"])
        exists = path.is_file()
        digest_ok = exists and sha256(path) == source["sha256"]
        checks[f"{source_name}_exists"] = exists
        checks[f"{source_name}_sha256"] = digest_ok
        if not exists:
            errors.append(f"missing read-only source {source['path']}")
        elif not digest_ok:
            errors.append(f"source hash mismatch {source['path']}")

    led_rtl = (ROOT / "rtl/p10_lane_activity_leds.sv").read_text(encoding="utf-8")
    wrapper = (ROOT / "rtl/p10_axi_dma_endpoint_peripheral_bd.v").read_text(
        encoding="utf-8"
    )
    transport = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
        encoding="utf-8"
    )
    integration_checks = {
        "monitor_has_no_global_permit_input": re.search(
            r"\binput\b[^;\n]*global_permit", led_rtl, flags=re.IGNORECASE
        ) is None,
        "tx_taps_final_role_local_output": ".final_txd_activity_i(tfdu_txd_o)" in wrapper,
        "rx_taps_crc_valid_frame": (
            "rx_frame_valid[1] && rx_frame_crc[1]" in transport
            and "rx_frame_valid[0] && rx_frame_crc[0]" in transport
        ),
        "shutdown_clears_holds": (
            "else if (effective_full_shutdown_i)" in led_rtl
            and "hold_counter_q[led_index] <= 0;" in led_rtl
        ),
        "reset_shutdown_drive_all_off": (
            "(!rst_n || effective_full_shutdown_i)" in led_rtl
            and "4'b1111" in led_rtl
        ),
        "configured_hold_is_200ms": (
            ".TICK_HZ(1_000)" in wrapper and ".HOLD_MS(200)" in wrapper
        ),
        "feedback_absent": "input  wire [3:0] pl_led_n_o" not in led_rtl,
    }
    checks.update(integration_checks)
    errors.extend(
        f"integration check failed: {name}"
        for name, passed in integration_checks.items()
        if not passed
    )

    report = {
        "test_id": "P10_1-LED-STATIC-INTEGRATION-001",
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "errors": errors,
    }
    path = raw / "static_integration_audit.json"
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report["log"] = rel(path)
    report["log_sha256"] = sha256(path)
    return report


def main() -> int:
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        print("P10_1_LED_OFFLINE_REFUSED: offline environment required", file=sys.stderr)
        return 2
    missing = [str(path) for path in TOOLS.values() if not path.is_file()]
    if missing:
        print("P10_1_LED_OFFLINE_REFUSED: missing tools: " + ", ".join(missing),
              file=sys.stderr)
        return 2
    missing_sources = [item for item in SOURCE_FILES if not (ROOT / item).is_file()]
    if missing_sources:
        print("P10_1_LED_OFFLINE_REFUSED: missing sources: " + ", ".join(missing_sources),
              file=sys.stderr)
        return 2

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    raw = OUT / "raw" / run_id
    raw.mkdir(parents=True, exist_ok=False)
    results = [run_led_xsim(raw), run_integration_elaboration(raw), static_audit(raw)]
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    source_dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=no", "--", *SOURCE_FILES],
            cwd=ROOT,
            text=True,
        )
    )
    summary = {
        "schema_version": 1,
        "test_id": "P10_1-AX7020-PL-ACTIVITY-LED-OFFLINE",
        "status": status,
        "generated_at_utc": now(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_worktree_dirty": source_dirty,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "jtag_connected": False,
        "fpga_programmed": False,
        "source_sha256": {item: sha256(ROOT / item) for item in SOURCE_FILES},
        "results": results,
        "raw_run": rel(raw),
    }
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "summary.json"
    md_path = OUT / "summary.md"
    json_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        "# P10.1 AX7020 PL activity LED offline verification",
        "",
        f"- Status: `{status}`",
        f"- Source commit: `{summary['source_commit']}`",
        f"- Source worktree dirty: `{str(source_dirty).lower()}`",
        "- Hardware actions executed: `false`",
        "",
        "| Test ID | Status | Raw evidence | SHA256 |",
        "|---|---|---|---|",
    ]
    for item in results:
        lines.append(
            f"| {item['test_id']} | {item['status']} | `{item['log']}` | "
            f"`{item['log_sha256']}` |"
        )
    lines.extend(["", f"Raw run: `{rel(raw)}`", ""])
    md_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print(f"P10_1_LED_OFFLINE={status}")
    print(f"P10_1_LED_OFFLINE_SUMMARY={rel(json_path)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
