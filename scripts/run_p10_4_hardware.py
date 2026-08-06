#!/usr/bin/env python3
"""Fail-closed autonomous P10.4 four-lane hardware campaign.

The runner is inert unless the exact committed current-run authorization and
both environment gates are present.  Every stage is bracketed by role-bound
dual shutdown programming.  A PL first-fault recorder is read, canonically
archived, SHA256-committed, and only then replaced by the independent shutdown
images.  Nonblocking P10.4 experiments are preserved without promoting them to
the mandatory stationary half-duplex scope.
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
import struct
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_3_ax7020_4lane_hardware as base
import run_p10_3f_full_hardware as legacy
import run_p10_3f_staircase_hardware as forensic
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


ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / "goals/P10_4_AUTONOMOUS_4LANE_HARDENING_GOAL.md"
GOAL_SHA256 = "0098acc827d22ad8f72876f5551e70d8051452e0c81eb2bfe8986e142f47254f"
SCOPE = "P10_4_AUTONOMOUS_4LANE_PERFORMANCE_ROBUSTNESS_AND_2PLUS2_EXPERIMENT"
FREEZE = ROOT / "evidence/generated/p10_4_artifact_freeze.json"
AUTH = ROOT / "config/p10_4_current_run_hardware_authorization.json"
CONFIG = ROOT / "config/performance/p10_4_hardening.yaml"
MODEL = ROOT / "evidence/generated/p10_4_model_reconciliation_offline.json"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
FORENSIC_TCL = ROOT / "scripts/hw/p10_3f_fault_forensics.tcl"
HW_ROOT = ROOT / "evidence/hardware/p10_4"
GENERATED = ROOT / "evidence/generated"
EXPECTED_BUILD = {"fixed": 0x50343446, "rotating": 0x50343452}
REGISTER_MAP_VERSION = 0x0A000004
REGISTER_MAP_HASH_LOW = 0xBCFECB39
INTERNAL_OBJECT_BYTES = 262_144
MAX_AGGREGATE_BYTES = 128 << 20
MODULE_BINDING = {
    "F0": "A0019", "F1": "B0012", "F2": "B0008", "F3": "B0020",
    "R0": "A0010", "R1": "A0017", "R2": "B0023", "R3": "B0025",
}
RUN_RE = re.compile(
    r"^p10_4_(?P<utc>[0-9]{8}T[0-9]{6}Z)_"
    r"(?P<source>[0-9a-f]{8})_(?P<fixed>[0-9a-f]{8})_"
    r"(?P<rotating>[0-9a-f]{8})$"
)
SHUTDOWN_POLICY = {
    "shutdown_before_every_stage": True,
    "archive_before_independent_shutdown": True,
    "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
    "verify_both_shutdown_markers": True,
    "clear_frozen_capture_before_shutdown_program": False,
}
NONBLOCKING_STAGES = {"streaming_128m", "two_plus_two"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def write_pair(base_path: Path, payload: dict[str, Any], title: str) -> None:
    write_json(base_path.with_suffix(".json"), payload)
    lines = [f"# {title}", "", f"- Status: `{payload.get('status')}`"]
    for key in (
        "test_id", "run_id", "artifact_source_commit",
        "hardware_actions_executed", "current_run_hardware_authorization",
    ):
        if key in payload:
            lines.append(f"- {key}: `{payload[key]}`")
    errors = payload.get("errors", [])
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {item}" for item in errors])
    write_text(base_path.with_suffix(".md"), "\n".join(lines) + "\n")


def file_matches_head(path: Path) -> bool:
    try:
        committed = subprocess.check_output(
            ["git", "show", f"HEAD:{rel(path)}"], cwd=ROOT
        )
    except subprocess.CalledProcessError:
        return False
    return committed == path.read_bytes()


def artifact_key(item: dict[str, Any]) -> str:
    return f"{item['role']}:{item['kind']}"


def load_config() -> dict[str, Any]:
    return base.load_yaml(CONFIG)


def baseline_config() -> dict[str, Any]:
    return {
        "name": "p10_3_baseline", "ring_depth": 32, "cache_batching": 1,
        "buffer_count": 4, "descriptor_batch": 8, "ack_threshold": 32,
        "outstanding": 32, "object_bytes": INTERNAL_OBJECT_BYTES,
        "descriptor_bytes": 65_536,
    }


def candidate_configs() -> list[dict[str, Any]]:
    raw = load_config()["tuning"]["candidates"]
    output = []
    for item in raw:
        merged = baseline_config()
        merged.update(item)
        output.append(merged)
    if not output or len(output) > 12:
        raise ValueError("P10.4 tuning candidate set is empty or exceeds 12")
    return output


def config_line(item: dict[str, Any]) -> str:
    return "P104_CONFIG {name} {ring_depth} {cache_batching} {buffer_count} " \
        "{descriptor_batch} {ack_threshold} {outstanding} {object_bytes} " \
        "{descriptor_bytes}".format(**item)


class ObjectIds:
    def __init__(self) -> None:
        self.next = 0x74000000

    def allocate(self, total_bytes: int = INTERNAL_OBJECT_BYTES) -> int:
        count = math.ceil(total_bytes / INTERNAL_OBJECT_BYTES)
        value = self.next
        self.next += count
        if self.next > 0x7F000000:
            raise ValueError("P10.4 object-ID range exhausted")
        return value


def total_line(label: str, size: int, direction: int, mask: int,
               unavailable: int, ids: ObjectIds) -> str:
    if size % INTERNAL_OBJECT_BYTES or not (
        INTERNAL_OBJECT_BYTES <= size <= MAX_AGGREGATE_BYTES
    ):
        raise ValueError(f"invalid aggregate size: {label}")
    return (
        f"P10FF_TOTAL {label} {size} {direction} {mask} {unavailable} "
        f"0x{ids.allocate(size):08X}"
    )


def stream_fault_case(label: str, direction: int, flag: int,
                      ids: ObjectIds) -> str:
    case = base.stream_case(
        label, size=2 * INTERNAL_OBJECT_BYTES, direction=direction, lane=15,
        object_id=ids.allocate(2 * INTERNAL_OBJECT_BYTES), timeout=300_000,
        flags=flag,
    )
    return case.plan_line()


def stage_order() -> tuple[str, ...]:
    stages = [
        "preflight", "counter_local_source", "counter_semantics",
        "baseline_smoke", "tuning", "half_duplex", "streaming_64m",
        "streaming_128m", "lane_recovery", "degrade", "direction_switch",
        "ps_reset_fixed", "ps_reset_rotating",
    ]
    for role in ("fixed", "rotating"):
        for index in range(1, 6):
            stages.extend((f"dma_reset_{role}_{index}",
                           f"dma_recovery_{role}_{index}"))
    for role in ("fixed", "rotating"):
        for index in range(1, 4):
            stages.extend((f"pl_reset_{role}_{index}",
                           f"pl_recovery_{role}_{index}"))
    stages.extend((
        "duplicate_fault", "duplicate_recovery", "stale_fault",
        "stale_recovery", "echo_crosstalk_8x8", "two_plus_two",
        "mixed_30min",
    ))
    return tuple(stages)


STAGES = stage_order()
EXPECTED_FAULT_STAGES = {
    stage for stage in STAGES
    if stage.startswith(("dma_reset_", "pl_reset_"))
} | {"duplicate_fault", "stale_fault"}


def tcl_stage(stage: str) -> str:
    if stage == "preflight":
        return "P10_4-PREFLIGHT"
    if stage in {"counter_local_source", "counter_semantics"}:
        return "P10_4-COUNTER_SEMANTICS"
    if stage == "baseline_smoke":
        return "P10_4-BASELINE_SMOKE"
    if stage == "tuning":
        return "P10_4-TUNING"
    if stage == "half_duplex":
        return "P10_4-HALF_DUPLEX"
    if stage == "streaming_64m":
        return "P10_4-STREAMING_64M"
    if stage == "streaming_128m":
        return "P10_4-STREAMING_128M"
    if stage in EXPECTED_FAULT_STAGES:
        return "P10_4-STREAMING_FAULT"
    if stage == "lane_recovery":
        return "P10_4-RESET_RECOVERY"
    if stage == "degrade":
        return "P10_4-DEGRADE"
    if stage == "direction_switch":
        return "P10_4-DIRECTION_SWITCH"
    if stage.startswith(("ps_reset_", "dma_recovery_", "pl_recovery_")) or \
            stage in {"duplicate_recovery", "stale_recovery"}:
        return "P10_4-RESET_RECOVERY"
    if stage == "echo_crosstalk_8x8":
        return "P10_4-ECHO_CROSSTALK"
    if stage == "two_plus_two":
        return "P10_4-TWO_PLUS_TWO"
    if stage == "mixed_30min":
        return "P10_4-MIXED_FORMAL"
    raise ValueError(stage)


def stage_timeout(stage: str) -> int:
    if stage == "streaming_64m":
        return 3_600
    if stage == "streaming_128m":
        return 2_400
    if stage == "lane_recovery":
        return 1_800
    if stage in {"direction_switch", "tuning", "half_duplex",
                 "echo_crosstalk_8x8"}:
        return 1_200
    if stage.startswith("ps_reset_"):
        return 2_400
    if stage == "mixed_30min":
        return 2_100
    return 900


def build_plans(selected: dict[str, Any] | None = None) -> dict[str, str]:
    selected = dict(selected or baseline_config())
    ids = ObjectIds()
    plans: dict[str, list[str]] = {stage: [] for stage in STAGES}
    plans["preflight"] = [
        base.Case("p10_4_identity", 1).plan_line(),
        base.Case("p10_4_receive_only_5000ms", 11, idle=5000,
                  timeout=15_000).plan_line(),
        base.Case("p10_4_ring32", 4, ring=32).plan_line(),
        base.Case("p10_4_dma_reset_idle", 5, ring=32).plan_line(),
        base.Case("p10_4_pl_soft_reset", 8).plan_line(),
        base.Case("p10_4_identity_after_reset", 1).plan_line(),
    ]
    plans["counter_local_source"] = [
        base.Case("counter_local_source_endpoint_shutdown", 10).plan_line(),
        "P104_LOCAL_SOURCE_TEST counter_local_source_all 15",
    ]
    plans["counter_semantics"] = [
        config_line(baseline_config()),
        "P10FF_WINDOW counter_direct_f2r 30 0 15",
        "P10FF_WINDOW counter_direct_r2f 30 1 15",
    ]
    smoke: list[str] = []
    for lane_index in range(4):
        lane = 1 << lane_index
        for direction, side in ((0, "F"), (1, "R")):
            smoke.append(base.Case(
                f"smoke_{side}{lane_index}_raw64", 2, lane=lane,
                direction=direction, rate=2, rawtarget=64, spacing=1024,
                timeout=30_000,
            ).plan_line())
            smoke.append(base.object_case(
                f"smoke_lane{lane_index}_{'f2r' if direction == 0 else 'r2f'}_100f",
                size=247 * 100, direction=direction, lane=lane,
                object_id=ids.allocate(), timeout=60_000,
            ).plan_line())
    smoke.extend((
        total_line("smoke_1m_f2r", 1 << 20, 0, 15, 0, ids),
        total_line("smoke_1m_r2f", 1 << 20, 1, 15, 0, ids),
    ))
    plans["baseline_smoke"] = smoke

    tuning: list[str] = []
    for candidate in candidate_configs():
        name = candidate["name"]
        tuning.extend((
            config_line(candidate),
            f"P10FF_WINDOW tune_{name}_f2r 30 0 15",
            f"P10FF_WINDOW tune_{name}_r2f 30 1 15",
        ))
    plans["tuning"] = tuning
    header = config_line(selected)
    plans["half_duplex"] = [
        header, "P10FF_WINDOW sustained_300s_f2r 300 0 15",
        "P10FF_WINDOW sustained_300s_r2f 300 1 15",
    ]
    plans["streaming_64m"] = [header]
    for direction, side in ((0, "f2r"), (1, "r2f")):
        for index in range(1, 11):
            plans["streaming_64m"].append(total_line(
                f"stream64_{side}_{index:02d}", 64 << 20, direction, 15, 0, ids
            ))
    plans["streaming_128m"] = [header]
    for direction, side in ((0, "f2r"), (1, "r2f")):
        for index in range(1, 4):
            plans["streaming_128m"].append(total_line(
                f"stream128_{side}_{index:02d}", 128 << 20,
                direction, 15, 0, ids
            ))
    plans["lane_recovery"] = [header]
    for lane in range(4):
        direction = lane & 1
        plans["lane_recovery"].extend((
            total_line(f"lane{lane}_unavailable", 64 << 20, direction,
                       15, 1 << lane, ids),
            total_line(f"lane{lane}_clean64", 64 << 20, direction,
                       15, 0, ids),
        ))
    plans["degrade"] = [header]
    for index, mask in enumerate((14, 15, 13, 15, 11, 15, 7, 15,
                                  3, 15, 5, 15, 10, 15, 1, 15)):
        plans["degrade"].append(
            f"P10FF_WINDOW degrade_{index:02d}_mask{mask:X} 10 {index & 1} {mask}"
        )
    plans["direction_switch"] = [header]
    for cycle in range(10):
        plans["direction_switch"].extend((
            f"P10FF_WINDOW switch_{cycle:02d}_f2r 30 0 15",
            f"P10FF_WINDOW switch_{cycle:02d}_r2f 30 1 15",
        ))

    for role in ("fixed", "rotating"):
        direction = 0 if role == "fixed" else 1
        plan = [header]
        for index in range(1, 6):
            plan.append(
                f"P101_PSRESET ps_reset_{role}_{index} {role} {direction} 15 "
                f"{INTERNAL_OBJECT_BYTES} {ids.allocate()}"
            )
            plan.append(total_line(
                f"ps_reset_{role}_{index}_clean64", 64 << 20,
                direction, 15, 0, ids
            ))
        plans[f"ps_reset_{role}"] = plan

    for role in ("fixed", "rotating"):
        direction = 0 if role == "fixed" else 1
        for index in range(1, 6):
            fault = f"dma_reset_{role}_{index}"
            recovery = f"dma_recovery_{role}_{index}"
            plans[fault] = [header, stream_fault_case(
                fault, direction, base.p101.FLAG_DMA_RESET_SENDER, ids
            )]
            plans[recovery] = [header, total_line(
                f"{fault}_clean64", 64 << 20, direction, 15, 0, ids
            )]
    for role in ("fixed", "rotating"):
        direction = 0 if role == "fixed" else 1
        for index in range(1, 4):
            fault = f"pl_reset_{role}_{index}"
            recovery = f"pl_recovery_{role}_{index}"
            plans[fault] = [header, stream_fault_case(
                fault, direction, base.p101.FLAG_PL_RESET_LOCAL_TX, ids
            )]
            plans[recovery] = [header, total_line(
                f"{fault}_clean64", 64 << 20, direction, 15, 0, ids
            )]
    plans["duplicate_fault"] = [header, stream_fault_case(
        "duplicate_segment", 0, base.p101.FLAG_DUPLICATE_SEGMENT, ids
    )]
    plans["duplicate_recovery"] = [header, total_line(
        "duplicate_segment_clean64", 64 << 20, 0, 15, 0, ids
    )]
    plans["stale_fault"] = [header, stream_fault_case(
        "stale_segment", 1, base.p101.FLAG_STALE_SEGMENT, ids
    )]
    plans["stale_recovery"] = [header, total_line(
        "stale_segment_clean64", 64 << 20, 1, 15, 0, ids
    )]

    matrix = [header]
    for lane in range(4):
        mask = 1 << lane
        for direction, side in ((0, "F"), (1, "R")):
            source = f"{side}{lane}"
            matrix.extend((
                base.Case(f"matrix_{source}_raw64", 2, lane=mask,
                          direction=direction, rate=2, rawtarget=64,
                          spacing=1024, timeout=30_000).plan_line(),
                base.Case(f"matrix_{source}_raw1024", 2, lane=mask,
                          direction=direction, rate=2, rawtarget=1024,
                          spacing=1024, timeout=30_000).plan_line(),
                f"P10FF_WINDOW matrix_{source}_frame30s 30 {direction} {mask}",
            ))
    plans["echo_crosstalk_8x8"] = matrix
    plans["two_plus_two"] = ["P104_TWO_PLUS_TWO_PROBE two_plus_two 300"]
    plans["mixed_30min"] = [header, "P104_MIXED_FORMAL mixed_30min 1800"]
    return {name: "\n".join(lines) + "\n" for name, lines in plans.items()}


def plan_sha256(selected: dict[str, Any]) -> dict[str, str]:
    return {
        stage: hashlib.sha256(text.encode("ascii")).hexdigest()
        for stage, text in build_plans(selected).items()
    }


def allowed_plan_sha256() -> dict[str, dict[str, str]]:
    configs = candidate_configs()
    names = [str(item["name"]) for item in configs]
    if len(names) != len(set(names)):
        raise ValueError("P10.4 tuning configuration names are not unique")
    return {str(item["name"]): plan_sha256(item) for item in configs}


def validate_plans() -> list[str]:
    errors: list[str] = []
    try:
        configs = candidate_configs()
        if len({str(item["name"]) for item in configs}) != len(configs):
            errors.append("tuning configuration names are not unique")
    except (KeyError, TypeError, ValueError) as exc:
        return [f"configuration validation failed: {exc}"]
    for config in configs:
        plans = build_plans(config)
        if tuple(plans) != STAGES:
            errors.append(f"{config['name']}: stage order mismatch")
        for stage, plan in plans.items():
            try:
                plan.encode("ascii")
            except UnicodeEncodeError:
                errors.append(f"{config['name']}:{stage}: non-ASCII plan")
            if not plan.endswith("\n"):
                errors.append(f"{config['name']}:{stage}: terminal newline missing")
            if stage in EXPECTED_FAULT_STAGES:
                cases = [line for line in plan.splitlines()
                         if line.startswith("CASE ")]
                if len(cases) != 1:
                    errors.append(
                        f"{config['name']}:{stage}: terminal fault must contain one CASE"
                    )
            for line in plan.splitlines():
                fields = line.split()
                if not fields or fields[0] in {
                    "P104_CONFIG", "P104_LOCAL_SOURCE_TEST",
                    "P104_MIXED_FORMAL", "P104_TWO_PLUS_TWO_PROBE",
                }:
                    continue
                if fields[0] == "P10FF_TOTAL" and \
                        int(fields[2], 0) > MAX_AGGREGATE_BYTES:
                    errors.append(
                        f"{config['name']}:{stage}: aggregate exceeds 128 MiB"
                    )
                if fields[0] in {"CASE", "P10FF_TOTAL", "P10FF_WINDOW",
                                 "P101_PSRESET"}:
                    mask_index = {"CASE": 5, "P10FF_TOTAL": 4,
                                  "P10FF_WINDOW": 4,
                                  "P101_PSRESET": 4}[fields[0]]
                    if int(fields[mask_index], 0) > 15:
                        errors.append(
                            f"{config['name']}:{stage}: lane mask exceeds 0xF"
                        )
    return errors


def validate_authorization(path: Path, run_id: str) -> tuple[
        dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = validate_plans()
    try:
        freeze = load_json(FREEZE)
        auth = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {}, [f"authorization/freeze read failed: {exc}"]
    match = RUN_RE.fullmatch(run_id)
    artifacts_by_key = {
        artifact_key(item): item for item in freeze.get("artifacts", [])
        if isinstance(item, dict)
    }
    if match is None:
        errors.append("invalid content-bound P10.4 run id")
    else:
        expected_parts = {
            "source": str(freeze.get("source_commit", ""))[:8],
            "fixed": str(artifacts_by_key.get(
                "fixed:functional_bitstream", {}).get("sha256", ""))[:8],
            "rotating": str(artifacts_by_key.get(
                "rotating:functional_bitstream", {}).get("sha256", ""))[:8],
        }
        for key, value in expected_parts.items():
            if match.group(key) != value:
                errors.append(f"run-id {key} digest mismatch")
    expected = {
        "schema_version": 1,
        "authorization_id": "P10_4-CURRENT-RUN-IMMUTABLE",
        "scope": SCOPE,
        "run_id": run_id,
        "authorized": True,
        "consumed": False,
        "current_run_hardware_authorization": True,
        "no_hardware": False,
        "goal_sha256": GOAL_SHA256,
        "source_commit": freeze.get("source_commit"),
        "fixed_jtag_serial": EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": EXPECTED_ROTATING_SERIAL,
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "ethernet_allowed": False,
        "external_instrumentation_allowed": False,
        "movement_rotation_realignment_rewiring_or_module_replacement_allowed": False,
        "shutdown_policy": SHUTDOWN_POLICY,
    }
    errors.extend(
        f"authorization {key} mismatch" for key, value in expected.items()
        if auth.get(key) != value
    )
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("artifact freeze is not acceptance eligible")
    if auth.get("artifacts") != freeze.get("artifacts"):
        errors.append("authorization artifacts differ from freeze")
    if auth.get("offline_inputs") != freeze.get("offline_inputs"):
        errors.append("authorization offline inputs differ from freeze")
    if auth.get("allowed_stages") != list(STAGES):
        errors.append("authorization stage order mismatch")
    configs = candidate_configs()
    if auth.get("allowed_selected_configs") != configs:
        errors.append("authorization selected-configuration set mismatch")
    exact_plan_hashes = allowed_plan_sha256()
    if auth.get("allowed_plan_sha256") != exact_plan_hashes:
        errors.append("authorization selected-plan hash set mismatch")
    if auth.get("baseline_plan_sha256") != exact_plan_hashes.get(
        baseline_config()["name"]
    ):
        errors.append("authorization baseline plan hash mismatch")
    if auth.get("register_map") != {
        "version": f"0x{REGISTER_MAP_VERSION:08X}",
        "hash_low": f"0x{REGISTER_MAP_HASH_LOW:08X}",
    }:
        errors.append("authorization register-map identity mismatch")
    for name, item in freeze.get("offline_inputs", {}).items():
        try:
            candidate = (ROOT / item["path"]).resolve()
            if not base.inside(candidate, ROOT) or not candidate.is_file() or \
                    candidate.stat().st_size != item["bytes"] or \
                    sha256(candidate) != item["sha256"]:
                errors.append(f"offline input changed: {name}")
        except (KeyError, OSError, TypeError, ValueError):
            errors.append(f"malformed offline input: {name}")
    if set(freeze.get("offline_inputs", {})) != {
        "performance_model", "performance_config", "register_map", "goal",
        "crc_bad_diagnosis", "crc_bad_remediation",
        "connector_ack_quarantine",
    }:
        errors.append("offline input set mismatch")
    if not file_matches_head(AUTH) or not file_matches_head(FREEZE):
        errors.append("authorization and freeze must be exact committed HEAD inputs")
    artifacts: dict[str, Path] = {}
    for key, item in artifacts_by_key.items():
        try:
            candidate = (ROOT / item["path"]).resolve()
            if not base.inside(candidate, ROOT) or not candidate.is_file() or \
                    candidate.stat().st_size != item["bytes"] or \
                    sha256(candidate) != item["sha256"]:
                errors.append(f"artifact changed: {key}")
            else:
                artifacts[key] = candidate
        except (KeyError, OSError, ValueError):
            errors.append(f"malformed artifact: {key}")
    required = {
        f"{role}:{kind}" for role in ("fixed", "rotating")
        for kind in ("shutdown_bitstream", "functional_bitstream", "xsa", "bsp", "elf")
    }
    if set(artifacts_by_key) != required:
        errors.append("artifact set mismatch")
    return auth, artifacts, errors


def initialize_run(run_root: Path, auth: Path, artifacts: dict[str, Path]) -> dict[str, Path]:
    run_root.mkdir(parents=True, exist_ok=False)
    for name in (
        "authorization", "artifacts", "target_identity", "safe_boot",
        "baseline_smoke", "counter_semantics", "performance_tuning",
        "half_duplex_performance", "streaming_64m", "streaming_128m",
        "degraded_modes", "direction_switch", "reset_recovery",
        "echo_crosstalk_8x8", "two_plus_two", "mixed_30min", "shutdown",
        "stages", "forensics", "raw_logs", "final",
    ):
        (run_root / name).mkdir(parents=True, exist_ok=False)
    copies = (
        (auth, run_root / "authorization/immutable_authorization.json"),
        (GOAL, run_root / "authorization/goal.md"),
        (FREEZE, run_root / "artifacts/artifact_freeze.json"),
        (CONFIG, run_root / "artifacts/performance_config.yaml"),
        (MODEL, run_root / "artifacts/offline_model.json"),
        (ROOT / "config/hardware/p10_3_actual_wiring.yaml",
         run_root / "artifacts/as_wired.yaml"),
        (ROOT / "config/hardware/tfdu_module_inventory.yaml",
         run_root / "artifacts/module_inventory.yaml"),
    )
    for source, destination in copies:
        shutil.copy2(source, destination)
    write_text(
        run_root / "authorization/NO_MOVEMENT_NETWORK_INSTRUMENT_ATTESTATION.txt",
        "AUTOMATION_ONLY=true\nNETWORK_USED=false\nHARDWARE_MOVED=false\n"
        "WIRING_CHANGED=false\nMODULE_REPLACED=false\n"
        "EXTERNAL_INSTRUMENTATION_USED=false\nMAX_LANE_MASK=0xF\nP11=false\n",
    )
    ps7: dict[str, Path] = {}
    derived = []
    for role in ("fixed", "rotating"):
        destination = run_root / "artifacts" / role / "ps7_init.tcl"
        destination.parent.mkdir(parents=True, exist_ok=True)
        extract_ps7_init(artifacts[f"{role}:xsa"], destination)
        ps7[role] = destination
        derived.append({"role": role, "file": metadata(destination)})
    write_json(run_root / "artifacts/derived_artifact_manifest.json", {
        "schema_version": 1, "status": "PASS", "files": derived,
    })
    return ps7


def invoke_stage(stage: str, plan_text: str, run_root: Path, auth: Path,
                 artifacts: dict[str, Path], ps7: dict[str, Path],
                 env: dict[str, str]) -> tuple[dict[str, Any], Path]:
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
        tcl_stage(stage), str(auth), run_root.name,
        f"0x{EXPECTED_BUILD['fixed']:08X}",
        f"0x{EXPECTED_BUILD['rotating']:08X}",
        f"0x{REGISTER_MAP_VERSION:08X}", f"0x{REGISTER_MAP_HASH_LOW:08X}",
    ]
    process = run_bounded(
        command, stage_dir / "xsdb.stdout.log", stage_dir / "xsdb.stderr.log",
        stage_timeout(stage), env,
    )
    return process, stage_dir


def capture_and_archive(label: str, run_root: Path, auth: Path,
                        env: dict[str, str], *, force_abort: bool = False) -> dict[str, Any]:
    out = run_root / "forensics" / label
    out.mkdir(parents=True, exist_ok=True)
    result = out / "capture.result.txt"
    command = [
        str(XSDB), str(FORENSIC_TCL),
        "abort_capture" if force_abort else "capture", "tcp:localhost:3121",
        EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL, str(out), str(auth),
        run_root.name, f"0x{EXPECTED_BUILD['fixed']:08X}",
        f"0x{EXPECTED_BUILD['rotating']:08X}", str(result), "NONE", "NONE",
        f"0x{REGISTER_MAP_VERSION:08X}", f"0x{REGISTER_MAP_HASH_LOW:08X}",
    ]
    process = run_bounded(
        command, out / "capture.stdout.log", out / "capture.stderr.log", 180, env
    )
    errors: list[str] = []
    archives: list[dict[str, Any]] = []
    markers = parse_markers(result)
    if process.get("returncode") != 0 or process.get("timed_out") or \
            markers.get("P10_FF_FORENSIC_RESULT") != "PASS":
        errors.append("forensic capture failed")
    if not errors:
        try:
            for role in ("fixed", "rotating"):
                archives.append(forensic.write_archive(
                    forensic.parse_psv(out / f"{role}.p10ff.psv"), out
                ))
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"forensic archive failed: {exc}")
    frozen = [item for item in archives if item.get("status") == "FROZEN"]
    commit_process = None
    if frozen and not errors:
        digests = {item["role"]: item["binary_sha256"] for item in frozen}
        commit_result = out / "commit.result.txt"
        commit_command = [
            str(XSDB), str(FORENSIC_TCL), "commit", "tcp:localhost:3121",
            EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL, str(out), str(auth),
            run_root.name, f"0x{EXPECTED_BUILD['fixed']:08X}",
            f"0x{EXPECTED_BUILD['rotating']:08X}", str(commit_result),
            digests.get("fixed", "NONE"), digests.get("rotating", "NONE"),
            f"0x{REGISTER_MAP_VERSION:08X}", f"0x{REGISTER_MAP_HASH_LOW:08X}",
        ]
        commit_process = run_bounded(
            commit_command, out / "commit.stdout.log", out / "commit.stderr.log",
            180, env,
        )
        if commit_process.get("returncode") != 0 or commit_process.get("timed_out") or \
                parse_markers(commit_result).get("P10_FF_FORENSIC_RESULT") != "PASS":
            errors.append("forensic archive commit failed")
    if force_abort and markers.get("P10_FF_ABORT_BEFORE_CAPTURE") != "PASS":
        errors.append("forced abort marker missing")
    payload = {
        "schema_version": 1, "status": "PASS" if not errors else "FAIL",
        "label": label, "capture_process": process,
        "commit_process": commit_process, "archives": archives,
        "frozen_roles": [item["role"] for item in frozen],
        "force_terminal_abort": force_abort, "explicit_clear_executed": False,
        "errors": errors, "generated_at_utc": utc_now(),
    }
    write_json(out / "summary.json", payload)
    return payload


def guarded_shutdown(run_root: Path, auth: Path, artifacts: dict[str, Path],
                     label: str, env: dict[str, str]) -> dict[str, Any]:
    previous = forensic.EXPECTED_BUILD
    forensic.EXPECTED_BUILD = EXPECTED_BUILD
    try:
        return forensic.guarded_shutdown(run_root, auth, artifacts, label, env)
    finally:
        forensic.EXPECTED_BUILD = previous


def read_rows(stage_dir: Path) -> tuple[list[dict[str, Any]], list[str]]:
    return legacy.read_rows(stage_dir)


def raw_errors(detail: dict[str, Any]) -> list[str]:
    if detail.get("command") != 2:
        return []
    errors: list[str] = []
    mask = int(detail["lane_mask"])
    if mask <= 0 or mask & (mask - 1):
        return [f"{detail['label']}: raw lane is not one-hot"]
    lane = int(math.log2(mask))
    direction = int(detail["direction"])
    sender_role = "fixed" if direction == 0 else "rotating"
    receiver_role = "rotating" if direction == 0 else "fixed"
    sender = detail[f"{sender_role}_p10_2"]
    receiver = detail[f"{receiver_role}_p10_2"]
    sender_module = lane if sender_role == "fixed" else 4 + lane
    receiver_module = 4 + lane if receiver_role == "rotating" else lane
    target = int(detail["plan_fields"]["rawtarget"])
    if sender["modules"][sender_module]["physical_tx"] != target:
        errors.append(f"{detail['label']}: physical TX count mismatch")
    observed = receiver["modules"][receiver_module]["raw_rx"]
    if not target <= observed <= target + 8:
        errors.append(f"{detail['label']}: remote raw count mismatch")
    detail["raw_source"] = ("F" if direction == 0 else "R") + str(lane)
    return errors


def connector_ack_quarantine_allowed_receiver_lanes(
        stage: str, detail: dict[str, Any]) -> frozenset[int]:
    """Return the exact receiver lane intentionally blanked by a physical ACK.

    The P10.4 remediation pairs lanes 0/1 on J10 and lanes 2/3 on J11.  During
    a one-lane command-13 frame window, the receiver transmits the ACK on the
    selected lane.  That final physical ACK is also an intentional quarantine
    source for the adjacent lane on the same connector.  Raw command-2 vectors,
    recovery vectors, multi-lane traffic, and every other campaign stage retain
    the historical zero-other-lane-blanking rule.
    """
    if stage != "echo_crosstalk_8x8" or detail.get("command") != 13 or \
            detail.get("recovery_case") or \
            int(detail.get("requested_bytes", 0)) <= 0:
        return frozenset()
    mask = int(detail.get("lane_mask", 0)) & 0xF
    if mask <= 0 or mask & (mask - 1):
        return frozenset()
    source_lane = mask.bit_length() - 1
    return frozenset({source_lane ^ 1})


def connector_ack_quarantine_frame_audit(
        stage: str, detail: dict[str, Any]
        ) -> tuple[list[str], list[dict[str, Any]]]:
    """Audit rather than hide the expected connector-pair ACK quarantine."""
    allowed_receiver = connector_ack_quarantine_allowed_receiver_lanes(
        stage, detail
    )
    if not allowed_receiver:
        return [], []
    errors: list[str] = []
    observations: list[dict[str, Any]] = []
    source_lane = (int(detail["lane_mask"]) & 0xF).bit_length() - 1
    paired_lane = source_lane ^ 1
    sender_role, receiver_role = base.path_roles(detail)
    for role in (sender_role, receiver_role):
        allowed = {source_lane}
        if role == receiver_role:
            allowed.add(paired_lane)
        snapshot = detail[f"{role}_p10_2"]
        for lane_index, lane in enumerate(snapshot.get("lanes", [])):
            blanked = int(lane.get("blanked_raw", 0))
            if blanked and lane_index not in allowed:
                errors.append(
                    f"{detail['label']}:{role}:unexpected lane{lane_index} blanked"
                )
        paired_blanked = int(
            detail[f"{receiver_role}_p10_2"]["lanes"][paired_lane]["blanked_raw"]
        )
        if role == receiver_role and paired_blanked:
            observations.append({
                "label": detail["label"],
                "command": 13,
                "direction": int(detail["direction"]),
                "source_lane": source_lane,
                "paired_lane": paired_lane,
                "connector": "J10" if source_lane < 2 else "J11",
                "ack_transmitter_role": receiver_role,
                "blanked_raw": paired_blanked,
                "accepted_remote_on_paired_lane": int(
                    detail[f"{receiver_role}_p10_2"]["lanes"][paired_lane][
                        "accepted_remote"
                    ]
                ),
                "crc_bad_on_paired_lane": int(
                    detail[f"{receiver_role}_p10_2"]["lanes"][paired_lane][
                        "crc_bad"
                    ]
                ),
            })
    return errors, observations


def window_metrics(details: list[dict[str, Any]], label: str,
                   duration: int, direction: int, mask: int) -> dict[str, Any]:
    selected = [item for item in details if item.get("window") == label]
    selected = [item for item in selected if not item.get("recovery_case")]
    receiver = "rotating" if direction == 0 else "fixed"
    requested = sum(int(item.get("requested_bytes", 0)) for item in selected)
    committed = sum(
        int(item.get(receiver, {}).get("perf_application_committed", 0))
        for item in selected
    )
    sender = "fixed" if direction == 0 else "rotating"
    counter_names = (
        "perf_outstanding_unacked", "perf_tx_idle_due_to_ack",
        "perf_window_full_stall", "perf_receiver_credit_stall",
        "perf_direction_turnaround_idle",
    )
    counters = {
        name: sum(int(item.get(sender, {}).get(name, 0)) for item in selected)
        for name in counter_names
    }
    return {
        "label": label, "duration_seconds": duration, "direction": direction,
        "lane_mask": mask, "commands": len(selected),
        "requested_bytes": requested, "committed_bytes": committed,
        "commit_matches_requested": committed == requested,
        "commit_measurement": f"{receiver}.perf_application_committed",
        "application_goodput_bps": committed * 8 / duration,
        "direct_counters": counters,
    }


def evaluate_stage(stage: str, stage_dir: Path, process: dict[str, Any],
                   forensic_summary: dict[str, Any], plan: str) -> dict[str, Any]:
    markers = parse_markers(stage_dir / "xsdb.result.txt")
    errors: list[str] = []
    if process.get("returncode") != 0 or process.get("timed_out"):
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS" or \
            markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("stage or safe-boot PASS marker missing")
    rows, row_errors = read_rows(stage_dir)
    errors.extend(row_errors)
    previous = legacy.EXPECTED_BUILD
    legacy.EXPECTED_BUILD = EXPECTED_BUILD
    try:
        details, detail_errors = legacy.load_custom_details(stage_dir, rows)
    finally:
        legacy.EXPECTED_BUILD = previous
    errors.extend(detail_errors)
    non_shutdown = [item for item in details
                    if not str(item.get("label", "")).endswith("endpoint_shutdown")]
    semantics: dict[str, Any] = {}
    if stage in EXPECTED_FAULT_STAGES:
        if markers.get("P10_3F_FAULT_KILL_BEFORE_FORENSIC_READ") != "PASS" or \
                markers.get("P10_3F_FAULT_CAPTURE_LEFT_FROZEN") != "1":
            errors.append("terminal first-fault kill/freeze marker missing")
        errors.extend(legacy.post_fault_archive_errors(forensic_summary))
        if len(non_shutdown) != 1 or not non_shutdown[0].get("recovery_case"):
            errors.append("terminal recovery vector is not exact")
        semantics["terminal_fault_archived_before_shutdown"] = True
    else:
        if forensic_summary.get("status") != "PASS":
            errors.append("forensic read/archive failed")
        if forensic_summary.get("frozen_roles"):
            errors.append("unexpected first-fault recorder freeze")
        shutdown_rows = [item for item in details
                         if str(item.get("label", "")).endswith("endpoint_shutdown")]
        if len(shutdown_rows) != 1:
            errors.append("exactly one functional endpoint-shutdown row required")
        for detail in non_shutdown:
            if detail.get("command") == 13 and not detail.get("recovery_case"):
                errors.extend(base.data_path_errors(
                    detail, unavailable=int(detail.get("unavailable", 0)),
                    allowed_receiver_blanked_lanes=(
                        connector_ack_quarantine_allowed_receiver_lanes(
                            stage, detail
                        )
                    ),
                ))
            errors.extend(raw_errors(detail))
        _, gpio_errors = base.load_ps_gpio(stage_dir)
        errors.extend(gpio_errors)

    fixed_labels = {
        fields[1] for fields in (line.split() for line in plan.splitlines())
        if fields and fields[0] in {"CASE", "P10FF_TOTAL", "P101_PSRESET"}
    }
    # Every fixed plan row, including the terminal endpoint-shutdown row, is
    # still an observation.  ``non_shutdown`` is only the data-path subset;
    # using it here falsely reports a correctly captured shutdown as missing.
    observed_labels = {str(item.get("label")) for item in details}
    missing = fixed_labels - observed_labels
    if stage in EXPECTED_FAULT_STAGES:
        missing -= {line.split()[1] for line in plan.splitlines()
                    if line.startswith("P104_CONFIG ")}
    if missing:
        errors.append(f"immutable plan observations missing: {sorted(missing)}")

    if stage == "counter_local_source":
        local_file = stage_dir / "dumps/counter_local_source_all.p10_4_local_source.psv"
        required = {
            "P10_4_LOCAL_SOURCE_REJECTION": "PASS",
            "P10_4_LOCAL_SOURCE_APPLICATION_COMMIT_ZERO": "PASS",
            "P10_4_LOCAL_SOURCE_PHYSICAL_TX_ZERO": "PASS",
        }
        if not local_file.is_file() or any(markers.get(k) != v for k, v in required.items()):
            errors.append("local-source direct evidence missing")
        semantics["local_source_evidence"] = rel(local_file) if local_file.is_file() else None
    elif stage == "counter_semantics":
        windows = [
            window_metrics(non_shutdown, "counter_direct_f2r", 30, 0, 15),
            window_metrics(non_shutdown, "counter_direct_r2f", 30, 1, 15),
        ]
        if any(not item["commands"] for item in windows):
            errors.append("direct-counter measurement window missing")
        semantics["windows"] = windows
        semantics["split_counter_semantics"] = "DIRECT_PREDICATES_NOT_ACK_OCCUPANCY_INFERENCE"
    elif stage == "baseline_smoke":
        raw = [item for item in non_shutdown if item.get("command") == 2]
        framed = [item for item in non_shutdown if item.get("command") in (3, 13)]
        if len(raw) != 8 or len(framed) != 10:
            errors.append("baseline smoke vector count mismatch")
        semantics.update({"raw_directions": len(raw), "framed_vectors": len(framed)})
    elif stage == "tuning":
        candidates = []
        for candidate in candidate_configs():
            name = candidate["name"]
            directions = [
                window_metrics(non_shutdown, f"tune_{name}_f2r", 30, 0, 15),
                window_metrics(non_shutdown, f"tune_{name}_r2f", 30, 1, 15),
            ]
            minimum = min(item["application_goodput_bps"] for item in directions)
            stalls = sum(
                sum(item["direct_counters"][key] for key in (
                    "perf_tx_idle_due_to_ack", "perf_window_full_stall",
                    "perf_receiver_credit_stall", "perf_direction_turnaround_idle",
                )) for item in directions
            )
            candidates.append({
                "config": candidate, "directions": directions,
                "minimum_bidirectional_goodput_bps": minimum,
                "direct_stall_cycles": stalls,
            })
        if any(not direction["commands"] for item in candidates
               for direction in item["directions"]):
            errors.append("tuning candidate measurement missing")
        selected = max(candidates, key=lambda item: (
            item["minimum_bidirectional_goodput_bps"], -item["direct_stall_cycles"]
        )) if candidates else None
        semantics.update({"candidates": candidates,
                          "selected": selected["config"] if selected else None})
    elif stage == "half_duplex":
        windows = [
            window_metrics(non_shutdown, "sustained_300s_f2r", 300, 0, 15),
            window_metrics(non_shutdown, "sustained_300s_r2f", 300, 1, 15),
        ]
        for item in windows:
            if item["application_goodput_bps"] < 8_000_000:
                errors.append(f"{item['label']}: below mandatory 8 Mbit/s")
        try:
            model = load_json(MODEL)
            application_ceiling = float(
                model["ceilings"]["APPLICATION_GOODPUT_BPS"]["ceiling_bps"]
            )
            airtime_ceiling = float(
                model["ceilings"]["FRAME_GOODPUT_BPS"]["ceiling_bps"]
            )
            if model.get("status") != "PASS" or application_ceiling <= 0 or \
                    airtime_ceiling <= 0:
                raise ValueError("invalid model status or ceiling")
            for item in windows:
                measured = float(item["application_goodput_bps"])
                item.update({
                    "modeled_application_ceiling_bps": application_ceiling,
                    "airtime_ceiling_bps": airtime_ceiling,
                    "measured_model_ratio": measured / application_ceiling,
                    "measured_airtime_ceiling_ratio": measured / airtime_ceiling,
                    "model_source_commit": model.get("source_commit"),
                })
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"measured/model reconciliation failed: {exc}")
        semantics["windows"] = windows
        semantics["model_reconciliation"] = "DIRECT_COMMITTED_BYTES_VS_FROZEN_MODEL"
    elif stage == "streaming_64m":
        labels = {f"stream64_{side}_{index:02d}"
                  for side in ("f2r", "r2f") for index in range(1, 11)}
        observed = {item.get("window") for item in non_shutdown
                    if item.get("requested_bytes") == 64 << 20}
        if observed != labels:
            errors.append("exact 10x64MiB per direction set mismatch")
        semantics["completed"] = sorted(observed)
    elif stage == "streaming_128m":
        labels = {f"stream128_{side}_{index:02d}"
                  for side in ("f2r", "r2f") for index in range(1, 4)}
        observed = {item.get("window") for item in non_shutdown
                    if item.get("requested_bytes") == 128 << 20}
        if observed != labels:
            errors.append("exact 3x128MiB per direction set mismatch")
        semantics["completed"] = sorted(observed)
    elif stage == "lane_recovery":
        if len([item for item in non_shutdown if item.get("requested_bytes") == 64 << 20]) != 8:
            errors.append("four unavailable/clean 64MiB pairs missing")
    elif stage == "degrade":
        windows = []
        for index, mask in enumerate((14, 15, 13, 15, 11, 15, 7, 15,
                                      3, 15, 5, 15, 10, 15, 1, 15)):
            windows.append(window_metrics(
                non_shutdown, f"degrade_{index:02d}_mask{mask:X}", 10,
                index & 1, mask
            ))
        full = [item["application_goodput_bps"] for item in windows
                if item["lane_mask"] == 15]
        if len(windows) != 16 or any(not item["commands"] for item in windows):
            errors.append("degradation sequence incomplete")
        if full and full[-1] < 0.9 * full[0]:
            errors.append("post-degrade full-mask goodput below 90 percent")
        semantics["windows"] = windows
    elif stage == "direction_switch":
        windows = []
        for cycle in range(10):
            windows.extend((
                window_metrics(non_shutdown, f"switch_{cycle:02d}_f2r", 30, 0, 15),
                window_metrics(non_shutdown, f"switch_{cycle:02d}_r2f", 30, 1, 15),
            ))
        if any(not item["commands"] for item in windows):
            errors.append("direction-switch window missing")
        semantics["windows"] = windows
    elif stage.startswith("ps_reset_"):
        role = stage.rsplit("_", 1)[1]
        resets = [item for item in non_shutdown if item.get("service_reset_case")]
        clean = [item for item in non_shutdown if item.get("requested_bytes") == 64 << 20]
        if len(resets) != 5 or len(clean) != 5:
            errors.append(f"{role}: exact five PS reset/recovery pairs missing")
        for index in range(1, 6):
            errors.extend(legacy.controlled_service_reset_shutdown_errors(
                stage_dir / f"dumps/ps_reset_{role}_{index}.service_reset_shutdown.psv"
            ))
        errors.extend(legacy.no_fault_archive_errors(forensic_summary))
    elif stage.endswith("_recovery") or "_recovery_" in stage:
        if len([item for item in non_shutdown if item.get("requested_bytes") == 64 << 20]) != 1:
            errors.append("fresh 64MiB recovery object missing")
    elif stage == "echo_crosstalk_8x8":
        raw = [item for item in non_shutdown if item.get("command") == 2]
        framed = [item for item in non_shutdown if item.get("command") == 13]
        cells: list[dict[str, Any]] = []
        expected_paired_ack_blanking: list[dict[str, Any]] = []
        same_module_raw_echo = 0
        maximum_non_target_accepted = 0
        maximum_cross_lane_accepted = 0
        for detail in raw:
            if not str(detail.get("label", "")).endswith("raw1024"):
                continue
            source = str(detail.get("raw_source", ""))
            if source not in MODULE_BINDING:
                errors.append(f"{detail.get('label')}: invalid matrix source")
                continue
            observations = [
                item["raw_rx"] for item in detail["fixed_p10_2"]["modules"][:4]
            ] + [
                item["raw_rx"] for item in detail["rotating_p10_2"]["modules"][4:8]
            ]
            source_index = list(MODULE_BINDING).index(source)
            target_index = source_index + 4 if source_index < 4 else source_index - 4
            same_module_raw_echo += int(observations[source_index])
            for index, module in enumerate(MODULE_BINDING):
                classification = (
                    "TARGET_REMOTE" if index == target_index else
                    "SAME_MODULE_ECHO" if index == source_index else
                    "NON_TARGET_RAW"
                )
                cells.append({
                    "tx_source": source, "rx_observation": module,
                    "classification": classification,
                    "raw_edges": int(observations[index]),
                })
            source_lane = int(source[1:])
            for role in ("fixed_p10_2", "rotating_p10_2"):
                snapshot = detail[role]
                maximum_non_target_accepted = max(
                    maximum_non_target_accepted,
                    int(snapshot.get("non_target_accepted", 0)),
                )
                maximum_cross_lane_accepted = max(
                    maximum_cross_lane_accepted,
                    int(snapshot.get("cross_lane_accepted", 0)),
                )
                if any(
                    int(lane.get("accepted_remote", 0)) or
                    int(lane.get("data_good", 0)) or
                    int(lane.get("ack_good", 0))
                    for lane in snapshot.get("lanes", [])
                ):
                    errors.append(
                        f"{detail['label']}:{role}: raw pulse admitted as frame/control"
                    )
                for lane_index, lane in enumerate(snapshot.get("lanes", [])):
                    if lane_index != source_lane and int(lane.get("blanked_raw", 0)):
                        errors.append(
                            f"{detail['label']}:{role}: non-source lane{lane_index} blanked"
                        )
        for detail in framed:
            audit_errors, observations = connector_ack_quarantine_frame_audit(
                stage, detail
            )
            errors.extend(audit_errors)
            expected_paired_ack_blanking.extend(observations)
        windows = [window_metrics(
            non_shutdown, f"matrix_{side}{lane}_frame30s", 30,
            0 if side == "F" else 1, 1 << lane
        ) for lane in range(4) for side in ("F", "R")]
        if len(raw) != 16 or len(cells) != 64 or \
                any(not item["commands"] for item in windows):
            errors.append("8x8 raw/frame matrix incomplete")
        if maximum_non_target_accepted or maximum_cross_lane_accepted:
            errors.append("8x8 matrix admitted a non-target or cross-lane frame")
        semantics.update({
            "raw_vectors": len(raw), "frame_windows": windows,
            "cells": cells, "cell_count": len(cells),
            "same_module_raw_echo_count": same_module_raw_echo,
            "same_module_accepted_data_or_control": maximum_non_target_accepted,
            "cross_lane_accepted_data_or_control": maximum_cross_lane_accepted,
            "expected_paired_ack_blanking": expected_paired_ack_blanking,
            "expected_paired_ack_blanking_observation_count": len(
                expected_paired_ack_blanking
            ),
            "expected_paired_ack_blanking_total": sum(
                item["blanked_raw"] for item in expected_paired_ack_blanking
            ),
            "paired_ack_blanking_policy": (
                "ONLY_RECEIVER_ACK_TRANSMITTER_ADJACENT_LANE_ON_SAME_CONNECTOR"
            ),
        })
    elif stage == "two_plus_two":
        if markers.get("P10_4_TWO_PLUS_TWO_RESULT") != "FAIL_WITH_NONBLOCKING_EVIDENCE" or \
                markers.get("P10_4_TWO_PLUS_TWO_TX_EXECUTED") != "false":
            errors.append("truthful 2+2 current-artifact capability marker missing")
        else:
            errors.append(
                "2+2 simultaneous opposite-direction transport is unsupported by "
                "the immutable single-bundle-direction artifact"
            )
        semantics.update({
            "result": "FAIL_WITH_EVIDENCE",
            "reason": markers.get("P10_4_TWO_PLUS_TWO_CAPABILITY"),
            "f_to_r_bps": 0, "r_to_f_bps": 0,
            "final_4plus4_full_duplex_pass": False,
        })
    elif stage == "mixed_30min":
        elapsed = int(markers.get("P10_4_MIXED_ELAPSED_MS", "0"))
        if markers.get("P10_4_MIXED_RESULT") != "PASS" or \
                elapsed not in range(1_800_000, 1_800_501):
            errors.append("mixed formal exact duration/result mismatch")
        half = [
            window_metrics(non_shutdown, "mixed_30min_half_f2r", 420, 0, 15),
            window_metrics(non_shutdown, "mixed_30min_half_r2f", 420, 1, 15),
        ]
        if any(item["application_goodput_bps"] < 8_000_000 for item in half):
            errors.append("mixed formal half-duplex window below 8 Mbit/s")
        semantics.update({"elapsed_ms": elapsed, "mandatory_half_duplex": half,
                          "two_plus_two": markers.get("P10_4_MIXED_TWO_PLUS_TWO")})

    payload = {
        "schema_version": 1, "test_id": f"P10_4-{stage.upper()}",
        "stage": stage, "status": "PASS" if not errors else "FAIL",
        "nonblocking": stage in NONBLOCKING_STAGES, "process": process,
        "markers": markers, "observation_count": len(rows), "details": details,
        "semantics": semantics, "forensic": forensic_summary,
        "errors": errors, "generated_at_utc": utc_now(),
    }
    write_json(stage_dir / "stage_summary.json", payload)
    return payload


def zero_counter_summary(stage_results: list[dict[str, Any]]) -> dict[str, int]:
    aliases = {
        "crc_bad": ("crc_bad_count",), "sha_mismatch": ("sha_mismatch_count",),
        "partial_commit": ("partial_commit_count",),
        "duplicate_commit": ("duplicate_commit_count",),
        "stale_commit": ("stale_commit_count",),
        "retry_exhausted": ("retry_exhausted_count",),
        "descriptor_leak": ("descriptor_leak_count",),
        "double_completion": ("double_completion_count",),
        "transport_timeout": ("tx_timeouts",),
    }
    output = {key: 0 for key in aliases}
    output.update({"deadlock": 0, "duty_violation": 0,
                   "continuous_high_violation": 0,
                   "same_module_accepted_data": 0,
                   "cross_lane_accepted_data": 0})
    for result in stage_results:
        for detail in result.get("details", []):
            for role in ("fixed", "rotating"):
                runtime = detail.get(role, {})
                for key, names in aliases.items():
                    output[key] = max(output[key], *(int(runtime.get(name, 0)) for name in names))
            for snap_name in ("fixed_p10_2", "rotating_p10_2"):
                snap = detail.get(snap_name, {})
                output["crc_bad"] = max(
                    output["crc_bad"],
                    *(int(lane.get("crc_bad", 0)) for lane in snap.get("lanes", [])),
                )
                output["same_module_accepted_data"] = max(
                    output["same_module_accepted_data"],
                    int(snap.get("non_target_accepted", 0)),
                )
                output["cross_lane_accepted_data"] = max(
                    output["cross_lane_accepted_data"],
                    int(snap.get("cross_lane_accepted", 0)),
                )
                for module in snap.get("modules", []):
                    output["duty_violation"] = max(
                        output["duty_violation"],
                        int(module.get("hard_fault", 0)),
                        int(int(module.get("duty_high_max", 0)) > base.HARD_DUTY_MAX_CYCLES),
                    )
                    output["continuous_high_violation"] = max(
                        output["continuous_high_violation"],
                        int(int(module.get("tx_high_max", 0)) > 64),
                    )
        output["deadlock"] = max(
            output["deadlock"], int(bool(result.get("process", {}).get("timed_out")))
        )
    return output


def group_payload(name: str, stages: list[str], by_stage: dict[str, dict[str, Any]],
                  common: dict[str, Any], *, nonblocking: bool = False) -> dict[str, Any]:
    selected = [by_stage[stage] for stage in stages if stage in by_stage]
    complete = len(selected) == len(stages)
    passed = complete and all(item.get("status") == "PASS" for item in selected)
    return {
        **common, "test_id": f"P10_4-{name.upper()}",
        "status": "PASS" if passed else ("FAIL_NONBLOCKING" if nonblocking else "FAIL"),
        "nonblocking": nonblocking, "expected_stages": stages,
        "stage_results": selected,
        "errors": [] if passed else ["stage set incomplete or failed"],
    }


def evidence_manifest(run_root: Path) -> dict[str, Any]:
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    files = []
    for path in sorted(run_root.rglob("*")):
        if path.is_file() and path != manifest_path:
            files.append(metadata(path))
    payload = {"schema_version": 1, "status": "PASS", "files": files,
               "file_count": len(files), "generated_at_utc": utc_now()}
    write_json(manifest_path, payload)
    return payload


def verify_evidence_manifest(run_root: Path, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    listed = manifest.get("files", [])
    if not isinstance(listed, list):
        return ["run evidence manifest file list is malformed"]
    by_path: dict[str, dict[str, Any]] = {}
    for item in listed:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            errors.append("run evidence manifest contains a malformed entry")
            continue
        if item["path"] in by_path:
            errors.append(f"duplicate manifest path: {item['path']}")
        by_path[item["path"]] = item
    actual_paths = {
        rel(path): path for path in run_root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if set(by_path) != set(actual_paths):
        errors.append("run evidence manifest path set differs from run root")
    for name, path in actual_paths.items():
        item = by_path.get(name, {})
        if item.get("bytes") != path.stat().st_size or \
                item.get("sha256") != sha256(path):
            errors.append(f"run evidence manifest hash/size mismatch: {name}")
    if manifest.get("file_count") != len(listed):
        errors.append("run evidence manifest count mismatch")
    return errors


def publish_evidence(summary: dict[str, Any], run_root: Path,
                     authorization: dict[str, Any]) -> dict[str, Any]:
    by_stage = {item["stage"]: item for item in summary["stages"]}
    common = {
        "schema_version": 1, "run_id": summary["run_id"],
        "scope": SCOPE, "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": summary["artifact_source_commit"],
        "artifacts": summary["artifacts"], "hardware_actions_executed": True,
        "current_run_hardware_authorization": False,
        "authorization_sha256": sha256(
            run_root / "authorization/immutable_authorization.json"
        ),
    }
    groups = {
        "safe_boot": (["preflight"], False),
        "counter_semantics": (["counter_local_source", "counter_semantics"], False),
        "baseline_smoke": (["baseline_smoke"], False),
        "performance_tuning": (["tuning"], False),
        "half_duplex_performance": (["half_duplex"], False),
        "streaming_64m": (["streaming_64m"], False),
        "streaming_128m": (["streaming_128m"], True),
        "degraded_modes": (["lane_recovery", "degrade"], False),
        "direction_switch": (["direction_switch"], False),
        "reset_recovery": ([stage for stage in STAGES if stage.startswith(
            ("ps_reset_", "dma_reset_", "dma_recovery_", "pl_reset_", "pl_recovery_"))
            or stage in {"duplicate_fault", "duplicate_recovery", "stale_fault",
                         "stale_recovery"}], False),
        "echo_crosstalk": (["echo_crosstalk_8x8"], False),
        "two_plus_two": (["two_plus_two"], True),
        "mixed_30min": (["mixed_30min"], False),
    }
    payloads = {}
    for name, (stages, nonblocking) in groups.items():
        payload = group_payload(name, stages, by_stage, common, nonblocking=nonblocking)
        payloads[name] = payload
        write_pair(GENERATED / f"p10_4_{name}", payload, f"P10.4 {name}")
        directory = {
            "safe_boot": "safe_boot", "counter_semantics": "counter_semantics",
            "baseline_smoke": "baseline_smoke",
            "performance_tuning": "performance_tuning",
            "half_duplex_performance": "half_duplex_performance",
            "streaming_64m": "streaming_64m", "streaming_128m": "streaming_128m",
            "degraded_modes": "degraded_modes", "direction_switch": "direction_switch",
            "reset_recovery": "reset_recovery",
            "echo_crosstalk": "echo_crosstalk_8x8",
            "two_plus_two": "two_plus_two", "mixed_30min": "mixed_30min",
        }[name]
        write_pair(run_root / directory / "summary", payload, f"P10.4 {name}")
    shutdown = {
        **common, "test_id": "P10_4-SAFE-001", "status": "PASS"
        if summary["SHUTDOWN_FIXED"] == summary["SHUTDOWN_ROTATING"] == "PASS"
        else "FAIL", "SHUTDOWN_FIXED": summary["SHUTDOWN_FIXED"],
        "SHUTDOWN_ROTATING": summary["SHUTDOWN_ROTATING"],
        "shutdowns": summary["shutdowns"], "errors": [],
    }
    write_pair(GENERATED / "p10_4_shutdown", shutdown, "P10.4 shutdown")
    write_pair(run_root / "shutdown/summary", shutdown, "P10.4 shutdown")
    write_json(run_root / "final/orchestrator_result.json", summary)
    write_pair(GENERATED / "p10_4_final_summary", summary, "P10.4 final summary")
    write_pair(run_root / "final/p10_4_final_summary", summary, "P10.4 final summary")
    consistency = {
        **common, "test_id": "P10_4-EVIDENCE-CONSISTENCY",
        "status": "PASS", "complete_generated_summary_set": True,
        "raw_run_root": rel(run_root), "errors": [],
    }
    write_pair(GENERATED / "p10_4_evidence_consistency", consistency,
               "P10.4 evidence consistency")
    write_pair(run_root / "final/p10_4_evidence_consistency", consistency,
               "P10.4 evidence consistency")
    manifest = evidence_manifest(run_root)
    manifest_errors = verify_evidence_manifest(run_root, manifest)
    consistency["manifest"] = rel(run_root / "final/run_evidence_sha256_manifest.json")
    consistency["manifest_file_count"] = manifest["file_count"]
    consistency["manifest_verified"] = not manifest_errors
    consistency["errors"] = manifest_errors
    consistency["status"] = "PASS" if not manifest_errors else "FAIL"
    write_pair(GENERATED / "p10_4_evidence_consistency", consistency,
               "P10.4 evidence consistency")
    return consistency


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
    if auth_path != AUTH.resolve():
        errors.append("canonical P10.4 authorization path required")
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "true":
        errors.append("NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required")
    run_root = HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("run-id evidence directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2), file=sys.stderr)
        return 3

    env = {
        **os.environ, "NO_HARDWARE": "0",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
        "RF_COMM_P10_HW_AUTH": "P10_4_IMMUTABLE_AUTHORIZED",
    }
    ps7 = initialize_run(run_root, auth_path, artifacts)
    server_proc = None
    stage_results: list[dict[str, Any]] = []
    shutdown_results: list[dict[str, Any]] = []
    forensic_results: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    selected = baseline_config()
    hardware_actions = False
    active_stage: str | None = None
    archived = True
    try:
        server_proc, server = start_hw_server(run_root / "raw_logs")
        hardware_actions = True
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server start failed"))
        initial = guarded_shutdown(run_root, auth_path, artifacts, "initial", env)
        shutdown_results.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for stage in STAGES:
            active_stage = stage
            archived = False
            before = guarded_shutdown(run_root, auth_path, artifacts, f"{stage}_before", env)
            shutdown_results.append(before)
            if before.get("status") != "PASS":
                raise RuntimeError(f"{stage}: shutdown-before unconfirmed")
            plans = build_plans(selected)
            selected_name = str(selected.get("name", ""))
            expected_plan_hash = authorization["allowed_plan_sha256"].get(
                selected_name, {}
            ).get(stage)
            actual_plan_hash = hashlib.sha256(
                plans[stage].encode("ascii")
            ).hexdigest()
            if expected_plan_hash != actual_plan_hash:
                raise RuntimeError(
                    f"{stage}: selected immutable plan authorization mismatch"
                )
            process, stage_dir = invoke_stage(
                stage, plans[stage], run_root, auth_path, artifacts, ps7, env
            )
            process_failed = bool(process.get("returncode") != 0 or process.get("timed_out"))
            archive = capture_and_archive(
                stage, run_root, auth_path, env,
                force_abort=process_failed,
            )
            forensic_results.append(archive)
            archived = archive.get("status") == "PASS"
            if not archived:
                raise RuntimeError(f"{stage}: forensic archive failed")
            after = guarded_shutdown(run_root, auth_path, artifacts, f"{stage}_after", env)
            shutdown_results.append(after)
            result = evaluate_stage(stage, stage_dir, process, archive, plans[stage])
            result["shutdown_before_status"] = before.get("status")
            result["shutdown_after_status"] = after.get("status")
            stage_results.append(result)
            if after.get("status") != "PASS":
                raise RuntimeError(f"{stage}: shutdown-after unconfirmed")
            if stage == "tuning" and result.get("status") == "PASS":
                proposed = dict(result["semantics"]["selected"])
                if proposed not in authorization["allowed_selected_configs"]:
                    raise RuntimeError("tuning selected an unauthorized configuration")
                selected = proposed
            if result.get("status") != "PASS" and stage not in NONBLOCKING_STAGES:
                raise RuntimeError(f"{stage}: mandatory stage failed closed")
        final_shutdown = guarded_shutdown(run_root, auth_path, artifacts, "final", env)
        shutdown_results.append(final_shutdown)
        if final_shutdown.get("status") != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except Exception as exc:
        campaign_errors.append(str(exc))
    finally:
        if active_stage is not None and not archived:
            try:
                retry = capture_and_archive(
                    f"{active_stage}_finally_before_shutdown", run_root,
                    auth_path, env, force_abort=True,
                )
                forensic_results.append(retry)
                if retry.get("status") != "PASS":
                    campaign_errors.append("finally forensic archive failed")
            except BaseException as exc:
                campaign_errors.append(f"finally forensic exception: {exc}")
        hardware_actions = True
        emergency = guarded_shutdown(run_root, auth_path, artifacts, "finally", env)
        shutdown_results.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            try:
                terminate_tree(server_proc)
            except Exception as exc:
                campaign_errors.append(f"hw_server termination failed: {exc}")

    by_stage = {item["stage"]: item for item in stage_results}
    mandatory = [stage for stage in STAGES if stage not in NONBLOCKING_STAGES]
    mandatory_pass = all(by_stage.get(stage, {}).get("status") == "PASS"
                         for stage in mandatory)
    all_shutdown = bool(shutdown_results) and all(
        item.get("status") == "PASS" and item.get("SHUTDOWN_FIXED") == "PASS"
        and item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdown_results
    )
    nonblocking_failures = [stage for stage in NONBLOCKING_STAGES
                            if by_stage.get(stage, {}).get("status") != "PASS"]
    counters = zero_counter_summary(stage_results)
    hard_zero = all(value == 0 for value in counters.values())
    half_windows = by_stage.get("half_duplex", {}).get("semantics", {}).get("windows", [])
    half_by_direction = {int(item["direction"]): item for item in half_windows}
    if mandatory_pass and all_shutdown and hard_zero and not campaign_errors:
        status = "PASS_WITH_NONBLOCKING_LIMITS" if nonblocking_failures else "PASS"
    elif all_shutdown and any(item.get("application_goodput_bps", 0) >= 8_000_000
                              for item in half_windows):
        status = "PARTIAL"
    else:
        status = "FAIL"
    summary = {
        "schema_version": 1, "test_id": "P10_4-FINAL",
        "status": status, "scope": SCOPE, "run_id": args.run_id,
        "goal_sha256": GOAL_SHA256,
        "artifact_source_commit": authorization["source_commit"],
        "artifacts": authorization["artifacts"],
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False,
        "automation_only": True, "user_hold_points": 0,
        "network_used": False, "hardware_moved": False,
        "wiring_changed": False, "module_replaced": False,
        "external_instrumentation_used": False, "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "board_binding": {
            "fixed": f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}",
            "rotating": f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}",
        },
        "module_binding": MODULE_BINDING, "selected_config": selected,
        "application_goodput_bps": {
            "F_TO_R": half_by_direction.get(0, {}).get("application_goodput_bps"),
            "R_TO_F": half_by_direction.get(1, {}).get("application_goodput_bps"),
        },
        "margin_9mbps": {
            "F_TO_R": half_by_direction.get(0, {}).get("application_goodput_bps", 0) >= 9_000_000,
            "R_TO_F": half_by_direction.get(1, {}).get("application_goodput_bps", 0) >= 9_000_000,
        },
        "stretch_9p6mbps": {
            "F_TO_R": half_by_direction.get(0, {}).get("application_goodput_bps", 0) >= 9_600_000,
            "R_TO_F": half_by_direction.get(1, {}).get("application_goodput_bps", 0) >= 9_600_000,
        },
        "counters": counters, "stages": stage_results,
        "forensics": forensic_results, "shutdowns": shutdown_results,
        "SHUTDOWN_FIXED": "PASS" if all_shutdown else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if all_shutdown else "FAIL",
        "nonblocking_failures": sorted(nonblocking_failures),
        "external_power_acceptance": "PENDING_NOT_IN_SCOPE",
        "external_tfdu_duty": "PENDING_NOT_IN_SCOPE", "p11_status": "NOT_STARTED",
        "errors": campaign_errors, "generated_at_utc": utc_now(),
    }
    consistency = publish_evidence(summary, run_root, authorization)
    if consistency.get("status") != "PASS":
        status = "FAIL"
        summary["status"] = status
        summary["errors"].append("run evidence consistency failed")
        write_json(run_root / "final/orchestrator_result.json", summary)
        write_pair(GENERATED / "p10_4_final_summary", summary,
                   "P10.4 final summary")
        write_pair(run_root / "final/p10_4_final_summary", summary,
                   "P10.4 final summary")
        write_pair(run_root / "final/p10_4_evidence_consistency", consistency,
                   "P10.4 evidence consistency")
        terminal_manifest = evidence_manifest(run_root)
        terminal_errors = verify_evidence_manifest(run_root, terminal_manifest)
        consistency["terminal_fail_manifest_verified"] = not terminal_errors
        consistency["terminal_fail_manifest_errors"] = terminal_errors
        write_pair(GENERATED / "p10_4_evidence_consistency", consistency,
                   "P10.4 evidence consistency")
    consumed = dict(authorization)
    consumed.update({
        "status": f"CONSUMED_AFTER_P10_4_{status}",
        "current_run_hardware_authorization": False, "consumed": True,
        "consumed_at_utc": utc_now(),
        "result": rel(run_root / "final/orchestrator_result.json"),
        "evidence_consistency": consistency["status"],
    })
    write_json(AUTH, consumed)
    write_pair(GENERATED / "p10_4_authorization", {
        "schema_version": 1, "test_id": "P10_4-AUTHORIZATION",
        "status": consumed["status"], "run_id": args.run_id,
        "authorization": rel(AUTH), "current_run_hardware_authorization": False,
        "consumed": True, "result": consumed["result"], "errors": [],
    }, "P10.4 current-run authorization")
    print(f"P10_4_HARDWARE={status}")
    print(f"P10_4_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={summary['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={summary['SHUTDOWN_ROTATING']}")
    return 0 if status in {"PASS", "PASS_WITH_NONBLOCKING_LIMITS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
