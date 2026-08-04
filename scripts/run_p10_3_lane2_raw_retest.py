#!/usr/bin/env python3
"""Bounded, fail-closed P10.3 single-lane raw-connectivity diagnostic.

The default remains the historical lane2 replacement retest.  ``--lane 3``
selects a fresh bidirectional lane3 retest after the user replaced R3 B0017
with B0025.  Both modes use independent shutdown-bound directions and raw-only
64/1024-pulse observations.

require-user-hw-authorization
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import shutil
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import run_p10_3_ax7020_4lane_hardware as p103


ROOT = p103.ROOT
HW_ROOT = ROOT / "evidence/hardware/p10_3_raw_connectivity"
GENERATED = ROOT / "evidence/generated"
REPORTS = ROOT / "reports"
STAGE_TIMEOUT_SECONDS = 600
MAXIMUM_ACTIVE_RUNTIME_SECONDS = 1200
MAXIMUM_WRAPPER_RUNTIME_SECONDS = 1800
RUN_RE = re.compile(
    r"^p10_3_raw_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}_[0-9a-f]{8}_[0-9a-f]{8}$"
)

LANE_CONFIGS: dict[int, dict[str, Any]] = {
    2: {
        "fixed_id": "B0001", "rotating_id": "B0023",
        "authorization_id": "P10_3-LANE2-RAW-RETEST-CURRENT-RUN-IMMUTABLE",
        "authorization": "config/p10_3_lane2_raw_retest_current_run_authorization.json",
        "blocker": "evidence/generated/p10_3_lane2_directional_connectivity_blocker.json",
        "output_stem": "p10_3_lane2_raw_connectivity_retest",
        "scope_suffix": "LANE2_RAW_CONNECTIVITY_RETEST",
        "title": "lane2 raw-connectivity retest after R2 replacement",
        "trigger": "User replaced R2 B0015 with B0023 and explicitly requested a new raw-connectivity test.",
        "user_statement": "我已将R2  B0015换为新的B0023，请重新测试raw连通性",
        "directions": ("f2_to_r2", "r2_to_f2"),
    },
    3: {
        "fixed_id": "B0020", "rotating_id": "B0025",
        "authorization_id": "P10_3-LANE3-B0020-B0025-RAW-RETEST-CURRENT-RUN-IMMUTABLE",
        "authorization": "config/p10_3_lane3_b0020_b0025_raw_retest_current_run_authorization.json",
        "blocker": "evidence/generated/p10_3_lane3_b0020_raw_connectivity_retest.json",
        "output_stem": "p10_3_lane3_b0020_b0025_raw_connectivity_retest",
        "scope_suffix": "LANE3_B0020_B0025_RAW_CONNECTIVITY_RETEST",
        "title": "lane3 bidirectional raw-connectivity retest after R3 replacement",
        "trigger": (
            "The user reported replacing R3 B0017 with B0025 and explicitly "
            "requested a quick lane3 raw-only retest. The fresh run must test "
            "both physical directions without relabeling prior failures."
        ),
        "user_statement": "我已经将B0017替换为B0025，请重新快速测试，我只需要知道raw连通性，你不要整理那么多文件",
        "directions": ("f3_to_r3", "r3_to_f3"),
    },
}


def configure_lane(lane: int) -> None:
    global ACTIVE_LANE, LANE_MASK, FIXED_MODULE, ROTATING_MODULE
    global FIXED_ID, ROTATING_ID, AUTH, PREVIOUS_BLOCKER, OUTPUT_STEM
    global SCOPE, TCL_STAGE, DIRECTIONS, TITLE, TRIGGER, USER_STATEMENT
    global AUTHORIZATION_ID
    if lane not in LANE_CONFIGS:
        raise ValueError("only bounded lane2 or lane3 raw diagnostics are supported")
    cfg = LANE_CONFIGS[lane]
    ACTIVE_LANE = lane
    LANE_MASK = 1 << lane
    FIXED_MODULE = f"F{lane}"
    ROTATING_MODULE = f"R{lane}"
    FIXED_ID = str(cfg["fixed_id"])
    ROTATING_ID = str(cfg["rotating_id"])
    AUTH = ROOT / str(cfg["authorization"])
    PREVIOUS_BLOCKER = ROOT / str(cfg["blocker"])
    OUTPUT_STEM = str(cfg["output_stem"])
    SCOPE = f"{p103.SCOPE}/{cfg['scope_suffix']}"
    TCL_STAGE = f"P10_3-LANE{lane}_RAW_RETEST"
    DIRECTIONS = tuple(str(item) for item in cfg["directions"])
    TITLE = str(cfg["title"])
    TRIGGER = str(cfg["trigger"])
    USER_STATEMENT = str(cfg["user_statement"])
    AUTHORIZATION_ID = str(cfg["authorization_id"])


configure_lane(2)


def auth_input_paths() -> tuple[Path, ...]:
    return (
        p103.GOAL, p103.FREEZE, p103.WIRING, p103.INVENTORY,
        PREVIOUS_BLOCKER, ROOT / "PROJECT_CONSTRAINTS.txt", ROOT / "AGENTS.md",
        ROOT / "config/register_map/ir_axi_regs.yaml",
        ROOT / "config/hardware/p10_2_ax7020_4lane_wiring.yaml",
        ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
        ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
        ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
        ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
        ROOT / "scripts/hw/p10_program_dual_shutdown.tcl", p103.STAGE_TCL,
        ROOT / "scripts/p10_hardware_runtime.py",
        ROOT / "scripts/run_p10_3_ax7020_4lane_hardware.py",
        Path(__file__).resolve(),
    )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def direction_value(name: str) -> int:
    if name == f"f{ACTIVE_LANE}_to_r{ACTIVE_LANE}":
        return 0
    if name == f"r{ACTIVE_LANE}_to_f{ACTIVE_LANE}":
        return 1
    raise ValueError(f"direction is outside lane{ACTIVE_LANE}: {name}")


def direction_label(name: str) -> str:
    return (
        f"{FIXED_MODULE}_TO_{ROTATING_MODULE}" if direction_value(name) == 0
        else f"{ROTATING_MODULE}_TO_{FIXED_MODULE}"
    )


def build_plans() -> dict[str, list[p103.Case]]:
    plans: dict[str, list[p103.Case]] = {}
    for name in DIRECTIONS:
        direction = direction_value(name)
        sender = FIXED_MODULE if direction == 0 else ROTATING_MODULE
        receiver = ROTATING_MODULE if direction == 0 else FIXED_MODULE
        plans[name] = [
            p103.Case(f"lane{ACTIVE_LANE}_{name}_receive_only_5000ms", 11,
                      idle=5000, timeout=15_000),
            p103.Case(f"lane{ACTIVE_LANE}_{sender}_to_{receiver}_raw_64",
                      2, lane=LANE_MASK, direction=direction, rate=2,
                      rawtarget=64, spacing=1024, timeout=30_000),
            p103.Case(f"lane{ACTIVE_LANE}_{sender}_to_{receiver}_raw_1024",
                      2, lane=LANE_MASK, direction=direction, rate=2,
                      rawtarget=1024, spacing=1024, timeout=30_000),
        ]
    return plans


def validate_plans() -> list[str]:
    errors: list[str] = []
    plans = build_plans()
    if tuple(plans) != DIRECTIONS:
        errors.append(f"lane{ACTIVE_LANE} diagnostic direction order mismatch")
    for name, items in plans.items():
        expected_direction = direction_value(name)
        if len(items) != 3 or items[0].command != 11:
            errors.append(f"{name}: exact receive-only/raw64/raw1024 set required")
        raw_targets = []
        for item in items:
            try:
                item.plan_line()
            except ValueError as exc:
                errors.append(str(exc))
            errors.extend(p103.case_semantic_errors(item))
            if item.command == 2:
                raw_targets.append(item.rawtarget)
                if item.lane != LANE_MASK or item.direction != expected_direction or \
                        item.rate != 2 or item.spacing != 1024:
                    errors.append(f"{item.label}: raw lane/direction/rate/spacing mismatch")
            elif item.command == 11:
                if item.lane != 0 or item.idle != 5000:
                    errors.append(f"{item.label}: receive-only vector mismatch")
            else:
                errors.append(f"{item.label}: non-raw diagnostic command forbidden")
        if raw_targets != [64, 1024]:
            errors.append(f"{name}: exact raw target order mismatch")
    return errors


def expected_inputs() -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for path in auth_input_paths():
        if not path.is_file():
            raise FileNotFoundError(path)
        output[p103.rel(path)] = {
            "sha256": p103.sha256(path), "bytes": path.stat().st_size,
        }
    return output


def validate_static_inputs() -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors = [*p103.validate_goal_files(), *p103.validate_baseline_refs()]
    try:
        freeze, artifacts = p103.load_freeze()
    except RuntimeError as exc:
        return {}, {}, [*errors, str(exc)]
    _, inventory, intake_errors = p103.validate_wiring_inventory()
    errors.extend(intake_errors)
    errors.extend(validate_plans())
    active = inventory.get("p10_3_current_installation", {}).get("modules", {})
    if active.get(FIXED_MODULE, {}).get("small_board_id") != FIXED_ID:
        errors.append(f"{FIXED_MODULE} active identity must be {FIXED_ID}")
    if active.get(ROTATING_MODULE, {}).get("small_board_id") != ROTATING_ID:
        errors.append(f"{ROTATING_MODULE} active identity must be {ROTATING_ID}")
    if ACTIVE_LANE == 2:
        replacement = inventory.get("r2_replacement_2026_08_04", {})
        if replacement.get("removed_small_board_id") != "B0015" or \
                replacement.get("installed_small_board_id") != "B0023" or \
                replacement.get("electronic_status") != \
                "BIDIRECTIONAL_RAW_PASS_PENDING_FRAME_INTAKE":
            errors.append("R2 replacement provenance/status mismatch")
    elif ACTIVE_LANE == 3:
        replacement = inventory.get("r3_replacement_2026_08_04", {})
        if replacement.get("removed_small_board_id") != "B0017" or \
                replacement.get("installed_small_board_id") != "B0025" or \
                replacement.get("electronic_status") != \
                "PENDING_BIDIRECTIONAL_RAW_RETEST":
            errors.append("R3 replacement provenance/status mismatch")
    try:
        tcl = p103.STAGE_TCL.read_text(encoding="utf-8")
        if f"LANE{ACTIVE_LANE}_RAW_RETEST" not in tcl:
            errors.append(
                f"XSDB executor does not recognize bounded lane{ACTIVE_LANE} retest stage"
            )
        expected_inputs()
    except OSError as exc:
        errors.append(f"diagnostic input missing: {exc}")
    if p103.git("branch", "--show-current") != p103.BRANCH:
        errors.append("P10.3 branch mismatch")
    return freeze, artifacts, errors


def expected_run_id(freeze: dict[str, Any]) -> str:
    artifacts = {p103.artifact_key(item): item for item in freeze["artifacts"]}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return (
        f"p10_3_raw_{stamp}_{freeze['source_commit'][:8]}_"
        f"{artifacts['fixed:functional_bitstream']['sha256'][:8]}_"
        f"{artifacts['rotating:functional_bitstream']['sha256'][:8]}"
    )


def prepare_authorization(run_id: str | None) -> dict[str, Any]:
    if os.environ.get("NO_HARDWARE") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() not in {
                "false", "0", "no",
            }:
        raise RuntimeError("authorization preparation requires NO_HARDWARE=1 and current authorization false")
    freeze, _, errors = validate_static_inputs()
    if p103.git("status", "--porcelain"):
        errors.append("authorization preparation requires a clean worktree")
    if errors:
        raise RuntimeError("; ".join(errors))
    actual_run_id = run_id or expected_run_id(freeze)
    if not RUN_RE.fullmatch(actual_run_id):
        raise RuntimeError(f"invalid lane{ACTIVE_LANE} raw-retest run ID")
    parent = p103.git("rev-parse", "HEAD")
    plans = build_plans()
    record = {
        "schema_version": 1,
        "authorization_id": AUTHORIZATION_ID,
        "status": "AUTHORIZED",
        "scope": SCOPE,
        "branch": p103.BRANCH,
        "run_id": actual_run_id,
        "goal_sha256": p103.GOAL_SHA256,
        "artifact_source_commit": freeze["source_commit"],
        "diagnostic_runner_parent_commit": parent,
        "authorization_parent_commit": parent,
        "artifact_freeze": p103.rel(p103.FREEZE),
        "artifact_freeze_sha256": p103.sha256(p103.FREEZE),
        "artifacts": freeze["artifacts"],
        "artifact_bundle_sha256": p103.hash_text(json.dumps(
            freeze["artifacts"], sort_keys=True, separators=(",", ":")
        )),
        "inputs": expected_inputs(),
        "actual_wiring_sha256": p103.sha256(p103.WIRING),
        "module_inventory_sha256": p103.sha256(p103.INVENTORY),
        "previous_blocker": {
            "path": p103.rel(PREVIOUS_BLOCKER),
            "sha256": p103.sha256(PREVIOUS_BLOCKER),
            "bytes": PREVIOUS_BLOCKER.stat().st_size,
        },
        "part": p103.EXPECTED_PART,
        "board_binding": {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating": "AX7020-R/JTAG:210512180081",
        },
        "module_binding": p103.EXPECTED_MODULE_BINDING,
        "diagnostic_trigger": TRIGGER,
        "lane": ACTIVE_LANE,
        "lane_pair": f"{FIXED_MODULE}-{ROTATING_MODULE}",
        "allowed_lane_masks": [LANE_MASK],
        "maximum_lane_mask": LANE_MASK,
        "allowed_hardware_stages": list(DIRECTIONS),
        "tcl_stage": TCL_STAGE,
        "plan_sha256": {
            name: p103.hash_text(p103.plan_text(plans[name])) for name in DIRECTIONS
        },
        "stimulus": {
            "commands": ["receive_only_5000ms", "raw_64", "raw_1024"],
            "directions": [direction_label(name) for name in DIRECTIONS],
            "rate_select": 2,
            "raw_spacing_cycles": 1024,
            "requested_txd_high_cycles": 8,
            "phy_clock_hz": 64000000,
            "requested_txd_high_ns": 125,
            "nominal_pulse_duty_percent": 0.78125,
            "framed_traffic": False,
        },
        "runtime_limits": {
            "per_direction_stage_seconds": STAGE_TIMEOUT_SECONDS,
            "active_functional_total_seconds": (
                STAGE_TIMEOUT_SECONDS * len(DIRECTIONS)
            ),
            "wrapper_seconds": MAXIMUM_WRAPPER_RUNTIME_SECONDS,
            "formal_run_seconds": 0,
        },
        "retry_override": {
            "goal_diagnostic_limit_previously_exhausted": True,
            "new_diagnostic_run_ids_authorized": 1,
            "this_run_consumes_override": True,
            "campaign_wide_unlimited_override": False,
            "reason": TRIGGER,
        },
        "user_authorization_received_on": "2026-08-04",
        "user_authorization_statement": USER_STATEMENT,
        "campaign_standing_authorization": (
            "P10.3 allows necessary bounded diagnostics/recovery/retest after exact "
            "artifact freeze and a user-reported pre-run module replacement, with "
            "shutdown-before/after and no physical changes during the run."
        ),
        "authorization_interpretation": (
            f"One fresh immutable lane{ACTIVE_LANE} raw-only run ID covering "
            f"{', '.join(direction_label(name) for name in DIRECTIONS)}. It does "
            "not authorize the remaining P10.3 campaign or additional retries."
        ),
        "evidence_retention": {
            "mode": "BYTE_EXACT_ZIP_PLUS_COMPACT_JSON",
            "individual_run_files_committed": False,
            "archive_only_after_inner_manifest_verification": True,
        },
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": False,
        "shutdown_policy": {
            "before": True, "between_directions": True,
            "on_error": True, "on_timeout": True, "on_ctrl_c": True,
            "on_normal_exit": True, "after": True, "verify_both": True,
        },
        "forbidden": {
            "ethernet": True, "movement": True, "rotation": True,
            "realignment": True, "module_swap_during_run": True,
            "rewiring": True,
            f"lane_mask_outside_0x{LANE_MASK:X}": True,
            "framed_or_protocol_test": True, "two_hour_test": True,
            "p11": True,
        },
        "network_used": False,
        "movement": False,
        "rotation": False,
        "realignment": False,
        "rewiring_by_codex": False,
        "two_hour_test": False,
        "p11": False,
        "generated_at_utc": utc_now(),
        "consumed": False,
    }
    if ACTIVE_LANE == 2:
        record["replacement"] = {
            "logical_module": "R2", "position": "AX7020-R/J11-A",
            "removed_small_board_id": "B0015", "installed_small_board_id": "B0023",
            "source": "Direct user statement on 2026-08-04",
            "identity_independently_verified": False,
            "replacement_power_state": "NOT_STATED_BY_USER; NOT_CLAIMED",
            "codex_physical_action": False,
        }
    elif ACTIVE_LANE == 3:
        record["replacement"] = {
            "logical_module": "R3", "position": "AX7020-R/J11-B",
            "removed_small_board_id": "B0017", "installed_small_board_id": "B0025",
            "source": "Direct user statement on 2026-08-04",
            "identity_independently_verified": False,
            "replacement_power_state": "NOT_STATED_BY_USER; NOT_CLAIMED",
            "codex_physical_action": False,
        }
    p103.write_json(AUTH, record)
    return record


def validate_authorization(path: Path, run_id: str) -> tuple[
        dict[str, Any], dict[str, Path], list[str]]:
    freeze, artifacts, errors = validate_static_inputs()
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, artifacts, [*errors, f"authorization unreadable: {exc}"]
    plans = build_plans()
    expected = {
        "schema_version": 1,
        "authorization_id": AUTHORIZATION_ID,
        "status": "AUTHORIZED",
        "scope": SCOPE,
        "branch": p103.BRANCH,
        "run_id": run_id,
        "goal_sha256": p103.GOAL_SHA256,
        "artifact_source_commit": freeze.get("source_commit"),
        "artifact_freeze": p103.rel(p103.FREEZE),
        "artifact_freeze_sha256": p103.sha256(p103.FREEZE),
        "artifact_bundle_sha256": p103.hash_text(json.dumps(
            freeze.get("artifacts", []), sort_keys=True, separators=(",", ":")
        )),
        "actual_wiring_sha256": p103.sha256(p103.WIRING),
        "module_inventory_sha256": p103.sha256(p103.INVENTORY),
        "part": p103.EXPECTED_PART,
        "board_binding": {
            "fixed": "AX7020-F/JTAG:210249855178",
            "rotating": "AX7020-R/JTAG:210512180081",
        },
        "module_binding": p103.EXPECTED_MODULE_BINDING,
        "lane": ACTIVE_LANE,
        "lane_pair": f"{FIXED_MODULE}-{ROTATING_MODULE}",
        "allowed_lane_masks": [LANE_MASK],
        "maximum_lane_mask": LANE_MASK,
        "allowed_hardware_stages": list(DIRECTIONS),
        "tcl_stage": TCL_STAGE,
        "plan_sha256": {
            name: p103.hash_text(p103.plan_text(plans[name])) for name in DIRECTIONS
        },
        "runtime_limits": {
            "per_direction_stage_seconds": STAGE_TIMEOUT_SECONDS,
            "active_functional_total_seconds": (
                STAGE_TIMEOUT_SECONDS * len(DIRECTIONS)
            ),
            "wrapper_seconds": MAXIMUM_WRAPPER_RUNTIME_SECONDS,
            "formal_run_seconds": 0,
        },
        "current_run_hardware_authorization": True,
        "hardware_actions_executed": False,
        "shutdown_policy": {
            "before": True, "between_directions": True,
            "on_error": True, "on_timeout": True, "on_ctrl_c": True,
            "on_normal_exit": True, "after": True, "verify_both": True,
        },
        "forbidden": {
            "ethernet": True, "movement": True, "rotation": True,
            "realignment": True, "module_swap_during_run": True,
            "rewiring": True,
            f"lane_mask_outside_0x{LANE_MASK:X}": True,
            "framed_or_protocol_test": True, "two_hour_test": True,
            "p11": True,
        },
        "network_used": False,
        "movement": False,
        "rotation": False,
        "realignment": False,
        "rewiring_by_codex": False,
        "two_hour_test": False,
        "p11": False,
        "consumed": False,
        "evidence_retention": {
            "mode": "BYTE_EXACT_ZIP_PLUS_COMPACT_JSON",
            "individual_run_files_committed": False,
            "archive_only_after_inner_manifest_verification": True,
        },
    }
    errors.extend(
        f"authorization {key} mismatch" for key, value in expected.items()
        if record.get(key) != value
    )
    if record.get("artifacts") != freeze.get("artifacts"):
        errors.append("authorization artifact bundle differs from freeze")
    try:
        inputs = expected_inputs()
    except OSError as exc:
        inputs = {}
        errors.append(f"authorization input missing: {exc}")
    if record.get("inputs") != inputs:
        errors.append("authorization exact input set/hash/size mismatch")
    if record.get("previous_blocker") != {
            "path": p103.rel(PREVIOUS_BLOCKER),
            "sha256": p103.sha256(PREVIOUS_BLOCKER),
            "bytes": PREVIOUS_BLOCKER.stat().st_size}:
        errors.append("authorization previous blocker binding mismatch")
    if record.get("diagnostic_trigger") != TRIGGER:
        errors.append("authorization diagnostic trigger mismatch")
    if ACTIVE_LANE == 2:
        replacement = record.get("replacement", {})
        if replacement.get("removed_small_board_id") != "B0015" or \
                replacement.get("installed_small_board_id") != "B0023" or \
                replacement.get("identity_independently_verified") is not False:
            errors.append("authorization replacement binding mismatch")
    elif ACTIVE_LANE == 3:
        replacement = record.get("replacement", {})
        if replacement.get("removed_small_board_id") != "B0017" or \
                replacement.get("installed_small_board_id") != "B0025" or \
                replacement.get("identity_independently_verified") is not False:
            errors.append("authorization replacement binding mismatch")
    retry = record.get("retry_override", {})
    if retry.get("new_diagnostic_run_ids_authorized") != 1 or \
            retry.get("this_run_consumes_override") is not True or \
            retry.get("campaign_wide_unlimited_override") is not False:
        errors.append("authorization retry override is not exactly one run ID")
    if not RUN_RE.fullmatch(run_id):
        errors.append(f"unsafe lane{ACTIVE_LANE} raw-retest run ID")
    if path.resolve() != AUTH.resolve():
        errors.append(
            f"canonical lane{ACTIVE_LANE} raw-retest authorization path required"
        )
    if p103.git("branch", "--show-current") != p103.BRANCH:
        errors.append("branch mismatch")
    if p103.git("status", "--porcelain"):
        errors.append("hardware run requires a clean worktree")
    parent = str(record.get("authorization_parent_commit", ""))
    runner_parent = str(record.get("diagnostic_runner_parent_commit", ""))
    if parent != runner_parent or not p103.git_commit_exists(parent) or \
            not p103.git_is_ancestor(parent):
        errors.append("authorization parent/diagnostic runner commit mismatch")
    try:
        if p103.git("rev-parse", "HEAD^") != parent:
            errors.append("authorization must be the immediate committed child of its parent")
    except Exception:
        errors.append("authorization parent relationship unavailable")
    if not p103.file_matches_head(path):
        errors.append("authorization file is not the committed HEAD version")
    return record, artifacts, errors


def expected_case_fields(item: p103.Case) -> dict[str, int]:
    values = (
        item.command, item.expected_status, item.flags, item.lane,
        item.direction, item.rate, item.weights, item.size, item.ring,
        item.cache, item.txoff, item.rxoff, item.timeout, item.session,
        item.path, item.object, item.dropdata, item.dropack, item.unavailable,
        item.rawtarget, item.spacing, item.stale, item.initialseq,
        item.faultflags, item.idle, item.injectmask, item.injectdelay,
    )
    return dict(zip(p103.CASE_ROW_FIELDS, values))


def evaluate_direction(name: str, stage_dir: Path,
                       process: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    markers = p103.parse_markers(stage_dir / "xsdb.result.txt")
    if process.get("returncode") != 0 or process.get("timed_out"):
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("dual safe-boot marker missing")
    ledger = stage_dir / "dumps/observations.psv"
    rows: list[dict[str, Any]] = []
    if ledger.is_file():
        with ledger.open(encoding="ascii", newline="") as handle:
            rows = [p103.integer_row(row) for row in csv.DictReader(
                handle, delimiter="|"
            )]
    else:
        errors.append("observation ledger missing")

    terminal_rows = [row for row in rows
                     if str(row.get("label", "")).endswith("_endpoint_shutdown")]
    body = [row for row in rows
            if not str(row.get("label", "")).endswith("_endpoint_shutdown")]
    plan = build_plans()[name]
    if len(body) > len(plan):
        errors.append("observation ledger contains extra diagnostic cases")
    for index, row in enumerate(body):
        if index >= len(plan):
            break
        item = plan[index]
        if row.get("label") != item.label:
            errors.append(f"case order mismatch: expected {item.label}")
            continue
        for key, value in expected_case_fields(item).items():
            if row.get(key) != value:
                errors.append(f"{item.label}:{key} differs from immutable plan")
    if process.get("returncode") == 0 and not process.get("timed_out"):
        if len(body) != len(plan):
            errors.append("successful XSDB process did not execute the exact plan")
        if len(terminal_rows) != 1 or rows[-1] is not terminal_rows[0]:
            errors.append("successful XSDB process lacks one final endpoint shutdown")
        if markers.get("P10_XSDB_STAGE_RESULT") != "PASS":
            errors.append("successful XSDB process lacks stage PASS marker")
    elif markers.get("P10_XSDB_STAGE_RESULT") != "FAIL":
        errors.append("failed XSDB process lacks stage FAIL marker")

    case_results: dict[str, dict[str, Any]] = {
        item.label: {
            "status": "NOT_RUN", "command": item.command,
            "requested_raw_pulses": item.rawtarget if item.command == 2 else 0,
        } for item in plan
    }
    safety_observations: list[dict[str, Any]] = []
    for row in rows:
        label = str(row.get("label", "unknown"))
        case_errors: list[str] = []
        try:
            fixed_mail_path = Path(row["fixed_dump_path"]).resolve()
            rotating_mail_path = Path(row["rotating_dump_path"]).resolve()
            if not p103.inside(fixed_mail_path, stage_dir) or \
                    not p103.inside(rotating_mail_path, stage_dir):
                raise ValueError("mailbox dump path escaped stage")
            fixed_words = p103.parse_mailbox(fixed_mail_path)
            rotating_words = p103.parse_mailbox(rotating_mail_path)
            pair_errors, _ = p103.generic_pair(row, fixed_words, rotating_words)
            case_errors.extend(pair_errors)
            fixed_snapshot_path = stage_dir / "dumps" / f"{label}.fixed.p10_2.psv"
            rotating_snapshot_path = stage_dir / "dumps" / f"{label}.rotating.p10_2.psv"
            fixed_snapshot = p103.parse_p103(fixed_snapshot_path)
            rotating_snapshot = p103.parse_p103(rotating_snapshot_path)
            case_errors.extend(p103.snapshot_errors(label, "fixed", fixed_snapshot))
            case_errors.extend(p103.snapshot_errors(label, "rotating", rotating_snapshot))
            safety_observations.append({
                "label": label,
                "fixed_safety_fault_mask": fixed_snapshot["safety_fault_mask"],
                "rotating_safety_fault_mask": rotating_snapshot["safety_fault_mask"],
                f"fixed_lane{ACTIVE_LANE}":
                    fixed_snapshot["modules"][ACTIVE_LANE],
                f"rotating_lane{ACTIVE_LANE}":
                    rotating_snapshot["modules"][4 + ACTIVE_LANE],
            })
            if label in case_results:
                result = case_results[label]
                result.update({
                    "fixed_command_status": fixed_words[8],
                    "rotating_command_status": rotating_words[8],
                    "fixed_service_state": fixed_words[3],
                    "rotating_service_state": rotating_words[3],
                    "fixed_mailbox": p103.rel(fixed_mail_path),
                    "rotating_mailbox": p103.rel(rotating_mail_path),
                    "fixed_snapshot": p103.rel(fixed_snapshot_path),
                    "rotating_snapshot": p103.rel(rotating_snapshot_path),
                })
                if row["command"] == 2:
                    sender_role = "fixed" if row["direction"] == 0 else "rotating"
                    receiver_role = "rotating" if row["direction"] == 0 else "fixed"
                    sender_snapshot = fixed_snapshot if sender_role == "fixed" else rotating_snapshot
                    receiver_snapshot = rotating_snapshot if receiver_role == "rotating" else fixed_snapshot
                    sender_index = (
                        ACTIVE_LANE if sender_role == "fixed" else 4 + ACTIVE_LANE
                    )
                    receiver_index = (
                        4 + ACTIVE_LANE if receiver_role == "rotating"
                        else ACTIVE_LANE
                    )
                    sender_tx = sender_snapshot["modules"][sender_index]["physical_tx"]
                    receiver_raw = receiver_snapshot["modules"][receiver_index]["raw_rx"]
                    target = row["rawtarget"]
                    result.update({
                        "sender_role": sender_role,
                        "receiver_role": receiver_role,
                        "sender_module": (
                            FIXED_MODULE if sender_role == "fixed"
                            else ROTATING_MODULE
                        ),
                        "receiver_module": (
                            ROTATING_MODULE if receiver_role == "rotating"
                            else FIXED_MODULE
                        ),
                        "sender_physical_tx_count": sender_tx,
                        "receiver_raw_rx_count": receiver_raw,
                        "receiver_allowed_raw_count_min": target,
                        "receiver_allowed_raw_count_max": target + 8,
                        "tx_high_max_cycles": sender_snapshot["modules"][sender_index]["tx_high_max"],
                        "rolling_duty_high_max_cycles": sender_snapshot["modules"][sender_index]["duty_high_max"],
                    })
                    if sender_tx != target:
                        case_errors.append(f"{label}: physical TX count {sender_tx} != {target}")
                    if not target <= receiver_raw <= target + 8:
                        case_errors.append(
                            f"{label}: remote raw count {receiver_raw} outside {target}..{target + 8}"
                        )
                if fixed_words[8] != 0 or rotating_words[8] != 0 or \
                        fixed_words[3] != 4 or rotating_words[3] != 4:
                    case_errors.append(f"{label}: endpoint command did not finish cleanly")
                result["errors"] = case_errors
                result["status"] = "PASS" if not case_errors else "FAIL"
        except (OSError, ValueError, KeyError, struct.error) as exc:
            case_errors.append(f"{label}: {exc}")
            if label in case_results:
                case_results[label]["errors"] = case_errors
                case_results[label]["status"] = "FAIL"
        errors.extend(case_errors)

    raw_results = [case_results[item.label]["status"]
                   for item in plan if item.command == 2]
    receive_only_status = case_results[plan[0].label]["status"]
    endpoint_shutdown = (
        len(terminal_rows) == 1 and
        markers.get("P10_ENDPOINT_SHUTDOWN_FIXED") == "PASS" and
        markers.get("P10_ENDPOINT_SHUTDOWN_ROTATING") == "PASS"
    )
    if not endpoint_shutdown and process.get("returncode") == 0:
        errors.append("endpoint shutdown command not evidenced")
    status = "PASS" if (
        not errors and receive_only_status == "PASS" and
        raw_results == ["PASS", "PASS"] and endpoint_shutdown
    ) else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": f"P10_3-HW-LANE{ACTIVE_LANE}-RAW-{name.upper()}",
        "status": status,
        "evidence_class": "RAW_PHYSICAL_ONLY",
        "direction": direction_label(name),
        "lane": ACTIVE_LANE,
        "lane_mask": f"0x{LANE_MASK:X}",
        "module_binding": {FIXED_MODULE: FIXED_ID, ROTATING_MODULE: ROTATING_ID},
        "process": process,
        "markers": markers,
        "observation_count": len(rows),
        "receive_only_status": receive_only_status,
        "case_results": case_results,
        "endpoint_shutdown_command": "PASS" if endpoint_shutdown else "NOT_CONFIRMED",
        "safety_observations": safety_observations,
        "errors": errors,
        "generated_at_utc": utc_now(),
    }
    p103.write_json(stage_dir / "stage_summary.json", summary)
    return summary


def invoke_direction(name: str, run_root: Path, auth: Path,
                     artifacts: dict[str, Path], ps7: dict[str, Path],
                     env: dict[str, str], abort: Path) -> dict[str, Any]:
    stage_dir = run_root / name
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=True)
    plan = stage_dir / f"{name}.plan"
    p103.write_text(plan, p103.plan_text(build_plans()[name]))
    result = stage_dir / "xsdb.result.txt"
    command = [
        str(p103.XSDB), str(p103.STAGE_TCL), "tcp:localhost:3121",
        p103.EXPECTED_FIXED_SERIAL, p103.EXPECTED_ROTATING_SERIAL,
        str(artifacts["fixed:functional_bitstream"]),
        str(artifacts["rotating:functional_bitstream"]),
        str(artifacts["fixed:elf"]), str(artifacts["rotating:elf"]),
        str(ps7["fixed"]), str(ps7["rotating"]), str(plan), str(dump_dir),
        str(abort), str(result), TCL_STAGE, str(auth), run_root.name,
        f"0x{p103.EXPECTED_PL_BUILD['fixed']:08X}",
        f"0x{p103.EXPECTED_PL_BUILD['rotating']:08X}",
    ]
    process = p103.run_bounded(
        command, stage_dir / "xsdb.stdout.log", stage_dir / "xsdb.stderr.log",
        STAGE_TIMEOUT_SECONDS, env,
    )
    return evaluate_direction(name, stage_dir, process)


def initialize_run_root(run_root: Path, auth: Path,
                        record: dict[str, Any]) -> dict[str, Path]:
    run_root.mkdir(parents=True, exist_ok=False)
    for name in ("authorization", "artifacts/fixed", "artifacts/rotating",
                 "wiring", *DIRECTIONS, "shutdown", "raw_logs", "final"):
        (run_root / name).mkdir(parents=True, exist_ok=False)
    copies = (
        (auth, run_root / "authorization/immutable_authorization.json"),
        (p103.GOAL, run_root / "authorization/goal.md"),
        (p103.FREEZE, run_root / "artifacts/artifact_freeze.json"),
        (p103.WIRING, run_root / "wiring/p10_3_actual_wiring.yaml"),
        (p103.INVENTORY, run_root / "wiring/tfdu_module_inventory.yaml"),
        (PREVIOUS_BLOCKER,
         run_root / f"authorization/previous_lane{ACTIVE_LANE}_blocker.json"),
    )
    manifest = []
    for source, destination in copies:
        shutil.copy2(source, destination)
        if p103.sha256(source) != p103.sha256(destination):
            raise RuntimeError(f"immutable input copy mismatch: {destination}")
        manifest.append({
            "source": str(source),
            "path": destination.relative_to(run_root).as_posix(),
            "sha256": p103.sha256(destination),
            "bytes": destination.stat().st_size,
        })
    p103.write_json(run_root / "authorization/immutable_input_copy_manifest.json", {
        "schema_version": 1, "status": "PASS", "files": manifest,
        "generated_at_utc": utc_now(),
    })
    p103.write_text(
        run_root / "authorization/PHYSICAL_AND_SCOPE_ATTESTATION.txt",
        f"DIAGNOSTIC_LANE={ACTIVE_LANE}\n"
        f"DIAGNOSTIC_DIRECTIONS={','.join(direction_label(name) for name in DIRECTIONS)}\n"
        f"MODULE_PAIR={FIXED_MODULE}:{FIXED_ID},{ROTATING_MODULE}:{ROTATING_ID}\n"
        "CODEX_PHYSICAL_ACTION=false\nETHERNET=false\nMOVEMENT=false\n"
        "ROTATION=false\nREALIGNMENT=false\nREWIRING_DURING_RUN=false\n"
        f"LANE_MASK=0x{LANE_MASK:X}\nFRAMED_TRAFFIC=false\nP11=false\n",
    )
    artifacts = {p103.artifact_key(item): (ROOT / item["path"]).resolve()
                 for item in record["artifacts"]}
    derived = []
    ps7: dict[str, Path] = {}
    for role in ("fixed", "rotating"):
        destination = run_root / f"artifacts/{role}/ps7_init.tcl"
        derived.append(p103.extract_ps7_init(artifacts[f"{role}:xsa"], destination))
        ps7[role] = destination
    p103.write_json(run_root / "artifacts/derived_artifact_manifest.json", derived)
    p103.write_json(run_root / "artifacts/authorized_artifact_manifest.json", {
        "schema_version": 1, "status": "PASS",
        "artifact_source_commit": record["artifact_source_commit"],
        "artifact_bundle_sha256": record["artifact_bundle_sha256"],
        "artifacts": record["artifacts"],
    })
    return ps7


def render_report(summary: dict[str, Any]) -> str:
    rows = []
    for direction in DIRECTIONS:
        stage = next((item for item in summary["directions"]
                      if item["direction"] == direction_label(direction)), None)
        if stage is None:
            rows.append(f"| {direction.upper()} | NOT_RUN | - | - | - |")
            continue
        for result in stage["case_results"].values():
            if result.get("command") != 2:
                continue
            rows.append(
                f"| {stage['direction']} / {result['requested_raw_pulses']} | "
                f"{result['status']} | {result.get('sender_physical_tx_count', '-')} | "
                f"{result.get('receiver_raw_rx_count', '-')} | "
                f"{result.get('tx_high_max_cycles', '-')} |"
            )
    artifact_lines = []
    for item in summary["artifacts"]:
        if item["kind"] in {"functional_bitstream", "elf", "shutdown_bitstream"}:
            artifact_lines.append(
                f"- {item['role']} {item['kind']}: `{item['sha256']}` — `{item['path']}`"
            )
    return "\n".join([
        f"# P10.3 {TITLE}",
        "",
        f"- Result: `{summary['status']}`",
        "- Evidence class: `RAW_PHYSICAL_ONLY`",
        f"- Run ID: `{summary['run_id']}`",
        f"- Active pair: `{FIXED_MODULE}={FIXED_ID}` ↔ "
        f"`{ROTATING_MODULE}={ROTATING_ID}`",
        f"- Lane mask used: `0x{LANE_MASK:X}`",
        "",
        "| Direction / requested pulses | Result | Sender final-path TX count | Remote raw RX count | Max TX-high cycles |",
        "|---|---|---:|---:|---:|",
        *rows,
        "",
        f"Shutdown fixed: `{summary['SHUTDOWN_FIXED']}`; rotating: `{summary['SHUTDOWN_ROTATING']}`.",
        "",
        "## Immutable artifacts",
        "",
        *artifact_lines,
        "",
        "## Scope boundary",
        "",
        f"This result concerns only the authorized lane{ACTIVE_LANE} raw pulse "
        "direction(s). It does not constitute framed-data, ARQ/SACK, DMA, "
        "streaming, four-lane, external electrical, module-health, P11, rotating, "
        "or final-product acceptance. Existing opposite-direction failures remain "
        "immutable and are not overwritten.",
        "",
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lane", type=int, choices=tuple(LANE_CONFIGS), default=2)
    parser.add_argument("--prepare-authorization", action="store_true")
    parser.add_argument("--run-id")
    parser.add_argument("--authorization", type=Path)
    parser.add_argument("--execute-hardware", action="store_true")
    args = parser.parse_args(argv)
    configure_lane(args.lane)
    if args.prepare_authorization:
        try:
            record = prepare_authorization(args.run_id)
        except Exception as exc:
            print(
                f"P10_3_LANE{ACTIVE_LANE}_RAW_AUTHORIZATION=FAIL\nERROR={exc}",
                file=sys.stderr,
            )
            return 2
        print(f"P10_3_LANE{ACTIVE_LANE}_RAW_AUTHORIZATION=PASS")
        print(f"P10_3_LANE{ACTIVE_LANE}_RAW_RUN_ID={record['run_id']}")
        print(
            f"P10_3_LANE{ACTIVE_LANE}_RAW_AUTHORIZATION_PATH={p103.rel(AUTH)}"
        )
        print(
            f"P10_3_LANE{ACTIVE_LANE}_RAW_AUTHORIZATION_SHA256={p103.sha256(AUTH)}"
        )
        return 0
    if not args.execute_hardware or not args.run_id:
        print(
            f"P10_3_LANE{ACTIVE_LANE}_RAW_RUNNER_REFUSED="
            "PREPARE_OR_EXPLICIT_HARDWARE_RUN_REQUIRED"
        )
        return 3

    auth = (args.authorization or AUTH).resolve()
    record, artifacts, errors = validate_authorization(auth, args.run_id)
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "true":
        errors.append("NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required")
    run_root = HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("run ID directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors},
                         indent=2, ensure_ascii=False), file=sys.stderr)
        return 3

    try:
        ps7 = initialize_run_root(run_root, auth, record)
    except Exception as exc:
        print(
            f"P10_3_LANE{ACTIVE_LANE}_RAW_INITIALIZATION=FAIL\nERROR={exc}",
            file=sys.stderr,
        )
        return 3
    abort = run_root / "authorization/ABORT_NOW.txt"
    env = {
        **os.environ,
        "NO_HARDWARE": "0",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
        "RF_COMM_P10_HW_AUTH": "P10_FASTTRACK_IMMUTABLE_AUTHORIZED",
    }
    server_proc = None
    shutdowns: list[dict[str, Any]] = []
    direction_results: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    hardware_actions = False
    try:
        server_proc, server = p103.start_hw_server(run_root / "raw_logs")
        p103.write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server unavailable"))
        hardware_actions = True
        initial = p103.guarded_shutdown(run_root, auth, artifacts,
                                        "initial_shutdown", env)
        shutdowns.append(initial)
        if initial["status"] != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for name in DIRECTIONS:
            before = p103.guarded_shutdown(run_root, auth, artifacts,
                                           f"{name}_before", env)
            shutdowns.append(before)
            if before["status"] != "PASS":
                raise RuntimeError(f"{name} shutdown-before unconfirmed")
            result: dict[str, Any] | None = None
            stage_exception: BaseException | None = None
            try:
                result = invoke_direction(name, run_root, auth, artifacts,
                                          ps7, env, abort)
                direction_results.append(result)
            except BaseException as exc:
                stage_exception = exc
            finally:
                after = p103.guarded_shutdown(run_root, auth, artifacts,
                                              f"{name}_after", env)
                shutdowns.append(after)
            if after["status"] != "PASS":
                raise RuntimeError(f"{name} shutdown-after unconfirmed")
            if stage_exception is not None:
                if isinstance(stage_exception, KeyboardInterrupt):
                    raise KeyboardInterrupt from stage_exception
                raise RuntimeError(f"{name} wrapper exception: {stage_exception}")
            # When multiple directions are authorized, deliberately continue
            # after a cleanly contained diagnostic FAIL.  Every transition is
            # independently shutdown-bound.
            assert result is not None
        final = p103.guarded_shutdown(run_root, auth, artifacts,
                                      "final_shutdown", env)
        shutdowns.append(final)
        if final["status"] != "PASS":
            raise RuntimeError("final dual shutdown unconfirmed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except Exception as exc:
        campaign_errors.append(str(exc))
    finally:
        if hardware_actions:
            emergency = p103.guarded_shutdown(run_root, auth, artifacts,
                                              "finally_emergency", env)
            shutdowns.append(emergency)
            if emergency["status"] != "PASS":
                campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            try:
                p103.terminate_tree(server_proc)
            except Exception as exc:
                campaign_errors.append(f"owned hw_server termination failed: {exc}")

    all_shutdown = bool(shutdowns) and all(
        item.get("status") == "PASS" for item in shutdowns
    )
    all_authorized_directions = len(direction_results) == len(DIRECTIONS) and all(
        item.get("status") == "PASS" for item in direction_results
    )
    status = "PASS" if (
        all_shutdown and all_authorized_directions and not campaign_errors
    ) else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": f"P10_3-HW-LANE{ACTIVE_LANE}-RAW-CONNECTIVITY-RETEST",
        "status": status,
        "evidence_class": "RAW_PHYSICAL_ONLY",
        "run_id": args.run_id,
        "scope": SCOPE,
        "goal_sha256": p103.GOAL_SHA256,
        "artifact_source_commit": record["artifact_source_commit"],
        "artifact_freeze_sha256": record["artifact_freeze_sha256"],
        "artifact_bundle_sha256": record["artifact_bundle_sha256"],
        "artifacts": record["artifacts"],
        "board_binding": record["board_binding"],
        "module_binding": record["module_binding"],
        "diagnostic_trigger": record["diagnostic_trigger"],
        "lane": ACTIVE_LANE,
        "lane_pair": f"{FIXED_MODULE}-{ROTATING_MODULE}",
        "maximum_lane_mask_authorized": f"0x{LANE_MASK:X}",
        "maximum_lane_mask_used": f"0x{LANE_MASK:X}" if direction_results else "0x0",
        "directions": direction_results,
        "hardware_actions_executed": hardware_actions,
        "current_run_hardware_authorization": False,
        "authorization_consumed": True,
        "network_used": False,
        "movement": False,
        "rotation": False,
        "realignment": False,
        "rewiring_by_codex": False,
        "framed_traffic": False,
        "two_hour_test": False,
        "p11": False,
        "shutdowns": shutdowns,
        "SHUTDOWN_FIXED": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_FIXED") == "PASS" for item in shutdowns
        ) else "FAIL",
        "SHUTDOWN_ROTATING": "PASS" if all_shutdown and all(
            item.get("SHUTDOWN_ROTATING") == "PASS" for item in shutdowns
        ) else "FAIL",
        "scope_boundary": (
            f"Raw lane{ACTIVE_LANE} physical-connectivity evidence for the explicitly "
            "authorized direction(s) only; no framed, "
            "protocol, DMA, streaming, four-lane, external electrical, module-health, "
            "P11, rotating, or final-product acceptance."
        ),
        "campaign_status": "P10_3_REMAINS_IN_PROGRESS",
        "errors": campaign_errors,
        "generated_at_utc": utc_now(),
    }
    if "replacement" in record:
        summary["replacement"] = record["replacement"]
    p103.write_json(run_root / "final/orchestrator_result.json", summary)
    p103.evidence_manifest(run_root, status)
    manifest_errors = p103.verify_evidence_manifest(run_root)
    if manifest_errors:
        status = "FAIL"
        summary["status"] = "FAIL"
        summary["errors"].extend(manifest_errors)
        p103.write_json(run_root / "final/orchestrator_result.json", summary)
        p103.evidence_manifest(run_root, status)
        manifest_errors = p103.verify_evidence_manifest(run_root)

    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    generated = dict(summary)
    generated.update({
        "status": status,
        "raw_result": p103.rel(run_root / "final/orchestrator_result.json"),
        "raw_result_sha256": p103.sha256(run_root / "final/orchestrator_result.json"),
        "run_evidence_manifest": p103.rel(manifest_path),
        "run_evidence_manifest_sha256": p103.sha256(manifest_path),
        "manifest_verification": "PASS" if not manifest_errors else "FAIL",
        "manifest_errors": manifest_errors,
    })
    GENERATED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)
    generated_json = GENERATED / f"{OUTPUT_STEM}.json"
    generated_md = GENERATED / f"{OUTPUT_STEM}.md"
    report = REPORTS / f"{OUTPUT_STEM}_{args.run_id}.md"
    p103.write_json(generated_json, generated)
    report_text = render_report(generated)
    p103.write_text(generated_md, report_text)
    p103.write_text(report, report_text)

    consumed = dict(record)
    consumed.update({
        "status": f"CONSUMED_AFTER_LANE{ACTIVE_LANE}_RAW_RETEST_{status}",
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": hardware_actions,
        "consumed": True,
        "consumed_at_utc": utc_now(),
        "result": p103.rel(generated_json),
        "run_evidence": p103.rel(run_root / "final/orchestrator_result.json"),
    })
    p103.write_json(AUTH, consumed)
    print(f"P10_3_LANE{ACTIVE_LANE}_RAW_CONNECTIVITY={status}")
    print(f"P10_3_LANE{ACTIVE_LANE}_RAW_RUN_ID={args.run_id}")
    print(f"SHUTDOWN_FIXED={generated['SHUTDOWN_FIXED']}")
    print(f"SHUTDOWN_ROTATING={generated['SHUTDOWN_ROTATING']}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
