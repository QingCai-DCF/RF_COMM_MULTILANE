#!/usr/bin/env python3
"""Bounded read-only JTAG serial inventory for the two P10 AX7020 boards.

require-user-hw-authorization --allow-hardware

This runner connects only to an already-running local hw_server and invokes
``jtag targets -target-properties`` through XSCT.  It never configures PL,
selects a debug target, resets a device, accesses memory, launches an ELF,
writes UART, or drives a TFDU signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
BRANCH = "p10/ax7020-dual-node-2lane"
GOAL = ROOT / "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md"
GOAL_SHA256 = "b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603"
XSCT = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsct.bat")
TCL = ROOT / "scripts/hw/p10_jtag_identity_readonly.tcl"
XSDB_URL = "tcp:localhost:3121"
AUTH_MARKER = "P10_FASTTRACK_READ_ONLY_IDENTITY"
RUN_ID_RE = re.compile(r"^p10_jtag_identity_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}$")

BOUND_INPUTS = (
    "PROJECT_CONSTRAINTS.txt",
    "AGENTS.md",
    "config/register_map/ir_axi_regs.yaml",
    "config/hardware/p10_active_wiring.yaml",
    "config/hardware/p10_board_inventory.yaml",
    "config/hardware/p10_tfdu_module_inventory.yaml",
    "board_profiles/ax7020_common/board_identity.yaml",
    "board_profiles/ax7020_fixed_2lane/profile.yaml",
    "board_profiles/ax7020_fixed_2lane/pinmap.csv",
    "board_profiles/ax7020_fixed_2lane/ax7020_fixed_2lane.generated.xdc",
    "board_profiles/ax7020_rotating_2lane/profile.yaml",
    "board_profiles/ax7020_rotating_2lane/pinmap.csv",
    "board_profiles/ax7020_rotating_2lane/ax7020_rotating_2lane.generated.xdc",
    "docs/hardware/P10_USER_HARDWARE_CLARIFICATIONS.md",
    "evidence/generated/p10_offline_artifact_manifest.json",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def is_ancestor(reference: str, head: str) -> bool:
    return git("merge-base", "--is-ancestor", reference, head, check=False).returncode == 0


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.5):
            return True
    except OSError:
        return False


def parse_markers(path: Path) -> dict[str, str]:
    markers: dict[str, str] = {}
    if not path.is_file():
        return markers
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"P10_JTAG_[A-Z0-9_]+", key):
            markers[key] = value.strip()
    return markers


def marker_inventory(markers: dict[str, str]) -> tuple[list[str], list[dict[str, str]]]:
    serial_by_index: list[tuple[int, str]] = []
    for key, value in markers.items():
        match = re.fullmatch(r"P10_JTAG_CABLE_([0-9]+)_SERIAL", key)
        if match:
            serial_by_index.append((int(match.group(1)), value))
    serials = [value for _, value in sorted(serial_by_index)]

    devices: list[dict[str, str]] = []
    count_text = markers.get("P10_JTAG_DEVICE_COUNT", "0") or "0"
    count = int(count_text) if count_text.isdigit() else 0
    for index in range(1, count + 1):
        prefix = f"P10_JTAG_DEVICE_{index}_"
        devices.append({
            "cable_serial": markers.get(prefix + "CABLE_SERIAL", ""),
            "name": markers.get(prefix + "NAME", ""),
            "idcode": markers.get(prefix + "IDCODE", ""),
            "node_id": markers.get(prefix + "NODE_ID", ""),
        })
    return serials, devices


def terminate_exact_child_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        process.kill()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()


def frozen_artifacts(errors: list[str]) -> list[dict[str, Any]]:
    manifest_path = ROOT / "evidence/generated/p10_offline_artifact_manifest.json"
    if not manifest_path.is_file():
        errors.append("offline artifact manifest is missing")
        return []
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records: list[dict[str, Any]] = []
    for item in manifest.get("artifacts", []):
        artifact = ROOT / str(item.get("path", "__missing__"))
        expected = item.get("sha256")
        actual = sha256(artifact) if artifact.is_file() else None
        if actual != expected:
            errors.append(f"artifact hash mismatch: {item.get('path')}")
        records.append({
            "role": item.get("role"),
            "kind": item.get("kind"),
            "path": item.get("path"),
            "sha256": expected,
            "verified": actual == expected,
            "execution_used": False,
        })
    if len(records) != 10:
        errors.append(f"expected 10 frozen artifacts, found {len(records)}")
    return records


def input_records(errors: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for name in BOUND_INPUTS:
        path = ROOT / name
        if not path.is_file():
            errors.append(f"bound input missing: {name}")
            continue
        records.append({"path": name, "bytes": path.stat().st_size, "sha256": sha256(path)})
    return records


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-hardware", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--max-runtime-seconds", type=int, default=60)
    args = parser.parse_args()

    errors: list[str] = []
    if not args.allow_hardware:
        errors.append("--allow-hardware is required")
    if os.environ.get("NO_HARDWARE") != "0":
        errors.append("NO_HARDWARE=0 is required")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "").lower() != "true":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION=true is required")
    if os.environ.get("P10_JTAG_IDENTITY_AUTHORIZATION") != AUTH_MARKER:
        errors.append(f"P10_JTAG_IDENTITY_AUTHORIZATION={AUTH_MARKER} is required")
    if not 1 <= args.max_runtime_seconds <= 60:
        errors.append("max runtime must be within 1..60 seconds")
    if not GOAL.is_file() or sha256(GOAL) != GOAL_SHA256:
        errors.append("fast-track goal missing or SHA256 mismatch")
    if not XSCT.is_file():
        errors.append(f"XSCT is missing: {XSCT}")
    if not TCL.is_file():
        errors.append(f"read-only identity TCL is missing: {TCL}")

    branch = git("branch", "--show-current").stdout.strip()
    head = git("rev-parse", "HEAD").stdout.strip()
    dirty = git("status", "--porcelain").stdout.splitlines()
    if branch != BRANCH:
        errors.append(f"branch mismatch: {branch}")
    if dirty:
        errors.append("worktree must be clean before a hardware identity run")
    for reference in ("main", "p8e-pass", "p9-z7010-2lane-pass"):
        if not is_ancestor(reference, head):
            errors.append(f"missing required ancestor: {reference}")

    inputs = input_records(errors)
    artifacts = frozen_artifacts(errors)
    if not port_open("127.0.0.1", 3121):
        errors.append("local hw_server tcp/3121 is not listening; this runner will not start one")

    if args.run_id:
        run_id = args.run_id
    else:
        nonce = hashlib.sha256(f"{head}:{time.time_ns()}".encode()).hexdigest()[:8]
        run_id = datetime.now(timezone.utc).strftime("p10_jtag_identity_%Y%m%dT%H%M%SZ_") + nonce
    if not RUN_ID_RE.fullmatch(run_id):
        errors.append(f"invalid run id: {run_id}")

    if errors:
        for error in errors:
            print(f"P10_JTAG_IDENTITY_REFUSED: {error}", file=sys.stderr)
        print("P10_JTAG_IDENTITY_HARDWARE_ACTIONS_EXECUTED=0")
        return 2

    run_root = ROOT / "evidence/hardware/p10" / run_id / "identity"
    run_root.mkdir(parents=True, exist_ok=False)
    result_path = run_root / "jtag_identity_result.txt"
    stdout_path = run_root / "xsct.stdout.log"
    stderr_path = run_root / "xsct.stderr.log"
    input_manifest_path = run_root / "input_manifest.json"
    summary_path = run_root / "summary.json"

    input_manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "scope": "P10_DUAL_AX7020_READ_ONLY_JTAG_SERIAL_INVENTORY",
        "source_commit": head,
        "branch": branch,
        "authorization": {
            "goal": rel(GOAL),
            "goal_sha256": GOAL_SHA256,
            "environment_marker": AUTH_MARKER,
            "current_run_hardware_authorization": True,
            "max_runtime_seconds": args.max_runtime_seconds,
        },
        "board_identity_method": "JTAG_CABLE_SERIAL",
        "bound_inputs": inputs,
        "frozen_artifacts": artifacts,
        "artifact_execution_used": False,
        "programming_allowed": False,
        "reset_allowed": False,
        "memory_access_allowed": False,
        "elf_execution_allowed": False,
        "uart_write_allowed": False,
        "tfdu_drive_allowed": False,
        "shutdown_required": False,
        "shutdown_reason": "No configuration, reset, memory access, ELF, UART, or TFDU drive is performed.",
        "hw_server": {"url": XSDB_URL, "reused": True, "started_by_runner": False},
    }
    write_json(input_manifest_path, input_manifest)

    command = [str(XSCT), str(TCL), XSDB_URL, str(result_path)]
    started_at = utc_now()
    started_monotonic = time.monotonic()
    process: subprocess.Popen[str] | None = None
    returncode = 127
    timed_out = False
    interrupted = False
    launch_error: str | None = None
    hardware_actions_executed = False

    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
    with stdout_path.open("w", encoding="utf-8", errors="replace") as stdout_stream, \
            stderr_path.open("w", encoding="utf-8", errors="replace") as stderr_stream:
        try:
            process = subprocess.Popen(
                command, cwd=ROOT, env=dict(os.environ), text=True,
                stdout=stdout_stream, stderr=stderr_stream, shell=False,
                creationflags=creationflags,
            )
            hardware_actions_executed = True
            returncode = process.wait(timeout=args.max_runtime_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            returncode = 124
            if process is not None:
                terminate_exact_child_tree(process)
        except KeyboardInterrupt:
            interrupted = True
            returncode = 130
            if process is not None:
                terminate_exact_child_tree(process)
        except BaseException as exc:
            launch_error = f"{type(exc).__name__}: {exc}"
            if process is not None:
                terminate_exact_child_tree(process)

    ended_at = utc_now()
    markers = parse_markers(result_path)
    serials, devices = marker_inventory(markers)
    distinct_serials = sorted(set(serials))
    topology_pass = (
        returncode == 0
        and markers.get("P10_JTAG_IDENTITY_RESULT") == "PASS"
        and markers.get("P10_JTAG_IDENTITY_READ_ONLY") == "1"
        and markers.get("P10_JTAG_MUTATING_COMMANDS_EXECUTED") == "0"
        and markers.get("P10_JTAG_DISCONNECTED") == "1"
        and len(serials) == 2
        and len(distinct_serials) == 2
        and len([item for item in devices if item["name"].lower() == "xc7z020" and item["idcode"] == "23727093"]) == 2
        and len([item for item in devices if item["name"].lower() == "arm_dap" and item["idcode"] == "4BA00477"]) == 2
    )
    if topology_pass:
        status = "PASS_ENUMERATED_UNASSIGNED"
    elif markers.get("P10_JTAG_IDENTITY_RESULT") == "INCOMPLETE" or returncode == 3:
        status = "INCOMPLETE"
    else:
        status = "FAIL"

    summary = {
        "schema_version": 1,
        "test_id": "P10-JTAG-IDENTITY-READONLY",
        "status": status,
        "run_id": run_id,
        "source_commit": head,
        "branch": branch,
        "started_at_utc": started_at,
        "ended_at_utc": ended_at,
        "duration_seconds": round(time.monotonic() - started_monotonic, 6),
        "max_runtime_seconds": args.max_runtime_seconds,
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": hardware_actions_executed,
        "jtag_connection_executed": hardware_actions_executed,
        "jtag_read_only": True,
        "programming_executed": False,
        "reset_executed": False,
        "memory_access_executed": False,
        "elf_executed": False,
        "uart_write_executed": False,
        "tfdu_drive_executed": False,
        "shutdown_required": False,
        "shutdown_fixed": "NOT_APPLICABLE_READ_ONLY_JTAG_ENUMERATION",
        "shutdown_rotating": "NOT_APPLICABLE_READ_ONLY_JTAG_ENUMERATION",
        "network_used": False,
        "local_hw_server_transport_used": True,
        "hw_server_started_by_runner": False,
        "timed_out": timed_out,
        "interrupted": interrupted,
        "launch_error": launch_error,
        "process_returncode": returncode,
        "command": command,
        "input_manifest": rel(input_manifest_path),
        "input_manifest_sha256": sha256(input_manifest_path),
        "raw_result": rel(result_path) if result_path.is_file() else None,
        "raw_result_sha256": sha256(result_path) if result_path.is_file() else None,
        "stdout": rel(stdout_path),
        "stdout_sha256": sha256(stdout_path),
        "stderr": rel(stderr_path),
        "stderr_sha256": sha256(stderr_path),
        "markers": markers,
        "observed_cable_serials": serials,
        "distinct_cable_serials": distinct_serials,
        "devices": devices,
        "role_binding_method": "JTAG_CABLE_SERIAL",
        "role_binding_status": "ENUMERATED_UNASSIGNED" if topology_pass else "NOT_READY",
        "fixed_board_serial": "PENDING_EXPLICIT_SERIAL_TO_ROLE_BINDING" if topology_pass else "NOT_AVAILABLE",
        "rotating_board_serial": "PENDING_EXPLICIT_SERIAL_TO_ROLE_BINDING" if topology_pass else "NOT_AVAILABLE",
        "target_order_used_for_role_binding": False,
        "blocking_condition_for_programming": "P10-SAFETY-POWERUP-001",
    }
    write_json(summary_path, summary)

    latest_json = ROOT / "evidence/generated/p10_jtag_identity_latest.json"
    write_json(latest_json, summary)
    latest_md = ROOT / "evidence/generated/p10_jtag_identity_latest.md"
    serial_text = ", ".join(f"`{value}`" for value in distinct_serials) or "none"
    latest_md.write_text(
        "# P10 read-only JTAG identity inventory\n\n"
        f"- Result: `{status}`\n"
        f"- Run ID: `{run_id}`\n"
        f"- Observed cable serials: {serial_text}\n"
        f"- Role binding: `{summary['role_binding_status']}`\n"
        "- Target order used for role binding: `false`\n"
        "- FPGA programming/reset/memory/ELF/UART/TFDU action: `false`\n"
        "- Shutdown: not required for this read-only enumeration.\n"
        f"- Raw evidence: `{rel(summary_path)}`\n"
        "- Programming remains blocked by `P10-SAFETY-POWERUP-001`.\n",
        encoding="utf-8",
    )

    print(f"P10_JTAG_IDENTITY_RESULT={status}")
    print(f"P10_JTAG_IDENTITY_RUN_ID={run_id}")
    print(f"P10_JTAG_IDENTITY_SERIALS={','.join(distinct_serials)}")
    print(f"P10_JTAG_IDENTITY_HARDWARE_ACTIONS_EXECUTED={1 if hardware_actions_executed else 0}")
    print("P10_JTAG_IDENTITY_PROGRAMMING_EXECUTED=0")
    return 0 if topology_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
