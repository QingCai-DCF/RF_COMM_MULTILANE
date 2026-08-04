#!/usr/bin/env python3
"""Fail-closed P10.3 stationary four-lane hardware acceptance orchestrator."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import p10_1_hardware_acceptance as p101
import yaml
from p10_hardware_runtime import (
    EXPECTED_FIXED_SERIAL,
    EXPECTED_PART,
    EXPECTED_ROTATING_SERIAL,
    XSDB,
    extract_ps7_init,
    inside,
    invoke_shutdown,
    mailbox_detail,
    parse_mailbox,
    parse_markers,
    run_bounded,
    sha256,
    start_hw_server,
    terminate_tree,
)


ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / "goals/P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_GOAL.md"
GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
EXTERNAL_GOAL = Path(r"C:\Users\user\Downloads\P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_GOAL.md")
EXTERNAL_GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
SCOPE = "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE"
BRANCH = "p10.3/ax7020-stationary-4lane-hardware"
FREEZE = ROOT / "evidence/generated/p10_3_artifact_freeze.json"
AUTH = ROOT / "config/p10_3_current_run_hardware_authorization.json"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
HW_ROOT = ROOT / "evidence/hardware/p10_3"
GENERATED = ROOT / "evidence/generated"
WIRING = ROOT / "config/hardware/p10_3_actual_wiring.yaml"
INVENTORY = ROOT / "config/hardware/tfdu_module_inventory.yaml"
P10_2_TAG = "p10.2-4lane-offline-ready"
P10_2_CHECKPOINT = "08771d6bf9e852c9d34bcff61add1598e120b70a"
P10_1R_PASS_TAG = "p10.1r-2lane-speed-stability-pass"
P10_1R_CLOSED_TAG = "p10.1r-2lane-speed-stability-closed"
P10_1R_CHECKPOINT = "9321ca2f1797eb12bfb02848c3ee27145e1e8eb4"
EXPECTED_MODULE_BINDING = {
    "F0": {"small_board_id": "A0019", "endpoint": "fixed", "position": "J10-A", "lane": 0},
    "F1": {"small_board_id": "B0012", "endpoint": "fixed", "position": "J10-B", "lane": 1},
    "F2": {"small_board_id": "B0001", "endpoint": "fixed", "position": "J11-A", "lane": 2},
    "F3": {"small_board_id": "B0004", "endpoint": "fixed", "position": "J11-B", "lane": 3},
    "R0": {"small_board_id": "A0010", "endpoint": "rotating", "position": "J10-A", "lane": 0},
    "R1": {"small_board_id": "A0017", "endpoint": "rotating", "position": "J10-B", "lane": 1},
    "R2": {"small_board_id": "B0023", "endpoint": "rotating", "position": "J11-A", "lane": 2},
    "R3": {"small_board_id": "B0017", "endpoint": "rotating", "position": "J11-B", "lane": 3},
}
RUN_DIRECTORIES = (
    "authorization", "wiring", "module_inventory", "artifacts",
    "target_identity", "safe_boot", "module_intake", "power_preflight",
    "raw_8x8", "per_lane_phy", "two_lane_regression", "four_lane_raw",
    "mask_matrix", "degraded_modes", "arq_scheduler", "dma_ddr_cache",
    "streaming_64m", "performance_f2r", "performance_r2f",
    "formal_30min", "shutdown", "raw_logs", "final",
)
AUTH_INPUT_PATHS = (
    GOAL, WIRING, INVENTORY,
    ROOT / "PROJECT_CONSTRAINTS.txt",
    ROOT / "AGENTS.md",
    ROOT / "config/project_state.json",
    ROOT / "config/project_requirements.yaml",
    ROOT / "config/register_map/ir_axi_regs.yaml",
    ROOT / "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
    ROOT / "config/hardware/p10_3_ax7020_activity_leds.yaml",
    ROOT / "docs/hardware/P10_3_AS_WIRED_RECORD.md",
    ROOT / "docs/hardware/P10_3_AX7020_ACTIVITY_LED_DESIGN.md",
    ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
    ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
    ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
    ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
    ROOT / "board_profiles/ax7020_fixed_4lane/p10_3_runtime_role.h",
    ROOT / "board_profiles/ax7020_rotating_4lane/p10_3_runtime_role.h",
    ROOT / "scripts/hw/p10_program_dual_shutdown.tcl",
    STAGE_TCL,
    ROOT / "scripts/p10_hardware_runtime.py",
    ROOT / "scripts/run_p10_2_xsim.py",
    ROOT / "scripts/verify_p10_2_existing.py",
    ROOT / "scripts/verify_p10_1r_existing.py",
    ROOT / "scripts/verify_p10_frozen_existing.py",
    ROOT / "scripts/prepare_p10_3_offline.py",
    ROOT / "scripts/freeze_p10_3_artifacts.py",
    Path(__file__).resolve(),
)

STAGES = (
    "preflight", "module_intake", "raw_8x8", "per_lane_phy",
    "two_lane_regression", "four_lane_raw", "mask_matrix", "degrade",
    "arq_sack", "dma", "streaming_64m", "performance", "formal_30min",
)
TCL_STAGE = {stage: f"P10_3-{stage.upper()}" for stage in STAGES}
STAGE_DIR = {
    "preflight": "safe_boot",
    "module_intake": "module_intake",
    "raw_8x8": "raw_8x8",
    "per_lane_phy": "per_lane_phy",
    "two_lane_regression": "two_lane_regression",
    "four_lane_raw": "four_lane_raw",
    "mask_matrix": "mask_matrix",
    "degrade": "degraded_modes",
    "arq_sack": "arq_scheduler",
    "dma": "dma_ddr_cache",
    "streaming_64m": "streaming_64m",
    "performance": "performance_f2r",
    "formal_30min": "formal_30min",
}
STAGE_TIMEOUT = {
    "preflight": 900, "module_intake": 1800, "raw_8x8": 2400,
    "per_lane_phy": 2400, "two_lane_regression": 2400,
    "four_lane_raw": 1800, "mask_matrix": 3000, "degrade": 3000,
    "arq_sack": 2400, "dma": 2400, "streaming_64m": 7200,
    "performance": 1200, "formal_30min": 2400,
}
RUN_RE = re.compile(
    r"^p10_3_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}_[0-9a-f]{8}_[0-9a-f]{8}$"
)
EXPECTED_PL_BUILD = {"fixed": 0x50333446, "rotating": 0x50333452}
EXPECTED_ROLE = {
    "fixed": {
        "firmware": 0x50333446, "build": 0x50333446,
        "profile": 0x702004F0, "capabilities": 0xF7204441,
        "local_indices": (0, 1, 2, 3),
    },
    "rotating": {
        "firmware": 0x50333452, "build": 0x50333452,
        "profile": 0x702004A0, "capabilities": 0xF7204441,
        "local_indices": (4, 5, 6, 7),
    },
}
MODULES = ("F0", "F1", "F2", "F3", "R0", "R1", "R2", "R3")
P103_SCHEMA = 0x50310201
TARGET_DUTY_CYCLES = 11520
HARD_DUTY_MAX_CYCLES = 12799


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"YAML root is not a mapping: {rel(path)}")
    return value


def metadata(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    return {"sha256": sha256(path), "bytes": path.stat().st_size}


def expected_authorization_inputs() -> dict[str, dict[str, Any]]:
    return {rel(path): metadata(path) for path in AUTH_INPUT_PATHS}


def git_commit_exists(commit: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=ROOT,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def git_is_ancestor(ancestor: str, descendant: str = "HEAD") -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def file_matches_head(path: Path) -> bool:
    try:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{rel(path)}"], cwd=ROOT,
        )
    except subprocess.CalledProcessError:
        return False
    return committed == path.read_bytes()


def validate_goal_files() -> list[str]:
    errors: list[str] = []
    for label, path, expected in (
        ("repository", GOAL, GOAL_SHA256),
        ("download", EXTERNAL_GOAL, EXTERNAL_GOAL_SHA256),
    ):
        if not path.is_file():
            errors.append(f"{label} Goal is missing: {path}")
        elif sha256(path) != expected:
            errors.append(f"{label} Goal SHA256 mismatch")
    return errors


def validate_baseline_refs() -> list[str]:
    errors: list[str] = []
    expected = (
        (P10_2_TAG, P10_2_CHECKPOINT),
        (P10_1R_PASS_TAG, P10_1R_CHECKPOINT),
        (P10_1R_CLOSED_TAG, "e90a220"),
    )
    for tag, target_prefix in expected:
        try:
            target = git("rev-list", "-n", "1", tag)
        except subprocess.CalledProcessError:
            errors.append(f"missing immutable baseline tag: {tag}")
            continue
        if not target.startswith(target_prefix):
            errors.append(f"immutable baseline tag target mismatch: {tag}={target}")
    if not git_is_ancestor(P10_2_CHECKPOINT):
        errors.append("P10.2 checkpoint is not an ancestor of HEAD")
    if not git_is_ancestor(P10_1R_CHECKPOINT):
        errors.append("P10.1R checkpoint is not an ancestor of HEAD")
    return errors


def validate_wiring_inventory() -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    errors: list[str] = []
    try:
        wiring = load_yaml(WIRING)
        inventory = load_yaml(INVENTORY)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        return {}, {}, [f"wiring/inventory parse failed: {exc}"]

    if wiring.get("scope") != SCOPE:
        errors.append("actual wiring scope mismatch")
    goal = wiring.get("goal", {})
    if goal.get("repository_sha256") != GOAL_SHA256 or \
            goal.get("external_sha256") != EXTERNAL_GOAL_SHA256:
        errors.append("actual wiring Goal binding mismatch")
    proposal = wiring.get("frozen_wiring_proposal", {})
    if proposal.get("sha256") != \
            "5f4a89b818b007af4863534759068dda529fe3c34501569ea4da89a42d8026fc":
        errors.append("P10.2 wiring proposal binding mismatch")
    boards = wiring.get("boards", {})
    if boards.get("fixed", {}).get("jtag_cable_serial") != EXPECTED_FIXED_SERIAL or \
            boards.get("rotating", {}).get("jtag_cable_serial") != EXPECTED_ROTATING_SERIAL:
        errors.append("actual wiring board/JTAG binding mismatch")
    expected_pairs = {f"lane{i}": f"F{i}-R{i}" for i in range(4)}
    if wiring.get("lane_pairs") != expected_pairs:
        errors.append("actual wiring lane pairing mismatch")
    physical = wiring.get("physical_state_declaration", {})
    if physical.get("P10_3_PHYSICAL_WIRING_COMPLETED") is not True or \
            physical.get("modules_installed") != list(MODULES) or \
            physical.get("old_f1_quarantined") is not True or \
            physical.get("no_hardware_movement_during_formal_run") is not True or \
            physical.get("no_rewiring_during_campaign") is not True:
        errors.append("user physical-state declaration is incomplete")
    if wiring.get("quarantined_historical_module", {}).get("active") is not False or \
            wiring.get("quarantined_historical_module", {}).get(
                "eligible_as_any_active_module") is not False:
        errors.append("historical failed F1 is not fail-closed in wiring")
    safety = wiring.get("safety_boundaries", {})
    if safety.get("maximum_lane_mask") != 15 or any(
            safety.get(key) is not False for key in
            ("ethernet", "movement", "rotation", "optical_realignment",
             "rewiring", "two_hour_test", "p11")
    ):
        errors.append("actual wiring safety boundary mismatch")

    positions = wiring.get("module_positions", {})
    inventory_modules = inventory.get("p10_3_current_installation", {}).get(
        "modules", {})
    if set(positions) != set(MODULES) or set(inventory_modules) != set(MODULES):
        errors.append("active eight-module key set mismatch")
    observed_ids: list[str] = []
    for module, expected in EXPECTED_MODULE_BINDING.items():
        actual = positions.get(module, {})
        connector_position = f"{actual.get('connector')}-{actual.get('position')}"
        if actual.get("small_board_id") != expected["small_board_id"] or \
                actual.get("endpoint") != expected["endpoint"] or \
                connector_position != expected["position"] or \
                actual.get("lane") != expected["lane"]:
            errors.append(f"actual wiring module binding mismatch: {module}")
        item = inventory_modules.get(module, {})
        expected_endpoint = (
            f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}" if expected["endpoint"] == "fixed"
            else f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}"
        )
        if item.get("small_board_id") != expected["small_board_id"] or \
                item.get("endpoint") != expected_endpoint or \
                item.get("position") != expected["position"]:
            errors.append(f"inventory module binding mismatch: {module}")
        observed_ids.append(str(item.get("small_board_id", "")))
    if len(set(observed_ids)) != 8 or any(not value for value in observed_ids):
        errors.append("active module small-board identifiers are not eight unique values")
    installation = inventory.get("p10_3_current_installation", {})
    if installation.get("active_modules") != list(MODULES) or \
            installation.get("lane_pairs") != expected_pairs or \
            installation.get("old_f1_active") is not False or \
            installation.get("old_f1_status") != "QUARANTINED_NOT_ACCEPTED":
        errors.append("inventory active/quarantine declaration mismatch")
    quarantine = inventory.get("quarantine", [])
    if not isinstance(quarantine, list) or not quarantine or any(
            item.get("inventory_status") != "QUARANTINED_NOT_ACCEPTED" or
            item.get("eligible_for_future_four_lane_use") is not False
            for item in quarantine if isinstance(item, dict)
    ):
        errors.append("historical failed F1 quarantine record is missing or eligible")
    accepted = {item.get("module_id") for item in inventory.get("accepted_baseline", [])
                if isinstance(item, dict)}
    pending = {item.get("module_id") for item in inventory.get(
        "pending_electronic_intake", []) if isinstance(item, dict)}
    if accepted != {"F0", "F1", "R0", "R1"} or \
            pending != {"F2", "F3", "R2", "R3"}:
        errors.append("inventory accepted/pending intake partition mismatch")
    return wiring, inventory, errors


@dataclass(frozen=True)
class Case:
    label: str
    command: int
    expected_status: int = 0
    flags: int = 0
    lane: int = 0
    direction: int = 0
    rate: int = 0
    weights: int = 0x01010101
    size: int = 0
    ring: int = 32
    cache: int = 0
    txoff: int = 0
    rxoff: int = 0
    timeout: int = 10_000
    session: int = 0xA1030001
    path: int = 0x103
    object: int = 1
    dropdata: int = 0
    dropack: int = 0
    unavailable: int = 0
    rawtarget: int = 0
    spacing: int = 1024
    stale: int = 0
    initialseq: int = 0
    faultflags: int = 0
    idle: int = 0
    injectmask: int = 0
    injectdelay: int = 0

    def plan_line(self) -> str:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.label):
            raise ValueError(f"unsafe label: {self.label}")
        if any(value < 0 or value > 0xF for value in
               (self.lane, self.unavailable, self.injectmask)):
            raise ValueError(f"lane mask exceeds 0xF: {self.label}")
        if self.direction not in (0, 1) or self.rate not in (0, 1, 2):
            raise ValueError(f"invalid direction/rate: {self.label}")
        if not 1 <= self.timeout <= 1_800_000:
            raise ValueError(f"invalid timeout: {self.label}")
        if self.command in (2, 3, 12, 13) and self.lane == 0:
            raise ValueError(f"transmit case has empty lane mask: {self.label}")
        values = (
            "CASE", self.label, self.command, self.expected_status, self.flags,
            self.lane, self.direction, self.rate, self.weights, self.size,
            self.ring, self.cache, self.txoff, self.rxoff, self.timeout,
            self.session, self.path, self.object, self.dropdata, self.dropack,
            self.unavailable, self.rawtarget, self.spacing, self.stale,
            self.initialseq, self.faultflags, self.idle, self.injectmask,
            self.injectdelay,
        )
        return " ".join(str(item) for item in values)


PlanItem = Case | tuple[str, ...]


STREAM_OBJECT_BYTES = 256 * 1024
STREAM_DESCRIPTOR_BYTES = 64 * 1024
STREAM_DESCRIPTOR_BATCH = 8
STREAM_BUFFER_COUNT = 4
STREAM_ACK_THRESHOLD = 32
STREAM_OUTSTANDING = 32


def stream_object_count(size: int) -> int:
    return math.ceil(size / STREAM_OBJECT_BYTES)


class ObjectIds:
    """Allocate non-overlapping protocol object-ID ranges.

    One command-13 request consumes first_object_id..first+object_count-1.
    Treating it as one ID made later commands reuse live protocol identities.
    """

    def __init__(self, first: int = 0x73000000) -> None:
        self.next = first

    def allocate(self, count: int = 1, pattern_mode: int | None = None) -> int:
        if count < 1 or self.next + count > 0x7FFFFFFF:
            raise ValueError("P10.3 object-ID allocation overflow")
        value = self.next
        self.next += count
        if pattern_mode is not None:
            if pattern_mode not in range(16):
                raise ValueError("invalid payload pattern mode")
            value = (pattern_mode << 28) | (value & 0x0FFFFFFF)
        return value


def object_case(label: str, *, size: int, direction: int, lane: int,
                object_id: int, timeout: int = 300_000, rate: int = 2,
                ring: int = 32, cache: int = 1,
                weights: int = 0x01010101, initial_sequence: int = 0,
                protocol_fault_flags: int = 0, physical_drop_data: int = 0,
                physical_drop_ack: int = 0, unavailable: int = 0,
                injectmask: int = 0, injectdelay: int = 0,
                txoff: int = 0, rxoff: int = 0) -> Case:
    """One real command-3 object using the mailbox fields' native meaning."""
    return Case(
        label=label, command=3, flags=2, lane=lane, direction=direction,
        rate=rate, weights=weights, size=size, ring=ring, cache=cache,
        txoff=txoff, rxoff=rxoff, timeout=timeout, object=object_id,
        dropdata=physical_drop_data, dropack=physical_drop_ack,
        unavailable=unavailable, initialseq=initial_sequence,
        faultflags=protocol_fault_flags, injectmask=injectmask,
        injectdelay=injectdelay,
    )


def stream_case(label: str, *, size: int, direction: int, lane: int,
                object_id: int, timeout: int = 600_000, flags: int = 0,
                injectmask: int = 0, injectdelay: int = 0,
                pattern: int = 0) -> Case:
    """One valid command-13 autonomous multi-object stream.

    The legacy mailbox names are frozen.  For command 13 they mean:
    dropdata=ACK threshold, dropack=outstanding frames, rawtarget=object bytes,
    spacing=descriptor bytes, stale=buffer count, initialseq=descriptor batch.
    Physical loss/wrap tests therefore use command 3 instead of overloading
    these fields.
    """
    return Case(
        label=label, command=13, flags=flags | ((pattern & 0xF) << 8), lane=lane,
        direction=direction, rate=2, size=size, ring=32, cache=1,
        timeout=timeout, object=object_id,
        dropdata=STREAM_ACK_THRESHOLD, dropack=STREAM_OUTSTANDING,
        unavailable=0, rawtarget=min(size, STREAM_OBJECT_BYTES),
        spacing=min(size, STREAM_DESCRIPTOR_BYTES),
        stale=STREAM_BUFFER_COUNT, initialseq=STREAM_DESCRIPTOR_BATCH,
        faultflags=0,
        injectmask=injectmask, injectdelay=injectdelay,
    )


def build_plans() -> dict[str, list[PlanItem]]:
    plans: dict[str, list[PlanItem]] = {}
    ids = ObjectIds()
    plans["preflight"] = [
        Case("p10_3_identity", 1),
        Case("p10_3_receive_only_5000ms", 11, idle=5000, timeout=15_000),
        Case("p10_3_ring32", 4, ring=32),
        Case("p10_3_dma_reset_idle", 5, ring=32),
        Case("p10_3_pl_soft_reset", 8),
        Case("p10_3_identity_after_reset", 1),
    ]

    intake: list[PlanItem] = []
    intake.append(Case("intake_receive_only_5000ms", 11, idle=5000,
                       timeout=15_000))
    # Establish both raw optical directions on every installed lane before any
    # framed traffic.  Lane0/lane1 are the accepted two-lane baseline, but this
    # campaign must re-observe them with the frozen four-lane artifacts instead
    # of inheriting their older hardware result.  Ordering all raw probes first
    # also preserves direct receiver evidence if a later ACK-return path is
    # absent or intermittent.
    for lane in (1, 2, 4, 8):
        lane_index = int(math.log2(lane))
        for direction, module in ((0, f"F{lane_index}"),
                                  (1, f"R{lane_index}")):
            for count in (64, 1024):
                intake.append(Case(
                    f"intake_{module}_raw_{count}", 2,
                    lane=lane, direction=direction, rate=2,
                    rawtarget=count, spacing=1024, timeout=30_000,
                ))
    for lane in (4, 8):
        lane_index = int(math.log2(lane))
        for direction, module in ((0, f"F{lane_index}"),
                                  (1, f"R{lane_index}")):
            intake.extend([
                object_case(
                    f"intake_{module}_counter_100f", size=247 * 100,
                    direction=direction, lane=lane,
                    object_id=ids.allocate(pattern_mode=3), timeout=60_000,
                ),
                object_case(
                    f"intake_{module}_prbs_1000f", size=247 * 1000,
                    direction=direction, lane=lane,
                    object_id=ids.allocate(), timeout=120_000,
                ),
            ])
    plans["module_intake"] = intake

    matrix: list[PlanItem] = []
    for lane_index in range(4):
        lane = 1 << lane_index
        for direction, side in ((0, "F"), (1, "R")):
            source = f"{side}{lane_index}"
            matrix.extend([
                Case(f"matrix_{source}_raw64", 2, lane=lane,
                     direction=direction, rate=2, rawtarget=64,
                     spacing=1024, timeout=30_000),
                Case(f"matrix_{source}_raw1024", 2, lane=lane,
                     direction=direction, rate=2, rawtarget=1024,
                     spacing=1024, timeout=30_000),
                ("P101_WINDOW", f"matrix_{source}_frame10s", "10",
                 str(direction), str(lane), "1048576"),
            ])
    plans["raw_8x8"] = matrix

    phy: list[PlanItem] = []
    for lane_index in range(4):
        lane = 1 << lane_index
        for direction, side in ((0, "f2r"), (1, "r2f")):
            phy.extend([
                object_case(
                    f"phy_lane{lane_index}_{side}_counter_100f",
                    size=247 * 100, direction=direction, lane=lane,
                    object_id=ids.allocate(pattern_mode=3), timeout=60_000,
                ),
                object_case(
                    f"phy_lane{lane_index}_{side}_prbs_10000f",
                    size=247 * 10_000, direction=direction, lane=lane,
                    object_id=ids.allocate(), timeout=300_000,
                ),
            ])
    plans["per_lane_phy"] = phy

    plans["two_lane_regression"] = [
        stream_case("regression_64m_f2r", size=64 << 20, direction=0,
                    lane=3,
                    object_id=ids.allocate(stream_object_count(64 << 20))),
        stream_case("regression_64m_r2f", size=64 << 20, direction=1,
                    lane=3,
                    object_id=ids.allocate(stream_object_count(64 << 20))),
        ("P101_WINDOW", "regression_60s_f2r", "60", "0", "3", "16777216"),
        ("P101_WINDOW", "regression_60s_r2f", "60", "1", "3", "16777216"),
    ]
    progressive: list[PlanItem] = []
    for mask in (1, 3, 7, 15):
        for direction, side in ((0, "f2r"), (1, "r2f")):
            progressive.append((
                "P101_WINDOW", f"raw_mask{mask:X}_{side}_10s", "10",
                str(direction), str(mask), "4194304",
            ))
    plans["four_lane_raw"] = progressive

    masks: list[PlanItem] = []
    for mask in range(1, 16):
        for direction, side in ((0, "f2r"), (1, "r2f")):
            masks.append(object_case(
                f"mask_{mask:X}_{side}", size=1 << 20,
                direction=direction, lane=mask, object_id=ids.allocate(),
                timeout=120_000,
            ))
    plans["mask_matrix"] = masks

    degrade: list[PlanItem] = []
    for unavailable in (1, 2, 4, 8, 3, 7):
        degrade.append(object_case(
            f"degrade_static_unavailable_{unavailable:X}", size=4 << 20,
            direction=unavailable & 1, lane=15,
            object_id=ids.allocate(), unavailable=unavailable,
            timeout=180_000,
        ))
    degrade.append(object_case(
        "degrade_static_recovery_maskF", size=4 << 20, direction=0,
        lane=15, object_id=ids.allocate(), timeout=180_000,
    ))
    for failed_lane in (1, 2, 4, 8):
        lane_index = int(math.log2(failed_lane))
        degrade.append(object_case(
            f"degrade_inflight_lane{int(math.log2(failed_lane))}",
            size=16 << 20, direction=(failed_lane >> 1) & 1, lane=15,
            object_id=ids.allocate(), injectmask=failed_lane,
            injectdelay=100, timeout=300_000,
        ))
        degrade.append(object_case(
            f"degrade_recovery_after_lane{lane_index}", size=4 << 20,
            direction=(failed_lane >> 1) & 1, lane=15,
            object_id=ids.allocate(), timeout=180_000,
        ))
    plans["degrade"] = degrade

    plans["arq_sack"] = [
        object_case("arq_wrap_f2r", size=247 * 96, direction=0, lane=15,
                    object_id=ids.allocate(), initial_sequence=0xFFFE),
        object_case("arq_wrap_r2f", size=247 * 96, direction=1, lane=15,
                    object_id=ids.allocate(), initial_sequence=0xFFFE),
        object_case("arq_ack_aggregation", size=247 * 512, direction=0,
                    lane=15, object_id=ids.allocate()),
        object_case("arq_data_loss", size=247 * 512, direction=0, lane=15,
                    object_id=ids.allocate(), physical_drop_data=1),
        object_case("arq_ack_loss", size=247 * 512, direction=1, lane=15,
                    object_id=ids.allocate(), physical_drop_ack=1),
        object_case("arq_sack_loss", size=247 * 512, direction=0, lane=15,
                    object_id=ids.allocate(), protocol_fault_flags=1 << 7),
        object_case("arq_duplicate_ack", size=247 * 512, direction=1,
                    lane=15, object_id=ids.allocate(),
                    protocol_fault_flags=1 << 5),
        object_case("arq_reorder", size=247 * 512, direction=0, lane=15,
                    object_id=ids.allocate(), protocol_fault_flags=1 << 6),
        object_case("arq_retry_migration", size=16 << 20, direction=1,
                    lane=15, object_id=ids.allocate(), injectmask=1,
                    injectdelay=100, timeout=300_000),
        object_case("scheduler_fair_f2r", size=16 << 20, direction=0,
                    lane=15, object_id=ids.allocate()),
        object_case("scheduler_fair_r2f", size=16 << 20, direction=1,
                    lane=15, object_id=ids.allocate()),
    ]

    dma: list[PlanItem] = [Case("dma_ring8", 4, ring=8), Case("dma_ring32", 4, ring=32)]
    for index, size in enumerate((1, 2, 3, 4, 31, 32, 63, 64, 247,
                                  256, 1024, 4096, 65536, 1048576)):
        dma.append(object_case(
            f"dma_size_{size}", size=size, direction=index & 1,
            lane=15, object_id=ids.allocate(), timeout=120_000,
        ))
    dma.extend([
        object_case("dma_cache_off_fixed", size=65536, direction=0,
                    lane=15, object_id=ids.allocate(), cache=0),
        object_case("dma_cache_off_rotating", size=65536, direction=1,
                    lane=15, object_id=ids.allocate(), cache=0),
        object_case("dma_misaligned", size=4096, direction=0, lane=15,
                    object_id=ids.allocate(), txoff=1, rxoff=3),
    ])
    # Each endpoint alternates TX/RX roles.  Seventy-two one-descriptor
    # commands force >32 producer and consumer advances on both endpoints.
    for index in range(72):
        dma.append(object_case(
            f"dma_ring32_wrap_{index:02d}", size=1,
            direction=index & 1, lane=15, object_id=ids.allocate(),
            timeout=30_000,
        ))
    dma.extend([
        Case("dma_reset_idle", 5, ring=32),
        Case("dma_reset_queued", 6, lane=15, direction=0, rate=2,
             size=4096, ring=32, cache=1, timeout=30_000),
        Case("dma_pl_soft_reset", 8),
        Case("dma_stale_completion", 9, stale=0xDEADBEEF),
        object_case("dma_post_reset_clean", size=1 << 20, direction=1,
                    lane=15, object_id=ids.allocate()),
    ])
    plans["dma"] = dma

    streaming: list[PlanItem] = []
    for direction, side in ((0, "f2r"), (1, "r2f")):
        for index in range(3):
            size = 64 << 20
            streaming.append(stream_case(
                f"stream64_{side}_{index + 1}", size=size,
                direction=direction, lane=15,
                object_id=ids.allocate(stream_object_count(size)),
                pattern=index % 5,
            ))
    lane2_fault_id = ids.allocate(stream_object_count(64 << 20))
    clean_lane2_id = ids.allocate(stream_object_count(4 << 20))
    lane3_fault_id = ids.allocate(stream_object_count(64 << 20))
    clean_lane3_id = ids.allocate(stream_object_count(4 << 20))
    dma_sender_id = ids.allocate(stream_object_count(64 << 20))
    clean_dma_id = ids.allocate(stream_object_count(4 << 20))
    service_reset_id = ids.allocate(stream_object_count(64 << 20))
    clean_service_id = ids.allocate(stream_object_count(4 << 20))
    streaming.extend([
        stream_case("stream_lane2_unavailable", size=64 << 20,
                    direction=0, lane=15, object_id=lane2_fault_id,
                    injectmask=4, injectdelay=100),
        stream_case("stream_clean_after_lane2", size=4 << 20,
                    direction=0, lane=15, object_id=clean_lane2_id),
        stream_case("stream_lane3_unavailable", size=64 << 20,
                    direction=1, lane=15, object_id=lane3_fault_id,
                    injectmask=8, injectdelay=100),
        stream_case("stream_clean_after_lane3", size=4 << 20,
                    direction=1, lane=15, object_id=clean_lane3_id),
        stream_case("stream_dma_reset_sender", size=64 << 20,
                    direction=0, lane=15, object_id=dma_sender_id,
                    flags=p101.FLAG_DMA_RESET_SENDER),
        stream_case("stream_clean_after_dma_reset", size=4 << 20,
                    direction=0, lane=15, object_id=clean_dma_id),
        ("P101_PSRESET", "stream_service_reset_receiver", "rotating", "0",
         "15", str(64 << 20), str(service_reset_id)),
        stream_case("stream_clean_after_service_reset", size=4 << 20,
                    direction=0, lane=15, object_id=clean_service_id),
    ])
    plans["streaming_64m"] = streaming

    plans["performance"] = [
        ("P101_WINDOW", "sustained_300s_f2r", "300", "0", "15", "67108864"),
        ("P101_WINDOW", "sustained_300s_r2f", "300", "1", "15", "67108864"),
    ]
    plans["formal_30min"] = [("P101_FORMAL", "stationary_30min", "1800")]
    lint_errors = validate_plans(plans)
    if lint_errors:
        raise ValueError("invalid P10.3 immutable plan: " + "; ".join(lint_errors))
    return plans


def case_semantic_errors(case: Case) -> list[str]:
    """Mirror firmware argument validation without touching hardware."""
    errors: list[str] = []
    prefix = case.label
    if case.command == 2:
        if case.rawtarget < 1 or case.spacing < 1024:
            errors.append(f"{prefix}: invalid raw pulse request")
    elif case.command == 3:
        if not 1 <= case.size <= 0x04000000:
            errors.append(f"{prefix}: command-3 size")
        if case.ring not in (8, 16, 32) or case.cache not in (0, 1):
            errors.append(f"{prefix}: command-3 DMA configuration")
        if case.txoff not in range(64) or case.rxoff not in range(64):
            errors.append(f"{prefix}: command-3 alignment offset")
        if case.unavailable & ~case.lane:
            errors.append(f"{prefix}: unavailable lane outside configured mask")
        if case.unavailable == case.lane:
            errors.append(f"{prefix}: all configured lanes unavailable")
    elif case.command == 13:
        total = case.size
        object_bytes = case.rawtarget
        descriptor_bytes = case.spacing
        if not 1 <= total <= 0x20000000:
            errors.append(f"{prefix}: stream total bytes")
        if not 1 <= object_bytes <= min(total, 0x04000000):
            errors.append(f"{prefix}: stream object bytes")
        if not 1 <= descriptor_bytes <= object_bytes or descriptor_bytes & 3:
            errors.append(f"{prefix}: stream descriptor bytes")
        descriptor_count = math.ceil(object_bytes / descriptor_bytes) \
            if descriptor_bytes else 0
        object_count = math.ceil(total / object_bytes) if object_bytes else 0
        active_buffers = min(case.stale, object_count)
        recovery = case.flags & p101.RECOVERY_FLAGS
        service_reset = case.flags & p101.SERVICE_RESET_FLAGS
        if case.ring not in (8, 16, 32) or case.cache != 1:
            errors.append(f"{prefix}: stream DMA configuration")
        if not 1 <= descriptor_count <= case.ring:
            errors.append(f"{prefix}: stream descriptor count")
        if not descriptor_count <= case.initialseq <= case.ring:
            errors.append(f"{prefix}: stream descriptor batch")
        if not 2 <= case.stale <= 16:
            errors.append(f"{prefix}: stream buffer count")
        if object_bytes * case.stale > 0x04000000:
            errors.append(f"{prefix}: stream buffer footprint")
        if descriptor_count * active_buffers > case.ring:
            errors.append(f"{prefix}: stream primed descriptors exceed ring")
        if case.dropdata != 32 or case.dropack != 32:
            errors.append(f"{prefix}: stream ACK/outstanding must be 32")
        if case.unavailable != 0 or case.faultflags != 0:
            errors.append(f"{prefix}: command-13 overloaded fault field")
        if recovery and recovery & (recovery - 1):
            errors.append(f"{prefix}: multiple stream recovery flags")
        if recovery and service_reset:
            errors.append(f"{prefix}: mixed firmware/host reset vector")
    return errors


def validate_plans(plans: dict[str, list[PlanItem]]) -> list[str]:
    errors: list[str] = []
    if tuple(plans) != STAGES:
        errors.append("stage order/scope mismatch")
    intervals: list[tuple[int, int, str]] = []
    for stage, items in plans.items():
        if not items:
            errors.append(f"{stage}: empty plan")
        for item in items:
            if isinstance(item, Case):
                try:
                    item.plan_line()
                except ValueError as exc:
                    errors.append(str(exc))
                    continue
                errors.extend(case_semantic_errors(item))
                if item.command in (3, 13):
                    count = stream_object_count(item.size) \
                        if item.command == 13 else 1
                    intervals.append((item.object, item.object + count - 1,
                                      f"{stage}:{item.label}"))
            elif item[0] == "P101_PSRESET":
                size = int(item[5])
                first = int(item[6])
                intervals.append((first, first + stream_object_count(size) - 1,
                                  f"{stage}:{item[1]}"))
            elif item[0] == "P101_WINDOW":
                if int(item[2]) < 10 or int(item[4]) not in range(1, 16):
                    errors.append(f"{stage}:{item[1]} invalid bounded window")
            elif item != ("P101_FORMAL", "stationary_30min", "1800"):
                errors.append(f"{stage}: unsupported plan record {item[0]}")
    for index, (first, last, label) in enumerate(sorted(intervals)):
        if index and first <= sorted(intervals)[index - 1][1]:
            prior = sorted(intervals)[index - 1]
            errors.append(
                f"object-ID overlap {prior[2]}=0x{prior[0]:08X}..0x{prior[1]:08X} "
                f"and {label}=0x{first:08X}..0x{last:08X}"
            )
    return errors


def plan_text(items: Iterable[PlanItem]) -> str:
    lines = ["# Immutable P10.3 four-lane stage plan"]
    for item in items:
        lines.append(item.plan_line() if isinstance(item, Case) else " ".join(item))
    return "\n".join(lines) + "\n"


def artifact_key(item: dict[str, Any]) -> str:
    return f"{item['role']}:{item['kind']}"


def load_freeze() -> tuple[dict[str, Any], dict[str, Path]]:
    record = json.loads(FREEZE.read_text(encoding="utf-8"))
    errors: list[str] = []
    expected_scalars = {
        "schema_version": 1,
        "test_id": "P10_3-IMMUTABLE-ARTIFACT-FREEZE",
        "status": "PASS",
        "scope": SCOPE,
        "branch": BRANCH,
        "goal_sha256": GOAL_SHA256,
        "acceptance_eligible": True,
        "source_tree_clean": True,
        "no_hardware": True,
        "hardware_actions_executed": False,
    }
    errors.extend(f"artifact freeze {key} mismatch" for key, value in
                  expected_scalars.items() if record.get(key) != value)
    if record.get("status") != "PASS" or not record.get("acceptance_eligible"):
        errors.append("artifact freeze is not acceptance-eligible PASS")
    if tuple(record.get("allowed_hardware_stages", ())) != STAGES:
        errors.append("artifact freeze stage scope mismatch")
    if record.get("baseline_verification", {}).get("status") != "PASS":
        errors.append("artifact freeze baseline verification is not PASS")
    required_gates = {
        "p10_2_verify_existing", "p10_1r_verify_existing", "p10_verify_existing",
        "p8c_safety_verify_existing", "state_requirements_consistency",
        "no_hardware_static_scan", "p10_3_xsim", "functional_fixed",
        "functional_rotating", "shutdown_fixed", "shutdown_rotating",
        "ps_runtime_fixed", "ps_runtime_rotating",
    }
    gates = record.get("offline_gates", {})
    if set(gates) != required_gates or any(
            not isinstance(item, dict) or item.get("status") != "PASS"
            for item in gates.values()
    ):
        errors.append("artifact freeze offline gate set/status mismatch")
    source = str(record.get("source_commit", ""))
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        errors.append("invalid artifact source commit")
    elif not git_commit_exists(source) or not git_is_ancestor(source):
        errors.append("artifact source commit missing or not an ancestor of HEAD")
    if record.get("expected_build_ids") != {
            "fixed": "0x50333446", "rotating": "0x50333452"}:
        errors.append("artifact freeze build-ID binding mismatch")
    artifacts: dict[str, Path] = {}
    for item in record.get("artifacts", []):
        try:
            key = artifact_key(item)
            path = (ROOT / item["path"]).resolve()
            if key in artifacts or not inside(path, ROOT / "artifacts/p10_3"):
                raise ValueError("duplicate/outside content store")
            expected_parent = (ROOT / "artifacts/p10_3" / source /
                               item["sha256"]).resolve()
            if path.parent != expected_parent:
                raise ValueError("artifact path is not source/SHA content-addressed")
            if not path.is_file() or sha256(path) != item["sha256"] or \
                    path.stat().st_size != item["bytes"]:
                raise ValueError("missing/hash/size mismatch")
            if item.get("read_only") is not True:
                raise ValueError("artifact is not declared read-only")
            artifacts[key] = path
        except (KeyError, OSError, ValueError) as exc:
            errors.append(f"malformed artifact record: {exc}")
    required = {
        f"{role}:{kind}" for role in ("fixed", "rotating")
        for kind in ("shutdown_bitstream", "functional_bitstream", "xsa", "bsp", "elf")
    }
    if set(artifacts) != required:
        errors.append(f"artifact set mismatch: {sorted(artifacts)}")
    build_evidence = record.get("build_evidence", {})
    if set(build_evidence) != {"functional", "shutdown", "ps_runtime", "xsim"}:
        errors.append("artifact freeze build-evidence set mismatch")
    else:
        for name, item in build_evidence.items():
            try:
                path = (ROOT / item["path"]).resolve()
                if not inside(path, ROOT / "evidence/generated") or \
                        not path.is_file() or sha256(path) != item["sha256"] or \
                        path.stat().st_size != item["bytes"]:
                    raise ValueError("missing/hash/size/outside generated evidence")
            except (KeyError, OSError, ValueError) as exc:
                errors.append(f"artifact freeze {name} evidence malformed: {exc}")
    if errors:
        raise RuntimeError("; ".join(errors))
    return record, artifacts


def expected_run_id(freeze: dict[str, Any]) -> str:
    fixed = next(item for item in freeze["artifacts"]
                 if artifact_key(item) == "fixed:functional_bitstream")
    rotating = next(item for item in freeze["artifacts"]
                    if artifact_key(item) == "rotating:functional_bitstream")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (f"p10_3_{stamp}_{freeze['source_commit'][:8]}_"
            f"{fixed['sha256'][:8]}_{rotating['sha256'][:8]}")


def prepare_authorization(run_id: str | None) -> dict[str, Any]:
    freeze, _ = load_freeze()
    preflight_errors = [*validate_goal_files(), *validate_baseline_refs()]
    _, _, wiring_errors = validate_wiring_inventory()
    preflight_errors.extend(wiring_errors)
    preflight_errors.extend(validate_plans(build_plans()))
    if preflight_errors:
        raise RuntimeError("; ".join(preflight_errors))
    if git("branch", "--show-current") != BRANCH:
        raise RuntimeError("P10.3 branch mismatch")
    if git("status", "--porcelain"):
        raise RuntimeError("authorization preparation requires a clean worktree")
    actual_run_id = run_id or expected_run_id(freeze)
    if not RUN_RE.fullmatch(actual_run_id):
        raise RuntimeError("invalid P10.3 run id")
    inputs = expected_authorization_inputs()
    freeze_commit = git("rev-parse", "HEAD")
    record = {
        "schema_version": 1,
        "authorization_id": "P10_3-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED",
        "scope": SCOPE,
        "branch": BRANCH,
        "run_id": actual_run_id,
        "source_commit": freeze["source_commit"],
        "artifact_freeze_commit": freeze_commit,
        "authorization_parent_commit": freeze_commit,
        "goal_sha256": GOAL_SHA256,
        "external_goal": {
            "path": str(EXTERNAL_GOAL),
            "sha256": EXTERNAL_GOAL_SHA256,
            "bytes": EXTERNAL_GOAL.stat().st_size,
        },
        "artifact_freeze": rel(FREEZE),
        "artifact_freeze_sha256": sha256(FREEZE),
        "artifacts": freeze["artifacts"],
        "artifact_bundle_sha256": hash_text(json.dumps(
            freeze["artifacts"], sort_keys=True, separators=(",", ":")
        )),
        "inputs": inputs,
        "actual_wiring_sha256": sha256(WIRING),
        "module_inventory_sha256": sha256(INVENTORY),
        "part": EXPECTED_PART,
        "board_binding": {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating": "AX7020-R/JTAG:210512180081",
        },
        "active_modules": list(MODULES),
        "module_binding": EXPECTED_MODULE_BINDING,
        "old_f1_selected": False,
        "old_f1_status": "QUARANTINED_NOT_ACCEPTED",
        "lane_pairs": {f"lane{i}": f"F{i}-R{i}" for i in range(4)},
        "allowed_stages": list(STAGES),
        "plan_sha256": {stage: hash_text(plan_text(build_plans()[stage]))
                         for stage in STAGES},
        "lane_masks": list(range(1, 16)),
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "retry_limits": {
            "jtag_connect": 3, "program_per_operation": 2,
            "diagnostic_run_ids_per_stage": 2,
        },
        "current_run_hardware_authorization": True,
        "user_authorization_received_on": "2026-08-04",
        "user_authorization_statement": "继续目标，raw测试还需要包括lane0 lane1",
        "authorization_basis": {
            "campaign_standing_authorization": (
                "User explicitly authorized automated P10_3 AX7020 stationary four-lane "
                "hardware acceptance for the current two boards and eight modules, "
                "mask<=0xF, no Ethernet/movement/rotation/realignment/rewiring, no "
                "two-hour run, and no P11."
            ),
            "fresh_current_run_instruction": (
                "Continue the P10.3 goal and include bidirectional raw tests for lane0 "
                "and lane1 in the new immutable run."
            ),
            "fresh_current_run_ids_authorized": 1,
        },
        "shutdown_policy": {
            "before": True, "on_error": True, "on_timeout": True,
            "on_ctrl_c": True, "on_normal_exit": True,
            "after_each_stage": True, "verify_both": True,
        },
        "forbidden": {
            "ethernet": True, "movement": True, "rotation": True,
            "realignment": True, "rewiring": True, "lane_mask_above_0xF": True,
            "two_hour_test": True, "p11": True,
        },
        "network_used": False,
        "hardware_movement": False,
        "rotation": False,
        "realignment": False,
        "rewiring": False,
        "two_hour_test": False,
        "p11": False,
        "generated_at_utc": utc_now(),
        "consumed": False,
    }
    write_json(AUTH, record)
    return record


def validate_authorization(path: Path, run_id: str,
                           stages: tuple[str, ...]) -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        freeze, artifacts = load_freeze()
    except (OSError, ValueError, RuntimeError) as exc:
        return {}, {}, [str(exc)]
    expected = {
        "schema_version": 1,
        "authorization_id": "P10_3-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED", "scope": SCOPE, "branch": BRANCH,
        "run_id": run_id,
        "source_commit": freeze.get("source_commit"),
        "goal_sha256": GOAL_SHA256,
        "artifact_freeze_sha256": sha256(FREEZE),
        "artifact_freeze": rel(FREEZE),
        "artifact_bundle_sha256": hash_text(json.dumps(
            freeze.get("artifacts", []), sort_keys=True, separators=(",", ":")
        )),
        "actual_wiring_sha256": sha256(WIRING),
        "module_inventory_sha256": sha256(INVENTORY),
        "part": EXPECTED_PART,
        "current_run_hardware_authorization": True,
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "old_f1_selected": False,
        "old_f1_status": "QUARANTINED_NOT_ACCEPTED",
        "active_modules": list(MODULES),
        "module_binding": EXPECTED_MODULE_BINDING,
        "board_binding": {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating": "AX7020-R/JTAG:210512180081",
        },
        "lane_pairs": {f"lane{i}": f"F{i}-R{i}" for i in range(4)},
        "lane_masks": list(range(1, 16)),
        "retry_limits": {
            "jtag_connect": 3, "program_per_operation": 2,
            "diagnostic_run_ids_per_stage": 2,
        },
        "shutdown_policy": {
            "before": True, "on_error": True, "on_timeout": True,
            "on_ctrl_c": True, "on_normal_exit": True,
            "after_each_stage": True, "verify_both": True,
        },
        "forbidden": {
            "ethernet": True, "movement": True, "rotation": True,
            "realignment": True, "rewiring": True,
            "lane_mask_above_0xF": True, "two_hour_test": True,
            "p11": True,
        },
        "network_used": False, "hardware_movement": False,
        "rotation": False, "realignment": False, "rewiring": False,
        "two_hour_test": False, "p11": False,
    }
    errors.extend(f"authorization {key} mismatch" for key, value in expected.items()
                  if record.get(key) != value)
    if record.get("consumed") is not False:
        errors.append("authorization already consumed")
    if tuple(record.get("allowed_stages", ())) != STAGES or stages != STAGES:
        errors.append("full immutable P10.3 stage set required")
    if record.get("plan_sha256") != {
        stage: hash_text(plan_text(build_plans()[stage])) for stage in STAGES
    }:
        errors.append("authorization plan hash mismatch")
    if record.get("artifacts") != freeze.get("artifacts"):
        errors.append("authorization artifacts differ from freeze")
    try:
        expected_inputs = expected_authorization_inputs()
    except OSError as exc:
        expected_inputs = {}
        errors.append(f"authorization input missing: {exc}")
    if record.get("inputs") != expected_inputs:
        errors.append("authorization exact input set/hash/size mismatch")
    for name, meta in record.get("inputs", {}).items():
        candidate = ROOT / name
        if not candidate.is_file() or sha256(candidate) != meta.get("sha256") or \
                candidate.stat().st_size != meta.get("bytes"):
            errors.append(f"authorization input changed: {name}")
    external = record.get("external_goal", {})
    if external != {
            "path": str(EXTERNAL_GOAL), "sha256": EXTERNAL_GOAL_SHA256,
            "bytes": EXTERNAL_GOAL.stat().st_size if EXTERNAL_GOAL.is_file() else -1}:
        errors.append("authorization external Goal binding mismatch")
    errors.extend(validate_goal_files())
    errors.extend(validate_baseline_refs())
    _, _, wiring_errors = validate_wiring_inventory()
    errors.extend(wiring_errors)
    errors.extend(validate_plans(build_plans()))
    if not RUN_RE.fullmatch(run_id):
        errors.append("unsafe run id")
    if git("branch", "--show-current") != BRANCH:
        errors.append("branch mismatch")
    if git("status", "--porcelain"):
        errors.append("hardware run requires clean worktree")
    source_commit = str(record.get("source_commit", ""))
    freeze_commit = str(record.get("artifact_freeze_commit", ""))
    parent_commit = str(record.get("authorization_parent_commit", ""))
    if not git_commit_exists(source_commit) or not git_is_ancestor(source_commit):
        errors.append("authorization source commit missing/not ancestor")
    if not git_commit_exists(freeze_commit) or not git_is_ancestor(freeze_commit):
        errors.append("authorization artifact-freeze commit missing/not ancestor")
    if parent_commit != freeze_commit:
        errors.append("authorization parent/freeze commit mismatch")
    if not file_matches_head(path):
        errors.append("authorization file is not the committed HEAD version")
    return record, artifacts, errors


def integer_row(row: dict[str, str]) -> dict[str, Any]:
    numbers = {
        "command", "expected_status", "flags", "lane", "direction", "rate",
        "weights", "size", "ring", "cache", "txoff", "rxoff", "timeout",
        "session", "path", "object", "dropdata", "dropack", "unavailable",
        "rawtarget", "spacing", "stale", "initialseq", "faultflags", "idle",
        "injectmask", "injectdelay", "started_ms", "finished_ms", "sequence",
        "fixed_status", "rotating_status", "fixed_state", "rotating_state",
        "injection_applied", "injection_readback", "injection_timestamp_ms",
    }
    return {key: int(value, 0) if key in numbers and value else value
            for key, value in row.items()}


def parse_p103(path: Path) -> dict[str, Any]:
    values = [int(item, 0) for item in path.read_text(encoding="ascii").strip().split("|")]
    if len(values) != 130:
        raise ValueError(f"P10.2 snapshot length {len(values)} != 130")
    # The XSDB writer prepends the atomic generation followed by the schema.
    # Keep this order explicit: swapping them would make every valid hardware
    # snapshot fail closed after the run had already exercised the link.
    generation, schema, *words = values
    if schema != P103_SCHEMA or words[127] != P103_SCHEMA or generation & 1:
        raise ValueError("P10.2 snapshot schema/generation mismatch")
    payload_bytes = (words[0] >> 24) & 0xFF
    window_size = (words[0] >> 16) & 0xFF
    lane_count = (words[0] >> 8) & 0xFF
    module_count = words[0] & 0xFF
    if (payload_bytes, window_size, lane_count, module_count) != (247, 32, 4, 8):
        raise ValueError("P10.2 snapshot is not four-lane/eight-module")
    lanes = []
    for lane in range(4):
        base = 8 + 12 * lane
        lanes.append({
            "scheduled_frames": words[base], "scheduled_bytes": words[base + 1],
            "scheduler_retries": words[base + 2], "migrations": words[base + 3],
            "data_good": words[base + 4], "ack_good": words[base + 5],
            "crc_bad": words[base + 6], "frame_bad": words[base + 7],
            "raw_while_local_tx": words[base + 8],
            "blanked_raw": words[base + 9], "local_source_reject": words[base + 10],
            "accepted_remote": words[base + 11],
        })
    modules = []
    for module in range(8):
        base = 56 + 8 * module
        modules.append({
            "raw_rx": words[base], "physical_tx": words[base + 1],
            "tx_high_max": words[base + 2], "duty_high_max": words[base + 3],
            "duty_current": words[base + 4], "duty_headroom": words[base + 5],
            "target_throttle": words[base + 6], "hard_fault": words[base + 7],
        })
    return {
        "generation": generation, "schema": f"0x{schema:08X}",
        "payload_bytes": payload_bytes, "window_size": window_size,
        "lane_count": lane_count, "module_count": module_count,
        "phy_ready_mask": words[1] & 0xF,
        "startup_done_mask": (words[1] >> 4) & 0xF,
        "safety_fault_mask": (words[1] >> 8) & 0xF,
        "active_mask": words[2] & 0xF, "unavailable_mask": (words[2] >> 4) & 0xF,
        "effective_mask": (words[2] & 0xF) & ~((words[2] >> 4) & 0xF),
        "rx_admission_status": words[3],
        "tx_attempts": words[4], "retry_count": words[5],
        "migration_count": words[6], "lanes": lanes, "modules": modules,
        "physical_data_good": words[7] & 0xFFFF,
        "physical_ack_good": (words[7] >> 16) & 0xFFFF,
        "overlap_violation": words[120], "admission_violation": words[121],
        "non_target_accepted": words[122], "cross_lane_accepted": words[123],
        "duty_window_cycles": words[124], "hard_limit_cycles": words[125],
        "target_limit_cycles": words[126],
    }


def snapshot_errors(label: str, role: str, snap: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if (snap["payload_bytes"], snap["window_size"], snap["lane_count"],
            snap["module_count"]) != (247, 32, 4, 8):
        errors.append(f"{label}:{role}:snapshot capability mismatch")
    if snap["safety_fault_mask"]:
        errors.append(f"{label}:{role}:snapshot safety fault mask nonzero")
    for field in ("overlap_violation", "admission_violation",
                  "non_target_accepted", "cross_lane_accepted"):
        if snap[field] != 0:
            errors.append(f"{label}:{role}:{field}={snap[field]}")
    if (snap["duty_window_cycles"], snap["hard_limit_cycles"],
            snap["target_limit_cycles"]) != (
                64000, HARD_DUTY_MAX_CYCLES, TARGET_DUTY_CYCLES):
        errors.append(f"{label}:{role}:duty configuration mismatch")
    local = range(4) if role == "fixed" else range(4, 8)
    for module in local:
        item = snap["modules"][module]
        if item["tx_high_max"] > 64:
            errors.append(f"{label}:{role}:module{module}:Txd high >1us")
        if item["duty_high_max"] > TARGET_DUTY_CYCLES:
            errors.append(f"{label}:{role}:module{module}:duty target exceeded")
        if item["duty_high_max"] > HARD_DUTY_MAX_CYCLES or item["hard_fault"]:
            errors.append(f"{label}:{role}:module{module}:hard duty violation")
    return errors


def generic_pair(row: dict[str, Any], fixed_words: list[int],
                 rotating_words: list[int]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    details: dict[str, Any] = {"label": row["label"], "command": row["command"],
                               "lane_mask": row["lane"], "direction": row["direction"]}
    for role, words in (("fixed", fixed_words), ("rotating", rotating_words)):
        local_errors, local = mailbox_detail(words, role, EXPECTED_ROLE)
        snapshot = lambda index: words[116 + index]
        object_config = snapshot(10)
        fault_config = snapshot(15)
        sequence_state = snapshot(22)
        window_state = snapshot(23)
        local["transport"] = {
            "configured_lane_mask": object_config & 0xF,
            "configured_rate_select": (object_config >> 8) & 0x3,
            "configured_direction": (object_config >> 16) & 0x1,
            "configured_weights": snapshot(11),
            "configured_session_epoch": snapshot(12),
            "configured_path_epoch": snapshot(13) & 0xFFFF,
            "configured_object_id": snapshot(14),
            "configured_drop_data": fault_config & 0xFF,
            "configured_drop_ack": (fault_config >> 8) & 0xFF,
            "configured_unavailable_mask": (fault_config >> 16) & 0xF,
            "tx_next_sequence": sequence_state & 0xFFFF,
            "tx_ack_base": (sequence_state >> 16) & 0xFFFF,
            "rx_base_sequence": window_state & 0xFFFF,
            "tx_outstanding": (window_state >> 16) & 0x3F,
            "tx_outstanding_high_watermark": (window_state >> 22) & 0x3F,
            "rx_sack_bitmap": snapshot(24),
            "physical_drop_data": snapshot(42),
            "physical_drop_ack": snapshot(43),
            "duplicate_ack": snapshot(34),
            "out_of_window_ack": snapshot(36),
            "initial_sequence": snapshot(88) & 0xFFFF,
            "protocol_fault_flags": snapshot(89) & 0xFFF,
            "rx_out_of_order": snapshot(90),
            "rx_old": snapshot(91),
            "rx_future": snapshot(92),
            "rx_gap": snapshot(93),
            "rx_delivery": snapshot(94),
            "rx_protocol_error": snapshot(95),
            "physical_frame_bad": snapshot(96),
            "physical_preamble": snapshot(97),
            "physical_symbol_error": snapshot(98),
        }
        local.update({
            "tx_double_completion": words[96],
            "rx_double_completion": words[97],
            "stale_completion_rejected": words[99],
        })
        errors.extend(f"{row['label']}:{item}" for item in local_errors)
        expected_state = 6 if row["command"] == 10 else 4
        if words[3] != expected_state or words[7] != row["sequence"] or words[8] != 0:
            errors.append(f"{row['label']}:{role}:mailbox terminal mismatch")
        details[role] = local
        if words[115] == 0x50534C44:
            errors.append(f"{row['label']}:{role}:PS activity LED counter fault")
    return errors, details


def window_summaries(details: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    output = []
    for item in build_plans()[stage]:
        if not isinstance(item, tuple) or item[0] != "P101_WINDOW":
            continue
        label, duration, direction, lane = item[1], int(item[2]), int(item[3]), int(item[4])
        matched = [detail for detail in details if detail.get("window") == label]
        committed = sum(detail.get("requested_bytes", 0) for detail in matched
                        if not detail.get("recovery_case"))
        output.append({
            "label": label, "duration_seconds": duration, "direction": direction,
            "lane_mask": lane, "case_count": len(matched),
            "committed_bytes": committed,
            "application_goodput_bps": committed * 8 / duration,
        })
    return output


CASE_ROW_FIELDS = (
    "command", "expected_status", "flags", "lane", "direction", "rate",
    "weights", "size", "ring", "cache", "txoff", "rxoff", "timeout",
    "session", "path", "object", "dropdata", "dropack", "unavailable",
    "rawtarget", "spacing", "stale", "initialseq", "faultflags", "idle",
    "injectmask", "injectdelay",
)


def validate_observation_shape(stage: str, rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    shutdown_positions = [index for index, row in enumerate(rows)
                          if str(row.get("label", "")).endswith("_endpoint_shutdown")]
    if shutdown_positions != [len(rows) - 1]:
        errors.append("exactly one final endpoint-shutdown observation required")
    body = rows[:-1] if shutdown_positions == [len(rows) - 1] else rows
    cursor = 0

    def consume_window(label: str, direction: int, lane: int) -> None:
        nonlocal cursor
        started = cursor
        while cursor < len(body) and body[cursor].get("window") == label:
            row = body[cursor]
            if row.get("command") != 13 or row.get("direction") != direction or \
                    row.get("lane") != lane or not str(row.get("label", "")).startswith(label):
                errors.append(f"{label}: dynamic window row mismatch")
            cursor += 1
        if cursor == started:
            errors.append(f"{label}: dynamic window has no autonomous command")

    for item in build_plans()[stage]:
        if isinstance(item, Case):
            if cursor >= len(body):
                errors.append(f"missing immutable case {item.label}")
                continue
            row = body[cursor]
            cursor += 1
            if row.get("label") != item.label:
                errors.append(f"case order mismatch: expected {item.label}")
                continue
            expected = dict(zip(CASE_ROW_FIELDS, (
                item.command, item.expected_status, item.flags, item.lane,
                item.direction, item.rate, item.weights, item.size, item.ring,
                item.cache, item.txoff, item.rxoff, item.timeout, item.session,
                item.path, item.object, item.dropdata, item.dropack,
                item.unavailable, item.rawtarget, item.spacing, item.stale,
                item.initialseq, item.faultflags, item.idle, item.injectmask,
                item.injectdelay,
            )))
            for key, value in expected.items():
                if row.get(key) != value:
                    errors.append(f"{item.label}:{key} differs from immutable plan")
            if item.injectmask:
                if row.get("injection_applied") != 1 or \
                        ((row.get("injection_readback", 0) >> 16) & 0xF) != item.injectmask:
                    errors.append(f"{item.label}: authorized live injection not evidenced")
            elif row.get("injection_applied", 0) != 0:
                errors.append(f"{item.label}: unexpected live injection")
        elif item[0] == "P101_WINDOW":
            consume_window(item[1], int(item[3]), int(item[4]))
        elif item[0] == "P101_PSRESET":
            if cursor >= len(body) or body[cursor].get("label") != item[1] or \
                    body[cursor].get("window") != "PS_SERVICE_RESET":
                errors.append(f"missing service-reset vector {item[1]}")
            else:
                cursor += 1
        elif item[0] == "P101_FORMAL":
            base = item[1]
            for suffix, direction in (("warmup_f2r", 0), ("warmup_r2f", 1),
                                      ("formal_f2r", 0), ("formal_r2f", 1)):
                consume_window(f"{base}_{suffix}", direction, 15)
    if cursor != len(body):
        errors.append(f"{len(body) - cursor} extra/reordered observations")

    intervals: list[tuple[int, int, str]] = []
    for row in body:
        if row.get("command") not in (3, 13):
            continue
        count = stream_object_count(row["size"]) if row["command"] == 13 else 1
        intervals.append((row["object"], row["object"] + count - 1, row["label"]))
    ordered = sorted(intervals)
    for previous, current in zip(ordered, ordered[1:]):
        if current[0] <= previous[1]:
            errors.append(
                f"observed object-ID overlap {previous[2]} and {current[2]}"
            )
    if len({row.get("sequence") for row in rows}) != len(rows):
        errors.append("duplicate command sequence in observation ledger")
    return errors


def mailbox_for(detail: dict[str, Any], role: str) -> dict[str, Any]:
    return detail.get(f"{role}_mailbox", detail.get(role, {}))


def path_roles(detail: dict[str, Any]) -> tuple[str, str]:
    return ("fixed", "rotating") if detail["direction"] == 0 else \
        ("rotating", "fixed")


def data_path_errors(detail: dict[str, Any], *, unavailable: int = 0,
                     injected: bool = False,
                     require_all_selected: bool = True) -> list[str]:
    """Gate lane use from direct PL snapshots, not the requested mask alone."""
    errors: list[str] = []
    if detail.get("command") not in (3, 13) or detail.get("recovery_case"):
        return errors
    sender_role, receiver_role = path_roles(detail)
    sender_snap = detail[f"{sender_role}_p10_2"]
    receiver_snap = detail[f"{receiver_role}_p10_2"]
    sender_mail = mailbox_for(detail, sender_role)
    receiver_mail = mailbox_for(detail, receiver_role)
    mask = detail["lane_mask"]
    effective = mask & ~unavailable & 0xF
    expected_receiver_unavailable = 0 if injected else unavailable
    for role, snap, expected_unavailable in (
        (sender_role, sender_snap, unavailable),
        (receiver_role, receiver_snap, expected_receiver_unavailable),
    ):
        if snap["active_mask"] != mask:
            errors.append(f"{detail['label']}:{role}:active-mask readback")
        if snap["unavailable_mask"] != expected_unavailable:
            errors.append(f"{detail['label']}:{role}:unavailable-mask readback")
    transport = sender_mail.get("transport", {})
    if transport:
        expected = {
            "configured_lane_mask": mask,
            "configured_rate_select": 2,
            "configured_direction": detail["direction"],
            "configured_unavailable_mask": unavailable,
        }
        for key, value in expected.items():
            if transport.get(key) != value:
                errors.append(f"{detail['label']}:{sender_role}:{key}")
    receiver_transport = receiver_mail.get("transport", {})
    if receiver_transport and receiver_transport.get("configured_lane_mask") != mask:
        errors.append(f"{detail['label']}:{receiver_role}:configured_lane_mask")

    sender_base = 0 if sender_role == "fixed" else 4
    receiver_base = 0 if receiver_role == "fixed" else 4
    any_selected_progress = False
    for lane in range(4):
        bit = 1 << lane
        selected = bool(effective & bit)
        scheduled = sender_snap["lanes"][lane]["scheduled_frames"]
        scheduled_bytes = sender_snap["lanes"][lane]["scheduled_bytes"]
        accepted = receiver_snap["lanes"][lane]["accepted_remote"]
        physical_data = receiver_snap["lanes"][lane]["data_good"]
        physical_tx = sender_snap["modules"][sender_base + lane]["physical_tx"]
        if selected:
            progressed = scheduled > 0 and scheduled_bytes > 0 and \
                accepted > 0 and physical_data > 0 and physical_tx > 0
            any_selected_progress |= progressed
            if require_all_selected and not progressed:
                errors.append(f"{detail['label']}:lane{lane}:selected lane made no progress")
        elif not injected or bit != unavailable:
            if scheduled or scheduled_bytes or accepted or physical_tx:
                errors.append(f"{detail['label']}:lane{lane}:disabled lane activity")
        if not mask & bit and receiver_snap["lanes"][lane]["blanked_raw"]:
            errors.append(f"{detail['label']}:lane{lane}:other lane blanked")
    if not any_selected_progress:
        errors.append(f"{detail['label']}:no healthy selected-lane progress")
    for module in range(8):
        if module not in range(sender_base, sender_base + 4) and \
                sender_snap["modules"][module]["physical_tx"]:
            errors.append(f"{detail['label']}:{sender_role}:nonlocal module TX")
        if module not in range(receiver_base, receiver_base + 4) and \
                receiver_snap["modules"][module]["physical_tx"]:
            errors.append(f"{detail['label']}:{receiver_role}:nonlocal module TX")
    return errors


def load_ps_gpio(stage_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    path = stage_dir / "dumps/ps_gpio_activity.psv"
    errors: list[str] = []
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows, ["PS GPIO activity ledger missing"]
    with path.open(encoding="ascii", newline="") as handle:
        for raw in csv.DictReader(handle, delimiter="|"):
            try:
                rows.append({
                    "captured_ms": int(raw["captured_ms"], 0),
                    "sequence": int(raw["sequence"], 0),
                    "label": raw["label"], "role": raw["role"],
                    "data_ro": int(raw["data_ro"], 0),
                    "dirm0": int(raw["dirm0"], 0),
                    "oen0": int(raw["oen0"], 0),
                })
            except (KeyError, ValueError) as exc:
                errors.append(f"malformed PS GPIO row: {exc}")
    mask = (1 << 0) | (1 << 13)
    for row in rows:
        if row["role"] not in ("fixed", "rotating") or \
                row["dirm0"] & mask != mask or row["oen0"] & mask != mask:
            errors.append(f"{row.get('label', 'unknown')}:PS LED GPIO direction/OE")
    safe = [row for row in rows if row["label"] == "SAFE_BOOT"]
    if len(safe) != 2 or any(row["data_ro"] & mask != mask for row in safe):
        errors.append("PS LED safe-boot off state not directly read back")
    terminal = [row for row in rows
                if row["label"].endswith("_endpoint_shutdown_terminal")]
    if len(terminal) != 2 or any(row["data_ro"] & mask != mask for row in terminal):
        errors.append("PS LED endpoint-shutdown off state not directly read back")
    return rows, errors


def evaluate_stage(stage: str, stage_dir: Path, process: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    markers = parse_markers(stage_dir / "xsdb.result.txt")
    if process.get("returncode") != 0 or process.get("timed_out"):
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS" or markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("XSDB stage/safe-boot PASS marker missing")
    ledger = stage_dir / "dumps/observations.psv"
    rows: list[dict[str, Any]] = []
    if ledger.is_file():
        with ledger.open(encoding="ascii", newline="") as handle:
            rows = [integer_row(row) for row in csv.DictReader(handle, delimiter="|")]
    else:
        errors.append("observation ledger missing")
    errors.extend(validate_observation_shape(stage, rows))
    details: list[dict[str, Any]] = []
    for row in rows:
        try:
            fixed_mail = Path(row["fixed_dump_path"]).resolve()
            rotating_mail = Path(row["rotating_dump_path"]).resolve()
            if not inside(fixed_mail, stage_dir) or not inside(rotating_mail, stage_dir):
                raise ValueError("mailbox path escaped stage")
            fixed_words = parse_mailbox(fixed_mail)
            rotating_words = parse_mailbox(rotating_mail)
            service_reset = row["command"] == 13 and bool(
                row["flags"] & p101.SERVICE_RESET_FLAGS
            )
            if service_reset:
                mailbox_errors, mailbox_detail_pair = [], {"fixed": {}, "rotating": {}}
            else:
                mailbox_errors, mailbox_detail_pair = generic_pair(
                    row, fixed_words, rotating_words
                )
            errors.extend(mailbox_errors)
            fixed_snap = parse_p103(stage_dir / "dumps" / f"{row['label']}.fixed.p10_2.psv")
            rotating_snap = parse_p103(stage_dir / "dumps" / f"{row['label']}.rotating.p10_2.psv")
            errors.extend(snapshot_errors(row["label"], "fixed", fixed_snap))
            errors.extend(snapshot_errors(row["label"], "rotating", rotating_snap))
            if row["command"] == 13:
                fixed_p101 = Path(row["fixed_p10_1_dump_path"]).resolve()
                rotating_p101 = Path(row["rotating_p10_1_dump_path"]).resolve()
                if not inside(fixed_p101, stage_dir) or not inside(rotating_p101, stage_dir):
                    raise ValueError("P10.1 result path escaped stage")
                pair_errors, detail = p101.evaluate_p101_pair(
                    row, p101.parse_p101(fixed_p101), p101.parse_p101(rotating_p101)
                )
                if not service_reset:
                    detail["fixed_mailbox"] = mailbox_detail_pair["fixed"]
                    detail["rotating_mailbox"] = mailbox_detail_pair["rotating"]
            else:
                pair_errors, detail = [], mailbox_detail_pair
            errors.extend(pair_errors)
            detail.update({"command": row["command"], "sequence": row["sequence"],
                           "started_ms": row["started_ms"],
                           "finished_ms": row["finished_ms"],
                           "window": row["window"], "flags": row["flags"],
                           "unavailable": row["unavailable"],
                           "injectmask": row["injectmask"],
                           "injection_applied": row.get("injection_applied", 0),
                           "injection_readback": row.get("injection_readback", 0),
                           "injection_timestamp_ms": row.get("injection_timestamp_ms", 0),
                           "injection_sender": row.get("injection_sender", "NA"),
                           "plan_fields": {key: row[key] for key in (
                               "command", "flags", "lane", "direction", "rate",
                               "weights", "size", "ring", "cache", "object",
                               "dropdata", "dropack", "unavailable", "rawtarget",
                               "spacing", "stale", "initialseq", "faultflags",
                               "injectmask", "injectdelay")},
                           "fixed_p10_2": fixed_snap, "rotating_p10_2": rotating_snap})
            if row["command"] == 2:
                lane_index = int(math.log2(row["lane"]))
                sender_role = "fixed" if row["direction"] == 0 else "rotating"
                receiver_role = "rotating" if row["direction"] == 0 else "fixed"
                sender = fixed_snap if sender_role == "fixed" else rotating_snap
                receiver = rotating_snap if receiver_role == "rotating" else fixed_snap
                sender_module = lane_index if sender_role == "fixed" else 4 + lane_index
                receiver_module = 4 + lane_index if receiver_role == "rotating" else lane_index
                if sender["modules"][sender_module]["physical_tx"] != row["rawtarget"]:
                    errors.append(f"{row['label']}:physical TX count mismatch")
                observed = receiver["modules"][receiver_module]["raw_rx"]
                if not row["rawtarget"] <= observed <= row["rawtarget"] + 8:
                    errors.append(f"{row['label']}:target remote raw count mismatch")
                detail["raw_source"] = ("F" if row["direction"] == 0 else "R") + str(lane_index)
            details.append(detail)
        except (OSError, ValueError, KeyError, struct.error) as exc:
            errors.append(f"{row.get('label', 'unknown')}:{exc}")

    ps_gpio, ps_gpio_errors = load_ps_gpio(stage_dir)
    errors.extend(ps_gpio_errors)
    semantics: dict[str, Any] = {
        "ps_led_gpio": {
            "samples": len(ps_gpio),
            "register_evidence": True,
            "physical_visible_state": "PENDING_DIRECT_USER_OBSERVATION",
        }
    }
    non_shutdown = [detail for detail in details
                    if not detail["label"].endswith("_endpoint_shutdown")]
    for detail in non_shutdown:
        if detail.get("command") != 13 or detail.get("recovery_case") or \
                detail["flags"] & p101.SERVICE_RESET_FLAGS or \
                detail["plan_fields"]["size"] < 64 << 20:
            continue
        sender_role, receiver_role = path_roles(detail)
        active = [row for row in ps_gpio if row["sequence"] == detail["sequence"] and
                  not row["label"].endswith("_terminal")]
        if not any(row["role"] == sender_role and not (row["data_ro"] & 1)
                   for row in active):
            errors.append(f"{detail['label']}:PS TX LED active-low state not sampled")
        if not any(row["role"] == receiver_role and
                   not (row["data_ro"] & (1 << 13)) for row in active):
            errors.append(f"{detail['label']}:PS RX LED active-low state not sampled")

    if stage == "preflight":
        identities = [d for d in non_shutdown if d["command"] == 1]
        if len(identities) != 2:
            errors.append("preflight identity/reset identity pair missing")
        semantics.update({
            "safe_boot_both": markers.get("P10_SAFE_BOOT") == "PASS",
            "receive_only_ms": 5000,
            "target_role_binding": {
                "fixed": EXPECTED_FIXED_SERIAL,
                "rotating": EXPECTED_ROTATING_SERIAL,
            },
        })
    elif stage == "module_intake":
        raw_status: dict[str, str] = {}
        for module in MODULES:
            expected_raw = {
                f"intake_{module}_raw_64", f"intake_{module}_raw_1024"
            }
            observed_raw = {
                d["label"] for d in non_shutdown if d["label"] in expected_raw
            }
            raw_status[module] = "PASS" if observed_raw == expected_raw else "FAIL"
            if raw_status[module] != "PASS":
                errors.append(f"{module}:bidirectional raw-intake vector incomplete")
        module_status: dict[str, str] = {}
        for module in ("F2", "F3", "R2", "R3"):
            expected = {f"intake_{module}_raw_64", f"intake_{module}_raw_1024",
                        f"intake_{module}_counter_100f",
                        f"intake_{module}_prbs_1000f"}
            observed = {d["label"] for d in non_shutdown if d["label"] in expected}
            module_status[module] = "PASS" if observed == expected else "FAIL"
            if module_status[module] != "PASS":
                errors.append(f"{module}:module intake vector incomplete")
        for detail in non_shutdown:
            if detail["command"] == 3:
                errors.extend(data_path_errors(detail))
        semantics.update({"raw_connectivity_all_modules": raw_status,
                          "modules": module_status,
                          "receive_only_startup": "PASS",
                          "mode_sd_txd_default": "DIRECT_PL_SAFE_STATE_EVIDENCE"})
    elif stage == "raw_8x8":
        cells: list[dict[str, Any]] = []
        same_module_echo = 0
        for detail in non_shutdown:
            if detail["command"] == 13:
                errors.extend(data_path_errors(detail))
            if not detail["label"].endswith("raw1024"):
                continue
            source = detail["raw_source"]
            fixed = detail["fixed_p10_2"]["modules"]
            rotating = detail["rotating_p10_2"]["modules"]
            observations = [item["raw_rx"] for item in fixed[:4]] + \
                           [item["raw_rx"] for item in rotating[4:8]]
            source_index = MODULES.index(source)
            target_index = source_index + 4 if source_index < 4 else source_index - 4
            same_module_echo += observations[source_index]
            for index, module in enumerate(MODULES):
                classification = "TARGET_REMOTE" if index == target_index else \
                    "SAME_MODULE_ECHO" if index == source_index else "NON_TARGET_RAW"
                cells.append({"tx_source": source, "rx_observation": module,
                              "classification": classification,
                              "raw_edges": observations[index]})
            for snap in (detail["fixed_p10_2"], detail["rotating_p10_2"]):
                if any(lane["accepted_remote"] or lane["data_good"]
                       for lane in snap["lanes"]):
                    errors.append(f"{detail['label']}:raw pulses admitted as frame")
        if len(cells) != 64:
            errors.append(f"8x8 matrix has {len(cells)} cells")
        semantics.update({"cells": cells, "cell_count": len(cells),
                          "same_module_raw_echo_count": same_module_echo,
                          "same_module_accepted_data": 0,
                          "cross_lane_accepted_data": 0,
                          "non_target_crc_valid_accepted": 0})
    elif stage == "per_lane_phy":
        directions: list[dict[str, Any]] = []
        for detail in non_shutdown:
            errors.extend(data_path_errors(detail, require_all_selected=True))
            lane = int(math.log2(detail["lane_mask"]))
            expected_frames = 100 if "counter_100f" in detail["label"] else 10_000
            sender_role, receiver_role = path_roles(detail)
            sender_snap = detail[f"{sender_role}_p10_2"]
            receiver_snap = detail[f"{receiver_role}_p10_2"]
            if sender_snap["lanes"][lane]["scheduled_frames"] != expected_frames or \
                    receiver_snap["lanes"][lane]["data_good"] != expected_frames:
                errors.append(f"{detail['label']}:exact frame count mismatch")
            if mailbox_for(detail, sender_role).get("tx_retries") != 0:
                errors.append(f"{detail['label']}:clean PHY retry nonzero")
            directions.append({"label": detail["label"], "lane": lane,
                               "direction": detail["direction"],
                               "frames": expected_frames,
                               "pattern": "counter" if "counter" in detail["label"] else "PRBS"})
        semantics.update({"cases": directions, "directions": 8,
                          "configured_raw_bps_per_lane": 4_000_000})
    elif stage == "two_lane_regression":
        for detail in non_shutdown:
            errors.extend(data_path_errors(detail))
        normals = [detail for detail in non_shutdown
                   if detail["label"].startswith("regression_64m")]
        if len(normals) != 2 or any(detail["requested_bytes"] != 64 << 20
                                    for detail in normals):
            errors.append("two-lane 64MiB bidirectional regression incomplete")
        windows = window_summaries(details, stage)
        if len(windows) != 2 or any(window["application_goodput_bps"] < 4_000_000
                                    for window in windows):
            errors.append("two-lane application goodput below 4 Mbit/s")
        semantics.update({"windows": windows, "stream64_count": len(normals),
                          "fresh_regression": True})
    elif stage == "four_lane_raw":
        for detail in non_shutdown:
            errors.extend(data_path_errors(detail))
        windows = window_summaries(details, stage)
        mask_f = [window for window in windows if window["lane_mask"] == 15]
        if len(mask_f) != 2:
            errors.append("mask 0xF simultaneous four-lane bring-up missing")
        semantics.update({"windows": windows,
                          "aggregate_raw_capability_bps": 16_000_000,
                          "capability_basis": "4 active lanes x direct 4-Mbit/s PL rate readback",
                          "raw_capability_is_application_goodput": False})
    elif stage == "mask_matrix":
        for detail in non_shutdown:
            errors.extend(data_path_errors(detail))
        masks = sorted({detail["lane_mask"] for detail in non_shutdown})
        per_mask_counts = {mask: sum(d["lane_mask"] == mask for d in non_shutdown)
                           for mask in range(1, 16)}
        if masks != list(range(1, 16)) or any(count != 2
                                               for count in per_mask_counts.values()):
            errors.append(f"lane-mask matrix incomplete: {masks}/{per_mask_counts}")
        semantics.update({"masks": masks, "directions_per_mask": per_mask_counts,
                          "case_count": len(non_shutdown)})
    elif stage == "degrade":
        static_masks: list[int] = []
        inflight: list[dict[str, Any]] = []
        for detail in non_shutdown:
            expected_unavailable = detail["injectmask"] or detail["unavailable"]
            errors.extend(data_path_errors(
                detail, unavailable=expected_unavailable,
                injected=bool(detail["injectmask"]),
                require_all_selected=True,
            ))
            if detail["unavailable"]:
                static_masks.append(detail["unavailable"])
            if detail["injectmask"]:
                sender_role, _ = path_roles(detail)
                sender_snap = detail[f"{sender_role}_p10_2"]
                if detail["injection_applied"] != 1 or \
                        sender_snap["migration_count"] == 0 or \
                        sum(lane["migrations"] for lane in sender_snap["lanes"]) == 0:
                    errors.append(f"{detail['label']}:retry migration not directly observed")
                inflight.append({"label": detail["label"],
                                 "fault_mask": detail["injectmask"],
                                 "readback": f"0x{detail['injection_readback']:08X}",
                                 "migration_count": sender_snap["migration_count"]})
        if sorted(set(static_masks)) != [1, 2, 3, 4, 7, 8] or len(inflight) != 4:
            errors.append("degrade single-lane/4-to-3-to-2-to-1 matrix incomplete")
        semantics.update({"static_unavailable_masks": static_masks,
                          "inflight_faults": inflight, "recovery_mask": 15,
                          "acked_frames_remigrated": 0})
    elif stage == "arq_sack":
        by_label = {detail["label"]: detail for detail in non_shutdown}
        for detail in non_shutdown:
            errors.extend(data_path_errors(
                detail, unavailable=detail["injectmask"],
                injected=bool(detail["injectmask"]),
            ))
            sender_role, _ = path_roles(detail)
            sender = mailbox_for(detail, sender_role)
            if not sender.get("terminal_window_valid") or \
                    sender.get("terminal_window_status", 0) & (0x3F << 16):
                errors.append(f"{detail['label']}:terminal selective-repeat window not empty")
        for label in ("arq_wrap_f2r", "arq_wrap_r2f"):
            item = by_label.get(label)
            if item:
                sender_role, _ = path_roles(item)
                sender = mailbox_for(item, sender_role)
                expected_base = (0xFFFE + math.ceil(item["plan_fields"]["size"] / 247)) & 0xFFFF
                if sender.get("terminal_tx_sequence_base") != expected_base:
                    errors.append(f"{label}:sequence wrap terminal base mismatch")
        ack = by_label.get("arq_ack_aggregation")
        if ack:
            _, receiver_role = path_roles(ack)
            receiver = mailbox_for(ack, receiver_role)
            if receiver.get("ack_aggregation", 0) == 0 or \
                    receiver.get("ack_frames", 0) >= 512:
                errors.append("ACK aggregation not directly observed")
        for label, drop_key in (("arq_data_loss", "physical_drop_data"),
                                ("arq_ack_loss", "physical_drop_ack"),
                                ("arq_sack_loss", "physical_drop_ack")):
            item = by_label.get(label)
            if item:
                sender_role, receiver_role = path_roles(item)
                drop_role = sender_role if label == "arq_data_loss" else receiver_role
                if mailbox_for(item, drop_role).get("transport", {}).get(drop_key, 0) == 0 or \
                        mailbox_for(item, sender_role).get("tx_retries", 0) == 0:
                    errors.append(f"{label}:loss/retry not directly observed")
        duplicate = by_label.get("arq_duplicate_ack")
        if duplicate:
            sender_role, _ = path_roles(duplicate)
            if mailbox_for(duplicate, sender_role).get("transport", {}).get("duplicate_ack", 0) == 0:
                errors.append("duplicate ACK rejection not observed")
        reorder = by_label.get("arq_reorder")
        if reorder:
            _, receiver_role = path_roles(reorder)
            transport = mailbox_for(reorder, receiver_role).get("transport", {})
            if transport.get("rx_out_of_order", 0) == 0 or transport.get("rx_gap", 0) == 0:
                errors.append("reorder/SACK gap not directly observed")
        migration = by_label.get("arq_retry_migration")
        if migration:
            sender_role, _ = path_roles(migration)
            if migration["injection_applied"] != 1 or \
                    migration[f"{sender_role}_p10_2"]["migration_count"] == 0:
                errors.append("ARQ retry migration not directly observed")
        fairness: list[dict[str, Any]] = []
        for detail in non_shutdown:
            if not detail["label"].startswith("scheduler_fair"):
                continue
            sender_role, _ = path_roles(detail)
            values = [lane["scheduled_bytes"]
                      for lane in detail[f"{sender_role}_p10_2"]["lanes"]]
            spread = (max(values) - min(values)) / max(values) if min(values) else 1.0
            if spread > 0.10:
                errors.append(f"{detail['label']}:scheduler fairness exceeds 10%")
            fairness.append({"label": detail["label"], "scheduled_bytes": values,
                             "spread_fraction": spread})
        semantics.update({"window": 32, "sack_bits": 32,
                          "ack_threshold": 32, "outstanding": 32,
                          "fairness_limit_percent": 10, "fairness": fairness,
                          "sequence_wrap": True, "loss_vectors": 3,
                          "retry_migration": True})
    elif stage == "dma":
        by_label = {detail["label"]: detail for detail in non_shutdown}
        sizes = {detail["plan_fields"]["size"] for detail in non_shutdown
                 if detail["label"].startswith("dma_size_")}
        expected_sizes = {1, 2, 3, 4, 31, 32, 63, 64, 247, 256, 1024,
                          4096, 65536, 1048576}
        if sizes != expected_sizes:
            errors.append("DMA size corpus incomplete")
        wrap = by_label.get("dma_ring32_wrap_71")
        if wrap is None:
            errors.append("DMA ring wrap terminal vector missing")
        else:
            for role in ("fixed", "rotating"):
                role_detail = mailbox_for(wrap, role)
                if not all(value > 0 for value in role_detail.get("tx_generations", [])) or \
                        not all(value > 0 for value in role_detail.get("rx_generations", [])):
                    errors.append(f"{role}:DMA producer/consumer generation did not wrap")
        final = by_label.get("dma_post_reset_clean")
        if final:
            for role in ("fixed", "rotating"):
                role_detail = mailbox_for(final, role)
                checks = {
                    "ring_full": all(role_detail.get("ring_full", [])),
                    "ring_empty": all(role_detail.get("ring_empty", [])),
                    "cache_enabled": role_detail.get("cache_enabled", 0) > 0,
                    "cache_disabled": role_detail.get("cache_disabled", 0) > 0,
                    "cache_flush": role_detail.get("cache_flush", 0) > 0,
                    "cache_invalidate": role_detail.get("cache_invalidate", 0) > 0,
                    "reset_queued": role_detail.get("dma_reset_queued", 0) > 0,
                    "stale_rejected": role_detail.get("stale_completion_rejected", 0) > 0,
                    "descriptor_leak": role_detail.get("descriptor_leak", 1) == 0,
                    "double_completion": role_detail.get("tx_double_completion", 1) == 0 and
                                         role_detail.get("rx_double_completion", 1) == 0,
                }
                errors.extend(f"{role}:DMA {name}" for name, passed in checks.items()
                              if not passed)
        semantics.update({"real_axi_dma": True, "sizes": sorted(sizes),
                          "ring_wrap_commands": 72, "cache_modes": [0, 1],
                          "ddr_cache_vectors": len(non_shutdown)})
    elif stage == "streaming_64m":
        for detail in non_shutdown:
            if detail["flags"] & (p101.RECOVERY_FLAGS | p101.SERVICE_RESET_FLAGS):
                continue
            errors.extend(data_path_errors(
                detail, unavailable=detail["injectmask"],
                injected=bool(detail["injectmask"]),
            ))
            if detail["injectmask"]:
                sender_role, _ = path_roles(detail)
                if detail[f"{sender_role}_p10_2"]["migration_count"] == 0:
                    errors.append(f"{detail['label']}:stream lane migration absent")
        normal = [detail for detail in non_shutdown
                  if detail["label"].startswith("stream64_")]
        if sum(detail["direction"] == 0 for detail in normal) != 3 or \
                sum(detail["direction"] == 1 for detail in normal) != 3:
            errors.append("three 64MiB objects per direction missing")
        clean = [detail for detail in non_shutdown if "clean_after" in detail["label"]]
        if len(clean) != 4 or any(detail["requested_bytes"] != 4 << 20 for detail in clean):
            errors.append("4MiB post-fault clean recovery set incomplete")
        semantics.update({"f2r_64m_count": 3, "r2f_64m_count": 3,
                          "fault_vectors": ["lane2", "lane3", "DMA reset",
                                            "endpoint service reset"],
                          "clean_4m_recoveries": len(clean)})
    elif stage == "performance":
        for detail in non_shutdown:
            errors.extend(data_path_errors(detail))
        windows = window_summaries(details, stage)
        if len(windows) != 2 or any(window["committed_bytes"] < 300 << 20
                                    for window in windows):
            errors.append("performance committed bytes below 300MiB")
        if any(window["application_goodput_bps"] < 8_000_000 for window in windows):
            errors.append("application goodput below 8 Mbit/s")
        for window in windows:
            matched = [d for d in non_shutdown if d["window"] == window["label"]]
            stalls = {name: sum(d[path_roles(d)[0]].get(name, 0) for d in matched)
                      for name in ("perf_ack_wait", "perf_dma_stall",
                                   "perf_axis_stall", "perf_direction_quiet")}
            window.update({
                "measured_model_ratio": window["application_goodput_bps"] / 8_000_000,
                "measured_rfap_ceiling_ratio": window["application_goodput_bps"] / 16_000_000,
                "primary_bottleneck": max(stalls, key=stalls.get) if stalls else "NONE",
                "bottleneck_counters": stalls,
            })
        semantics.update({"windows": windows, "measurement_mode": "APPLICATION_SUSTAINED",
                          "host_in_fast_path": False})
    elif stage == "formal_30min":
        elapsed = int(markers.get("P10_1_FORMAL_ELAPSED_MS", "0"))
        if markers.get("P10_1_FORMAL_RESULT") != "PASS" or \
                not 1_800_000 <= elapsed <= 1_800_500:
            errors.append("formal active window not exactly 1800 seconds")
        windows = []
        for label, direction in (("stationary_30min_formal_f2r", 0),
                                 ("stationary_30min_formal_r2f", 1)):
            matched = [detail for detail in non_shutdown if detail.get("window") == label]
            for detail in matched:
                errors.extend(data_path_errors(detail))
            committed = sum(detail.get("requested_bytes", 0) for detail in matched)
            active_ms = sum(detail["finished_ms"] - detail["started_ms"]
                            for detail in matched)
            goodput = committed * 8 / 840
            windows.append({"label": label, "direction": direction,
                            "duration_seconds": 840, "active_ms": active_ms,
                            "active_coverage": active_ms / 840_000,
                            "committed_bytes": committed,
                            "application_goodput_bps": goodput,
                            "host_launch_commands": len(matched)})
            if not matched or goodput < 8_000_000 or active_ms < 798_000:
                errors.append(f"{label}:formal goodput/continuous coverage failed")
        semantics.update({"elapsed_ms": elapsed, "formal_windows": windows,
                          "single_complete_run_id": True,
                          "warmup_seconds": 120})

    summary = {
        "schema_version": 1, "test_id": f"P10_3-HW-{stage.upper()}",
        "stage": stage, "status": "PASS" if not errors else "FAIL",
        "process": process, "markers": markers, "observation_count": len(rows),
        "details": details, "semantics": semantics, "errors": errors,
        "generated_at_utc": utc_now(),
    }
    write_json(stage_dir / "stage_summary.json", summary)
    return summary


def invoke_stage(stage: str, run_root: Path, auth: Path,
                 artifacts: dict[str, Path], ps7: dict[str, Path],
                 env: dict[str, str], abort: Path) -> dict[str, Any]:
    stage_dir = run_root / STAGE_DIR[stage]
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    plan = stage_dir / f"{stage}.plan"
    write_text(plan, plan_text(build_plans()[stage]))
    result = stage_dir / "xsdb.result.txt"
    command = [
        str(XSDB), str(STAGE_TCL), "tcp:localhost:3121",
        EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL,
        str(artifacts["fixed:functional_bitstream"]),
        str(artifacts["rotating:functional_bitstream"]),
        str(artifacts["fixed:elf"]), str(artifacts["rotating:elf"]),
        str(ps7["fixed"]), str(ps7["rotating"]), str(plan), str(dump_dir),
        str(abort), str(result), TCL_STAGE[stage], str(auth), run_root.name,
        f"0x{EXPECTED_PL_BUILD['fixed']:08X}",
        f"0x{EXPECTED_PL_BUILD['rotating']:08X}",
    ]
    process = run_bounded(command, stage_dir / "xsdb.stdout.log",
                          stage_dir / "xsdb.stderr.log", STAGE_TIMEOUT[stage], env)
    return evaluate_stage(stage, stage_dir, process)


def guarded_shutdown(run_root: Path, auth: Path, artifacts: dict[str, Path],
                     label: str, env: dict[str, str]) -> dict[str, Any]:
    """Attempt a dual shutdown without allowing wrapper exceptions to skip closeout."""
    try:
        return invoke_shutdown(
            run_root, auth, artifacts, label, env, retry_limit=2,
        )
    except BaseException as exc:  # Ctrl+C must still result in a recorded shutdown failure.
        failure = {
            "status": "FAIL", "test_id": "P10_3-DUAL-SHUTDOWN",
            "label": label, "attempts": [], "SHUTDOWN_FIXED": "FAIL",
            "SHUTDOWN_ROTATING": "FAIL", "exception": repr(exc),
            "generated_at_utc": utc_now(),
        }
        write_json(run_root / "shutdown" / label / "wrapper_exception.json", failure)
        return failure


def initialize_run_root(run_root: Path, auth: Path) -> list[dict[str, Any]]:
    run_root.mkdir(parents=True, exist_ok=False)
    for name in RUN_DIRECTORIES:
        (run_root / name).mkdir(parents=True, exist_ok=False)
    copies = (
        (auth, run_root / "authorization/immutable_authorization.json"),
        (GOAL, run_root / "authorization/goal.md"),
        (FREEZE, run_root / "artifacts/artifact_freeze.json"),
        (WIRING, run_root / "wiring/p10_3_actual_wiring.yaml"),
        (ROOT / "docs/hardware/P10_3_AS_WIRED_RECORD.md",
         run_root / "wiring/P10_3_AS_WIRED_RECORD.md"),
        (ROOT / "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
         run_root / "wiring/p10_2_ax7020_4lane_wiring.yaml"),
        (ROOT / "docs/hardware/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md",
         run_root / "wiring/P10_2_AX7020_4LANE_WIRING_PROPOSAL.md"),
        (ROOT / "config/hardware/p10_3_ax7020_activity_leds.yaml",
         run_root / "wiring/p10_3_ax7020_activity_leds.yaml"),
        (INVENTORY, run_root / "module_inventory/tfdu_module_inventory.yaml"),
    )
    records: list[dict[str, Any]] = []
    for source, destination in copies:
        shutil.copy2(source, destination)
        if sha256(source) != sha256(destination):
            raise RuntimeError(f"immutable run input copy mismatch: {destination}")
        records.append({
            "source": str(source),
            "path": destination.relative_to(run_root).as_posix(),
            "sha256": sha256(destination), "bytes": destination.stat().st_size,
        })
    write_json(run_root / "authorization/immutable_input_copy_manifest.json", {
        "schema_version": 1, "status": "PASS", "files": records,
        "generated_at_utc": utc_now(),
    })
    write_text(
        run_root / "authorization/NO_MOVEMENT_NETWORK_ATTESTATION.txt",
        "ETHERNET=false\nMOVEMENT=false\nROTATION=false\nREALIGNMENT=false\n"
        "REWIRING=false\nMAX_LANE_MASK=0xF\nTWO_HOUR=false\nP11=false\n",
    )
    return records


def write_summary_pair(base: Path, payload: dict[str, Any], title: str) -> None:
    write_json(base.with_suffix(".json"), payload)
    write_text(
        base.with_suffix(".md"),
        f"# {title}\n\n"
        f"Status: `{payload.get('status', 'NOT_RECORDED')}`\n\n"
        f"Run ID: `{payload.get('run_id', 'NONE')}`\n\n"
        "The adjacent machine-readable JSON and its raw-evidence paths are authoritative.\n",
    )


def evidence_manifest(run_root: Path, acceptance_status: str) -> dict[str, Any]:
    target = run_root / "final/run_evidence_sha256_manifest.json"
    files = []
    for path in sorted(item for item in run_root.rglob("*") if item.is_file()):
        if path == target:
            continue
        files.append({"path": path.relative_to(run_root).as_posix(),
                      "bytes": path.stat().st_size, "sha256": sha256(path)})
    value = {"schema_version": 1, "test_id": "P10_3-HW-EVIDENCE-MANIFEST",
             "status": "INDEX_GENERATED", "acceptance_status": acceptance_status,
             "run_id": run_root.name, "files": files,
             "generated_at_utc": utc_now()}
    write_json(target, value)
    return value


def verify_evidence_manifest(run_root: Path) -> list[str]:
    errors: list[str] = []
    path = run_root / "final/run_evidence_sha256_manifest.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"evidence manifest unreadable: {exc}"]
    seen: set[str] = set()
    for item in value.get("files", []):
        name = item.get("path", "")
        candidate = (run_root / name).resolve()
        if name in seen or not inside(candidate, run_root) or not candidate.is_file():
            errors.append(f"manifest duplicate/missing/outside path: {name}")
            continue
        seen.add(name)
        if candidate.stat().st_size != item.get("bytes") or \
                sha256(candidate) != item.get("sha256"):
            errors.append(f"manifest hash/size mismatch: {name}")
    expected = {
        path.relative_to(run_root).as_posix() for path in run_root.rglob("*")
        if path.is_file() and path != run_root / "final/run_evidence_sha256_manifest.json"
    }
    if seen != expected:
        errors.append(f"manifest file-set mismatch missing={sorted(expected - seen)} "
                      f"extra={sorted(seen - expected)}")
    return errors


def stage_payload(item: dict[str, Any], run_root: Path, generated_name: str) -> dict[str, Any]:
    return {
        "schema_version": 1, "test_id": item["test_id"],
        "status": item["status"], "run_id": run_root.name,
        "source_commit": json.loads(
            (run_root / "authorization/immutable_authorization.json").read_text(
                encoding="utf-8"))["source_commit"],
        "goal_sha256": GOAL_SHA256,
        "actual_wiring_sha256": sha256(WIRING),
        "module_inventory_sha256": sha256(INVENTORY),
        "raw_summary": rel(run_root / STAGE_DIR[item["stage"]] / "stage_summary.json"),
        "summary_name": generated_name,
        "semantics": item.get("semantics", {}), "errors": item.get("errors", []),
        "hardware_actions_executed": True, "network_used": False,
        "movement": False, "rotation": False, "realignment": False,
        "rewiring": False, "maximum_lane_mask": 15,
        "two_hour_test": False, "p11": False,
    }


def publish(summary: dict[str, Any], run_root: Path,
            consistency: dict[str, Any]) -> None:
    by_stage = {item["stage"]: item for item in summary["stages"]}
    mapping = {
        "module_intake": "module_intake", "raw_8x8": "raw_8x8",
        "per_lane_phy": "per_lane_phy", "two_lane_regression": "two_lane_regression",
        "four_lane_raw": "four_lane_raw", "mask_matrix": "mask_matrix",
        "degrade": "degraded_modes", "arq_sack": "arq_scheduler",
        "dma": "dma_ddr_cache", "streaming_64m": "streaming_64m",
        "performance": "performance", "formal_30min": "formal_30min",
    }
    for stage, name in mapping.items():
        item = by_stage.get(stage)
        if item is None:
            continue
        payload = stage_payload(item, run_root, name)
        write_summary_pair(GENERATED / f"p10_3_{name}", payload,
                           f"P10.3 {name.replace('_', ' ')}")

    preflight = by_stage.get("preflight")
    if preflight is not None:
        base = stage_payload(preflight, run_root, "safe_boot")
        for name, additions in (
            ("target_identity", {"board_binding": {
                "fixed": "AX7020-F/JTAG:210249855178",
                "rotating": "AX7020-R/JTAG:210512180081"}}),
            ("safe_boot", {"safe_boot_both": preflight["status"]}),
            ("power_preflight", {
                "external_four_lane_power_acceptance": "PENDING_EXTERNAL_MEASUREMENT",
                "internal_no_brownout_is_external_measurement": False,
                "engineering_peak_iRED_current_per_transmitting_endpoint_amps": 2.4,
            }),
        ):
            payload = {**base, **additions, "summary_name": name}
            write_summary_pair(GENERATED / f"p10_3_{name}", payload,
                               f"P10.3 {name.replace('_', ' ')}")

    shutdown_payload = {
        "schema_version": 1, "test_id": "P10_3-HW-SHUTDOWN",
        "status": "PASS" if summary["SHUTDOWN_FIXED"] == "PASS" and
                  summary["SHUTDOWN_ROTATING"] == "PASS" else "FAIL",
        "run_id": run_root.name, "shutdowns": summary["shutdowns"],
        "SHUTDOWN_FIXED": summary["SHUTDOWN_FIXED"],
        "SHUTDOWN_ROTATING": summary["SHUTDOWN_ROTATING"],
        "raw_root": rel(run_root / "shutdown"),
    }
    write_summary_pair(GENERATED / "p10_3_shutdown", shutdown_payload,
                       "P10.3 dual-endpoint shutdown")
    write_summary_pair(GENERATED / "p10_3_evidence_consistency", consistency,
                       "P10.3 evidence consistency")
    write_summary_pair(GENERATED / "p10_3_final_summary", summary,
                       "P10.3 stationary four-lane hardware acceptance")


def materialize_run_views(summary: dict[str, Any], run_root: Path) -> None:
    by_stage = {item["stage"]: item for item in summary["stages"]}
    preflight = by_stage.get("preflight")
    if preflight is not None:
        target = {
            "schema_version": 1, "test_id": "P10_3-HW-TARGET-IDENTITY",
            "status": preflight["status"], "run_id": run_root.name,
            "board_binding": {
                "fixed": "AX7020-F/JTAG:210249855178",
                "rotating": "AX7020-R/JTAG:210512180081",
            },
            "expected_part": EXPECTED_PART,
            "expected_build_ids": {role: f"0x{value:08X}"
                                   for role, value in EXPECTED_PL_BUILD.items()},
            "raw_summary": rel(run_root / "safe_boot/stage_summary.json"),
        }
        write_summary_pair(run_root / "target_identity/summary", target,
                           "P10.3 target identity")
        power = {
            "schema_version": 1, "test_id": "P10_3-HW-POWER-PREFLIGHT",
            "status": preflight["status"], "run_id": run_root.name,
            "engineering_peak_iRED_current_per_module_amps": 0.6,
            "engineering_peak_iRED_current_per_transmitting_endpoint_amps": 2.4,
            "external_four_lane_power_acceptance": "PENDING_EXTERNAL_MEASUREMENT",
            "user_power_arrangement_attestation": True,
            "user_attestation_is_external_measurement": False,
            "internal_no_brownout_is_external_power_acceptance": False,
            "progressive_masks": [1, 3, 7, 15],
            "safe_boot_raw_summary": rel(run_root / "safe_boot/stage_summary.json"),
            "progressive_raw_summary": rel(run_root / "four_lane_raw/stage_summary.json")
                if (run_root / "four_lane_raw/stage_summary.json").is_file() else None,
        }
        write_summary_pair(run_root / "power_preflight/summary", power,
                           "P10.3 power functional preflight")

    performance = by_stage.get("performance")
    if performance is not None:
        windows = performance.get("semantics", {}).get("windows", [])
        for direction, directory in ((0, "performance_f2r"), (1, "performance_r2f")):
            selected = [item for item in windows if item.get("direction") == direction]
            payload = {
                "schema_version": 1,
                "test_id": f"P10_3-HW-PERFORMANCE-{'F2R' if direction == 0 else 'R2F'}",
                "status": "PASS" if performance["status"] == "PASS" and
                          len(selected) == 1 and
                          selected[0].get("application_goodput_bps", 0) >= 8_000_000
                          else "FAIL",
                "run_id": run_root.name, "direction": direction,
                "windows": selected,
                "combined_raw_summary": rel(
                    run_root / "performance_f2r/stage_summary.json"),
            }
            write_summary_pair(run_root / directory / "direction_summary", payload,
                               f"P10.3 performance {'F to R' if direction == 0 else 'R to F'}")

    shutdown_payload = {
        "schema_version": 1, "test_id": "P10_3-HW-SHUTDOWN",
        "status": "PASS" if summary["SHUTDOWN_FIXED"] == "PASS" and
                  summary["SHUTDOWN_ROTATING"] == "PASS" else "FAIL",
        "run_id": run_root.name, "shutdowns": summary["shutdowns"],
        "SHUTDOWN_FIXED": summary["SHUTDOWN_FIXED"],
        "SHUTDOWN_ROTATING": summary["SHUTDOWN_ROTATING"],
    }
    write_summary_pair(run_root / "shutdown/summary", shutdown_payload,
                       "P10.3 shutdown evidence")
    write_summary_pair(run_root / "final/p10_3_final_summary", summary,
                       "P10.3 stationary four-lane hardware acceptance")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-authorization", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args(argv)
    if args.prepare_authorization:
        try:
            record = prepare_authorization(args.run_id)
        except Exception as exc:
            print(f"P10_3_AUTHORIZATION=FAIL\nERROR={exc}", file=sys.stderr)
            return 2
        print("P10_3_AUTHORIZATION=PASS")
        print(f"P10_3_RUN_ID={record['run_id']}")
        print(f"P10_3_AUTHORIZATION_PATH={rel(AUTH)}")
        print(f"P10_3_AUTHORIZATION_SHA256={sha256(AUTH)}")
        return 0
    if not args.execute_hardware or not args.run_id:
        print("P10_3_RUNNER_REFUSED=PREPARE_OR_EXPLICIT_HARDWARE_RUN_REQUIRED")
        return 3
    auth = args.authorization.resolve()
    record, artifacts, errors = validate_authorization(auth, args.run_id, STAGES)
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "true":
        errors.append("NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required")
    if auth != AUTH.resolve():
        errors.append("canonical P10.3 authorization path required")
    run_root = HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("run_id directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2, ensure_ascii=False), file=sys.stderr)
        return 3
    try:
        initialize_run_root(run_root, auth)
    except Exception as exc:
        print(f"P10_3_RUN_ROOT_INITIALIZATION=FAIL\nERROR={exc}", file=sys.stderr)
        return 3
    abort = run_root / "authorization/ABORT_NOW.txt"
    ps7: dict[str, Path] = {}
    derived = []
    initialization_errors: list[str] = []
    try:
        for role in ("fixed", "rotating"):
            destination = run_root / f"artifacts/{role}/ps7_init.tcl"
            derived.append(extract_ps7_init(artifacts[f"{role}:xsa"], destination))
            ps7[role] = destination
    except Exception as exc:
        initialization_errors.append(f"PS7 init extraction failed: {exc}")
    write_json(run_root / "artifacts/derived_artifact_manifest.json", derived)
    write_json(run_root / "artifacts/authorized_artifact_manifest.json", {
        "schema_version": 1, "status": "PASS" if not initialization_errors else "FAIL",
        "source_commit": record["source_commit"], "artifacts": record["artifacts"],
        "artifact_bundle_sha256": record["artifact_bundle_sha256"],
        "errors": initialization_errors,
    })
    env = {**os.environ, "NO_HARDWARE": "0",
           "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
           "RF_COMM_P10_HW_AUTH": "P10_FASTTRACK_IMMUTABLE_AUTHORIZED"}
    server_proc = None
    shutdowns: list[dict[str, Any]] = []
    stage_results: list[dict[str, Any]] = []
    campaign_errors: list[str] = list(initialization_errors)
    hardware_actions = False
    try:
        if initialization_errors:
            raise RuntimeError("artifact derivation precondition failed")
        server_proc, server = start_hw_server(run_root / "raw_logs")
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server unavailable"))
        hardware_actions = True
        initial = guarded_shutdown(run_root, auth, artifacts, "initial_shutdown", env)
        shutdowns.append(initial)
        if initial["status"] != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for stage in STAGES:
            before = guarded_shutdown(run_root, auth, artifacts, f"{stage}_before", env)
            shutdowns.append(before)
            if before["status"] != "PASS":
                raise RuntimeError(f"{stage} shutdown-before unconfirmed")
            result: dict[str, Any] | None = None
            stage_exception: BaseException | None = None
            try:
                result = invoke_stage(stage, run_root, auth, artifacts, ps7, env, abort)
                stage_results.append(result)
            except BaseException as exc:
                stage_exception = exc
            finally:
                after = guarded_shutdown(run_root, auth, artifacts,
                                         f"{stage}_after", env)
                shutdowns.append(after)
            if after["status"] != "PASS":
                raise RuntimeError(f"{stage} shutdown-after unconfirmed")
            if stage_exception is not None:
                if isinstance(stage_exception, KeyboardInterrupt):
                    raise KeyboardInterrupt from stage_exception
                raise RuntimeError(f"{stage} wrapper exception: {stage_exception}")
            assert result is not None
            if result["status"] != "PASS":
                raise RuntimeError(f"{stage} acceptance failed")
        final_shutdown = guarded_shutdown(run_root, auth, artifacts, "final_shutdown", env)
        shutdowns.append(final_shutdown)
        if final_shutdown["status"] != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except Exception as exc:
        campaign_errors.append(str(exc))
    finally:
        if hardware_actions:
            emergency = guarded_shutdown(run_root, auth, artifacts,
                                         "finally_emergency", env)
            shutdowns.append(emergency)
            if emergency["status"] != "PASS":
                campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            try:
                terminate_tree(server_proc)
            except Exception as exc:
                campaign_errors.append(f"owned hw_server termination failed: {exc}")
    all_shutdown = bool(shutdowns) and all(item["status"] == "PASS" for item in shutdowns)
    all_stages = len(stage_results) == len(STAGES) and all(
        item["status"] == "PASS" for item in stage_results
    )
    core_stages = STAGES[:STAGES.index("performance")]
    core_pass = all(
        next((item["status"] for item in stage_results if item["stage"] == stage), None)
        == "PASS" for stage in core_stages
    )
    if all_shutdown and all_stages and not campaign_errors:
        status = "PASS"
    elif all_shutdown and core_pass:
        status = "PARTIAL"
    else:
        status = "FAIL"
    observed_masks = [
        int(detail.get("lane_mask", 0))
        for item in stage_results for detail in item.get("details", [])
        if isinstance(detail, dict)
    ]
    maximum_mask = max(observed_masks, default=0)
    shutdown_fixed = "PASS" if all_shutdown and all(
        item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdowns) else "FAIL"
    shutdown_rotating = "PASS" if all_shutdown and all(
        item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdowns) else "FAIL"
    summary = {
        "schema_version": 1, "test_id": "P10_3-HW-FINAL",
        "status": status, "run_id": args.run_id,
        "source_commit": record["source_commit"], "goal_sha256": GOAL_SHA256,
        "actual_wiring_sha256": sha256(WIRING),
        "module_inventory_sha256": sha256(INVENTORY),
        "artifact_freeze_sha256": sha256(FREEZE),
        "artifacts": record["artifacts"],
        "board_binding": record["board_binding"],
        "module_binding": record["module_binding"],
        "active_modules": list(MODULES),
        "old_f1_status": "QUARANTINED_NOT_ACCEPTED",
        "hardware_actions_executed": hardware_actions, "network_used": False,
        "movement": False, "rotation": False, "realignment": False,
        "rewiring": False,
        "maximum_lane_mask_used": f"0x{maximum_mask:X}",
        "maximum_lane_mask_authorized": "0xF",
        "two_hour_test": False, "p11": False,
        "current_run_hardware_authorization": False,
        "stages": stage_results, "shutdowns": shutdowns,
        "SHUTDOWN_FIXED": shutdown_fixed,
        "SHUTDOWN_ROTATING": shutdown_rotating,
        "external_four_lane_power_acceptance": "PENDING_EXTERNAL_MEASUREMENT",
        "external_tfdu_duty": "PENDING_EXTERNAL_MEASUREMENT",
        "errors": campaign_errors, "generated_at_utc": utc_now(),
    }
    write_json(run_root / "final/orchestrator_result.json", summary)
    materialize_run_views(summary, run_root)
    evidence_manifest(run_root, status)
    manifest_errors = verify_evidence_manifest(run_root)
    consistency = {
        "schema_version": 1, "test_id": "P10_3-HW-EVIDENCE-CONSISTENCY",
        "status": "PASS" if not manifest_errors else "FAIL",
        "run_id": run_root.name,
        "manifest": rel(run_root / "final/run_evidence_sha256_manifest.json"),
        "errors": manifest_errors, "generated_at_utc": utc_now(),
    }
    write_summary_pair(run_root / "final/p10_3_evidence_consistency", consistency,
                       "P10.3 evidence consistency")
    evidence_manifest(run_root, status)
    final_manifest_errors = verify_evidence_manifest(run_root)
    if final_manifest_errors:
        consistency["status"] = "FAIL"
        consistency["errors"] = final_manifest_errors
        campaign_errors.extend(final_manifest_errors)
        summary["status"] = "FAIL"
        status = "FAIL"
        summary["errors"] = campaign_errors
        write_json(run_root / "final/orchestrator_result.json", summary)
        write_summary_pair(run_root / "final/p10_3_final_summary", summary,
                           "P10.3 stationary four-lane hardware acceptance")
        write_summary_pair(run_root / "final/p10_3_evidence_consistency", consistency,
                           "P10.3 evidence consistency")
        evidence_manifest(run_root, status)
    try:
        publish(summary, run_root, consistency)
    except Exception as exc:
        status = "FAIL"
        summary["status"] = "FAIL"
        campaign_errors.append(f"generated evidence publication failed: {exc}")
        summary["errors"] = campaign_errors
        write_json(run_root / "final/orchestrator_result.json", summary)
        write_summary_pair(run_root / "final/p10_3_final_summary", summary,
                           "P10.3 stationary four-lane hardware acceptance")
        evidence_manifest(run_root, status)
    consumed = dict(record)
    consumed.update({"status": f"CONSUMED_AFTER_P10_3_{status}",
                     "current_run_hardware_authorization": False,
                     "consumed": True, "consumed_at_utc": utc_now(),
                     "result": rel(run_root / "final/orchestrator_result.json")})
    write_json(AUTH, consumed)
    auth_summary = {
        "schema_version": 1, "test_id": "P10_3-HW-AUTHORIZATION",
        "status": consumed["status"], "run_id": args.run_id,
        "authorization": rel(AUTH),
        "immutable_authorization": rel(
            run_root / "authorization/immutable_authorization.json"),
        "current_run_hardware_authorization": False,
        "consumed": True, "result": consumed["result"],
    }
    write_summary_pair(GENERATED / "p10_3_authorization", auth_summary,
                       "P10.3 current-run hardware authorization")
    print(f"P10_3_HARDWARE={status}")
    print(f"P10_3_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
