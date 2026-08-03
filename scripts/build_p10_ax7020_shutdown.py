#!/usr/bin/env python3
"""Build and freeze the two role-addressed P10 AX7020 shutdown images.

This is an offline-only build. It neither starts nor connects hw_server and
contains no JTAG, programming, ELF, UART, Ethernet, or TFDU runtime action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
TCL = ROOT / "scripts/vivado/build_p10_ax7020_shutdown.tcl"
TOP = ROOT / "rtl/p10_ax7020_shutdown_top.v"
OUT_ROOT = ROOT / "evidence/generated/vivado/p10_ax7020_shutdown"
ARTIFACT_ROOT = ROOT / "artifacts/p10"
SUMMARY_JSON = ROOT / "evidence/generated/p10_ax7020_shutdown_build_summary.json"
SUMMARY_MD = ROOT / "evidence/generated/p10_ax7020_shutdown_build_summary.md"
CAMPAIGN = "p10"
TEST_ID = "P10-AX7020-DUAL-SHUTDOWN-BUILD"
SUMMARY_TITLE = "P10 AX7020 dual shutdown build"
EXPECTED_GOALS = {
    "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md":
        "b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603",
    "goals/P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET_GOAL.md":
        "5a81eeea8cf5bb0ff9d41c237a2af097f58cf71d1d208825dfb6144b5d6e23a3",
}
P10_1R_GOAL = "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md"
P10_1R_GOAL_SHA256 = (
    "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
)
PROFILES = {
    "fixed": {
        "profile": "P10_AX7020_FIXED_2LANE",
        "xdc": ROOT / "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
        "bit": "p10_ax7020_fixed_shutdown.bit",
    },
    "rotating": {
        "profile": "P10_AX7020_ROTATING_2LANE",
        "xdc": ROOT / "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
        "bit": "p10_ax7020_rotating_shutdown.bit",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def configure_campaign(campaign: str) -> None:
    global OUT_ROOT, ARTIFACT_ROOT, SUMMARY_JSON, SUMMARY_MD
    global CAMPAIGN, TEST_ID, SUMMARY_TITLE
    CAMPAIGN = campaign
    if campaign == "p10":
        return
    if campaign != "p10_1r":
        raise ValueError(f"unsupported campaign: {campaign}")
    OUT_ROOT = ROOT / "evidence/generated/vivado/p10_1r_shutdown"
    ARTIFACT_ROOT = ROOT / "artifacts/p10_1r"
    SUMMARY_JSON = ROOT / "evidence/generated/p10_1r_shutdown_build_summary.json"
    SUMMARY_MD = ROOT / "evidence/generated/p10_1r_shutdown_build_summary.md"
    TEST_ID = "P10_1R-AX7020-DUAL-SHUTDOWN-BUILD"
    SUMMARY_TITLE = "P10.1R AX7020 dual shutdown build"


def active_goals() -> dict[str, str]:
    goals = dict(EXPECTED_GOALS)
    if CAMPAIGN == "p10_1r":
        goals[P10_1R_GOAL] = P10_1R_GOAL_SHA256
    return goals


def tracked_source_dirty(paths: list[Path]) -> bool:
    return bool(subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no", "--",
         *[relative(path) for path in paths]], cwd=ROOT, text=True))


def parse_markers(path: Path) -> dict[str, str]:
    markers: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            markers[key.strip()] = value.strip()
    return markers


def bundle_hash(role: str, profile: dict[str, object]) -> tuple[str, dict[str, str]]:
    paths = [Path(__file__).resolve(), TOP, TCL, Path(profile["xdc"]),
             *[ROOT / item for item in active_goals()]]
    hashes = {relative(path): sha256(path) for path in paths}
    payload = json.dumps(
        {"campaign": CAMPAIGN, "role": role,
         "part": "xc7z020clg400-2", "inputs": hashes},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest(), hashes


def freeze(source: Path, source_bundle: str) -> dict[str, object]:
    digest = sha256(source)
    namespace = (
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        if CAMPAIGN == "p10_1r"
        else source_bundle
    )
    destination = ARTIFACT_ROOT / namespace / digest / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) != digest:
        raise RuntimeError(f"content-address collision: {destination}")
    if not destination.exists():
        shutil.copy2(source, destination)
    if sha256(destination) != digest:
        raise RuntimeError(f"frozen artifact verification failed: {destination}")
    destination.chmod(stat.S_IREAD)
    return {
        "path": relative(destination),
        "sha256": digest,
        "bytes": destination.stat().st_size,
        "read_only": True,
    }


def run_role(role: str, profile: dict[str, object]) -> dict[str, object]:
    out_dir = OUT_ROOT / role
    out_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(VIVADO), "-mode", "batch", "-nolog", "-nojournal",
        "-source", str(TCL), "-tclargs", str(ROOT), role, str(out_dir),
    ]
    completed = subprocess.run(
        command, cwd=ROOT, text=True, capture_output=True, timeout=1800,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    log_path = out_dir / "vivado_stdout_stderr.txt"
    log_path.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n" +
        f"RETURN_CODE={completed.returncode}\nSTDOUT_BEGIN\n{completed.stdout}\n" +
        f"STDOUT_END\nSTDERR_BEGIN\n{completed.stderr}\nSTDERR_END\n",
        encoding="utf-8", errors="replace", newline="\n",
    )
    marker_path = out_dir / "p10_shutdown_build_markers.txt"
    bit_path = out_dir / str(profile["bit"])
    required = [
        marker_path, bit_path, out_dir / "post_route_drc.rpt",
        out_dir / "post_route_timing_summary.rpt",
        out_dir / "post_route_utilization.rpt",
        out_dir / "post_route_methodology.rpt", out_dir / "post_route_cdc.rpt",
    ]
    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"Vivado return code {completed.returncode}")
    errors.extend(f"missing {relative(path)}" for path in required if not path.is_file())
    markers = parse_markers(marker_path) if marker_path.is_file() else {}
    expected_markers = {
        "P10_SHUTDOWN_BUILD": "PASS",
        "P10_ENDPOINT_ROLE": role,
        "P10_PROFILE_ID": str(profile["profile"]),
        "P10_PART": "xc7z020clg400-2",
        "P10_TOP": "p10_ax7020_shutdown_top",
        "P10_SHUTDOWN_MODE_INTENT": "0x3",
        "P10_SHUTDOWN_SD_INTENT": "0x3",
        "P10_SHUTDOWN_TXD_INTENT": "0x0",
        "P10_SHUTDOWN_LED_N_INTENT": "0xF",
        "P10_SHUTDOWN_LED_ACTIVE_LOW": "true",
        "P10_SHUTDOWN_LED_PORT_COUNT": "4",
        "P10_DRC_CRITICAL_COUNT": "0",
        "P10_DRC_ERROR_COUNT": "0",
        "P10_REQP_1839_COUNT": "0",
        "P10_METHODOLOGY_CRITICAL_COUNT": "0",
        "P10_CDC_CRITICAL_COUNT": "0",
    }
    for key, expected in expected_markers.items():
        if markers.get(key) != expected:
            errors.append(f"marker {key}={markers.get(key)!r}, expected {expected!r}")
    source_bundle, input_hashes = bundle_hash(role, profile)
    artifact = freeze(bit_path, source_bundle) if not errors else None
    return {
        "status": "PASS" if not errors else "FAIL",
        "role": role,
        "profile": profile["profile"],
        "part": "xc7z020clg400-2",
        "source_bundle_sha256": source_bundle,
        "input_sha256": input_hashes,
        "xdc_sha256": sha256(Path(profile["xdc"])),
        "markers": markers,
        "artifact": artifact,
        "vivado_log": relative(log_path),
        "vivado_log_sha256": sha256(log_path),
        "reports": [
            {"path": relative(path), "sha256": sha256(path), "bytes": path.stat().st_size}
            for path in required if path.is_file() and path != bit_path
        ],
        "errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--campaign", choices=("p10", "p10_1r"), default="p10",
        help="Use a separate Goal-bound evidence and artifact namespace.",
    )
    args = parser.parse_args()
    configure_campaign(args.campaign)
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_SHUTDOWN_BUILD_REFUSED: offline environment required", file=sys.stderr)
        return 2
    if not VIVADO.is_file():
        print(f"Vivado not found: {VIVADO}", file=sys.stderr)
        return 2
    for item, expected in active_goals().items():
        path = ROOT / item
        if not path.is_file() or sha256(path) != expected:
            print(f"P10_SHUTDOWN_BUILD_REFUSED: goal hash mismatch: {item}", file=sys.stderr)
            return 2
    source_worktree_dirty = tracked_source_dirty([
        Path(__file__).resolve(), TOP, TCL,
        *(Path(profile["xdc"]) for profile in PROFILES.values()),
        *(ROOT / item for item in active_goals()),
    ])
    results = [run_role(role, profile) for role, profile in PROFILES.items()]
    status = "PASS" if all(result["status"] == "PASS" for result in results) else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": TEST_ID,
        "campaign": CAMPAIGN,
        "status": status,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": source_worktree_dirty,
        "no_hardware": True,
        "current_run_hardware_authorization_for_this_offline_build": False,
        "hardware_actions_executed": False,
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "configured_shutdown_intent": {
            "Mode": "HIGH",
            "SD": "HIGH",
            "Txd": "LOW",
            "PL_LED_N": "HIGH_ALL_OFF",
        },
        "unconfigured_or_partial_power_guarantee": False,
        "roles": results,
    }
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
    lines = [
        f"# {SUMMARY_TITLE}",
        "",
        f"- Status: `{status}`",
        "- Hardware actions executed: `false`",
        "- Part: `xc7z020clg400-2`",
        "- Configured intent: `Mode=HIGH`, `SD=HIGH`, `Txd=LOW` on both lanes and `PL_LED_N=0xF` (all four active-low LEDs off).",
        "- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).",
        "- Boundary: these bitstreams establish only post-configuration PL levels; they do not prove FPGA-unconfigured or partial-power safety.",
        "",
        "| Role | Result | Source bundle SHA256 | Bitstream SHA256 | Artifact |",
        "|---|---|---|---|---|",
    ]
    for result in results:
        artifact = result.get("artifact") or {}
        lines.append(
            f"| {result['role']} | {result['status']} | `{result['source_bundle_sha256']}` | "
            f"`{artifact.get('sha256', 'NONE')}` | `{artifact.get('path', 'NONE')}` |"
        )
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_AX7020_DUAL_SHUTDOWN_BUILD={status}")
    print(f"P10_AX7020_DUAL_SHUTDOWN_SUMMARY={relative(SUMMARY_JSON)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
