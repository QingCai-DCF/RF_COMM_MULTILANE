#!/usr/bin/env python3
"""Fail-closed P10.1 dual-AX7020 hardware-performance orchestrator."""

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
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from p10_hardware_runtime import (
    Case,
    EXPECTED_FIXED_SERIAL,
    EXPECTED_FIXED_TARGET,
    EXPECTED_PART,
    EXPECTED_ROTATING_SERIAL,
    EXPECTED_ROTATING_TARGET,
    XSDB,
    STAGE_TCL,
    evaluate_pair,
    extract_ps7_init,
    inside,
    invoke_shutdown,
    parse_mailbox,
    parse_markers,
    plan_text,
    run_bounded,
    sha256,
    start_hw_server,
    terminate_tree,
)


ROOT = Path(__file__).resolve().parents[1]
GOAL = Path(
    r"C:\Users\user\Downloads"
    r"\P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE_GOAL.md"
)
EXPECTED_GOAL_SHA256 = (
    "b3d0ae793a89ba270ca72880fb4fa38bcb17ac7631f3fc650e2557963840f9d3"
)
EXPECTED_BRANCH = "p10.1/hardware-performance-acceptance"
EXPECTED_SCOPE = "P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE"
OFFLINE_TAG = "p10.1-offline-performance-ready"
OFFLINE_SOURCE = "ae942f0b5d9e9b4b7f5ced4751cc748c55b81183"
OFFLINE_EVIDENCE_CHECKPOINT = "8c34d60f064b01b95dc9c35b664ffbe43efb0b1f"
AUTH_PATH = ROOT / "config/p10_1_current_run_hardware_authorization.json"
RETRY_OVERRIDE_PATH = (
    ROOT / "config/p10_1_retry_limit_override_authorization.json"
)
FUNCTIONAL_SUMMARY = (
    ROOT / "evidence/generated/p10_1_hw_functional_build_summary.json"
)
RUNTIME_SUMMARY = (
    ROOT / "evidence/generated/p10_1_hw_ps_runtime_build_summary.json"
)
SHUTDOWN_MANIFEST = ROOT / "evidence/generated/p10_offline_artifact_manifest.json"
HARDWARE_RUNTIME_CONFIG = (
    ROOT / "config/performance/p10_1_hardware_runtime.yaml"
)
HASHED_INPUTS = {
    "goal": GOAL,
    "requirements": ROOT / "config/project_requirements.yaml",
    "register_map": ROOT / "config/register_map/ir_axi_regs.yaml",
    "measurement_contract": (
        ROOT / "config/performance/p10_1_measurement_contract.yaml"
    ),
    "pipeline_model": ROOT / "config/performance/p10_1_pipeline.yaml",
    "streaming_contract": ROOT / "config/performance/p10_1_streaming.yaml",
    "hardware_runtime": HARDWARE_RUNTIME_CONFIG,
    "wiring": ROOT / "config/hardware/p10_active_wiring.yaml",
    "fixed_profile": ROOT / "board_profiles/ax7020_fixed_2lane/profile.yaml",
    "fixed_xdc": (
        ROOT
        / "board_profiles/ax7020_fixed_2lane"
        / "ax7020_fixed_2lane.generated.xdc"
    ),
    "rotating_profile": (
        ROOT / "board_profiles/ax7020_rotating_2lane/profile.yaml"
    ),
    "rotating_xdc": (
        ROOT
        / "board_profiles/ax7020_rotating_2lane"
        / "ax7020_rotating_2lane.generated.xdc"
    ),
    "runner": Path(__file__).resolve(),
    "xsdb_stage": STAGE_TCL,
}
HW_ROOT = ROOT / "evidence/hardware/p10_1"
GENERATED = ROOT / "evidence/generated"
RUN_RE = re.compile(r"^p10_1_[A-Za-z0-9_.-]+$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
DIAGNOSTIC_STAGE_NEW_RUN_ID_LIMIT = 2
RETRY_OVERRIDE_AUTHORIZATION_ID = (
    "P10_1-HARDWARE-DIAGNOSTIC-RETRY-LIMIT-OVERRIDE"
)
UNLIMITED_RETRY_OVERRIDE_POLICY = (
    "USER_OVERRIDE_NO_LIMIT_UNTIL_CAMPAIGN_TERMINAL"
)
FLAG_ABORT_25 = 1 << 16
FLAG_ABORT_75 = 1 << 17
FLAG_DMA_RESET_SENDER = 1 << 18
FLAG_PL_RESET = 1 << 19
FLAG_DUPLICATE_SEGMENT = 1 << 20
FLAG_STALE_SEGMENT = 1 << 21
FLAG_PS_RESET_SENDER = 1 << 22
FLAG_PS_RESET_RECEIVER = 1 << 23
FLAG_DMA_RESET_RECEIVER = 1 << 24
RECOVERY_FLAGS = (
    FLAG_ABORT_25
    | FLAG_ABORT_75
    | FLAG_DMA_RESET_SENDER
    | FLAG_PL_RESET
    | FLAG_DUPLICATE_SEGMENT
    | FLAG_STALE_SEGMENT
    | FLAG_DMA_RESET_RECEIVER
)
SERVICE_RESET_FLAGS = FLAG_PS_RESET_SENDER | FLAG_PS_RESET_RECEIVER
P10_1_MAGIC = 0x31303150
P10_1_SCHEMA = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True
    ).strip()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def hash_inputs() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for label, path in HASHED_INPUTS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        result[label] = {
            "path": str(path) if not inside(path, ROOT) else rel(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
    return result


def p101_case(
    label: str,
    *,
    direction: int,
    total: int,
    lane: int = 3,
    buffer_count: int = 4,
    ring: int = 16,
    batch: int = 4,
    object_bytes: int = 256 * 1024,
    descriptor_bytes: int = 64 * 1024,
    flags: int = 0,
    object_id: int = 0x10100000,
    timeout: int = 600_000,
    faultflags: int = 0,
) -> Case:
    return Case(
        label=label,
        command=13,
        flags=flags,
        lane=lane,
        direction=direction,
        rate=2,
        weights=0x0101,
        size=total,
        ring=ring,
        cache=1,
        timeout=timeout,
        session=0xA1010001,
        path=0x101,
        object=object_id,
        dropdata=8,
        dropack=32,
        unavailable=0,
        rawtarget=object_bytes,
        spacing=descriptor_bytes,
        stale=buffer_count,
        initialseq=batch,
        faultflags=faultflags,
    )


PlanItem = Case | tuple[str, ...]


def p101_window(
    label: str,
    *,
    duration: int,
    direction: int,
    lane: int,
    maximum_chunk: int,
) -> tuple[str, ...]:
    return (
        "P101_WINDOW",
        label,
        str(duration),
        str(direction),
        str(lane),
        str(maximum_chunk),
    )


def p101_ps_reset(
    label: str,
    *,
    reset_role: str,
    direction: int,
    object_id: int,
) -> tuple[str, ...]:
    return (
        "P101_PSRESET",
        label,
        reset_role,
        str(direction),
        "3",
        str(64 * 1024 * 1024),
        str(object_id),
    )


def build_plans() -> dict[str, list[PlanItem]]:
    mib = 1024 * 1024
    plans: dict[str, list[PlanItem]] = {}
    plans["preflight"] = [
        Case("preflight_identity", 1),
        Case(
            "diagnostic_only_1byte",
            3,
            flags=2,
            lane=3,
            direction=0,
            rate=2,
            size=1,
            ring=16,
            cache=1,
            timeout=30_000,
            object=0x10100001,
        ),
        Case("short_ring_wrap", 4, ring=8),
        Case("idle_heavy_5s", 11, idle=5000, timeout=15_000),
        *[
            p101_case(
                f"pattern_{name}_1m",
                direction=index & 1,
                total=mib,
                flags=index << 8,
                object_id=0x10100010 + index,
                timeout=120_000,
            )
            for index, name in enumerate(
                ("prbs", "zero", "one", "counter", "corpus")
            )
        ],
        p101_case(
            "failed_object_diagnostic",
            direction=0,
            total=mib,
            flags=FLAG_ABORT_25,
            object_id=0x10100020,
            timeout=120_000,
        ),
    ]
    plans["smoke"] = [
        Case("identity", 1),
        *[
            Case(
                f"raw_{lane_name}_{direction_name}_64",
                2,
                lane=lane,
                direction=direction,
                rawtarget=64,
                spacing=1024,
                timeout=30_000,
            )
            for lane, lane_name in ((1, "lane0"), (2, "lane1"))
            for direction, direction_name in ((0, "f_to_r"), (1, "r_to_f"))
        ],
        p101_case(
            "smoke_lane0_f_to_r_1m",
            direction=0,
            lane=1,
            total=mib,
            object_id=0x10100100,
            timeout=120_000,
        ),
        p101_case(
            "smoke_lane0_r_to_f_1m",
            direction=1,
            lane=1,
            total=mib,
            object_id=0x10100101,
            timeout=120_000,
        ),
        p101_case(
            "smoke_lane1_f_to_r_1m",
            direction=0,
            lane=2,
            total=mib,
            object_id=0x10100102,
            timeout=120_000,
        ),
        p101_case(
            "smoke_lane1_r_to_f_1m",
            direction=1,
            lane=2,
            total=mib,
            object_id=0x10100103,
            timeout=120_000,
        ),
        p101_case(
            "smoke_two_lane_f_to_r_1m",
            direction=0,
            total=mib,
            object_id=0x10100104,
            timeout=120_000,
        ),
        p101_case(
            "smoke_two_lane_r_to_f_1m",
            direction=1,
            total=mib,
            object_id=0x10100105,
            timeout=120_000,
        ),
        Case("identity_after_stream_rearm", 1),
    ]
    plans["baseline"] = [
        p101_window(
            f"baseline_{lane_name}_{direction_name}_30s",
            duration=30,
            direction=direction,
            lane=lane,
            maximum_chunk=mib,
        )
        for lane, lane_name in ((1, "lane0"), (2, "lane1"))
        for direction, direction_name in ((0, "f_to_r"), (1, "r_to_f"))
    ] + [
        p101_window(
            "baseline_two_lane_f_to_r_60s",
            duration=60,
            direction=0,
            lane=3,
            maximum_chunk=16 * mib,
        ),
        p101_window(
            "baseline_two_lane_r_to_f_60s",
            duration=60,
            direction=1,
            lane=3,
            maximum_chunk=16 * mib,
        ),
    ]
    plans["tuning"] = [
        p101_case(
            "tune_buffer2",
            direction=0,
            total=4 * mib,
            buffer_count=2,
            object_id=0x10101000,
            timeout=30_000,
        ),
        p101_case(
            "tune_buffer4",
            direction=0,
            total=4 * mib,
            object_id=0x10101001,
            timeout=30_000,
        ),
        p101_case(
            "tune_buffer8",
            direction=0,
            total=4 * mib,
            buffer_count=8,
            object_bytes=128 * 1024,
            object_id=0x10101002,
            timeout=30_000,
        ),
        p101_case(
            "tune_ring8",
            direction=0,
            total=4 * mib,
            ring=8,
            object_bytes=128 * 1024,
            object_id=0x10101003,
            timeout=30_000,
        ),
        p101_case(
            "tune_ring16",
            direction=0,
            total=4 * mib,
            object_id=0x10101004,
            timeout=30_000,
        ),
        p101_case(
            "tune_ring32",
            direction=0,
            total=4 * mib,
            ring=32,
            object_id=0x10101005,
            timeout=30_000,
        ),
        p101_case(
            "tune_batch1",
            direction=0,
            total=4 * mib,
            ring=8,
            batch=1,
            object_bytes=64 * 1024,
            object_id=0x10101006,
            timeout=30_000,
        ),
        p101_case(
            "tune_batch4",
            direction=0,
            total=4 * mib,
            batch=4,
            object_id=0x10101007,
            timeout=30_000,
        ),
        p101_case(
            "tune_batch8",
            direction=0,
            total=4 * mib,
            ring=32,
            batch=8,
            object_bytes=512 * 1024,
            object_id=0x10101008,
            timeout=30_000,
        ),
        p101_case(
            "tune_batch16",
            direction=0,
            total=4 * mib,
            buffer_count=2,
            ring=32,
            batch=16,
            object_bytes=mib,
            object_id=0x10101009,
            timeout=30_000,
        ),
    ]
    plans["pipeline"] = [
        p101_window(
            "pipeline_f_to_r_120s",
            duration=120,
            direction=0,
            lane=3,
            maximum_chunk=16 * mib,
        ),
        p101_window(
            "pipeline_r_to_f_120s",
            duration=120,
            direction=1,
            lane=3,
            maximum_chunk=16 * mib,
        ),
    ]
    plans["streaming"] = [
        p101_case(
            "stream_64m_f_to_r",
            direction=0,
            total=64 * mib,
            object_id=0x10102000,
        ),
        p101_case(
            "stream_64m_r_to_f",
            direction=1,
            total=64 * mib,
            object_id=0x10102001,
        ),
    ]
    plans["faults"] = [
        p101_case(
            "abort25_f_to_r_64m",
            direction=0,
            total=64 * mib,
            flags=FLAG_ABORT_25,
            object_id=0x10103000,
        ),
        p101_case(
            "post_abort25_clean_f_to_r_64m",
            direction=0,
            total=64 * mib,
            object_id=0x10103001,
        ),
        p101_case(
            "abort75_r_to_f_64m",
            direction=1,
            total=64 * mib,
            flags=FLAG_ABORT_75,
            object_id=0x10103002,
        ),
        p101_case(
            "post_abort75_clean_r_to_f_64m",
            direction=1,
            total=64 * mib,
            object_id=0x10103003,
        ),
        p101_case(
            "dma_reset_sender_f_to_r_64m",
            direction=0,
            total=64 * mib,
            flags=FLAG_DMA_RESET_SENDER,
            object_id=0x10103004,
        ),
        p101_case(
            "post_dma_reset_clean_f_to_r_64m",
            direction=0,
            total=64 * mib,
            object_id=0x10103005,
        ),
        p101_case(
            "dma_reset_receiver_f_to_r_64m",
            direction=0,
            total=64 * mib,
            flags=FLAG_DMA_RESET_RECEIVER,
            object_id=0x10103006,
        ),
        p101_case(
            "post_dma_receiver_clean_f_to_r_64m",
            direction=0,
            total=64 * mib,
            object_id=0x10103007,
        ),
        p101_case(
            "pl_reset_r_to_f_64m",
            direction=1,
            total=64 * mib,
            flags=FLAG_PL_RESET,
            object_id=0x10103008,
        ),
        p101_case(
            "post_pl_reset_clean_r_to_f_64m",
            direction=1,
            total=64 * mib,
            object_id=0x10103009,
        ),
        p101_case(
            "duplicate_segment_f_to_r_64m",
            direction=0,
            total=64 * mib,
            flags=FLAG_DUPLICATE_SEGMENT,
            object_id=0x1010300A,
        ),
        p101_case(
            "post_duplicate_clean_f_to_r_64m",
            direction=0,
            total=64 * mib,
            object_id=0x1010300B,
        ),
        p101_case(
            "stale_segment_r_to_f_64m",
            direction=1,
            total=64 * mib,
            flags=FLAG_STALE_SEGMENT,
            object_id=0x1010300C,
        ),
        p101_case(
            "post_stale_clean_r_to_f_64m",
            direction=1,
            total=64 * mib,
            object_id=0x1010300D,
        ),
        p101_ps_reset(
            "sender_ps_service_reset_f_to_r",
            reset_role="fixed",
            direction=0,
            object_id=0x1010300E,
        ),
        p101_case(
            "post_sender_ps_reset_clean_f_to_r_64m",
            direction=0,
            total=64 * mib,
            object_id=0x1010300F,
        ),
        p101_ps_reset(
            "receiver_ps_service_reset_f_to_r",
            reset_role="rotating",
            direction=0,
            object_id=0x10103010,
        ),
        p101_case(
            "post_receiver_ps_reset_clean_f_to_r_64m",
            direction=0,
            total=64 * mib,
            object_id=0x10103011,
        ),
    ]
    raw_xtalk: list[PlanItem] = []
    frame_xtalk: list[PlanItem] = []
    for direction, role in ((0, "f"), (1, "r")):
        for lane, lane_name in ((1, "0"), (2, "1")):
            for count in (64, 1024):
                raw_xtalk.append(
                    Case(
                        f"xtalk_tx_{role}{lane_name}_raw{count}",
                        2,
                        lane=lane,
                        direction=direction,
                        rawtarget=count,
                        spacing=1024,
                        timeout=60_000,
                    )
                )
            frame_xtalk.append(
                p101_window(
                    f"xtalk_tx_{role}{lane_name}_frame_10s",
                    duration=10,
                    direction=direction,
                    lane=lane,
                    maximum_chunk=mib,
                )
            )
    plans["crosstalk"] = raw_xtalk + frame_xtalk
    plans["half_duplex"] = [
        p101_window(
            "half_duplex_f_to_r_320s",
            duration=320,
            direction=0,
            lane=3,
            maximum_chunk=64 * mib,
        ),
        p101_window(
            "half_duplex_r_to_f_320s",
            duration=320,
            direction=1,
            lane=3,
            maximum_chunk=64 * mib,
        ),
    ]
    plans["oneplusone"] = [
        ("P101_1PLUS1_PROBE", "oneplusone_lane0_f2r_lane1_r2f"),
    ]
    plans["formal"] = [
        ("P101_FORMAL", "stationary_30min", "1800"),
    ]
    return plans


def plan_hashes(stages: list[str]) -> dict[str, str]:
    plans = build_plans()
    return {
        stage: hashlib.sha256(plan_text(plans[stage]).encode()).hexdigest()
        for stage in stages
    }


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def attempted_stage_run_ids(
    stage: str, *, hardware_root: Path = HW_ROOT
) -> list[str]:
    """Return run IDs that actually entered a hardware stage.

    ``stages/<stage>`` is created only after hardware execution begins. Merely
    preparing an authorization or running a dry-run cannot consume the Goal's
    diagnostic-stage run-ID budget.
    """

    if not hardware_root.is_dir():
        return []
    run_ids: list[str] = []
    run_roots = sorted(
        item for item in hardware_root.iterdir() if item.is_dir()
    )
    for run_root in run_roots:
        if not RUN_RE.fullmatch(run_root.name):
            continue
        stage_root = run_root / "stages" / stage
        if stage_root.is_dir() and any(
            item.is_file() for item in stage_root.rglob("*")
        ):
            run_ids.append(run_root.name)
    return run_ids


def diagnostic_retry_budget(
    stages: list[str], *, hardware_root: Path = HW_ROOT
) -> dict[str, dict[str, Any]]:
    return {
        stage: {
            "limit": DIAGNOSTIC_STAGE_NEW_RUN_ID_LIMIT,
            "run_ids": attempted_stage_run_ids(
                stage, hardware_root=hardware_root
            ),
        }
        for stage in stages
    }


def _expected_board_identities() -> dict[str, dict[str, str]]:
    return {
        "fixed": {
            "id": f"AX7020-F/JTAG:{EXPECTED_FIXED_SERIAL}",
            "serial": EXPECTED_FIXED_SERIAL,
            "target": EXPECTED_FIXED_TARGET,
        },
        "rotating": {
            "id": f"AX7020-R/JTAG:{EXPECTED_ROTATING_SERIAL}",
            "serial": EXPECTED_ROTATING_SERIAL,
            "target": EXPECTED_ROTATING_TARGET,
        },
    }


def validate_retry_limit_override(
    path: Path,
    run_id: str,
    stages: list[str],
    *,
    hardware_root: Path = HW_ROOT,
) -> tuple[dict[str, Any] | None, dict[str, dict[str, Any]], list[str]]:
    """Validate an explicit user override of the Goal section 23 limits.

    This runner intentionally has no command that creates the override record.
    It may only be materialized after the user explicitly extends or removes
    the limit. An unlimited campaign override is only an authorization source;
    every actual attempt still receives a new run-bound immutable record.
    """

    budget = diagnostic_retry_budget(stages, hardware_root=hardware_root)
    exhausted = {
        stage: item
        for stage, item in budget.items()
        if len(item["run_ids"]) >= int(item["limit"])
    }
    if not path.is_file():
        if not exhausted:
            return None, budget, []
        names = ", ".join(sorted(exhausted))
        return None, budget, [
            "Goal section 23 diagnostic-stage run-ID limit exhausted for "
            f"{names}; explicit run-bound retry-limit override is absent"
        ]
    try:
        record = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, budget, [f"retry-limit override unreadable: {exc}"]

    if record.get("retry_limit_policy") == UNLIMITED_RETRY_OVERRIDE_POLICY:
        try:
            artifact_source, artifacts = collect_artifacts()
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            return None, budget, [
                f"retry-limit override artifact validation failed: {exc}"
            ]
        expected_unlimited = {
            "schema_version": 2,
            "authorization_id": RETRY_OVERRIDE_AUTHORIZATION_ID,
            "status": "AUTHORIZED",
            "authorization_source_only": True,
            "scope": EXPECTED_SCOPE,
            "goal_sha256": EXPECTED_GOAL_SHA256,
            "user_retry_limit_override": "不设上限",
            "retry_limit_policy": UNLIMITED_RETRY_OVERRIDE_POLICY,
            "current_run_hardware_authorization": False,
            "current_run_authorization_materialized_per_run": True,
            "authorized_campaign_stages": list(build_plans()),
            "run_id_policy": "NEW_UNIQUE_IMMUTABLE_AUTHORIZATION_PER_RUN",
            "board_identities": _expected_board_identities(),
            "part": EXPECTED_PART,
            "artifact_source_commit": artifact_source,
            "artifacts": artifacts,
            "base_goal_retry_limits": {
                "jtag_connect": 3,
                "program": 2,
                "diagnostic_stage_new_run_id": 2,
            },
            "base_goal_retry_limits_overridden": [
                "jtag_connect",
                "program",
                "diagnostic_stage_new_run_id",
            ],
            "effective_retry_limits": {
                "jtag_connect": None,
                "program": None,
                "diagnostic_stage_new_run_id": None,
            },
            "maximum_single_formal_run_seconds": 1800,
            "maximum_lane_mask": 3,
            "lane_masks": [1, 2, 3],
            "ethernet_allowed": False,
            "movement_allowed": False,
            "rotation_allowed": False,
            "angle_adjustment_allowed": False,
            "obscuration_allowed": False,
            "module_exchange_allowed": False,
            "rewiring_allowed": False,
            "reusable_for_new_run_id_within_same_campaign": True,
            "reusable_for_future_campaign": False,
        }
        errors = [
            f"unlimited retry override {key} mismatch"
            for key, value in expected_unlimited.items()
            if record.get(key) != value
        ]
        for stage, item in budget.items():
            item["base_goal_limit"] = item.pop("limit")
            item["effective_limit"] = None
            item["override_applied"] = True
        errors.extend(_retry_override_common_errors(record))
        return record, budget, errors

    if not exhausted:
        return None, budget, []

    exhausted_names = sorted(exhausted)
    historical = {
        stage: exhausted[stage]["run_ids"] for stage in exhausted_names
    }
    expected = {
        "schema_version": 1,
        "authorization_id": RETRY_OVERRIDE_AUTHORIZATION_ID,
        "status": "AUTHORIZED",
        "scope": EXPECTED_SCOPE,
        "goal_sha256": EXPECTED_GOAL_SHA256,
        "current_run_hardware_authorization": True,
        "authorized_run_id": run_id,
        "authorized_campaign_stages": stages,
        "retry_limit_override_stages": exhausted_names,
        "historical_stage_run_ids": historical,
        "additional_new_run_ids_by_stage": {
            stage: 1 for stage in exhausted_names
        },
        "board_identities": _expected_board_identities(),
        "maximum_single_formal_run_seconds": 1800,
        "maximum_lane_mask": 3,
        "ethernet_allowed": False,
        "movement_allowed": False,
        "rotation_allowed": False,
        "angle_adjustment_allowed": False,
        "obscuration_allowed": False,
        "module_exchange_allowed": False,
        "rewiring_allowed": False,
        "reusable_for_future_run": False,
    }
    errors = [
        f"retry-limit override {key} mismatch"
        for key, value in expected.items()
        if record.get(key) != value
    ]
    errors.extend(_retry_override_common_errors(record))
    return record, budget, errors


def _retry_override_common_errors(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    statement = record.get("user_authorization_statement")
    statement_hash = record.get("user_authorization_statement_sha256")
    if not isinstance(statement, str) or not statement.strip():
        errors.append("retry-limit override user authorization statement missing")
    elif (
        not isinstance(statement_hash, str)
        or not SHA_RE.fullmatch(statement_hash)
        or hashlib.sha256(statement.encode("utf-8")).hexdigest()
        != statement_hash
    ):
        errors.append("retry-limit override user authorization statement hash mismatch")
    timestamp = record.get("user_authorization_received_at")
    if not isinstance(timestamp, str) or not timestamp.strip():
        errors.append("retry-limit override authorization timestamp missing")
    reason = record.get("override_reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append("retry-limit override reason missing")
    shutdown = record.get("shutdown", {})
    if any(
        shutdown.get(key) is not True
        for key in (
            "before",
            "on_error",
            "on_timeout",
            "on_interrupt",
            "normal_exit",
            "after",
            "program_role_bound_shutdown_bitstreams",
        )
    ):
        errors.append("retry-limit override shutdown policy is incomplete")
    return errors


def retry_override_binding(record: dict[str, Any] | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "path": rel(RETRY_OVERRIDE_PATH),
        "sha256": sha256(RETRY_OVERRIDE_PATH),
        "authorization_id": RETRY_OVERRIDE_AUTHORIZATION_ID,
        "retry_limit_policy": record.get("retry_limit_policy"),
        "user_authorization_statement_sha256": record.get(
            "user_authorization_statement_sha256"
        ),
    }


def _record(
    role: str, kind: str, item: dict[str, Any]
) -> dict[str, Any]:
    path = ROOT / item["path"]
    if not path.is_file() or sha256(path) != item["sha256"]:
        raise RuntimeError(f"invalid build artifact {role}:{kind}")
    return {
        "role": role,
        "kind": kind,
        "path": rel(path),
        "sha256": item["sha256"],
        "bytes": path.stat().st_size,
    }


def collect_artifacts() -> tuple[str, list[dict[str, Any]]]:
    functional = _load_json(FUNCTIONAL_SUMMARY)
    runtime = _load_json(RUNTIME_SUMMARY)
    shutdown = _load_json(SHUTDOWN_MANIFEST)
    source = functional.get("source_commit")
    if (
        not isinstance(source, str)
        or not re.fullmatch(r"[0-9a-f]{40}", source)
        or runtime.get("source_commit") != source
    ):
        raise RuntimeError("functional/runtime artifact source mismatch")
    for name, summary in (("functional", functional), ("runtime", runtime)):
        if (
            summary.get("status") != "PASS"
            or summary.get("source_worktree_dirty") is not False
        ):
            raise RuntimeError(f"{name} build summary is not a clean source match")
    records: list[dict[str, Any]] = []
    for role in ("fixed", "rotating"):
        f_role = next(item for item in functional["roles"] if item["role"] == role)
        r_role = next(item for item in runtime["roles"] if item["role"] == role)
        records.extend(
            [
                _record(
                    role,
                    "functional_bitstream",
                    f_role["artifacts"]["bitstream"],
                ),
                _record(role, "xsa", f_role["artifacts"]["xsa"]),
                _record(role, "bsp", r_role["artifacts"]["bsp"]),
                _record(role, "elf", r_role["artifacts"]["elf"]),
            ]
        )
        shutdown_item = next(
            item
            for item in shutdown["artifacts"]
            if item["role"] == role and item["kind"] == "shutdown_bitstream"
        )
        records.append(_record(role, "shutdown_bitstream", shutdown_item))
    return source, records


def create_authorization(run_id: str, stages: list[str]) -> dict[str, Any]:
    if not RUN_RE.fullmatch(run_id):
        raise ValueError("invalid P10.1 run id")
    if git("branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError("wrong P10.1 hardware branch")
    if git("status", "--porcelain"):
        raise RuntimeError("authorization requires a clean worktree")
    retry_override, retry_budget, retry_errors = validate_retry_limit_override(
        RETRY_OVERRIDE_PATH, run_id, stages
    )
    if retry_errors:
        raise RuntimeError("; ".join(retry_errors))
    try:
        prior_authorization = _load_json(AUTH_PATH)
    except (OSError, ValueError, json.JSONDecodeError):
        prior_authorization = {}
    if prior_authorization.get("consumed") is True and retry_override is None:
        raise RuntimeError(
            "prior current-run hardware authorization is consumed; a fresh "
            "explicit run-bound authorization is required"
        )
    authorization_parent = git("rev-parse", "HEAD")
    if (
        git("rev-list", "-n", "1", OFFLINE_TAG)
        != OFFLINE_EVIDENCE_CHECKPOINT
        or subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                OFFLINE_EVIDENCE_CHECKPOINT,
                authorization_parent,
            ],
            cwd=ROOT,
        ).returncode
        != 0
    ):
        raise RuntimeError("offline base tag/checkpoint mismatch")
    if (
        subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                OFFLINE_SOURCE,
                OFFLINE_EVIDENCE_CHECKPOINT,
            ],
            cwd=ROOT,
        ).returncode
        != 0
    ):
        raise RuntimeError("offline source is not an ancestor of its checkpoint")
    inputs = hash_inputs()
    if inputs["goal"]["sha256"] != EXPECTED_GOAL_SHA256:
        raise RuntimeError("live P10.1 hardware Goal hash mismatch")
    source, artifacts = collect_artifacts()
    if (
        subprocess.run(
            ["git", "merge-base", "--is-ancestor", source, authorization_parent],
            cwd=ROOT,
        ).returncode
        != 0
    ):
        raise RuntimeError("artifact source is not an ancestor of authorization")
    if (
        subprocess.run(
            [
                "git",
                "merge-base",
                "--is-ancestor",
                OFFLINE_EVIDENCE_CHECKPOINT,
                source,
            ],
            cwd=ROOT,
        ).returncode
        != 0
    ):
        raise RuntimeError("artifact source does not contain offline checkpoint")
    payload = {
        "schema_version": 1,
        "authorization_id": "P10_1-HARDWARE-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED",
        "scope": EXPECTED_SCOPE,
        "run_id": run_id,
        "source_commit": source,
        "authorization_parent_commit": authorization_parent,
        "branch": EXPECTED_BRANCH,
        "offline_base_tag": OFFLINE_TAG,
        "offline_source_commit": OFFLINE_SOURCE,
        "offline_evidence_checkpoint": OFFLINE_EVIDENCE_CHECKPOINT,
        "goal_sha256": EXPECTED_GOAL_SHA256,
        "current_run_hardware_authorization": True,
        "user_authorization_received_at": (
            retry_override.get("user_authorization_received_at")
            if retry_override is not None
            else "2026-07-31"
        ),
        "board_identities": _expected_board_identities(),
        "part": EXPECTED_PART,
        "authorized_stages": stages,
        "plan_sha256": plan_hashes(stages),
        "maximum_single_formal_run_seconds": 1800,
        "maximum_lane_mask": 3,
        "lane_masks": [1, 2, 3],
        "ethernet_allowed": False,
        "movement_allowed": False,
        "rotation_allowed": False,
        "angle_adjustment_allowed": False,
        "obscuration_allowed": False,
        "module_exchange_allowed": False,
        "rewiring_allowed": False,
        "shutdown": {
            "before": True,
            "on_error": True,
            "on_timeout": True,
            "on_interrupt": True,
            "normal_exit": True,
            "after": True,
            "program_role_bound_shutdown_bitstreams": True,
        },
        "input_hashes": inputs,
        "build_summaries": {
            "functional": {
                "path": rel(FUNCTIONAL_SUMMARY),
                "sha256": sha256(FUNCTIONAL_SUMMARY),
            },
            "runtime": {
                "path": rel(RUNTIME_SUMMARY),
                "sha256": sha256(RUNTIME_SUMMARY),
            },
            "shutdown": {
                "path": rel(SHUTDOWN_MANIFEST),
                "sha256": sha256(SHUTDOWN_MANIFEST),
            },
        },
        "artifacts": artifacts,
        "diagnostic_stage_retry_budget": retry_budget,
        "retry_limit_policy": (
            retry_override.get("retry_limit_policy")
            if retry_override is not None
            else "GOAL_SECTION_23_BOUNDED"
        ),
        "base_goal_retry_limits_overridden": (
            retry_override.get("base_goal_retry_limits_overridden", [])
            if retry_override is not None
            else []
        ),
        "effective_retry_limits": (
            retry_override.get("effective_retry_limits")
            if retry_override is not None
            else {
                "jtag_connect": 3,
                "program": 2,
                "diagnostic_stage_new_run_id": 2,
            }
        ),
        "user_retry_limit_override": (
            retry_override.get("user_retry_limit_override")
            if retry_override is not None
            else None
        ),
        "retry_limit_override": retry_override_binding(retry_override),
        "generated_at_utc": utc_now(),
    }
    write_json(AUTH_PATH, payload)
    return payload


def validate_authorization(
    path: Path, run_id: str, stages: list[str]
) -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        record = _load_json(path)
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {}, [f"authorization unreadable: {exc}"]
    retry_override, retry_budget, retry_errors = validate_retry_limit_override(
        RETRY_OVERRIDE_PATH, run_id, stages
    )
    errors.extend(retry_errors)
    expected = {
        "schema_version": 1,
        "authorization_id": "P10_1-HARDWARE-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED",
        "scope": EXPECTED_SCOPE,
        "run_id": run_id,
        "branch": EXPECTED_BRANCH,
        "offline_base_tag": OFFLINE_TAG,
        "offline_source_commit": OFFLINE_SOURCE,
        "offline_evidence_checkpoint": OFFLINE_EVIDENCE_CHECKPOINT,
        "goal_sha256": EXPECTED_GOAL_SHA256,
        "current_run_hardware_authorization": True,
        "part": EXPECTED_PART,
        "authorized_stages": stages,
        "plan_sha256": plan_hashes(stages),
        "maximum_single_formal_run_seconds": 1800,
        "maximum_lane_mask": 3,
        "lane_masks": [1, 2, 3],
        "ethernet_allowed": False,
        "movement_allowed": False,
        "rotation_allowed": False,
        "angle_adjustment_allowed": False,
        "obscuration_allowed": False,
        "module_exchange_allowed": False,
        "rewiring_allowed": False,
        "diagnostic_stage_retry_budget": retry_budget,
        "retry_limit_policy": (
            retry_override.get("retry_limit_policy")
            if retry_override is not None
            else "GOAL_SECTION_23_BOUNDED"
        ),
        "base_goal_retry_limits_overridden": (
            retry_override.get("base_goal_retry_limits_overridden", [])
            if retry_override is not None
            else []
        ),
        "effective_retry_limits": (
            retry_override.get("effective_retry_limits")
            if retry_override is not None
            else {
                "jtag_connect": 3,
                "program": 2,
                "diagnostic_stage_new_run_id": 2,
            }
        ),
        "user_retry_limit_override": (
            retry_override.get("user_retry_limit_override")
            if retry_override is not None
            else None
        ),
        "retry_limit_override": retry_override_binding(retry_override),
    }
    for key, value in expected.items():
        if record.get(key) != value:
            errors.append(f"authorization {key} mismatch")
    head = git("rev-parse", "HEAD")
    source = record.get("source_commit")
    parent = record.get("authorization_parent_commit")
    if not isinstance(source, str) or not re.fullmatch(
        r"[0-9a-f]{40}", source
    ):
        errors.append("authorization artifact source commit is malformed")
    if not isinstance(parent, str) or not re.fullmatch(
        r"[0-9a-f]{40}", parent
    ):
        errors.append("authorization parent commit is malformed")
    else:
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", parent, head],
            cwd=ROOT,
        ).returncode != 0:
            errors.append("authorization parent is not an ancestor of HEAD")
        else:
            changed = {
                item
                for item in git(
                    "diff", "--name-only", f"{parent}..{head}"
                ).splitlines()
                if item
            }
            if changed != {
                "config/p10_1_current_run_hardware_authorization.json"
            }:
                errors.append(
                    "post-authorization commit changed files other than the "
                    "immutable authorization"
                )
    if isinstance(source, str) and subprocess.run(
        ["git", "merge-base", "--is-ancestor", source, head], cwd=ROOT
    ).returncode != 0:
        errors.append("artifact source is not an ancestor of HEAD")
    if git("branch", "--show-current") != EXPECTED_BRANCH:
        errors.append("wrong hardware branch")
    if git("status", "--porcelain"):
        errors.append("hardware worktree is not clean")
    try:
        live_inputs = hash_inputs()
    except OSError as exc:
        live_inputs = {}
        errors.append(f"input hash read failed: {exc}")
    if record.get("input_hashes") != live_inputs:
        errors.append("authorization input hashes differ from live files")
    for label, expected_path in (
        ("functional", FUNCTIONAL_SUMMARY),
        ("runtime", RUNTIME_SUMMARY),
        ("shutdown", SHUTDOWN_MANIFEST),
    ):
        item = record.get("build_summaries", {}).get(label, {})
        if (
            item.get("path") != rel(expected_path)
            or not expected_path.is_file()
            or item.get("sha256") != sha256(expected_path)
        ):
            errors.append(f"authorization {label} summary hash mismatch")
    for label, expected_path in (
        ("functional", FUNCTIONAL_SUMMARY),
        ("runtime", RUNTIME_SUMMARY),
    ):
        try:
            summary = _load_json(expected_path)
        except (OSError, json.JSONDecodeError):
            summary = {}
        if (
            summary.get("status") != "PASS"
            or summary.get("source_commit") != source
            or summary.get("source_worktree_dirty") is not False
        ):
            errors.append(f"live {label} build summary source mismatch")
    identities = record.get("board_identities", {})
    if identities.get("fixed", {}).get("serial") != EXPECTED_FIXED_SERIAL:
        errors.append("fixed JTAG identity mismatch")
    if identities.get("rotating", {}).get("serial") != EXPECTED_ROTATING_SERIAL:
        errors.append("rotating JTAG identity mismatch")
    shutdown = record.get("shutdown", {})
    if any(
        shutdown.get(key) is not True
        for key in (
            "before",
            "on_error",
            "on_timeout",
            "on_interrupt",
            "normal_exit",
            "after",
            "program_role_bound_shutdown_bitstreams",
        )
    ):
        errors.append("shutdown policy is incomplete")
    artifacts: dict[str, Path] = {}
    required = {
        f"{role}:{kind}"
        for role in ("fixed", "rotating")
        for kind in (
            "shutdown_bitstream",
            "functional_bitstream",
            "xsa",
            "bsp",
            "elf",
        )
    }
    for item in record.get("artifacts", []):
        try:
            key = f"{item['role']}:{item['kind']}"
            candidate = (ROOT / item["path"]).resolve()
            expected_hash = item["sha256"]
            expected_bytes = int(item["bytes"])
        except (KeyError, TypeError, ValueError):
            errors.append("malformed authorization artifact")
            continue
        allowed_root = (
            ROOT / "artifacts/p10"
            if item.get("kind") == "shutdown_bitstream"
            else ROOT / "artifacts/p10_1"
        )
        if key in artifacts:
            errors.append(f"duplicate artifact {key}")
        elif not inside(candidate, allowed_root):
            errors.append(f"artifact outside content store {key}")
        elif (
            item.get("kind") != "shutdown_bitstream"
            and source is not None
            and f"/{source}/" not in candidate.as_posix()
        ):
            errors.append(f"artifact source namespace mismatch {key}")
        elif (
            not candidate.is_file()
            or not SHA_RE.fullmatch(str(expected_hash))
            or sha256(candidate) != expected_hash
            or candidate.stat().st_size != expected_bytes
        ):
            errors.append(f"artifact hash/size mismatch {key}")
        artifacts[key] = candidate
    if set(artifacts) != required:
        errors.append("authorization artifact set is incomplete")
    return record, artifacts, errors


def u64(words: list[int], index: int) -> int:
    return words[index] | (words[index + 1] << 32)


def parse_p101(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    if len(data) != 2048:
        raise ValueError(f"P10.1 result is {len(data)} bytes, expected 2048")
    words = list(struct.unpack("<512I", data))
    return {
        "words": words,
        "magic": words[0],
        "schema_version": words[1],
        "firmware_build_id": words[2],
        "endpoint_role": words[3],
        "service_state": words[4],
        "status": words[5],
        "command_sequence": words[6],
        "flags": words[7],
        "lane_mask": words[8],
        "direction": words[9],
        "rate_select": words[10],
        "total_bytes": words[11],
        "object_bytes": words[12],
        "descriptor_bytes": words[13],
        "descriptor_count_per_object": words[14],
        "object_count": words[15],
        "ring_depth": words[16],
        "descriptor_batch": words[17],
        "buffer_count": words[18],
        "ack_threshold": words[19],
        "outstanding_frames": words[20],
        "timeout_ms": words[21],
        "ps_elapsed_ticks": u64(words, 30),
        "pl_elapsed_ticks": u64(words, 36),
        "ps_timer_frequency_hz": words[38],
        "pl_timer_frequency_hz": words[39],
        "timer_error_ppm": words[40],
        "timer_crosscheck_pass": words[41],
        "application_bytes_accepted": u64(words, 42),
        "application_bytes_committed": u64(words, 44),
        "wire_bytes": u64(words, 46),
        "descriptors_submitted": u64(words, 48),
        "descriptors_completed": u64(words, 50),
        "objects_submitted": words[52],
        "objects_completed": words[53],
        "atomic_commit_count": words[54],
        "host_command_count": words[55],
        "fast_path_segment_count": words[56],
        "remote_commit_confirmed": words[57],
        "partial_commit_count": words[58],
        "duplicate_commit_count": words[59],
        "stale_commit_count": words[60],
        "descriptor_leak_count": words[61],
        "double_completion_count": words[62],
        "integrity_error_count": words[63],
        "crc_bad_count": words[64],
        "sha_mismatch_count": words[65],
        "retry_exhausted_count": words[66],
        "abort_count": words[67],
        "dma_reset_count": words[68],
        "pl_reset_count": words[69],
        "first_mismatch_offset": words[70],
        "last_error_detail": words[71],
        "input_crc32": words[72],
        "output_crc32": words[73],
        "input_sha256_words": words[74:82],
        "output_sha256_words": words[82:90],
        "payload_prepare_ticks": u64(words, 90),
        "integrity_verify_ticks": u64(words, 92),
        "inter_object_signal_ticks": u64(words, 94),
        "perf_snapshot_generation": words[96],
        "perf_application_accepted": u64(words, 97),
        "perf_application_committed": u64(words, 99),
        "perf_frame_acked": u64(words, 101),
        "perf_wire_bytes": u64(words, 103),
        "perf_descriptor_submitted": words[105],
        "perf_descriptor_completed": words[106],
        "perf_dma_stall": u64(words, 107),
        "perf_axis_stall": u64(words, 109),
        "perf_queue_occupancy": words[111],
        "perf_ack_wait": u64(words, 112),
        "perf_direction_quiet": u64(words, 114),
        "perf_integrity_error_count": words[116],
        "perf_retry_exhausted_count": words[117],
        "perf_descriptor_leak_count": words[118],
        "perf_double_completion_count": words[119],
        "raw_rx_before": words[120:124],
        "raw_rx_after": words[124:128],
        "physical_tx_before": words[128:132],
        "physical_tx_after": words[132:136],
        "duty_high_max_after": words[136:140],
        "duty_hard_fault_after": words[140:144],
        "tx_high_max_after": words[144:148],
        "physical_data_good_by_lane_after": words[148:150],
        "physical_ack_good_by_lane_after": words[150:152],
        "physical_crc_bad_by_lane_after": words[152:154],
        "physical_frame_bad_by_lane_after": words[154:156],
        "physical_preamble_by_lane_after": words[156:158],
        "physical_symbol_error_by_lane_after": words[158:160],
        "shutdown_attempt_count": words[160],
        "shutdown_verified_count": words[161],
        "final_pl_status": words[162],
        "final_phy_status": words[163],
        "descriptors_reclaimed_by_reset": words[164],
        "injected_fault_observed_count": words[165],
    }


def _integer_row(row: dict[str, str]) -> dict[str, Any]:
    numeric = {
        "command",
        "expected_status",
        "flags",
        "lane",
        "direction",
        "rate",
        "weights",
        "size",
        "ring",
        "cache",
        "txoff",
        "rxoff",
        "timeout",
        "session",
        "path",
        "object",
        "dropdata",
        "dropack",
        "unavailable",
        "rawtarget",
        "spacing",
        "stale",
        "initialseq",
        "faultflags",
        "idle",
        "injectmask",
        "injectdelay",
        "started_ms",
        "finished_ms",
        "sequence",
        "fixed_status",
        "rotating_status",
        "fixed_state",
        "rotating_state",
    }
    return {
        key: int(value, 0) if key in numeric and value else value
        for key, value in row.items()
    }


def evaluate_p101_pair(
    row: dict[str, Any], fixed: dict[str, Any], rotating: dict[str, Any]
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    recovery = (row["flags"] & RECOVERY_FLAGS) != 0
    service_reset = (row["flags"] & SERVICE_RESET_FLAGS) != 0
    if service_reset:
        expected_role = {"fixed": 1, "rotating": 2}
        for role, result in (("fixed", fixed), ("rotating", rotating)):
            checks = {
                "magic": result["magic"] == P10_1_MAGIC,
                "schema": result["schema_version"] == P10_1_SCHEMA,
                "role": result["endpoint_role"] == expected_role[role],
                "active_state": result["service_state"] in {3, 4},
                "status_not_failed": result["status"] == 0,
                "sequence": result["command_sequence"] == row["sequence"],
                "lane_mask": result["lane_mask"] == row["lane"],
                "direction": result["direction"] == row["direction"],
                "zero_commit_bytes": (
                    result["application_bytes_committed"] == 0
                ),
                "zero_atomic_commit": result["atomic_commit_count"] == 0,
                "no_remote_commit": result["remote_commit_confirmed"] == 0,
                "host_not_fast_path": result["host_command_count"] == 1,
                "descriptors_submitted": (
                    result["descriptors_submitted"] > 0
                ),
            }
            failed = [
                name for name, passed in checks.items() if not passed
            ]
            errors.extend(
                f"{row['label']}:{role}:{name}" for name in failed
            )
            result["checks"] = checks
        return errors, {
            "label": row["label"],
            "direction": row["direction"],
            "lane_mask": row["lane"],
            "requested_bytes": row["size"],
            "recovery_case": True,
            "service_reset_case": True,
            "application_goodput_bps": None,
            "fixed": {
                key: value
                for key, value in fixed.items()
                if key != "words"
            },
            "rotating": {
                key: value
                for key, value in rotating.items()
                if key != "words"
            },
        }
    expected_state = 7 if recovery else 6
    expected_role = {"fixed": 1, "rotating": 2}
    for role, result in (("fixed", fixed), ("rotating", rotating)):
        checks = {
            "magic": result["magic"] == P10_1_MAGIC,
            "schema": result["schema_version"] == P10_1_SCHEMA,
            "role": result["endpoint_role"] == expected_role[role],
            "service_state": result["service_state"] == expected_state,
            "status": result["status"] == 0,
            "sequence": result["command_sequence"] == row["sequence"],
            "lane_mask": result["lane_mask"] == row["lane"],
            "direction": result["direction"] == row["direction"],
            "total": result["total_bytes"] == row["size"],
            "ring": result["ring_depth"] == row["ring"],
            "batch": result["descriptor_batch"] == row["initialseq"],
            "buffers": result["buffer_count"] == row["stale"],
            "host_not_fast_path": result["host_command_count"] == 1,
            "segments_exceed_host_commands": (
                result["fast_path_segment_count"]
                > result["host_command_count"]
            ),
            "timer": result["timer_crosscheck_pass"] == 1,
            "descriptor_leak": result["descriptor_leak_count"] == 0,
            "double_completion": result["double_completion_count"] == 0,
            "partial_commit": result["partial_commit_count"] == 0,
            "duplicate_commit": result["duplicate_commit_count"] == 0,
            "stale_commit": result["stale_commit_count"] == 0,
            "integrity": result["integrity_error_count"] == 0,
            "crc": result["crc_bad_count"] == 0,
            "sha": result["sha_mismatch_count"] == 0,
            "retry_exhausted": result["retry_exhausted_count"] == 0,
            "perf_integrity": result["perf_integrity_error_count"] == 0,
            "perf_retry_exhausted": (
                result["perf_retry_exhausted_count"] == 0
            ),
            "perf_descriptor_leak": (
                result["perf_descriptor_leak_count"] == 0
            ),
            "perf_double_completion": (
                result["perf_double_completion_count"] == 0
            ),
            "shutdown_verified": (
                result["shutdown_attempt_count"] > 0
                and result["shutdown_verified_count"] > 0
            ),
            "safe_final_status": (
                (result["final_pl_status"] & 0x285) == 0
                and (result["final_pl_status"] & 0x2) != 0
            ),
            "safe_final_phy": (result["final_phy_status"] & 0xF00) == 0,
        }
        if recovery:
            checks.update(
                {
                    "zero_commit_bytes": (
                        result["application_bytes_committed"] == 0
                    ),
                    "zero_atomic_commit": result["atomic_commit_count"] == 0,
                    "no_remote_commit": (
                        result["remote_commit_confirmed"] == 0
                    ),
                    "abort_recorded": result["abort_count"] == 1,
                    "descriptor_reclaim_recorded": (
                        result["descriptors_reclaimed_by_reset"] > 0
                    ),
                }
            )
            local_sender = (
                (role == "fixed" and row["direction"] == 0)
                or (role == "rotating" and row["direction"] == 1)
            )
            if (
                row["flags"] & FLAG_DMA_RESET_SENDER
                and local_sender
            ) or (
                row["flags"] & FLAG_DMA_RESET_RECEIVER
                and not local_sender
            ):
                checks["role_selected_dma_reset"] = (
                    result["dma_reset_count"] > 0
                )
            if row["flags"] & FLAG_PL_RESET:
                checks["pl_reset_recorded"] = (
                    result["pl_reset_count"] > 0
                )
        else:
            checks.update(
                {
                    "accepted": (
                        result["application_bytes_accepted"] == row["size"]
                    ),
                    "committed": (
                        result["application_bytes_committed"] == row["size"]
                    ),
                    "single_atomic_commit": (
                        result["atomic_commit_count"] == 1
                    ),
                    "remote_commit": result["remote_commit_confirmed"] == 1,
                    "objects": (
                        result["objects_submitted"]
                        == result["objects_completed"]
                        == result["object_count"]
                    ),
                    "descriptors": (
                        result["descriptors_submitted"]
                        == result["descriptors_completed"]
                    ),
                }
            )
        failed = [name for name, passed in checks.items() if not passed]
        errors.extend(f"{row['label']}:{role}:{name}" for name in failed)
        result["checks"] = checks
    if row["flags"] & (FLAG_DUPLICATE_SEGMENT | FLAG_STALE_SEGMENT):
        receiver_role = "rotating" if row["direction"] == 0 else "fixed"
        receiver_result = rotating if receiver_role == "rotating" else fixed
        if receiver_result["injected_fault_observed_count"] == 0:
            errors.append(
                f"{row['label']}:{receiver_role}:injected fault not observed"
            )
    if not recovery:
        receiver = rotating if row["direction"] == 0 else fixed
        sender = fixed if row["direction"] == 0 else rotating
        sender_checks = {
            "pl_application_accepted": (
                sender["perf_application_accepted"] == row["size"]
            ),
            "local_wire_metric_consistent": (
                sender["wire_bytes"] == sender["perf_wire_bytes"]
            ),
            "pl_tx_object_packets": (
                sender["perf_descriptor_submitted"]
                == sender["object_count"]
            ),
        }
        receiver_checks = {
            "pl_application_committed": (
                receiver["perf_application_committed"] == row["size"]
            ),
            "pl_frame_acked_payload": (
                receiver["perf_frame_acked"] == row["size"]
            ),
            "local_wire_metric_consistent": (
                receiver["wire_bytes"] == receiver["perf_wire_bytes"]
            ),
            "pl_rx_object_packets": (
                receiver["perf_descriptor_completed"]
                == receiver["object_count"]
            ),
        }
        if (
            sender["perf_wire_bytes"] + receiver["perf_wire_bytes"]
            <= row["size"]
        ):
            errors.append(
                f"{row['label']}: physical wire bytes do not exceed "
                "application payload"
            )
        errors.extend(
            f"{row['label']}:sender:{name}"
            for name, passed in sender_checks.items()
            if not passed
        )
        errors.extend(
            f"{row['label']}:receiver:{name}"
            for name, passed in receiver_checks.items()
            if not passed
        )
        sender["pl_role_checks"] = sender_checks
        receiver["pl_role_checks"] = receiver_checks
        if receiver["input_crc32"] != receiver["output_crc32"]:
            errors.append(f"{row['label']}:receiver stream CRC mismatch")
        if receiver["input_sha256_words"] != receiver["output_sha256_words"]:
            errors.append(f"{row['label']}:receiver stream SHA mismatch")
        if sender["input_sha256_words"] != receiver["input_sha256_words"]:
            errors.append(f"{row['label']}:cross-board expected SHA mismatch")
        elapsed = sender["ps_elapsed_ticks"]
        frequency = sender["ps_timer_frequency_hz"]
        goodput = (
            row["size"] * 8 * frequency / elapsed
            if elapsed and frequency
            else 0.0
        )
        for timer_name, ticks_name, frequency_name in (
            ("PS", "ps_elapsed_ticks", "ps_timer_frequency_hz"),
            ("PL", "pl_elapsed_ticks", "pl_timer_frequency_hz"),
        ):
            fixed_seconds = (
                fixed[ticks_name] / fixed[frequency_name]
                if fixed[frequency_name]
                else 0.0
            )
            rotating_seconds = (
                rotating[ticks_name] / rotating[frequency_name]
                if rotating[frequency_name]
                else 0.0
            )
            maximum = max(fixed_seconds, rotating_seconds)
            error_fraction = (
                abs(fixed_seconds - rotating_seconds) / maximum
                if maximum
                else 1.0
            )
            if error_fraction > 0.01:
                errors.append(
                    f"{row['label']}:{timer_name} cross-board elapsed "
                    f"error exceeds 1%"
                )
    else:
        goodput = None
    return errors, {
        "label": row["label"],
        "direction": row["direction"],
        "lane_mask": row["lane"],
        "requested_bytes": row["size"],
        "recovery_case": recovery,
        "application_goodput_bps": goodput,
        "fixed": {key: value for key, value in fixed.items() if key != "words"},
        "rotating": {
            key: value for key, value in rotating.items() if key != "words"
        },
    }


def _marker_label(label: str) -> str:
    return label.replace(".", "_").replace("-", "_").upper()


def _window_specs(stage: str) -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for item in build_plans()[stage]:
        if not isinstance(item, tuple):
            continue
        if item[0] == "P101_WINDOW":
            specs.append(
                {
                    "label": item[1],
                    "duration_seconds": int(item[2]),
                    "direction": int(item[3]),
                    "lane_mask": int(item[4]),
                }
            )
        elif item[0] == "P101_FORMAL":
            base = item[1]
            specs.extend(
                [
                    {
                        "label": f"{base}_warmup_f2r",
                        "duration_seconds": 150,
                        "direction": 0,
                        "lane_mask": 3,
                        "formal_direction": False,
                    },
                    {
                        "label": f"{base}_warmup_r2f",
                        "duration_seconds": 150,
                        "direction": 1,
                        "lane_mask": 3,
                        "formal_direction": False,
                    },
                    {
                        "label": f"{base}_formal_f2r",
                        "duration_seconds": 750,
                        "direction": 0,
                        "lane_mask": 3,
                        "formal_direction": True,
                    },
                    {
                        "label": f"{base}_formal_r2f",
                        "duration_seconds": 750,
                        "direction": 1,
                        "lane_mask": 3,
                        "formal_direction": True,
                    },
                ]
            )
    return specs


def _aggregate_windows(
    stage: str,
    rows: list[dict[str, Any]],
    details: list[dict[str, Any]],
    markers: dict[str, str],
) -> tuple[list[str], list[dict[str, Any]]]:
    errors: list[str] = []
    by_label = {
        detail["label"]: detail
        for detail in details
        if "fixed" in detail and "rotating" in detail
    }
    aggregates: list[dict[str, Any]] = []
    for spec in _window_specs(stage):
        label = spec["label"]
        window_rows = [
            row
            for row in rows
            if row.get("window") == label and row.get("command") == 13
        ]
        key = f"P10_1_WINDOW_PASS_{_marker_label(label)}"
        marker = markers.get(key, "")
        match = re.fullmatch(r"cases:(\d+),elapsed_ms:(\d+)", marker)
        marker_cases = int(match.group(1)) if match else 0
        elapsed_ms = int(match.group(2)) if match else 0
        if not match:
            errors.append(f"{label}: bounded-window PASS marker missing")
        if marker_cases != len(window_rows) or not window_rows:
            errors.append(f"{label}: window case count mismatch")
        duration_ms = spec["duration_seconds"] * 1000
        if not duration_ms <= elapsed_ms <= duration_ms + 500:
            errors.append(f"{label}: window elapsed time is not bounded")
        committed = 0
        active_seconds = 0.0
        wall_started: list[int] = []
        wall_finished: list[int] = []
        host_commands = 0
        segments = 0
        objects = 0
        for row in window_rows:
            detail = by_label.get(row["label"])
            if detail is None:
                errors.append(f"{row['label']}: window detail missing")
                continue
            if row["direction"] != spec["direction"] or row["lane"] != spec[
                "lane_mask"
            ]:
                errors.append(f"{row['label']}: immutable window tuple mismatch")
            sender = (
                detail["fixed"]
                if spec["direction"] == 0
                else detail["rotating"]
            )
            committed += int(sender["application_bytes_committed"])
            ticks = int(sender["ps_elapsed_ticks"])
            frequency = int(sender["ps_timer_frequency_hz"])
            if ticks > 0 and frequency > 0:
                active_seconds += ticks / frequency
            host_commands += int(sender["host_command_count"])
            segments += int(sender["fast_path_segment_count"])
            objects += int(sender["objects_completed"])
            wall_started.append(int(row["started_ms"]))
            wall_finished.append(int(row["finished_ms"]))
        active_goodput = (
            committed * 8.0 / active_seconds if active_seconds > 0 else 0.0
        )
        wall_goodput = committed * 8.0 / spec["duration_seconds"]
        aggregate = {
            **spec,
            "marker": marker,
            "case_count": len(window_rows),
            "elapsed_ms": elapsed_ms,
            "committed_bytes": committed,
            "active_stream_seconds": active_seconds,
            "active_application_goodput_bps": active_goodput,
            "wall_application_goodput_bps": wall_goodput,
            "host_command_count": host_commands,
            "objects_completed": objects,
            "segments_completed": segments,
            "host_not_in_fast_path": (
                host_commands <= 20
                and segments > host_commands
                and objects >= host_commands
            ),
            "first_case_started_ms": min(wall_started)
            if wall_started
            else None,
            "last_case_finished_ms": max(wall_finished)
            if wall_finished
            else None,
        }
        if not aggregate["host_not_in_fast_path"]:
            errors.append(f"{label}: host fast-path exclusion failed")
        aggregates.append(aggregate)
    return errors, aggregates


def _validate_stage_semantics(
    stage: str,
    rows: list[dict[str, Any]],
    details: list[dict[str, Any]],
    raw_matrix: list[dict[str, Any]],
    markers: dict[str, str],
) -> tuple[list[str], dict[str, Any]]:
    errors, windows = _aggregate_windows(
        stage, rows, details, markers
    )
    semantics: dict[str, Any] = {"windows": windows}
    if stage == "preflight":
        semantics["diagnostic_only_labels"] = ["diagnostic_only_1byte"]
        semantics["diagnostic_eligible_for_scaling"] = False
        if not any(
            detail.get("label") == "failed_object_diagnostic"
            and detail.get("recovery_case")
            for detail in details
        ):
            errors.append("failed-object metric vector missing")
    elif stage == "baseline":
        by_label = {item["label"]: item for item in windows}
        scaling: dict[str, float] = {}
        for direction, direction_name in ((0, "f_to_r"), (1, "r_to_f")):
            singles = [
                item["wall_application_goodput_bps"]
                for item in windows
                if item["direction"] == direction and item["lane_mask"] in {1, 2}
            ]
            two = by_label[
                f"baseline_two_lane_{direction_name}_60s"
            ]["wall_application_goodput_bps"]
            ratio = two / (sum(singles) / len(singles)) if singles else 0.0
            scaling[direction_name] = ratio
            if ratio < 1.6:
                errors.append(
                    f"baseline {direction_name} two-lane scaling {ratio:.6f} < 1.6"
                )
        semantics["two_lane_scaling"] = scaling
    elif stage == "tuning":
        candidates = [
            item
            for item in details
            if not item.get("recovery_case")
            and item.get("application_goodput_bps") is not None
        ]
        if not candidates:
            errors.append("adaptive tuning produced no valid candidate")
        else:
            for item in candidates:
                sender = (
                    item["fixed"]
                    if item["direction"] == 0
                    else item["rotating"]
                )
                elapsed_seconds = (
                    sender["ps_elapsed_ticks"]
                    / sender["ps_timer_frequency_hz"]
                    if sender["ps_timer_frequency_hz"]
                    else float("inf")
                )
                if elapsed_seconds > 30.0:
                    errors.append(
                        f"{item['label']}: tuning active time exceeds 30 seconds"
                    )
            best = max(
                candidates, key=lambda item: item["application_goodput_bps"]
            )
            semantics["best_candidate"] = {
                "label": best["label"],
                "application_goodput_bps": best[
                    "application_goodput_bps"
                ],
                "buffer_count": best["fixed"]["buffer_count"],
                "ring_depth": best["fixed"]["ring_depth"],
                "descriptor_batch": best["fixed"]["descriptor_batch"],
                "ack_threshold": best["fixed"]["ack_threshold"],
                "outstanding_frames": best["fixed"][
                    "outstanding_frames"
                ],
            }
            semantics["candidate_count"] = len(candidates)
            if len(candidates) > 12:
                errors.append("adaptive tuning exceeded 12 cases")
    elif stage == "faults":
        recovery_details = [
            item for item in details if item.get("recovery_case")
        ]
        clean_details = [
            item for item in details if not item.get("recovery_case")
        ]
        expected_recovery = sum(
            1
            for item in build_plans()["faults"]
            if (
                isinstance(item, Case)
                and (item.flags & RECOVERY_FLAGS) != 0
            )
            or (
                isinstance(item, tuple)
                and item[0] == "P101_PSRESET"
            )
        )
        if len(recovery_details) != expected_recovery:
            errors.append("fault/recovery vector count mismatch")
        if len(clean_details) != expected_recovery:
            errors.append("post-recovery clean-vector count mismatch")
        semantics["recovery_vector_count"] = len(recovery_details)
        semantics["post_recovery_clean_count"] = len(clean_details)
    elif stage in {"half_duplex", "formal"}:
        qualifying = [
            item
            for item in windows
            if stage == "half_duplex" or item.get("formal_direction")
        ]
        for item in qualifying:
            if stage == "half_duplex":
                if item["duration_seconds"] < 300:
                    errors.append(
                        f"{item['label']}: duration is below 300 seconds"
                    )
                if item["committed_bytes"] < 150 * 1024 * 1024:
                    errors.append(
                        f"{item['label']}: committed bytes are below 150 MiB"
                    )
            if item["wall_application_goodput_bps"] < 4_000_000:
                errors.append(
                    f"{item['label']}: wall application goodput below 4 Mbit/s"
                )
            if item["active_application_goodput_bps"] < 4_000_000:
                errors.append(
                    f"{item['label']}: active application goodput below 4 Mbit/s"
                )
        semantics["directions"] = qualifying
        if stage == "formal":
            try:
                elapsed = int(markers["P10_1_FORMAL_ELAPSED_MS"])
            except (KeyError, ValueError):
                elapsed = 0
            semantics["formal_elapsed_ms"] = elapsed
            if (
                markers.get("P10_1_FORMAL_RESULT") != "PASS"
                or not 1_800_000 <= elapsed <= 1_800_500
            ):
                errors.append("formal 1800-second marker invalid")
    elif stage == "crosstalk":
        if len(raw_matrix) != 8:
            errors.append("raw 64/1024-pulse 4x4 matrix is incomplete")
        frames: list[dict[str, Any]] = []
        for item in windows:
            matching = [
                detail
                for detail in details
                if detail["label"].startswith(item["label"] + "_")
            ]
            for detail in matching:
                receiver = (
                    detail["rotating"]
                    if item["direction"] == 0
                    else detail["fixed"]
                )
                sender = (
                    detail["fixed"]
                    if item["direction"] == 0
                    else detail["rotating"]
                )
                target_lane = 0 if item["lane_mask"] == 1 else 1
                target_valid = receiver[
                    "physical_data_good_by_lane_after"
                ][target_lane]
                non_target_valid = (
                    sum(receiver["physical_data_good_by_lane_after"])
                    - target_valid
                    + sum(sender["physical_data_good_by_lane_after"])
                )
                frames.append(
                    {
                        "label": detail["label"],
                        "target_valid_frames": target_valid,
                        "non_target_crc_valid_frames": non_target_valid,
                    }
                )
                if target_valid == 0:
                    errors.append(f"{detail['label']}: target frame missing")
                if non_target_valid != 0:
                    errors.append(
                        f"{detail['label']}: non-target CRC-valid false frame"
                    )
        semantics["frame_matrix"] = frames
    elif stage == "oneplusone":
        outcome = markers.get("P10_1_1PLUS1_OUTCOME")
        reason = markers.get("P10_1_1PLUS1_REASON")
        semantics["outcome"] = outcome
        semantics["reason"] = reason
        if outcome != "SKIP_WITH_REASON" or not reason:
            errors.append("1+1 nonblocking outcome is not explicit")
    return errors, semantics


def evaluate_stage(
    stage: str, stage_dir: Path, process: dict[str, Any]
) -> dict[str, Any]:
    markers = parse_markers(stage_dir / "xsdb.result.txt")
    observation = stage_dir / "dumps/observations.psv"
    errors: list[str] = []
    details: list[dict[str, Any]] = []
    raw_matrix: list[dict[str, Any]] = []
    if process["returncode"] != 0 or process["timed_out"]:
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS":
        errors.append("XSDB PASS marker missing")
    if markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("safe-boot marker missing")
    rows: list[dict[str, Any]] = []
    if observation.is_file():
        with observation.open(encoding="utf-8", newline="") as handle:
            rows = [_integer_row(row) for row in csv.DictReader(handle, delimiter="|")]
    else:
        errors.append("observation ledger missing")
    plan = build_plans()[stage]
    static_labels = [
        item.label
        for item in plan
        if isinstance(item, Case)
    ] + [
        item[1]
        for item in plan
        if isinstance(item, tuple) and item[0] == "P101_PSRESET"
    ]
    dynamic_minimum = len(_window_specs(stage))
    expected_minimum = len(static_labels) + dynamic_minimum + 1
    if len(rows) < expected_minimum:
        errors.append(
            f"observation count {len(rows)} is below minimum {expected_minimum}"
        )
    observed_labels = {row.get("label") for row in rows}
    for label in static_labels:
        if label not in observed_labels:
            errors.append(f"immutable plan case missing: {label}")
    shutdown_rows = [
        row for row in rows if row["label"].endswith("_endpoint_shutdown")
    ]
    if (
        len(shutdown_rows) != 1
        or not rows
        or rows[-1] is not shutdown_rows[0]
    ):
        errors.append("exactly one final endpoint shutdown row is required")
    for row in rows:
        if row["label"].endswith("_endpoint_shutdown"):
            continue
        try:
            if row["command"] == 13:
                fixed_path = Path(row["fixed_p10_1_dump_path"]).resolve()
                rotating_path = Path(
                    row["rotating_p10_1_dump_path"]
                ).resolve()
                if not inside(fixed_path, stage_dir) or not inside(
                    rotating_path, stage_dir
                ):
                    raise ValueError("P10.1 dump escaped stage directory")
                pair_errors, detail = evaluate_p101_pair(
                    row, parse_p101(fixed_path), parse_p101(rotating_path)
                )
                errors.extend(pair_errors)
                details.append(detail)
            else:
                fixed_path = Path(row["fixed_dump_path"]).resolve()
                rotating_path = Path(row["rotating_dump_path"]).resolve()
                if not inside(fixed_path, stage_dir) or not inside(
                    rotating_path, stage_dir
                ):
                    raise ValueError("mailbox dump escaped stage directory")
                pair_errors, detail = evaluate_pair(
                    row, parse_mailbox(fixed_path), parse_mailbox(rotating_path)
                )
                if stage == "crosstalk" and row["command"] == 2:
                    pair_errors = [
                        item
                        for item in pair_errors
                        if not item.endswith(
                            ": destination off-lane crosstalk"
                        )
                    ]
                errors.extend(pair_errors)
                details.append(detail)
                if "raw_matrix" in detail:
                    raw_matrix.append(
                        {"label": row["label"], **detail["raw_matrix"]}
                    )
        except (OSError, ValueError, KeyError, struct.error) as exc:
            errors.append(f"{row.get('label', 'unknown')}: {exc}")
    semantic_errors, semantics = _validate_stage_semantics(
        stage, rows, details, raw_matrix, markers
    )
    errors.extend(semantic_errors)
    summary = {
        "schema_version": 1,
        "test_id": f"P10_1-HW-{stage.upper()}",
        "stage": stage,
        "status": "PASS" if not errors else "FAIL",
        "process": process,
        "markers": markers,
        "observation_count": len(rows),
        "details": details,
        "raw_matrix": raw_matrix,
        "semantics": semantics,
        "errors": errors,
    }
    write_json(stage_dir / "stage_summary.json", summary)
    return summary


def invoke_stage(
    stage: str,
    run_root: Path,
    auth: Path,
    artifacts: dict[str, Path],
    ps7: dict[str, Path],
    env: dict[str, str],
    abort_file: Path,
) -> dict[str, Any]:
    stage_dir = run_root / "stages" / stage
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    plan = stage_dir / f"{stage}.plan"
    write_text(plan, plan_text(build_plans()[stage]))
    result_file = stage_dir / "xsdb.result.txt"
    command = [
        str(XSDB),
        str(STAGE_TCL),
        "tcp:localhost:3121",
        EXPECTED_FIXED_SERIAL,
        EXPECTED_ROTATING_SERIAL,
        str(artifacts["fixed:functional_bitstream"]),
        str(artifacts["rotating:functional_bitstream"]),
        str(artifacts["fixed:elf"]),
        str(artifacts["rotating:elf"]),
        str(ps7["fixed"]),
        str(ps7["rotating"]),
        str(plan),
        str(dump_dir),
        str(abort_file),
        str(result_file),
        "P10-DIAG",
        str(auth),
        run_root.name,
    ]
    timeout = {
        "preflight": 1800,
        "smoke": 900,
        "baseline": 1200,
        "tuning": 1200,
        "pipeline": 1200,
        "streaming": 1500,
        "faults": 7200,
        "crosstalk": 1800,
        "half_duplex": 1800,
        "oneplusone": 900,
        "formal": 2400,
    }[stage]
    process = run_bounded(
        command,
        stage_dir / "xsdb.stdout.log",
        stage_dir / "xsdb.stderr.log",
        timeout,
        env,
    )
    return evaluate_stage(stage, stage_dir, process)


def evidence_manifest(run_root: Path) -> dict[str, Any]:
    output = run_root / "final/run_evidence_sha256_manifest.json"
    files = []
    for path in sorted(item for item in run_root.rglob("*") if item.is_file()):
        if path == output:
            continue
        files.append(
            {
                "path": path.relative_to(run_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    payload = {
        "schema_version": 1,
        "test_id": "P10_1-HW-EVIDENCE-MANIFEST",
        "status": "PASS",
        "run_id": run_root.name,
        "files": files,
        "generated_at_utc": utc_now(),
    }
    write_json(output, payload)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument(
        "--stage",
        action="append",
        choices=tuple(build_plans()),
        required=True,
    )
    parser.add_argument("--authorize-from", type=Path, default=AUTH_PATH)
    parser.add_argument("--prepare-authorization", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    stages = list(dict.fromkeys(args.stage))
    if args.prepare_authorization:
        try:
            record = create_authorization(args.run_id, stages)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            print(f"P10_1_AUTHORIZATION=FAIL\nERROR={exc}", file=sys.stderr)
            return 1
        print("P10_1_AUTHORIZATION=PASS")
        print(f"P10_1_AUTHORIZATION_PATH={rel(AUTH_PATH)}")
        print(f"P10_1_AUTHORIZATION_SHA256={sha256(AUTH_PATH)}")
        if args.json_summary:
            print(json.dumps(record, sort_keys=True))
        return 0

    auth = args.authorize_from.resolve()
    record, artifacts, errors = validate_authorization(
        auth, args.run_id, stages
    )
    run_root = HW_ROOT / (
        args.run_id if RUN_RE.fullmatch(args.run_id) else "invalid_run_id"
    )
    if run_root.exists() and any(run_root.iterdir()):
        errors.append("run directory already exists and is nonempty")
    for directory in (
        "authorization",
        "artifacts",
        "stages",
        "shutdown",
        "raw_logs",
        "final",
    ):
        (run_root / directory).mkdir(parents=True, exist_ok=True)
    auth_record = {
        "schema_version": 1,
        "test_id": "P10_1-HW-CURRENT-RUN-AUTHORIZATION",
        "status": "PASS" if not errors else "FAIL",
        "run_id": args.run_id,
        "authorization": str(auth),
        "authorization_sha256": sha256(auth) if auth.is_file() else None,
        "source_commit": record.get("source_commit"),
        "goal_sha256": record.get("goal_sha256"),
        "board_identities": record.get("board_identities"),
        "maximum_single_formal_run_seconds": record.get(
            "maximum_single_formal_run_seconds"
        ),
        "shutdown": record.get("shutdown"),
        "errors": errors,
        "hardware_actions_executed": False,
    }
    write_json(
        run_root / "authorization/authorization_record.json", auth_record
    )
    if auth.is_file():
        shutil.copy2(
            auth, run_root / "authorization/immutable_authorization.json"
        )
    if errors or args.dry_run or not args.execute_hardware:
        status = "PASS" if args.dry_run and not errors else "FAIL"
        summary = {
            **auth_record,
            "status": status,
            "dry_run": True,
            "hardware_actions_executed": False,
        }
        write_json(run_root / "final/orchestrator_result.json", summary)
        print(f"P10_1_HARDWARE_DRY_RUN={status}")
        return 0 if status == "PASS" else 1
    if (
        os.environ.get("NO_HARDWARE", "1") != "0"
        or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
        ).lower()
        != "true"
    ):
        print("P10.1 hardware environment gates are closed", file=sys.stderr)
        return 1

    ps7: dict[str, Path] = {}
    try:
        for role in ("fixed", "rotating"):
            destination = run_root / "artifacts" / role / "ps7_init.tcl"
            extract_ps7_init(artifacts[f"{role}:xsa"], destination)
            ps7[role] = destination
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        auth_record["errors"].append(f"PS7 init extraction failed: {exc}")
        write_json(
            run_root / "authorization/authorization_record.json", auth_record
        )
        return 1

    env = os.environ.copy()
    env["RF_COMM_P10_HW_AUTH"] = "P10_FASTTRACK_IMMUTABLE_AUTHORIZED"
    abort_file = run_root / "authorization/ABORT_NOW.txt"
    server_proc: subprocess.Popen[Any] | None = None
    shutdowns: list[dict[str, Any]] = []
    stage_results: dict[str, dict[str, Any]] = {}
    campaign_errors: list[str] = []
    hardware_actions = False
    try:
        server_proc, server = start_hw_server(run_root / "raw_logs")
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server["status"] != "PASS":
            raise RuntimeError(server.get("reason", "hw_server failed"))
        hardware_actions = True
        initial = invoke_shutdown(
            run_root, auth, artifacts, "initial_shutdown", env
        )
        shutdowns.append(initial)
        if initial["status"] != "PASS":
            raise RuntimeError("initial shutdown unconfirmed")
        for stage in stages:
            before = invoke_shutdown(
                run_root, auth, artifacts, f"{stage}_before", env
            )
            shutdowns.append(before)
            if before["status"] != "PASS":
                raise RuntimeError(f"{stage} shutdown-before unconfirmed")
            result: dict[str, Any] = {"status": "FAIL"}
            after: dict[str, Any]
            try:
                result = invoke_stage(
                    stage,
                    run_root,
                    auth,
                    artifacts,
                    ps7,
                    env,
                    abort_file,
                )
                stage_results[stage] = result
            finally:
                after = invoke_shutdown(
                    run_root, auth, artifacts, f"{stage}_after", env
                )
                shutdowns.append(after)
            if result.get("status") != "PASS":
                raise RuntimeError(f"{stage} validation failed")
            if after.get("status") != "PASS":
                raise RuntimeError(f"{stage} shutdown-after unconfirmed")
        final_shutdown = invoke_shutdown(
            run_root, auth, artifacts, "final_shutdown", env
        )
        shutdowns.append(final_shutdown)
        if final_shutdown["status"] != "PASS":
            raise RuntimeError("final shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except BaseException as exc:
        campaign_errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        emergency = invoke_shutdown(
            run_root, auth, artifacts, "finally_emergency", env
        )
        shutdowns.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally shutdown unconfirmed")
        if server_proc is not None:
            terminate_tree(server_proc)

    shutdown_fixed = (
        "PASS"
        if shutdowns
        and all(item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdowns)
        else "FAIL"
    )
    shutdown_rotating = (
        "PASS"
        if shutdowns
        and all(item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdowns)
        else "FAIL"
    )
    status = (
        "PASS"
        if not campaign_errors
        and all(
            stage_results.get(stage, {}).get("status") == "PASS"
            for stage in stages
        )
        and shutdown_fixed == shutdown_rotating == "PASS"
        else "FAIL"
    )
    summary = {
        "schema_version": 1,
        "test_id": "P10_1-HW-ORCHESTRATOR",
        "status": status,
        "run_id": args.run_id,
        "source_commit": record.get("source_commit"),
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": hardware_actions,
        "network_used": False,
        "ethernet_used": False,
        "hardware_movement": False,
        "rotation_executed": False,
        "rewiring_executed": False,
        "maximum_lane_mask_used": "0x3",
        "stages": {
            stage: stage_results.get(stage, {}).get("status", "NOT_RUN")
            for stage in stages
        },
        "stage_results": stage_results,
        "shutdowns": shutdowns,
        "SHUTDOWN_FIXED": shutdown_fixed,
        "SHUTDOWN_ROTATING": shutdown_rotating,
        "errors": campaign_errors,
        "generated_at_utc": utc_now(),
    }
    summary["evidence_manifest"] = rel(
        run_root / "final/run_evidence_sha256_manifest.json"
    )
    summary["evidence_file_count"] = sum(
        1
        for path in run_root.rglob("*")
        if path.is_file()
        and path
        != run_root / "final/run_evidence_sha256_manifest.json"
    ) + 1
    write_json(run_root / "final/orchestrator_result.json", summary)
    manifest = evidence_manifest(run_root)
    if len(manifest["files"]) != summary["evidence_file_count"]:
        summary["status"] = "FAIL"
        summary["errors"].append("evidence manifest file count mismatch")
        status = "FAIL"
        write_json(run_root / "final/orchestrator_result.json", summary)
        manifest = evidence_manifest(run_root)
    write_json(GENERATED / "p10_1_hw_latest_run_summary.json", summary)
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"P10_1_HARDWARE_STATUS={status}")
        print(f"P10_1_RUN_ID={args.run_id}")
        print(f"SHUTDOWN_FIXED={shutdown_fixed}")
        print(f"SHUTDOWN_ROTATING={shutdown_rotating}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
