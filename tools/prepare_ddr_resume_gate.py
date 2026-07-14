#!/usr/bin/env python3
"""Prepare one immutable DDR external-master authorization request offline.

This program never connects to hardware, never launches Vivado or XSDB, never
sets ``RF_COMM_HW_AUTH``, and never creates a granted authorization file.  It
materializes the first new diagnostic fixture, a run configuration, a complete
artifact manifest, and a deliberately non-authorizing human-review template.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
HW = ROOT / "scripts" / "hw"
for directory in (TOOLS, HW):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

import p7_hardware_safety as safety  # noqa: E402
import run_p7_ps_application_stage_safe as runner  # noqa: E402


STAGE62_PACKAGING_COMMIT = "53571e305846f89bf3da8c146f5a07bdb003f606"
DEFAULT_BOARD_ID = "210512180081"
DEFAULT_PART = "xc7z010clg400-1"
DEFAULT_TARGET = "localhost:3121/xilinx_tcf/Digilent/210512180081"
DEFAULT_HW_SERVER = "localhost:3121"
DEFAULT_VIVADO = Path(r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat")
DEFAULT_XSDB = Path(r"D:\Xilinx\Vitis\2023.1\bin\xsdb.bat")
P6_SUMMARY = ROOT / "evidence/generated/vivado/p6_ps_candidate/p6_ps_candidate_build_summary.json"
P7_SUMMARY = ROOT / "evidence/generated/vitis/p7_ps_runtime/p7_ps_runtime_build_summary.json"
CORE_READINESS = ROOT / "evidence/generated/p7_ps_core_hardware_readiness.json"
ACTIVE_PROFILE = ROOT / "board_profiles/ACTIVE_PROFILE.json"
LANE1_SUMMARY = ROOT / "evidence/generated/p7_lane1_promotion_summary.json"
FUNCTIONAL_PROFILE = ROOT / "profiles/p7/p7_ps_application_functional.json"
ACTIVE_XDC = ROOT / "constraints/active/PORT1.generated.xdc"
PINMAP = ROOT / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv"
REGISTER_MAP = ROOT / "config/register_map/ir_axi_regs.yaml"
SHUTDOWN_BIT = ROOT / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit"
INPUT_SEED = (
    ROOT
    / "evidence/hardware/p7/artifacts"
    / "p7_input_seed_4b96ec3b91e9f764ac0227ca7df451bd8294cd46298047b43b960ae1c0b0afc5.bin"
)
PS7_INIT = ROOT / "build/p7_ps_vitis_workspace/p7_platform/hw/ps7_init.tcl"


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    if path.exists() or partial.exists():
        raise RuntimeError(f"refusing to overwrite generated DDR gate file: {path}")
    try:
        with partial.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(partial, path)
    finally:
        if partial.exists():
            partial.unlink()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    atomic_write(
        path,
        (json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n").encode(
            "utf-8"
        ),
    )


def load_json(path: Path, label: str) -> dict[str, Any]:
    if not path.is_file() or path.is_symlink():
        raise RuntimeError(f"{label} is missing/not regular: {path}")
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{label} top level is not an object")
    return value


def git_output(*arguments: str) -> str:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(arguments)} failed: {completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout.strip()


def require_file(path: Path, expected_sha256: str | None = None) -> Path:
    resolved = path.resolve(strict=True)
    if resolved.is_symlink() or not resolved.is_file():
        raise RuntimeError(f"artifact is missing/not regular: {resolved}")
    actual = sha256_file(resolved)
    if expected_sha256 is not None and actual != expected_sha256.lower():
        raise RuntimeError(
            f"artifact SHA256 mismatch: path={resolved} expected={expected_sha256.lower()} actual={actual}"
        )
    return resolved


def content_addressed_plan() -> Path:
    candidates = list((ROOT / "evidence/hardware/p7/artifacts").glob("p7_plan_*.md"))
    valid = []
    for path in candidates:
        suffix = path.stem.removeprefix("p7_plan_").lower()
        if safety.SHA256_RE.fullmatch(suffix) and sha256_file(path) == suffix:
            valid.append(path)
    if len(valid) != 1:
        raise RuntimeError(
            f"exactly one content-addressed P7 plan is required, observed={len(valid)}"
        )
    return valid[0].resolve(strict=True)


def materialize_exact_copy(source: Path, destination: Path, expected_sha256: str) -> Path:
    source = require_file(source, expected_sha256)
    destination = destination.resolve(strict=False)
    if destination.exists():
        return require_file(destination, expected_sha256)
    atomic_write(destination, source.read_bytes())
    return require_file(destination, expected_sha256)


def artifact_record(
    *,
    role: str,
    path: Path,
    git_commit: str,
    actual_run_input: bool,
    consumption: str,
    provenance_kind: str,
) -> dict[str, Any]:
    path = require_file(path)
    if not safety.COMMIT_RE.fullmatch(git_commit):
        raise RuntimeError(f"artifact Git commit is invalid: {role}={git_commit}")
    return {
        "role": role,
        "absolute_path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "git_commit": git_commit.lower(),
        "actual_run_input": actual_run_input,
        "consumption": consumption,
        "provenance_kind": provenance_kind,
    }


def auth_line_path(path: Path) -> str:
    return str(path.resolve(strict=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--pattern", choices=runner.DDR_EXTERNAL_PATTERN_NAMES, required=True)
    parser.add_argument("--address", required=True)
    parser.add_argument(
        "--access-method", choices=runner.DDR_EXTERNAL_ACCESS_METHODS, required=True
    )
    parser.add_argument("--repetition", type=int, required=True)
    parser.add_argument("--unaligned-accesses", action="store_true")
    parser.add_argument("--max-runtime-sec", type=int, default=60)
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--json-summary", action="store_true")
    return parser


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    source_commit = args.source_commit.lower()
    if not safety.COMMIT_RE.fullmatch(source_commit):
        raise RuntimeError("source commit must be a full 40-hex commit")
    if git_output("rev-parse", "HEAD").lower() != source_commit:
        raise RuntimeError("source commit does not equal current linked-worktree HEAD")
    if not runner.RUN_ID_RE.fullmatch(args.run_id):
        raise RuntimeError("DDR new run ID is malformed")
    if any(token in args.run_id for token in ("r34", "r35", "r36", "r37")):
        raise RuntimeError("R34-R37 run IDs are immutable and cannot be reused")
    if not 1 <= args.max_runtime_sec <= 900:
        raise RuntimeError("DDR diagnostic max runtime must be in 1..900 seconds")

    identity, fixture_payload = runner.ddr_external_identity(
        run_id=args.run_id,
        pattern=args.pattern,
        address_text=args.address,
        access_method=args.access_method,
        repetition=args.repetition,
        unaligned_accesses=args.unaligned_accesses,
        fixture_sha256=hashlib.sha256(
            runner.build_ddr_external_fixture(args.pattern)
        ).hexdigest(),
    )
    output_dir = (
        Path(args.output_dir).resolve(strict=False)
        if args.output_dir
        else (ROOT / ".hardware_authorization" / f"{args.run_id}.request").resolve(
            strict=False
        )
    )
    authorization_root = (ROOT / ".hardware_authorization").resolve(strict=False)
    try:
        output_dir.relative_to(authorization_root)
    except ValueError as exc:
        raise RuntimeError(
            f"DDR request output must be under {authorization_root}: {output_dir}"
        ) from exc
    if output_dir.exists():
        raise RuntimeError(f"DDR request output already exists: {output_dir}")
    expected_authorization = (
        ROOT / ".hardware_authorization" / f"{args.run_id}.txt"
    ).resolve(strict=False)
    evidence_dir = (
        ROOT / "evidence/hardware/p7/ddr_external_master" / args.run_id
    ).resolve(strict=False)
    if expected_authorization.exists():
        raise RuntimeError(
            f"new-run authorization path already exists: {expected_authorization}"
        )
    if evidence_dir.exists():
        raise RuntimeError(f"new-run evidence directory already exists: {evidence_dir}")

    p6 = load_json(P6_SUMMARY, "P6 PS build summary")
    p7 = load_json(P7_SUMMARY, "P7 PS build summary")
    core = load_json(CORE_READINESS, "P7 PS core readiness")
    if p6.get("P6_PS_CANDIDATE_BUILD") != "PASS":
        raise RuntimeError("P6 PS build summary is not PASS")
    if p7.get("P7_PS_RUNTIME_BUILD") != "PASS" or p7.get("syntax_only") is not False:
        raise RuntimeError("P7 runtime build summary is not a real PASS build")
    if (
        core.get("P7_PS_CORE_HARDWARE_READINESS") != "PASS"
        or core.get("source_commit") != source_commit
        or core.get("hardware_actions_executed") is not False
        or core.get("HARDWARE_ACCEPTANCE") != "PENDING_HW"
    ):
        raise RuntimeError("P7 core readiness is not PASS and source-commit bound")

    bit_meta = p6["artifacts"]["bit"]
    xsa_meta = p6["artifacts"]["xsa"]
    elf_meta = p7["artifacts"]["elf"]
    map_meta = p7["artifacts"]["linker_map"]
    disassembly_meta = p7["inspection"]["disassembly"]
    bitstream = require_file(ROOT / bit_meta["immutable"], bit_meta["sha256"])
    xsa = require_file(ROOT / xsa_meta["immutable"], xsa_meta["sha256"])
    elf = require_file(ROOT / elf_meta["immutable"], elf_meta["sha256"])
    linker_map = require_file(ROOT / map_meta["immutable"], map_meta["sha256"])
    disassembly = require_file(
        ROOT / disassembly_meta["path"], disassembly_meta["sha256"]
    )
    plan = content_addressed_plan()
    ps7_init = require_file(PS7_INIT)
    platform_xsa = materialize_exact_copy(
        xsa,
        ps7_init.parent / xsa.name,
        xsa_meta["sha256"],
    )
    shutdown = require_file(SHUTDOWN_BIT)
    shutdown_sha = sha256_file(shutdown)
    frozen_shutdown = materialize_exact_copy(
        shutdown,
        runner.FROZEN_SHUTDOWN_DIR / f"p7_frozen_shutdown_{shutdown_sha}.bit",
        shutdown_sha,
    )

    common_paths = {
        "plan": plan,
        "bitstream": bitstream,
        "xsa": xsa,
        "elf": elf,
        "profile": require_file(FUNCTIONAL_PROFILE),
        "active_xdc": require_file(ACTIVE_XDC),
        "pinmap": require_file(PINMAP),
        "register_map": require_file(REGISTER_MAP),
        "shutdown_bitstream": shutdown,
        "ps7_init": ps7_init,
        "p6_build_summary": require_file(P6_SUMMARY),
        "p7_build_summary": require_file(P7_SUMMARY),
        "input_seed": require_file(INPUT_SEED),
        "core_readiness": require_file(CORE_READINESS),
        "active_profile": require_file(ACTIVE_PROFILE),
        "lane1_summary": require_file(LANE1_SUMMARY),
    }

    output_dir.mkdir(parents=True, exist_ok=False)
    fixture_path = output_dir / "ddr_external_master_fixture.bin"
    atomic_write(fixture_path, fixture_payload)
    fixture_path = require_file(fixture_path, identity["fixture_sha256"])
    run_configuration_path = output_dir / "run_configuration.json"
    run_configuration = {
        "schema": runner.DDR_RUN_CONFIGURATION_SCHEMA,
        "generated_at_utc": now_utc(),
        "run_id": args.run_id,
        "source_commit": source_commit,
        "mode": "ddr-external-master",
        "execution_scope": "STAGE62_ONLY",
        "stage62_only": True,
        "diagnostic_only": True,
        "coverage_claimed": False,
        "functional_stages_1_61_executed": False,
        "stage62_executed": False,
        "stationary_executed": False,
        "historical_run_reused": False,
        "pattern": args.pattern,
        "address": identity["address"],
        "access_method": args.access_method,
        "length": runner.DDR_EXTERNAL_LENGTH,
        "repetition": args.repetition,
        "unaligned_accesses": bool(args.unaligned_accesses),
        "max_runtime_sec": args.max_runtime_sec,
        "fixture_path": str(fixture_path),
        "fixture_sha256": identity["fixture_sha256"],
        "evidence_dir": str(evidence_dir),
        "new_evidence_directory_required": True,
        "shutdown_before_required": True,
        "shutdown_after_required": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    atomic_json(run_configuration_path, run_configuration)

    source_roles = {
        "runner_python": Path(runner.__file__).resolve(),
        "runner_tcl": runner.PS_EXECUTE_TCL.resolve(),
        "parser": (ROOT / "tools/ddr_external_master_diagnostic.py").resolve(),
    }
    artifacts: list[dict[str, Any]] = [
        artifact_record(
            role="elf",
            path=elf,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="authorization_and_layout_validation_only; DDR mode does not download/start ELF",
            provenance_kind="rebuilt_from_source_commit",
        ),
        artifact_record(
            role="linker_map",
            path=linker_map,
            git_commit=source_commit,
            actual_run_input=False,
            consumption="offline linker evidence",
            provenance_kind="tracked_source_commit",
        ),
        artifact_record(
            role="disassembly",
            path=disassembly,
            git_commit=source_commit,
            actual_run_input=False,
            consumption="offline instruction/layout evidence",
            provenance_kind="tracked_source_commit",
        ),
        artifact_record(
            role="bitstream",
            path=bitstream,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="candidate FPGA image",
            provenance_kind="rebuilt_from_source_commit",
        ),
        artifact_record(
            role="xsa",
            path=xsa,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="authorization/platform provenance validation",
            provenance_kind="rebuilt_from_source_commit",
        ),
        artifact_record(
            role="platform_xsa",
            path=platform_xsa,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="PS7 platform-directory XSA identity",
            provenance_kind="rebuilt_from_source_commit",
        ),
        artifact_record(
            role="platform_ps7_init",
            path=ps7_init,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="PS DDR/platform initialization",
            provenance_kind="rebuilt_platform_from_source_commit",
        ),
        artifact_record(
            role="shutdown_bitstream",
            path=shutdown,
            git_commit=STAGE62_PACKAGING_COMMIT,
            actual_run_input=True,
            consumption="shutdown-before/after source image",
            provenance_kind="exact_hash_reused_from_stage62",
        ),
        artifact_record(
            role="frozen_shutdown_bitstream",
            path=frozen_shutdown,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="content-addressed shutdown-before/after image",
            provenance_kind="generated_exact_copy_from_source_commit",
        ),
        artifact_record(
            role="fixture",
            path=fixture_path,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="external-master write payload",
            provenance_kind="generated_from_source_commit",
        ),
        artifact_record(
            role="microtest_image",
            path=fixture_path,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="DDR boundary microtest image; same immutable fixture bytes",
            provenance_kind="generated_from_source_commit",
        ),
        artifact_record(
            role="run_configuration",
            path=run_configuration_path,
            git_commit=source_commit,
            actual_run_input=True,
            consumption="authorization-bound one-run configuration",
            provenance_kind="generated_from_source_commit",
        ),
    ]
    for role, path in source_roles.items():
        artifacts.append(
            artifact_record(
                role=role,
                path=path,
                git_commit=source_commit,
                actual_run_input=True,
                consumption={
                    "runner_python": "safe orchestration, validation, raw postprocess",
                    "runner_tcl": "XSDB DDR external-master transaction executor",
                    "parser": "raw fixture/readback comparison and deterministic pattern contract",
                }[role],
                provenance_kind="tracked_source_commit",
            )
        )
    extra_roles = {
        "goal_plan": common_paths["plan"],
        "profile": common_paths["profile"],
        "active_xdc": common_paths["active_xdc"],
        "pinmap": common_paths["pinmap"],
        "register_map": common_paths["register_map"],
        "input_seed": common_paths["input_seed"],
        "p6_build_summary": common_paths["p6_build_summary"],
        "p7_build_summary": common_paths["p7_build_summary"],
        "core_readiness": common_paths["core_readiness"],
        "active_profile": common_paths["active_profile"],
        "lane1_promotion_summary": common_paths["lane1_summary"],
    }
    for role, path in extra_roles.items():
        artifacts.append(
            artifact_record(
                role=role,
                path=path,
                git_commit=source_commit,
                actual_run_input=True,
                consumption="safe-wrapper authorization/readiness input",
                provenance_kind="verified_at_source_commit",
            )
        )

    artifact_manifest_path = output_dir / "artifact_manifest.json"
    artifact_manifest = {
        "schema": runner.DDR_RESUME_ARTIFACT_SCHEMA,
        "generated_at_utc": now_utc(),
        "run_id": args.run_id,
        "source_commit": source_commit,
        "status": "READY_FOR_HUMAN_AUTHORIZATION",
        "hardware_actions_executed": False,
        "human_authorization_required": True,
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    atomic_json(artifact_manifest_path, artifact_manifest)
    artifact_manifest_sha = sha256_file(artifact_manifest_path)
    run_configuration_sha = sha256_file(run_configuration_path)

    auth_fields = [
        "# HUMAN APPROVAL REQUIRED: this template is intentionally not a valid authorization.",
        "# After reviewing every bound hash, the human approver must uncomment the next marker,",
        "# change USER_HARDWARE_AUTHORIZATION_FOR_P7 to GRANTED, and save as the expected path.",
        "# P7_STATIONARY_APP_LAYER_APPROVED",
        "AUTHORIZED_STAGE=P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET",
        "USER_HARDWARE_AUTHORIZATION_FOR_P7=REQUIRES_HUMAN_GRANT",
        "AUTHORIZATION_SCOPE=USER_EXPLICIT_DDR_EXTERNAL_MASTER_ONLY_2026-07-14",
        f"BOARD_ID={DEFAULT_BOARD_ID}",
        f"EXPECTED_PART={DEFAULT_PART}",
        f"EXPECTED_TARGET={DEFAULT_TARGET}",
        f"SOURCE_COMMIT={source_commit}",
        f"MAX_RUNTIME_SEC={args.max_runtime_sec}",
        "SHUTDOWN_ON_EXIT=required",
        "NO_ETHERNET=true",
        "NO_MOTION=true",
        "LANE_COUNT=2",
        "MAX_LANE_MASK=0x3",
        "P7_EXECUTION_MODE=DIAGNOSTIC_ONLY",
        "P7_EXECUTION_SCOPE=STAGE62_ONLY",
        "P7_DIAGNOSTIC_ONLY=true",
        "P7_COVERAGE_CLAIMED=false",
        "HARDWARE_ACCEPTANCE=PENDING_HW",
        "FUNCTIONAL_STAGES_1_61_EXECUTED=false",
        "P7_STAGE62_EXECUTED=false",
        "P7_STATIONARY_EXECUTED=false",
        "HISTORICAL_RUN_REUSED=false",
        f"P7_RUN_ID={args.run_id}",
        f"P7_DDR_EXTERNAL_FIXTURE_PATH={auth_line_path(fixture_path)}",
        f"P7_DDR_EXTERNAL_PATTERN={args.pattern}",
        f"P7_DDR_EXTERNAL_ADDRESS={identity['address']}",
        f"P7_DDR_EXTERNAL_ACCESS_METHOD={args.access_method}",
        f"P7_DDR_EXTERNAL_LENGTH={runner.DDR_EXTERNAL_LENGTH}",
        f"P7_DDR_EXTERNAL_REPETITION={args.repetition}",
        "P7_DDR_EXTERNAL_UNALIGNED_ACCESSES="
        + ("true" if args.unaligned_accesses else "false"),
        f"P7_DDR_EXTERNAL_FIXTURE_SHA256={identity['fixture_sha256']}",
        f"P7_DDR_RUN_CONFIGURATION_PATH={auth_line_path(run_configuration_path)}",
        f"P7_DDR_RUN_CONFIGURATION_SHA256={run_configuration_sha}",
        f"P7_DDR_ARTIFACT_MANIFEST_PATH={auth_line_path(artifact_manifest_path)}",
        f"P7_DDR_ARTIFACT_MANIFEST_SHA256={artifact_manifest_sha}",
        f"P7_PLAN_PATH={auth_line_path(common_paths['plan'])}",
        f"P7_PLAN_SHA256={sha256_file(common_paths['plan'])}",
        f"BITSTREAM_PATH={auth_line_path(common_paths['bitstream'])}",
        f"BITSTREAM_SHA256={sha256_file(common_paths['bitstream'])}",
        f"XSA_PATH={auth_line_path(common_paths['xsa'])}",
        f"XSA_SHA256={sha256_file(common_paths['xsa'])}",
        f"ELF_PATH={auth_line_path(common_paths['elf'])}",
        f"ELF_SHA256={sha256_file(common_paths['elf'])}",
        f"PROFILE_PATH={auth_line_path(common_paths['profile'])}",
        f"PROFILE_SHA256={sha256_file(common_paths['profile'])}",
        f"ACTIVE_XDC_PATH={auth_line_path(common_paths['active_xdc'])}",
        f"ACTIVE_XDC_SHA256={sha256_file(common_paths['active_xdc'])}",
        f"PINMAP_PATH={auth_line_path(common_paths['pinmap'])}",
        f"PINMAP_SHA256={sha256_file(common_paths['pinmap'])}",
        f"REGISTER_MAP_PATH={auth_line_path(common_paths['register_map'])}",
        f"REGISTER_MAP_SHA256={sha256_file(common_paths['register_map'])}",
        f"SHUTDOWN_BITSTREAM_PATH={auth_line_path(common_paths['shutdown_bitstream'])}",
        f"SHUTDOWN_BITSTREAM_SHA256={sha256_file(common_paths['shutdown_bitstream'])}",
        f"PS7_INIT_PATH={auth_line_path(common_paths['ps7_init'])}",
        f"PS7_INIT_SHA256={sha256_file(common_paths['ps7_init'])}",
        f"P6_PS_BUILD_SUMMARY_PATH={auth_line_path(common_paths['p6_build_summary'])}",
        f"P6_PS_BUILD_SUMMARY_SHA256={sha256_file(common_paths['p6_build_summary'])}",
        f"P7_PS_BUILD_SUMMARY_PATH={auth_line_path(common_paths['p7_build_summary'])}",
        f"P7_PS_BUILD_SUMMARY_SHA256={sha256_file(common_paths['p7_build_summary'])}",
        f"P7_INPUT_PATH={auth_line_path(common_paths['input_seed'])}",
        f"P7_INPUT_SHA256={sha256_file(common_paths['input_seed'])}",
        "P7_PS_MODE=ddr-external-master",
        "P7_PS_CORE_READINESS=PASS",
        f"P7_PS_CORE_READINESS_PATH={auth_line_path(common_paths['core_readiness'])}",
        f"P7_PS_CORE_READINESS_SHA256={sha256_file(common_paths['core_readiness'])}",
        f"ACTIVE_PROFILE_PATH={auth_line_path(common_paths['active_profile'])}",
        f"ACTIVE_PROFILE_SHA256={sha256_file(common_paths['active_profile'])}",
        f"P7_LANE1_PROMOTION_SUMMARY_PATH={auth_line_path(common_paths['lane1_summary'])}",
        f"P7_LANE1_PROMOTION_SUMMARY_SHA256={sha256_file(common_paths['lane1_summary'])}",
        f"P7_FROZEN_SHUTDOWN_PATH={auth_line_path(frozen_shutdown)}",
        f"P7_FROZEN_SHUTDOWN_SHA256={shutdown_sha}",
        f"P7_COUNTS_PER_SECOND={runner.P7_COUNTS_PER_SECOND}",
    ]
    authorization_template = output_dir / "hardware_authorization.HUMAN_REVIEW_REQUIRED.txt.template"
    atomic_write(authorization_template, ("\n".join(auth_fields) + "\n").encode("utf-8"))

    command = [
        sys.executable,
        str(runner.__file__),
        "--execute-hardware",
        "--authorization-file",
        str(expected_authorization),
        "--authorization-sha256",
        "__HUMAN_APPROVED_FILE_SHA256__",
        "--board-id",
        DEFAULT_BOARD_ID,
        "--expected-part",
        DEFAULT_PART,
        "--expected-target",
        DEFAULT_TARGET,
        "--source-commit",
        source_commit,
        "--plan-file",
        str(common_paths["plan"]),
        "--plan-sha256",
        sha256_file(common_paths["plan"]),
        "--bitstream",
        str(common_paths["bitstream"]),
        "--bitstream-sha256",
        sha256_file(common_paths["bitstream"]),
        "--xsa",
        str(common_paths["xsa"]),
        "--xsa-sha256",
        sha256_file(common_paths["xsa"]),
        "--elf",
        str(common_paths["elf"]),
        "--elf-sha256",
        sha256_file(common_paths["elf"]),
        "--profile",
        str(common_paths["profile"]),
        "--profile-sha256",
        sha256_file(common_paths["profile"]),
        "--active-xdc",
        str(common_paths["active_xdc"]),
        "--active-xdc-sha256",
        sha256_file(common_paths["active_xdc"]),
        "--pinmap",
        str(common_paths["pinmap"]),
        "--pinmap-sha256",
        sha256_file(common_paths["pinmap"]),
        "--register-map",
        str(common_paths["register_map"]),
        "--register-map-sha256",
        sha256_file(common_paths["register_map"]),
        "--shutdown-bitstream",
        str(common_paths["shutdown_bitstream"]),
        "--shutdown-bitstream-sha256",
        sha256_file(common_paths["shutdown_bitstream"]),
        "--max-runtime-sec",
        str(args.max_runtime_sec),
        "--shutdown-on-exit",
        "--no-ethernet",
        "--no-motion",
        "--lane-count",
        "2",
        "--max-lane-mask",
        "0x3",
        "--vivado-path",
        str(DEFAULT_VIVADO),
        "--hw-server-url",
        DEFAULT_HW_SERVER,
        "--mode",
        "ddr-external-master",
        "--stage-name",
        "p7_ddr_external_master_stage62_fixture_rep1",
        "--stage62-only",
        "--run-id",
        args.run_id,
        "--ddr-pattern",
        args.pattern,
        "--ddr-address",
        identity["address"],
        "--ddr-access-method",
        args.access_method,
        "--ddr-repetition",
        str(args.repetition),
        "--ddr-fixture-file",
        str(fixture_path),
        "--ddr-fixture-sha256",
        identity["fixture_sha256"],
        "--ddr-run-configuration",
        str(run_configuration_path),
        "--ddr-run-configuration-sha256",
        run_configuration_sha,
        "--ddr-artifact-manifest",
        str(artifact_manifest_path),
        "--ddr-artifact-manifest-sha256",
        artifact_manifest_sha,
        "--input-file",
        str(common_paths["input_seed"]),
        "--input-sha256",
        sha256_file(common_paths["input_seed"]),
        "--ps7-init",
        str(common_paths["ps7_init"]),
        "--ps7-init-sha256",
        sha256_file(common_paths["ps7_init"]),
        "--p6-build-summary",
        str(common_paths["p6_build_summary"]),
        "--p6-build-summary-sha256",
        sha256_file(common_paths["p6_build_summary"]),
        "--p7-build-summary",
        str(common_paths["p7_build_summary"]),
        "--p7-build-summary-sha256",
        sha256_file(common_paths["p7_build_summary"]),
        "--core-readiness-attestation",
        str(common_paths["core_readiness"]),
        "--core-readiness-attestation-sha256",
        sha256_file(common_paths["core_readiness"]),
        "--active-profile",
        str(common_paths["active_profile"]),
        "--active-profile-sha256",
        sha256_file(common_paths["active_profile"]),
        "--lane1-promotion-summary",
        str(common_paths["lane1_summary"]),
        "--lane1-promotion-summary-sha256",
        sha256_file(common_paths["lane1_summary"]),
        "--xsdb-path",
        str(DEFAULT_XSDB),
        "--jtag-frequency-hz",
        "1000000",
        "--preflight-timeout-sec",
        "180",
        "--shutdown-timeout-sec",
        "240",
        "--sample-interval-sec",
        "10",
        "--idle-deadline-margin-sec",
        "60",
        "--stationary-object-bytes",
        "65536",
        "--evidence-dir",
        str(evidence_dir),
    ]
    if args.unaligned_accesses:
        command.append("--ddr-unaligned-accesses")
    command_template = output_dir / "run_command_after_human_approval.txt"
    atomic_write(
        command_template,
        (
            "# DO NOT RUN until a human-created authorization file exists and its SHA256 replaces the placeholder.\n"
            "# The human/operator must separately set RF_COMM_HW_AUTH=P7_STATIONARY_APP_LAYER_APPROVED.\n"
            + subprocess.list2cmdline(command)
            + "\n"
        ).encode("utf-8"),
    )

    result = {
        "schema": "rf-comm-ddr-resume-gate-preparation-v1",
        "DDR_RESUME_GATE_PREPARED": True,
        "generated_at_utc": now_utc(),
        "run_id": args.run_id,
        "source_commit": source_commit,
        "hardware_actions_executed": False,
        "authorization_environment_modified": False,
        "authorization_granted": False,
        "human_approval_required": True,
        "expected_authorization_file": str(expected_authorization),
        "expected_authorization_file_exists": expected_authorization.is_file(),
        "authorization_template": {
            "path": str(authorization_template),
            "sha256": sha256_file(authorization_template),
        },
        "artifact_manifest": {
            "path": str(artifact_manifest_path),
            "sha256": artifact_manifest_sha,
        },
        "run_configuration": {
            "path": str(run_configuration_path),
            "sha256": run_configuration_sha,
        },
        "fixture": {
            "path": str(fixture_path),
            "sha256": identity["fixture_sha256"],
        },
        "run_command_template": {
            "path": str(command_template),
            "sha256": sha256_file(command_template),
        },
        "next_action": "HUMAN_REVIEW_AND_CREATE_AUTHORIZATION_FILE",
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
    }
    atomic_json(output_dir / "preparation_summary.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare(args)
    except Exception as exc:
        result = {
            "DDR_RESUME_GATE_PREPARED": False,
            "hardware_actions_executed": False,
            "authorization_granted": False,
            "error": f"{type(exc).__name__}: {exc}",
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        }
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 2
    if args.json_summary:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("DDR_RESUME_GATE_PREPARED")
        print(f"authorization_file={result['expected_authorization_file']}")
        print(f"artifact_manifest={result['artifact_manifest']['path']}")
        print("human_approval_required=true")
        print("NO_HARDWARE_ACTIONS_EXECUTED=true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
