#!/usr/bin/env python3
"""Fail-closed full P10.3 campaign runner for the P10.3F artifact bundle.

This host-only follow-up combines the original stationary four-lane acceptance
matrix with the later first-fault archive and bounded-transfer rules.  It is
inert unless a committed, exact current-run authorization is supplied together
with both hardware environment gates and ``--execute-hardware``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_3_ax7020_4lane_hardware as base
import run_p10_3f_staircase_hardware as forensic
from p10_hardware_runtime import (
    EXPECTED_FIXED_SERIAL,
    EXPECTED_ROTATING_SERIAL,
    XSDB,
    extract_ps7_init,
    parse_mailbox,
    parse_markers,
    run_bounded,
    start_hw_server,
    terminate_tree,
)


ROOT = Path(__file__).resolve().parents[1]
SCOPE = (
    "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_"
    "WITH_FIRST_FAULT_FORENSICS"
)
GOAL = ROOT / "goals/P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_GOAL.md"
GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
ARTIFACT_FREEZE = ROOT / "evidence/generated/p10_3_fault_forensics_artifact_freeze.json"
CAMPAIGN_FREEZE = ROOT / "evidence/generated/p10_3f_full_campaign_freeze.json"
CAMPAIGN_FREEZE_MD = ROOT / "evidence/generated/p10_3f_full_campaign_freeze.md"
CAMPAIGN_FREEZE_RAW = ROOT / "evidence/generated/p10_3f_full_campaign_freeze_raw"
AUTH = ROOT / "config/p10_3f_full_current_run_hardware_authorization.json"
WIRING = ROOT / "config/hardware/p10_3_actual_wiring.yaml"
INVENTORY = ROOT / "config/hardware/tfdu_module_inventory.yaml"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
FORENSIC_TCL = ROOT / "scripts/hw/p10_3f_fault_forensics.tcl"
TCL_COMPLETE_CHECK = ROOT / "scripts/hw/check_tcl_complete.tcl"
TCLSH = Path(
    r"D:\Xilinx\Vivado\2023.1\tps\win64\git-2.16.2\mingw64\bin\tclsh.exe"
)
HW_ROOT = ROOT / "evidence/hardware/p10_3f_full"
GENERATED_FINAL = ROOT / "evidence/generated/p10_3f_full_hardware_final_summary.json"
EXPECTED_BUILD = {"fixed": 0x50334646, "rotating": 0x50334652}
MAX_COMMAND_BYTES = 262_144
MAX_FUNCTIONAL_DIAGNOSTIC_BYTES = 16 << 20
RUN_RE = re.compile(r"^p10_3f_full_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}$")

BASE_STAGES = (
    "preflight",
    "module_intake",
    "raw_8x8",
    "per_lane_phy",
    "four_lane_raw",
    "mask_matrix",
    "degrade",
    "arq_sack",
    "dma",
)
STAIRCASE_STAGES = (
    "staircase_1k",
    "staircase_4k",
    "staircase_16k",
    "staircase_64k",
    "staircase_256k",
)
STAGES = (
    "preflight",
    "module_intake",
    "fault_capture",
    "raw_8x8",
    "per_lane_phy",
    "two_lane_regression",
    "four_lane_raw",
    "mask_matrix",
    "degrade",
    "arq_sack",
    "dma",
    *STAIRCASE_STAGES,
    "streaming_64m",
    "stream_dma_reset_fault",
    "stream_dma_reset_recovery_64m",
    "stream_service_reset_fault",
    "stream_service_reset_recovery_64m",
    "performance",
    "formal_30min",
)
EXPECTED_FAULT_STAGES = (
    "fault_capture",
    "stream_dma_reset_fault",
    "stream_service_reset_fault",
)
STREAM_RECOVERY_STAGES = (
    "stream_dma_reset_recovery_64m",
    "stream_service_reset_recovery_64m",
)
BOUNDED_LONG_STAGES = {
    "two_lane_regression",
    "streaming_64m",
    *STREAM_RECOVERY_STAGES,
    "performance",
    "formal_30min",
    *STAIRCASE_STAGES,
}
TCL_STAGE = {
    "preflight": "P10_3F-PREFLIGHT",
    "module_intake": "P10_3F-MODULE_INTAKE",
    "fault_capture": "P10_3F-FAULT_CAPTURE",
    "raw_8x8": "P10_3F-RAW_8X8",
    "per_lane_phy": "P10_3F-PER_LANE_PHY",
    "two_lane_regression": "P10_3F-TWO_LANE_REGRESSION",
    "four_lane_raw": "P10_3F-FOUR_LANE_RAW",
    "mask_matrix": "P10_3F-MASK_MATRIX",
    "degrade": "P10_3F-DEGRADE",
    "arq_sack": "P10_3F-ARQ_SACK",
    "dma": "P10_3F-DMA",
    **{stage: "P10_3F-STAIRCASE" for stage in STAIRCASE_STAGES},
    "streaming_64m": "P10_3F-STREAMING_64M",
    "stream_dma_reset_fault": "P10_3F-STREAMING_FAULT",
    "stream_dma_reset_recovery_64m": "P10_3F-STREAMING_64M",
    "stream_service_reset_fault": "P10_3F-STREAMING_FAULT",
    "stream_service_reset_recovery_64m": "P10_3F-STREAMING_64M",
    "performance": "P10_3F-PERFORMANCE",
    "formal_30min": "P10_3F-FORMAL",
}
STAGE_TIMEOUT = {
    **{stage: base.STAGE_TIMEOUT[stage] for stage in BASE_STAGES},
    "fault_capture": 900,
    "two_lane_regression": 3600,
    **{stage: 900 for stage in STAIRCASE_STAGES},
    "streaming_64m": 14_400,
    "stream_dma_reset_fault": 900,
    "stream_dma_reset_recovery_64m": 3600,
    "stream_service_reset_fault": 900,
    "stream_service_reset_recovery_64m": 3600,
    "performance": 900,
    "formal_30min": 2100,
}
MODULE_BINDING = {
    "F0": "A0019",
    "F1": "B0012",
    "F2": "B0001",
    "F3": "B0020",
    "R0": "A0010",
    "R1": "A0017",
    "R2": "B0023",
    "R3": "B0025",
}
SHUTDOWN_POLICY = {
    "shutdown_before_every_stage": True,
    "archive_before_independent_shutdown": True,
    "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
    "verify_both_shutdown_markers": True,
    "clear_frozen_capture_before_shutdown_program": False,
}
HOST_INPUTS = (
    GOAL,
    ROOT / "AGENTS.md",
    ROOT / "PROJECT_CONSTRAINTS.txt",
    ROOT / "config/project_state.json",
    ROOT / "config/project_requirements.yaml",
    ROOT / "config/register_map/ir_axi_regs.yaml",
    ROOT / "config/safety/p10_3_fault_forensics.yaml",
    ROOT / "config/performance/p10_3f_staircase.yaml",
    WIRING,
    INVENTORY,
    ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
    ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
    ROOT / "scripts/archive_p10_fault_forensics.py",
    ROOT / "scripts/run_p10_3_ax7020_4lane_hardware.py",
    ROOT / "scripts/run_p10_3f_staircase_hardware.py",
    Path(__file__).resolve(),
    ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl",
    ROOT / "scripts/hw/p10_3f_fault_forensics.tcl",
    ROOT / "scripts/hw/p10_program_dual_shutdown.tcl",
    TCL_COMPLETE_CHECK,
    ROOT / "scripts/p10_hardware_runtime.py",
    ROOT / "tests/test_p10_3f_full_hardware.py",
)
OFFLINE_GATE_COMMANDS = {
    "tcl_syntax_complete": [
        str(TCLSH),
        "scripts/hw/check_tcl_complete.tcl",
        "scripts/hw/p10_dual_xsdb_stage.tcl",
        "scripts/hw/p10_3f_fault_forensics.tcl",
        "scripts/hw/p10_program_dual_shutdown.tcl",
    ],
    "full_runner_regression": [
        sys.executable,
        "-m",
        "unittest",
        "tests.test_p10_3f_full_hardware",
        "tests.test_p10_3f_fault_forensics",
        "tests.test_p10_3_hardware_acceptance",
    ],
    "p10_2_verify_existing": [sys.executable, "scripts/verify_p10_2_existing.py"],
    "p10_1r_verify_existing": [sys.executable, "scripts/verify_p10_1r_existing.py"],
    "p10_verify_existing": [sys.executable, "scripts/verify_p10_frozen_existing.py"],
    "p8c_safety_verify_existing": [sys.executable, "scripts/verify_p8c_existing.py"],
    "state_requirements_consistency": [
        sys.executable,
        "scripts/check_p8a_consistency.py",
        "--check",
    ],
    "requirement_traceability": [
        sys.executable,
        "scripts/generate_requirement_traceability.py",
        "--check",
    ],
    "register_map_verify": [
        sys.executable,
        "scripts/generate_register_headers.py",
        "--verify",
    ],
    "no_hardware_static_scan": [sys.executable, "scripts/check_no_hardware_calls.py"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def git_is_ancestor(ancestor: str, descendant: str = "HEAD") -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0


def file_matches_head(path: Path) -> bool:
    try:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{rel(path)}"], cwd=ROOT
        )
    except subprocess.CalledProcessError:
        return False
    return committed == path.read_bytes()


def dirty_paths() -> set[str]:
    tracked = subprocess.check_output(
        ["git", "diff", "--name-only", "HEAD"], cwd=ROOT, text=True
    ).splitlines()
    untracked = subprocess.check_output(
        ["git", "ls-files", "--others", "--exclude-standard"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    return {item.replace("\\", "/") for item in (*tracked, *untracked) if item}


def run_offline_gate(name: str, command: list[str]) -> dict[str, Any]:
    """Run one bounded no-hardware readiness gate and hash its complete log."""
    CAMPAIGN_FREEZE_RAW.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "NO_HARDWARE": "1",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
    }
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=900,
            check=False,
        )
        output = result.stdout
        returncode = result.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        output = f"EXCEPTION={exc!r}\n"
        returncode = -1
    log = CAMPAIGN_FREEZE_RAW / f"{name}.log"
    write_text(log, output)
    return {
        "status": "PASS" if returncode == 0 else "FAIL",
        "command": command,
        "returncode": returncode,
        "log": metadata(log),
    }


def artifact_key(item: dict[str, Any]) -> str:
    return f"{item['role']}:{item['kind']}"


class ObjectIds:
    def __init__(self, first: int = 0x60000000) -> None:
        self.next = first

    def allocate(self, total_bytes: int = MAX_COMMAND_BYTES) -> int:
        count = (total_bytes + MAX_COMMAND_BYTES - 1) // MAX_COMMAND_BYTES
        first = self.next
        self.next += count
        if self.next > 0x7F000000:
            raise ValueError("P10.3F bounded aggregate object-ID space exhausted")
        return first


def total_line(
    label: str,
    total_bytes: int,
    direction: int,
    lane_mask: int,
    unavailable_mask: int,
    ids: ObjectIds,
) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", label):
        raise ValueError("unsafe P10.3F total label")
    if total_bytes % MAX_COMMAND_BYTES or not MAX_COMMAND_BYTES <= total_bytes <= 64 << 20:
        raise ValueError("invalid P10.3F total byte count")
    first = ids.allocate(total_bytes)
    return (
        f"P10FF_TOTAL {label} {total_bytes} {direction} {lane_mask} "
        f"{unavailable_mask} 0x{first:08X}"
    )


def build_plans() -> dict[str, str]:
    legacy = base.build_plans()
    plans = {stage: base.plan_text(legacy[stage]) for stage in BASE_STAGES}
    ids = ObjectIds()
    plans["fault_capture"] = (
        "# Controlled terminal-object fault; archive occurs in the host wrapper\n"
        "P10FF_CHECKPOINT controlled_fault_before_launch 0xF3FA0001\n"
        "P10FF_ABORT_FAULT controlled_terminal_abort 0 15 262144\n"
    )
    plans["two_lane_regression"] = "\n".join(
        (
            "# Exact aggregate 64-MiB two-lane regression with 256-KiB commands",
            total_line("regression64_f2r", 64 << 20, 0, 3, 0, ids),
            total_line("regression64_r2f", 64 << 20, 1, 3, 0, ids),
            "",
        )
    )
    for stage, (level, size, tag) in zip(
        STAIRCASE_STAGES, forensic.LEVELS, strict=True
    ):
        plans[stage] = forensic.staircase_plan(level, size, tag)

    streaming = ["# Aggregate streaming; every autonomous command is <=256 KiB"]
    for direction, side in ((0, "f2r"), (1, "r2f")):
        for index in range(1, 4):
            streaming.append(
                total_line(f"stream64_{side}_{index}", 64 << 20, direction, 15, 0, ids)
            )
    streaming.extend(
        (
            total_line("stream_lane2_unavailable", 64 << 20, 0, 15, 4, ids),
            total_line("stream_clean_after_lane2", 64 << 20, 0, 15, 0, ids),
            total_line("stream_lane3_unavailable", 64 << 20, 1, 15, 8, ids),
            total_line("stream_clean_after_lane3", 64 << 20, 1, 15, 0, ids),
        )
    )
    streaming.append("")
    plans["streaming_64m"] = "\n".join(streaming)

    dma_reset = base.stream_case(
        "stream_dma_reset_sender",
        size=MAX_COMMAND_BYTES,
        direction=0,
        lane=15,
        object_id=ids.allocate(),
        flags=base.p101.FLAG_DMA_RESET_SENDER,
    )
    plans["stream_dma_reset_fault"] = (
        "# Expected DMA-reset terminal object fault; host archives before shutdown\n"
        + dma_reset.plan_line()
        + "\n"
    )
    plans["stream_dma_reset_recovery_64m"] = (
        "# Fresh post-archive/reload 64-MiB DMA-reset recovery aggregate\n"
        + total_line("stream_clean_after_dma_reset", 64 << 20, 0, 15, 0, ids)
        + "\n"
    )
    service_id = ids.allocate()
    plans["stream_service_reset_fault"] = (
        "# Expected endpoint-service-reset terminal fault; archive before shutdown\n"
        "P101_PSRESET stream_service_reset_receiver fixed 1 15 "
        f"{MAX_COMMAND_BYTES} {service_id}\n"
    )
    plans["stream_service_reset_recovery_64m"] = (
        "# Fresh post-archive/reload 64-MiB service-reset recovery aggregate\n"
        + total_line("stream_clean_after_service_reset", 64 << 20, 1, 15, 0, ids)
        + "\n"
    )
    plans["performance"] = (
        "# 300-second application windows; internal command size is 256 KiB\n"
        "P10FF_WINDOW sustained_300s_f2r 300 0 15\n"
        "P10FF_WINDOW sustained_300s_r2f 300 1 15\n"
    )
    plans["formal_30min"] = forensic.formal_plan()
    return {stage: plans[stage] for stage in STAGES}


def validate_plans(plans: dict[str, str]) -> list[str]:
    errors: list[str] = []
    object_ranges: list[tuple[int, int, str]] = []
    if tuple(plans) != STAGES:
        errors.append("full stage order mismatch")
    for stage, text in plans.items():
        try:
            text.encode("ascii")
        except UnicodeEncodeError:
            errors.append(f"{stage}: plan is not ASCII")
        if not text.endswith("\n"):
            errors.append(f"{stage}: plan lacks terminal newline")
        for line in text.splitlines():
            fields = line.split()
            if not fields or fields[0].startswith("#"):
                continue
            if fields[0] == "CASE":
                try:
                    command = int(fields[2], 0)
                    size = int(fields[9], 0)
                except (IndexError, ValueError):
                    errors.append(f"{stage}: malformed CASE")
                    continue
                if command in (3, 13):
                    if stage not in BASE_STAGES and size > MAX_COMMAND_BYTES:
                        errors.append(f"{stage}: bounded CASE exceeds 256 KiB")
                    if stage in BASE_STAGES and size > MAX_FUNCTIONAL_DIAGNOSTIC_BYTES:
                        errors.append(f"{stage}: functional diagnostic exceeds 16 MiB")
            if fields[0] == "P10FF_TOTAL":
                if len(fields) != 7:
                    errors.append(f"{stage}: malformed bounded total")
                    continue
                try:
                    total = int(fields[2], 0)
                    first = int(fields[6], 0)
                except ValueError:
                    errors.append(f"{stage}: malformed bounded total")
                    continue
                if total % MAX_COMMAND_BYTES or not MAX_COMMAND_BYTES <= total <= 64 << 20:
                    errors.append(f"{stage}: malformed bounded total")
                else:
                    count = total // MAX_COMMAND_BYTES
                    object_ranges.append((first, first + count - 1, f"{stage}:{fields[1]}"))
            if fields[0] in {"P10FF_TOTAL", "P10FF_WINDOW", "P10FF_FORMAL"} and \
                    stage not in BOUNDED_LONG_STAGES:
                errors.append(f"{stage}: unexpected long-test primitive")
            if fields[0] == "P10FF_ABORT_FAULT" and stage != "fault_capture":
                errors.append(f"{stage}: unexpected direct fault primitive")
            if stage in EXPECTED_FAULT_STAGES and fields[0] in {
                "P10FF_TOTAL", "P10FF_WINDOW", "P10FF_FORMAL"
            }:
                errors.append(f"{stage}: expected-fault stage cannot continue streaming")
    ordered_ranges = sorted(object_ranges)
    for previous, current in zip(ordered_ranges, ordered_ranges[1:]):
        if current[0] <= previous[1]:
            errors.append(
                f"bounded object-ID overlap: {previous[2]} and {current[2]}"
            )
    for stage in EXPECTED_FAULT_STAGES:
        records = [
            line.split()[0]
            for line in plans.get(stage, "").splitlines()
            if line.split() and not line.lstrip().startswith("#") and
            line.split()[0] != "P10FF_CHECKPOINT"
        ]
        expected = ["P10FF_ABORT_FAULT"] if stage == "fault_capture" else \
            (["CASE"] if stage == "stream_dma_reset_fault" else ["P101_PSRESET"])
        if records != expected:
            errors.append(f"{stage}: terminal-fault record set/order mismatch")
    if "67108864" in plans["formal_30min"]:
        errors.append("formal plan contains a 64-MiB command")
    return errors


def validate_artifact_freeze() -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        freeze = load_json(ARTIFACT_FREEZE)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {}, [f"artifact freeze read failed: {exc}"]
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("P10.3F artifact freeze is not acceptance-eligible PASS")
    if freeze.get("goal_sha256") != GOAL_SHA256:
        errors.append("P10.3F artifact freeze Goal hash mismatch")
    if freeze.get("allowed_hardware_stages") != ["staircase", "formal"]:
        errors.append("base P10.3F artifact freeze scope changed unexpectedly")
    if freeze.get("no_hardware") is not True or \
            freeze.get("hardware_actions_executed") is not False or \
            freeze.get("old_hardware_pass_inherited") is not False:
        errors.append("base P10.3F artifact freeze provenance mismatch")
    if freeze.get("expected_build_ids") != {
        "fixed": "0x50334646",
        "rotating": "0x50334652",
    }:
        errors.append("base P10.3F build-ID binding mismatch")
    source_commit = str(freeze.get("source_commit", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit) or \
            not git_is_ancestor(source_commit):
        errors.append("P10.3F artifact source commit is not an ancestor of HEAD")
    records = [item for item in freeze.get("artifacts", []) if isinstance(item, dict)]
    by_key = {artifact_key(item): item for item in records}
    required = {
        f"{role}:{kind}"
        for role in ("fixed", "rotating")
        for kind in ("shutdown_bitstream", "functional_bitstream", "xsa", "bsp", "elf")
    }
    if set(by_key) != required:
        errors.append("P10.3F artifact set is incomplete or ambiguous")
    paths: dict[str, Path] = {}
    store = (ROOT / "artifacts/p10_3_fault_forensics").resolve()
    for key in sorted(required & set(by_key)):
        item = by_key[key]
        candidate = (ROOT / item["path"]).resolve()
        try:
            candidate.relative_to(store)
        except ValueError:
            errors.append(f"artifact escapes content store: {key}")
            continue
        if not candidate.is_file() or candidate.stat().st_size != item.get("bytes") or \
                sha256(candidate) != item.get("sha256"):
            errors.append(f"artifact hash/size mismatch: {key}")
            continue
        paths[key] = candidate
    build_evidence = freeze.get("build_evidence", {})
    if set(build_evidence) != {"functional", "shutdown", "ps_runtime", "xsim", "offline"}:
        errors.append("base P10.3F build-evidence set mismatch")
    else:
        for name, item in build_evidence.items():
            try:
                candidate = (ROOT / item["path"]).resolve()
                if not base.inside(candidate, ROOT / "evidence/generated") or \
                        not candidate.is_file() or \
                        candidate.stat().st_size != item.get("bytes") or \
                        sha256(candidate) != item.get("sha256"):
                    raise ValueError("missing/hash/size/outside generated evidence")
            except (KeyError, OSError, TypeError, ValueError) as exc:
                errors.append(f"base P10.3F {name} evidence malformed: {exc}")
    offline_gates = freeze.get("offline_gates", {})
    if not isinstance(offline_gates, dict) or not offline_gates or any(
        not isinstance(item, dict) or item.get("status") != "PASS"
        for item in offline_gates.values()
    ):
        errors.append("base P10.3F offline-gate status mismatch")
    else:
        for name, item in offline_gates.items():
            log_item = item.get("log")
            if not isinstance(log_item, dict):
                continue
            try:
                candidate = (ROOT / log_item["path"]).resolve()
                if not base.inside(candidate, ROOT / "evidence/generated") or \
                        not candidate.is_file() or \
                        candidate.stat().st_size != log_item.get("bytes") or \
                        sha256(candidate) != log_item.get("sha256"):
                    raise ValueError("log hash/size mismatch")
            except (KeyError, OSError, TypeError, ValueError) as exc:
                errors.append(f"base P10.3F offline gate {name} malformed: {exc}")
    return freeze, paths, errors


def prepare_campaign_freeze() -> dict[str, Any]:
    errors: list[str] = []
    initial_dirty = dirty_paths()
    if initial_dirty:
        errors.append(
            "worktree must be completely clean before full-campaign readiness: "
            + ",".join(sorted(initial_dirty))
        )
    if os.environ.get("NO_HARDWARE") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() not in {
        "false", "0", "no",
    }:
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    if not GOAL.is_file() or sha256(GOAL) != GOAL_SHA256:
        errors.append("P10.3 Goal hash mismatch")
    freeze, _, freeze_errors = validate_artifact_freeze()
    errors.extend(freeze_errors)
    try:
        _, _, wiring_errors = base.validate_wiring_inventory()
        errors.extend(wiring_errors)
    except Exception as exc:  # readiness must fail closed on parser regressions.
        errors.append(f"wiring/inventory validation exception: {exc}")
    plans = build_plans()
    errors.extend(validate_plans(plans))
    missing = [rel(path) for path in HOST_INPUTS if not path.is_file()]
    errors.extend(f"missing host input: {path}" for path in missing)
    uncommitted = [rel(path) for path in HOST_INPUTS if path.is_file() and not file_matches_head(path)]
    errors.extend(f"host input is not the committed HEAD version: {path}" for path in uncommitted)
    offline_gates = {
        name: run_offline_gate(name, command)
        for name, command in OFFLINE_GATE_COMMANDS.items()
    }
    errors.extend(
        f"offline readiness gate failed: {name}"
        for name, result in offline_gates.items()
        if result.get("status") != "PASS"
    )
    allowed_generated = {
        rel(CAMPAIGN_FREEZE),
        rel(CAMPAIGN_FREEZE_MD),
    }
    unexpected_after_gates = {
        path for path in dirty_paths()
        if path not in allowed_generated and
        not path.startswith(rel(CAMPAIGN_FREEZE_RAW) + "/")
    }
    if unexpected_after_gates:
        errors.append(
            "offline gates changed files outside their evidence outputs: "
            + ",".join(sorted(unexpected_after_gates))
        )
    head = git("rev-parse", "HEAD")
    artifacts = freeze.get("artifacts", []) if isinstance(freeze, dict) else []
    functional_case_sizes = [
        int(fields[9], 0)
        for stage in BASE_STAGES
        for line in plans[stage].splitlines()
        if (fields := line.split()) and fields[0] == "CASE" and
        int(fields[2], 0) in (3, 13)
    ]
    payload = {
        "schema_version": 1,
        "test_id": "P10_3F-FULL-CAMPAIGN-FREEZE",
        "status": "PASS" if not errors else "FAIL",
        "scope": SCOPE,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": freeze.get("source_commit") if freeze else None,
        "host_source_commit": head,
        "base_artifact_freeze": {
            "path": rel(ARTIFACT_FREEZE),
            "sha256": sha256(ARTIFACT_FREEZE) if ARTIFACT_FREEZE.is_file() else None,
        },
        "acceptance_eligible": not errors,
        "eligibility_scope": "NEW_EXACT_CURRENT_RUN_AUTHORIZATION_ONLY",
        "source_tree_clean": not initial_dirty,
        "source_tree_clean_before_generation": not initial_dirty,
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "manual_instrumentation": "OMITTED_BY_USER",
        "old_hardware_pass_inherited": False,
        "allowed_hardware_stages": list(STAGES),
        "base_artifact_freeze_allowed_hardware_stages": freeze.get(
            "allowed_hardware_stages", []
        ) if freeze else [],
        "scope_expansion_policy": (
            "SUPPLEMENTAL_HOST_AND_EVIDENCE_FREEZE; NO_OLD_HARDWARE_RESULT_INHERITANCE"
        ),
        "stage_plan_sha256": {
            stage: hashlib.sha256(text.encode("ascii")).hexdigest()
            for stage, text in plans.items()
        },
        "maximum_lane_mask": 15,
        "maximum_long_test_command_bytes": MAX_COMMAND_BYTES,
        "maximum_functional_diagnostic_object_bytes": max(
            functional_case_sizes, default=0
        ),
        "safety_snapshot_after_each_functional_case": True,
        "maximum_single_formal_run_seconds": 1800,
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}",
        },
        "module_binding": MODULE_BINDING,
        "shutdown_policy": SHUTDOWN_POLICY,
        "artifacts": artifacts,
        "host_inputs": [metadata(path) for path in HOST_INPUTS if path.is_file()],
        "offline_gates": offline_gates,
        "forbidden": {
            "ethernet": True,
            "movement": True,
            "rotation": True,
            "realignment": True,
            "rewiring": True,
            "lane_mask_above_0xF": True,
            "two_hour_test": True,
            "p11": True,
        },
        "generated_at_utc": utc_now(),
        "errors": errors,
    }
    write_json(CAMPAIGN_FREEZE, payload)
    lines = [
        "# P10.3F full-campaign offline freeze",
        "",
        f"- Status: `{payload['status']}`",
        f"- Artifact source commit: `{payload['artifact_source_commit']}`",
        f"- Host source commit: `{head}`",
        "- Hardware actions executed: `false`",
        "- Current-run hardware authorization: `false`",
        "- Manual instrumentation: `OMITTED_BY_USER`",
        f"- Maximum long-test command: `{MAX_COMMAND_BYTES}` bytes",
        f"- Maximum bounded functional diagnostic object: "
        f"`{payload['maximum_functional_diagnostic_object_bytes']}` bytes",
        f"- Stages: `{len(STAGES)}`",
    ]
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {error}" for error in errors])
    write_text(CAMPAIGN_FREEZE_MD, "\n".join(lines) + "\n")
    return payload


def validate_authorization(
    path: Path, run_id: str
) -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        campaign = load_json(CAMPAIGN_FREEZE)
        record = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {}, [f"authorization/campaign freeze read failed: {exc}"]
    expected = {
        "schema_version": 1,
        "authorization_id": "P10_3F-FULL-CURRENT-RUN-IMMUTABLE",
        "scope": SCOPE,
        "run_id": run_id,
        "authorized": True,
        "consumed": False,
        "current_run_hardware_authorization": True,
        "no_hardware": False,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": campaign.get("artifact_source_commit"),
        "host_source_commit": campaign.get("host_source_commit"),
        "fixed_jtag_serial": EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": EXPECTED_ROTATING_SERIAL,
        "maximum_lane_mask": 15,
        "maximum_long_test_command_bytes": MAX_COMMAND_BYTES,
        "maximum_functional_diagnostic_object_bytes": MAX_FUNCTIONAL_DIAGNOSTIC_BYTES,
        "maximum_single_formal_run_seconds": 1800,
        "ethernet_allowed": False,
        "movement_rotation_realignment_or_rewiring_allowed": False,
        "manual_instrumentation": "OMITTED_BY_USER",
    }
    errors.extend(
        f"authorization {key} mismatch" for key, value in expected.items()
        if record.get(key) != value
    )
    if campaign.get("status") != "PASS" or campaign.get("acceptance_eligible") is not True:
        errors.append("full-campaign freeze is not acceptance-eligible PASS")
    if not file_matches_head(CAMPAIGN_FREEZE):
        errors.append("full-campaign freeze is not the committed HEAD version")
    base_record = campaign.get("base_artifact_freeze", {})
    if not isinstance(base_record, dict) or \
            base_record.get("path") != rel(ARTIFACT_FREEZE) or \
            not ARTIFACT_FREEZE.is_file() or \
            base_record.get("sha256") != sha256(ARTIFACT_FREEZE):
        errors.append("base artifact-freeze binding changed")
    if record.get("campaign_freeze_sha256") != sha256(CAMPAIGN_FREEZE):
        errors.append("authorization full-campaign freeze hash mismatch")
    if record.get("allowed_stages") != list(STAGES):
        errors.append("authorization stage set/order mismatch")
    if record.get("shutdown_policy") != SHUTDOWN_POLICY:
        errors.append("authorization shutdown/archive policy mismatch")
    if record.get("module_binding") != MODULE_BINDING:
        errors.append("authorization module binding mismatch")
    if not str(record.get("user_authorization_statement", "")).strip() or \
            not str(record.get("user_authorization_received_at_utc", "")).strip():
        errors.append("authorization lacks a new explicit user statement/timestamp")
    if record.get("artifacts") != campaign.get("artifacts"):
        errors.append("authorization artifact records differ from campaign freeze")
    if record.get("host_inputs") != campaign.get("host_inputs"):
        errors.append("authorization host input records differ from campaign freeze")
    offline_gates = campaign.get("offline_gates", {})
    if set(offline_gates) != set(OFFLINE_GATE_COMMANDS) or any(
        not isinstance(item, dict) or item.get("status") != "PASS"
        for item in offline_gates.values()
    ):
        errors.append("campaign offline-gate set/status mismatch")
    else:
        for name, item in offline_gates.items():
            try:
                log_item = item["log"]
                candidate = (ROOT / log_item["path"]).resolve()
                if not base.inside(candidate, CAMPAIGN_FREEZE_RAW) or \
                        not candidate.is_file() or \
                        candidate.stat().st_size != log_item.get("bytes") or \
                        sha256(candidate) != log_item.get("sha256"):
                    raise ValueError("gate log hash/size/path mismatch")
            except (KeyError, OSError, TypeError, ValueError) as exc:
                errors.append(f"campaign offline gate {name} changed: {exc}")
    host_source = str(campaign.get("host_source_commit", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", host_source) or not git_is_ancestor(host_source):
        errors.append("campaign host source commit is not an ancestor of HEAD")
    expected_host_paths = {rel(path) for path in HOST_INPUTS}
    observed_host_paths: set[str] = set()
    for item in campaign.get("host_inputs", []):
        if not isinstance(item, dict):
            errors.append("malformed campaign host-input record")
            continue
        try:
            candidate = (ROOT / item["path"]).resolve()
            if not base.inside(candidate, ROOT):
                raise ValueError("host input escapes repository")
            observed_host_paths.add(rel(candidate))
            if not candidate.is_file() or candidate.stat().st_size != item.get("bytes") or \
                    sha256(candidate) != item.get("sha256"):
                raise ValueError("host input hash/size mismatch")
            if not file_matches_head(candidate):
                raise ValueError("host input differs from committed HEAD")
        except (KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f"authorized host input changed: {exc}")
    if observed_host_paths != expected_host_paths:
        errors.append("campaign host-input path set mismatch")
    current_dirty = dirty_paths()
    allowed_dirty = {rel(path)}
    if current_dirty - allowed_dirty:
        errors.append(
            "hardware worktree contains changes outside the committed authorization: "
            + ",".join(sorted(current_dirty - allowed_dirty))
        )
    if not file_matches_head(path):
        errors.append("authorization is not the committed HEAD version")
    artifacts: dict[str, Path] = {}
    for item in campaign.get("artifacts", []):
        if not isinstance(item, dict):
            errors.append("malformed campaign artifact record")
            continue
        key = artifact_key(item)
        candidate = (ROOT / item["path"]).resolve()
        if not candidate.is_file() or candidate.stat().st_size != item.get("bytes") or \
                sha256(candidate) != item.get("sha256"):
            errors.append(f"authorized artifact changed: {key}")
        else:
            artifacts[key] = candidate
    return record, artifacts, errors


def invoke_stage(
    stage: str,
    plan_text: str,
    run_root: Path,
    auth: Path,
    artifacts: dict[str, Path],
    ps7: dict[str, Path],
    env: dict[str, str],
) -> tuple[dict[str, Any], Path]:
    stage_dir = run_root / "stages" / stage
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=False)
    plan = stage_dir / "immutable.plan"
    write_text(plan, plan_text)
    result = stage_dir / "xsdb.result.txt"
    command = [
        str(XSDB), str(STAGE_TCL), "tcp:localhost:3121",
        EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL,
        str(artifacts["fixed:functional_bitstream"]),
        str(artifacts["rotating:functional_bitstream"]),
        str(artifacts["fixed:elf"]), str(artifacts["rotating:elf"]),
        str(ps7["fixed"]), str(ps7["rotating"]), str(plan), str(dump_dir),
        str(run_root / "authorization/ABORT_NOW.txt"), str(result),
        TCL_STAGE[stage], str(auth), run_root.name,
        f"0x{EXPECTED_BUILD['fixed']:08X}", f"0x{EXPECTED_BUILD['rotating']:08X}",
    ]
    process = run_bounded(
        command,
        stage_dir / "xsdb.stdout.log",
        stage_dir / "xsdb.stderr.log",
        STAGE_TIMEOUT[stage],
        env,
    )
    return process, stage_dir


def read_rows(stage_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    ledger = stage_dir / "dumps/observations.psv"
    if not ledger.is_file():
        return [], ["observation ledger missing"]
    with ledger.open(encoding="ascii", newline="") as handle:
        try:
            return [base.integer_row(row) for row in csv.DictReader(handle, delimiter="|")], []
        except (KeyError, ValueError) as exc:
            return [], [f"observation ledger parse failed: {exc}"]


def load_custom_details(
    stage_dir: Path, rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    details: list[dict[str, Any]] = []
    errors: list[str] = []
    for row in rows:
        try:
            fixed_mail = Path(row["fixed_dump_path"]).resolve()
            rotating_mail = Path(row["rotating_dump_path"]).resolve()
            if not base.inside(fixed_mail, stage_dir) or not base.inside(rotating_mail, stage_dir):
                raise ValueError("mailbox path escaped stage")
            fixed_words = parse_mailbox(fixed_mail)
            rotating_words = parse_mailbox(rotating_mail)
            service_reset = row["command"] == 13 and bool(
                row["flags"] & base.p101.SERVICE_RESET_FLAGS
            )
            if service_reset:
                mailbox_errors: list[str] = []
                mailbox_pair: dict[str, Any] = {"fixed": {}, "rotating": {}}
            else:
                mailbox_errors, mailbox_pair = base.generic_pair(
                    row, fixed_words, rotating_words
                )
            errors.extend(mailbox_errors)
            fixed_snap = base.parse_p103(
                stage_dir / "dumps" / f"{row['label']}.fixed.p10_2.psv"
            )
            rotating_snap = base.parse_p103(
                stage_dir / "dumps" / f"{row['label']}.rotating.p10_2.psv"
            )
            errors.extend(base.snapshot_errors(row["label"], "fixed", fixed_snap))
            errors.extend(base.snapshot_errors(row["label"], "rotating", rotating_snap))
            if row["command"] == 13:
                fixed_p101 = Path(row["fixed_p10_1_dump_path"]).resolve()
                rotating_p101 = Path(row["rotating_p10_1_dump_path"]).resolve()
                if not base.inside(fixed_p101, stage_dir) or not base.inside(
                    rotating_p101, stage_dir
                ):
                    raise ValueError("P10.1 result path escaped stage")
                pair_errors, detail = base.p101.evaluate_p101_pair(
                    row,
                    base.p101.parse_p101(fixed_p101),
                    base.p101.parse_p101(rotating_p101),
                )
                if not service_reset:
                    detail["fixed_mailbox"] = mailbox_pair["fixed"]
                    detail["rotating_mailbox"] = mailbox_pair["rotating"]
                errors.extend(pair_errors)
            else:
                detail = mailbox_pair
            detail.update(
                {
                    "label": row["label"],
                    "command": row["command"],
                    "sequence": row["sequence"],
                    "started_ms": row["started_ms"],
                    "finished_ms": row["finished_ms"],
                    "window": row["window"],
                    "flags": row["flags"],
                    "lane_mask": row["lane"],
                    "direction": row["direction"],
                    "requested_bytes": row["size"],
                    "unavailable": row["unavailable"],
                    "injectmask": row["injectmask"],
                    "plan_fields": {
                        key: row[key]
                        for key in (
                            "command", "flags", "lane", "direction", "rate", "weights",
                            "size", "ring", "cache", "object", "dropdata", "dropack",
                            "unavailable", "rawtarget", "spacing", "stale", "initialseq",
                            "faultflags", "injectmask", "injectdelay",
                        )
                    },
                    "fixed_p10_2": fixed_snap,
                    "rotating_p10_2": rotating_snap,
                }
            )
            details.append(detail)
        except (OSError, ValueError, KeyError, struct.error) as exc:
            errors.append(f"{row.get('label', 'unknown')}:{exc}")
    return details, errors


def post_fault_archive_errors(forensic_summary: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if forensic_summary.get("status") != "PASS":
        return ["forensic capture/archive failed"]
    if set(forensic_summary.get("frozen_roles", [])) != {"fixed", "rotating"}:
        errors.append("controlled fault did not freeze both endpoint recorders")
    for item in forensic_summary.get("archives", []):
        if item.get("status") != "FROZEN":
            continue
        try:
            parsed = load_json(Path(item["json"]))
            snapshot = parsed["snapshot"]
            if (int(snapshot["fault_cause"], 0) & 0x10) == 0:
                errors.append(f"{item['role']}: frozen cause lacks terminal object fault")
            events = parsed.get("events", [])
            if len(events) < 8:
                errors.append(f"{item['role']}: post-fault event tail is incomplete")
                continue
            tail = [int(event["packed_status"], 0) for event in events[-8:]]
            terminal = tail[-1]
            if terminal & 0xF or ((terminal >> 8) & 0xF) != 0xF or \
                    not (terminal & (1 << 25)) or not (terminal & (1 << 26)):
                errors.append(f"{item['role']}: final event is not TX-low/SD-high/kill/shutdown")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"forensic archive decode failed: {exc}")
    return errors


def evaluate_custom_stage(
    stage: str,
    stage_dir: Path,
    process: dict[str, Any],
    forensic_summary: dict[str, Any],
) -> dict[str, Any]:
    markers = parse_markers(stage_dir / "xsdb.result.txt")
    errors: list[str] = []
    if process.get("returncode") != 0 or process.get("timed_out"):
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS" or \
            markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("stage/safe-boot PASS marker missing")
    rows, row_errors = read_rows(stage_dir)
    errors.extend(row_errors)
    if stage in EXPECTED_FAULT_STAGES:
        fault_label = {
            "fault_capture": "controlled_terminal_abort",
            "stream_dma_reset_fault": "stream_dma_reset_sender",
            "stream_service_reset_fault": "stream_service_reset_receiver",
        }[stage]
        direct = stage_dir / f"dumps/{fault_label}.fault_before_forensic_read.psv"
        if markers.get("P10_3F_FAULT_KILL_BEFORE_FORENSIC_READ") != "PASS" or \
                markers.get("P10_3F_FAULT_CAPTURE_LEFT_FROZEN") != "1" or \
                not direct.is_file():
            errors.append("controlled-fault direct pre-read evidence missing")
        errors.extend(post_fault_archive_errors(forensic_summary))
        if stage == "fault_capture":
            details: list[dict[str, Any]] = []
            if rows:
                errors.append("direct controlled-fault stage unexpectedly recorded a mailbox case")
        else:
            details, detail_errors = load_custom_details(stage_dir, rows)
            errors.extend(detail_errors)
            if len(details) != 1 or details[0].get("label") != fault_label or \
                    not details[0].get("recovery_case"):
                errors.append("expected reset-fault observation is incomplete")
        semantics = {
            "fault_type": {
                "fault_capture": "DIRECT_PL_ABORT_OF_ACTIVE_BOUNDED_OBJECT",
                "stream_dma_reset_fault": "EXPECTED_DMA_RESET_OBJECT_ABORT",
                "stream_service_reset_fault": "EXPECTED_ENDPOINT_SERVICE_RESET_ABORT",
            }[stage],
            "forensic_read_after_kill": True,
            "direct_evidence": rel(direct) if direct.is_file() else None,
            "explicit_clear_executed": False,
            "independent_shutdown_required_before_recovery": True,
        }
    else:
        if forensic_summary.get("status") != "PASS" or forensic_summary.get(
            "frozen_roles"
        ):
            errors.append("unexpected first-fault capture in acceptance stage")
        details, detail_errors = load_custom_details(stage_dir, rows)
        errors.extend(detail_errors)
        non_shutdown = [
            item for item in details if not item["label"].endswith("_endpoint_shutdown")
        ]
        shutdown = [
            item for item in details if item["label"].endswith("_endpoint_shutdown")
        ]
        if len(shutdown) != 1:
            errors.append("exactly one functional endpoint-shutdown observation required")
        for detail in non_shutdown:
            if detail["command"] in (3, 13):
                if detail["requested_bytes"] > MAX_COMMAND_BYTES:
                    errors.append(f"{detail['label']}: command exceeds 256 KiB")
                if not detail.get("recovery_case"):
                    errors.extend(
                        base.data_path_errors(
                            detail, unavailable=detail.get("unavailable", 0)
                        )
                    )
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for detail in non_shutdown:
            groups[str(detail.get("window", "NA"))].append(detail)
        semantics = {"maximum_command_bytes": MAX_COMMAND_BYTES}
        if stage in STAIRCASE_STAGES:
            expected = dict(zip(STAIRCASE_STAGES, forensic.LEVELS, strict=True))[stage]
            _, size, _ = expected
            if len(non_shutdown) != 2 or {d["direction"] for d in non_shutdown} != {0, 1} or \
                    any(d["requested_bytes"] != size or d["lane_mask"] != 15
                        for d in non_shutdown):
                errors.append("staircase level did not complete exact two-direction vector")
            semantics.update({"level_bytes": size, "directions": [0, 1]})
        elif stage == "two_lane_regression":
            totals = {}
            for label, direction in (("regression64_f2r", 0), ("regression64_r2f", 1)):
                selected = groups.get(label, [])
                committed = sum(item["requested_bytes"] for item in selected)
                elapsed_ms = max((item["finished_ms"] for item in selected), default=0) - \
                    min((item["started_ms"] for item in selected), default=0)
                goodput = committed * 8000 / elapsed_ms if elapsed_ms > 0 else 0
                if committed != 64 << 20 or len(selected) != 256 or \
                        any(item["direction"] != direction or item["lane_mask"] != 3
                            for item in selected) or goodput < 4_000_000:
                    errors.append(f"{label}: bounded 64-MiB regression/goodput failed")
                totals[label] = {"bytes": committed, "commands": len(selected),
                                 "application_goodput_bps": goodput}
            semantics["totals"] = totals
        elif stage == "streaming_64m":
            normal = {}
            for direction, side in ((0, "f2r"), (1, "r2f")):
                for index in range(1, 4):
                    label = f"stream64_{side}_{index}"
                    selected = groups.get(label, [])
                    committed = sum(item["requested_bytes"] for item in selected)
                    if committed != 64 << 20 or len(selected) != 256 or \
                            any(item["direction"] != direction for item in selected):
                        errors.append(f"{label}: exact bounded 64-MiB aggregate missing")
                    normal[label] = {"bytes": committed, "commands": len(selected)}
            expected_recovery = {
                "stream_lane2_unavailable": (64 << 20, 4),
                "stream_clean_after_lane2": (64 << 20, 0),
                "stream_lane3_unavailable": (64 << 20, 8),
                "stream_clean_after_lane3": (64 << 20, 0),
            }
            for label, (expected_bytes, unavailable) in expected_recovery.items():
                selected = groups.get(label, [])
                if sum(item["requested_bytes"] for item in selected) != expected_bytes or \
                        any(item["unavailable"] != unavailable for item in selected):
                    errors.append(f"{label}: bounded recovery aggregate failed")
            semantics.update({"normal_64m": normal, "object_bytes": MAX_COMMAND_BYTES,
                              "old_64m_hardware_result_inherited": False})
        elif stage in STREAM_RECOVERY_STAGES:
            label, direction, fault_stage = {
                "stream_dma_reset_recovery_64m": (
                    "stream_clean_after_dma_reset", 0, "stream_dma_reset_fault"
                ),
                "stream_service_reset_recovery_64m": (
                    "stream_clean_after_service_reset", 1,
                    "stream_service_reset_fault"
                ),
            }[stage]
            selected = groups.get(label, [])
            committed = sum(item["requested_bytes"] for item in selected)
            if committed != 64 << 20 or len(selected) != 256 or any(
                item["direction"] != direction or item["lane_mask"] != 15
                for item in selected
            ):
                errors.append(f"{label}: exact post-fault 64-MiB recovery missing")
            semantics.update({
                "recovery_after_stage": fault_stage,
                "committed_bytes": committed,
                "commands": len(selected),
                "fresh_functional_reload": True,
            })
        elif stage == "performance":
            windows = []
            for label, direction in (("sustained_300s_f2r", 0), ("sustained_300s_r2f", 1)):
                selected = groups.get(label, [])
                committed = sum(item["requested_bytes"] for item in selected)
                goodput = committed * 8 / 300
                if committed < 300 << 20 or goodput < 8_000_000 or \
                        any(item["direction"] != direction for item in selected):
                    errors.append(f"{label}: 300-second performance target failed")
                windows.append({"label": label, "committed_bytes": committed,
                                "application_goodput_bps": goodput,
                                "commands": len(selected)})
            semantics["windows"] = windows
        elif stage == "formal_30min":
            elapsed = int(markers.get("P10_3F_FORMAL_ELAPSED_MS", "0"))
            if markers.get("P10_3F_FORMAL_RESULT") != "PASS" or \
                    elapsed not in range(1_800_000, 1_800_501):
                errors.append("formal duration/result marker mismatch")
            windows = []
            for label, direction in (
                ("stationary_30min_formal_f2r", 0),
                ("stationary_30min_formal_r2f", 1),
            ):
                selected = groups.get(label, [])
                committed = sum(item["requested_bytes"] for item in selected)
                goodput = committed * 8 / 840
                active_ms = sum(item["finished_ms"] - item["started_ms"] for item in selected)
                if not selected or goodput < 8_000_000 or active_ms < 798_000 or \
                        any(item["direction"] != direction for item in selected):
                    errors.append(f"{label}: formal goodput/coverage failed")
                windows.append({"label": label, "committed_bytes": committed,
                                "application_goodput_bps": goodput,
                                "active_ms": active_ms, "commands": len(selected)})
            semantics.update({"elapsed_ms": elapsed, "formal_windows": windows,
                              "maximum_command_bytes": MAX_COMMAND_BYTES})

        gpio_rows, gpio_errors = base.load_ps_gpio(stage_dir)
        errors.extend(gpio_errors)
        # Short 1/4/16-KiB commands can legitimately finish between the mailbox
        # ACTIVE read and the following JTAG GPIO read.  Require direct active
        # LED readback only in the sustained stages, where missing the state is
        # not explainable by that sampling race.  Every stage still proves the
        # GPIO direction/OE plus safe-boot and endpoint-shutdown OFF states.
        if stage in {
            "streaming_64m", *STREAM_RECOVERY_STAGES,
            "performance", "formal_30min",
        }:
            active_gpio = [
                row for row in gpio_rows if row["label"].endswith("_active")
            ]
            for direction in {item["direction"] for item in non_shutdown
                              if item["command"] in (3, 13)}:
                sender = "fixed" if direction == 0 else "rotating"
                receiver = "rotating" if direction == 0 else "fixed"
                if not any(row["role"] == sender and not (row["data_ro"] & 1)
                           for row in active_gpio):
                    errors.append(f"direction{direction}: PS TX LED activity not sampled")
                if not any(row["role"] == receiver and
                           not (row["data_ro"] & (1 << 13))
                           for row in active_gpio):
                    errors.append(f"direction{direction}: PS RX LED activity not sampled")

    summary = {
        "schema_version": 1,
        "test_id": f"P10_3F-FULL-{stage.upper()}",
        "stage": stage,
        "status": "PASS" if not errors else "FAIL",
        "process": process,
        "markers": markers,
        "observation_count": len(rows),
        "details": details,
        "semantics": semantics,
        "forensics": forensic_summary,
        "errors": errors,
        "generated_at_utc": utc_now(),
    }
    write_json(stage_dir / "stage_summary.json", summary)
    return summary


def evaluate_stage(
    stage: str,
    stage_dir: Path,
    process: dict[str, Any],
    forensic_summary: dict[str, Any],
) -> dict[str, Any]:
    if stage in BASE_STAGES:
        summary = base.evaluate_stage(stage, stage_dir, process)
        if forensic_summary.get("status") != "PASS" or forensic_summary.get(
            "frozen_roles"
        ):
            summary["errors"].append("unexpected or unarchived first-fault capture")
            summary["status"] = "FAIL"
        summary["forensics"] = forensic_summary
        write_json(stage_dir / "stage_summary.json", summary)
        return summary
    return evaluate_custom_stage(stage, stage_dir, process, forensic_summary)


def guarded_shutdown(
    run_root: Path,
    auth: Path,
    artifacts: dict[str, Path],
    label: str,
    env: dict[str, str],
) -> dict[str, Any]:
    return forensic.guarded_shutdown(run_root, auth, artifacts, label, env)


def evidence_manifest(run_root: Path, status: str) -> dict[str, Any]:
    records = []
    for path in sorted(run_root.rglob("*")):
        if path.is_file() and path.name != "run_evidence_sha256_manifest.json":
            records.append(metadata(path))
    payload = {
        "schema_version": 1,
        "status": status,
        "run_id": run_root.name,
        "files": records,
        "generated_at_utc": utc_now(),
    }
    write_json(run_root / "final/run_evidence_sha256_manifest.json", payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-readiness", action="store_true")
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--run-id")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_readiness:
        payload = prepare_campaign_freeze()
        print(f"P10_3F_FULL_CAMPAIGN_FREEZE={payload['status']}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
        return 0 if payload["status"] == "PASS" else 2
    if not args.run_id or not RUN_RE.fullmatch(args.run_id):
        print("P10_3F_FULL_RUNNER_REFUSED=VALID_UNIQUE_RUN_ID_REQUIRED", file=sys.stderr)
        return 3
    auth = args.authorization.resolve()
    record, artifacts, errors = validate_authorization(auth, args.run_id)
    if args.validate_only:
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors},
                         indent=2, ensure_ascii=False))
        return 0 if not errors else 3
    if not args.execute_hardware:
        errors.append("--execute-hardware is required")
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "true":
        errors.append("NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required")
    if auth != AUTH.resolve():
        errors.append("canonical P10.3F full authorization path required")
    run_root = HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("run_id evidence directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2, ensure_ascii=False), file=sys.stderr)
        return 3

    for name in ("authorization", "artifacts", "stages", "forensics", "shutdown",
                 "raw_logs", "final"):
        (run_root / name).mkdir(parents=True, exist_ok=False)
    shutil.copy2(auth, run_root / "authorization/immutable_authorization.json")
    shutil.copy2(CAMPAIGN_FREEZE, run_root / "artifacts/campaign_freeze.json")
    shutil.copy2(ARTIFACT_FREEZE, run_root / "artifacts/base_artifact_freeze.json")
    ps7: dict[str, Path] = {}
    for role in ("fixed", "rotating"):
        destination = run_root / "artifacts" / role / "ps7_init.tcl"
        extract_ps7_init(artifacts[f"{role}:xsa"], destination)
        ps7[role] = destination

    env = {
        **os.environ,
        "NO_HARDWARE": "0",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
        "RF_COMM_P10_HW_AUTH": "P10_3F_IMMUTABLE_AUTHORIZED",
    }
    plans = build_plans()
    server_proc = None
    stage_results: list[dict[str, Any]] = []
    forensic_results: list[dict[str, Any]] = []
    shutdown_results: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    functional_loaded = False
    active_stage: str | None = None
    active_archived = False
    try:
        server_proc, server = start_hw_server(run_root / "raw_logs")
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server unavailable"))
        initial = guarded_shutdown(run_root, auth, artifacts, "initial", env)
        shutdown_results.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for stage in STAGES:
            active_stage = stage
            active_archived = False
            before = guarded_shutdown(run_root, auth, artifacts, f"{stage}_before", env)
            shutdown_results.append(before)
            if before.get("status") != "PASS":
                raise RuntimeError(f"{stage} shutdown-before unconfirmed")
            functional_loaded = True
            process, stage_dir = invoke_stage(
                stage, plans[stage], run_root, auth, artifacts, ps7, env
            )
            forensic_summary = forensic.capture_and_archive(stage, run_root, auth, env)
            forensic_results.append(forensic_summary)
            active_archived = True
            after = guarded_shutdown(run_root, auth, artifacts, f"{stage}_after", env)
            shutdown_results.append(after)
            functional_loaded = False
            result = evaluate_stage(stage, stage_dir, process, forensic_summary)
            result["shutdown_after_status"] = after.get("status")
            stage_results.append(result)
            if forensic_summary.get("status") != "PASS" or after.get("status") != "PASS" or \
                    result.get("status") != "PASS":
                raise RuntimeError(f"{stage} failed closed")
        final_shutdown = guarded_shutdown(run_root, auth, artifacts, "final", env)
        shutdown_results.append(final_shutdown)
        if final_shutdown.get("status") != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except Exception as exc:
        campaign_errors.append(str(exc))
    finally:
        if functional_loaded and active_stage is not None and not active_archived:
            try:
                forensic_results.append(
                    forensic.capture_and_archive(
                        f"{active_stage}_finally_before_shutdown", run_root, auth, env
                    )
                )
            except BaseException as exc:
                campaign_errors.append(f"finally forensic archive failed: {exc}")
        emergency = guarded_shutdown(run_root, auth, artifacts, "finally", env)
        shutdown_results.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            try:
                terminate_tree(server_proc)
            except Exception as exc:
                campaign_errors.append(f"hw_server termination failed: {exc}")

    all_stages = len(stage_results) == len(STAGES) and all(
        item.get("status") == "PASS" for item in stage_results
    )
    all_shutdown = bool(shutdown_results) and all(
        item.get("status") == "PASS" for item in shutdown_results
    )
    status = "PASS" if all_stages and all_shutdown and not campaign_errors else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": "P10_3F-FULL-HARDWARE-FINAL",
        "status": status,
        "scope": SCOPE,
        "run_id": args.run_id,
        "artifact_source_commit": record["artifact_source_commit"],
        "host_source_commit": record["host_source_commit"],
        "goal_sha256": GOAL_SHA256,
        "campaign_freeze_sha256": sha256(CAMPAIGN_FREEZE),
        "hardware_actions_executed": True,
        "ethernet_used": False,
        "movement": False,
        "rotation": False,
        "realignment": False,
        "rewiring": False,
        "maximum_lane_mask": 15,
        "maximum_long_test_command_bytes": MAX_COMMAND_BYTES,
        "maximum_functional_diagnostic_object_bytes": MAX_FUNCTIONAL_DIAGNOSTIC_BYTES,
        "maximum_single_formal_run_seconds": 1800,
        "manual_instrumentation": "OMITTED_BY_USER",
        "old_hardware_pass_inherited": False,
        "module_binding": MODULE_BINDING,
        "stages": stage_results,
        "forensics": forensic_results,
        "shutdowns": shutdown_results,
        "SHUTDOWN_FIXED": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdown_results
        ) else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdown_results
        ) else "FAIL",
        "errors": campaign_errors,
        "generated_at_utc": utc_now(),
    }
    write_json(run_root / "final/summary.json", summary)
    evidence_manifest(run_root, status)
    write_json(GENERATED_FINAL, summary)
    consumed = dict(record)
    consumed.update(
        {
            "status": f"CONSUMED_AFTER_P10_3F_FULL_{status}",
            "current_run_hardware_authorization": False,
            "consumed": True,
            "consumed_at_utc": utc_now(),
            "result": rel(run_root / "final/summary.json"),
        }
    )
    write_json(AUTH, consumed)
    print(f"P10_3F_FULL_HARDWARE={status}")
    print(f"P10_3F_FULL_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
