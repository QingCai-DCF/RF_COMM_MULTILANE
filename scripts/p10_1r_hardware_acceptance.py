#!/usr/bin/env python3
"""Fail-closed P10.1R stationary two-lane hardware orchestrator.

The script is inert unless a run-bound authorization has first been generated
from a clean worktree, committed as the only file in its commit, and then
supplied with both explicit hardware environment gates.  Every selected stage
is bracketed by independently programming the two role-bound shutdown images.
The same shutdown is attempted after success, failure, timeout, Ctrl+C, and in
the outer finally path.

No Ethernet, motion, rewiring, module exchange, power cycling, SPI, 1+1 full
duplex, P11, or lane mask above 0x3 is implemented here.
"""

from __future__ import annotations

import argparse
import copy
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
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import p10_1_hardware_acceptance as p101
from p10_hardware_runtime import (
    Case,
    EXPECTED_FIXED_SERIAL,
    EXPECTED_FIXED_TARGET,
    EXPECTED_PART,
    EXPECTED_ROTATING_SERIAL,
    EXPECTED_ROTATING_TARGET,
    XSDB,
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
GOAL = ROOT / "goals/P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION_GOAL.md"
EXPECTED_GOAL_SHA256 = (
    "299e9b04b824f6bcf77b51398e87a2b7dc19272bcc245ef968fc7cdf0e57b35f"
)
EXPECTED_BRANCH = "p10.1r/2lane-speed-stability-remediation"
EXPECTED_SCOPE = "P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION"
STANDING_AUTHORIZATION_SOURCES = (
    {
        "source_thread_id": "019fc130-82cb-7653-bda1-69a0ccfee3fd",
        "received_on": "2026-08-02",
        "source_kind": "codex_delegation_from_user_side_conversation",
        "user_quotes": [
            "我想一次性授权之后全部需要的操作",
            "我确认，帮我告诉主线程",
        ],
        "scope": EXPECTED_SCOPE,
        "campaign_level_standing_authorization": True,
        "artifact_bundle_iteration_authorized": True,
    },
    {
        "source_thread_id": "019fbafb-34a3-7223-95dc-7b3982218221",
        "received_on": "2026-08-01",
        "source_kind": "codex_delegation_from_user_side_conversation",
        "user_quotes": ["不设上限"],
        "scope": EXPECTED_SCOPE,
        "campaign_new_run_id_limit": None,
    },
)
EXPECTED_BASE_FAILURE_TAG = "p10.1-hardware-performance-fail-20260801"
EXPECTED_BASE_FAILURE_COMMIT = "991cc8a6cc5fd656178f9a3ddd9bb7c2f9c84151"
ARTIFACT_FREEZE = ROOT / "evidence/generated/p10_1r_artifact_freeze.json"
EXPECTED_ARTIFACT_FREEZE_SHA256 = (
    "aededfa8ada3171351ca073ba7616a57688e6e184bdc8a5af6a873352cf8d4bc"
)
EXPECTED_ARTIFACT_PURPOSE = "FINAL_ACCEPTANCE"
EXPECTED_ACCEPTANCE_ELIGIBLE = True
EXPECTED_ALLOWED_HARDWARE_STAGES: tuple[str, ...] = (
    "preflight",
    "echo_tail",
    "crosstalk",
    "phy_sanity",
    "ack_tuning",
    "performance",
    "streaming_64m",
    "formal_30min",
)
AUTH_PATH = ROOT / "config/p10_1r_current_run_hardware_authorization.json"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
SHUTDOWN_TCL = ROOT / "scripts/hw/p10_program_dual_shutdown.tcl"
HW_ROOT = ROOT / "evidence/hardware/p10_1r"
GENERATED = ROOT / "evidence/generated"

RUN_RE = re.compile(
    r"^p10_1r_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}_[0-9a-f]{8}_[0-9a-f]{8}$"
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
STAGES = (
    "preflight",
    "echo_tail",
    "crosstalk",
    "phy_sanity",
    "ack_tuning",
    "performance",
    "streaming_64m",
    "formal_30min",
)
TCL_STAGE = {
    stage: f"P10_1R-{stage.upper()}" for stage in STAGES
}
STAGE_DIRECTORY = {
    "preflight": "safe_boot",
    "echo_tail": "echo_tail",
    "crosstalk": "crosstalk_remediation",
    "phy_sanity": "phy_sanity",
    "ack_tuning": "ack_tuning",
    "performance": "sustained_performance",
    "streaming_64m": "streaming_64m",
    "formal_30min": "formal_30min",
}

FLAG_ABORT_50 = 1 << 25
# P10.1's parser/evaluator is intentionally reused.  P10.1R adds one recovery
# flag while preserving the result schema, so extend only the in-process mask.
p101.RECOVERY_FLAGS |= FLAG_ABORT_50

OBJECT_BYTES = 256 * 1024
DESCRIPTOR_BYTES = 64 * 1024
BUFFER_COUNT = 4
RING_DEPTH = 32
DESCRIPTOR_BATCH = 8
ACK_THRESHOLD = 32
OUTSTANDING_FRAMES = 32
GUARD_MARGIN_CYCLES = 4096
EXPECTED_ADMISSION_CAPS = 0x52310101
EXPECTED_GUARD_CYCLES = 4096
EXPECTED_IDLE_QUALIFY_CYCLES = 256
EXPECTED_MAX_QUARANTINE_CYCLES = 131072
EXPECTED_IDLE_LOW_CYCLES = 4
EXPECTED_IDLE_HIGH_CYCLES = 3
EXPECTED_PL_BUILD_IDS = {
    "fixed": 0x50325346,
    "rotating": 0x50325352,
}
EXPECTED_ROLE_IDENTITIES = {
    "fixed": {
        "firmware": 0x50313046,
        "build": EXPECTED_PL_BUILD_IDS["fixed"],
        "profile": 0x702000F0,
        "local_indices": (0, 1),
    },
    "rotating": {
        "firmware": 0x50313052,
        "build": EXPECTED_PL_BUILD_IDS["rotating"],
        "profile": 0x702000A0,
        "local_indices": (2, 3),
    },
}

HASHED_INPUTS = {
    "goal": GOAL,
    "project_constraints": ROOT / "PROJECT_CONSTRAINTS.txt",
    "requirements": ROOT / "config/project_requirements.yaml",
    "project_state": ROOT / "config/project_state.json",
    "register_map": ROOT / "config/register_map/ir_axi_regs.yaml",
    "register_map_manifest": (
        ROOT / "config/register_map/generated/ir_regs_manifest.json"
    ),
    "runtime": ROOT / "config/performance/p10_1r_hardware_runtime.yaml",
    "rx_admission": ROOT / "config/tfdu_rx_admission.yaml",
    "measurement_contract": (
        ROOT / "docs/hardware/P10_1R_HARDWARE_MEASUREMENT_CONTRACT.md"
    ),
    "active_wiring": ROOT / "config/hardware/p10_active_wiring.yaml",
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
    "artifact_freeze": ARTIFACT_FREEZE,
    "runner": Path(__file__).resolve(),
    "p101_evaluator": ROOT / "scripts/p10_1_hardware_acceptance.py",
    "runtime_helpers": ROOT / "scripts/p10_hardware_runtime.py",
    "xsdb_stage": STAGE_TCL,
    "shutdown_stage": SHUTDOWN_TCL,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
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


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def hash_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def hash_inputs() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for name, path in HASHED_INPUTS.items():
        if not path.is_file():
            raise FileNotFoundError(path)
        result[name] = {
            "path": rel(path),
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
    return result


def p101_case(
    label: str,
    *,
    size: int,
    direction: int,
    lane: int = 3,
    object_id: int,
    timeout: int = 600_000,
    flags: int = 0,
) -> Case:
    object_bytes = min(size, OBJECT_BYTES)
    descriptor_bytes = min(object_bytes, DESCRIPTOR_BYTES)
    descriptor_bytes &= ~3
    if descriptor_bytes == 0:
        descriptor_bytes = 4
    return Case(
        label=label,
        command=13,
        flags=flags,
        lane=lane,
        direction=direction,
        rate=2,
        weights=0x0101,
        size=size,
        ring=RING_DEPTH,
        cache=1,
        timeout=timeout,
        session=0xA1010001,
        path=0x101,
        object=object_id,
        dropdata=ACK_THRESHOLD,
        dropack=OUTSTANDING_FRAMES,
        rawtarget=object_bytes,
        spacing=descriptor_bytes,
        stale=BUFFER_COUNT,
        initialseq=DESCRIPTOR_BATCH,
    )


def build_plans() -> dict[str, list[Case | tuple[str, ...]]]:
    plans: dict[str, list[Case | tuple[str, ...]]] = {}
    plans["preflight"] = [
        Case("p10_1r_identity", 1),
        Case("p10_1r_receive_only_5000ms", 11, idle=5000, timeout=15_000),
        Case("p10_1r_ring32", 4, ring=32),
        Case("p10_1r_dma_reset_idle", 5, ring=32),
        Case("p10_1r_pl_soft_reset", 8),
        Case("p10_1r_identity_after_reset", 1),
    ]
    plans["echo_tail"] = [
        ("P101R_ECHO_SWEEP", "echo_F0", "0", "1", "1000", "1024"),
        ("P101R_ECHO_SWEEP", "echo_F1", "0", "2", "1000", "1024"),
        ("P101R_ECHO_SWEEP", "echo_R0", "1", "1", "1000", "1024"),
        ("P101R_ECHO_SWEEP", "echo_R1", "1", "2", "1000", "1024"),
    ]
    crosstalk: list[Case | tuple[str, ...]] = []
    for lane, lane_name in ((1, "lane0"), (2, "lane1")):
        for direction, direction_name in ((0, "f2r"), (1, "r2f")):
            for count in (64, 1024):
                crosstalk.append(
                    Case(
                        f"remediation_raw_{lane_name}_{direction_name}_{count}",
                        2,
                        lane=lane,
                        direction=direction,
                        rate=2,
                        rawtarget=count,
                        spacing=1024,
                        timeout=30_000,
                    )
                )
            crosstalk.append(
                (
                    "P101_WINDOW",
                    f"remediation_frame_{lane_name}_{direction_name}",
                    "10",
                    str(direction),
                    str(lane),
                    "1048576",
                )
            )
    plans["crosstalk"] = crosstalk
    plans["phy_sanity"] = [
        p101_case(
            f"phy_4mbps_{lane_name}_{direction_name}_1000f",
            size=247 * 1000,
            direction=direction,
            lane=lane,
            object_id=0x71000000 + lane * 0x100 + direction,
            timeout=120_000,
            flags=((lane + direction) % 5) << 8,
        )
        for lane, lane_name in ((1, "lane0"), (2, "lane1"))
        for direction, direction_name in ((0, "f2r"), (1, "r2f"))
    ]
    plans["ack_tuning"] = [
        (
            "P101R_TIMED_CASE", "ack32_burst32_f2r", "30", "0", "3",
            "15000000", "1895825408",
        ),
        (
            "P101R_TIMED_CASE", "ack32_burst32_r2f", "30", "1", "3",
            "15000000", "1895825409",
        ),
    ]
    plans["performance"] = [
        ("P101_WINDOW", "sustained_300s_f2r", "300", "0", "3", "67108864"),
        ("P101_WINDOW", "sustained_300s_r2f", "300", "1", "3", "67108864"),
    ]
    stream: list[Case | tuple[str, ...]] = []
    oid = 0x72000000
    for direction, name in ((0, "f2r"), (1, "r2f")):
        for index in range(5):
            stream.append(
                p101_case(
                    f"stream64_{name}_{index + 1}",
                    size=64 * 1024 * 1024,
                    direction=direction,
                    object_id=oid,
                    flags=(index % 5) << 8,
                )
            )
            oid += 1
    stream.extend(
        [
            p101_case(
                "stream_abort50_f2r",
                size=64 * 1024 * 1024,
                direction=0,
                object_id=oid,
                flags=FLAG_ABORT_50,
            ),
            p101_case(
                "stream_clean_after_abort50_f2r",
                size=64 * 1024 * 1024,
                direction=0,
                object_id=oid + 1,
            ),
            (
                "P101_PSRESET",
                "stream_service_reset_receiver",
                "rotating",
                "0",
                "3",
                str(64 * 1024 * 1024),
                str(oid + 2),
            ),
            p101_case(
                "stream_clean_after_service_reset_f2r",
                size=64 * 1024 * 1024,
                direction=0,
                object_id=oid + 3,
            ),
            p101_case(
                "stream_dma_reset_sender_r2f",
                size=64 * 1024 * 1024,
                direction=1,
                object_id=oid + 4,
                flags=p101.FLAG_DMA_RESET_SENDER,
            ),
            p101_case(
                "stream_clean_after_dma_reset_r2f",
                size=64 * 1024 * 1024,
                direction=1,
                object_id=oid + 5,
            ),
        ]
    )
    plans["streaming_64m"] = stream
    plans["formal_30min"] = [
        ("P101_FORMAL", "stationary_30min", "1800")
    ]
    return plans


def plan_hashes(stages: Iterable[str]) -> dict[str, str]:
    plans = build_plans()
    return {stage: hash_text(plan_text(plans[stage])) for stage in stages}


def load_freeze() -> tuple[dict[str, Any], dict[str, Path]]:
    if sha256(ARTIFACT_FREEZE) != EXPECTED_ARTIFACT_FREEZE_SHA256:
        raise RuntimeError("P10.1R artifact-freeze SHA256 mismatch")
    record = json.loads(ARTIFACT_FREEZE.read_text(encoding="utf-8"))
    if record.get("status") != "PASS" or record.get("no_hardware") is not True:
        raise RuntimeError("P10.1R artifact freeze is not an offline PASS")
    if (
        record.get("purpose") != EXPECTED_ARTIFACT_PURPOSE
        or record.get("acceptance_eligible") is not EXPECTED_ACCEPTANCE_ELIGIBLE
        or tuple(record.get("allowed_hardware_stages", ()))
        != EXPECTED_ALLOWED_HARDWARE_STAGES
    ):
        raise RuntimeError("P10.1R artifact-bundle scope mismatch")
    if record.get("goal", {}).get("sha256") != EXPECTED_GOAL_SHA256:
        raise RuntimeError("artifact freeze Goal binding mismatch")
    for item in record.get("inputs", []):
        path = (ROOT / item["path"]).resolve()
        if (
            not inside(path, ROOT)
            or not path.is_file()
            or path.stat().st_size != int(item["bytes"])
            or sha256(path) != item["sha256"]
        ):
            raise RuntimeError(f"artifact-freeze input mismatch: {item['path']}")
    artifacts: dict[str, Path] = {}
    kind_map = {
        "bitstream": "functional_bitstream",
        "shutdown_bitstream": "shutdown_bitstream",
        "xsa": "xsa",
        "bsp": "bsp",
        "elf": "elf",
    }
    for role in ("fixed", "rotating"):
        for freeze_kind, runtime_kind in kind_map.items():
            item = record["roles"][role][freeze_kind]
            path = (ROOT / item["path"]).resolve()
            key = f"{role}:{runtime_kind}"
            built_source = item.get("built_source_commit", "")
            if not inside(path, ROOT / "artifacts/p10_1r"):
                raise RuntimeError(f"{key} escaped P10.1R content store")
            if (
                not re.fullmatch(r"[0-9a-f]{40}", built_source)
                or built_source not in path.parts
                or subprocess.run(
                    ["git", "merge-base", "--is-ancestor", built_source, "HEAD"],
                    cwd=ROOT,
                    capture_output=True,
                ).returncode
            ):
                raise RuntimeError(f"{key} build provenance mismatch")
            if (
                not path.is_file()
                or path.stat().st_size != int(item["bytes"])
                or sha256(path) != item["sha256"]
                or not SHA_RE.fullmatch(item["sha256"])
            ):
                raise RuntimeError(f"{key} hash/size mismatch")
            artifacts[key] = path
    return record, artifacts


def artifact_records(freeze: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for role in ("fixed", "rotating"):
        for kind in ("bitstream", "shutdown_bitstream", "xsa", "bsp", "elf"):
            item = freeze["roles"][role][kind]
            records.append(
                {
                    "role": role,
                    "kind": "functional_bitstream" if kind == "bitstream" else kind,
                    "path": item["path"],
                    "sha256": item["sha256"],
                    "bytes": item["bytes"],
                    "built_source_commit": item["built_source_commit"],
                }
            )
    return records


def expected_run_id(freeze: dict[str, Any], prefix: str) -> str:
    fixed = freeze["roles"]["fixed"]["bitstream"]["sha256"][:8]
    rotating = freeze["roles"]["rotating"]["bitstream"]["sha256"][:8]
    return f"p10_1r_{prefix}_{freeze['source_commit'][:8]}_{fixed}_{rotating}"


def create_authorization(run_id: str, stages: list[str]) -> dict[str, Any]:
    if not RUN_RE.fullmatch(run_id):
        raise ValueError("invalid content-bound P10.1R run_id")
    if not stages or any(stage not in STAGES for stage in stages):
        raise ValueError("invalid P10.1R stage set")
    if git("branch", "--show-current") != EXPECTED_BRANCH:
        raise RuntimeError("wrong P10.1R branch")
    if git("status", "--porcelain"):
        raise RuntimeError("authorization generation requires a clean worktree")
    if sha256(GOAL) != EXPECTED_GOAL_SHA256:
        raise RuntimeError("live P10.1R Goal hash mismatch")
    if git("rev-list", "-n", "1", EXPECTED_BASE_FAILURE_TAG) != EXPECTED_BASE_FAILURE_COMMIT:
        raise RuntimeError("immutable base failure tag mismatch")
    freeze, _ = load_freeze()
    allowed_stages = freeze["allowed_hardware_stages"]
    if any(stage not in allowed_stages for stage in stages):
        raise RuntimeError("requested stage exceeds artifact-bundle purpose")
    timestamp = run_id.split("_")[2]
    if run_id != expected_run_id(freeze, timestamp):
        raise RuntimeError("run_id does not match frozen source/bitstream hashes")
    source = freeze["source_commit"]
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", source, "HEAD"], cwd=ROOT
    ).returncode:
        raise RuntimeError("artifact source is not an ancestor of authorization")
    inputs = hash_inputs()
    parent = git("rev-parse", "HEAD")
    statement = (
        "用户授权 Codex 在 P10_1R_AX7020_2LANE_SPEED_STABILITY_REMEDIATION "
        "范围内，对当前两块 AX7020 和四个 TFDU6102 小板执行自动化硬件操作；"
        "除明确电气危险、无法唯一绑定板卡、必须人工操作硬件或无法确认 shutdown "
        "外，不再请求确认。"
    )
    record = {
        "schema_version": 1,
        "authorization_id": "P10_1R-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED",
        "scope": EXPECTED_SCOPE,
        "run_id": run_id,
        "authorized_stages": stages,
        "branch": EXPECTED_BRANCH,
        "authorization_parent_commit": parent,
        "source_commit": source,
        "goal": rel(GOAL),
        "goal_sha256": EXPECTED_GOAL_SHA256,
        "artifact_freeze": rel(ARTIFACT_FREEZE),
        "artifact_freeze_sha256": EXPECTED_ARTIFACT_FREEZE_SHA256,
        "artifact_bundle_purpose": EXPECTED_ARTIFACT_PURPOSE,
        "acceptance_eligible": EXPECTED_ACCEPTANCE_ELIGIBLE,
        "artifacts": artifact_records(freeze),
        "pl_build_identity": {
            role: f"0x{value:08X}"
            for role, value in EXPECTED_PL_BUILD_IDS.items()
        },
        "inputs": inputs,
        "plan_sha256": plan_hashes(stages),
        "current_run_hardware_authorization": True,
        "consumed": False,
        "reusable_for_future_run": False,
        "standing_authorization_sources": list(STANDING_AUTHORIZATION_SOURCES),
        "standing_authorization_policy": {
            "scope": EXPECTED_SCOPE,
            "new_immutable_bundle_requires_exact_offline_pass_and_sha256_freeze": True,
            "fresh_per_run_authorization_required": True,
            "campaign_new_run_id_limit": None,
            "historical_authorization_or_artifact_pass_reuse": False,
        },
        "user_authorization_statement": statement,
        "user_authorization_statement_sha256": hashlib.sha256(
            statement.encode("utf-8")
        ).hexdigest(),
        "user_authorization_received_at": "2026-08-02T00:00:00+08:00",
        "board_identities": {
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
        },
        "part": EXPECTED_PART,
        "maximum_single_formal_run_seconds": 1800,
        "maximum_lane_mask": 3,
        "lane_masks": [1, 2, 3],
        "shutdown": {
            "before": True,
            "after": True,
            "on_error": True,
            "on_timeout": True,
            "on_interrupt": True,
            "normal_exit": True,
            "finally": True,
            "program_role_bound_shutdown_bitstreams": True,
            "required_markers": [
                "SHUTDOWN_FIXED=PASS",
                "SHUTDOWN_ROTATING=PASS",
                "TFDU_SHUTDOWN_PROGRAMMED=1",
                "SHUTDOWN_EXIT=0",
            ],
        },
        "prohibited": {
            "ethernet": True,
            "spi": True,
            "movement": True,
            "rotation": True,
            "angle_adjustment": True,
            "obscuration": True,
            "module_exchange": True,
            "rewiring": True,
            "lane_mask_above_0x3": True,
            "oneplusone_full_duplex": True,
            "p11": True,
            "8x32": True,
        },
        "generated_at_utc": utc_now(),
    }
    write_json(AUTH_PATH, record)
    return record


def _artifact_key(item: dict[str, Any]) -> str:
    return f"{item['role']}:{item['kind']}"


def validate_authorization(
    path: Path, run_id: str, stages: list[str]
) -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {}, [f"authorization unreadable: {exc}"]
    expected = {
        "schema_version": 1,
        "authorization_id": "P10_1R-CURRENT-RUN-IMMUTABLE",
        "status": "AUTHORIZED",
        "scope": EXPECTED_SCOPE,
        "run_id": run_id,
        "authorized_stages": stages,
        "branch": EXPECTED_BRANCH,
        "goal_sha256": EXPECTED_GOAL_SHA256,
        "artifact_freeze_sha256": EXPECTED_ARTIFACT_FREEZE_SHA256,
        "artifact_bundle_purpose": EXPECTED_ARTIFACT_PURPOSE,
        "acceptance_eligible": EXPECTED_ACCEPTANCE_ELIGIBLE,
        "current_run_hardware_authorization": True,
        "consumed": False,
        "reusable_for_future_run": False,
        "standing_authorization_sources": list(STANDING_AUTHORIZATION_SOURCES),
        "standing_authorization_policy": {
            "scope": EXPECTED_SCOPE,
            "new_immutable_bundle_requires_exact_offline_pass_and_sha256_freeze": True,
            "fresh_per_run_authorization_required": True,
            "campaign_new_run_id_limit": None,
            "historical_authorization_or_artifact_pass_reuse": False,
        },
        "part": EXPECTED_PART,
        "maximum_single_formal_run_seconds": 1800,
        "maximum_lane_mask": 3,
        "lane_masks": [1, 2, 3],
        "pl_build_identity": {
            role: f"0x{value:08X}"
            for role, value in EXPECTED_PL_BUILD_IDS.items()
        },
    }
    errors.extend(
        f"authorization {key} mismatch"
        for key, value in expected.items()
        if record.get(key) != value
    )
    if not RUN_RE.fullmatch(str(record.get("run_id", ""))):
        errors.append("authorization run_id syntax invalid")
    if sha256(GOAL) != EXPECTED_GOAL_SHA256:
        errors.append("live Goal SHA256 mismatch")
    try:
        live_inputs = hash_inputs()
    except (OSError, ValueError) as exc:
        errors.append(f"authorization input unavailable: {exc}")
        live_inputs = {}
    if record.get("inputs") != live_inputs:
        errors.append("authorization input hashes mismatch")
    if record.get("plan_sha256") != plan_hashes(stages):
        errors.append("authorization plan hashes mismatch")
    statement = record.get("user_authorization_statement", "")
    if not isinstance(statement, str) or not statement:
        errors.append("user authorization statement missing")
    elif hashlib.sha256(statement.encode("utf-8")).hexdigest() != record.get(
        "user_authorization_statement_sha256"
    ):
        errors.append("user authorization statement hash mismatch")
    expected_boards = {
        "fixed": (EXPECTED_FIXED_SERIAL, EXPECTED_FIXED_TARGET),
        "rotating": (EXPECTED_ROTATING_SERIAL, EXPECTED_ROTATING_TARGET),
    }
    for role, (serial, target) in expected_boards.items():
        item = record.get("board_identities", {}).get(role, {})
        if item.get("serial") != serial or item.get("target") != target:
            errors.append(f"{role} board binding mismatch")
    shutdown = record.get("shutdown", {})
    for key in (
        "before",
        "after",
        "on_error",
        "on_timeout",
        "on_interrupt",
        "normal_exit",
        "finally",
        "program_role_bound_shutdown_bitstreams",
    ):
        if shutdown.get(key) is not True:
            errors.append(f"shutdown policy missing {key}")
    try:
        freeze, frozen_paths = load_freeze()
        if record.get("source_commit") != freeze.get("source_commit"):
            errors.append("authorization source/freeze mismatch")
        if record.get("artifacts") != artifact_records(freeze):
            errors.append("authorization artifact ledger mismatch")
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        errors.append(f"artifact freeze validation failed: {exc}")
        frozen_paths = {}
    artifacts: dict[str, Path] = {}
    for item in record.get("artifacts", []):
        try:
            key = _artifact_key(item)
            candidate = (ROOT / item["path"]).resolve()
            if (
                not inside(candidate, ROOT / "artifacts/p10_1r")
                or not candidate.is_file()
                or candidate.stat().st_size != int(item["bytes"])
                or sha256(candidate) != item["sha256"]
            ):
                errors.append(f"authorization artifact invalid: {key}")
            artifacts[key] = candidate
        except (KeyError, TypeError, ValueError, OSError) as exc:
            errors.append(f"malformed authorization artifact: {exc}")
    if frozen_paths and artifacts != frozen_paths:
        errors.append("authorization artifact paths differ from freeze")
    if git("branch", "--show-current") != EXPECTED_BRANCH:
        errors.append("wrong branch")
    if git("status", "--porcelain"):
        errors.append("hardware execution requires a clean worktree")
    parent = record.get("authorization_parent_commit", "")
    head = git("rev-parse", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", str(parent)):
        errors.append("authorization parent commit invalid")
    else:
        try:
            if git("rev-parse", "HEAD^") != parent:
                errors.append("authorization commit parent mismatch")
            changed = git(
                "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"
            ).splitlines()
            if changed != [rel(AUTH_PATH)]:
                errors.append("authorization commit must contain only its record")
            committed = subprocess.check_output(
                ["git", "show", f"{head}:{rel(AUTH_PATH)}"], cwd=ROOT
            )
            if hashlib.sha256(committed).hexdigest() != sha256(AUTH_PATH):
                errors.append("working authorization differs from committed blob")
        except (OSError, subprocess.CalledProcessError) as exc:
            errors.append(f"authorization commit binding failed: {exc}")
    return record, artifacts, errors


def consumed_authorization_payload(
    authorization: dict[str, Any],
    *,
    run_id: str,
    campaign_status: str,
    consumed_at_utc: str,
    final_evidence_path: str,
    final_evidence_sha256: str,
    shutdown_fixed: str,
    shutdown_rotating: str,
    hardware_actions_executed: bool,
) -> dict[str, Any]:
    """Return the fail-closed terminal state for one immutable run grant."""
    result = copy.deepcopy(authorization)
    if result.get("run_id") != run_id:
        raise ValueError("current authorization run_id does not match hardware run")
    if result.get("current_run_hardware_authorization") is False:
        if (
            result.get("consumed") is True
            and result.get("consumed_by_run_id") == run_id
            and result.get("reusable_for_future_run") is False
        ):
            return result
        raise ValueError("current authorization has an invalid consumed state")
    if (
        result.get("status") != "AUTHORIZED"
        or result.get("current_run_hardware_authorization") is not True
        or result.get("consumed") is not False
    ):
        raise ValueError("current authorization was not active for this run")
    if campaign_status not in {"PASS", "FAIL"}:
        raise ValueError("campaign status must be PASS or FAIL")
    if shutdown_fixed not in {"PASS", "FAIL"} or shutdown_rotating not in {
        "PASS", "FAIL"
    }:
        raise ValueError("shutdown status is malformed")
    disposition = (
        "ACCEPTANCE_COMPLETE"
        if campaign_status == "PASS"
        else "REMEDIATION_REQUIRED_NEW_IMMUTABLE_BUNDLE"
    )
    next_action = (
        "freeze the final evidence checkpoint and annotated PASS tag"
        if campaign_status == "PASS"
        else (
            "preserve this run, remediate the direct failure, freeze a new "
            "exact-source artifact bundle, and create a fresh per-run authorization"
        )
    )
    result.update(
        {
            "status": f"CONSUMED_AFTER_P10_1R_HARDWARE_{campaign_status}",
            "authorization_status_at_run_start": "AUTHORIZED",
            "current_run_hardware_authorization": False,
            "consumed": True,
            "consumed_by_run_id": run_id,
            "consumed_at_utc": consumed_at_utc,
            "reusable_for_future_run": False,
            "campaign_status": campaign_status,
            "campaign_disposition": disposition,
            "hardware_actions_executed": hardware_actions_executed,
            "shutdown_fixed": shutdown_fixed,
            "shutdown_rotating": shutdown_rotating,
            "final_evidence_path": final_evidence_path,
            "final_evidence_sha256": final_evidence_sha256,
            "next_required_action": next_action,
        }
    )
    return result


SNAPSHOT_NAMES = (
    "status",
    "raw_lane0",
    "raw_lane1",
    "raw_while_tx_lane0",
    "raw_while_tx_lane1",
    "blanked_raw_lane0",
    "blanked_raw_lane1",
    "blanked_frame_lane0",
    "blanked_frame_lane1",
    "blanked_crc_lane0",
    "blanked_crc_lane1",
    "local_source_reject_lane0",
    "local_source_reject_lane1",
    "accepted_remote_lane0",
    "accepted_remote_lane1",
    "guard_total_lane0",
    "guard_total_lane1",
    "guard_max_lane0",
    "guard_max_lane1",
    "echo_tail_max_lane0",
    "echo_tail_max_lane1",
    "decoder_clear_lane0",
    "decoder_clear_lane1",
    "last_txd_rise_lane0",
    "last_txd_rise_lane1",
    "last_txd_fall_lane0",
    "last_txd_fall_lane1",
    "first_rxd_after_tx_lane0",
    "first_rxd_after_tx_lane1",
    "last_rxd_after_tx_lane0",
    "last_rxd_after_tx_lane1",
    "overlap_violation",
    "admission_violation",
    "non_target_accepted",
    "cross_lane_accepted",
    "configured_guard_cycles",
    "idle_qualify_cycles",
    "max_quarantine_cycles",
    "decoder_clear_cycles",
    "admission_config_flags",
)


def parse_snapshot(path: Path) -> dict[str, Any]:
    fields = path.read_text(encoding="ascii").strip().split("|")
    if len(fields) != 42:
        raise ValueError(f"snapshot field count {len(fields)} != 42")
    values = [int(value, 0) for value in fields]
    generation, caps = values[:2]
    words = values[2:]
    if generation <= 0 or generation & 1:
        raise ValueError("snapshot generation is not positive/even")
    if caps != EXPECTED_ADMISSION_CAPS:
        raise ValueError("snapshot capability mismatch")
    result = {name: value for name, value in zip(SNAPSHOT_NAMES, words)}
    result.update({"generation": generation, "capabilities": caps})
    expected_constants = (
        EXPECTED_GUARD_CYCLES,
        EXPECTED_IDLE_QUALIFY_CYCLES,
        EXPECTED_MAX_QUARANTINE_CYCLES,
        EXPECTED_IDLE_LOW_CYCLES,
        EXPECTED_IDLE_HIGH_CYCLES,
    )
    if tuple(words[35:40]) != expected_constants:
        raise ValueError("snapshot admission constants mismatch")
    return result


def integer_row(row: dict[str, str]) -> dict[str, Any]:
    text_fields = {
        "label",
        "window",
        "fixed_dump_path",
        "rotating_dump_path",
        "fixed_p10_1_dump_path",
        "rotating_p10_1_dump_path",
        "fixed_p10_1r_dump_path",
        "rotating_p10_1r_dump_path",
    }
    return {
        key: value if key in text_fields or not value else int(value, 0)
        for key, value in row.items()
    }


def nearest_rank(values: list[int], percentile: float) -> int:
    if not values:
        raise ValueError("empty percentile sample")
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def evaluate_echo(stage_dir: Path) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    modules: dict[str, Any] = {}
    for path in sorted((stage_dir / "dumps").glob("*.echo_tail.psv")):
        with path.open(encoding="ascii", newline="") as handle:
            rows = [
                {key: (value if key == "module" else int(value, 0))
                 for key, value in row.items()}
                for row in csv.DictReader(handle, delimiter="|")
            ]
        if len(rows) != 1000:
            errors.append(f"{path.name}: expected 1000 samples, got {len(rows)}")
            continue
        module_names = {row["module"] for row in rows}
        if len(module_names) != 1:
            errors.append(f"{path.name}: module identity is not unique")
            continue
        module = module_names.pop()
        tails = [row["tail_cycles"] for row in rows]
        summary = {
            "module": module,
            "samples": len(rows),
            "p99_cycles": nearest_rank(tails, 0.99),
            "p99_9_cycles": nearest_rank(tails, 0.999),
            "maximum_cycles": max(tails),
            "same_module_raw_count": sum(row["sender_raw"] for row in rows),
            "raw_while_tx_count": sum(
                row["sender_raw_while_tx"] for row in rows
            ),
            "blanked_raw_count": sum(
                row["sender_blanked_raw"] for row in rows
            ),
            "blanked_frame_count": sum(
                row["sender_blanked_frame"] for row in rows
            ),
            "local_source_reject_count": sum(
                row["sender_local_source_reject"] for row in rows
            ),
            "sender_accepted_remote_count": sum(
                row["sender_accepted_remote"] for row in rows
            ),
            "receiver_raw_count": sum(row["receiver_raw"] for row in rows),
            "source": rel(path),
        }
        violation_fields = (
            "sender_overlap_violation",
            "sender_admission_violation",
            "sender_non_target_accepted",
            "sender_cross_lane_accepted",
            "receiver_overlap_violation",
            "receiver_admission_violation",
            "receiver_non_target_accepted",
            "receiver_cross_lane_accepted",
        )
        summary["violations"] = {
            field: sum(row[field] for row in rows) for field in violation_fields
        }
        if summary["same_module_raw_count"] <= 0:
            errors.append(f"{module}: same-module raw echo was not observed")
        if summary["receiver_raw_count"] < 1000:
            errors.append(f"{module}: intended remote raw observations < 1000")
        if summary["sender_accepted_remote_count"] != 0:
            errors.append(f"{module}: same-module event entered accepted path")
        for field, value in summary["violations"].items():
            if value != 0:
                errors.append(f"{module}: {field}={value}")
        modules[module] = summary
    if set(modules) != {"F0", "F1", "R0", "R1"}:
        errors.append("echo-tail evidence does not contain F0/F1/R0/R1 exactly")
    maximum = max(
        (item["maximum_cycles"] for item in modules.values()), default=0
    )
    minimum_safe = maximum + GUARD_MARGIN_CYCLES
    configured_safe = EXPECTED_GUARD_CYCLES >= minimum_safe
    if not configured_safe:
        errors.append(
            f"configured guard {EXPECTED_GUARD_CYCLES} < measured-safe {minimum_safe}"
        )
    return errors, {
        "modules": modules,
        "sample_count": sum(item["samples"] for item in modules.values()),
        "same_module_raw_echo_count": sum(
            item["same_module_raw_count"] for item in modules.values()
        ),
        "same_module_blanked_frame_count": sum(
            item["blanked_frame_count"] for item in modules.values()
        ),
        "measured_maximum_echo_tail_cycles": maximum,
        "deterministic_margin_cycles": GUARD_MARGIN_CYCLES,
        "minimum_safe_guard_cycles": minimum_safe,
        "configured_guard_cycles": EXPECTED_GUARD_CYCLES,
        "configured_guard_is_safe": configured_safe,
        "guard_minimization_pending": minimum_safe != EXPECTED_GUARD_CYCLES,
    }


def _p101_sender(detail: dict[str, Any]) -> dict[str, Any]:
    return detail["fixed"] if detail["direction"] == 0 else detail["rotating"]


def _p101_receiver(detail: dict[str, Any]) -> dict[str, Any]:
    return detail["rotating"] if detail["direction"] == 0 else detail["fixed"]


def window_summary(details: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    specs = [item for item in build_plans()[stage] if isinstance(item, tuple)]
    windows: list[dict[str, Any]] = []
    for item in specs:
        if item[0] not in {"P101_WINDOW", "P101R_TIMED_CASE"}:
            continue
        label, duration, direction, lane = item[1], int(item[2]), int(item[3]), int(item[4])
        matched = [detail for detail in details if detail.get("window") == label]
        committed = sum(detail["requested_bytes"] for detail in matched)
        host_commands = len(matched)
        frames = 0
        acknowledgements = 0
        ack_wait = 0
        pl_ticks = 0
        inter_object = 0
        ps_ticks = 0
        for detail in matched:
            sender = _p101_sender(detail)
            frames += math.ceil(detail["requested_bytes"] / 247)
            acknowledgements += sum(sender["physical_ack_good_by_lane_after"])
            ack_wait += sender["perf_ack_wait"]
            pl_ticks += sender["pl_elapsed_ticks"]
            inter_object += sender["inter_object_signal_ticks"]
            ps_ticks += sender["ps_elapsed_ticks"]
        windows.append(
            {
                "label": label,
                "duration_seconds": duration,
                "direction": direction,
                "lane_mask": lane,
                "case_count": len(matched),
                "host_blocking_commands": host_commands,
                "committed_bytes": committed,
                "application_goodput_bps": committed * 8 / duration,
                "data_frames": frames,
                "ack_count": acknowledgements,
                "data_frames_per_ack": (
                    frames / acknowledgements if acknowledgements else 0.0
                ),
                "ack_wait_ratio": ack_wait / pl_ticks if pl_ticks else 0.0,
                "inter_object_ratio": (
                    inter_object / ps_ticks if ps_ticks else 0.0
                ),
            }
        )
    return windows


def common_snapshot_errors(
    label: str, fixed: dict[str, Any], rotating: dict[str, Any]
) -> list[str]:
    errors: list[str] = []
    for role, snapshot in (("fixed", fixed), ("rotating", rotating)):
        for field in (
            "overlap_violation",
            "admission_violation",
            "non_target_accepted",
            "cross_lane_accepted",
        ):
            if snapshot[field] != 0:
                errors.append(f"{label}:{role}:{field}={snapshot[field]}")
    return errors


def evaluate_stage(
    stage: str, stage_dir: Path, process: dict[str, Any]
) -> dict[str, Any]:
    errors: list[str] = []
    markers = parse_markers(stage_dir / "xsdb.result.txt")
    if process.get("returncode") != 0 or process.get("timed_out"):
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS":
        errors.append("XSDB PASS marker missing")
    if markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("safe-boot marker missing")
    ledger = stage_dir / "dumps/observations.psv"
    rows: list[dict[str, Any]] = []
    if ledger.is_file():
        with ledger.open(encoding="ascii", newline="") as handle:
            rows = [integer_row(row) for row in csv.DictReader(handle, delimiter="|")]
    else:
        errors.append("observation ledger missing")
    shutdown_rows = [row for row in rows if row["label"].endswith("_endpoint_shutdown")]
    if len(shutdown_rows) != 1 or not rows or rows[-1] is not shutdown_rows[0]:
        errors.append("exactly one final endpoint-shutdown row required")
    details: list[dict[str, Any]] = []
    for row in rows:
        try:
            fixed_snapshot_path = Path(row["fixed_p10_1r_dump_path"]).resolve()
            rotating_snapshot_path = Path(row["rotating_p10_1r_dump_path"]).resolve()
            if not inside(fixed_snapshot_path, stage_dir) or not inside(
                rotating_snapshot_path, stage_dir
            ):
                raise ValueError("P10.1R snapshot escaped stage directory")
            fixed_snapshot = parse_snapshot(fixed_snapshot_path)
            rotating_snapshot = parse_snapshot(rotating_snapshot_path)
            if row["command"] == 13:
                fixed_path = Path(row["fixed_p10_1_dump_path"]).resolve()
                rotating_path = Path(row["rotating_p10_1_dump_path"]).resolve()
                if not inside(fixed_path, stage_dir) or not inside(rotating_path, stage_dir):
                    raise ValueError("P10.1 result escaped stage directory")
                pair_errors, detail = p101.evaluate_p101_pair(
                    row, p101.parse_p101(fixed_path), p101.parse_p101(rotating_path)
                )
            else:
                fixed_path = Path(row["fixed_dump_path"]).resolve()
                rotating_path = Path(row["rotating_dump_path"]).resolve()
                if not inside(fixed_path, stage_dir) or not inside(rotating_path, stage_dir):
                    raise ValueError("mailbox dump escaped stage directory")
                pair_errors, detail = evaluate_pair(
                    row,
                    parse_mailbox(fixed_path),
                    parse_mailbox(rotating_path),
                    EXPECTED_ROLE_IDENTITIES,
                )
            errors.extend(pair_errors)
            errors.extend(
                common_snapshot_errors(row["label"], fixed_snapshot, rotating_snapshot)
            )
            detail.update(
                {
                    "command": row["command"],
                    "flags": row["flags"],
                    "window": row["window"],
                    "started_ms": row["started_ms"],
                    "finished_ms": row["finished_ms"],
                    "fixed_p10_1r": fixed_snapshot,
                    "rotating_p10_1r": rotating_snapshot,
                }
            )
            details.append(detail)
        except (OSError, ValueError, KeyError, struct.error) as exc:
            errors.append(f"{row.get('label', 'unknown')}: {exc}")
    plan = build_plans()[stage]
    observed_labels = {row.get("label") for row in rows}
    observed_windows = {row.get("window") for row in rows}
    for item in plan:
        if isinstance(item, Case):
            if item.label not in observed_labels:
                errors.append(f"immutable plan case missing: {item.label}")
        elif item[0] in {"P101_PSRESET", "P101R_TIMED_CASE"}:
            if item[1] not in observed_labels:
                errors.append(f"immutable plan case missing: {item[1]}")
        elif item[0] == "P101_WINDOW":
            if item[1] not in observed_windows:
                errors.append(f"bounded window has no observation: {item[1]}")
        elif item[0] == "P101_FORMAL":
            expected_windows = {
                f"{item[1]}_warmup_f2r",
                f"{item[1]}_warmup_r2f",
                f"{item[1]}_formal_f2r",
                f"{item[1]}_formal_r2f",
            }
            missing = expected_windows - observed_windows
            if missing:
                errors.append(
                    "formal windows missing: " + ",".join(sorted(missing))
                )
    semantics: dict[str, Any] = {}
    if stage == "echo_tail":
        echo_errors, semantics = evaluate_echo(stage_dir)
        errors.extend(echo_errors)
    elif stage in {"crosstalk", "phy_sanity"}:
        non_shutdown = [
            detail for detail in details if not detail["label"].endswith("_endpoint_shutdown")
        ]
        reconciled = 0
        local_rejected = 0
        other_lane_blanked = 0
        for detail in non_shutdown:
            if detail["command"] != 13:
                continue
            sender_role = "fixed" if detail["direction"] == 0 else "rotating"
            receiver_role = "rotating" if detail["direction"] == 0 else "fixed"
            sender = detail[sender_role]
            receiver = detail[receiver_role]
            sender_snapshot = detail[f"{sender_role}_p10_1r"]
            receiver_snapshot = detail[f"{receiver_role}_p10_1r"]
            legitimate_ack = sum(sender["physical_ack_good_by_lane_after"])
            legitimate_data = sum(receiver["physical_data_good_by_lane_after"])
            sender_accepted = (
                sender_snapshot["accepted_remote_lane0"]
                + sender_snapshot["accepted_remote_lane1"]
            )
            receiver_accepted = (
                receiver_snapshot["accepted_remote_lane0"]
                + receiver_snapshot["accepted_remote_lane1"]
            )
            if sender_accepted != legitimate_ack:
                errors.append(f"{detail['label']}: sender accepted/legitimate ACK mismatch")
            if receiver_accepted != legitimate_data:
                errors.append(f"{detail['label']}: receiver accepted/legitimate DATA mismatch")
            if legitimate_data <= 0:
                errors.append(f"{detail['label']}: intended remote valid frame missing")
            lane_index = 0 if detail["lane_mask"] == 1 else 1
            other_index = 1 - lane_index
            if stage == "phy_sanity":
                selected_frames = receiver[
                    "physical_data_good_by_lane_after"
                ][lane_index]
                other_frames = receiver[
                    "physical_data_good_by_lane_after"
                ][other_index]
                if selected_frames != 1000:
                    errors.append(
                        f"{detail['label']}: selected valid frames "
                        f"{selected_frames} != 1000"
                    )
                if other_frames != 0:
                    errors.append(
                        f"{detail['label']}: off-lane valid frames={other_frames}"
                    )
            local_rejected += sender_snapshot[f"local_source_reject_lane{lane_index}"]
            other_lane_blanked += sender_snapshot[f"blanked_raw_lane{other_index}"]
            reconciled += 1
        if other_lane_blanked != 0:
            errors.append("transmitting one lane blanked the other lane")
        semantics = {
            "remote_acceptance_reconciled_case_count": reconciled,
            "same_module_accepted_data_count": 0 if reconciled else None,
            "cross_lane_accepted_data_count": 0 if reconciled else None,
            "local_source_rejected_frame_count": local_rejected,
            "local_source_rejection_enabled": all(
                detail[f"{role}_p10_1r"]["admission_config_flags"] & 1
                for detail in non_shutdown
                for role in ("fixed", "rotating")
            ),
            "local_source_rejection_observed": local_rejected > 0,
            "other_lane_blanked_count": other_lane_blanked,
        }
    elif stage in {"ack_tuning", "performance"}:
        windows = window_summary(details, stage)
        if len(windows) != 2:
            errors.append(f"{stage}: expected two direction windows")
        for window in windows:
            if window["application_goodput_bps"] < 4_000_000:
                errors.append(f"{window['label']}: application goodput below 4 Mbit/s")
            if stage == "ack_tuning":
                if window["data_frames_per_ack"] < 24:
                    errors.append(f"{window['label']}: fewer than 24 data frames/ACK")
                if window["host_blocking_commands"] > 4:
                    errors.append(f"{window['label']}: more than four host commands")
        semantics = {
            "windows": windows,
            "best_burst_frames": 32,
            "best_ack_threshold": 32,
            "best_ack_max_delay_cycles": 64000,
            "objects_in_flight": 4,
        }
    elif stage == "streaming_64m":
        normal = [
            detail for detail in details if detail["label"].startswith("stream64_")
        ]
        f2r = [detail for detail in normal if detail["direction"] == 0]
        r2f = [detail for detail in normal if detail["direction"] == 1]
        recovery = [detail for detail in details if detail.get("recovery_case")]
        clean = [
            detail for detail in details if detail["label"].startswith("stream_clean_after_")
        ]
        if len(f2r) != 5 or len(r2f) != 5:
            errors.append("five 64MiB objects per direction were not observed")
        if len(recovery) != 3 or len(clean) != 3:
            errors.append("abort/service-reset/DMA-reset recovery matrix incomplete")
        semantics = {
            "f2r_64m_count": len(f2r),
            "r2f_64m_count": len(r2f),
            "recovery_vector_count": len(recovery),
            "post_recovery_clean_count": len(clean),
        }
    elif stage == "formal_30min":
        elapsed_text = markers.get("P10_1_FORMAL_ELAPSED_MS", "0")
        elapsed = int(elapsed_text) if elapsed_text.isdigit() else 0
        if markers.get("P10_1_FORMAL_RESULT") != "PASS" or not 1_800_000 <= elapsed <= 1_800_500:
            errors.append("formal active window is not exactly 1800 seconds")
        windows: list[dict[str, Any]] = []
        for label, duration, direction in (
            ("stationary_30min_formal_f2r", 840, 0),
            ("stationary_30min_formal_r2f", 840, 1),
        ):
            matched = [detail for detail in details if detail.get("window") == label]
            committed = sum(detail["requested_bytes"] for detail in matched)
            goodput = committed * 8 / duration
            windows.append(
                {
                    "label": label,
                    "duration_seconds": duration,
                    "direction": direction,
                    "case_count": len(matched),
                    "committed_bytes": committed,
                    "application_goodput_bps": goodput,
                }
            )
            if not matched or goodput < 4_000_000:
                errors.append(f"{label}: formal goodput below 4 Mbit/s")
        semantics = {"elapsed_ms": elapsed, "formal_windows": windows}
    summary = {
        "schema_version": 1,
        "test_id": f"P10_1R-HW-{stage.upper()}",
        "stage": stage,
        "status": "PASS" if not errors else "FAIL",
        "process": process,
        "markers": markers,
        "observation_count": len(rows),
        "details": details,
        "semantics": semantics,
        "errors": errors,
        "generated_at_utc": utc_now(),
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
    stage_dir = run_root / STAGE_DIRECTORY[stage]
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    plan_path = stage_dir / f"{stage}.plan"
    write_text(plan_path, plan_text(build_plans()[stage]))
    result_path = stage_dir / "xsdb.result.txt"
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
        str(plan_path),
        str(dump_dir),
        str(abort_file),
        str(result_path),
        TCL_STAGE[stage],
        str(auth),
        run_root.name,
        f"0x{EXPECTED_PL_BUILD_IDS['fixed']:08X}",
        f"0x{EXPECTED_PL_BUILD_IDS['rotating']:08X}",
    ]
    timeout = {
        "preflight": 900,
        "echo_tail": 7200,
        "crosstalk": 1800,
        "phy_sanity": 900,
        "ack_tuning": 900,
        "performance": 1200,
        "streaming_64m": 7200,
        "formal_30min": 2400,
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
        if path in {output, run_root / "final/orchestrator_result.json"}:
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
        "test_id": "P10_1R-HW-EVIDENCE-MANIFEST",
        "status": "PASS",
        "run_id": run_root.name,
        "files": files,
        "generated_at_utc": utc_now(),
    }
    write_json(output, payload)
    return payload


def publish_stage(stage: str, summary: dict[str, Any], run_root: Path) -> None:
    name = "safe_boot" if stage == "preflight" else stage
    json_path = GENERATED / f"p10_1r_{name}.json"
    md_path = GENERATED / f"p10_1r_{name}.md"
    payload = {
        "schema_version": 1,
        "test_id": summary["test_id"],
        "status": summary["status"],
        "run_id": run_root.name,
        "source_commit": json.loads(AUTH_PATH.read_text(encoding="utf-8"))[
            "source_commit"
        ],
        "raw_summary": rel(
            run_root / STAGE_DIRECTORY[stage] / "stage_summary.json"
        ),
        "raw_summary_sha256": sha256(
            run_root / STAGE_DIRECTORY[stage] / "stage_summary.json"
        ),
        "semantics": summary.get("semantics", {}),
        "errors": summary.get("errors", []),
        "hardware_actions_executed": True,
        "network_used": False,
        "hardware_movement": False,
        "rewiring_executed": False,
        "generated_at_utc": utc_now(),
    }
    write_json(json_path, payload)
    write_text(
        md_path,
        "\n".join(
            [
                f"# P10.1R {name.replace('_', ' ')}",
                "",
                f"Status: `{payload['status']}`",
                f"Run ID: `{run_root.name}`",
                f"Raw summary: `{payload['raw_summary']}`",
                "",
                "The adjacent JSON is the authoritative machine-readable record.",
            ]
        )
        + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--stage", action="append", choices=STAGES, required=True)
    parser.add_argument("--authorize-from", type=Path, default=AUTH_PATH)
    parser.add_argument("--prepare-authorization", action="store_true")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    stages = list(dict.fromkeys(args.stage))
    if args.prepare_authorization:
        try:
            record = create_authorization(args.run_id, stages)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            print(f"P10_1R_AUTHORIZATION=FAIL\nERROR={exc}", file=sys.stderr)
            return 1
        print("P10_1R_AUTHORIZATION=PASS")
        print(f"P10_1R_AUTHORIZATION_PATH={rel(AUTH_PATH)}")
        print(f"P10_1R_AUTHORIZATION_SHA256={sha256(AUTH_PATH)}")
        if args.json_summary:
            print(json.dumps(record, sort_keys=True))
        return 0

    auth = args.authorize_from.resolve()
    record, artifacts, errors = validate_authorization(
        auth, args.run_id, stages
    )
    if auth != AUTH_PATH.resolve():
        errors.append("hardware run must use the canonical current-run authorization")
    if args.validate_only:
        result = {
            "status": "PASS" if not errors else "FAIL",
            "run_id": args.run_id,
            "stages": stages,
            "errors": errors,
            "hardware_actions_executed": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 0 if not errors else 1
    if not args.execute_hardware:
        errors.append("--execute-hardware is required")
    if os.environ.get("NO_HARDWARE", "1") != "0":
        errors.append("NO_HARDWARE=0 is required")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "true":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION=true is required")
    run_root = HW_ROOT / (
        args.run_id if RUN_RE.fullmatch(args.run_id) else "invalid_run_id"
    )
    if run_root.exists() and any(run_root.iterdir()):
        errors.append("run directory already exists and is nonempty")
    for directory in (
        "authorization",
        "artifacts",
        "safe_boot",
        "echo_tail",
        "crosstalk_remediation",
        "phy_sanity",
        "ack_tuning",
        "sustained_performance",
        "streaming_64m",
        "formal_30min",
        "shutdown",
        "raw_logs",
        "final",
    ):
        (run_root / directory).mkdir(parents=True, exist_ok=True)
    authorization_record = {
        "schema_version": 1,
        "test_id": "P10_1R-HW-CURRENT-RUN-AUTHORIZATION",
        "status": "PASS" if not errors else "FAIL",
        "run_id": args.run_id,
        "authorization": rel(auth) if inside(auth, ROOT) else str(auth),
        "authorization_sha256": sha256(auth) if auth.is_file() else None,
        "source_commit": record.get("source_commit"),
        "goal_sha256": record.get("goal_sha256"),
        "board_identities": record.get("board_identities"),
        "authorized_stages": stages,
        "maximum_single_formal_run_seconds": 1800,
        "shutdown": record.get("shutdown"),
        "errors": errors,
        "hardware_actions_executed": False,
    }
    write_json(
        run_root / "authorization/authorization_record.json",
        authorization_record,
    )
    if auth.is_file():
        shutil.copy2(auth, run_root / "authorization/immutable_authorization.json")
    if errors:
        write_json(run_root / "final/orchestrator_result.json", authorization_record)
        print("P10_1R_HARDWARE=FAIL_PRECONDITION", file=sys.stderr)
        for error in errors:
            print(f"ERROR={error}", file=sys.stderr)
        return 1

    ps7: dict[str, Path] = {}
    derived: dict[str, Any] = {}
    try:
        for role in ("fixed", "rotating"):
            destination = run_root / "artifacts" / role / "ps7_init.tcl"
            derived[role] = extract_ps7_init(
                artifacts[f"{role}:xsa"], destination
            )
            ps7[role] = destination
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        authorization_record["errors"].append(f"PS7 init extraction failed: {exc}")
        write_json(run_root / "authorization/authorization_record.json", authorization_record)
        return 1
    write_json(
        run_root / "artifacts/derived_artifact_manifest.json",
        {"schema_version": 1, "status": "PASS", "ps7_init": derived},
    )
    write_text(
        run_root / "authorization/NO_MOVEMENT_NETWORK_ATTESTATION.txt",
        "NO_HARDWARE_MOVEMENT=true\nROTATION_EXECUTED=false\n"
        "REWIRING_EXECUTED=false\nMODULE_EXCHANGE_EXECUTED=false\n"
        "EXTERNAL_NETWORK_USED=false\nETHERNET_USED=false\nSPI_USED=false\n"
        "LOCALHOST_HW_SERVER_USED=true\nMAX_LANE_MASK_USED=0x3\n",
    )
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
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server failed"))
        hardware_actions = True
        initial = invoke_shutdown(
            run_root, auth, artifacts, "initial_shutdown", env, retry_limit=3
        )
        shutdowns.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for stage in stages:
            before = invoke_shutdown(
                run_root, auth, artifacts, f"{stage}_before", env, retry_limit=3
            )
            shutdowns.append(before)
            if before.get("status") != "PASS":
                raise RuntimeError(f"{stage} shutdown-before unconfirmed")
            result: dict[str, Any] = {"status": "FAIL"}
            try:
                result = invoke_stage(
                    stage, run_root, auth, artifacts, ps7, env, abort_file
                )
                stage_results[stage] = result
            finally:
                after = invoke_shutdown(
                    run_root, auth, artifacts, f"{stage}_after", env, retry_limit=3
                )
                shutdowns.append(after)
            if result.get("status") != "PASS":
                raise RuntimeError(f"{stage} validation failed")
            if after.get("status") != "PASS":
                raise RuntimeError(f"{stage} shutdown-after unconfirmed")
        final_shutdown = invoke_shutdown(
            run_root, auth, artifacts, "final_shutdown", env, retry_limit=3
        )
        shutdowns.append(final_shutdown)
        if final_shutdown.get("status") != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except BaseException as exc:
        campaign_errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        emergency = invoke_shutdown(
            run_root, auth, artifacts, "finally_emergency", env, retry_limit=3
        )
        shutdowns.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            terminate_tree(server_proc)

    shutdown_fixed = (
        "PASS"
        if shutdowns and all(item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdowns)
        else "FAIL"
    )
    shutdown_rotating = (
        "PASS"
        if shutdowns and all(item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdowns)
        else "FAIL"
    )
    status = (
        "PASS"
        if not campaign_errors
        and all(stage_results.get(stage, {}).get("status") == "PASS" for stage in stages)
        and shutdown_fixed == shutdown_rotating == "PASS"
        else "FAIL"
    )
    summary = {
        "schema_version": 1,
        "test_id": "P10_1R-HW-ORCHESTRATOR",
        "status": status,
        "run_id": args.run_id,
        "source_commit": record.get("source_commit"),
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": hardware_actions,
        "network_used": False,
        "ethernet_used": False,
        "spi_used": False,
        "hardware_movement": False,
        "rotation_executed": False,
        "rewiring_executed": False,
        "maximum_lane_mask_used": "0x3",
        "stage_status": {
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
    authorization_record["hardware_actions_executed"] = hardware_actions
    write_json(run_root / "authorization/authorization_record.json", authorization_record)
    write_json(run_root / "final/orchestrator_result.json", summary)
    manifest = evidence_manifest(run_root)
    summary["evidence_manifest"] = rel(
        run_root / "final/run_evidence_sha256_manifest.json"
    )
    summary["evidence_file_count"] = len(manifest["files"])
    write_json(run_root / "final/orchestrator_result.json", summary)
    for stage, result in stage_results.items():
        publish_stage(stage, result, run_root)
    immutable_authorization = (
        run_root / "authorization/immutable_authorization.json"
    )
    authorization_consumption_error: str | None = None
    current_authorization: dict[str, Any] | None = None
    try:
        final_result = run_root / "final/orchestrator_result.json"
        current_authorization = consumed_authorization_payload(
            record,
            run_id=args.run_id,
            campaign_status=status,
            consumed_at_utc=utc_now(),
            final_evidence_path=rel(final_result),
            final_evidence_sha256=sha256(final_result),
            shutdown_fixed=shutdown_fixed,
            shutdown_rotating=shutdown_rotating,
            hardware_actions_executed=hardware_actions,
        )
        write_json(AUTH_PATH, current_authorization)
    except (OSError, ValueError, TypeError) as exc:
        authorization_consumption_error = (
            f"current-run authorization consumption failed: {exc}"
        )
        status = "FAIL"
        summary["status"] = status
        summary["errors"].append(authorization_consumption_error)
        write_json(run_root / "final/orchestrator_result.json", summary)
    authorization_generated = {
        "schema_version": 1,
        "test_id": "P10_1R-CURRENT-RUN-AUTHORIZATION-EVIDENCE",
        "status": (
            "PASS"
            if not authorization_record["errors"]
            and authorization_consumption_error is None
            and current_authorization is not None
            else "FAIL"
        ),
        "run_id": args.run_id,
        "authorization_at_run_start": rel(immutable_authorization),
        "authorization_at_run_start_sha256": sha256(immutable_authorization),
        "authorization_status_at_run_start": "AUTHORIZED",
        "current_authorization": rel(AUTH_PATH),
        "current_authorization_sha256": sha256(AUTH_PATH),
        "current_run_hardware_authorization": (
            current_authorization.get("current_run_hardware_authorization")
            if current_authorization is not None
            else record.get("current_run_hardware_authorization")
        ),
        "consumed": (
            current_authorization.get("consumed")
            if current_authorization is not None
            else False
        ),
        "reusable_for_future_run": False,
        "campaign_status": status,
        "raw_record": rel(run_root / "authorization/authorization_record.json"),
        "hardware_actions_executed": hardware_actions,
        "shutdown_fixed": shutdown_fixed,
        "shutdown_rotating": shutdown_rotating,
        "errors": (
            [authorization_consumption_error]
            if authorization_consumption_error is not None
            else []
        ),
        "generated_at_utc": utc_now(),
    }
    write_json(GENERATED / "p10_1r_authorization.json", authorization_generated)
    write_text(
        GENERATED / "p10_1r_authorization.md",
        "# P10.1R current-run authorization\n\n"
        f"Status: `{authorization_generated['status']}`\n\n"
        f"Run ID: `{args.run_id}`\n\n"
        "The adjacent JSON is authoritative.\n",
    )
    shutdown_generated = {
        "schema_version": 1,
        "test_id": "P10_1R-DUAL-SHUTDOWN",
        "status": "PASS" if shutdown_fixed == shutdown_rotating == "PASS" else "FAIL",
        "run_id": args.run_id,
        "SHUTDOWN_FIXED": shutdown_fixed,
        "SHUTDOWN_ROTATING": shutdown_rotating,
        "attempts": shutdowns,
        "generated_at_utc": utc_now(),
    }
    write_json(GENERATED / "p10_1r_shutdown.json", shutdown_generated)
    write_text(
        GENERATED / "p10_1r_shutdown.md",
        "# P10.1R shutdown evidence\n\n"
        f"Fixed / rotating: `{shutdown_fixed}` / `{shutdown_rotating}`\n\n"
        "The adjacent JSON is authoritative.\n",
    )
    if args.json_summary:
        print(json.dumps(summary, sort_keys=True))
    else:
        print(f"P10_1R_HARDWARE={status}")
        print(f"P10_1R_RUN_ID={args.run_id}")
        print(f"SHUTDOWN_FIXED={shutdown_fixed}")
        print(f"SHUTDOWN_ROTATING={shutdown_rotating}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
