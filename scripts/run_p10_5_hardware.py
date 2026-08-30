#!/usr/bin/env python3
"""Fail-closed autonomous P10.5 split-lane bidirectional hardware campaign."""

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
from typing import Any

import run_p10_3_ax7020_4lane_hardware as p103
import run_p10_4_hardware as p104
from p10_hardware_runtime import (
    EXPECTED_FIXED_SERIAL,
    EXPECTED_ROTATING_SERIAL,
    XSDB,
    extract_ps7_init,
    parse_markers,
    run_bounded,
    start_hw_server,
    terminate_tree,
)
from p10_tfdu_runtime_guard import RuntimeRestGuard, load_policy


ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / "goals/P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE_GOAL.md"
GOAL_SHA256 = "5c08e89917ffc18150e37f65ff29cf7c48f749d81033fe02a0d1bce772c23a36"
SCOPE = "P10_5_DUAL_DIRECTION_2PLUS2_ARCHITECTURE_AND_HARDWARE_ACCEPTANCE"
FREEZE = ROOT / "evidence/generated/p10_5_artifact_freeze.json"
AUTH = ROOT / "config/p10_5_current_run_hardware_authorization.json"
CONFIG = ROOT / "config/p10_5_dual_direction.yaml"
REGISTER_MAP = ROOT / "config/register_map/ir_axi_regs.yaml"
AS_WIRED = ROOT / "config/hardware/p10_3_actual_wiring.yaml"
MODULE_INVENTORY = ROOT / "config/hardware/tfdu_module_inventory.yaml"
RUNTIME_REST_POLICY = ROOT / "config/safety/p10_tfdu_runtime_rest_policy.yaml"
SHUTDOWN_TCL = ROOT / "scripts/hw/p10_program_dual_shutdown.tcl"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
FORENSIC_TCL = ROOT / "scripts/hw/p10_3f_fault_forensics.tcl"
HW_ROOT = ROOT / "evidence/hardware/p10_5"
GENERATED = ROOT / "evidence/generated"
EXPECTED_BUILD = {"fixed": 0x50353546, "rotating": 0x50353552}
EXPECTED_PROFILE = {"fixed": 0x702004F0, "rotating": 0x702004A0}
REGISTER_MAP_VERSION = 0x0A000005
REGISTER_MAP_HASH_LOW = 0x00000000  # replaced from the generated manifest below
EXPECTED_CAPABILITIES = 0xF7204441
INTERNAL_OBJECT_BYTES = 262_144
DESCRIPTOR_BYTES = 65_536
MAX_STREAM_BYTES = 0x70000000
PRIMARY_F2R = 0x3
PRIMARY_R2F = 0xC
STALE_ROLE_PROTOCOL_FLAG = 1 << 12
FLAG_DIRECTION_FAULT = 1 << 27
FLAG_TARGET_R2F = 1 << 28
FLAG_ABORT_DIRECTION = 1 << 29
FLAG_DMA_BACKPRESSURE = 1 << 30
FLAG_STALE_ROLE = 1 << 31
HOST_LAUNCH_RELEASE_MASK = 1 << 31
LAUNCH_BARRIER_TIMEOUT_MS = 60_000
INTER_OBJECT_RX_LEAD_US = 5_000
MODULE_BINDING = {
    "F0": "A0019", "F1": "B0012", "F2": "B0019", "F3": "B0020",
    "R0": "A0010", "R1": "A0017", "R2": "B0023", "R3": "B0011",
}
ALL_MODULES = tuple(MODULE_BINDING)
SHUTDOWN_POLICY = {
    "shutdown_before_every_stage": True,
    "archive_before_independent_shutdown": True,
    "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
    "verify_both_shutdown_markers": True,
    "clear_frozen_capture_before_shutdown_program": False,
}
RUN_RE = re.compile(
    r"^p10_5_(?P<utc>[0-9]{8}T[0-9]{6}Z)_"
    r"(?P<source>[0-9a-f]{8})_(?P<fixed>[0-9a-f]{8})_"
    r"(?P<rotating>[0-9a-f]{8})$"
)


def _map_identity() -> tuple[int, int]:
    manifest = json.loads((
        ROOT / "config/register_map/generated/ir_regs_manifest.json"
    ).read_text(encoding="utf-8"))
    return int(manifest["register_map_version_value"], 0), int(manifest["hash_low"], 0)


REGISTER_MAP_VERSION, REGISTER_MAP_HASH_LOW = _map_identity()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               ensure_ascii=False) + "\n",
                    encoding="utf-8", newline="\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path),
            "bytes": path.stat().st_size}


def write_pair(base: Path, payload: dict[str, Any], title: str) -> None:
    write_json(base.with_suffix(".json"), payload)
    lines = [f"# {title}", "", f"- Status: `{payload.get('status')}`"]
    for key in ("test_id", "run_id", "artifact_source_commit"):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    if payload.get("errors"):
        lines += ["", "## Errors", ""] + [f"- {x}" for x in payload["errors"]]
    write_text(base.with_suffix(".md"), "\n".join(lines) + "\n")


@dataclass(frozen=True)
class P105Case:
    label: str
    active: int
    f2r: int
    r2f: int
    size: int
    timeout: int
    object_id: int
    duration_ms: int = 0
    flags: int = 0
    unavailable: int = 0
    drop_data: int = 0
    drop_ack: int = 0
    protocol_flags: int = 0
    command: int = 15

    @property
    def packed_mask(self) -> int:
        return self.active | (self.f2r << 8) | (self.r2f << 16)

    def validate(self) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.label):
            raise ValueError(f"unsafe P10.5 label: {self.label}")
        if self.command != 15 or not 0 < self.active <= 15 or not self.f2r or not self.r2f:
            raise ValueError(f"invalid P10.5 command/mask: {self.label}")
        if self.f2r & self.r2f or self.f2r | self.r2f != self.active:
            raise ValueError(f"overlapping/incomplete P10.5 masks: {self.label}")
        if not 0 <= self.unavailable <= 15 or self.unavailable & ~self.active:
            raise ValueError(f"invalid unavailable mask: {self.label}")
        if not 1 <= self.size <= MAX_STREAM_BYTES or not 1 <= self.timeout <= 1_800_000:
            raise ValueError(f"invalid size/timeout: {self.label}")
        if self.duration_ms and (self.timeout < self.duration_ms or
                                 self.size < self.duration_ms * 1000):
            raise ValueError(f"duration ceiling is unsafe: {self.label}")
        if self.protocol_flags not in {0, STALE_ROLE_PROTOCOL_FLAG}:
            raise ValueError(f"unsupported P10.5 protocol flags: {self.label}")

    def plan_line(self) -> str:
        self.validate()
        values = [
            "CASE", self.label, self.command, 0, self.flags, self.packed_mask,
            2, 2, 0x01010101, self.size, 32, 1, 0, 0, self.timeout,
            0xA5050001, 0x0505, self.object_id, self.drop_data,
            self.drop_ack, self.unavailable, INTERNAL_OBJECT_BYTES,
            DESCRIPTOR_BYTES, 4, 8, self.protocol_flags,
            self.duration_ms, 0, 0,
        ]
        return " ".join(str(value) for value in values)


PlanItem = P105Case | tuple[str, ...]


class ObjectIds:
    def __init__(self) -> None:
        self.value = 0x75000000

    def take(self, size: int) -> int:
        value = self.value
        self.value += math.ceil(size / INTERNAL_OBJECT_BYTES) + 4
        if self.value >= 0x7F000000:
            raise ValueError("P10.5 object-ID space exhausted")
        return value


def duration_case(ids: ObjectIds, label: str, f2r: int, r2f: int,
                  seconds: int, **kwargs: Any) -> P105Case:
    duration_ms = seconds * 1000
    size = max(4 * INTERNAL_OBJECT_BYTES, duration_ms * 1000)
    timeout = min(1_800_000, duration_ms + 120_000)
    return P105Case(label, f2r | r2f, f2r, r2f, size, timeout,
                    ids.take(size), duration_ms=duration_ms, **kwargs)


def object_case(ids: ObjectIds, label: str, f2r: int, r2f: int,
                size: int, **kwargs: Any) -> P105Case:
    return P105Case(label, f2r | r2f, f2r, r2f, size, 600_000,
                    ids.take(size), **kwargs)


def stage_order() -> tuple[str, ...]:
    return (
        "safe_start", "capability", "one_plus_one", "two_plus_one",
        "two_plus_two", "role_commit", "performance",
        "streaming_64m_1", "streaming_64m_2", "streaming_64m_3",
        "streaming_64m_4", "streaming_64m_5", "faults", "formal_30min",
    )


STAGES = stage_order()


def build_plans() -> dict[str, list[PlanItem]]:
    ids = ObjectIds()
    plans: dict[str, list[PlanItem]] = {stage: [] for stage in STAGES}
    plans["safe_start"] = [("CASE", "p10_5_identity", "1", "0", "0", "0",
                             "0", "0", "0", "0", "8", "0", "0", "0",
                             "10000", "0", "0", "0", "0", "0", "0", "0",
                             "1024", "0", "0", "0", "0", "0", "0")]
    plans["capability"] = [
        ("P105_CAPABILITY", "precommit", "0", "0", "0"),
        # Capability is a finite transfer gate, not a duration-accuracy test.
        # A one-second duration included RX-ring priming and the first complete
        # 256-KiB optical object inside its deadline; direct hardware evidence
        # showed that clean object finishing at ~1.4 s and therefore returning
        # TIMER before the post-commit readback.  Use four finite objects so
        # this gate still proves simultaneous TX/RX, ACK/credit progress and
        # atomic commit without imposing a physically impossible wall-clock
        # deadline.  Timed operation remains covered by the 10/20/30/300/1800
        # second mandatory stages below.
        object_case(ids, "capability_primary", PRIMARY_F2R, PRIMARY_R2F,
                    4 * INTERNAL_OBJECT_BYTES),
        ("P105_CAPABILITY", "primary", "15", "3", "12"),
    ]
    for f_lane in range(4):
        for r_lane in range(4):
            if f_lane == r_lane:
                continue
            plans["one_plus_one"].append(duration_case(
                ids, f"oneplusone_f{f_lane}_r{r_lane}",
                1 << f_lane, 1 << r_lane, 10))
    for pair in range(1, 16):
        if pair.bit_count() != 2:
            continue
        remaining = 15 ^ pair
        for lane in range(4):
            bit = 1 << lane
            if remaining & bit:
                plans["two_plus_one"].append(duration_case(
                    ids, f"twoplusone_f{pair:X}_r{bit:X}", pair, bit, 20))
                plans["two_plus_one"].append(duration_case(
                    ids, f"oneplustwo_f{bit:X}_r{pair:X}", bit, pair, 20))
    for f2r, r2f in ((3, 12), (12, 3), (5, 10), (10, 5), (9, 6), (6, 9)):
        plans["two_plus_two"].append(duration_case(
            ids, f"twoplustwo_f{f2r:X}_r{r2f:X}", f2r, r2f, 30))
    role_vectors = ((3, 12), (5, 10), (9, 6), (3, 12))
    for index, (f2r, r2f) in enumerate(role_vectors):
        stale = index == 0
        plans["role_commit"].append(duration_case(
            ids, f"role_commit_{index}_f{f2r:X}_r{r2f:X}", f2r, r2f, 10,
            flags=FLAG_STALE_ROLE if stale else 0,
            protocol_flags=STALE_ROLE_PROTOCOL_FLAG if stale else 0))
        plans["role_commit"].append((
            "P105_CAPABILITY", f"role_readback_{index}", "15",
            str(f2r), str(r2f)))
    plans["performance"] = [duration_case(
        ids, "primary_300s", PRIMARY_F2R, PRIMARY_R2F, 300)]
    for index in range(1, 6):
        plans[f"streaming_64m_{index}"] = [object_case(
            ids, f"simultaneous_64m_{index}", PRIMARY_F2R, PRIMARY_R2F,
            64 << 20)]

    faults: list[PlanItem] = []
    diagnostics = (
        ("data_f2r", FLAG_DIRECTION_FAULT, 1, 0),
        ("data_r2f", FLAG_DIRECTION_FAULT | FLAG_TARGET_R2F, 1, 0),
        ("ack_f2r", FLAG_DIRECTION_FAULT, 0, 1),
        ("ack_r2f", FLAG_DIRECTION_FAULT | FLAG_TARGET_R2F, 0, 1),
        ("abort_f2r", FLAG_DIRECTION_FAULT | FLAG_ABORT_DIRECTION, 0, 0),
        ("abort_r2f", FLAG_DIRECTION_FAULT | FLAG_TARGET_R2F |
         FLAG_ABORT_DIRECTION, 0, 0),
        ("backpressure_f2r", FLAG_DIRECTION_FAULT | FLAG_DMA_BACKPRESSURE, 0, 0),
        ("backpressure_r2f", FLAG_DIRECTION_FAULT | FLAG_TARGET_R2F |
         FLAG_DMA_BACKPRESSURE, 0, 0),
    )
    clean_index = 0
    for label, flags, drop_data, drop_ack in diagnostics:
        faults.append(object_case(
            ids, f"fault_{label}", PRIMARY_F2R, PRIMARY_R2F,
            INTERNAL_OBJECT_BYTES, flags=flags, drop_data=drop_data,
            drop_ack=drop_ack))
        clean_index += 1
        faults.append(object_case(
            ids, f"fault_clean_{clean_index}", PRIMARY_F2R, PRIMARY_R2F,
            4 * INTERNAL_OBJECT_BYTES))
    for label, mask in (("disable_lane0", 1), ("disable_lane2", 4)):
        faults.append(object_case(
            ids, label, PRIMARY_F2R, PRIMARY_R2F, 4 * INTERNAL_OBJECT_BYTES,
            unavailable=mask))
        clean_index += 1
        faults.append(object_case(
            ids, f"fault_clean_{clean_index}", PRIMARY_F2R, PRIMARY_R2F,
            4 * INTERNAL_OBJECT_BYTES))
    plans["faults"] = faults
    plans["formal_30min"] = [duration_case(
        ids, "formal_primary_1800s", PRIMARY_F2R, PRIMARY_R2F, 1800)]
    return plans


def item_line(item: PlanItem) -> str:
    return item.plan_line() if isinstance(item, P105Case) else " ".join(item)


def plan_text(items: list[PlanItem]) -> str:
    return "\n".join(item_line(item) for item in items) + "\n"


def plan_hashes() -> dict[str, str]:
    return {stage: hashlib.sha256(plan_text(items).encode("ascii")).hexdigest()
            for stage, items in build_plans().items()}


def validate_plans() -> list[str]:
    errors: list[str] = []
    plans = build_plans()
    if tuple(plans) != STAGES:
        errors.append("stage order mismatch")
    try:
        for items in plans.values():
            plan_text(items).encode("ascii")
    except (UnicodeEncodeError, ValueError) as exc:
        errors.append(str(exc))
    one = {(x.f2r, x.r2f) for x in plans["one_plus_one"] if isinstance(x, P105Case)}
    if len(one) != 12 or any(a.bit_count() != b.bit_count() or a.bit_count() != 1
                             for a, b in one):
        errors.append("1+1 matrix is incomplete")
    mixed = [x for x in plans["two_plus_one"] if isinstance(x, P105Case)]
    if len(mixed) != 24:
        errors.append("2+1/1+2 matrix is incomplete")
    two = {(x.f2r, x.r2f) for x in plans["two_plus_two"] if isinstance(x, P105Case)}
    if two != {(3, 12), (12, 3), (5, 10), (10, 5), (9, 6), (6, 9)}:
        errors.append("directed 2+2 matrix mismatch")
    capability = [x for x in plans["capability"] if isinstance(x, P105Case)]
    if len(capability) != 1 or capability[0].duration_ms != 0 or \
            capability[0].size != 4 * INTERNAL_OBJECT_BYTES:
        errors.append("capability gate must be one finite four-object transfer")
    formal = [x for x in plans["formal_30min"] if isinstance(x, P105Case)]
    if len(formal) != 1 or formal[0].duration_ms != 1_800_000:
        errors.append("formal stage is not exactly 1800 seconds")
    return errors


def tcl_stage(stage: str) -> str:
    if stage.startswith("streaming_64m_"):
        return "P10_5-STREAMING_64M"
    return {
        "safe_start": "P10_5-SAFE_START", "capability": "P10_5-CAPABILITY",
        "one_plus_one": "P10_5-ONE_PLUS_ONE",
        "two_plus_one": "P10_5-TWO_PLUS_ONE",
        "two_plus_two": "P10_5-TWO_PLUS_TWO",
        "role_commit": "P10_5-ROLE_COMMIT",
        "performance": "P10_5-PERFORMANCE", "faults": "P10_5-FAULTS",
        "formal_30min": "P10_5-FORMAL_30MIN",
    }[stage]


def stage_runtime_limit(stage: str) -> int:
    return {
        "safe_start": 1, "capability": 10, "one_plus_one": 120,
        "two_plus_one": 480, "two_plus_two": 180, "role_commit": 40,
        "performance": 300, "faults": 900, "formal_30min": 1800,
    }.get(stage, 600)


def stage_host_timeout(stage: str) -> int:
    return stage_runtime_limit(stage) + (360 if stage != "formal_30min" else 300)


def artifact_key(item: dict[str, Any]) -> str:
    return f"{item['role']}:{item['kind']}"


def file_matches_head(path: Path) -> bool:
    try:
        return subprocess.check_output(
            ["git", "show", f"HEAD:{rel(path)}"], cwd=ROOT
        ) == path.read_bytes()
    except (OSError, subprocess.CalledProcessError, ValueError):
        return False


def host_runtime_input_paths() -> dict[str, Path]:
    return {
        "campaign_runner": ROOT / "scripts/run_p10_5_hardware.py",
        "shutdown_tcl": SHUTDOWN_TCL,
        "stage_tcl": STAGE_TCL,
        "forensic_tcl": FORENSIC_TCL,
        "runtime_guard": ROOT / "scripts/p10_tfdu_runtime_guard.py",
    }


def validate_authorization(path: Path, run_id: str) -> tuple[
        dict[str, Any], dict[str, Path], list[str]]:
    errors = validate_plans()
    try:
        freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
        auth = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {}, errors + [f"authorization/freeze unavailable: {exc}"]
    by_key = {artifact_key(x): x for x in freeze.get("artifacts", [])}
    match = RUN_RE.fullmatch(run_id)
    if match is None:
        errors.append("invalid content-bound P10.5 run id")
    else:
        expected_parts = {
            "source": str(freeze.get("source_commit", ""))[:8],
            "fixed": str(by_key.get("fixed:functional_bitstream", {}).get("sha256", ""))[:8],
            "rotating": str(by_key.get("rotating:functional_bitstream", {}).get("sha256", ""))[:8],
        }
        errors += [f"run-id {key} hash mismatch" for key, value in expected_parts.items()
                   if match.group(key) != value]
    expected = {
        "schema_version": 1, "authorization_id": "P10_5-CURRENT-RUN-IMMUTABLE",
        "scope": SCOPE, "run_id": run_id, "authorized": True, "consumed": False,
        "current_run_hardware_authorization": True, "no_hardware": False,
        "goal_sha256": GOAL_SHA256, "source_commit": freeze.get("source_commit"),
        "fixed_jtag_serial": EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": EXPECTED_ROTATING_SERIAL,
        "maximum_lane_mask": 15, "maximum_single_formal_run_seconds": 1800,
        "maximum_continuous_module_runtime_seconds": 1800,
        "minimum_interstage_cooldown_ratio": 0.5,
        "ethernet_allowed": False, "spi_allowed": False,
        "movement_rotation_realignment_rewiring_or_module_replacement_allowed": False,
        "shutdown_policy": SHUTDOWN_POLICY,
    }
    errors += [f"authorization {key} mismatch" for key, value in expected.items()
               if auth.get(key) != value]
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("artifact freeze is not acceptance eligible")
    if auth.get("artifacts") != freeze.get("artifacts"):
        errors.append("authorization artifact set mismatch")
    if auth.get("allowed_stages") != list(STAGES):
        errors.append("authorization stage order mismatch")
    if auth.get("allowed_plan_sha256") != plan_hashes():
        errors.append("authorization plan hashes mismatch")
    if auth.get("module_binding") != MODULE_BINDING:
        errors.append("authorization module binding mismatch")
    if auth.get("register_map") != {
        "version": f"0x{REGISTER_MAP_VERSION:08X}",
        "hash_low": f"0x{REGISTER_MAP_HASH_LOW:08X}",
    }:
        errors.append("authorization register-map mismatch")
    if not file_matches_head(path) or not file_matches_head(FREEZE):
        errors.append("authorization/freeze are not exact committed HEAD files")
    artifacts: dict[str, Path] = {}
    for key, item in by_key.items():
        try:
            candidate = (ROOT / item["path"]).resolve()
            if not inside(candidate, ROOT) or not candidate.is_file() or \
                    candidate.stat().st_size != item["bytes"] or \
                    sha256(candidate) != item["sha256"]:
                errors.append(f"artifact changed: {key}")
            else:
                artifacts[key] = candidate
        except (KeyError, OSError, TypeError, ValueError):
            errors.append(f"malformed artifact: {key}")
    required = {f"{role}:{kind}" for role in ("fixed", "rotating")
                for kind in ("shutdown_bitstream", "functional_bitstream",
                             "xsa", "bsp", "elf")}
    if set(by_key) != required:
        errors.append("artifact set mismatch")
    for name, item in auth.get("offline_inputs", {}).items():
        try:
            candidate = (ROOT / item["path"]).resolve()
            if not candidate.is_file() or sha256(candidate) != item["sha256"]:
                errors.append(f"offline input changed: {name}")
        except (KeyError, OSError, TypeError):
            errors.append(f"malformed offline input: {name}")
    expected_configuration = {
        "actual_wiring": AS_WIRED,
        "module_inventory": MODULE_INVENTORY,
        "dual_direction_config": CONFIG,
        "runtime_rest_policy": RUNTIME_REST_POLICY,
    }
    expected_host = host_runtime_input_paths()
    for section, expected_paths in (
            ("hardware_configuration_inputs", expected_configuration),
            ("host_runtime_inputs", expected_host)):
        records = auth.get(section)
        if not isinstance(records, dict) or set(records) != set(expected_paths):
            errors.append(f"authorization {section} set mismatch")
            continue
        for name, expected_path in expected_paths.items():
            item = records[name]
            try:
                if item != metadata(expected_path):
                    errors.append(f"authorization {section}:{name} mismatch")
            except OSError:
                errors.append(f"authorization {section}:{name} unavailable")
    return auth, artifacts, errors


def initialize_run(run_root: Path, auth: Path,
                   artifacts: dict[str, Path]) -> dict[str, Path]:
    run_root.mkdir(parents=True, exist_ok=False)
    for name in ("authorization", "artifacts", "target_identity", "safe_boot",
                 "capability", "role_masks", "one_plus_one", "two_plus_one",
                 "two_plus_two_partitions", "role_commit", "performance",
                 "streaming_64m", "faults", "formal_30min", "shutdown",
                 "runtime_rest", "stages", "forensics", "raw_logs", "final"):
        (run_root / name).mkdir()
    copies = (
        (auth, run_root / "authorization/immutable_authorization.json"),
        (GOAL, run_root / "authorization/goal.md"),
        (FREEZE, run_root / "artifacts/artifact_freeze.json"),
        (CONFIG, run_root / "artifacts/p10_5_dual_direction.yaml"),
        (REGISTER_MAP, run_root / "artifacts/ir_axi_regs.yaml"),
        (AS_WIRED, run_root / "artifacts/as_wired.yaml"),
        (MODULE_INVENTORY, run_root / "artifacts/module_inventory.yaml"),
        (RUNTIME_REST_POLICY, run_root / "artifacts/runtime_rest_policy.yaml"),
    )
    for source, destination in copies:
        shutil.copy2(source, destination)
    write_text(run_root / "authorization/SCOPE_ATTESTATION.txt",
               "AUTOMATION_ONLY=true\nNETWORK_USED=false\nSPI_USED=false\n"
               "HARDWARE_MOVED=false\nWIRING_CHANGED=false\n"
               "MODULE_REPLACED=false\nMAX_LANE_MASK=0xF\nP11=false\n")
    ps7: dict[str, Path] = {}
    derived = []
    for role in ("fixed", "rotating"):
        destination = run_root / "artifacts" / role / "ps7_init.tcl"
        extract_ps7_init(artifacts[f"{role}:xsa"], destination)
        ps7[role] = destination
        derived.append({"role": role, "file": metadata(destination)})
    write_json(run_root / "artifacts/derived_artifact_manifest.json",
               {"schema_version": 1, "status": "PASS", "files": derived})
    return ps7


def invoke_stage(stage: str, text: str, run_root: Path, auth: Path,
                 artifacts: dict[str, Path], ps7: dict[str, Path],
                 env: dict[str, str]) -> tuple[dict[str, Any], Path]:
    stage_dir = run_root / "stages" / stage
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=False)
    plan = stage_dir / "immutable.plan"
    write_text(plan, text)
    result = stage_dir / "xsdb.result.txt"
    command = [
        str(XSDB), str(STAGE_TCL), "tcp:localhost:3121",
        EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL,
        str(artifacts["fixed:functional_bitstream"]),
        str(artifacts["rotating:functional_bitstream"]),
        str(artifacts["fixed:elf"]), str(artifacts["rotating:elf"]),
        str(ps7["fixed"]), str(ps7["rotating"]), str(plan), str(dump_dir),
        str(run_root / "authorization/ABORT_NOW.txt"), str(result),
        tcl_stage(stage), str(auth), run_root.name,
        f"0x{EXPECTED_BUILD['fixed']:08X}", f"0x{EXPECTED_BUILD['rotating']:08X}",
        f"0x{REGISTER_MAP_VERSION:08X}", f"0x{REGISTER_MAP_HASH_LOW:08X}",
    ]
    process = run_bounded(command, stage_dir / "xsdb.stdout.log",
                          stage_dir / "xsdb.stderr.log",
                          stage_host_timeout(stage), env)
    return process, stage_dir


def configure_shared_helpers() -> None:
    p104.EXPECTED_BUILD = dict(EXPECTED_BUILD)
    p104.REGISTER_MAP_VERSION = REGISTER_MAP_VERSION
    p104.REGISTER_MAP_HASH_LOW = REGISTER_MAP_HASH_LOW


def guarded_shutdown(run_root: Path, auth: Path, artifacts: dict[str, Path],
                     label: str, env: dict[str, str]) -> dict[str, Any]:
    configure_shared_helpers()
    return p104.guarded_shutdown(run_root, auth, artifacts, label, env)


def capture_and_archive(label: str, run_root: Path, auth: Path,
                        env: dict[str, str], force_abort: bool) -> dict[str, Any]:
    configure_shared_helpers()
    return p104.capture_and_archive(label, run_root, auth, env,
                                    force_abort=force_abort)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle, delimiter="|"):
            row: dict[str, Any] = dict(raw)
            for key, value in raw.items():
                if key not in {"label", "window", "fixed_dump_path",
                               "rotating_dump_path", "fixed_p10_1_dump_path",
                               "rotating_p10_1_dump_path",
                               "fixed_p10_1r_dump_path",
                               "rotating_p10_1r_dump_path", "injection_sender"}:
                    row[key] = int(value, 0)
            rows.append(row)
    return rows


def observation_active_runtime_seconds(rows: list[dict[str, Any]]) -> float:
    """Conservatively sum every non-shutdown hardware case interval.

    Firmware result timers can remain unset when a case fails or times out.
    The XSDB observation timestamps bracket the actual armed case and are
    therefore the fail-closed runtime/rest source for those paths.
    """
    active_ms = 0
    for row in rows:
        if int(row["command"]) == 10:
            continue
        started_ms = int(row["started_ms"])
        finished_ms = int(row["finished_ms"])
        if started_ms < 0 or finished_ms < started_ms:
            raise ValueError(
                f"invalid observation runtime for {row.get('label', '<unlabeled>')}"
            )
        active_ms += finished_ms - started_ms
    return active_ms / 1000.0


def parse_words(path: Path, count: int) -> list[int]:
    data = path.read_bytes()
    if len(data) != count * 4:
        raise ValueError(f"unexpected binary size: {path}")
    return list(struct.unpack(f"<{count}I", data))


def u64(words: list[int], index: int) -> int:
    return words[index] | (words[index + 1] << 32)


def parse_p105_result(path: Path, role: str) -> dict[str, Any]:
    words = parse_words(path, 512)
    return {
        "role": role, "words": words, "magic": words[0], "schema": words[1],
        "firmware_build": words[2], "endpoint_role": words[3],
        "service_state": words[4], "status": words[5], "sequence": words[6],
        "flags": words[7], "total_bytes": words[11],
        "object_bytes": words[12], "objects_completed": words[53],
        "application_accepted": u64(words, 42),
        "application_committed": u64(words, 44), "wire_bytes": u64(words, 46),
        "descriptors_submitted": u64(words, 48),
        "descriptors_completed": u64(words, 50),
        "ps_elapsed_ticks": u64(words, 30), "ps_timer_hz": words[38],
        "timer_crosscheck": words[41], "atomic_commit": words[54],
        "remote_commit": words[57], "partial_commit": words[58],
        "duplicate_commit": words[59], "stale_commit": words[60],
        "descriptor_leak": words[61], "double_completion": words[62],
        "integrity_errors": words[63], "crc_bad": words[64],
        "sha_mismatch": words[65], "retry_exhausted": words[66],
        "perf_integrity": words[116], "perf_retry_exhausted": words[117],
        "perf_descriptor_leak": words[118], "perf_double_completion": words[119],
        "input_crc32": words[72], "output_crc32": words[73],
        "input_sha256": "".join(f"{x:08x}" for x in words[74:82]),
        "output_sha256": "".join(f"{x:08x}" for x in words[82:90]),
        "descriptors_reclaimed": words[164], "dual_mode": words[176],
        "active_mask": words[177], "f2r_mask": words[178],
        "r2f_mask": words[179], "local_tx_mask": words[180],
        "local_rx_mask": words[181], "role_epoch": words[182],
        "context_status": words[183], "piggyback_tx": words[184],
        "piggyback_rx": words[185], "control_only_ack": words[186],
        "direction_reject": words[187], "role_epoch_reject": words[188],
        "tx_bytes": words[189], "rx_bytes": words[190],
        "tx_retries": words[191], "tx_timeouts": words[192],
        "tx_axis_stall": words[193], "rx_axis_stall": words[194],
        "application_committed_local": words[203],
        "duration_target_ms": words[204], "duration_elapsed_ms": words[205],
        "stream_ceiling_bytes": words[206], "prefetched_reclaimed": words[207],
        "fault_kind": words[208], "fault_target": words[209],
        "unaffected_progress": words[210], "affected_commit": words[211],
        "fault_recovery_pass": words[212], "diagnostic_before": words[213],
        "diagnostic_after": words[214], "diagnostic_stall_delta": words[215],
        "launch_barrier_waited": words[216],
        "launch_release_seen": words[217],
        "launch_wait_ticks": u64(words, 218),
        "launch_rx_object_prestarted": words[220],
        "launch_tx_descriptors_held": words[221],
        "launch_tx_descriptors_released": words[222],
        "launch_prestart_context_status": words[223],
        "initial_tx_descriptors_held_total": words[224],
        "inter_object_rx_lead_us": words[225],
        "deferred_tx_objects_released": words[226],
        "unique_object_sessions_programmed": words[227],
    }


def transport_timeout_is_hard_failure(stage: str) -> bool:
    """The Goal requires a zero transport-timeout count only for formal."""
    return stage == "formal_30min"


def dma_backpressure_evidence_errors(
        label: str, case: P105Case, result: dict[str, Any]) -> list[str]:
    """Validate the one endpoint that actually executes a direction fault.

    Firmware injects DMA TX backpressure only when the endpoint's local TX
    direction equals ``direction_fault_target``.  F_TO_R therefore executes
    on fixed and R_TO_F executes on rotating.  Requiring the peer endpoint to
    report the same local diagnostic stall is both impossible and masks a
    useful isolation check: the peer must remain unarmed with zero injected
    stall delta.
    """
    if not case.flags & FLAG_DMA_BACKPRESSURE:
        return []
    role = result["role"]
    injected_role = "rotating" if case.flags & FLAG_TARGET_R2F else "fixed"
    armed_before = bool(result["diagnostic_before"] & 1)
    armed_after = bool(result["diagnostic_after"] & 1)
    stall_delta = result["diagnostic_stall_delta"]
    if role == injected_role:
        if armed_before or armed_after or stall_delta <= 0:
            return [f"{label}:{role}: DMA backpressure evidence"]
    elif armed_before or armed_after or stall_delta != 0:
        return [f"{label}:{role}: unexpected DMA backpressure evidence"]
    return []


def result_errors(stage: str, label: str, case: P105Case,
                  result: dict[str, Any]) -> list[str]:
    role = result["role"]
    errors: list[str] = []
    expected_local_tx = case.f2r if role == "fixed" else case.r2f
    expected_local_rx = case.r2f if role == "fixed" else case.f2r
    launch_limit_ticks = (LAUNCH_BARRIER_TIMEOUT_MS * result["ps_timer_hz"] // 1000
                          if result["ps_timer_hz"] else 0)
    checks = {
        "result identity": result["magic"] == 0x31303150 and result["schema"] == 1,
        "firmware build": result["firmware_build"] == EXPECTED_BUILD[role],
        "endpoint role": result["endpoint_role"] == (1 if role == "fixed" else 2),
        "terminal service": result["service_state"] == 6 and result["status"] == 0,
        "dual mode": result["dual_mode"] == 1,
        "global masks": (result["active_mask"], result["f2r_mask"],
                         result["r2f_mask"]) == (case.active, case.f2r, case.r2f),
        "local masks": (result["local_tx_mask"], result["local_rx_mask"]) ==
                       (expected_local_tx, expected_local_rx),
        "role epoch": result["role_epoch"] > 0,
        "timer crosscheck": result["timer_crosscheck"] == 1,
        "direction reject": result["direction_reject"] == 0,
        "physical TX evidence": result["tx_bytes"] > 0,
        "physical RX evidence": result["rx_bytes"] > 0,
        "paired launch barrier":
            result["launch_barrier_waited"] == 1 and
            result["launch_release_seen"] == 1 and
            0 < result["launch_wait_ticks"] <= launch_limit_ticks,
        "RX-first TX-deferred launch":
            result["launch_rx_object_prestarted"] == 1 and
            result["launch_tx_descriptors_held"] > 0 and
            result["launch_tx_descriptors_released"] ==
                result["launch_tx_descriptors_held"] and
            (result["launch_prestart_context_status"] & 0x8F) == 0x09,
        "multi-object RX-first release":
            result["initial_tx_descriptors_held_total"] >=
                result["launch_tx_descriptors_held"] and
            result["inter_object_rx_lead_us"] == INTER_OBJECT_RX_LEAD_US and
            result["deferred_tx_objects_released"] >= 1 and
            result["unique_object_sessions_programmed"] >=
                result["deferred_tx_objects_released"],
    }
    errors += [f"{label}:{role}: {name}" for name, passed in checks.items() if not passed]
    if transport_timeout_is_hard_failure(stage) and result["tx_timeouts"] != 0:
        errors.append(f"{label}:{role}: formal transport timeout is nonzero")
    for name in ("partial_commit", "duplicate_commit", "stale_commit",
                 "descriptor_leak", "double_completion", "integrity_errors",
                 "crc_bad", "sha_mismatch", "retry_exhausted",
                 "perf_integrity", "perf_retry_exhausted",
                 "perf_descriptor_leak", "perf_double_completion"):
        if result[name] != 0:
            errors.append(f"{label}:{role}: {name} is nonzero")
    stale_role = bool(case.flags & FLAG_STALE_ROLE)
    if stale_role != (result["role_epoch_reject"] > 0):
        errors.append(f"{label}:{role}: stale role-epoch rejection mismatch")
    abort = bool(case.flags & FLAG_ABORT_DIRECTION)
    if not abort and not case.duration_ms:
        expected_objects = math.ceil(case.size / INTERNAL_OBJECT_BYTES)
        if result["objects_completed"] != expected_objects or \
                result["deferred_tx_objects_released"] != expected_objects or \
                result["unique_object_sessions_programmed"] != expected_objects:
            errors.append(f"{label}:{role}: multi-object boundary accounting mismatch")
    if not abort:
        if result["application_committed"] <= 0 or \
                result["application_committed_local"] <= 0 or \
                result["input_crc32"] != result["output_crc32"] or \
                result["input_sha256"] != result["output_sha256"]:
            errors.append(f"{label}:{role}: application integrity/commit mismatch")
        if result["atomic_commit"] != 1 or result["remote_commit"] != 1:
            errors.append(f"{label}:{role}: atomic remote commit missing")
    if case.duration_ms:
        if result["duration_target_ms"] != case.duration_ms or \
                not case.duration_ms <= result["duration_elapsed_ms"] <= case.duration_ms + 50:
            errors.append(f"{label}:{role}: duration evidence mismatch")
        if result["stream_ceiling_bytes"] != case.size:
            errors.append(f"{label}:{role}: stream ceiling mismatch")
    else:
        if result["duration_target_ms"] != 0 or result["total_bytes"] != case.size:
            errors.append(f"{label}:{role}: fixed-size stream mismatch")
    if case.flags & FLAG_DIRECTION_FAULT:
        expected_kind = 1 if case.drop_data else 2 if case.drop_ack else \
            3 if abort else 4
        expected_target = 1 if case.flags & FLAG_TARGET_R2F else 0
        if (result["fault_kind"], result["fault_target"],
            result["fault_recovery_pass"]) != (expected_kind, expected_target, 1):
            errors.append(f"{label}:{role}: direction-fault classification/recovery")
        if result["unaffected_progress"] <= 0 or \
                result["affected_commit"] != (0 if abort else 1):
            errors.append(f"{label}:{role}: direction isolation evidence")
        errors += dma_backpressure_evidence_errors(label, case, result)
    return errors


def case_goodput(case: P105Case, fixed: dict[str, Any],
                 rotating: dict[str, Any]) -> dict[str, float]:
    def elapsed(result: dict[str, Any]) -> float:
        if result["duration_elapsed_ms"]:
            return result["duration_elapsed_ms"] / 1000.0
        return (result["ps_elapsed_ticks"] / result["ps_timer_hz"]
                if result["ps_timer_hz"] else 0.0)
    return {
        "F_TO_R": 8.0 * rotating["application_committed"] / elapsed(rotating)
        if elapsed(rotating) else 0.0,
        "R_TO_F": 8.0 * fixed["application_committed"] / elapsed(fixed)
        if elapsed(fixed) else 0.0,
    }


def parse_capability_files(stage_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for path in sorted((stage_dir / "dumps").glob("*.p10_5_capability.psv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            parsed = list(csv.DictReader(handle, delimiter="|"))
        if len(parsed) != 2 or {x["role"] for x in parsed} != {"fixed", "rotating"}:
            errors.append(f"malformed capability evidence: {path.name}")
            continue
        for raw in parsed:
            row = {"label": path.stem.split(".")[0], "role": raw["role"]}
            row.update({key: int(value, 0) for key, value in raw.items() if key != "role"})
            rows.append(row)
    return rows, errors


def evaluate_stage(stage: str, stage_dir: Path, process: dict[str, Any],
                   archive: dict[str, Any], items: list[PlanItem]) -> dict[str, Any]:
    errors: list[str] = []
    markers = parse_markers(stage_dir / "xsdb.result.txt")
    if process.get("returncode") != 0 or process.get("timed_out"):
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS" or \
            markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("safe-boot/stage PASS marker missing")
    if archive.get("status") != "PASS" or archive.get("frozen_roles"):
        errors.append("normal stage forensic archive is failed or frozen")
    obs_path = stage_dir / "dumps/observations.psv"
    rows = load_rows(obs_path) if obs_path.is_file() else []
    try:
        observation_runtime = observation_active_runtime_seconds(rows)
    except (KeyError, TypeError, ValueError) as exc:
        errors.append(f"observation active-runtime evidence: {exc}")
        observation_runtime = 0.0
    expected_labels = [x.label for x in items if isinstance(x, P105Case)]
    for item in items:
        if isinstance(item, tuple) and item and item[0] == "CASE":
            expected_labels.append(item[1])
    observed = [x["label"] for x in rows if x["command"] != 10]
    if observed != expected_labels or not rows or rows[-1]["command"] != 10:
        errors.append("observation sequence differs from immutable plan")
    case_by_label = {x.label: x for x in items if isinstance(x, P105Case)}
    details: list[dict[str, Any]] = []
    active_runtime = 0.0
    for row in rows:
        label = row["label"]
        for role in ("fixed", "rotating"):
            try:
                mailbox = Path(row[f"{role}_dump_path"]).resolve()
                if not inside(mailbox, stage_dir):
                    raise ValueError("mailbox path escaped stage")
                words = parse_words(mailbox, 256)
                expected_state = 6 if row["command"] == 10 else 4
                if words[0] != 0x424D3950 or words[1] != 5 or \
                        words[2] != EXPECTED_BUILD[role] or words[3] != expected_state or \
                        words[8] != 0 or words[33] != EXPECTED_BUILD[role] or \
                        words[34] != EXPECTED_PROFILE[role] or \
                        words[35] != REGISTER_MAP_VERSION or \
                        words[36] != REGISTER_MAP_HASH_LOW or \
                        words[37] != EXPECTED_CAPABILITIES:
                    errors.append(f"{label}:{role}: mailbox identity/result mismatch")
                snapshot = p103.parse_p103(
                    stage_dir / "dumps" / f"{label}.{role}.p10_2.psv")
                errors += p103.snapshot_errors(label, role, snapshot)
            except (OSError, ValueError, KeyError, struct.error) as exc:
                errors.append(f"{label}:{role}: evidence parse: {exc}")
        if row["command"] != 15:
            continue
        case = case_by_label.get(label)
        if case is None:
            errors.append(f"{label}: command-15 case absent from plan")
            continue
        pair: dict[str, Any] = {"label": label, "case": case.__dict__}
        try:
            for role in ("fixed", "rotating"):
                path = Path(row[f"{role}_p10_1_dump_path"]).resolve()
                if not inside(path, stage_dir):
                    raise ValueError("P10.5 result path escaped stage")
                result = parse_p105_result(path, role)
                errors += result_errors(stage, label, case, result)
                pair[role] = {key: value for key, value in result.items() if key != "words"}
            if pair["fixed"]["role_epoch"] != pair["rotating"]["role_epoch"]:
                errors.append(f"{label}: endpoint role epochs differ")
            pair["application_goodput_bps"] = case_goodput(
                case, pair["fixed"], pair["rotating"])
            elapsed = max(pair[role]["duration_elapsed_ms"] / 1000.0
                          if pair[role]["duration_elapsed_ms"] else
                          pair[role]["ps_elapsed_ticks"] / pair[role]["ps_timer_hz"]
                          for role in ("fixed", "rotating"))
            active_runtime += elapsed
            details.append(pair)
        except (OSError, ValueError, KeyError, ZeroDivisionError, struct.error) as exc:
            errors.append(f"{label}: P10.5 result parse: {exc}")
    active_runtime = max(active_runtime, observation_runtime)
    capabilities, capability_errors = parse_capability_files(stage_dir)
    errors += capability_errors
    if stage == "capability" and len(capabilities) != 4:
        errors.append("pre/post capability readback set is incomplete")
    if stage == "role_commit":
        epochs = [x["fixed"]["role_epoch"] for x in details]
        if len(epochs) != 4 or any(b <= a for a, b in zip(epochs, epochs[1:])):
            errors.append("role epoch did not strictly increment at atomic commits")
        if not details or not all(x["fixed"]["role_epoch_reject"] > 0 and
                                  x["rotating"]["role_epoch_reject"] > 0
                                  for x in details[:1]):
            errors.append("stale role-epoch hardware rejection was not observed")
    if stage in {"performance", "formal_30min"} and details:
        for direction, bps in details[0]["application_goodput_bps"].items():
            if bps < 4_000_000:
                errors.append(f"{stage}: {direction} goodput below 4 Mbit/s")
    if stage.startswith("streaming_64m_") and details:
        if any(details[0][role]["application_committed"] != 64 << 20
               for role in ("fixed", "rotating")):
            errors.append("simultaneous 64 MiB commit mismatch")
    if stage == "faults":
        diagnostic = [x for x in details if x["case"]["flags"] & FLAG_DIRECTION_FAULT]
        if len(diagnostic) != 8:
            errors.append("direction-isolated diagnostic set is incomplete")
    if stage == "formal_30min" and details:
        if any(details[0][role]["duration_elapsed_ms"] != 1_800_000
               for role in ("fixed", "rotating")):
            errors.append("formal simultaneous duration is not 1800 seconds")
    return {
        "schema_version": 1, "test_id": f"P10_5-{stage.upper()}",
        "stage": stage, "status": "PASS" if not errors else "FAIL",
        "process": process, "markers": markers, "errors": errors,
        "details": details, "capability_readbacks": capabilities,
        "observations": rel(obs_path) if obs_path.is_file() else None,
        "observation_active_runtime_seconds": observation_runtime,
        "active_runtime_seconds": active_runtime if active_runtime > 0 else 0.001,
    }


def aggregate_counters(stages: list[dict[str, Any]]) -> dict[str, int]:
    names = ("partial_commit", "duplicate_commit", "stale_commit",
             "descriptor_leak", "double_completion", "integrity_errors",
             "crc_bad", "sha_mismatch", "retry_exhausted", "tx_timeouts")
    return {name: max([0] + [int(pair[role].get(name, 0))
                             for stage in stages for pair in stage.get("details", [])
                             for role in ("fixed", "rotating")]) for name in names}


def formal_transport_timeout_zero(stages: list[dict[str, Any]]) -> bool:
    formal = next((stage for stage in stages
                   if stage.get("stage") == "formal_30min"), None)
    if formal is None or not formal.get("details"):
        return False
    return all(int(pair.get(role, {}).get("tx_timeouts", -1)) == 0
               for pair in formal["details"]
               for role in ("fixed", "rotating"))


def tx_capable_runtime_seconds(stage: str, result: dict[str, Any]) -> float:
    measured = float(result["active_runtime_seconds"])
    if stage != "formal_30min":
        return measured
    details = result.get("details") or []
    if len(details) != 1:
        raise RuntimeError("formal TX-capable interval evidence is incomplete")
    durations = [
        int(details[0].get(role, {}).get("duration_elapsed_ms", 0))
        for role in ("fixed", "rotating")
    ]
    if any(value <= 0 for value in durations):
        raise RuntimeError("formal TX-capable interval evidence is invalid")
    return max(durations) / 1000.0


def finish_runtime_stage(
        guard: RuntimeRestGuard, *, shutdown_verified: bool,
        measured_runtime_seconds: float,
        tx_capable_runtime_seconds: float) -> dict[str, Any]:
    try:
        record = guard.finish_stage(
            shutdown_verified=shutdown_verified,
            measured_runtime_seconds=measured_runtime_seconds,
            tx_capable_runtime_seconds=tx_capable_runtime_seconds,
        )
    except BaseException:
        guard.wait_for_cooldown()
        raise
    guard.wait_for_cooldown()
    return record


def aggregate_shutdown_evidence(shutdowns: list[dict[str, Any]]) -> dict[str, Any]:
    fixed = bool(shutdowns) and all(
        item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdowns)
    rotating = bool(shutdowns) and all(
        item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdowns)
    all_shutdown = fixed and rotating and all(
        item.get("status") == "PASS" for item in shutdowns)
    return {
        "all_shutdown": all_shutdown,
        "SHUTDOWN_FIXED": "PASS" if fixed else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if rotating else "FAIL",
    }


def aggregate_capability_evidence(stages: list[dict[str, Any]]) -> dict[str, Any]:
    results = [pair[role] for stage in stages
               for pair in stage.get("details", [])
               for role in ("fixed", "rotating")]
    piggyback_tx = max([0] + [int(x.get("piggyback_tx", 0)) for x in results])
    piggyback_rx = max([0] + [int(x.get("piggyback_rx", 0)) for x in results])
    control_only = max([0] + [int(x.get("control_only_ack", 0)) for x in results])
    two_plus_two_pairs = [pair for stage in stages
                          if stage.get("stage") == "two_plus_two"
                          for pair in stage.get("details", [])]
    two_plus_two_tx_executed = len(two_plus_two_pairs) == 6 and all(
        int(pair.get(role, {}).get("tx_bytes", 0)) > 0 and
        int(pair.get(role, {}).get("rx_bytes", 0)) > 0
        for pair in two_plus_two_pairs for role in ("fixed", "rotating"))
    return {
        "ack_piggyback_tx_observed": piggyback_tx > 0,
        "ack_piggyback_rx_observed": piggyback_rx > 0,
        "control_only_ack_fallback_observed": control_only > 0,
        "two_plus_two_tx_executed": two_plus_two_tx_executed,
        "maximum_piggyback_tx_count": piggyback_tx,
        "maximum_piggyback_rx_count": piggyback_rx,
        "maximum_control_only_ack_count": control_only,
    }


def evidence_manifest(run_root: Path) -> dict[str, Any]:
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    files = []
    for path in sorted(x for x in run_root.rglob("*") if x.is_file() and
                       x != manifest_path):
        files.append({"path": path.relative_to(run_root).as_posix(),
                      "sha256": sha256(path), "bytes": path.stat().st_size})
    payload = {"schema_version": 1, "status": "PASS", "run_id": run_root.name,
               "file_count": len(files), "files": files}
    write_json(manifest_path, payload)
    return payload


def publish_generated(summary: dict[str, Any], run_root: Path) -> None:
    by_stage = {x["stage"]: x for x in summary["stages"]}
    groups = {
        "safe_boot": ["safe_start", "capability"],
        "1plus1": ["one_plus_one"], "2plus1": ["two_plus_one"],
        "2plus2_partitions": ["two_plus_two"], "role_commit": ["role_commit"],
        "performance": ["performance"],
        "streaming_64m": [f"streaming_64m_{i}" for i in range(1, 6)],
        "faults": ["faults"], "formal_30min": ["formal_30min"],
    }
    common = {key: summary[key] for key in (
        "schema_version", "run_id", "artifact_source_commit",
        "hardware_actions_executed", "current_run_hardware_authorization")}
    for name, stages in groups.items():
        selected = [by_stage[x] for x in stages if x in by_stage]
        payload = {**common, "test_id": f"P10_5-{name.upper()}",
                   "status": "PASS" if len(selected) == len(stages) and
                   all(x["status"] == "PASS" for x in selected) else "FAIL",
                   "stages": selected, "errors": [e for x in selected
                                                     for e in x.get("errors", [])]}
        write_pair(GENERATED / f"p10_5_{name}", payload, f"P10.5 {name}")
    write_pair(GENERATED / "p10_5_shutdown", {
        **common, "test_id": "P10_5-SHUTDOWN",
        "status": "PASS" if summary["SHUTDOWN_FIXED"] ==
        summary["SHUTDOWN_ROTATING"] == "PASS" else "FAIL",
        "SHUTDOWN_FIXED": summary["SHUTDOWN_FIXED"],
        "SHUTDOWN_ROTATING": summary["SHUTDOWN_ROTATING"],
        "errors": [],
    }, "P10.5 shutdown")
    write_pair(GENERATED / "p10_5_final_summary", summary, "P10.5 final summary")
    write_pair(run_root / "final/p10_5_final_summary", summary,
               "P10.5 final summary")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args(argv)
    auth_path = args.authorization.resolve()
    authorization, artifacts, errors = validate_authorization(auth_path, args.run_id)
    if args.validate_only:
        print(json.dumps({"status": "PASS" if not errors else "FAIL",
                          "errors": errors}, indent=2))
        return 0 if not errors else 3
    if not args.execute_hardware:
        errors.append("--execute-hardware is required")
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "true":
        errors.append("NO_HARDWARE=0 and current-run authorization=true required")
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                               text=True).strip():
        errors.append("worktree must be clean at hardware launch")
    run_root = HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("run-id evidence directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2), file=sys.stderr)
        return 3
    env = {**os.environ, "NO_HARDWARE": "0",
           "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
           "RF_COMM_P10_HW_AUTH": "P10_5_IMMUTABLE_AUTHORIZED"}
    ps7 = initialize_run(run_root, auth_path, artifacts)
    runtime_guard = RuntimeRestGuard(load_policy(RUNTIME_REST_POLICY),
                                     run_root / "runtime_rest/runtime_rest_ledger.json",
                                     ALL_MODULES)
    server_proc = None
    stage_results: list[dict[str, Any]] = []
    shutdowns: list[dict[str, Any]] = []
    forensics: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    active_stage: str | None = None
    archived = True
    runtime_active = False
    hardware_actions = False
    plans = build_plans()
    try:
        server_proc, server = start_hw_server(run_root / "raw_logs")
        hardware_actions = True
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server failed"))
        initial = guarded_shutdown(run_root, auth_path, artifacts, "initial", env)
        shutdowns.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for stage in STAGES:
            runtime_guard.wait_for_cooldown()
            active_stage = stage
            archived = False
            before = guarded_shutdown(run_root, auth_path, artifacts,
                                      f"{stage}_before", env)
            shutdowns.append(before)
            if before.get("status") != "PASS":
                raise RuntimeError(f"{stage}: shutdown-before unconfirmed")
            text = plan_text(plans[stage])
            if hashlib.sha256(text.encode("ascii")).hexdigest() != \
                    authorization["allowed_plan_sha256"][stage]:
                raise RuntimeError(f"{stage}: immutable plan mismatch")
            runtime_guard.begin_stage(stage, stage_runtime_limit(stage))
            runtime_active = True
            process, stage_dir = invoke_stage(
                stage, text, run_root, auth_path, artifacts, ps7, env)
            archive = capture_and_archive(
                stage, run_root, auth_path, env,
                force_abort=bool(process.get("returncode") != 0 or
                                 process.get("timed_out")))
            forensics.append(archive)
            archived = archive.get("status") == "PASS"
            if not archived:
                raise RuntimeError(f"{stage}: forensic archive failed")
            after = guarded_shutdown(run_root, auth_path, artifacts,
                                     f"{stage}_after", env)
            shutdowns.append(after)
            result = evaluate_stage(stage, stage_dir, process, archive, plans[stage])
            measured = float(result["active_runtime_seconds"])
            limit_runtime = tx_capable_runtime_seconds(stage, result)
            try:
                record = finish_runtime_stage(
                    runtime_guard,
                    shutdown_verified=after.get("status") == "PASS",
                    measured_runtime_seconds=measured,
                    tx_capable_runtime_seconds=limit_runtime)
            finally:
                runtime_active = False
            result["runtime_rest"] = dict(record)
            result["shutdown_before_status"] = before.get("status")
            result["shutdown_after_status"] = after.get("status")
            stage_results.append(result)
            if after.get("status") != "PASS" or result["status"] != "PASS":
                raise RuntimeError(f"{stage}: mandatory stage failed closed")
        final = guarded_shutdown(run_root, auth_path, artifacts, "final", env)
        shutdowns.append(final)
        if final.get("status") != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except BaseException as exc:
        campaign_errors.append(str(exc))
    finally:
        if active_stage is not None and not archived:
            try:
                forensics.append(capture_and_archive(
                    f"{active_stage}_finally_before_shutdown", run_root,
                    auth_path, env, force_abort=True))
            except BaseException as exc:
                campaign_errors.append(f"finally forensic capture: {exc}")
        emergency = guarded_shutdown(run_root, auth_path, artifacts, "finally", env)
        shutdowns.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally dual shutdown unconfirmed")
        if runtime_active:
            try:
                runtime_guard.finish_stage(
                    shutdown_verified=emergency.get("status") == "PASS")
                runtime_guard.wait_for_cooldown()
            except BaseException as exc:
                campaign_errors.append(f"runtime/rest finalization: {exc}")
        if server_proc is not None:
            try:
                terminate_tree(server_proc)
            except BaseException as exc:
                campaign_errors.append(f"hw_server termination: {exc}")

    shutdown_evidence = aggregate_shutdown_evidence(shutdowns)
    all_shutdown = shutdown_evidence["all_shutdown"]
    all_stages = len(stage_results) == len(STAGES) and all(
        x["status"] == "PASS" for x in stage_results)
    counters = aggregate_counters(stage_results)
    capabilities = aggregate_capability_evidence(stage_results)
    integrity_hard_zero = all(value == 0 for name, value in counters.items()
                              if name != "tx_timeouts")
    formal_timeout_zero = formal_transport_timeout_zero(stage_results)
    feature_pass = all(bool(capabilities[key]) for key in (
        "ack_piggyback_tx_observed", "ack_piggyback_rx_observed",
        "control_only_ack_fallback_observed", "two_plus_two_tx_executed"))
    runtime_ledger = runtime_guard.public_ledger()
    runtime_pass = runtime_ledger.get("status") == "PASS"
    status = "PASS" if all_shutdown and all_stages and integrity_hard_zero and \
        formal_timeout_zero and feature_pass and runtime_pass and \
        not campaign_errors else "FAIL"
    performance = next((x for x in stage_results if x["stage"] == "performance"), {})
    perf_pair = (performance.get("details") or [{}])[0]
    goodput = perf_pair.get("application_goodput_bps", {})
    formal = next((x for x in stage_results if x["stage"] == "formal_30min"), {})
    formal_pair = (formal.get("details") or [{}])[0]
    summary = {
        "schema_version": 1, "test_id": "P10_5-FINAL", "status": status,
        "scope": SCOPE, "run_id": args.run_id, "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": authorization["source_commit"],
        "artifacts": authorization["artifacts"],
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False, "automation_only": True,
        "user_hold_points": 0, "network_used": False, "spi_used": False,
        "hardware_moved": False, "wiring_changed": False,
        "module_replaced": False,
        "module_replaced_during_run": False,
        "pre_run_user_module_replacement": {
            "logical_module": "R3", "position": "AX7020-R/J11-B",
            "removed_small_board_id": "B0025",
            "installed_small_board_id": "B0011",
            "identity_basis": "USER_REPORTED_NOT_INDEPENDENTLY_VERIFIED",
            "replacement_power_state": "NOT_STATED_BY_USER; NOT_CLAIMED",
            "codex_physical_action": False,
        },
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "minimum_interstage_cooldown_ratio": 0.5,
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}"},
        "module_binding": MODULE_BINDING, "operating_mode":
        "SPLIT_LANE_SIMULTANEOUS_BIDIRECTIONAL",
        "active_lane_mask": 15, "f_to_r_lane_mask": 3, "r_to_f_lane_mask": 12,
        "application_goodput_bps": goodput,
        "stretch_4p8mbps": {key: value >= 4_800_000 for key, value in goodput.items()},
        "formal_committed_bytes": {
            "F_TO_R": formal_pair.get("rotating", {}).get("application_committed"),
            "R_TO_F": formal_pair.get("fixed", {}).get("application_committed")},
        "counters": counters,
        "nonformal_transport_timeouts_are_diagnostic": True,
        "formal_transport_timeout_zero": formal_timeout_zero,
        "integrity_hard_counters_zero": integrity_hard_zero,
        "capability_evidence": capabilities,
        "TWO_PLUS_TWO_TX_EXECUTED": capabilities["two_plus_two_tx_executed"],
        "stages": stage_results,
        "runtime_rest_ledger": runtime_ledger, "forensics": forensics,
        "shutdowns": shutdowns,
        "SHUTDOWN_FIXED": shutdown_evidence["SHUTDOWN_FIXED"],
        "SHUTDOWN_ROTATING": shutdown_evidence["SHUTDOWN_ROTATING"],
        "p11_status": "NOT_STARTED", "errors": campaign_errors,
        "generated_at_utc": utc_now(),
    }
    publish_generated(summary, run_root)
    manifest = evidence_manifest(run_root)
    consistency = {
        "schema_version": 1, "test_id": "P10_5-EVIDENCE-CONSISTENCY",
        "status": "PASS", "run_id": args.run_id,
        "artifact_source_commit": authorization["source_commit"],
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False,
        "manifest": rel(run_root / "final/run_evidence_sha256_manifest.json"),
        "manifest_file_count": manifest["file_count"], "errors": [],
    }
    write_pair(GENERATED / "p10_5_evidence_consistency", consistency,
               "P10.5 evidence consistency")
    consumed = dict(authorization)
    consumed.update({"status": f"CONSUMED_AFTER_P10_5_{status}",
                     "authorized": False, "consumed": True,
                     "current_run_hardware_authorization": False,
                     "no_hardware": True, "consumed_at_utc": utc_now(),
                     "result": rel(run_root / "final/p10_5_final_summary.json")})
    write_json(auth_path, consumed)
    write_pair(GENERATED / "p10_5_authorization", {
        "schema_version": 1, "test_id": "P10_5-AUTHORIZATION",
        "status": consumed["status"], "run_id": args.run_id,
        "artifact_source_commit": authorization["source_commit"],
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False,
        "authorization": rel(auth_path), "consumed": True, "errors": [],
    }, "P10.5 current-run authorization")
    print(f"P10_5_HARDWARE={status}")
    print(f"P10_5_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
