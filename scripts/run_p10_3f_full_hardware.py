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
AGGREGATE_RUNTIME_CONFIG = (
    ROOT / "config/performance/p10_3f_full_aggregate_runtime.yaml"
)
WIRING = ROOT / "config/hardware/p10_3_actual_wiring.yaml"
INVENTORY = ROOT / "config/hardware/tfdu_module_inventory.yaml"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
FORENSIC_TCL = ROOT / "scripts/hw/p10_3f_fault_forensics.tcl"
TCL_COMPLETE_CHECK = ROOT / "scripts/hw/check_tcl_complete.tcl"
TCLSH = Path(
    r"D:\Xilinx\Vivado\2023.1\tps\win64\git-2.16.2\mingw64\bin\tclsh.exe"
)
HW_ROOT = ROOT / "evidence/hardware/p10_3f_full"
GENERATED = ROOT / "evidence/generated"
GENERATED_FINAL = ROOT / "evidence/generated/p10_3f_full_hardware_final_summary.json"
STATIC_REPO_INTAKE = GENERATED / "p10_3_repo_intake.json"
STATIC_WIRING_INTAKE = GENERATED / "p10_3_wiring.json"
STATIC_MODULE_INTAKE = GENERATED / "p10_3_module_inventory.json"
STATIC_INTAKE_FILES = (
    STATIC_REPO_INTAKE,
    GENERATED / "p10_3_repo_intake.md",
    STATIC_WIRING_INTAKE,
    GENERATED / "p10_3_wiring.md",
    STATIC_MODULE_INTAKE,
    GENERATED / "p10_3_module_inventory.md",
)
STATIC_REPO_INPUTS = (
    ROOT / "PROJECT_CONSTRAINTS.txt",
    ROOT / "AGENTS.md",
    ROOT / "config/project_state.json",
    ROOT / "config/project_requirements.yaml",
    ROOT / "config/register_map/ir_axi_regs.yaml",
    WIRING,
    INVENTORY,
    ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
    ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
    ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
    ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
)
ALLOWED_EXECUTION_BRANCHES = {
    "p10.3/ax7020-stationary-4lane-hardware",
    "codex/p10.3-fault-forensics",
}
EXPECTED_BUILD = {"fixed": 0x50334646, "rotating": 0x50334652}
INTERNAL_OBJECT_BYTES = 262_144
MAX_STAIRCASE_LEVEL_BYTES = INTERNAL_OBJECT_BYTES
MAX_AGGREGATE_COMMAND_BYTES = 64 << 20
WINDOW_COMMAND_BYTES = frozenset((1 << 20, 4 << 20, 16 << 20, 64 << 20))
# Compatibility name for callers that mean the protocol's internal object,
# not the size of one board-autonomous aggregate command.
MAX_COMMAND_BYTES = INTERNAL_OBJECT_BYTES
MAX_FUNCTIONAL_DIAGNOSTIC_BYTES = 16 << 20
RUN_RE = re.compile(
    r"^p10_3f_full_(?P<utc>[0-9]{8}T[0-9]{6}Z)_"
    r"(?P<host>[0-9a-f]{8})_(?P<fixed>[0-9a-f]{8})_"
    r"(?P<rotating>[0-9a-f]{8})$"
)


def with_current_build_expectations(callback: Any, *args: Any, **kwargs: Any) -> Any:
    """Run a legacy P10.3 evaluator against this immutable bundle's IDs.

    The shared P10.3 evaluator intentionally retains the older P10.3 artifact
    identity.  P10.3F reuses its parsing and safety checks, but must compare the
    mailbox identity against the P10.3F functional images.  Replace the shared
    expectation only for the duration of one synchronous evaluation and always
    restore it so historical runners keep their original artifact binding.
    """
    previous = base.EXPECTED_ROLE
    base.EXPECTED_ROLE = {
        role: {
            **values,
            "firmware": EXPECTED_BUILD[role],
            "build": EXPECTED_BUILD[role],
        }
        for role, values in previous.items()
    }
    try:
        return callback(*args, **kwargs)
    finally:
        base.EXPECTED_ROLE = previous

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
    # The user-required 1/4/16/64/256-KiB progression must precede every
    # longer diagnostic, aggregate, performance, or formal transfer.  No later
    # stage is admitted until both directions at every level pass their safety
    # snapshot gate.
    *STAIRCASE_STAGES,
    "fault_capture",
    "raw_8x8",
    "per_lane_phy",
    "two_lane_regression",
    "four_lane_raw",
    "mask_matrix",
    "degrade",
    "arq_sack",
    "dma",
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
RUN_DIRECTORIES = (
    "authorization", "wiring", "module_inventory", "artifacts", "stages",
    "forensics", "fault_forensics", "staircase", "target_identity",
    "safe_boot", "power_preflight", "module_intake", "raw_8x8",
    "per_lane_phy", "two_lane_regression", "four_lane_raw", "mask_matrix",
    "degraded_modes", "arq_scheduler", "dma_ddr_cache", "streaming_64m",
    "performance_f2r", "performance_r2f", "formal_30min", "shutdown",
    "raw_logs", "final",
)
PUBLISHED_STAGE_GROUPS = {
    "module_intake": ("module_intake",),
    "raw_8x8": ("raw_8x8",),
    "per_lane_phy": ("per_lane_phy",),
    "two_lane_regression": ("two_lane_regression",),
    "four_lane_raw": ("four_lane_raw",),
    "mask_matrix": ("mask_matrix",),
    "degraded_modes": ("degrade",),
    "arq_scheduler": ("arq_sack",),
    "dma_ddr_cache": ("dma",),
    "streaming_64m": (
        "streaming_64m", "stream_dma_reset_fault",
        "stream_dma_reset_recovery_64m", "stream_service_reset_fault",
        "stream_service_reset_recovery_64m",
    ),
    "performance": ("performance",),
    "formal_30min": ("formal_30min",),
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
    AGGREGATE_RUNTIME_CONFIG,
    WIRING,
    INVENTORY,
    ROOT / "config/hardware/p10_3_ax7020_activity_leds.yaml",
    ROOT / "docs/hardware/P10_3_AS_WIRED_RECORD.md",
    ROOT / "docs/hardware/P10_3_AX7020_ACTIVITY_LED_DESIGN.md",
    ROOT / "docs/design/P10_3_FIRST_FAULT_FORENSICS.md",
    ROOT / "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
    ROOT / "docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md",
    ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
    ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
    ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
    ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
    ROOT / "board_profiles/ax7020_fixed_4lane/p10_3_runtime_role.h",
    ROOT / "board_profiles/ax7020_rotating_4lane/p10_3_runtime_role.h",
    ROOT / "scripts/archive_p10_fault_forensics.py",
    ROOT / "scripts/prepare_p10_3_offline.py",
    ROOT / "scripts/run_p10_3_ax7020_4lane_hardware.py",
    ROOT / "scripts/run_p10_3f_staircase_hardware.py",
    Path(__file__).resolve(),
    ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl",
    ROOT / "scripts/hw/p10_3f_fault_forensics.tcl",
    ROOT / "scripts/hw/p10_program_dual_shutdown.tcl",
    TCL_COMPLETE_CHECK,
    ROOT / "scripts/p10_hardware_runtime.py",
    ROOT / "tests/test_p10_3f_full_hardware.py",
    *STATIC_INTAKE_FILES,
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

    def allocate(self, total_bytes: int = INTERNAL_OBJECT_BYTES) -> int:
        count = (total_bytes + INTERNAL_OBJECT_BYTES - 1) // INTERNAL_OBJECT_BYTES
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
    if total_bytes % INTERNAL_OBJECT_BYTES or not (
        INTERNAL_OBJECT_BYTES <= total_bytes <= MAX_AGGREGATE_COMMAND_BYTES
    ):
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
            "# Exact 64-MiB board-autonomous regression; internal objects are 256 KiB",
            total_line("regression64_f2r", 64 << 20, 0, 3, 0, ids),
            total_line("regression64_r2f", 64 << 20, 1, 3, 0, ids),
            "",
        )
    )
    for stage, (level, size, tag) in zip(
        STAIRCASE_STAGES, forensic.LEVELS, strict=True
    ):
        plans[stage] = forensic.staircase_plan(level, size, tag)

    streaming = [
        "# Board-autonomous 64-MiB commands; internal protocol objects are 256 KiB"
    ]
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
        size=INTERNAL_OBJECT_BYTES,
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
        f"{INTERNAL_OBJECT_BYTES} {service_id}\n"
    )
    plans["stream_service_reset_recovery_64m"] = (
        "# Fresh post-archive/reload 64-MiB service-reset recovery aggregate\n"
        + total_line("stream_clean_after_service_reset", 64 << 20, 1, 15, 0, ids)
        + "\n"
    )
    plans["performance"] = (
        "# 300-second windows use 1/4/16/64-MiB board-autonomous commands\n"
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
    staircase_end = max(STAGES.index(stage) for stage in STAIRCASE_STAGES)
    for later in (
        "fault_capture", "raw_8x8", "per_lane_phy", "two_lane_regression",
        "four_lane_raw", "mask_matrix", "degrade", "arq_sack", "dma",
        "streaming_64m", "performance", "formal_30min",
    ):
        if STAGES.index(later) <= staircase_end:
            errors.append(f"{later}: admitted before bounded staircase completed")
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
                    if stage not in BASE_STAGES and size > INTERNAL_OBJECT_BYTES:
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
                if total % INTERNAL_OBJECT_BYTES or not (
                    INTERNAL_OBJECT_BYTES <= total <= MAX_AGGREGATE_COMMAND_BYTES
                ):
                    errors.append(f"{stage}: malformed bounded total")
                else:
                    count = total // INTERNAL_OBJECT_BYTES
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


def validate_static_intake_evidence() -> list[str]:
    """Verify that the Goal-named offline intake views match current inputs.

    These files are mutable generated views, not historical raw evidence.  A
    current-artifact campaign must not silently carry forward module identities,
    wiring hashes, branches, or canonical-input hashes from an earlier bundle.
    """
    errors: list[str] = []
    try:
        repo = load_json(STATIC_REPO_INTAKE)
        wiring_view = load_json(STATIC_WIRING_INTAKE)
        inventory_view = load_json(STATIC_MODULE_INTAKE)
        wiring = base.load_yaml(WIRING)
        inventory = base.load_yaml(INVENTORY)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"static intake evidence read failed: {exc}"]

    branch = git("branch", "--show-current")
    if branch not in ALLOWED_EXECUTION_BRANCHES or repo.get("branch") != branch:
        errors.append("static repository-intake branch is not the current allowed branch")
    for name, payload in (
        ("repository", repo),
        ("wiring", wiring_view),
        ("module inventory", inventory_view),
    ):
        if payload.get("status") != "PASS" or payload.get("no_hardware") is not True or \
                payload.get("hardware_actions_executed") is not False or \
                payload.get("current_run_hardware_authorization", False) is not False:
            errors.append(f"static {name} intake status/safety declaration mismatch")
        source = str(payload.get("source_commit", ""))
        if not re.fullmatch(r"[0-9a-f]{40}", source) or not git_is_ancestor(source):
            errors.append(f"static {name} intake source commit is not an ancestor")

    if repo.get("goal") != metadata(GOAL):
        errors.append("static repository intake Goal binding is stale")
    observed_inputs = {
        item.get("path"): item for item in repo.get("inputs", [])
        if isinstance(item, dict)
    }
    expected_inputs = {rel(path): metadata(path) for path in STATIC_REPO_INPUTS}
    if observed_inputs != expected_inputs:
        errors.append("static repository intake canonical-input set/hash is stale")

    expected_wiring = metadata(WIRING)
    if any((
        wiring_view.get("canonical_path") != expected_wiring["path"],
        wiring_view.get("sha256") != expected_wiring["sha256"],
        wiring_view.get("bytes") != expected_wiring["bytes"],
        wiring_view.get("module_positions") != wiring.get("module_positions"),
        wiring_view.get("physical_wiring_completed") is not True,
    )):
        errors.append("static actual-wiring intake does not match current canonical wiring")

    expected_inventory = metadata(INVENTORY)
    installation = inventory.get("p10_3_current_installation", {})
    active = installation.get("modules", {})
    observed_binding = {
        module: item.get("small_board_id")
        for module, item in active.items() if isinstance(item, dict)
    }
    if any((
        inventory_view.get("canonical_path") != expected_inventory["path"],
        inventory_view.get("sha256") != expected_inventory["sha256"],
        inventory_view.get("bytes") != expected_inventory["bytes"],
        inventory_view.get("active_modules") != active,
        inventory_view.get("active_module_count") != 8,
        inventory_view.get("unique_small_board_id_count") != 8,
        observed_binding != MODULE_BINDING,
        inventory_view.get("old_f1_active") is not False,
        inventory_view.get("old_f1_status") != "QUARANTINED_NOT_ACCEPTED",
    )):
        errors.append("static module-inventory intake does not match current installation")
    return errors


def validate_aggregate_runtime_contract() -> list[str]:
    """Bind the host remediation to a separate canonical runtime contract.

    The original P10.3F staircase file remains the immutable contract for the
    already-frozen RTL artifact.  This supplemental host contract controls only
    post-staircase aggregation and must never weaken the underlying safety path.
    """
    try:
        config = base.load_yaml(AGGREGATE_RUNTIME_CONFIG)
    except (OSError, ValueError) as exc:
        return [f"aggregate runtime contract read failed: {exc}"]
    admission = config.get("admission_precondition", {})
    runtime = config.get("aggregate_runtime", {})
    safety = config.get("safety", {})
    formal = config.get("formal", {})
    expected_levels = [1024, 4096, 16384, 65536, 262144]
    errors: list[str] = []
    if config.get("schema_version") != 1 or config.get("status") != \
            "OFFLINE_DEFINED_PENDING_CURRENT_RUN_AUTHORIZATION":
        errors.append("aggregate runtime contract identity/status mismatch")
    if admission.get("staircase_config") != rel(
        ROOT / "config/performance/p10_3f_staircase.yaml"
    ) or admission.get("exact_bidirectional_levels_bytes") != expected_levels or \
            admission.get("require_each_staircase_direction_snapshot_gate") is not True:
        errors.append("aggregate runtime staircase admission mismatch")
    expected_runtime = {
        "internal_object_bytes": INTERNAL_OBJECT_BYTES,
        "segment_bytes": 65_536,
        "maximum_board_autonomous_aggregate_command_bytes": (
            MAX_AGGREGATE_COMMAND_BYTES
        ),
        "exact_64m_host_commands_per_direction": 1,
        "adaptive_window_command_bytes": sorted(WINDOW_COMMAND_BYTES),
        "host_in_per_object_fast_path": False,
        "require_snapshot_after_each_aggregate_command": True,
        "continuous_pl_first_fault_kill_during_command": True,
        "old_hardware_result_inherited": False,
    }
    if runtime != expected_runtime:
        errors.append("aggregate runtime command/object contract mismatch")
    for key in (
        "single_global_permit_preserved",
        "exact_rolling_duty_guard_preserved",
        "continuous_high_guard_preserved",
        "sd_mode_txd_kill_preserved",
        "immediate_fault_tx_kill_and_full_shutdown",
        "frozen_forensics_preserved_until_archive_commit",
    ):
        if safety.get(key) is not True:
            errors.append(f"aggregate runtime safety contract mismatch: {key}")
    if formal != {"maximum_single_run_seconds": 1800, "lane_mask": "0xF"}:
        errors.append("aggregate runtime formal bound mismatch")
    authorization = config.get("authorization", {})
    if authorization.get("no_hardware") is not True or \
            authorization.get("current_run_hardware_authorization") is not False:
        errors.append("aggregate runtime offline authorization state mismatch")
    return errors


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
    errors.extend(validate_static_intake_evidence())
    errors.extend(validate_aggregate_runtime_contract())
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
        "internal_stream_object_bytes": INTERNAL_OBJECT_BYTES,
        "maximum_staircase_level_bytes": MAX_STAIRCASE_LEVEL_BYTES,
        "maximum_long_test_command_bytes": MAX_AGGREGATE_COMMAND_BYTES,
        "maximum_board_autonomous_aggregate_command_bytes": (
            MAX_AGGREGATE_COMMAND_BYTES
        ),
        "maximum_functional_diagnostic_object_bytes": max(
            functional_case_sizes, default=0
        ),
        "safety_snapshot_after_each_functional_case": True,
        "safety_snapshot_after_each_staircase_direction": True,
        "safety_snapshot_after_each_aggregate_command": True,
        "hardware_first_fault_kill_active_during_each_command": True,
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
        f"- Internal protocol object: `{INTERNAL_OBJECT_BYTES}` bytes",
        f"- Maximum staircase level: `{MAX_STAIRCASE_LEVEL_BYTES}` bytes",
        f"- Maximum board-autonomous aggregate command: "
        f"`{MAX_AGGREGATE_COMMAND_BYTES}` bytes",
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
    run_match = RUN_RE.fullmatch(run_id)
    if run_match is None:
        errors.append("run ID does not satisfy the content-bound P10.3F format")
    else:
        artifacts_by_key = {
            artifact_key(item): item
            for item in campaign.get("artifacts", [])
            if isinstance(item, dict)
        }
        expected_run_parts = {
            "host": str(campaign.get("host_source_commit", ""))[:8],
            "fixed": str(
                artifacts_by_key.get("fixed:functional_bitstream", {}).get(
                    "sha256", ""
                )
            )[:8],
            "rotating": str(
                artifacts_by_key.get("rotating:functional_bitstream", {}).get(
                    "sha256", ""
                )
            )[:8],
        }
        for name, value in expected_run_parts.items():
            if run_match.group(name) != value:
                errors.append(f"run ID {name} digest prefix mismatch")
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
        "internal_stream_object_bytes": INTERNAL_OBJECT_BYTES,
        "maximum_staircase_level_bytes": MAX_STAIRCASE_LEVEL_BYTES,
        "maximum_long_test_command_bytes": MAX_AGGREGATE_COMMAND_BYTES,
        "maximum_board_autonomous_aggregate_command_bytes": (
            MAX_AGGREGATE_COMMAND_BYTES
        ),
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


def validate_custom_observation_shape(
    stage: str, rows: list[dict[str, Any]], plan_text: str
) -> list[str]:
    """Bind custom-stage observations to the immutable plan, in exact order.

    The Tcl process returning PASS is necessary but not sufficient evidence.
    This independent host check rejects skipped, duplicated, reordered, enlarged,
    or out-of-plan autonomous transfers and verifies actual object-ID separation.
    """
    errors: list[str] = []
    expected_fault = stage in EXPECTED_FAULT_STAGES
    shutdown_positions = [
        index for index, row in enumerate(rows)
        if str(row.get("label", "")).endswith("_endpoint_shutdown")
    ]
    if expected_fault:
        if shutdown_positions:
            errors.append("terminal-fault stage recorded an unexpected mailbox shutdown")
        body = rows
    else:
        if shutdown_positions != [len(rows) - 1]:
            errors.append("exactly one final functional endpoint-shutdown row required")
        body = rows[:-1] if shutdown_positions == [len(rows) - 1] else rows

    cursor = 0

    def consume_dynamic(
        label: str, direction: int, lane: int, unavailable: int = 0,
        total_bytes: int | None = None, first_object: int | None = None,
        aggregate: bool = False,
    ) -> None:
        nonlocal cursor
        selected: list[dict[str, Any]] = []
        while cursor < len(body) and body[cursor].get("window") == label:
            selected.append(body[cursor])
            cursor += 1
        if not selected:
            errors.append(f"{label}: dynamic window has no autonomous command")
            return
        for index, row in enumerate(selected):
            size = row.get("size", 0)
            valid_size = (
                size == total_bytes
                if aggregate
                else size in WINDOW_COMMAND_BYTES
            )
            if row.get("command") != 13 or row.get("direction") != direction or \
                    row.get("lane") != lane or row.get("unavailable") != unavailable or \
                    not str(row.get("label", "")).startswith(label) or \
                    not valid_size:
                errors.append(f"{label}: dynamic command {index} differs from bounded plan")
            if first_object is not None and row.get("object") != first_object:
                errors.append(f"{label}: object-ID sequence mismatch at command {index}")
        if total_bytes is not None:
            if sum(row.get("size", 0) for row in selected) != total_bytes:
                errors.append(f"{label}: aggregate byte count mismatch")
            expected_count = 1 if aggregate else (
                total_bytes + INTERNAL_OBJECT_BYTES - 1
            ) // INTERNAL_OBJECT_BYTES
            if len(selected) != expected_count:
                errors.append(f"{label}: aggregate command count mismatch")

    records = [
        line.split() for line in plan_text.splitlines()
        if line.split() and not line.lstrip().startswith("#")
    ]
    for fields in records:
        kind = fields[0]
        if kind == "P10FF_CHECKPOINT":
            continue
        if kind == "P10FF_ABORT_FAULT":
            if stage != "fault_capture":
                errors.append("out-of-stage direct fault record")
            continue
        if kind == "CASE":
            if cursor >= len(body):
                errors.append(f"missing immutable case {fields[1]}")
                continue
            row = body[cursor]
            cursor += 1
            if row.get("label") != fields[1]:
                errors.append(f"case order mismatch: expected {fields[1]}")
                continue
            expected_fields = dict(zip(base.CASE_ROW_FIELDS, (
                int(fields[2], 0), int(fields[3], 0), int(fields[4], 0),
                int(fields[5], 0), int(fields[6], 0), int(fields[7], 0),
                int(fields[8], 0), int(fields[9], 0), int(fields[10], 0),
                int(fields[11], 0), int(fields[12], 0), int(fields[13], 0),
                int(fields[14], 0), int(fields[15], 0), int(fields[16], 0),
                int(fields[17], 0), int(fields[18], 0), int(fields[19], 0),
                int(fields[20], 0), int(fields[21], 0), int(fields[22], 0),
                int(fields[23], 0), int(fields[24], 0), int(fields[25], 0),
                int(fields[26], 0), int(fields[27], 0), int(fields[28], 0),
            )))
            for name, value in expected_fields.items():
                if row.get(name) != value:
                    errors.append(f"{fields[1]}:{name} differs from immutable plan")
        elif kind == "P101_PSRESET":
            if cursor >= len(body):
                errors.append(f"missing service-reset vector {fields[1]}")
            else:
                row = body[cursor]
                cursor += 1
                direction = int(fields[3], 0)
                sender = "fixed" if direction == 0 else "rotating"
                expected_flag = 1 << (22 if fields[2] == sender else 23)
                expected = {
                    "label": fields[1],
                    "window": "PS_SERVICE_RESET",
                    "command": 13,
                    "flags": expected_flag,
                    "direction": direction,
                    "lane": int(fields[4], 0),
                    "size": int(fields[5], 0),
                    "object": int(fields[6], 0),
                    "unavailable": 0,
                }
                for name, value in expected.items():
                    if row.get(name) != value:
                        errors.append(
                            f"{fields[1]}:{name} differs from immutable service-reset plan"
                        )
        elif kind == "P10FF_TOTAL":
            consume_dynamic(
                fields[1], int(fields[3], 0), int(fields[4], 0),
                int(fields[5], 0), int(fields[2], 0), int(fields[6], 0), True,
            )
        elif kind == "P10FF_WINDOW":
            consume_dynamic(fields[1], int(fields[3], 0), int(fields[4], 0))
        elif kind == "P10FF_FORMAL":
            root = fields[1]
            for suffix, direction in (
                ("warmup_f2r", 0), ("warmup_r2f", 1),
                ("formal_f2r", 0), ("formal_r2f", 1),
            ):
                consume_dynamic(f"{root}_{suffix}", direction, 15)
        else:
            errors.append(f"unsupported custom plan record: {kind}")
    if cursor != len(body):
        errors.append(f"{len(body) - cursor} extra or reordered observations")
    sequences = [row.get("sequence") for row in rows]
    if len(set(sequences)) != len(sequences):
        errors.append("duplicate command sequence in observation ledger")
    intervals: list[tuple[int, int, str]] = []
    for row in body:
        if row.get("command") not in (3, 13):
            continue
        count = base.stream_object_count(row["size"]) if row["command"] == 13 else 1
        intervals.append((row["object"], row["object"] + count - 1, row["label"]))
    ordered = sorted(intervals)
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] <= previous[1]:
            errors.append(
                f"observed object-ID overlap: {previous[2]} and {current[2]}"
            )
    return errors


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
                mailbox_errors, mailbox_pair = with_current_build_expectations(
                    base.generic_pair, row, fixed_words, rotating_words
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
    errors.extend(validate_custom_observation_shape(
        stage, rows, build_plans()[stage]
    ))
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
                maximum = (
                    MAX_AGGREGATE_COMMAND_BYTES
                    if stage in BOUNDED_LONG_STAGES and stage not in STAIRCASE_STAGES
                    else INTERNAL_OBJECT_BYTES
                )
                if detail["requested_bytes"] > maximum:
                    errors.append(
                        f"{detail['label']}: command exceeds stage maximum {maximum}"
                    )
                if not detail.get("recovery_case"):
                    errors.extend(
                        base.data_path_errors(
                            detail, unavailable=detail.get("unavailable", 0)
                        )
                    )
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for detail in non_shutdown:
            groups[str(detail.get("window", "NA"))].append(detail)
        semantics = {
            "internal_object_bytes": INTERNAL_OBJECT_BYTES,
            "maximum_staircase_level_bytes": MAX_STAIRCASE_LEVEL_BYTES,
            "maximum_board_autonomous_aggregate_command_bytes": (
                MAX_AGGREGATE_COMMAND_BYTES
            ),
            "continuous_pl_first_fault_kill_during_command": True,
            "snapshot_after_each_completed_aggregate_command": True,
        }
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
                if committed != 64 << 20 or len(selected) != 1 or \
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
                    if committed != 64 << 20 or len(selected) != 1 or \
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
                        len(selected) != 1 or \
                        any(item["unavailable"] != unavailable for item in selected):
                    errors.append(f"{label}: bounded recovery aggregate failed")
            semantics.update({"normal_64m": normal,
                              "object_bytes": INTERNAL_OBJECT_BYTES,
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
            if committed != 64 << 20 or len(selected) != 1 or any(
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
                                "commands": len(selected), "direction": direction,
                                "duration_seconds": 300, "lane_mask": 15})
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
                                "active_ms": active_ms, "commands": len(selected),
                                "direction": direction, "duration_seconds": 840,
                                "lane_mask": 15})
            semantics.update({"elapsed_ms": elapsed, "formal_windows": windows,
                              "internal_object_bytes": INTERNAL_OBJECT_BYTES,
                              "maximum_board_autonomous_aggregate_command_bytes":
                              MAX_AGGREGATE_COMMAND_BYTES})

        gpio_rows, gpio_errors = base.load_ps_gpio(stage_dir)
        errors.extend(gpio_errors)
        # Short 1/4/16-KiB commands can legitimately finish between the mailbox
        # ACTIVE read and the following JTAG GPIO read.  Require direct LED
        # readback only in sustained stages.  The first ``*_active`` sample is
        # taken when either endpoint enters RUNNING; descriptor activity on the
        # actual sender/receiver can begin just after that read.  Therefore the
        # sustained-stage verdict must include the periodic in-window samples
        # carrying the exact case label, rather than treating the first sample
        # as the whole observation window.  Safe-boot and endpoint-shutdown OFF
        # states remain independently mandatory in ``base.load_ps_gpio``.
        if stage in {
            "streaming_64m", *STREAM_RECOVERY_STAGES,
            "performance", "formal_30min",
        }:
            led_evidence = []
            for direction in {item["direction"] for item in non_shutdown
                              if item["command"] in (3, 13)}:
                sender = "fixed" if direction == 0 else "rotating"
                receiver = "rotating" if direction == 0 else "fixed"
                labels = {
                    item["label"] for item in non_shutdown
                    if item["command"] in (3, 13) and
                    item["direction"] == direction
                }
                activity = summarize_ps_gpio_activity(
                    gpio_rows, labels, sender, receiver
                )
                activity["direction"] = direction
                led_evidence.append(activity)
                if activity["sender_tx_active_samples"] == 0:
                    errors.append(f"direction{direction}: PS TX LED activity not sampled")
                if activity["receiver_rx_active_samples"] == 0:
                    errors.append(f"direction{direction}: PS RX LED activity not sampled")
            semantics["ps_gpio_activity_evidence"] = led_evidence

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


def summarize_ps_gpio_activity(
    gpio_rows: list[dict[str, Any]],
    labels: set[str],
    sender: str,
    receiver: str,
) -> dict[str, Any]:
    """Summarize direct active-low PS LED samples for sustained commands.

    ``*_active`` is an edge-adjacent sample and an exact-label row is a
    periodic sample taken while the same command remains active.  Terminal,
    safe-boot, and unrelated-command rows are deliberately excluded.
    """
    accepted_labels = labels | {f"{label}_active" for label in labels}
    samples = [row for row in gpio_rows if row["label"] in accepted_labels]
    sender_tx = sum(
        row["role"] == sender and not (row["data_ro"] & 1)
        for row in samples
    )
    receiver_rx = sum(
        row["role"] == receiver and not (row["data_ro"] & (1 << 13))
        for row in samples
    )
    return {
        "labels": sorted(labels),
        "sample_count": len(samples),
        "sender": sender,
        "receiver": receiver,
        "sender_tx_active_samples": sender_tx,
        "receiver_rx_active_samples": receiver_rx,
    }


def evaluate_stage(
    stage: str,
    stage_dir: Path,
    process: dict[str, Any],
    forensic_summary: dict[str, Any],
) -> dict[str, Any]:
    if stage in BASE_STAGES:
        summary = with_current_build_expectations(
            base.evaluate_stage, stage, stage_dir, process
        )
        if forensic_summary.get("status") != "PASS" or forensic_summary.get(
            "frozen_roles"
        ):
            summary["errors"].append("unexpected or unarchived first-fault capture")
            summary["status"] = "FAIL"
        summary["forensics"] = forensic_summary
        write_json(stage_dir / "stage_summary.json", summary)
        return summary
    return evaluate_custom_stage(stage, stage_dir, process, forensic_summary)


def capture_and_archive(
    label: str,
    run_root: Path,
    auth: Path,
    env: dict[str, str],
    *,
    force_terminal_fault: bool = False,
) -> dict[str, Any]:
    """Capture, canonically archive, hash, and commit a volatile PL recorder.

    This full-campaign implementation intentionally does not modify the earlier
    staircase runner whose exact hash is part of immutable offline PASS evidence.
    """
    out = run_root / "forensics" / label
    out.mkdir(parents=True, exist_ok=True)
    capture_result = out / "capture.result.txt"
    command = [
        str(XSDB), FORENSIC_TCL,
        "abort_capture" if force_terminal_fault else "capture",
        "tcp:localhost:3121", EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL,
        out, auth, run_root.name, f"0x{EXPECTED_BUILD['fixed']:08X}",
        f"0x{EXPECTED_BUILD['rotating']:08X}", capture_result,
    ]
    process = run_bounded(
        [str(item) for item in command],
        out / "capture.stdout.log",
        out / "capture.stderr.log",
        180,
        env,
    )
    errors: list[str] = []
    archives: list[dict[str, Any]] = []
    markers = parse_markers(capture_result)
    if process.get("returncode") != 0 or process.get("timed_out") or \
            markers.get("P10_FF_FORENSIC_RESULT") != "PASS":
        errors.append("forensic XSDB capture failed")
    if not errors:
        try:
            for role in ("fixed", "rotating"):
                archives.append(
                    forensic.write_archive(
                        forensic.parse_psv(out / f"{role}.p10ff.psv"), out
                    )
                )
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"forensic binary/JSON archive failed: {exc}")
    frozen = [item for item in archives if item.get("status") == "FROZEN"]
    commit_process = None
    if frozen and not errors:
        digest = {item["role"]: item["binary_sha256"] for item in frozen}
        commit_result = out / "commit.result.txt"
        commit_command = [
            str(XSDB), str(FORENSIC_TCL), "commit", "tcp:localhost:3121",
            EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL, str(out), str(auth),
            run_root.name, f"0x{EXPECTED_BUILD['fixed']:08X}",
            f"0x{EXPECTED_BUILD['rotating']:08X}", str(commit_result),
            digest.get("fixed", "NONE"), digest.get("rotating", "NONE"),
        ]
        commit_process = run_bounded(
            commit_command,
            out / "commit.stdout.log",
            out / "commit.stderr.log",
            180,
            env,
        )
        if commit_process.get("returncode") != 0 or commit_process.get("timed_out") or \
                parse_markers(commit_result).get("P10_FF_FORENSIC_RESULT") != "PASS":
            errors.append("forensic archive commit failed")
    if force_terminal_fault:
        if markers.get("P10_FF_ABORT_BEFORE_CAPTURE") != "PASS":
            errors.append("forced terminal abort marker missing")
        if {item["role"] for item in frozen} != {"fixed", "rotating"}:
            errors.append("forced terminal abort did not archive both endpoint recorders")
    summary = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "label": label,
        "capture_process": process,
        "commit_process": commit_process,
        "archives": archives,
        "frozen_roles": [item["role"] for item in frozen],
        "force_terminal_fault": force_terminal_fault,
        "explicit_clear_executed": False,
        "errors": errors,
        "generated_at_utc": utc_now(),
    }
    write_json(out / "summary.json", summary)
    return summary


def guarded_shutdown(
    run_root: Path,
    auth: Path,
    artifacts: dict[str, Path],
    label: str,
    env: dict[str, str],
) -> dict[str, Any]:
    return forensic.guarded_shutdown(run_root, auth, artifacts, label, env)


def initialize_run_root(run_root: Path, auth: Path) -> list[dict[str, Any]]:
    """Create a self-contained immutable-input envelope before touching JTAG."""
    run_root.mkdir(parents=True, exist_ok=False)
    for name in RUN_DIRECTORIES:
        (run_root / name).mkdir(parents=True, exist_ok=False)
    copies = (
        (auth, run_root / "authorization/immutable_authorization.json"),
        (GOAL, run_root / "authorization/goal.md"),
        (CAMPAIGN_FREEZE, run_root / "artifacts/campaign_freeze.json"),
        (ARTIFACT_FREEZE, run_root / "artifacts/base_artifact_freeze.json"),
        (WIRING, run_root / "wiring/p10_3_actual_wiring.yaml"),
        (ROOT / "docs/hardware/P10_3_AS_WIRED_RECORD.md",
         run_root / "wiring/P10_3_AS_WIRED_RECORD.md"),
        (ROOT / "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
         run_root / "wiring/p10_2_ax7020_4lane_wiring.yaml"),
        (ROOT / "docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md",
         run_root / "wiring/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md"),
        (ROOT / "config/hardware/p10_3_ax7020_activity_leds.yaml",
         run_root / "wiring/p10_3_ax7020_activity_leds.yaml"),
        (ROOT / "docs/hardware/P10_3_AX7020_ACTIVITY_LED_DESIGN.md",
         run_root / "wiring/P10_3_AX7020_ACTIVITY_LED_DESIGN.md"),
        (INVENTORY, run_root / "module_inventory/tfdu_module_inventory.yaml"),
        (ROOT / "config/safety/p10_3_fault_forensics.yaml",
         run_root / "artifacts/p10_3_fault_forensics.yaml"),
        (ROOT / "config/performance/p10_3f_staircase.yaml",
         run_root / "artifacts/p10_3f_staircase.yaml"),
        (AGGREGATE_RUNTIME_CONFIG,
         run_root / "artifacts/p10_3f_full_aggregate_runtime.yaml"),
        (ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
         run_root / "artifacts/fixed/profile.yaml"),
        (ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
         run_root / "artifacts/rotating/profile.yaml"),
        (ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
         run_root / "artifacts/fixed/ax7020_fixed_4lane.generated.xdc"),
        (ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
         run_root / "artifacts/rotating/ax7020_rotating_4lane.generated.xdc"),
        (ROOT / "board_profiles/ax7020_fixed_4lane/p10_3_runtime_role.h",
         run_root / "artifacts/fixed/p10_3_runtime_role.h"),
        (ROOT / "board_profiles/ax7020_rotating_4lane/p10_3_runtime_role.h",
         run_root / "artifacts/rotating/p10_3_runtime_role.h"),
    )
    records: list[dict[str, Any]] = []
    for source, destination in copies:
        if not source.is_file():
            raise RuntimeError(f"immutable run input missing: {rel(source)}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        if sha256(source) != sha256(destination):
            raise RuntimeError(f"immutable run input copy mismatch: {destination}")
        records.append({
            "source": rel(source),
            "path": destination.relative_to(run_root).as_posix(),
            "sha256": sha256(destination),
            "bytes": destination.stat().st_size,
        })
    write_json(run_root / "authorization/immutable_input_copy_manifest.json", {
        "schema_version": 1,
        "status": "PASS",
        "files": records,
        "generated_at_utc": utc_now(),
    })
    write_text(
        run_root / "authorization/NO_MOVEMENT_NETWORK_ATTESTATION.txt",
        "ETHERNET=false\nMOVEMENT=false\nROTATION=false\nREALIGNMENT=false\n"
        "REWIRING=false\nMAX_LANE_MASK=0xF\nTWO_HOUR=false\nP11=false\n"
        "MANUAL_INSTRUMENTATION=OMITTED_BY_USER\n",
    )
    return records


def write_summary_pair(path_base: Path, payload: dict[str, Any], title: str) -> None:
    write_json(path_base.with_suffix(".json"), payload)
    write_text(
        path_base.with_suffix(".md"),
        f"# {title}\n\n"
        f"Status: `{payload.get('status', 'NOT_RECORDED')}`\n\n"
        f"Run ID: `{payload.get('run_id', 'NONE')}`\n\n"
        "The adjacent machine-readable JSON and its hashed raw-evidence "
        "references are authoritative.\n",
    )


def run_metadata(path: Path, run_root: Path) -> dict[str, Any]:
    return {
        "path": path.resolve().relative_to(run_root.resolve()).as_posix(),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def evidence_manifest(run_root: Path, status: str) -> dict[str, Any]:
    target = run_root / "final/run_evidence_sha256_manifest.json"
    records = []
    for path in sorted(run_root.rglob("*")):
        if path.is_file() and path != target:
            records.append(run_metadata(path, run_root))
    payload = {
        "schema_version": 1,
        "test_id": "P10_3F-FULL-HW-EVIDENCE-MANIFEST",
        "status": "INDEX_GENERATED",
        "acceptance_status": status,
        "run_id": run_root.name,
        "files": records,
        "generated_at_utc": utc_now(),
    }
    write_json(target, payload)
    return payload


def verify_evidence_manifest(run_root: Path) -> list[str]:
    errors: list[str] = []
    target = run_root / "final/run_evidence_sha256_manifest.json"
    try:
        value = load_json(target)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"evidence manifest unreadable: {exc}"]
    if value.get("schema_version") != 1 or value.get("run_id") != run_root.name or \
            value.get("status") != "INDEX_GENERATED":
        errors.append("evidence manifest identity/status mismatch")
    seen: set[str] = set()
    files = value.get("files")
    if not isinstance(files, list):
        return [*errors, "evidence manifest files is not a list"]
    for item in files:
        if not isinstance(item, dict):
            errors.append("malformed evidence manifest record")
            continue
        name = item.get("path", "")
        candidate = (run_root / str(name)).resolve()
        if not isinstance(name, str) or not name or "\\" in name or \
                name in seen or not base.inside(candidate, run_root) or \
                not candidate.is_file():
            errors.append(f"manifest duplicate/missing/outside path: {name}")
            continue
        seen.add(name)
        if candidate.stat().st_size != item.get("bytes") or \
                sha256(candidate) != item.get("sha256"):
            errors.append(f"manifest hash/size mismatch: {name}")
    expected = {
        path.relative_to(run_root).as_posix()
        for path in run_root.rglob("*")
        if path.is_file() and path != target
    }
    if seen != expected:
        errors.append(
            f"manifest file-set mismatch missing={sorted(expected - seen)} "
            f"extra={sorted(seen - expected)}"
        )
    return errors


def stage_reference(
    item: dict[str, Any] | None, stage: str, run_root: Path
) -> dict[str, Any]:
    path = run_root / "stages" / stage / "stage_summary.json"
    reference: dict[str, Any] = {
        "stage": stage,
        "status": item.get("status") if item else "NOT_EXECUTED",
        "test_id": item.get("test_id") if item else None,
        "errors": item.get("errors", []) if item else ["stage not executed"],
        "semantics": item.get("semantics", {}) if item else {},
    }
    if path.is_file():
        record = run_metadata(path, run_root)
        record["repository_path"] = rel(path)
        reference["raw_summary"] = record
    else:
        reference["raw_summary"] = None
    return reference


def common_evidence_binding(
    summary: dict[str, Any], run_root: Path, authorization: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "run_id": run_root.name,
        "scope": SCOPE,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": authorization["artifact_source_commit"],
        "host_source_commit": authorization["host_source_commit"],
        "campaign_freeze": {
            "path": rel(CAMPAIGN_FREEZE),
            "sha256": sha256(CAMPAIGN_FREEZE),
        },
        "base_artifact_freeze": {
            "path": rel(ARTIFACT_FREEZE),
            "sha256": sha256(ARTIFACT_FREEZE),
        },
        "artifacts": authorization["artifacts"],
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}",
        },
        "module_binding": MODULE_BINDING,
        "actual_wiring_sha256": sha256(WIRING),
        "module_inventory_sha256": sha256(INVENTORY),
        "hardware_actions_executed": summary["hardware_actions_executed"],
        "network_used": False,
        "movement": False,
        "rotation": False,
        "realignment": False,
        "rewiring": False,
        "maximum_lane_mask_authorized": "0xF",
        "two_hour_test": False,
        "p11": False,
        "manual_instrumentation": "OMITTED_BY_USER",
        "old_hardware_pass_inherited": False,
    }


def grouped_stage_payload(
    name: str,
    stages: tuple[str, ...],
    by_stage: dict[str, dict[str, Any]],
    run_root: Path,
    common: dict[str, Any],
) -> dict[str, Any]:
    references = [stage_reference(by_stage.get(stage), stage, run_root) for stage in stages]
    return {
        **common,
        "test_id": f"P10_3F-FULL-{name.upper()}",
        "summary_name": name,
        "status": "PASS" if all(
            reference["status"] == "PASS" for reference in references
        ) else "FAIL",
        "stage_evidence": references,
    }


def collect_campaign_metrics(stage_results: list[dict[str, Any]]) -> dict[str, Any]:
    by_stage = {item.get("stage"): item for item in stage_results}
    details = [
        detail
        for item in stage_results
        for detail in item.get("details", [])
        if isinstance(detail, dict)
    ]
    module_index = {
        "F0": ("fixed_p10_2", 0), "F1": ("fixed_p10_2", 1),
        "F2": ("fixed_p10_2", 2), "F3": ("fixed_p10_2", 3),
        "R0": ("rotating_p10_2", 4), "R1": ("rotating_p10_2", 5),
        "R2": ("rotating_p10_2", 6), "R3": ("rotating_p10_2", 7),
    }
    max_duty: dict[str, int | None] = {}
    max_continuous: dict[str, int | None] = {}
    module_hard_fault: dict[str, int | None] = {}
    for module, (snapshot_name, index) in module_index.items():
        observed = [
            detail[snapshot_name]["modules"][index]
            for detail in details
            if isinstance(detail.get(snapshot_name), dict) and
            isinstance(detail[snapshot_name].get("modules"), list) and
            len(detail[snapshot_name]["modules"]) > index
        ]
        max_duty[module] = max(
            (int(item.get("duty_high_max", 0)) for item in observed), default=None
        )
        max_continuous[module] = max(
            (int(item.get("tx_high_max", 0)) for item in observed), default=None
        )
        module_hard_fault[module] = max(
            (int(item.get("hard_fault", 0)) for item in observed), default=None
        )

    counter_aliases = {
        "crc_bad": ("physical_crc_bad",),
        "sha_mismatch": ("sha_mismatch_count",),
        "partial_commit": ("partial_commit_count",),
        "duplicate_commit": ("duplicate_commit_count",),
        "stale_commit": ("stale_commit_count",),
        "retry_exhausted": ("retry_exhausted_count", "retry_exhausted"),
        "descriptor_leak": ("descriptor_leak_count", "descriptor_leak"),
        "double_completion": ("tx_double_completion", "rx_double_completion"),
        "transport_timeout": ("tx_timeouts",),
    }
    counters: dict[str, int | None] = {}
    for output, aliases in counter_aliases.items():
        values: list[int] = []
        for detail in details:
            for role in ("fixed", "rotating"):
                role_detail = detail.get(role)
                if not isinstance(role_detail, dict):
                    role_detail = detail.get(f"{role}_mailbox")
                if not isinstance(role_detail, dict):
                    continue
                values.extend(
                    int(role_detail[key])
                    for key in aliases
                    if isinstance(role_detail.get(key), (int, bool))
                )
        counters[output] = max(values, default=None)
    lane_crc = [
        int(lane.get("crc_bad", 0))
        for detail in details
        for snapshot_name in ("fixed_p10_2", "rotating_p10_2")
        if isinstance(detail.get(snapshot_name), dict)
        for lane in detail[snapshot_name].get("lanes", [])
        if isinstance(lane, dict)
    ]
    if lane_crc:
        counters["crc_bad"] = max(
            [value for value in (counters["crc_bad"], max(lane_crc)) if value is not None]
        )
    process_timeouts = [
        bool(item.get("process", {}).get("timed_out"))
        for item in stage_results
        if isinstance(item.get("process"), dict)
    ]
    if process_timeouts:
        counters["deadlock"] = max(
            int(any(process_timeouts)), int(counters.get("transport_timeout") or 0)
        )
    else:
        counters["deadlock"] = None
    counters["duty_violation"] = None if not any(
        value is not None for value in max_duty.values()
    ) else int(any(
        (max_duty[module] or 0) > 11520 or (module_hard_fault[module] or 0) != 0
        for module in module_index
    ))
    counters["continuous_high_violation"] = None if not any(
        value is not None for value in max_continuous.values()
    ) else int(any((value or 0) > 64 for value in max_continuous.values()))

    performance_windows = by_stage.get("performance", {}).get(
        "semantics", {}
    ).get("windows", [])
    performance_by_direction = {
        int(item.get("direction", 0 if "f2r" in item.get("label", "") else 1)): item
        for item in performance_windows
        if isinstance(item, dict)
    }
    formal = by_stage.get("formal_30min", {}).get("semantics", {})
    formal_windows = formal.get("formal_windows", [])
    formal_by_direction = {
        int(item.get("direction", 0 if "f2r" in item.get("label", "") else 1)): item
        for item in formal_windows
        if isinstance(item, dict)
    }
    max_masks = [
        int(detail["lane_mask"])
        for detail in details
        if isinstance(detail.get("lane_mask"), int)
    ]
    return {
        "application_goodput_bps": {
            "F_TO_R": performance_by_direction.get(0, {}).get(
                "application_goodput_bps"
            ),
            "R_TO_F": performance_by_direction.get(1, {}).get(
                "application_goodput_bps"
            ),
        },
        "formal": {
            "runtime_seconds": (
                formal.get("elapsed_ms") / 1000
                if isinstance(formal.get("elapsed_ms"), (int, float)) else None
            ),
            "committed_bytes_f_to_r": formal_by_direction.get(0, {}).get(
                "committed_bytes"
            ),
            "committed_bytes_r_to_f": formal_by_direction.get(1, {}).get(
                "committed_bytes"
            ),
        },
        "maximum_duty_cycles": max_duty,
        "maximum_continuous_high_cycles": max_continuous,
        "module_hard_fault": module_hard_fault,
        "counters": counters,
        "maximum_lane_mask_observed": (
            f"0x{max(max_masks):X}" if max_masks else None
        ),
        "direct_observation_count": len(details),
    }


def materialize_run_views(
    summary: dict[str, Any], run_root: Path, authorization: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    by_stage = {item["stage"]: item for item in summary["stages"]}
    common = common_evidence_binding(summary, run_root, authorization)
    payloads: dict[str, dict[str, Any]] = {}
    preflight = grouped_stage_payload(
        "safe_boot", ("preflight",), by_stage, run_root, common
    )
    payloads["target_identity"] = {
        **preflight,
        "test_id": "P10_3F-FULL-TARGET-IDENTITY",
        "summary_name": "target_identity",
        "expected_build_ids": {
            role: f"0x{value:08X}" for role, value in EXPECTED_BUILD.items()
        },
    }
    payloads["safe_boot"] = preflight
    payloads["power_preflight"] = {
        **preflight,
        "test_id": "P10_3F-FULL-POWER-PREFLIGHT",
        "summary_name": "power_preflight",
        "external_four_lane_power_acceptance": "OMITTED_BY_USER",
        "user_power_arrangement_attestation": True,
        "user_attestation_is_external_measurement": False,
        "internal_no_brownout_is_external_measurement": False,
    }
    for name, stages in PUBLISHED_STAGE_GROUPS.items():
        payloads[name] = grouped_stage_payload(name, stages, by_stage, run_root, common)
    payloads["staircase"] = grouped_stage_payload(
        "bounded_staircase", STAIRCASE_STAGES, by_stage, run_root, common
    )
    payloads["fault_forensics"] = grouped_stage_payload(
        "fault_forensics", EXPECTED_FAULT_STAGES, by_stage, run_root, common
    )

    run_view = {
        "target_identity": "target_identity/summary",
        "safe_boot": "safe_boot/summary",
        "power_preflight": "power_preflight/summary",
        "module_intake": "module_intake/summary",
        "raw_8x8": "raw_8x8/summary",
        "per_lane_phy": "per_lane_phy/summary",
        "two_lane_regression": "two_lane_regression/summary",
        "four_lane_raw": "four_lane_raw/summary",
        "mask_matrix": "mask_matrix/summary",
        "degraded_modes": "degraded_modes/summary",
        "arq_scheduler": "arq_scheduler/summary",
        "dma_ddr_cache": "dma_ddr_cache/summary",
        "streaming_64m": "streaming_64m/summary",
        "formal_30min": "formal_30min/summary",
        "staircase": "staircase/summary",
        "fault_forensics": "fault_forensics/summary",
    }
    for name, destination in run_view.items():
        write_summary_pair(
            run_root / destination,
            payloads[name],
            f"P10.3 {name.replace('_', ' ')}",
        )
    performance = payloads["performance"]
    windows = by_stage.get("performance", {}).get("semantics", {}).get("windows", [])
    for direction, directory in ((0, "performance_f2r"), (1, "performance_r2f")):
        selected = [
            item for item in windows
            if int(item.get("direction", 0 if "f2r" in item.get("label", "") else 1))
            == direction
        ]
        directional = {
            **performance,
            "test_id": f"P10_3F-FULL-PERFORMANCE-{'F2R' if direction == 0 else 'R2F'}",
            "direction": direction,
            "windows": selected,
            "status": "PASS" if performance["status"] == "PASS" and
            len(selected) == 1 and
            selected[0].get("application_goodput_bps", 0) >= 8_000_000 else "FAIL",
        }
        write_summary_pair(
            run_root / directory / "direction_summary",
            directional,
            f"P10.3 performance {'F to R' if direction == 0 else 'R to F'}",
        )
    return payloads


def shutdown_payload(
    summary: dict[str, Any], run_root: Path, authorization: dict[str, Any]
) -> dict[str, Any]:
    common = common_evidence_binding(summary, run_root, authorization)
    return {
        **common,
        "test_id": "P10_3F-FULL-SHUTDOWN",
        "summary_name": "shutdown",
        "status": "PASS" if summary["SHUTDOWN_FIXED"] == "PASS" and
        summary["SHUTDOWN_ROTATING"] == "PASS" else "FAIL",
        "SHUTDOWN_FIXED": summary["SHUTDOWN_FIXED"],
        "SHUTDOWN_ROTATING": summary["SHUTDOWN_ROTATING"],
        "shutdowns": summary["shutdowns"],
        "raw_root": rel(run_root / "shutdown"),
    }


def publish_generated_evidence(
    summary: dict[str, Any],
    consistency: dict[str, Any],
    payloads: dict[str, dict[str, Any]],
    shutdown: dict[str, Any],
    run_root: Path,
) -> None:
    for name in (
        "target_identity", "safe_boot", "power_preflight", "module_intake",
        "raw_8x8", "per_lane_phy", "two_lane_regression", "four_lane_raw",
        "mask_matrix", "degraded_modes", "arq_scheduler", "dma_ddr_cache",
        "streaming_64m", "performance", "formal_30min",
    ):
        write_summary_pair(
            GENERATED / f"p10_3_{name}", payloads[name],
            f"P10.3 {name.replace('_', ' ')}",
        )
    write_summary_pair(
        GENERATED / "p10_3_shutdown", shutdown, "P10.3 dual-endpoint shutdown"
    )
    write_summary_pair(
        GENERATED / "p10_3_evidence_consistency", consistency,
        "P10.3 evidence consistency",
    )
    write_summary_pair(
        GENERATED / "p10_3_final_summary", summary,
        "P10.3 stationary four-lane hardware acceptance",
    )
    write_summary_pair(
        GENERATED / "p10_3f_hardware/final/summary", summary,
        "P10.3F current-artifact hardware acceptance",
    )
    write_summary_pair(
        GENERATED / "p10_3f_hardware/staircase/summary", payloads["staircase"],
        "P10.3F bounded staircase",
    )
    write_summary_pair(
        GENERATED / "p10_3f_hardware/fault_forensics/summary",
        payloads["fault_forensics"], "P10.3F first-fault forensics",
    )
    write_json(GENERATED_FINAL, summary)


def finalize_run_evidence(
    summary: dict[str, Any], run_root: Path, authorization: dict[str, Any]
) -> tuple[str, dict[str, Any]]:
    """Materialize Goal-named evidence and verify the complete run file set."""
    status = str(summary["status"])
    write_json(run_root / "final/orchestrator_result.json", summary)
    write_summary_pair(
        run_root / "final/p10_3_final_summary", summary,
        "P10.3 stationary four-lane hardware acceptance",
    )
    payloads = materialize_run_views(summary, run_root, authorization)
    shutdown = shutdown_payload(summary, run_root, authorization)
    write_summary_pair(
        run_root / "shutdown/summary", shutdown, "P10.3 dual-endpoint shutdown"
    )
    evidence_manifest(run_root, status)
    first_errors = verify_evidence_manifest(run_root)
    consistency = {
        **common_evidence_binding(summary, run_root, authorization),
        "test_id": "P10_3F-FULL-EVIDENCE-CONSISTENCY",
        "status": "PASS" if not first_errors else "FAIL",
        "manifest": rel(run_root / "final/run_evidence_sha256_manifest.json"),
        "verified_complete_file_set": not first_errors,
        "errors": first_errors,
        "generated_at_utc": utc_now(),
    }
    write_summary_pair(
        run_root / "final/p10_3_evidence_consistency", consistency,
        "P10.3 evidence consistency",
    )
    evidence_manifest(run_root, status)
    final_errors = verify_evidence_manifest(run_root)
    if final_errors:
        status = "FAIL"
        summary["status"] = "FAIL"
        summary["errors"].extend(final_errors)
        consistency["status"] = "FAIL"
        consistency["verified_complete_file_set"] = False
        consistency["errors"] = final_errors
        write_json(run_root / "final/orchestrator_result.json", summary)
        write_summary_pair(
            run_root / "final/p10_3_final_summary", summary,
            "P10.3 stationary four-lane hardware acceptance",
        )
        write_summary_pair(
            run_root / "final/p10_3_evidence_consistency", consistency,
            "P10.3 evidence consistency",
        )
        evidence_manifest(run_root, status)
    try:
        publish_generated_evidence(summary, consistency, payloads, shutdown, run_root)
    except Exception as exc:
        status = "FAIL"
        summary["status"] = "FAIL"
        summary["errors"].append(f"generated evidence publication failed: {exc}")
        consistency["status"] = "FAIL"
        consistency["errors"].append(str(exc))
        write_json(run_root / "final/orchestrator_result.json", summary)
        write_summary_pair(
            run_root / "final/p10_3_final_summary", summary,
            "P10.3 stationary four-lane hardware acceptance",
        )
        write_summary_pair(
            run_root / "final/p10_3_evidence_consistency", consistency,
            "P10.3 evidence consistency",
        )
        evidence_manifest(run_root, status)
        write_json(GENERATED_FINAL, summary)
    return status, consistency


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

    try:
        initialize_run_root(run_root, auth)
    except Exception as exc:
        print(
            f"P10_3F_FULL_RUN_ROOT_INITIALIZATION=FAIL\nERROR={exc}",
            file=sys.stderr,
        )
        return 3
    ps7: dict[str, Path] = {}
    derived: list[dict[str, Any]] = []
    initialization_errors: list[str] = []
    try:
        for role in ("fixed", "rotating"):
            destination = run_root / "artifacts" / role / "ps7_init.tcl"
            extract_ps7_init(artifacts[f"{role}:xsa"], destination)
            ps7[role] = destination
            derived.append({
                "role": role,
                "source_xsa": metadata(artifacts[f"{role}:xsa"]),
                "derived": run_metadata(destination, run_root),
            })
    except Exception as exc:
        initialization_errors.append(f"PS7 init extraction failed: {exc}")
    write_json(run_root / "artifacts/derived_artifact_manifest.json", {
        "schema_version": 1,
        "status": "PASS" if not initialization_errors else "FAIL",
        "files": derived,
        "errors": initialization_errors,
        "generated_at_utc": utc_now(),
    })
    write_json(run_root / "artifacts/authorized_artifact_manifest.json", {
        "schema_version": 1,
        "status": "PASS" if not initialization_errors else "FAIL",
        "artifact_source_commit": record["artifact_source_commit"],
        "host_source_commit": record["host_source_commit"],
        "artifacts": record["artifacts"],
        "errors": initialization_errors,
        "generated_at_utc": utc_now(),
    })

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
    campaign_errors: list[str] = list(initialization_errors)
    hardware_actions = False
    functional_loaded = False
    active_stage: str | None = None
    active_archived = False
    try:
        if initialization_errors:
            raise RuntimeError("artifact derivation precondition failed")
        server_proc, server = start_hw_server(run_root / "raw_logs")
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server unavailable"))
        hardware_actions = True
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
            process_failed = bool(
                process.get("returncode") != 0 or process.get("timed_out")
            )
            forensic_summary = capture_and_archive(
                stage, run_root, auth, env,
                force_terminal_fault=process_failed,
            )
            forensic_results.append(forensic_summary)
            active_archived = forensic_summary.get("status") == "PASS"
            if not active_archived:
                # Do not reconfigure the FPGA and destroy a possibly frozen,
                # unarchived recorder.  The finally path first retries a forced
                # terminal abort/capture, then performs the independent dual
                # shutdown even if that retry cannot be archived.
                raise RuntimeError(f"{stage} forensic archive failed")
            after = guarded_shutdown(run_root, auth, artifacts, f"{stage}_after", env)
            shutdown_results.append(after)
            functional_loaded = after.get("status") != "PASS"
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
                retry_archive = capture_and_archive(
                    f"{active_stage}_finally_before_shutdown", run_root, auth, env,
                    force_terminal_fault=True,
                )
                forensic_results.append(retry_archive)
                active_archived = retry_archive.get("status") == "PASS"
                if not active_archived:
                    campaign_errors.append("finally forensic archive failed closed")
            except BaseException as exc:
                campaign_errors.append(f"finally forensic archive failed: {exc}")
        hardware_actions = True
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
    core_stages = STAGES[:STAGES.index("performance")]
    core_pass = all(
        next(
            (item.get("status") for item in stage_results if item.get("stage") == stage),
            None,
        ) == "PASS"
        for stage in core_stages
    )
    if all_stages and all_shutdown and not campaign_errors:
        status = "PASS"
    elif all_shutdown and core_pass:
        status = "PARTIAL"
    else:
        status = "FAIL"
    metrics = collect_campaign_metrics(stage_results)
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
        "hardware_actions_executed": hardware_actions,
        "ethernet_used": False,
        "movement": False,
        "rotation": False,
        "realignment": False,
        "rewiring": False,
        "maximum_lane_mask": 15,
        "internal_stream_object_bytes": INTERNAL_OBJECT_BYTES,
        "maximum_staircase_level_bytes": MAX_STAIRCASE_LEVEL_BYTES,
        "maximum_long_test_command_bytes": MAX_AGGREGATE_COMMAND_BYTES,
        "maximum_board_autonomous_aggregate_command_bytes": (
            MAX_AGGREGATE_COMMAND_BYTES
        ),
        "maximum_functional_diagnostic_object_bytes": MAX_FUNCTIONAL_DIAGNOSTIC_BYTES,
        "maximum_single_formal_run_seconds": 1800,
        "manual_instrumentation": "OMITTED_BY_USER",
        "old_hardware_pass_inherited": False,
        "current_run_hardware_authorization": False,
        "artifacts": record["artifacts"],
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}",
        },
        "module_binding": MODULE_BINDING,
        "active_modules": list(MODULE_BINDING),
        "historical_failed_modules_active": False,
        "stages": stage_results,
        "forensics": forensic_results,
        "shutdowns": shutdown_results,
        "SHUTDOWN_FIXED": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdown_results
        ) else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdown_results
        ) else "FAIL",
        "external_four_lane_power_acceptance": "OMITTED_BY_USER",
        "external_tfdu_duty": "OMITTED_BY_USER",
        "metrics": metrics,
        "errors": campaign_errors,
        "generated_at_utc": utc_now(),
    }
    status, consistency = finalize_run_evidence(summary, run_root, record)
    consumed = dict(record)
    consumed.update(
        {
            "status": f"CONSUMED_AFTER_P10_3F_FULL_{status}",
            "current_run_hardware_authorization": False,
            "consumed": True,
            "consumed_at_utc": utc_now(),
            "result": rel(run_root / "final/orchestrator_result.json"),
        }
    )
    write_json(AUTH, consumed)
    write_summary_pair(GENERATED / "p10_3_authorization", {
        "schema_version": 1,
        "test_id": "P10_3F-FULL-HARDWARE-AUTHORIZATION",
        "status": consumed["status"],
        "run_id": args.run_id,
        "authorization": rel(AUTH),
        "immutable_authorization": rel(
            run_root / "authorization/immutable_authorization.json"
        ),
        "current_run_hardware_authorization": False,
        "consumed": True,
        "result": consumed["result"],
        "evidence_consistency": consistency["status"],
    }, "P10.3 current-run hardware authorization")
    print(f"P10_3F_FULL_HARDWARE={status}")
    print(f"P10_3F_FULL_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
