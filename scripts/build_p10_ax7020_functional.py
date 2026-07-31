#!/usr/bin/env python3
"""Build, audit, and freeze the two offline P10 AX7020 functional designs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
TCL = ROOT / "scripts/vivado/build_p10_ax7020_functional.tcl"
OUT = ROOT / "evidence/generated/vivado/p10_ax7020_functional"
ARTIFACTS = ROOT / "artifacts/p10"
SUMMARY_JSON = ROOT / "evidence/generated/p10_ax7020_functional_build_summary.json"
SUMMARY_MD = ROOT / "evidence/generated/p10_ax7020_functional_build_summary.md"
CAMPAIGN = "p10"
TEST_ID = "P10-AX7020-DUAL-FUNCTIONAL-BUILD"
SUMMARY_TITLE = "P10 AX7020 dual functional build"
GOAL_HASH = "b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603"

RTL = [
    "rtl/generated/tfdu_safety_config.svh",
    "rtl/generated/ir_register_map_defs.svh",
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

ROLES = {
    "fixed": {
        "role_value": "1",
        "profile": "P10_AX7020_FIXED_2LANE",
        "profile_path": "board_profiles/ax7020_fixed_2lane/profile.yaml",
        "xdc": "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
    },
    "rotating": {
        "role_value": "2",
        "profile": "P10_AX7020_ROTATING_2LANE",
        "profile_path": "board_profiles/ax7020_rotating_2lane/profile.yaml",
        "xdc": "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def configure_campaign(campaign: str) -> None:
    global OUT, ARTIFACTS, SUMMARY_JSON, SUMMARY_MD
    global CAMPAIGN, TEST_ID, SUMMARY_TITLE
    CAMPAIGN = campaign
    if campaign == "p10":
        return
    if campaign != "p10_1_led":
        raise ValueError(f"unsupported campaign: {campaign}")
    OUT = ROOT / "evidence/generated/vivado/p10_1_ax7020_pl_activity_led"
    ARTIFACTS = ROOT / "artifacts/p10_1_led"
    SUMMARY_JSON = ROOT / "evidence/generated/p10_1_ax7020_pl_activity_led_build_summary.json"
    SUMMARY_MD = ROOT / "evidence/generated/p10_1_ax7020_pl_activity_led_build_summary.md"
    TEST_ID = "P10_1-AX7020-PL-ACTIVITY-LED-DUAL-ROUTED-BUILD"
    SUMMARY_TITLE = "P10.1 AX7020 PL activity LED dual routed build"


def tracked_source_dirty(paths: list[str]) -> bool:
    return bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", *paths],
        cwd=ROOT, text=True))


def parse_markers(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                result[key.strip()] = value.strip()
    return result


def freeze(path: Path, bundle: str) -> dict[str, Any]:
    digest = sha256(path)
    destination = ARTIFACTS / bundle / digest / path.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) != digest:
        raise RuntimeError(f"content-address collision: {destination}")
    if not destination.exists():
        shutil.copy2(path, destination)
    if sha256(destination) != digest:
        raise RuntimeError(f"frozen artifact hash mismatch: {destination}")
    destination.chmod(stat.S_IREAD)
    return {"path": rel(destination), "sha256": digest,
            "bytes": destination.stat().st_size, "read_only": True}


def source_bundle(role: str, cfg: dict[str, str]) -> tuple[str, dict[str, str]]:
    sources = [*RTL, rel(Path(__file__).resolve()), rel(TCL),
               "board_profiles/ax7020_common/p10_ps7_config.tcl",
               cfg["profile_path"], cfg["xdc"],
               "config/register_map/ir_axi_regs.yaml",
               "config/hardware/p10_1_ax7020_pl_activity_leds.yaml",
               "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md"]
    hashes = {item: sha256(ROOT / item) for item in sources}
    payload = json.dumps({"campaign": CAMPAIGN, "role": role,
                          "part": "xc7z020clg400-2",
                          "inputs": hashes}, sort_keys=True,
                         separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest(), hashes


def audit_xsa(path: Path, role_value: str) -> dict[str, Any]:
    errors: list[str] = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            required = {"p10_ps_system.hwh", "ps7_init.c", "ps7_init.tcl",
                        "sysdef.xml", "xsa.json"}
            missing = sorted(required - names)
            if missing:
                errors.append("missing XSA members: " + ", ".join(missing))
            hwh = archive.read("p10_ps_system.hwh").decode("utf-8", errors="replace") \
                if "p10_ps_system.hwh" in names else ""
    except (OSError, zipfile.BadZipFile) as exc:
        return {"status": "FAIL", "errors": [str(exc)]}
    checks = {
        # Vivado HWH serializes the canonical part as three SYSTEMINFO
        # attributes rather than as the project-style xc7z020clg400-2 token.
        "part_device": 'DEVICE="7z020"' in hwh,
        "part_package": 'PACKAGE="clg400"' in hwh,
        "part_speedgrade": 'SPEEDGRADE="-2"' in hwh,
        "endpoint_role": f'<PARAMETER NAME="ENDPOINT_ROLE" VALUE="{role_value}"/>' in hwh,
        "ddr_part": '<PARAMETER NAME="PCW_UIPARAM_DDR_PARTNO" VALUE="MT41J256M16 RE-125"/>' in hwh,
        "ddr_width": '<PARAMETER NAME="PCW_UIPARAM_DDR_BUS_WIDTH" VALUE="32 Bit"/>' in hwh,
        "ethernet_disabled": '<PARAMETER NAME="PCW_EN_ENET0" VALUE="0"/>' in hwh,
        "dma_base": 'VALUE="0x40400000"' in hwh,
        "peripheral_base": 'VALUE="0x43C00000"' in hwh,
        "activity_led_port": "pl_activity_led_n_o" in hwh.lower(),
    }
    errors.extend(f"XSA contract check failed: {key}" for key, ok in checks.items() if not ok)
    return {"status": "PASS" if not errors else "FAIL", "checks": checks,
            "errors": errors}


def run_role(role: str, cfg: dict[str, str], reuse: bool) -> dict[str, Any]:
    out = OUT / role
    out.mkdir(parents=True, exist_ok=True)
    log = out / "vivado_stdout_stderr.txt"
    command = [str(VIVADO), "-mode", "batch", "-nolog", "-nojournal",
               "-source", str(TCL), "-tclargs", str(ROOT), role, str(out)]
    returncode = 0
    if not reuse:
        proc = subprocess.run(
            command, cwd=ROOT, text=True, capture_output=True, timeout=1800,
            env={**os.environ, "NO_HARDWARE": "1",
                 "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
        )
        returncode = proc.returncode
        log.write_text(
            "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
            f"RETURN_CODE={returncode}\nSTDOUT_BEGIN\n{proc.stdout}\nSTDOUT_END\n" +
            f"STDERR_BEGIN\n{proc.stderr}\nSTDERR_END\n",
            encoding="utf-8", errors="replace", newline="\n",
        )
    marker_path = out / "p10_functional_build_markers.txt"
    bit = out / f"p10_ax7020_{role}_functional.bit"
    xsa = out / f"p10_ax7020_{role}_functional.xsa"
    reports = [out / name for name in (
        "post_route_drc.rpt", "post_route_methodology.rpt",
        "post_route_timing_summary.rpt", "post_route_utilization.rpt",
        "post_route_cdc.rpt", "post_route_clock_interaction.rpt")]
    errors: list[str] = []
    if returncode != 0:
        errors.append(f"Vivado return code {returncode}")
    for path in [marker_path, bit, xsa, *reports]:
        if not path.is_file():
            errors.append(f"missing {rel(path)}")
    markers = parse_markers(marker_path)
    expected = {
        "P10_FUNCTIONAL_BUILD": "PASS", "P10_ENDPOINT_ROLE": role,
        "P10_ENDPOINT_ROLE_VALUE": cfg["role_value"],
        "P10_PROFILE_ID": cfg["profile"], "P10_PART": "xc7z020clg400-2",
        "P10_ETHERNET_ENABLED": "false", "P10_WNS_NS": None,
        "P10_WHS_NS": None, "P10_TNS_NS": "0.0",
        "P10_DRC_CRITICAL_COUNT": "0", "P10_DRC_ERROR_COUNT": "0",
        "P10_REQP_1839_COUNT": "0", "P10_METHODOLOGY_CRITICAL_COUNT": "0",
        "P10_CDC_CRITICAL_COUNT": "0", "P10_HARDWARE_ADMISSION": "false",
        "P10_BLOCKING_CONDITION": "P10-SAFETY-POWERUP-001",
        "P10_PL_ACTIVITY_LED_ACTIVE_LOW": "true",
        "P10_PL_ACTIVITY_LED_HOLD_MS": "200",
        "P10_PL_ACTIVITY_LED_SAFETY_ROLE": "MONITOR_ONLY",
    }
    for key, value in expected.items():
        if key not in markers or (value is not None and markers[key] != value):
            errors.append(f"marker {key}={markers.get(key)!r}, expected {value!r}")
    for key in ("P10_WNS_NS", "P10_WHS_NS"):
        try:
            if float(markers[key]) < 0.0:
                errors.append(f"negative timing marker {key}")
        except (KeyError, ValueError):
            errors.append(f"invalid timing marker {key}")
    xsa_audit = audit_xsa(xsa, cfg["role_value"]) if xsa.is_file() else {
        "status": "FAIL", "errors": ["XSA absent"]}
    if xsa_audit["status"] != "PASS":
        errors.extend(xsa_audit["errors"])
    bundle, input_hashes = source_bundle(role, cfg)
    frozen = {"bitstream": freeze(bit, bundle), "xsa": freeze(xsa, bundle)} \
        if not errors else {}
    return {
        "role": role, "profile": cfg["profile"],
        "status": "PASS" if not errors else "FAIL",
        "source_bundle_sha256": bundle, "source_sha256": input_hashes,
        "markers": markers, "xsa_audit": xsa_audit, "artifacts": frozen,
        "reports": [{"path": rel(path), "sha256": sha256(path),
                     "bytes": path.stat().st_size} for path in reports if path.is_file()],
        "log": rel(log) if log.is_file() else None,
        "log_sha256": sha256(log) if log.is_file() else None,
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-existing", action="store_true",
                        help="audit/freeze existing outputs without rerunning Vivado")
    parser.add_argument(
        "--campaign",
        choices=("p10", "p10_1_led"),
        default="p10",
        help="Use a separate output/evidence namespace for a follow-up campaign.",
    )
    args = parser.parse_args()
    configure_campaign(args.campaign)
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_FUNCTIONAL_BUILD_REFUSED: offline environment required", file=sys.stderr)
        return 2
    goal = ROOT / "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md"
    if not goal.is_file() or sha256(goal) != GOAL_HASH:
        print("P10_FUNCTIONAL_BUILD_REFUSED: goal hash mismatch", file=sys.stderr)
        return 2
    if not args.reuse_existing and not VIVADO.is_file():
        print(f"Vivado not found: {VIVADO}", file=sys.stderr)
        return 2
    source_paths = sorted({
        *RTL, rel(Path(__file__).resolve()), rel(TCL),
        "board_profiles/ax7020_common/p10_ps7_config.tcl",
        *(cfg["profile_path"] for cfg in ROLES.values()),
        *(cfg["xdc"] for cfg in ROLES.values()),
        "config/register_map/ir_axi_regs.yaml",
        "config/hardware/p10_1_ax7020_pl_activity_leds.yaml",
        "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md",
    })
    source_worktree_dirty = tracked_source_dirty(source_paths)
    results = [run_role(role, cfg, args.reuse_existing)
               for role, cfg in ROLES.items()]
    status = "PASS" if all(item["status"] == "PASS" for item in results) else "FAIL"
    summary = {
        "schema_version": 1, "test_id": TEST_ID, "campaign": CAMPAIGN,
        "status": status, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": source_worktree_dirty,
        "part": "xc7z020clg400-2", "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False, "network_used": False,
        "hardware_admission": False, "blocking_condition": "P10-SAFETY-POWERUP-001",
        "roles": results,
    }
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8", newline="\n")
    lines = [f"# {SUMMARY_TITLE}", "", f"- Status: `{status}`",
             "- Hardware actions executed: `false`", "- Ethernet enabled: `false`",
             "- Hardware admission remains blocked by `P10-SAFETY-POWERUP-001`.", "",
             "| Role | Build | WNS (ns) | WHS (ns) | TNS (ns) | Bitstream SHA256 | XSA SHA256 |",
             "|---|---|---:|---:|---:|---|---|"]
    for item in results:
        markers = item["markers"]
        artifacts = item.get("artifacts", {})
        lines.append(
            f"| {item['role']} | {item['status']} | {markers.get('P10_WNS_NS', 'NONE')} | "
            f"{markers.get('P10_WHS_NS', 'NONE')} | {markers.get('P10_TNS_NS', 'NONE')} | "
            f"`{artifacts.get('bitstream', {}).get('sha256', 'NONE')}` | "
            f"`{artifacts.get('xsa', {}).get('sha256', 'NONE')}` |")
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_AX7020_DUAL_FUNCTIONAL_BUILD={status}")
    print(f"P10_FUNCTIONAL_BUILD_SUMMARY={rel(SUMMARY_JSON)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
