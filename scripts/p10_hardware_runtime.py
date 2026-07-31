#!/usr/bin/env python3
"""Fail-closed P10 dual-AX7020 stationary two-lane hardware campaign.

The runner is deliberately inert unless an immutable, committed current-run
authorization is supplied together with ``--execute-hardware`` and
``NO_HARDWARE=0``.  Every XSDB stage is bracketed by independent programming
of both role-specific shutdown images; the same dual shutdown is attempted on
normal exit, stage failure, timeout, Ctrl+C, and outer-wrapper failure.
Ethernet, motion, board power cycling, rewiring, and lane masks above 0x3 are
not implemented.

require-user-hw-authorization: the FastTrack goal, immutable machine record,
explicit CLI enable, and environment gate are all mandatory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md"
WIRING = ROOT / "config/hardware/p10_active_wiring.yaml"
IDENTITY = ROOT / "config/hardware/p10_jtag_identity_inventory.json"
OFFLINE_MANIFEST = ROOT / "evidence/generated/p10_offline_artifact_manifest.json"
GENERATED = ROOT / "evidence/generated"
HW_ROOT = ROOT / "evidence/hardware/p10"
VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
HW_SERVER = Path(r"D:\Xilinx\Vivado\2023.1\bin\hw_server.bat")
XSDB = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsdb.bat")
SHUTDOWN_TCL = ROOT / "scripts/hw/p10_program_dual_shutdown.tcl"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
AUTH_GENERATOR = ROOT / "scripts/create_p10_fasttrack_authorization.py"
DEFAULT_AUTH = ROOT / "config/p10_fasttrack_current_run_authorization.json"

EXPECTED_SCOPE = "P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET"
EXPECTED_BRANCH = "p10/ax7020-dual-node-2lane"
EXPECTED_PART = "xc7z020clg400-2"
EXPECTED_FIXED_SERIAL = "210249855178"
EXPECTED_ROTATING_SERIAL = "210512180081"
EXPECTED_FIXED_TARGET = "localhost:3121/xilinx_tcf/Digilent/210249855178"
EXPECTED_ROTATING_TARGET = "localhost:3121/xilinx_tcf/Digilent/210512180081"
EXPECTED_GOAL_SHA256 = "b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603"
EXPECTED_REGISTER_MAP_VERSION = 0x09000003
EXPECTED_REGISTER_MAP_HASH_LOW = 0xCF35F13A
EXPECTED_CAPABILITIES = 0xF7204221
EXPECTED_MAILBOX_MAGIC = 0x424D3950
EXPECTED_MAILBOX_SCHEMA = 5
EXPECTED_ROLE = {
    "fixed": {"firmware": 0x50313046, "build": 0x50313046,
              "profile": 0x702000F0, "local_indices": (0, 1)},
    "rotating": {"firmware": 0x50313052, "build": 0x50313052,
                 "profile": 0x702000A0, "local_indices": (2, 3)},
}
P10_DUTY_WINDOW_CYCLES = 64_000
P10_DUTY_HARD_MAX_HIGH_CYCLES = 12_799
P10_DUTY_TARGET_MAX_HIGH_CYCLES = 11_520
PL_SNAPSHOT_START = 116
TERMINAL_WINDOW_START = 252
TERMINAL_WINDOW_VALID = 0x5457494E
RUN_RE = re.compile(r"^p10_[A-Za-z0-9_.-]+$")
STAGE_RE = re.compile(r"^P10-(?:[A-J]|DIAG)$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
ALL_FORMAL_STAGES = tuple(f"P10-{letter}" for letter in "ABCDEFGHIJ")
P10_J_SOAK_PLAN = ("SOAK", "stationary_30min", "1800")
P10_J_SOAK_SIZES = (4096, 65536, 1048576)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("ascii")).hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def parse_markers(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.fullmatch(r"[A-Z0-9_]+", key):
            result[key] = value
    return result


@dataclass(frozen=True)
class Case:
    label: str
    command: int
    expected_status: int = 0
    flags: int = 0
    lane: int = 0
    direction: int = 0
    rate: int = 0
    weights: int = 0x0101
    size: int = 0
    ring: int = 8
    cache: int = 0
    txoff: int = 0
    rxoff: int = 0
    timeout: int = 10_000
    session: int = 0xA0100001
    path: int = 10
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

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.label):
            raise ValueError(f"unsafe case label: {self.label}")
        if self.lane not in range(4) or self.unavailable not in range(4) or \
                self.injectmask not in range(4):
            raise ValueError(f"lane mask outside 0x0..0x3: {self.label}")
        if self.direction not in {0, 1} or self.rate not in {0, 1, 2}:
            raise ValueError(f"direction/rate invalid: {self.label}")
        if not 1 <= self.timeout <= 1_800_000:
            raise ValueError(f"timeout outside authorization: {self.label}")
        if self.command in {2, 3, 12, 13} and self.lane not in {1, 2, 3}:
            raise ValueError(f"transmit-capable command lacks lane mask: {self.label}")
        if self.command in {3, 13} and not 1 <= self.size <= 0x04000000:
            raise ValueError(f"object size invalid: {self.label}")

    def plan_line(self) -> str:
        self.validate()
        values = ["CASE", self.label, self.command, self.expected_status,
                  self.flags, self.lane, self.direction, self.rate,
                  self.weights, self.size, self.ring, self.cache, self.txoff,
                  self.rxoff, self.timeout, self.session, self.path,
                  self.object, self.dropdata, self.dropack, self.unavailable,
                  self.rawtarget, self.spacing, self.stale, self.initialseq,
                  self.faultflags, self.idle, self.injectmask,
                  self.injectdelay]
        return " ".join(str(value) for value in values)


PlanItem = Case | tuple[str, ...]


def object_case(label: str, *, lane: int, direction: int, size: int,
                object_id: int, rate: int = 2, ring: int = 32,
                cache: int = 1, weights: int = 0x0101,
                timeout: int = 120_000, initial: int = 0, fault: int = 0,
                dropdata: int = 0, dropack: int = 0,
                unavailable: int = 0, txoff: int = 0, rxoff: int = 0,
                injectmask: int = 0, injectdelay: int = 0,
                rfap: int = 0, session: int = 0xA0100001,
                path: int = 10) -> Case:
    if rfap not in {0, 1, 2}:
        raise ValueError("RFAP mode must be 0, 1, or 2")
    rfap_flag = 4 if rfap == 1 else 8 if rfap == 2 else 0
    return Case(label=label, command=3, flags=2 | rfap_flag,
                lane=lane, direction=direction, rate=rate,
                weights=weights, size=size, ring=ring, cache=cache,
                txoff=txoff, rxoff=rxoff, timeout=timeout,
                session=session, path=path, object=object_id,
                dropdata=dropdata, dropack=dropack,
                unavailable=unavailable, initialseq=initial,
                faultflags=fault, injectmask=injectmask,
                injectdelay=injectdelay)


def build_plans() -> dict[str, list[PlanItem]]:
    plans: dict[str, list[PlanItem]] = {}
    plans["P10-A"] = [
        Case("bringup_identity", 1),
        Case("bringup_receive_only_5000ms", 11, idle=5000, timeout=15_000),
        Case("bringup_ring_depth_8", 4, ring=8),
        Case("bringup_ring_depth_32", 4, ring=32),
        Case("bringup_dma_reset_idle", 5, ring=32),
        Case("bringup_dma_reset_queued", 6, lane=3, direction=0, rate=2,
             size=4096, ring=32, cache=1, timeout=30_000),
        Case("bringup_pl_soft_reset", 8),
        Case("bringup_identity_after_reset", 1),
    ]

    raw: list[PlanItem] = []
    for lane_mask, lane_name in ((1, "lane0"), (2, "lane1")):
        for direction, direction_name in ((0, "f_to_r"), (1, "r_to_f")):
            for count in (64, 1024):
                raw.append(Case(f"raw_{lane_name}_{direction_name}_{count}",
                                2, lane=lane_mask, direction=direction,
                                rawtarget=count, spacing=1024,
                                timeout=30_000))
    plans["P10-B"] = raw

    rate: list[PlanItem] = []
    oid = 0xC000
    for lane_mask, lane_name in ((1, "lane0"), (2, "lane1")):
        for direction, direction_name in ((0, "f_to_r"), (1, "r_to_f")):
            rate.extend([
                object_case(f"rate4_{lane_name}_{direction_name}_short",
                            lane=lane_mask, direction=direction, size=31,
                            object_id=0x40000000 | oid, timeout=30_000),
                object_case(f"rate4_{lane_name}_{direction_name}_prbs247",
                            lane=lane_mask, direction=direction, size=247,
                            object_id=oid + 1, timeout=30_000),
                object_case(f"rate4_{lane_name}_{direction_name}_counter247",
                            lane=lane_mask, direction=direction, size=247,
                            object_id=0x30000000 | (oid + 2), timeout=30_000),
                object_case(f"rate4_{lane_name}_{direction_name}_100f",
                            lane=lane_mask, direction=direction, size=247 * 100,
                            object_id=oid + 3, timeout=60_000),
                object_case(f"rate4_{lane_name}_{direction_name}_10000f",
                            lane=lane_mask, direction=direction,
                            size=247 * 10_000, object_id=oid + 4,
                            timeout=240_000),
            ])
            oid += 0x10
    for direction, name in ((0, "f_to_r"), (1, "r_to_f")):
        rate.append(object_case(f"rate4_two_lane_{name}_10000f", lane=3,
                                direction=direction, size=247 * 10_000,
                                object_id=oid, timeout=240_000))
        oid += 1
    plans["P10-C"] = rate

    plans["P10-D"] = [
        object_case("sr_lane0_f_to_r", lane=1, direction=0,
                    size=247 * 128, object_id=0xD000),
        object_case("sr_lane0_r_to_f", lane=1, direction=1,
                    size=247 * 128, object_id=0xD001),
        object_case("sr_lane1_f_to_r", lane=2, direction=0,
                    size=247 * 128, object_id=0xD002),
        object_case("sr_lane1_r_to_f", lane=2, direction=1,
                    size=247 * 128, object_id=0xD003),
        object_case("sr_wrap_f_to_r", lane=3, direction=0,
                    size=247 * 96, object_id=0xD004, initial=0xFFFE),
        object_case("sr_wrap_r_to_f", lane=3, direction=1,
                    size=247 * 96, object_id=0xD005, initial=0xFFFE),
        object_case("sack_ack_aggregation", lane=3, direction=0,
                    size=247 * 256, object_id=0xD006),
        object_case("loss_recovery_data", lane=3, direction=1,
                    size=247 * 256, object_id=0xD007, dropdata=1),
        object_case("loss_recovery_ack", lane=3, direction=0,
                    size=247 * 256, object_id=0xD008, dropack=1),
        object_case("duplicate_recovery", lane=3, direction=1,
                    size=247 * 256, object_id=0xD009, fault=1 << 5),
        object_case("reorder_recovery", lane=3, direction=0,
                    size=247 * 256, object_id=0xD00A, fault=1 << 6),
        object_case("stale_session_rejection", lane=3, direction=1,
                    size=247 * 96, object_id=0xD00B, fault=1 << 0),
        object_case("stale_path_rejection", lane=3, direction=0,
                    size=247 * 96, object_id=0xD00C, fault=1 << 1),
    ]

    dma: list[PlanItem] = [
        Case("dma_ring_depth_8", 4, ring=8),
        Case("dma_ring_depth_32", 4, ring=32),
    ]
    for index, size in enumerate((1, 2, 3, 4, 31, 32, 63, 64, 247,
                                  256, 1024, 4096, 65536, 1048576)):
        dma.append(object_case(f"dma_size_{size}", lane=3,
                               direction=index & 1, size=size,
                               object_id=0xE000 + index))
    dma.extend([
        object_case("dma_cache_off_fixed_tx", lane=3, direction=0,
                    size=65536, object_id=0xE080, cache=0),
        object_case("dma_cache_off_rotating_tx", lane=3, direction=1,
                    size=65536, object_id=0xE081, cache=0),
        object_case("dma_misaligned", lane=3, direction=0, size=4096,
                    object_id=0xE082, txoff=1, rxoff=3),
    ])
    for index in range(36):
        dma.append(object_case(f"dma_ring32_wrap_{index:02d}", lane=3,
                               direction=index & 1, size=1,
                               object_id=0xE100 + index, timeout=30_000))
    dma.extend([
        Case("dma_reset_idle", 5, ring=32),
        Case("dma_reset_queued", 6, lane=3, direction=0, rate=2,
             size=4096, ring=32, cache=1, timeout=30_000),
        Case("dma_pl_soft_reset", 8),
        Case("dma_stale_completion", 9, stale=0xDEADBEEF),
        object_case("dma_post_reset_clean", lane=3, direction=1,
                    size=65536, object_id=0xE1FE),
    ])
    plans["P10-E"] = dma

    objects: list[PlanItem] = []
    oid = 0xF000
    for size, suffix in ((4096, "4k"), (65536, "64k"),
                         (1048576, "1m"), (16 * 1048576, "16m")):
        for direction, name in ((0, "f_to_r"), (1, "r_to_f")):
            objects.append(object_case(f"dual_ps_{suffix}_{name}", lane=3,
                                       direction=direction, size=size,
                                       object_id=oid, timeout=600_000,
                                       rfap=2, session=0xA01000F0,
                                       path=0x10))
            oid += 1
    plans["P10-F"] = objects

    plans["P10-G"] = [
        object_case("reboot_baseline", lane=3, direction=0, size=65536,
                    object_id=0x10000),
        ("REBOOT", "fixed", "fixed_ps_reboot"),
        Case("fixed_reboot_identity", 1),
        object_case("fixed_reboot_clean", lane=3, direction=1, size=65536,
                    object_id=0x10001),
        ("REBOOT", "rotating", "rotating_ps_reboot"),
        Case("rotating_reboot_identity", 1),
        object_case("rotating_reboot_clean", lane=3, direction=0,
                    size=65536, object_id=0x10002),
        ("REBOOT", "rotating", "rotating_first_order"),
        ("REBOOT", "fixed", "fixed_second_order"),
        object_case("reverse_reboot_order_clean", lane=3, direction=1,
                    size=65536, object_id=0x10003),
        Case("recovery_pl_soft_reset", 8),
        object_case("post_pl_reset_clean", lane=3, direction=0,
                    size=65536, object_id=0x10004),
        Case("recovery_dma_reset", 5, ring=32),
        object_case("post_dma_reset_clean", lane=3, direction=1,
                    size=65536, object_id=0x10005),
    ]

    plans["P10-H"] = [
        object_case("sched_lane0_f_to_r", lane=1, direction=0,
                    size=247 * 256, object_id=0x11000),
        object_case("sched_lane0_r_to_f", lane=1, direction=1,
                    size=247 * 256, object_id=0x11001),
        object_case("sched_lane1_f_to_r", lane=2, direction=0,
                    size=247 * 256, object_id=0x11002),
        object_case("sched_lane1_r_to_f", lane=2, direction=1,
                    size=247 * 256, object_id=0x11003),
        object_case("sched_equal_f_to_r", lane=3, direction=0,
                    size=247 * 512, object_id=0x11004, weights=0x0101),
        object_case("sched_equal_r_to_f", lane=3, direction=1,
                    size=247 * 512, object_id=0x11005, weights=0x0101),
        object_case("lane0_unavailable", lane=3, direction=0,
                    size=247 * 256, object_id=0x11006, unavailable=1),
        object_case("lane1_unavailable", lane=3, direction=1,
                    size=247 * 256, object_id=0x11007, unavailable=2),
        object_case("retry_migration", lane=3, direction=0,
                    size=247 * 1024, object_id=0x11008, dropdata=1,
                    injectmask=1, injectdelay=10),
        object_case("lane_fault_in_flight", lane=3, direction=1,
                    size=1048576, object_id=0x11009,
                    injectmask=2, injectdelay=100, timeout=180_000),
        object_case("scheduler_recovery", lane=3, direction=0,
                    size=65536, object_id=0x1100A),
    ]

    perf: list[PlanItem] = []
    oid = 0x12000
    for lane in (1, 2, 3):
        for direction in (0, 1):
            for size, suffix in ((4096, "4k"), (1048576, "1m")):
                perf.append(object_case(
                    f"perf_m{lane}_d{direction}_{suffix}", lane=lane,
                    direction=direction, size=size, object_id=oid,
                    timeout=180_000, rfap=2))
                oid += 1
    plans["P10-I"] = perf
    plans["P10-J"] = [("SOAK", "stationary_30min", "1800")]
    plans["P10-DIAG"] = [Case("diagnostic_identity", 1)]
    return plans


def plan_text(items: Iterable[PlanItem]) -> str:
    lines = ["# Immutable P10 paired hardware plan"]
    for item in items:
        if isinstance(item, Case):
            lines.append(item.plan_line())
        else:
            lines.append(" ".join(item))
    return "\n".join(lines) + "\n"


def plan_hashes(stages: Iterable[str]) -> dict[str, str]:
    plans = build_plans()
    return {stage: hash_text(plan_text(plans[stage])) for stage in stages}


def runner_input_hashes() -> dict[str, str]:
    paths = (Path(__file__).resolve(), SHUTDOWN_TCL, STAGE_TCL,
             AUTH_GENERATOR, GOAL, WIRING, IDENTITY, OFFLINE_MANIFEST,
             ROOT / "config/register_map/ir_axi_regs.yaml")
    return {rel(path): sha256(path) for path in paths}


def _artifact_key(record: dict[str, Any]) -> str:
    return f"{record['role']}:{record['kind']}"


def create_authorization_payload(run_id: str, stages: list[str],
                                 source_commit: str) -> dict[str, Any]:
    if not RUN_RE.fullmatch(run_id):
        raise ValueError("invalid P10 run id")
    if not stages or any(not STAGE_RE.fullmatch(stage) for stage in stages):
        raise ValueError("invalid P10 stage authorization")
    manifest = json.loads(OFFLINE_MANIFEST.read_text(encoding="utf-8"))
    artifacts = []
    for item in manifest.get("artifacts", []):
        if item.get("role") in {"fixed", "rotating"} and item.get("kind") in {
                "shutdown_bitstream", "functional_bitstream", "xsa", "elf"}:
            artifacts.append({key: item[key] for key in
                              ("role", "kind", "path", "sha256", "bytes")})
    required = {f"{role}:{kind}" for role in ("fixed", "rotating")
                for kind in ("shutdown_bitstream", "functional_bitstream",
                             "xsa", "elf")}
    if {_artifact_key(item) for item in artifacts} != required:
        raise RuntimeError("offline artifact manifest lacks the exact P10 hardware set")
    return {
        "schema_version": 1,
        "authorization_id": "P10-FASTTRACK-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED",
        "scope": EXPECTED_SCOPE,
        "run_id": run_id,
        "authorized_stages": stages,
        "formal_campaign": stages == list(ALL_FORMAL_STAGES),
        "source_commit": source_commit,
        "branch": EXPECTED_BRANCH,
        "goal": rel(GOAL),
        "goal_sha256": sha256(GOAL),
        "current_run_hardware_authorization": True,
        "authorization_source": "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md",
        "maximum_active_test_seconds": 1800,
        "maximum_lane_mask": 3,
        "lane_masks": [1, 2, 3],
        "network_used": False,
        "ethernet_allowed": False,
        "movement_allowed": False,
        "rotation_allowed": False,
        "rewiring_allowed": False,
        "intentional_power_cycle_allowed": False,
        "fixed_board": {"role": "AX7020-F", "serial": EXPECTED_FIXED_SERIAL,
                        "target": EXPECTED_FIXED_TARGET},
        "rotating_board": {"role": "AX7020-R",
                           "serial": EXPECTED_ROTATING_SERIAL,
                           "target": EXPECTED_ROTATING_TARGET},
        "part": EXPECTED_PART,
        "artifact_manifest": rel(OFFLINE_MANIFEST),
        "artifact_manifest_sha256": sha256(OFFLINE_MANIFEST),
        "artifacts": artifacts,
        "plan_sha256": plan_hashes(stages),
        "runner_input_sha256": runner_input_hashes(),
        "generated_at_utc": utc_now(),
    }


def validate_authorization(path: Path) -> tuple[dict[str, Any],
                                                dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {}, [f"authorization cannot be read: {exc}"]
    expected_scalars = {
        "schema_version": 1,
        "authorization_id": "P10-FASTTRACK-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED",
        "scope": EXPECTED_SCOPE,
        "branch": EXPECTED_BRANCH,
        "goal_sha256": EXPECTED_GOAL_SHA256,
        "current_run_hardware_authorization": True,
        "maximum_active_test_seconds": 1800,
        "maximum_lane_mask": 3,
        "network_used": False,
        "ethernet_allowed": False,
        "movement_allowed": False,
        "rotation_allowed": False,
        "rewiring_allowed": False,
        "intentional_power_cycle_allowed": False,
        "part": EXPECTED_PART,
    }
    for key, expected in expected_scalars.items():
        if record.get(key) != expected:
            errors.append(f"authorization {key} mismatch")
    run_id = record.get("run_id", "")
    if not isinstance(run_id, str) or not RUN_RE.fullmatch(run_id):
        errors.append("authorization run id invalid")
    stages = record.get("authorized_stages")
    if not isinstance(stages, list) or not stages or any(
            not isinstance(stage, str) or not STAGE_RE.fullmatch(stage)
            for stage in stages):
        errors.append("authorized stage list invalid")
        stages = []
    if record.get("lane_masks") != [1, 2, 3]:
        errors.append("authorized lane masks are not exactly 0x1/0x2/0x3")
    for role, serial, target in (
        ("fixed_board", EXPECTED_FIXED_SERIAL, EXPECTED_FIXED_TARGET),
        ("rotating_board", EXPECTED_ROTATING_SERIAL, EXPECTED_ROTATING_TARGET),
    ):
        item = record.get(role, {})
        if item.get("serial") != serial or item.get("target") != target:
            errors.append(f"{role} JTAG binding mismatch")
    if record.get("goal_sha256") != sha256(GOAL):
        errors.append("live FastTrack goal hash mismatch")
    if record.get("artifact_manifest_sha256") != sha256(OFFLINE_MANIFEST):
        errors.append("offline artifact manifest hash mismatch")
    if record.get("plan_sha256") != plan_hashes(stages):
        errors.append("authorized plan hash mismatch")
    if record.get("runner_input_sha256") != runner_input_hashes():
        errors.append("authorized runner input hash mismatch")
    source = record.get("source_commit", "")
    if not re.fullmatch(r"[0-9a-f]{40}", str(source)):
        errors.append("authorization source commit invalid")
    else:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, "HEAD"],
            cwd=ROOT, capture_output=True).returncode == 0
        if not ancestor:
            errors.append("authorization source commit is not an ancestor of HEAD")

    artifacts: dict[str, Path] = {}
    seen: set[str] = set()
    for item in record.get("artifacts", []):
        try:
            key = _artifact_key(item)
            candidate = (ROOT / item["path"]).resolve()
            expected_hash = item["sha256"]
            expected_bytes = int(item["bytes"])
        except (KeyError, TypeError, ValueError):
            errors.append("malformed authorization artifact")
            continue
        if key in seen:
            errors.append(f"duplicate authorization artifact: {key}")
            continue
        seen.add(key)
        if not inside(candidate, ROOT / "artifacts/p10"):
            errors.append(f"artifact outside P10 content store: {key}")
        elif not candidate.is_file():
            errors.append(f"artifact missing: {key}")
        elif not SHA_RE.fullmatch(str(expected_hash)) or sha256(candidate) != expected_hash:
            errors.append(f"artifact SHA256 mismatch: {key}")
        elif candidate.stat().st_size != expected_bytes:
            errors.append(f"artifact byte count mismatch: {key}")
        artifacts[key] = candidate
    required = {f"{role}:{kind}" for role in ("fixed", "rotating")
                for kind in ("shutdown_bitstream", "functional_bitstream",
                             "xsa", "elf")}
    if seen != required:
        errors.append(f"authorization artifact set mismatch: {sorted(seen)}")
    return record, artifacts, errors


def terminate_tree(proc: subprocess.Popen[Any]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()


def run_bounded(command: list[str], stdout_path: Path, stderr_path: Path,
                timeout: int, env: dict[str, str]) -> dict[str, Any]:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    timed_out = False
    proc: subprocess.Popen[Any] | None = None
    with stdout_path.open("w", encoding="utf-8", errors="replace",
                          newline="\n") as stdout, \
            stderr_path.open("w", encoding="utf-8", errors="replace",
                             newline="\n") as stderr:
        try:
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            proc = subprocess.Popen(command, cwd=ROOT, stdout=stdout,
                                    stderr=stderr, text=True, env=env,
                                    creationflags=creationflags)
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            if proc is not None:
                terminate_tree(proc)
                returncode = proc.returncode if proc.returncode is not None else -9
        except KeyboardInterrupt:
            if proc is not None:
                terminate_tree(proc)
            raise
    return {"command": command, "returncode": returncode,
            "timeout_seconds": timeout, "timed_out": timed_out,
            "elapsed_seconds": time.monotonic() - started,
            "stdout": rel(stdout_path), "stderr": rel(stderr_path)}


def port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def start_hw_server(raw_logs: Path) -> tuple[subprocess.Popen[Any] | None,
                                             dict[str, Any]]:
    if port_open("127.0.0.1", 3121):
        return None, {"status": "PASS", "reused": True,
                      "url": "localhost:3121"}
    if not HW_SERVER.is_file():
        return None, {"status": "FAIL", "reason": "hw_server missing"}
    stdout = (raw_logs / "hw_server.stdout.log").open(
        "w", encoding="utf-8", errors="replace", newline="\n")
    stderr = (raw_logs / "hw_server.stderr.log").open(
        "w", encoding="utf-8", errors="replace", newline="\n")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen([str(HW_SERVER)], cwd=ROOT, stdout=stdout,
                            stderr=stderr, text=True, creationflags=flags)
    for _ in range(100):
        if port_open("127.0.0.1", 3121):
            return proc, {"status": "PASS", "reused": False,
                          "pid": proc.pid, "url": "localhost:3121"}
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    terminate_tree(proc)
    return None, {"status": "FAIL", "reason": "hw_server did not listen"}


def extract_ps7_init(xsa: Path, destination: Path) -> dict[str, Any]:
    with zipfile.ZipFile(xsa) as archive:
        names = [name for name in archive.namelist()
                 if Path(name).name.lower() == "ps7_init.tcl"]
        if len(names) != 1:
            raise RuntimeError(f"XSA must contain exactly one ps7_init.tcl: {xsa}")
        data = archive.read(names[0])
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    return {"path": rel(destination), "sha256": sha256(destination),
            "bytes": destination.stat().st_size, "xsa": rel(xsa),
            "xsa_sha256": sha256(xsa), "member": names[0]}


def invoke_shutdown(run_root: Path, auth: Path,
                    artifacts: dict[str, Path], label: str,
                    env: dict[str, str], retry_limit: int = 1) -> dict[str, Any]:
    shutdown_dir = run_root / "shutdown" / label
    shutdown_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    for attempt in range(1, retry_limit + 1):
        result_file = shutdown_dir / f"attempt_{attempt}.result.txt"
        command = [str(VIVADO), "-mode", "batch", "-nolog", "-nojournal",
                   "-notrace", "-source", str(SHUTDOWN_TCL), "-tclargs",
                   "localhost:3121", EXPECTED_FIXED_TARGET,
                   EXPECTED_ROTATING_TARGET, EXPECTED_FIXED_SERIAL,
                   EXPECTED_ROTATING_SERIAL, EXPECTED_PART, str(auth),
                   str(artifacts["fixed:shutdown_bitstream"]),
                   str(artifacts["rotating:shutdown_bitstream"]),
                   str(result_file)]
        process = run_bounded(command,
                              shutdown_dir / f"attempt_{attempt}.stdout.log",
                              shutdown_dir / f"attempt_{attempt}.stderr.log",
                              180, env)
        markers = parse_markers(result_file)
        passed = (process["returncode"] == 0 and not process["timed_out"] and
                  markers.get("SHUTDOWN_FIXED") == "PASS" and
                  markers.get("SHUTDOWN_ROTATING") == "PASS" and
                  markers.get("TFDU_SHUTDOWN_PROGRAMMED") == "1" and
                  markers.get("SHUTDOWN_EXIT") == "0")
        attempts.append({"attempt": attempt, "status": "PASS" if passed else "FAIL",
                         "process": process, "markers": markers,
                         "result": rel(result_file) if result_file.is_file() else None})
        if passed:
            return {"status": "PASS", "test_id": "P10-DUAL-SHUTDOWN",
                    "label": label, "attempts": attempts,
                    "SHUTDOWN_FIXED": "PASS",
                    "SHUTDOWN_ROTATING": "PASS"}
        time.sleep(1)
    return {"status": "FAIL", "test_id": "P10-DUAL-SHUTDOWN",
            "label": label, "attempts": attempts,
            "SHUTDOWN_FIXED": attempts[-1]["markers"].get(
                "SHUTDOWN_FIXED", "FAIL") if attempts else "FAIL",
            "SHUTDOWN_ROTATING": attempts[-1]["markers"].get(
                "SHUTDOWN_ROTATING", "FAIL") if attempts else "FAIL"}


def parse_mailbox(path: Path) -> list[int]:
    data = path.read_bytes()
    if len(data) != 1024:
        raise ValueError(f"mailbox dump size {len(data)} != 1024: {path}")
    return list(struct.unpack("<256I", data))


def pl(words: list[int], index: int) -> int:
    return words[PL_SNAPSHOT_START + index]


def digest(words: list[int], start: int) -> str:
    return "".join(f"{word:08x}" for word in words[start:start + 8])


def mailbox_detail(words: list[int], role: str) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    expected = EXPECTED_ROLE[role]
    checks = {
        "mailbox_magic": words[0] == EXPECTED_MAILBOX_MAGIC,
        "mailbox_schema": words[1] == EXPECTED_MAILBOX_SCHEMA,
        "firmware_build": words[2] == expected["firmware"],
        "pl_id": words[32] == 0x5031305A,
        "pl_build": words[33] == expected["build"],
        "pl_profile": words[34] == expected["profile"],
        "register_map_version": words[35] == EXPECTED_REGISTER_MAP_VERSION,
        "register_map_hash": words[36] == EXPECTED_REGISTER_MAP_HASH_LOW,
        "capabilities": words[37] == EXPECTED_CAPABILITIES,
        "dma_base": words[39] == 0x40400000,
        "dma_sg": words[40] == 1,
        "descriptor_alignment": words[49] == 64,
        "cache_line": words[50] == 32,
        "snapshot_id": pl(words, 0) == 0x5031305A,
    }
    errors.extend(f"{role}: {name}" for name, passed in checks.items()
                  if not passed)
    status = pl(words, 7)
    phy = pl(words, 8)
    if status & 0x285:
        errors.append(f"{role}: endpoint/object/raw/receiver active after command")
    if not status & 0x2:
        errors.append(f"{role}: final TX kill inactive after command")
    if phy & 0xF00:
        errors.append(f"{role}: sticky physical safety fault")
    high_max = [pl(words, index) for index in range(61, 65)]
    duty_max = [pl(words, index) for index in range(65, 69)]
    hard_faults = [pl(words, index) for index in range(81, 85)]
    limits = (pl(words, 85), pl(words, 86), pl(words, 87))
    if any(value > 64 for value in high_max):
        errors.append(f"{role}: continuous Txd high exceeded 1 us")
    if any(hard_faults):
        errors.append(f"{role}: hard duty fault count nonzero")
    if limits != (P10_DUTY_WINDOW_CYCLES, P10_DUTY_HARD_MAX_HIGH_CYCLES,
                  P10_DUTY_TARGET_MAX_HIGH_CYCLES):
        errors.append(f"{role}: exact duty parameters mismatch")
    if any(value > P10_DUTY_HARD_MAX_HIGH_CYCLES for value in duty_max):
        errors.append(f"{role}: strict rolling-duty limit violated")
    if any(value > P10_DUTY_TARGET_MAX_HIGH_CYCLES for value in duty_max):
        errors.append(f"{role}: rolling-duty design target exceeded")
    if words[96] or words[97] or words[98]:
        errors.append(f"{role}: descriptor double completion or leak")
    detail = {
        "role": role, "service_state": words[3], "command_status": words[8],
        "firmware_build_id": f"0x{words[2]:08X}",
        "pl_build_id": f"0x{words[33]:08X}",
        "pl_profile_id": f"0x{words[34]:08X}",
        "pl_status": f"0x{status:08X}", "phy_status": f"0x{phy:08X}",
        "elapsed_ticks": (words[58] << 32) | words[57],
        "counts_per_second": words[59], "actual_rx_length": words[60],
        "input_crc32": words[61], "output_crc32": words[62],
        "input_sha256": digest(words, 63), "output_sha256": digest(words, 71),
        "first_mismatch_offset": words[79],
        "tx_submitted": words[80], "tx_completed": words[81],
        "rx_submitted": words[82], "rx_completed": words[83],
        "tx_generations": [words[88], words[89]],
        "rx_generations": [words[90], words[91]],
        "ring_full": [words[92], words[93]],
        "ring_empty": [words[94], words[95]],
        "descriptor_leak": words[98],
        "cache_flush": words[100], "cache_invalidate": words[101],
        "memory_barriers": words[102], "cache_enabled": words[103],
        "cache_disabled": words[104], "misaligned": words[105],
        "dma_resets": words[106], "dma_reset_queued": words[107],
        "object_aborts": words[108], "pl_soft_resets": words[109],
        "shutdown_attempts": words[110], "shutdown_verified": words[111],
        "last_error_detail": words[115],
        "tx_attempts": pl(words, 25), "tx_retries": pl(words, 26),
        "retry_exhausted": pl(words, 27), "tx_timeouts": pl(words, 28),
        "tx_migrations": pl(words, 29), "rx_duplicates": pl(words, 30),
        "ack_aggregation": pl(words, 31), "ack_frames": pl(words, 33),
        "stale_ack": pl(words, 35), "stale_session": pl(words, 37),
        "stale_path": pl(words, 38),
        "physical_data_good": pl(words, 39),
        "physical_ack_good": pl(words, 40),
        "physical_crc_bad": pl(words, 41),
        "scheduler_frames": [pl(words, 44), pl(words, 45)],
        "scheduler_bytes": [pl(words, 46), pl(words, 47)],
        "scheduler_retries": [pl(words, 48), pl(words, 49)],
        "scheduler_migrations": [pl(words, 50), pl(words, 51)],
        "starvation_max": pl(words, 52),
        "raw_rx": [pl(words, index) for index in range(53, 57)],
        "physical_tx": [pl(words, index) for index in range(57, 61)],
        "tx_high_max_cycles": high_max, "duty_max_cycles": duty_max,
        "duty_hard_faults": hard_faults,
        "duty_parameters": list(limits),
        "terminal_window_valid": (
            words[TERMINAL_WINDOW_START] == TERMINAL_WINDOW_VALID and
            words[TERMINAL_WINDOW_START + 1] == words[6]),
        "terminal_tx_sequence_base": words[TERMINAL_WINDOW_START + 2],
        "terminal_window_status": words[TERMINAL_WINDOW_START + 3],
    }
    return errors, detail


def transfer_bytes(row: dict[str, Any]) -> int:
    useful = row["size"]
    flags = row["flags"]
    if flags & 4:
        return useful + 32 * math.ceil(useful / 215)
    if flags & 8:
        return useful + 48 * math.ceil(useful / 65536)
    return useful


def evaluate_pair(row: dict[str, Any], fixed_words: list[int],
                  rotating_words: list[int]) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    fixed_errors, fixed = mailbox_detail(fixed_words, "fixed")
    rotating_errors, rotating = mailbox_detail(rotating_words, "rotating")
    errors.extend(f"{row['label']}: {item}" for item in
                  fixed_errors + rotating_errors)
    expected_state = 6 if row["command"] == 10 else \
        4 if row["expected_status"] == 0 else 5
    for role, words in (("fixed", fixed_words), ("rotating", rotating_words)):
        if words[3] != expected_state:
            errors.append(f"{row['label']}: {role} service state")
        if words[7] != row["sequence"]:
            errors.append(f"{row['label']}: {role} response sequence")
        if words[8] != row["expected_status"]:
            errors.append(f"{row['label']}: {role} command status")

    pair_detail: dict[str, Any] = {"label": row["label"],
                                  "command": row["command"],
                                  "lane_mask": row["lane"],
                                  "direction": row["direction"],
                                  "rate_select": row["rate"],
                                  "requested_size": row["size"],
                                  "window": row["window"],
                                  "fixed": fixed, "rotating": rotating}
    if row["command"] == 2:
        sender_role = "fixed" if row["direction"] == 0 else "rotating"
        receiver_role = "rotating" if row["direction"] == 0 else "fixed"
        sender = fixed if sender_role == "fixed" else rotating
        receiver = rotating if receiver_role == "rotating" else fixed
        sender_base = 0 if sender_role == "fixed" else 2
        receiver_base = 2 if receiver_role == "rotating" else 0
        target = row["rawtarget"]
        for lane_index, bit in enumerate((1, 2)):
            expected = target if row["lane"] & bit else 0
            if sender["physical_tx"][sender_base + lane_index] != expected:
                errors.append(f"{row['label']}: sender physical TX lane{lane_index}")
            observed = receiver["raw_rx"][receiver_base + lane_index]
            if expected and not target <= observed <= target + 4:
                errors.append(f"{row['label']}: destination raw RX lane{lane_index}")
            if not expected and observed != 0:
                errors.append(f"{row['label']}: destination off-lane crosstalk")
            if receiver["physical_tx"][receiver_base + lane_index] != 0:
                errors.append(f"{row['label']}: receiver transmitted during raw test")
        pair_detail["raw_matrix"] = {
            "module_order": ["F0", "F1", "R0", "R1"],
            "fixed_rx": fixed["raw_rx"], "rotating_rx": rotating["raw_rx"],
            "fixed_tx": fixed["physical_tx"],
            "rotating_tx": rotating["physical_tx"],
            "sender_role": sender_role, "receiver_role": receiver_role,
        }
    elif row["command"] == 3 and row["expected_status"] == 0:
        sender = fixed if row["direction"] == 0 else rotating
        receiver = rotating if row["direction"] == 0 else fixed
        expected_bytes = transfer_bytes(row)
        if sender["input_crc32"] != receiver["output_crc32"] or \
                receiver["input_crc32"] != receiver["output_crc32"]:
            errors.append(f"{row['label']}: end-to-end CRC32 mismatch")
        if sender["input_sha256"] != receiver["output_sha256"] or \
                receiver["input_sha256"] != receiver["output_sha256"]:
            errors.append(f"{row['label']}: end-to-end SHA256 mismatch")
        if receiver["actual_rx_length"] != expected_bytes:
            errors.append(f"{row['label']}: receiver byte length mismatch")
        if sender["tx_submitted"] == 0 or \
                sender["tx_submitted"] != sender["tx_completed"]:
            errors.append(f"{row['label']}: sender DMA completion imbalance")
        if receiver["rx_submitted"] == 0 or \
                receiver["rx_submitted"] != receiver["rx_completed"]:
            errors.append(f"{row['label']}: receiver DMA completion imbalance")
        if sender["retry_exhausted"] != 0 or receiver["retry_exhausted"] != 0:
            errors.append(f"{row['label']}: retry exhausted")
        if not row["faultflags"] & (1 << 4) and (
                sender["physical_crc_bad"] or receiver["physical_crc_bad"]):
            errors.append(f"{row['label']}: unexpected physical CRC bad")
        pair_detail["end_to_end"] = {
            "sender_role": "fixed" if row["direction"] == 0 else "rotating",
            "receiver_role": "rotating" if row["direction"] == 0 else "fixed",
            "transfer_bytes": expected_bytes,
            "crc32": f"0x{receiver['output_crc32']:08X}",
            "sha256": receiver["output_sha256"],
        }
    return errors, pair_detail


def load_observations(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle, delimiter="|"):
            row: dict[str, Any] = dict(raw)
            for key, value in raw.items():
                if key not in {"label", "window", "fixed_dump_path",
                               "rotating_dump_path"}:
                    row[key] = int(value, 0)
            rows.append(row)
    return rows


def validate_observation_shape(stage: str, plan_items: list[PlanItem],
                               rows: list[dict[str, Any]]) -> list[str]:
    """Validate static CASE plans and the dynamic P10-J soak expansion."""
    errors: list[str] = []
    shutdown_label = f"{stage}_endpoint_shutdown"
    shutdown_positions = [index for index, row in enumerate(rows)
                          if row.get("label") == shutdown_label]
    if shutdown_positions != [len(rows) - 1]:
        errors.append("exactly one final endpoint-shutdown observation required")

    case_items = [item for item in plan_items if isinstance(item, Case)]
    if stage != "P10-J":
        expected_cases = len(case_items) + 1
        if len(rows) != expected_cases:
            errors.append(f"observation count {len(rows)} != {expected_cases}")
        expected_labels = [item.label for item in case_items]
        observed_labels = [row.get("label") for row in rows
                           if row.get("label") != shutdown_label]
        if expected_labels != observed_labels:
            errors.append("observed case labels differ from immutable plan")
        return errors

    if plan_items != [P10_J_SOAK_PLAN]:
        errors.append("unsupported dynamic hardware plan")
        return errors

    soak_rows = [row for row in rows if row.get("label") != shutdown_label]
    if len(soak_rows) < 6:
        errors.append("stationary soak did not cover all size/direction pairs")
    for index, row in enumerate(soak_rows):
        size = P10_J_SOAK_SIZES[index % len(P10_J_SOAK_SIZES)]
        direction = index & 1
        expected_label = f"soak_{index:05d}_{size}_d{direction}"
        if row.get("label") != expected_label:
            errors.append(f"stationary soak sequence mismatch at index {index}")
            break
        expected_fields = {
            "command": 3,
            "expected_status": 0,
            "flags": 2,
            "lane": 3,
            "direction": direction,
            "rate": 2,
            "size": size,
            "ring": 32,
            "cache": 1,
            "session": 0xA0100001,
            "path": 10,
            "object": 0x3A000000 + index,
            "window": "ACCEPTANCE",
        }
        if any(row.get(key) != value for key, value in expected_fields.items()):
            errors.append(f"stationary soak fields mismatch at index {index}")
            break
    return errors


def evaluate_stage(stage: str, stage_dir: Path,
                   process: dict[str, Any], plan_items: list[PlanItem]) -> dict[str, Any]:
    result_file = stage_dir / "xsdb.result.txt"
    markers = parse_markers(result_file)
    errors: list[str] = []
    if process["returncode"] != 0 or process["timed_out"]:
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS":
        errors.append("P10 XSDB stage marker missing or failed")
    if markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("dual safe-boot marker missing")
    observation_path = stage_dir / "dumps/observations.psv"
    rows = load_observations(observation_path) if observation_path.is_file() else []
    errors.extend(validate_observation_shape(stage, plan_items, rows))
    details: list[dict[str, Any]] = []
    raw_matrix: list[dict[str, Any]] = []
    for row in rows:
        try:
            fixed_path = Path(row["fixed_dump_path"]).resolve()
            rotating_path = Path(row["rotating_dump_path"]).resolve()
            if not inside(fixed_path, stage_dir) or not inside(rotating_path, stage_dir):
                raise ValueError("mailbox dump path escaped stage evidence")
            pair_errors, detail = evaluate_pair(
                row, parse_mailbox(fixed_path), parse_mailbox(rotating_path))
            errors.extend(pair_errors)
            details.append(detail)
            if "raw_matrix" in detail:
                raw_matrix.append({"label": detail["label"],
                                   **detail["raw_matrix"]})
        except (OSError, ValueError, KeyError, struct.error) as exc:
            errors.append(f"{row.get('label', 'unknown')}: mailbox evaluation: {exc}")
    # Stage-specific direct gates.  These are additive to per-mailbox safety,
    # identity, DMA balance, CRC, and SHA checks above.
    non_shutdown = [item for item in details
                    if not item["label"].endswith("_endpoint_shutdown")]
    if stage == "P10-B" and len(raw_matrix) != 8:
        errors.append("four-direction 64/1024 raw matrix is incomplete")
    if stage == "P10-C":
        clean_10k = [item for item in non_shutdown if "10000f" in item["label"]]
        if len(clean_10k) != 6 or any(item["rate_select"] != 2 for item in clean_10k):
            errors.append("4 Mbit/s lane/two-lane acceptance set incomplete")
    if stage == "P10-D":
        by_label = {item["label"]: item for item in non_shutdown}
        if not all(name in by_label for name in
                   ("sr_wrap_f_to_r", "sr_wrap_r_to_f",
                    "sack_ack_aggregation", "loss_recovery_data",
                    "loss_recovery_ack", "duplicate_recovery",
                    "reorder_recovery")):
            errors.append("selective-repeat/SACK recovery set incomplete")
    if stage == "P10-E":
        role_final = non_shutdown[-1] if non_shutdown else None
        if role_final is None or any(role_final[role]["descriptor_leak"]
                                     for role in ("fixed", "rotating")):
            errors.append("DMA final descriptor ownership did not reconcile")
    if stage == "P10-F":
        expected_sizes = {4096, 65536, 1048576, 16 * 1048576}
        for direction in (0, 1):
            observed = {item["requested_size"] for item in non_shutdown
                        if item["direction"] == direction}
            if observed != expected_sizes:
                errors.append(f"dual-PS object sizes incomplete direction={direction}")
    if stage == "P10-H":
        migration = next((item for item in non_shutdown
                          if item["label"] == "retry_migration"), None)
        if migration is None:
            errors.append("retry migration case missing")
        else:
            sender = migration["fixed"]
            if sender["tx_retries"] == 0 or sender["tx_migrations"] == 0:
                errors.append("retry migration was not directly observed")
    if stage == "P10-J":
        elapsed_text = markers.get("P10_SOAK_ACTIVE_ELAPSED_MS", "0")
        elapsed = int(elapsed_text) if elapsed_text.isdigit() else 0
        if not 1_800_000 <= elapsed <= 1_800_500:
            errors.append("stationary active window is not exactly 1800 seconds")
        case_count_text = markers.get("P10_SOAK_CASE_COUNT", "")
        case_count = int(case_count_text) if case_count_text.isdigit() else -1
        if case_count != len(non_shutdown):
            errors.append("stationary soak marker/observation count mismatch")
        if not any(item.get("window") == "ACCEPTANCE" for item in non_shutdown):
            errors.append("stationary acceptance window has no objects")

    performance: list[dict[str, Any]] = []
    for item in non_shutdown:
        if item["command"] != 3 or "end_to_end" not in item:
            continue
        sender_role = item["end_to_end"]["sender_role"]
        ticks = item[sender_role]["elapsed_ticks"]
        cps = item[sender_role]["counts_per_second"]
        bps = (8 * item["end_to_end"]["transfer_bytes"] * cps / ticks
               if ticks and cps else 0.0)
        performance.append({"label": item["label"],
                            "direction": item["direction"],
                            "application_goodput_bps": bps})
    summary = {
        "schema_version": 1, "test_id": f"{stage}-HARDWARE",
        "stage": stage, "status": "PASS" if not errors else "FAIL",
        "process": process, "markers": markers,
        "observation_count": len(rows), "errors": errors,
        "details": details, "raw_matrix": raw_matrix,
        "performance": performance,
        "observations": rel(observation_path) if observation_path.is_file() else None,
    }
    write_json(stage_dir / "stage_summary.json", summary)
    return summary


def invoke_stage(stage: str, run_root: Path, auth: Path,
                 artifacts: dict[str, Path], ps7: dict[str, Path],
                 plan_path: Path, env: dict[str, str],
                 abort_file: Path) -> dict[str, Any]:
    stage_dir = run_root / "stages" / stage.lower().replace("-", "_")
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    result_file = stage_dir / "xsdb.result.txt"
    command = [str(XSDB), str(STAGE_TCL), "tcp:localhost:3121",
               EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL,
               str(artifacts["fixed:functional_bitstream"]),
               str(artifacts["rotating:functional_bitstream"]),
               str(artifacts["fixed:elf"]), str(artifacts["rotating:elf"]),
               str(ps7["fixed"]), str(ps7["rotating"]), str(plan_path),
               str(dump_dir), str(abort_file), str(result_file), stage,
               str(auth), run_root.name]
    timeout = 2100 if stage == "P10-J" else 1500 if stage in {
        "P10-C", "P10-D", "P10-F"} else 900
    process = run_bounded(command, stage_dir / "xsdb.stdout.log",
                          stage_dir / "xsdb.stderr.log", timeout, env)
    return evaluate_stage(stage, stage_dir, process, build_plans()[stage])


def evidence_manifest(run_root: Path) -> dict[str, Any]:
    output = run_root / "final/run_evidence_sha256_manifest.json"
    orchestrator = run_root / "final/orchestrator_result.json"
    files = []
    for path in sorted(item for item in run_root.rglob("*") if item.is_file()):
        # The manifest and the orchestrator summary refer to one another.  Both
        # are immutable evidence, but including either self-referential file
        # here would make the recorded digest stale when the final manifest
        # metadata is inserted into the summary.
        if path in {output, orchestrator}:
            continue
        files.append({"path": path.relative_to(run_root).as_posix(),
                      "bytes": path.stat().st_size, "sha256": sha256(path)})
    payload = {"schema_version": 1, "test_id": "P10-EVIDENCE-MANIFEST",
               "status": "PASS", "run_id": run_root.name,
               "generated_at_utc": utc_now(), "files": files}
    write_json(output, payload)
    return payload


def summarize_campaign(run_root: Path, record: dict[str, Any],
                       stage_results: dict[str, dict[str, Any]],
                       shutdowns: list[dict[str, Any]], errors: list[str],
                       hardware_actions: bool) -> dict[str, Any]:
    stages = record["authorized_stages"]
    stage_status = {stage: stage_results.get(stage, {}).get("status", "NOT_RUN")
                    for stage in stages}
    all_stage_pass = all(status == "PASS" for status in stage_status.values())
    shutdown_fixed = "PASS" if shutdowns and all(
        item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdowns) else "FAIL"
    shutdown_rotating = "PASS" if shutdowns and all(
        item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdowns) else "FAIL"
    formal = record.get("formal_campaign") is True
    final_status = "PASS" if (all_stage_pass and shutdown_fixed == "PASS" and
                              shutdown_rotating == "PASS" and not errors) else "FAIL"
    perf = [row for result in stage_results.values()
            for row in result.get("performance", [])]
    f_to_r = [row["application_goodput_bps"] for row in perf
              if row["direction"] == 0]
    r_to_f = [row["application_goodput_bps"] for row in perf
              if row["direction"] == 1]
    gates = {
        "F_R_BUILD_ROLE_SAFE_BOOT_SHUTDOWN": (
            "PASS" if all_stage_pass and shutdown_fixed == shutdown_rotating == "PASS"
            else "FAIL"),
        "FOUR_DIRECTION_RAW": stage_status.get("P10-B", "NOT_RUN"),
        "LANE0_4MBPS": stage_status.get("P10-C", "NOT_RUN"),
        "LANE1_4MBPS": stage_status.get("P10-C", "NOT_RUN"),
        "TWO_LANE_8MBPS_RAW": stage_status.get("P10-C", "NOT_RUN"),
        "SELECTIVE_REPEAT_SACK": stage_status.get("P10-D", "NOT_RUN"),
        "DMA_DDR_CACHE_FIXED": stage_status.get("P10-E", "NOT_RUN"),
        "DMA_DDR_CACHE_ROTATING": stage_status.get("P10-E", "NOT_RUN"),
        "DUAL_INDEPENDENT_PS": stage_status.get("P10-F", "NOT_RUN"),
        "F_TO_R_OBJECT": stage_status.get("P10-F", "NOT_RUN"),
        "R_TO_F_OBJECT": stage_status.get("P10-F", "NOT_RUN"),
        "ENDPOINT_REBOOT_RECOVERY": stage_status.get("P10-G", "NOT_RUN"),
        "SCHEDULER_LANE_FAULT": stage_status.get("P10-H", "NOT_RUN"),
        "PERFORMANCE": stage_status.get("P10-I", "NOT_RUN"),
        "STATIONARY_30MIN": stage_status.get("P10-J", "NOT_RUN"),
    }
    summary = {
        "schema_version": 1, "test_id": "P10-FASTTRACK-FINAL",
        "status": final_status, "formal_campaign": formal,
        "run_id": run_root.name, "source_commit": record["source_commit"],
        "current_head": git("rev-parse", "HEAD"),
        "branch": EXPECTED_BRANCH,
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": hardware_actions,
        "network_used": False, "hardware_movement": False,
        "rotation_executed": False, "rewiring_executed": False,
        "intentional_power_cycle": False, "maximum_lane_mask_used": "0x3",
        "fixed_board_id": f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}",
        "rotating_board_id": f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}",
        "stage_status": stage_status, "mandatory_gates": gates,
        "SHUTDOWN_FIXED": shutdown_fixed,
        "SHUTDOWN_ROTATING": shutdown_rotating,
        "campaign_errors": errors,
        "application_goodput_f_to_r_bps": min(f_to_r) if f_to_r else None,
        "application_goodput_r_to_f_bps": min(r_to_f) if r_to_f else None,
        "unchanged_pending_scopes": {
            "ETHERNET": "DEFERRED", "SPI": "PENDING",
            "PHYSICAL_GLOBAL_PERMIT": "PENDING_D17",
            "EXTERNAL_TFDU_DUTY": "PENDING_EXTERNAL_MEASUREMENT",
            "HANDOVER": "PENDING_P11", "8X32": "PENDING_P12",
            "600RPM": "PENDING_P13", "PRODUCT_FINAL": "PENDING",
        },
        "generated_at_utc": utc_now(),
    }
    write_json(run_root / "final/orchestrator_result.json", summary)
    return summary


def publish_latest(summary: dict[str, Any], run_root: Path) -> None:
    write_json(GENERATED / "p10_fasttrack_final_summary.json", summary)
    lines = [
        "# P10 fast-track final summary", "",
        f"P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET: `{summary['status']}`",
        f"Run ID: `{summary['run_id']}`",
        f"Fixed board: `{summary['fixed_board_id']}`",
        f"Rotating board: `{summary['rotating_board_id']}`",
        f"Shutdown fixed/rotating: `{summary['SHUTDOWN_FIXED']}` / `{summary['SHUTDOWN_ROTATING']}`",
        "", "The adjacent JSON is the authoritative machine-readable record.",
        f"Raw evidence: `{rel(run_root)}`",
    ]
    write_text(GENERATED / "p10_fasttrack_final_summary.md",
               "\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorize-from", type=Path, default=DEFAULT_AUTH)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--formal", action="store_true")
    parser.add_argument("--stage", default="")
    parser.add_argument("--max-runtime", type=int, required=True)
    parser.add_argument("--lane-mask", type=lambda value: int(value, 0),
                        required=True)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)

    auth = args.authorize_from.resolve()
    record, artifacts, errors = validate_authorization(auth)
    if args.run_id != record.get("run_id"):
        errors.append("CLI run id differs from immutable authorization")
    stages = record.get("authorized_stages", [])
    requested = list(ALL_FORMAL_STAGES) if args.formal else [args.stage]
    if requested != stages:
        errors.append("CLI stage set differs from immutable authorization")
    if args.formal != bool(record.get("formal_campaign")):
        errors.append("CLI formal mode differs from immutable authorization")
    if args.max_runtime != 1800:
        errors.append("maximum active runtime must be exactly 1800 seconds")
    if args.lane_mask != 3:
        errors.append("maximum lane mask must be exactly 0x3")
    if git("branch", "--show-current") != EXPECTED_BRANCH:
        errors.append("wrong P10 branch")
    if git("status", "--porcelain"):
        errors.append("P10 worktree is not clean")
    for ancestor in ("main", "p8e-pass", "p9-z7010-2lane-pass"):
        if subprocess.run(["git", "merge-base", "--is-ancestor", ancestor,
                           "HEAD"], cwd=ROOT).returncode != 0:
            errors.append(f"HEAD does not contain {ancestor}")
    for tool in (VIVADO, XSDB, SHUTDOWN_TCL, STAGE_TCL):
        if not tool.is_file():
            errors.append(f"required tool/input missing: {tool}")

    run_root = HW_ROOT / (args.run_id if RUN_RE.fullmatch(args.run_id)
                          else "invalid_run_id")
    if run_root.exists() and any(run_root.iterdir()):
        errors.append("run directory already exists and is nonempty")
    for directory in ("authorization", "artifacts", "plans", "stages",
                      "shutdown", "raw_logs", "final"):
        (run_root / directory).mkdir(parents=True, exist_ok=True)
    abort_file = run_root / "authorization/ABORT_NOW.txt"
    plans = build_plans()
    plan_records: dict[str, dict[str, Any]] = {}
    for stage in stages:
        path = run_root / "plans" / f"{stage.lower().replace('-', '_')}.plan"
        text = plan_text(plans[stage])
        write_text(path, text)
        plan_records[stage] = {"path": rel(path), "sha256": sha256(path)}
        if sha256(path) != record.get("plan_sha256", {}).get(stage):
            errors.append(f"materialized plan hash mismatch: {stage}")

    auth_record = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "test_id": "P10-CURRENT-RUN-AUTHORIZATION",
        "run_id": args.run_id, "source_commit": record.get("source_commit"),
        "authorization": rel(auth) if inside(auth, ROOT) else str(auth),
        "authorization_sha256": sha256(auth) if auth.is_file() else None,
        "plans": plan_records, "errors": errors,
        "hardware_actions_executed": False,
    }
    write_json(run_root / "authorization/authorization_record.json", auth_record)
    if auth.is_file():
        shutil.copy2(auth, run_root / "authorization/immutable_authorization.json")

    if errors or args.dry_run or not args.execute_hardware:
        status = "PASS" if args.dry_run and not errors else "FAIL"
        summary = {**auth_record, "status": status, "dry_run": True,
                   "hardware_actions_executed": False}
        write_json(run_root / "final/orchestrator_result.json", summary)
        if args.json_summary:
            print(json.dumps(summary, sort_keys=True))
        else:
            print(f"P10_DRY_RUN={status}")
        return 0 if status == "PASS" else 1
    if os.environ.get("NO_HARDWARE", "1") != "0" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "true":
        summary = {**auth_record, "status": "FAIL", "dry_run": False,
                   "errors": ["NO_HARDWARE=0 and current-run authorization=true required"],
                   "hardware_actions_executed": False}
        write_json(run_root / "final/orchestrator_result.json", summary)
        return 1

    ps7_records = {}
    ps7_paths: dict[str, Path] = {}
    try:
        for role in ("fixed", "rotating"):
            destination = run_root / "artifacts" / role / "ps7_init.tcl"
            ps7_records[role] = extract_ps7_init(artifacts[f"{role}:xsa"],
                                                 destination)
            ps7_paths[role] = destination
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        auth_record["errors"].append(f"PS7 init extraction failed: {exc}")
        write_json(run_root / "authorization/authorization_record.json",
                   auth_record)
        return 1
    write_json(run_root / "artifacts/derived_artifact_manifest.json",
               {"schema_version": 1, "status": "PASS", "ps7_init": ps7_records})
    write_text(run_root / "authorization/NO_MOVEMENT_NETWORK_ATTESTATION.txt",
               "NO_HARDWARE_MOVEMENT=true\nROTATION_EXECUTED=false\n"
               "REWIRING_EXECUTED=false\nINTENTIONAL_POWER_CYCLE=false\n"
               "EXTERNAL_NETWORK_USED=false\nETHERNET_USED=false\n"
               "LOCALHOST_HW_SERVER_USED=true\nMAX_LANE_MASK_USED=0x3\n")

    env = os.environ.copy()
    env["RF_COMM_P10_HW_AUTH"] = "P10_FASTTRACK_IMMUTABLE_AUTHORIZED"
    stage_results: dict[str, dict[str, Any]] = {}
    shutdowns: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    server_proc: subprocess.Popen[Any] | None = None
    hardware_actions = False
    try:
        server_proc, server = start_hw_server(run_root / "raw_logs")
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server["status"] != "PASS":
            raise RuntimeError(server.get("reason", "hw_server failed"))
        hardware_actions = True
        initial = invoke_shutdown(run_root, auth, artifacts,
                                  "initial_shutdown", env)
        shutdowns.append(initial)
        if initial["status"] != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for stage in stages:
            before = invoke_shutdown(run_root, auth, artifacts,
                                     f"{stage.lower()}_before", env)
            shutdowns.append(before)
            if before["status"] != "PASS":
                raise RuntimeError(f"{stage} shutdown-before unconfirmed")
            result: dict[str, Any] = {"status": "FAIL"}
            after: dict[str, Any]
            try:
                result = invoke_stage(stage, run_root, auth, artifacts,
                                      ps7_paths,
                                      Path(plan_records[stage]["path"]),
                                      env, abort_file)
                stage_results[stage] = result
            finally:
                after = invoke_shutdown(run_root, auth, artifacts,
                                        f"{stage.lower()}_after", env)
                shutdowns.append(after)
            if result.get("status") != "PASS":
                raise RuntimeError(f"{stage} hardware validation failed")
            if after.get("status") != "PASS":
                raise RuntimeError(f"{stage} shutdown-after unconfirmed")
        final_shutdown = invoke_shutdown(run_root, auth, artifacts,
                                         "final_shutdown", env)
        shutdowns.append(final_shutdown)
        if final_shutdown["status"] != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except BaseException as exc:
        campaign_errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        emergency = invoke_shutdown(run_root, auth, artifacts,
                                    "finally_emergency", env)
        shutdowns.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            terminate_tree(server_proc)

    auth_record["hardware_actions_executed"] = hardware_actions
    write_json(run_root / "authorization/authorization_record.json", auth_record)
    summary = summarize_campaign(run_root, record, stage_results, shutdowns,
                                 campaign_errors, hardware_actions)
    manifest = evidence_manifest(run_root)
    summary["evidence_manifest"] = rel(
        run_root / "final/run_evidence_sha256_manifest.json")
    summary["evidence_manifest_file_count"] = len(manifest["files"])
    write_json(run_root / "final/orchestrator_result.json", summary)
    publish_latest(summary, run_root)
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"P10_STATUS={summary['status']}")
        print(f"P10_RUN_ID={args.run_id}")
        print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
        print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
