#!/usr/bin/env python3
"""Generate a deterministic, fully bound P7 hardware sequence plan offline.

This generator never launches Vivado, XSDB, a P7 safe wrapper, or any hardware
process.  It does not read or set ``RF_COMM_HW_AUTH``.  It only validates a
clean frozen offline checkpoint, writes deterministic inputs/transaction
bundles and user-authorized stage binding files, assembles either the exact
66-stage formal plan or the explicitly zero-coverage diagnostic suffix plan,
and calls ``validate_sequence_plan`` locally.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import p7_hardware_safety as safety  # noqa: E402
import p7_jtag_backend as jtag_backend  # noqa: E402
import run_p7_authorized_hardware_sequence as sequence  # noqa: E402

HW_DIR = (sequence.ROOT / "scripts" / "hw").resolve(strict=False)
if str(HW_DIR) not in sys.path:
    sys.path.insert(0, str(HW_DIR))

import run_p7_jtag_axi_stage_safe as jtag_safe_wrapper  # noqa: E402
import run_p7_ps_application_stage_safe as ps_safe_wrapper  # noqa: E402


ROOT = sequence.ROOT
AUTH_ROOT = (ROOT / ".hardware_authorization").resolve(strict=False)
BUILD_ROOT = (ROOT / "build").resolve(strict=False)
HARDWARE_ROOT = sequence.HARDWARE_ROOT
GENERATOR_SCHEMA = "rf-comm-p7-authorized-sequence-generator-v1"
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{2,63}$")
COUNTS_PER_SECOND = 333_333_343
CANONICAL_AXI_BASE = 0x43C00000
DEFAULT_P6_SESSION = 0x2201
PS_SEED_BYTES = 247
CANONICAL_BOARD_ID = "210512180081"
CANONICAL_PART = "xc7z010clg400-1"
CANONICAL_TARGET = "localhost:3121/xilinx_tcf/Digilent/210512180081"
CANONICAL_HW_SERVER_URL = "localhost:3121"
CANONICAL_JTAG_FREQUENCY_HZ = 1_000_000


ARTIFACT_ARGUMENTS = (
    "goal_plan",
    "jtag_bitstream",
    "jtag_ltx",
    "ps_bitstream",
    "xsa",
    "elf",
    "jtag_profile",
    "ps_functional_profile",
    "ps_stationary_profile",
    "active_xdc",
    "pinmap",
    "register_map",
    "shutdown_bitstream",
    "ps7_init",
    "p6_build_summary",
    "p7_build_summary",
    "core_readiness_attestation",
    "active_profile",
    "lane1_promotion_summary",
)


@dataclass(frozen=True)
class Artifact:
    path: Path
    sha256: str


@dataclass(frozen=True)
class StageSpec:
    index: int
    stage_id: str
    group: str
    risk_index: int
    case: dict[str, Any]
    kind: str
    mode: str
    pattern: str
    max_runtime_sec: int
    preflight_timeout_sec: int
    stage_timeout_sec: int | None
    shutdown_timeout_sec: int
    wrapper_timeout_sec: int


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    return safety.sha256_file(path)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    if path.exists() or partial.exists():
        raise RuntimeError(f"refusing to overwrite generated file: {path}")
    try:
        with partial.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    finally:
        if partial.exists():
            partial.unlink()


def atomic_write_text(path: Path, text: str) -> None:
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def path_inside(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except ValueError:
        return False


def policy_slug(policy: str) -> str:
    return {
        "LANE0_ONLY": "l0",
        "LANE1_ONLY": "l1",
        "STRIPE_ROUND_ROBIN": "rr",
        "REPLICATE_0X3": "rep3",
    }[policy]


def size_slug(size: int) -> str:
    return {4096: "4k", 65_536: "64k", 1_048_576: "1m"}.get(size, str(size))


def pattern_slug(pattern: str) -> str:
    return {
        "counter": "counter",
        "prbs15": "prbs15",
        "deterministic_random": "random",
        "binary_all_byte_values_repeated": "all_bytes",
    }[pattern]


def build_stage_specs() -> list[StageSpec]:
    specs: list[StageSpec] = []
    for index, contract in enumerate(sequence.expected_stage_contracts(), 1):
        group = str(contract["group"])
        case = dict(contract["case"])
        if group == "safe_idle":
            stage_id = "p7_safe_idle"
            kind, mode, pattern = "jtag", "safe-idle", "none"
            runtime, preflight, stage_timeout, shutdown = 600, 30, 90, 60
        elif group == "p6_frame_regression":
            mask = int(case["lane_mask"])
            stage_id = f"p7_p6_frame_regression_m{mask}"
            kind, mode, pattern = "jtag", "rfap", "counter"
            runtime, preflight, stage_timeout, shutdown = 960, 60, 550, 60
        elif group == "fragment_boundary":
            length = int(case["object_size"])
            policy = str(case["lane_policy"])
            stage_id = f"p7_fragment_boundary_{length}_{policy_slug(policy)}"
            kind, mode = "jtag", "rfap"
            pattern = "counter" if length == 0 else "binary_all_byte_values_repeated"
            runtime, preflight, stage_timeout, shutdown = 960, 60, 550, 60
        elif group == "large_object_jtag":
            length = int(case["object_size"])
            policy = str(case["lane_policy"])
            pattern = str(case["pattern"])
            stage_id = (
                f"p7_large_jtag_{size_slug(length)}_{policy_slug(policy)}_{pattern_slug(pattern)}"
            )
            kind, mode = "jtag", "rfap"
            # A 1 MiB transaction is about 1,073,038 bounded operations and
            # needs the separately authorized 1800 s global ceiling at 1 MHz.
            # It is not a timed stationary service run.
            if length == 1_048_576:
                runtime, preflight, stage_timeout, shutdown = 1800, 60, 1400, 60
            else:
                runtime, preflight, stage_timeout, shutdown = 960, 60, 550, 60
        else:
            mode = {
                "ps_functional": "functional",
                "ps_fault": "fault-fallback",
                "ps_abort": "abort-restart",
                "ps_queue": "queue",
                "ps_stationary": "stationary",
            }[group]
            stage_id = f"p7_ps_{mode.replace('-', '_')}"
            kind, pattern = "ps", "deterministic_seed"
            runtime = 1800 if group == "ps_stationary" else 900
            preflight, stage_timeout, shutdown = 60, None, 60
        if kind == "jtag":
            # The child JTAG wrapper's --max-runtime-sec is a global ceiling
            # that already includes every phase, all four containment
            # allowances, and the independent other-overhead guard.
            wrapper_timeout = runtime + jtag_backend.JTAG_OUTER_WRAPPER_GRACE_SECONDS
        else:
            # PS --max-runtime-sec is the service/candidate window, not the
            # whole wrapper.  Preserve the exact 1800 s stationary active
            # window while independently bounding setup, evidence reap,
            # shutdown phases, containment, and outer orchestration.
            minimum_outer = int(
                ps_safe_wrapper.ps_wrapper_wall_budget(
                    mode=mode,
                    max_runtime_sec=runtime,
                    preflight_timeout_sec=preflight,
                    shutdown_timeout_sec=shutdown,
                )["minimum_outer_wrapper_timeout_seconds"]
            )
            wrapper_timeout = ((minimum_outer + 29) // 30) * 30
        specs.append(
            StageSpec(
                index=index,
                stage_id=stage_id,
                group=group,
                risk_index=int(contract["risk_index"]),
                case=case,
                kind=kind,
                mode=mode,
                pattern=pattern,
                max_runtime_sec=runtime,
                preflight_timeout_sec=preflight,
                stage_timeout_sec=stage_timeout,
                shutdown_timeout_sec=shutdown,
                wrapper_timeout_sec=wrapper_timeout,
            )
        )
    return specs


def validate_stage_specs(specs: list[StageSpec]) -> None:
    expected = sequence.expected_stage_contracts()
    if len(specs) != len(expected) or len(specs) != 66:
        raise ValueError("stage specification count must be exactly 66")
    ids = [spec.stage_id for spec in specs]
    if len(set(ids)) != len(ids):
        raise ValueError("stage specification ids are not unique")
    for spec, contract in zip(specs, expected):
        if not sequence.STAGE_ID_RE.fullmatch(spec.stage_id):
            raise ValueError(
                f"stage id violates the child-wrapper 64-character contract: {spec.stage_id}"
            )
        if not jtag_safe_wrapper.STAGE_NAME_RE.fullmatch(
            spec.stage_id
        ) or not ps_safe_wrapper.STAGE_NAME_RE.fullmatch(spec.stage_id):
            raise ValueError(f"stage id is not accepted by both safe wrappers: {spec.stage_id}")
        if {
            "group": spec.group,
            "risk_index": spec.risk_index,
            "case": spec.case,
        } != contract:
            raise ValueError(f"stage specification contract mismatch: {spec.stage_id}")
        if spec.kind == "jtag":
            if spec.stage_timeout_sec is None:
                raise ValueError(f"JTAG stage timeout is missing: {spec.stage_id}")
            if spec.mode == "safe-idle":
                operation_count = 13
            else:
                object_size = (
                    4096
                    if spec.group == "p6_frame_regression"
                    else int(spec.case["object_size"])
                )
                operation_count = jtag_backend.transaction_shape(object_size)["operation_count"]
            feasibility = jtag_backend.runtime_feasibility(
                operation_count,
                jtag_frequency_hz=CANONICAL_JTAG_FREQUENCY_HZ,
                authorized_runtime_sec=spec.max_runtime_sec,
                preflight_timeout_sec=spec.preflight_timeout_sec,
                shutdown_timeout_sec=spec.shutdown_timeout_sec,
                configured_stage_timeout_sec=spec.stage_timeout_sec,
            )
            if not feasibility["global_runtime_budget"]["feasible"]:
                raise ValueError(f"JTAG stage global runtime budget is infeasible: {spec.stage_id}")
            minimum_outer = (
                spec.max_runtime_sec + jtag_backend.JTAG_OUTER_WRAPPER_GRACE_SECONDS
            )
        else:
            wall_budget = ps_safe_wrapper.ps_wrapper_wall_budget(
                mode=spec.mode,
                max_runtime_sec=spec.max_runtime_sec,
                preflight_timeout_sec=spec.preflight_timeout_sec,
                shutdown_timeout_sec=spec.shutdown_timeout_sec,
            )
            minimum_outer = int(wall_budget["minimum_outer_wrapper_timeout_seconds"])
        if spec.wrapper_timeout_sec < minimum_outer:
            raise ValueError(
                f"outer wrapper timeout is below the independent wall bound: {spec.stage_id} "
                f"configured={spec.wrapper_timeout_sec} required={minimum_outer}"
            )


def select_stage_specs(
    specs: list[StageSpec], *, diagnostic_suffix55: bool
) -> list[StageSpec]:
    if not diagnostic_suffix55:
        return list(specs)
    wanted = set(sequence.DIAGNOSTIC_FULL_STAGE_ORDINALS)
    selected = [spec for spec in specs if spec.index in wanted]
    if [spec.index for spec in selected] != list(sequence.DIAGNOSTIC_FULL_STAGE_ORDINALS):
        raise ValueError("diagnostic suffix selection must be exactly full ordinals 1--4 and 55--65")
    if len(selected) != 15 or any(spec.group == "ps_stationary" for spec in selected):
        raise ValueError("diagnostic suffix must contain 15 stages and exclude stationary")
    return selected


def patterned_data(pattern: str, size: int, salt: int) -> bytes:
    if pattern == "counter":
        return bytes((index + salt) & 0xFF for index in range(size))
    if pattern == "binary_all_byte_values_repeated":
        return bytes(range(256)) * (size // 256) + bytes(range(size % 256))
    if pattern == "prbs15":
        state = ((salt << 7) ^ 0x4A6D) & 0x7FFF or 1
        output = bytearray(size)
        for index in range(size):
            value = 0
            for bit in range(8):
                value |= (state & 1) << bit
                feedback = ((state >> 14) ^ (state >> 13)) & 1
                state = ((state << 1) & 0x7FFF) | feedback
            output[index] = value
        return bytes(output)
    if pattern == "deterministic_random":
        seed = hashlib.sha256(
            b"RF_COMM_P7_SEQUENCE_INPUT_V1\x00" + salt.to_bytes(4, "little")
        ).digest()
        return hashlib.shake_256(seed).digest(size)
    raise ValueError(f"unsupported deterministic payload pattern: {pattern}")


def write_safe_idle_transaction(path: Path, axi_base: int = CANONICAL_AXI_BASE) -> None:
    addresses = {
        "SAFE_STATUS": 0x104,
        "SAFE_TX_COUNT": 0x12C,
        "SAFE_RX_GOOD_L0": 0x130,
        "SAFE_RX_GOOD_L1": 0x134,
        "SAFE_CRC_BAD": 0x138,
        "SAFE_PAYLOAD_MISMATCH": 0x13C,
        "SAFE_RETRY_EXHAUSTED": 0x144,
        "SAFE_TX_FAIL": 0x148,
        "SAFE_TXD_HIGH_MAX": 0x14C,
        "SAFE_DUTY_VIOLATION": 0x150,
        "SAFE_ERROR_CODE": 0x160,
        "SAFE_STICKY_ERROR": 0x164,
    }
    lines = ["P7_JTAG_AXI_TRANSACTIONS_V1", "META EVIDENCE_KIND safe_idle"]
    for key, offset in addresses.items():
        mask = 0xE8 if key == "SAFE_STATUS" else 0xFFFFFFFF
        lines.append(f"ASSERT32 0x{axi_base + offset:08x} 0x{mask:08x} 0x00000000 {key}")
    lines.extend([f"W32 0x{axi_base + 0x100:08x} 0x00000030", "END", ""])
    atomic_write_text(path, "\n".join(lines))


def git_state() -> tuple[str | None, list[str], str | None]:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
        status = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, [], str(exc)
    if head.returncode != 0 or status.returncode != 0:
        return None, [], (head.stderr + status.stderr).strip() or "git state command failed"
    value = head.stdout.strip().lower()
    dirty = [line for line in status.stdout.splitlines() if line.strip()]
    return value, dirty, None


def classify_dirty_entries(entries: list[str]) -> tuple[list[str], list[str]]:
    """Allow only post-gate generated evidence; reject every source/hardware path."""

    allowed: list[str] = []
    rejected: list[str] = []
    for entry in entries:
        if len(entry) < 4:
            rejected.append(entry)
            continue
        payload = entry[3:].strip()
        # A rename/copy is safe only if both the source and destination are
        # generated evidence.  Quoted/escaped ambiguity is rejected closed.
        paths = payload.split(" -> ")
        normalized: list[str] = []
        ambiguous = False
        for raw_path in paths:
            value = raw_path.strip()
            if value.startswith('"') or value.endswith('"'):
                ambiguous = True
                break
            normalized.append(value.replace("\\", "/"))
        if (
            not ambiguous
            and normalized
            and all(path.startswith("evidence/generated/") for path in normalized)
        ):
            allowed.append(entry)
        else:
            rejected.append(entry)
    return allowed, rejected


def artifact_from_args(args: argparse.Namespace, name: str) -> Artifact:
    path = sequence.resolve_path(str(getattr(args, name)))
    expected = str(getattr(args, f"{name}_sha256")).lower()
    if not sequence.SHA256_RE.fullmatch(expected):
        raise ValueError(f"{name} SHA256 is malformed")
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{name} must be an existing regular non-symlink file: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError(f"{name} SHA256 mismatch: expected={expected} actual={actual}")
    return Artifact(path=path, sha256=expected)


def load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} JSON is invalid: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def validate_bound_metadata(artifacts: Mapping[str, Artifact]) -> None:
    functional = load_json(artifacts["ps_functional_profile"].path, "functional profile")
    if (
        functional.get("max_runtime_sec") != 900
        or functional.get("lane_count") != 2
        or functional.get("max_lane_mask") != "0x3"
        or functional.get("network_required") is not False
        or functional.get("motion_required") is not False
        or functional.get("shutdown_on_exit") is not True
    ):
        raise ValueError("PS functional profile does not match the bounded 900 s/no-network/no-motion contract")
    stationary = load_json(artifacts["ps_stationary_profile"].path, "stationary profile")
    if (
        stationary.get("max_runtime_sec") != 1800
        or stationary.get("calibration_window_sec") != 300
        or stationary.get("acceptance_window_sec") != 1500
        or stationary.get("sample_interval_sec") != 30
        or stationary.get("lane_count") != 2
        or stationary.get("max_lane_mask") != "0x3"
        or stationary.get("network_required") is not False
        or stationary.get("motion_required") is not False
        or stationary.get("shutdown_on_exit") is not True
    ):
        raise ValueError("PS stationary profile does not match the exact 300+1500/1800 s contract")
    jtag_profile = load_json(artifacts["jtag_profile"].path, "JTAG profile")
    if (
        int(jtag_profile.get("max_runtime_sec", 0)) < 1800
        or jtag_profile.get("lane_count") != 2
        or jtag_profile.get("max_lane_mask") != "0x3"
        or jtag_profile.get("network_required") is not False
        or jtag_profile.get("motion_required") is not False
        or jtag_profile.get("shutdown_on_exit") is not True
    ):
        raise ValueError(
            "JTAG profile does not satisfy the 1800 s-capable two-lane/no-network/no-motion safety contract"
        )
    p6_build = load_json(artifacts["p6_build_summary"].path, "P6 build summary")
    if p6_build.get("P6_PS_CANDIDATE_BUILD") != "PASS":
        raise ValueError("P6 build summary is not PASS")
    p6_artifacts = p6_build.get("artifacts", {})
    if (
        not isinstance(p6_artifacts, dict)
        or p6_artifacts.get("bit", {}).get("sha256") != artifacts["ps_bitstream"].sha256
        or p6_artifacts.get("xsa", {}).get("sha256") != artifacts["xsa"].sha256
    ):
        raise ValueError("P6 build summary does not bind the supplied PS bitstream/XSA hashes")
    p7_build = load_json(artifacts["p7_build_summary"].path, "P7 build summary")
    if (
        p7_build.get("P7_PS_RUNTIME_BUILD") != "PASS"
        or p7_build.get("counts_per_second") != COUNTS_PER_SECOND
        or p7_build.get("xsa_sha256") != artifacts["xsa"].sha256
        or p7_build.get("artifacts", {}).get("elf", {}).get("sha256") != artifacts["elf"].sha256
    ):
        raise ValueError("P7 build summary does not bind the supplied XSA/ELF/timer contract")
    readiness = load_json(artifacts["core_readiness_attestation"].path, "core readiness")
    if readiness.get("P7_PS_CORE_HARDWARE_READINESS") != "PASS":
        raise ValueError("P7 PS core readiness is not PASS")
    promotion = load_json(artifacts["lane1_promotion_summary"].path, "lane1 promotion")
    if promotion.get("P7_LANE1_RELIABILITY_PROMOTION_GATE") != "PASS":
        raise ValueError("lane1 reliability promotion is not PASS")
    active = load_json(artifacts["active_profile"].path, "active profile")
    if active.get("lane1_reliable_enabled") is not True:
        raise ValueError("active profile does not enable the promoted lane1 reliability boundary")


def validate_canonical_artifact_paths(artifacts: Mapping[str, Artifact], abort_file: Path) -> None:
    p6_dir = (ROOT / "evidence" / "hardware" / "p6" / "bitstreams").resolve(strict=False)
    p7_dir = (ROOT / "evidence" / "hardware" / "p7" / "artifacts").resolve(strict=False)
    expected = (
        (
            "jtag_bitstream",
            p6_dir,
            f"p6_jtag_dynamic_transport_{artifacts['jtag_bitstream'].sha256}.bit",
        ),
        ("jtag_ltx", p6_dir, f"p6_jtag_dynamic_transport_{artifacts['jtag_ltx'].sha256}.ltx"),
        (
            "ps_bitstream",
            p6_dir,
            f"p6_ps_dynamic_transport_{artifacts['ps_bitstream'].sha256}.bit",
        ),
        ("xsa", p6_dir, f"p6_ps_dynamic_transport_{artifacts['xsa'].sha256}.xsa"),
        ("elf", p7_dir, f"p7_runtime_{artifacts['elf'].sha256}.elf"),
    )
    for name, parent, filename in expected:
        artifact = artifacts[name]
        if artifact.path.parent.resolve(strict=False) != parent or artifact.path.name.casefold() != filename.casefold():
            raise ValueError(
                f"{name} must use its canonical content-addressed immutable path: {parent / filename}"
            )
    canonical_files = {
        "goal_plan": p7_dir / f"p7_plan_{artifacts['goal_plan'].sha256}.md",
        "active_xdc": ROOT / "constraints" / "active" / "PORT1.generated.xdc",
        "pinmap": ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv",
        "register_map": ROOT / "config" / "register_map" / "ir_axi_regs.yaml",
        # The 1800 s stationary profile is also the canonical safe ceiling for
        # 1 MiB direct-JTAG transactions; those transactions are not timed
        # stationary PS service runs.
        "jtag_profile": ROOT / "profiles" / "p7" / "p7_stationary_app_30min.json",
        "ps_functional_profile": ROOT / "profiles" / "p7" / "p7_ps_application_functional.json",
        "ps_stationary_profile": ROOT / "profiles" / "p7" / "p7_stationary_app_30min.json",
    }
    for name, expected_path in canonical_files.items():
        expected_path = expected_path.resolve(strict=False)
        if artifacts[name].path != expected_path:
            raise ValueError(f"{name} must be canonical: {expected_path}")
    canonical_shutdown = (ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit").resolve(
        strict=False
    )
    if artifacts["shutdown_bitstream"].path != canonical_shutdown:
        raise ValueError(f"shutdown bitstream must be canonical: {canonical_shutdown}")
    canonical_active = (ROOT / "board_profiles" / "ACTIVE_PROFILE.json").resolve(strict=False)
    if artifacts["active_profile"].path != canonical_active:
        raise ValueError(f"active profile must be canonical: {canonical_active}")
    canonical_promotion = (
        ROOT / "evidence" / "generated" / "p7_lane1_promotion_summary.json"
    ).resolve(strict=False)
    if artifacts["lane1_promotion_summary"].path != canonical_promotion:
        raise ValueError(f"lane1 promotion summary must be canonical: {canonical_promotion}")
    if abort_file != safety.DEFAULT_ABORT_FILE.resolve(strict=False):
        raise ValueError(f"abort file must be canonical: {safety.DEFAULT_ABORT_FILE}")


def resolve_output_paths(args: argparse.Namespace) -> tuple[Path, Path, Path, Path]:
    run_id = args.run_id
    bundle_dir = (
        sequence.resolve_path(args.bundle_dir)
        if args.bundle_dir
        else BUILD_ROOT / "p7_authorized_sequence" / run_id
    ).resolve(strict=False)
    authorization_dir = (
        sequence.resolve_path(args.authorization_dir) if args.authorization_dir else AUTH_ROOT
    ).resolve(strict=False)
    plan_path = (
        sequence.resolve_path(args.output_plan)
        if args.output_plan
        else AUTH_ROOT / f"{run_id}_sequence_plan.txt"
    ).resolve(strict=False)
    evidence_root = (
        sequence.resolve_path(args.evidence_root)
        if args.evidence_root
        else HARDWARE_ROOT / "authorized_sequence" / run_id
    ).resolve(strict=False)
    return bundle_dir, authorization_dir, plan_path, evidence_root


def validate_canonical_identity(args: argparse.Namespace) -> None:
    if args.board_id != CANONICAL_BOARD_ID:
        raise ValueError(f"board id must be the canonical live board {CANONICAL_BOARD_ID}")
    if args.expected_part != CANONICAL_PART:
        raise ValueError(f"expected part must be canonical {CANONICAL_PART}")
    if args.expected_target != CANONICAL_TARGET:
        raise ValueError(f"expected target must be canonical {CANONICAL_TARGET}")
    if args.hw_server_url != CANONICAL_HW_SERVER_URL:
        raise ValueError(f"hw_server URL must be canonical {CANONICAL_HW_SERVER_URL}")
    if args.jtag_frequency_hz != CANONICAL_JTAG_FREQUENCY_HZ:
        raise ValueError(
            f"JTAG frequency must be canonical {CANONICAL_JTAG_FREQUENCY_HZ} Hz"
        )
    if args.axi_base_address != CANONICAL_AXI_BASE:
        raise ValueError(f"AXI base must remain canonical 0x{CANONICAL_AXI_BASE:08x}")
    if args.p6_session != DEFAULT_P6_SESSION:
        raise ValueError(f"P6 session must remain canonical 0x{DEFAULT_P6_SESSION:04x}")


def validate_preconditions(args: argparse.Namespace) -> dict[str, Any]:
    if not RUN_ID_RE.fullmatch(args.run_id):
        raise ValueError("--run-id must match [a-z0-9][a-z0-9_-]{2,63}")
    diagnostic_suffix55 = bool(getattr(args, "diagnostic_suffix55", False))
    if diagnostic_suffix55 and "diag_suffix55" not in args.run_id:
        raise ValueError("diagnostic suffix run-id must contain diag_suffix55")
    if not diagnostic_suffix55 and "diag" in args.run_id:
        raise ValueError("run-id containing diag requires the explicit diagnostic suffix mode")
    source_commit = args.source_commit.lower()
    if not sequence.COMMIT_RE.fullmatch(source_commit):
        raise ValueError("--source-commit must be exactly 40 lowercase hex characters")
    validate_canonical_identity(args)
    head, dirty, git_error = git_state()
    if git_error:
        raise ValueError(f"unable to establish clean repository state: {git_error}")
    if head != source_commit:
        raise ValueError(f"source commit mismatch: requested={source_commit} current={head}")
    allowed_generated_dirty, rejected_dirty = classify_dirty_entries(dirty)
    if rejected_dirty:
        raise ValueError(
            "generator permits only post-gate evidence/generated changes; rejected dirty entries: "
            f"{rejected_dirty}"
        )
    checkpoint = sequence.resolve_path(args.offline_checkpoint)
    checkpoint_sha = args.offline_checkpoint_sha256.lower()
    checkpoint_payload, checkpoint_errors = sequence._validate_offline_checkpoint(
        checkpoint, checkpoint_sha, source_commit
    )
    if checkpoint_errors:
        raise ValueError("offline checkpoint validation failed: " + "; ".join(checkpoint_errors))
    artifacts = {name: artifact_from_args(args, name) for name in ARTIFACT_ARGUMENTS}
    validate_bound_metadata(artifacts)
    bundle_dir, authorization_dir, plan_path, evidence_root = resolve_output_paths(args)
    if not path_inside(bundle_dir, BUILD_ROOT) or bundle_dir == BUILD_ROOT:
        raise ValueError(f"bundle output must be a child of ignored build root {BUILD_ROOT}")
    if bundle_dir.exists() and (
        bundle_dir.is_symlink() or not bundle_dir.is_dir() or any(bundle_dir.iterdir())
    ):
        raise ValueError(f"bundle output must be new or empty: {bundle_dir}")
    if not path_inside(authorization_dir, AUTH_ROOT):
        raise ValueError(f"authorization output must remain under {AUTH_ROOT}")
    if authorization_dir.exists() and (authorization_dir.is_symlink() or not authorization_dir.is_dir()):
        raise ValueError(f"authorization output is not a regular directory: {authorization_dir}")
    if not path_inside(plan_path, AUTH_ROOT) or plan_path.suffix.casefold() != ".txt":
        raise ValueError("sequence plan output must be a .txt file under .hardware_authorization")
    if plan_path.exists() or plan_path.with_name(plan_path.name + ".partial").exists():
        raise ValueError(f"sequence plan output already exists: {plan_path}")
    if plan_path == artifacts["goal_plan"].path:
        raise ValueError("frozen goal plan and generated sequence plan must be distinct files")
    if not path_inside(evidence_root, HARDWARE_ROOT) or evidence_root == HARDWARE_ROOT:
        raise ValueError(f"evidence root must be a child of {HARDWARE_ROOT}")
    if evidence_root.exists() and (
        evidence_root.is_symlink() or not evidence_root.is_dir() or any(evidence_root.iterdir())
    ):
        raise ValueError(f"evidence target root must be new or empty: {evidence_root}")
    abort_file = sequence.resolve_path(args.abort_file)
    if abort_file.exists():
        raise ValueError(f"operator abort file is present: {abort_file}")
    validate_canonical_artifact_paths(artifacts, abort_file)
    vivado = Path(args.vivado_path).resolve(strict=False)
    xsdb = Path(args.xsdb_path).resolve(strict=False)
    if not vivado.is_file() or not xsdb.is_file():
        raise ValueError("explicit Vivado and XSDB executables must both exist")
    if not sequence.is_exact_vivado_batch_launcher(vivado):
        raise ValueError("explicit Vivado launcher must be exactly vivado.bat; vivado.exe is forbidden")
    full_specs = build_stage_specs()
    validate_stage_specs(full_specs)
    specs = select_stage_specs(full_specs, diagnostic_suffix55=diagnostic_suffix55)
    for spec in specs:
        auth_path = authorization_dir / f"{args.run_id}_{spec.index:03d}_{spec.stage_id}.txt"
        if auth_path.exists() or auth_path.with_name(auth_path.name + ".partial").exists():
            raise ValueError(f"stage authorization output already exists: {auth_path}")
        evidence_dir = evidence_root / f"{spec.index:03d}_{spec.stage_id}"
        if evidence_dir.exists() and (
            evidence_dir.is_symlink() or not evidence_dir.is_dir() or any(evidence_dir.iterdir())
        ):
            raise ValueError(f"stage evidence target is not new/empty: {evidence_dir}")
    return {
        "source_commit": source_commit,
        "checkpoint_path": checkpoint,
        "checkpoint_sha256": checkpoint_sha,
        "checkpoint_payload": checkpoint_payload,
        "artifacts": artifacts,
        "bundle_dir": bundle_dir,
        "authorization_dir": authorization_dir,
        "plan_path": plan_path,
        "evidence_root": evidence_root,
        "abort_file": abort_file,
        "vivado": vivado,
        "xsdb": xsdb,
        "specs": specs,
        "plan_mode": (
            sequence.DIAGNOSTIC_PLAN_MODE
            if diagnostic_suffix55
            else sequence.FULL_PLAN_MODE
        ),
        "full_stage_ordinals": [spec.index for spec in specs],
        "allowed_post_gate_generated_dirty": allowed_generated_dirty,
    }


def common_authorization_lines(
    args: argparse.Namespace,
    context: Mapping[str, Any],
    spec: StageSpec,
    *,
    bitstream: Artifact,
    profile: Artifact,
    include_ltx: bool,
) -> list[str]:
    artifacts: Mapping[str, Artifact] = context["artifacts"]
    bindings = (
        ("P7_PLAN", artifacts["goal_plan"]),
        ("BITSTREAM", bitstream),
        ("XSA", artifacts["xsa"]),
        ("ELF", artifacts["elf"]),
        ("PROFILE", profile),
        ("ACTIVE_XDC", artifacts["active_xdc"]),
        ("PINMAP", artifacts["pinmap"]),
        ("REGISTER_MAP", artifacts["register_map"]),
        ("SHUTDOWN_BITSTREAM", artifacts["shutdown_bitstream"]),
    )
    lines = [
        safety.AUTH_MARKER,
        f"AUTHORIZED_STAGE={safety.AUTHORIZED_STAGE}",
        "USER_HARDWARE_AUTHORIZATION_FOR_P7=GRANTED",
        f"BOARD_ID={args.board_id}",
        f"EXPECTED_PART={args.expected_part}",
        f"EXPECTED_TARGET={args.expected_target}",
        f"SOURCE_COMMIT={context['source_commit']}",
        f"MAX_RUNTIME_SEC={spec.max_runtime_sec}",
        "SHUTDOWN_ON_EXIT=required",
        "NO_ETHERNET=true",
        "NO_MOTION=true",
        "LANE_COUNT=2",
        "MAX_LANE_MASK=0x3",
    ]
    if context.get("plan_mode") == sequence.DIAGNOSTIC_PLAN_MODE:
        lines.extend(
            [
                "P7_EXECUTION_MODE=DIAGNOSTIC_ONLY",
                "P7_COVERAGE_CLAIMED=false",
                "HARDWARE_ACCEPTANCE=PENDING_HW",
                f"P7_FULL_STAGE_ORDINAL={spec.index}",
            ]
        )
    for prefix, artifact in bindings:
        path_key = "P7_PLAN_PATH" if prefix == "P7_PLAN" else f"{prefix}_PATH"
        sha_key = "P7_PLAN_SHA256" if prefix == "P7_PLAN" else f"{prefix}_SHA256"
        lines.extend([f"{path_key}={artifact.path}", f"{sha_key}={artifact.sha256}"])
    if include_ltx:
        ltx = artifacts["jtag_ltx"]
        lines.extend([f"LTX_PATH={ltx.path}", f"LTX_SHA256={ltx.sha256}"])
    return lines


def write_stage_authorization(
    args: argparse.Namespace,
    context: Mapping[str, Any],
    spec: StageSpec,
    auth_path: Path,
    *,
    transaction: Artifact | None = None,
    backend_manifest: Artifact | None = None,
    ps_input: Artifact | None = None,
) -> Artifact:
    artifacts: Mapping[str, Artifact] = context["artifacts"]
    if spec.kind == "jtag":
        bitstream = artifacts["jtag_bitstream"]
        profile = artifacts["jtag_profile"]
    else:
        bitstream = artifacts["ps_bitstream"]
        profile = (
            artifacts["ps_stationary_profile"]
            if spec.group == "ps_stationary"
            else artifacts["ps_functional_profile"]
        )
    lines = common_authorization_lines(
        args,
        context,
        spec,
        bitstream=bitstream,
        profile=profile,
        include_ltx=spec.kind == "jtag",
    )
    if spec.kind == "jtag":
        if transaction is None:
            raise RuntimeError("JTAG authorization requires a transaction binding")
        lines.extend(
            [
                f"P7_JTAG_STAGE_NAME={spec.stage_id}",
                f"P7_JTAG_SEMANTIC_MODE={spec.mode}",
                f"P7_JTAG_TRANSACTION_PATH={transaction.path}",
                f"P7_JTAG_TRANSACTION_SHA256={transaction.sha256}",
                f"P7_JTAG_FREQUENCY_HZ={args.jtag_frequency_hz}",
                f"P7_JTAG_AXI_BASE=0x{args.axi_base_address:08x}",
            ]
        )
        if backend_manifest is not None:
            lines.extend(
                [
                    f"P7_JTAG_BACKEND_MANIFEST_PATH={backend_manifest.path}",
                    f"P7_JTAG_BACKEND_MANIFEST_SHA256={backend_manifest.sha256}",
                ]
            )
    else:
        if ps_input is None:
            raise RuntimeError("PS authorization requires a deterministic input binding")
        shutdown = artifacts["shutdown_bitstream"]
        frozen_shutdown = (
            ROOT
            / "evidence"
            / "hardware"
            / "p7"
            / "shutdown"
            / f"p7_frozen_shutdown_{shutdown.sha256}.bit"
        ).resolve(strict=False)
        extensions = (
            ("PS7_INIT", artifacts["ps7_init"]),
            ("P6_PS_BUILD_SUMMARY", artifacts["p6_build_summary"]),
            ("P7_PS_BUILD_SUMMARY", artifacts["p7_build_summary"]),
            ("P7_PS_CORE_READINESS", artifacts["core_readiness_attestation"]),
            ("ACTIVE_PROFILE", artifacts["active_profile"]),
            ("P7_LANE1_PROMOTION_SUMMARY", artifacts["lane1_promotion_summary"]),
        )
        for prefix, artifact in extensions:
            lines.extend([f"{prefix}_PATH={artifact.path}", f"{prefix}_SHA256={artifact.sha256}"])
        lines.extend(
            [
                f"P7_INPUT_PATH={ps_input.path}",
                f"P7_INPUT_SHA256={ps_input.sha256}",
                f"P7_PS_MODE={spec.mode}",
                "P7_PS_CORE_READINESS=PASS",
                f"P7_FROZEN_SHUTDOWN_PATH={frozen_shutdown}",
                f"P7_FROZEN_SHUTDOWN_SHA256={shutdown.sha256}",
                f"P7_COUNTS_PER_SECOND={COUNTS_PER_SECOND}",
            ]
        )
    atomic_write_text(auth_path, "\n".join(lines) + "\n")
    return Artifact(auth_path.resolve(strict=False), sha256_file(auth_path))


def common_wrapper_argv(
    args: argparse.Namespace,
    context: Mapping[str, Any],
    spec: StageSpec,
    auth: Artifact,
    *,
    bitstream: Artifact,
    profile: Artifact,
    include_ltx: bool,
) -> list[str]:
    artifacts: Mapping[str, Artifact] = context["artifacts"]
    argv = [
        "--execute-hardware",
        "--authorization-file",
        str(auth.path),
        "--authorization-sha256",
        auth.sha256,
        "--board-id",
        args.board_id,
        "--expected-part",
        args.expected_part,
        "--expected-target",
        args.expected_target,
        "--source-commit",
        context["source_commit"],
        "--plan-file",
        str(artifacts["goal_plan"].path),
        "--plan-sha256",
        artifacts["goal_plan"].sha256,
        "--bitstream",
        str(bitstream.path),
        "--bitstream-sha256",
        bitstream.sha256,
        "--xsa",
        str(artifacts["xsa"].path),
        "--xsa-sha256",
        artifacts["xsa"].sha256,
        "--elf",
        str(artifacts["elf"].path),
        "--elf-sha256",
        artifacts["elf"].sha256,
        "--profile",
        str(profile.path),
        "--profile-sha256",
        profile.sha256,
        "--active-xdc",
        str(artifacts["active_xdc"].path),
        "--active-xdc-sha256",
        artifacts["active_xdc"].sha256,
        "--pinmap",
        str(artifacts["pinmap"].path),
        "--pinmap-sha256",
        artifacts["pinmap"].sha256,
        "--register-map",
        str(artifacts["register_map"].path),
        "--register-map-sha256",
        artifacts["register_map"].sha256,
        "--shutdown-bitstream",
        str(artifacts["shutdown_bitstream"].path),
        "--shutdown-bitstream-sha256",
        artifacts["shutdown_bitstream"].sha256,
    ]
    if include_ltx:
        argv.extend(
            [
                "--ltx",
                str(artifacts["jtag_ltx"].path),
                "--ltx-sha256",
                artifacts["jtag_ltx"].sha256,
            ]
        )
    argv.extend(
        [
            "--max-runtime-sec",
            str(spec.max_runtime_sec),
            "--shutdown-on-exit",
            "--no-ethernet",
            "--no-motion",
            "--lane-count",
            "2",
            "--max-lane-mask",
            "0x3",
            "--abort-file",
            str(context["abort_file"]),
            "--vivado-path",
            str(context["vivado"]),
            "--hw-server-url",
            args.hw_server_url,
            "--stage-name",
            spec.stage_id,
        ]
    )
    return argv


def build_jtag_command(
    args: argparse.Namespace,
    context: Mapping[str, Any],
    spec: StageSpec,
    auth: Artifact,
    transaction: Artifact,
    backend_manifest: Artifact | None,
    evidence_dir: Path,
) -> list[str]:
    artifacts: Mapping[str, Artifact] = context["artifacts"]
    command = [sys.executable, str(sequence.JTAG_WRAPPER)] + common_wrapper_argv(
        args,
        context,
        spec,
        auth,
        bitstream=artifacts["jtag_bitstream"],
        profile=artifacts["jtag_profile"],
        include_ltx=True,
    )
    command.extend(
        [
            "--semantic-mode",
            spec.mode,
            "--transaction-file",
            str(transaction.path),
            "--transaction-sha256",
            transaction.sha256,
        ]
    )
    if backend_manifest is not None:
        command.extend(
            [
                "--backend-manifest",
                str(backend_manifest.path),
                "--backend-manifest-sha256",
                backend_manifest.sha256,
            ]
        )
    command.extend(
        [
            "--axi-base-address",
            f"0x{args.axi_base_address:08x}",
            "--jtag-frequency-hz",
            str(args.jtag_frequency_hz),
            "--preflight-timeout-sec",
            str(spec.preflight_timeout_sec),
            "--stage-timeout-sec",
            str(spec.stage_timeout_sec),
            "--shutdown-timeout-sec",
            str(spec.shutdown_timeout_sec),
            "--evidence-dir",
            str(evidence_dir),
            "--json-summary",
        ]
    )
    return command


def build_ps_command(
    args: argparse.Namespace,
    context: Mapping[str, Any],
    spec: StageSpec,
    auth: Artifact,
    ps_input: Artifact,
    evidence_dir: Path,
) -> list[str]:
    artifacts: Mapping[str, Artifact] = context["artifacts"]
    profile = (
        artifacts["ps_stationary_profile"]
        if spec.group == "ps_stationary"
        else artifacts["ps_functional_profile"]
    )
    command = [sys.executable, str(sequence.PS_WRAPPER)] + common_wrapper_argv(
        args,
        context,
        spec,
        auth,
        bitstream=artifacts["ps_bitstream"],
        profile=profile,
        include_ltx=False,
    )
    command.extend(
        [
            "--mode",
            spec.mode,
            "--input-file",
            str(ps_input.path),
            "--input-sha256",
            ps_input.sha256,
            "--ps7-init",
            str(artifacts["ps7_init"].path),
            "--ps7-init-sha256",
            artifacts["ps7_init"].sha256,
            "--p6-build-summary",
            str(artifacts["p6_build_summary"].path),
            "--p6-build-summary-sha256",
            artifacts["p6_build_summary"].sha256,
            "--p7-build-summary",
            str(artifacts["p7_build_summary"].path),
            "--p7-build-summary-sha256",
            artifacts["p7_build_summary"].sha256,
            "--core-readiness-attestation",
            str(artifacts["core_readiness_attestation"].path),
            "--core-readiness-attestation-sha256",
            artifacts["core_readiness_attestation"].sha256,
            "--active-profile",
            str(artifacts["active_profile"].path),
            "--active-profile-sha256",
            artifacts["active_profile"].sha256,
            "--lane1-promotion-summary",
            str(artifacts["lane1_promotion_summary"].path),
            "--lane1-promotion-summary-sha256",
            artifacts["lane1_promotion_summary"].sha256,
            "--xsdb-path",
            str(context["xsdb"]),
            "--jtag-frequency-hz",
            str(args.jtag_frequency_hz),
            "--preflight-timeout-sec",
            str(spec.preflight_timeout_sec),
            "--shutdown-timeout-sec",
            str(spec.shutdown_timeout_sec),
        ]
    )
    if spec.group == "ps_stationary":
        command.extend(
            [
                "--calibration-sec",
                "300",
                "--acceptance-sec",
                "1500",
                "--sample-interval-sec",
                "30",
                "--idle-deadline-margin-sec",
                "60",
                "--stationary-object-bytes",
                str(64 * 1024),
            ]
        )
    command.extend(["--evidence-dir", str(evidence_dir), "--json-summary"])
    return command


def generated_artifact(path: Path) -> Artifact:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"generated artifact is missing/not regular: {path}")
    return Artifact(path.resolve(strict=False), sha256_file(path))


def validate_child_wrapper_dry(spec: StageSpec, command: list[str]) -> dict[str, Any]:
    """Run the child's offline control validator without calling its main/run path."""

    if spec.kind == "jtag":
        parsed = jtag_safe_wrapper.build_parser().parse_args(command[2:])
        errors, transaction = jtag_safe_wrapper._stage_control_errors(parsed)
        report = {
            "kind": "jtag",
            "operation_count": transaction.get("operation_count"),
            "fragment_count": transaction.get("backend_manifest", {}).get("fragment_count")
            if isinstance(transaction.get("backend_manifest"), dict)
            else None,
            "runtime_feasibility": transaction.get("runtime_feasibility"),
            "global_runtime_budget": transaction.get("global_runtime_budget"),
            "errors": errors,
        }
    else:
        parsed = ps_safe_wrapper.build_parser().parse_args(command[2:])
        core_readiness = ps_safe_wrapper.validate_core_readiness(parsed)
        errors = ps_safe_wrapper._stage_validation(parsed, core_readiness)
        report = {
            "kind": "ps",
            "mode": parsed.mode,
            "core_readiness": core_readiness.get("status"),
            "errors": errors,
        }
    common = safety.validate_request(parsed)
    external_auth_error = (
        f"external environment authorization required: {safety.AUTH_ENV}={safety.AUTH_ENV_VALUE}"
    )
    common_errors = [item for item in common["errors"] if item != external_auth_error]
    if common_errors:
        errors.extend(f"common safety validation: {item}" for item in common_errors)
    report["common_safety_validation"] = (
        "PASS"
        if not common["errors"]
        else "PASS_OFFLINE_WITH_EXTERNAL_EXECUTION_ENVIRONMENT_INTENTIONALLY_ABSENT"
        if common["errors"] == [external_auth_error]
        else "BLOCKED"
    )
    if errors:
        raise RuntimeError(
            f"child safe-wrapper offline validation failed for {spec.stage_id}: "
            + "; ".join(str(item) for item in errors)
        )
    return report


def generate_sequence(args: argparse.Namespace) -> dict[str, Any]:
    context = validate_preconditions(args)
    bundle_dir: Path = context["bundle_dir"]
    authorization_dir: Path = context["authorization_dir"]
    evidence_root: Path = context["evidence_root"]
    artifacts: Mapping[str, Artifact] = context["artifacts"]
    bundle_dir.mkdir(parents=True, exist_ok=True)
    authorization_dir.mkdir(parents=True, exist_ok=True)
    inputs_dir = bundle_dir / "inputs"
    transactions_dir = bundle_dir / "transactions"
    manifests_dir = bundle_dir / "manifests"
    inputs_dir.mkdir()
    transactions_dir.mkdir()
    manifests_dir.mkdir()
    ps_seed_path = inputs_dir / "p7_ps_seed_247.bin"
    ps_seed_data = patterned_data("deterministic_random", PS_SEED_BYTES, 0x7000)
    atomic_write_bytes(ps_seed_path, ps_seed_data)
    ps_input = generated_artifact(ps_seed_path)
    plan_stages: list[dict[str, Any]] = []
    generated_inputs: list[dict[str, Any]] = [
        {
            "stage": "ps_all_modes",
            "pattern": "deterministic_random",
            "path": str(ps_input.path),
            "sha256": ps_input.sha256,
            "bytes": PS_SEED_BYTES,
        }
    ]
    authorization_records: list[dict[str, Any]] = []
    child_dry_validations: list[dict[str, Any]] = []
    plan_mode = str(context["plan_mode"])
    diagnostic = plan_mode == sequence.DIAGNOSTIC_PLAN_MODE

    for spec in context["specs"]:
        auth_path = authorization_dir / f"{args.run_id}_{spec.index:03d}_{spec.stage_id}.txt"
        evidence_dir = evidence_root / f"{spec.index:03d}_{spec.stage_id}"
        summary_name = (
            "p7_jtag_axi_stage_summary.json"
            if spec.kind == "jtag"
            else "p7_ps_application_stage_summary.json"
        )
        if spec.kind == "jtag":
            transaction_path = transactions_dir / f"{spec.index:03d}_{spec.stage_id}.transactions.txt"
            backend_manifest: Artifact | None = None
            if spec.mode == "safe-idle":
                write_safe_idle_transaction(transaction_path, args.axi_base_address)
            else:
                if spec.group == "p6_frame_regression":
                    object_size = 4096
                    lane_policy = {1: "LANE0_ONLY", 2: "LANE1_ONLY", 3: "REPLICATE_0X3"}[
                        int(spec.case["lane_mask"])
                    ]
                else:
                    object_size = int(spec.case["object_size"])
                    lane_policy = str(spec.case["lane_policy"])
                data = patterned_data(spec.pattern, object_size, spec.index)
                input_path = inputs_dir / f"{spec.index:03d}_{spec.stage_id}.bin"
                atomic_write_bytes(input_path, data)
                input_artifact = generated_artifact(input_path)
                generated_inputs.append(
                    {
                        "stage": spec.stage_id,
                        "pattern": spec.pattern,
                        "path": str(input_artifact.path),
                        "sha256": input_artifact.sha256,
                        "bytes": object_size,
                    }
                )
                manifest_path = manifests_dir / f"{spec.index:03d}_{spec.stage_id}.manifest.json"
                manifest = jtag_backend.generate_bundle(
                    data,
                    transaction_path=transaction_path,
                    manifest_path=manifest_path,
                    session_epoch=0x50370000 + spec.index,
                    object_id=spec.index,
                    lane_policy=lane_policy,
                    base_address=args.axi_base_address,
                    p6_session=args.p6_session,
                    jtag_frequency_hz=args.jtag_frequency_hz,
                    authorized_runtime_sec=spec.max_runtime_sec,
                )
                if spec.group == "p6_frame_regression" and int(manifest.get("fragment_count", 0)) < 10:
                    raise RuntimeError(f"P6 regression bundle has fewer than 10 fragments: {spec.stage_id}")
                # Bind the plan-required pattern explicitly for evidence
                # aggregation; the backend parser tolerates and preserves this
                # declarative field while still validating all core fields.
                manifest["payload_pattern"] = spec.pattern
                manifest["sequence_stage_id"] = spec.stage_id
                manifest["input_file"] = str(input_artifact.path)
                manifest["input_file_sha256"] = input_artifact.sha256
                manifest_path.unlink()
                atomic_write_json(manifest_path, manifest)
                backend_manifest = generated_artifact(manifest_path)
            transaction = generated_artifact(transaction_path)
            auth = write_stage_authorization(
                args,
                context,
                spec,
                auth_path,
                transaction=transaction,
                backend_manifest=backend_manifest,
            )
            command = build_jtag_command(
                args,
                context,
                spec,
                auth,
                transaction,
                backend_manifest,
                evidence_dir,
            )
        else:
            auth = write_stage_authorization(
                args,
                context,
                spec,
                auth_path,
                ps_input=ps_input,
            )
            command = build_ps_command(args, context, spec, auth, ps_input, evidence_dir)
        child_report = validate_child_wrapper_dry(spec, command)
        child_dry_validations.append({"stage": spec.stage_id, **child_report})
        authorization_records.append(
            {"stage": spec.stage_id, "path": str(auth.path), "sha256": auth.sha256}
        )
        plan_stages.append(
            {
                "id": spec.stage_id,
                "group": spec.group,
                "risk_index": spec.risk_index,
                "case": spec.case,
                "command": command,
                "summary_path": str((evidence_dir / summary_name).resolve(strict=False)),
                "wrapper_timeout_sec": spec.wrapper_timeout_sec,
            }
        )

    plan = {
        "schema": sequence.SEQUENCE_SCHEMA,
        "description": (
            "DIAGNOSTIC_ONLY deterministic zero-coverage P7 suffix; no Ethernet, no motion, two lanes; "
            "formal ordinals 1--4 and 55--65 only; stationary is forbidden."
            if diagnostic
            else "Deterministic offline-generated P7 safe-wrapper sequence; no Ethernet, no motion, two lanes; "
            "the sole timed 1800-second PS stationary run is final."
        ),
        "source_commit": context["source_commit"],
        "offline_checkpoint": {
            "path": str(context["checkpoint_path"]),
            "sha256": context["checkpoint_sha256"],
        },
        "stages": plan_stages,
        **(
            {
                "plan_mode": sequence.DIAGNOSTIC_PLAN_MODE,
                "full_stage_ordinals": context["full_stage_ordinals"],
                "coverage_claimed": False,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            }
            if diagnostic
            else {}
        ),
    }
    atomic_write_json(context["plan_path"], plan)
    plan_hash = sha256_file(context["plan_path"])
    validation = sequence.validate_sequence_plan(context["plan_path"], plan_hash)
    if validation.get("errors"):
        raise RuntimeError(
            "generated plan failed the executor's strict local dry validation: "
            + "; ".join(str(item) for item in validation["errors"])
        )
    expected_stage_count = 15 if diagnostic else 66
    if validation.get("stage_count") != expected_stage_count:
        raise RuntimeError(
            f"generated plan validator did not observe exactly {expected_stage_count} stages"
        )
    groups = [spec.group for spec in context["specs"]]
    manifest = {
        "schema": GENERATOR_SCHEMA,
        "P7_AUTHORIZED_SEQUENCE_GENERATOR": "PASS",
        "generated_at_utc": now_utc(),
        "hardware_actions_executed": False,
        "safe_wrapper_processes_launched": False,
        "vivado_invoked": False,
        "xsdb_invoked": False,
        "authorization_environment_modified": False,
        "network_used": False,
        "motion_used": False,
        "plan_mode": plan_mode,
        "coverage_claimed": False if diagnostic else None,
        "HARDWARE_ACCEPTANCE": "PENDING_HW" if diagnostic else None,
        "full_stage_ordinals": context["full_stage_ordinals"],
        "source_commit": context["source_commit"],
        "allowed_post_gate_generated_dirty": context["allowed_post_gate_generated_dirty"],
        "offline_checkpoint": {
            "path": str(context["checkpoint_path"]),
            "sha256": context["checkpoint_sha256"],
        },
        "frozen_goal_plan": {
            "path": str(artifacts["goal_plan"].path),
            "sha256": artifacts["goal_plan"].sha256,
        },
        "sequence_plan": {
            "path": str(context["plan_path"]),
            "sha256": plan_hash,
            "stage_count": expected_stage_count,
            "executor_dry_validation": "PASS",
        },
        "counts": {
            "safe_idle": groups.count("safe_idle"),
            "p6_frame_regression": groups.count("p6_frame_regression"),
            "fragment_boundary": groups.count("fragment_boundary"),
            "large_object_jtag": groups.count("large_object_jtag"),
            "ps_modes": sum(group.startswith("ps_") for group in groups),
            "stationary": groups.count("ps_stationary"),
        },
        "authorization_count": len(authorization_records),
        "authorization_records": authorization_records,
        "child_wrapper_dry_validation_count": len(child_dry_validations),
        "child_wrapper_dry_validations": child_dry_validations,
        "generated_input_count": len(generated_inputs),
        "generated_inputs": generated_inputs,
        "evidence_root_planned_not_created": str(evidence_root),
    }
    manifest_path = bundle_dir / "p7_authorized_sequence_generation_manifest.json"
    atomic_write_json(manifest_path, manifest)
    manifest["generation_manifest"] = {
        "path": str(manifest_path),
        "sha256": sha256_file(manifest_path),
    }
    return manifest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate and locally validate a formal P7 sequence or zero-coverage diagnostic suffix; never touches hardware."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--offline-checkpoint", required=True)
    parser.add_argument("--offline-checkpoint-sha256", required=True)
    for name in ARTIFACT_ARGUMENTS:
        parser.add_argument(f"--{name.replace('_', '-')}", required=True)
        parser.add_argument(f"--{name.replace('_', '-')}-sha256", required=True)
    parser.add_argument("--board-id", required=True)
    parser.add_argument("--expected-part", required=True)
    parser.add_argument("--expected-target", required=True)
    parser.add_argument("--vivado-path", required=True)
    parser.add_argument("--xsdb-path", required=True)
    parser.add_argument("--hw-server-url", default="localhost:3121")
    parser.add_argument("--jtag-frequency-hz", type=int, default=1_000_000)
    parser.add_argument("--axi-base-address", type=lambda value: int(value, 0), default=CANONICAL_AXI_BASE)
    parser.add_argument("--p6-session", type=lambda value: int(value, 0), default=DEFAULT_P6_SESSION)
    parser.add_argument("--abort-file", default=str(safety.DEFAULT_ABORT_FILE.relative_to(ROOT)))
    parser.add_argument("--bundle-dir", default="")
    parser.add_argument("--authorization-dir", default="")
    parser.add_argument("--output-plan", default="")
    parser.add_argument("--evidence-root", default="")
    parser.add_argument(
        "--diagnostic-suffix55",
        action="store_true",
        help="Generate only formal ordinals 1--4 and 55--65; excludes stationary and claims zero coverage.",
    )
    parser.add_argument("--json-summary", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = generate_sequence(args)
        returncode = 0
    except Exception as exc:
        result = {
            "schema": GENERATOR_SCHEMA,
            "P7_AUTHORIZED_SEQUENCE_GENERATOR": "BLOCKED",
            "generated_at_utc": now_utc(),
            "hardware_actions_executed": False,
            "safe_wrapper_processes_launched": False,
            "vivado_invoked": False,
            "xsdb_invoked": False,
            "authorization_environment_modified": False,
            "network_used": False,
            "motion_used": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }
        returncode = 2
    if args.json_summary:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"P7_AUTHORIZED_SEQUENCE_GENERATOR: {result['P7_AUTHORIZED_SEQUENCE_GENERATOR']}")
        plan = result.get("sequence_plan")
        if isinstance(plan, dict):
            print(f"P7_SEQUENCE_PLAN_PATH={plan.get('path')}")
            print(f"P7_SEQUENCE_PLAN_SHA256={plan.get('sha256')}")
    return returncode


if __name__ == "__main__":
    raise SystemExit(main())
