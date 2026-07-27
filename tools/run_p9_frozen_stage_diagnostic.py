#!/usr/bin/env python3
"""Run one bounded P9 diagnostic stage with a frozen hardware package.

This is deliberately not a formal/resumable P9 campaign.  It executes one
stage from the immutable runner package, brackets it with the immutable
shutdown image, preserves both the frozen and worktree evaluator results, and
never grants formal acceptance credit.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import types
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTIC_ROOT = ROOT / "evidence/hardware/p9_diagnostics"
FROZEN_RUNTIME_MEMBER = "scripts/p9_hardware_runtime.py"
ALLOWED_HOST_DIAGNOSTIC_DRIFT = {
    "scripts/p9_hardware_runtime.py",
    "scripts/hw/p9_xsdb_stage.tcl",
    "sim/tb/tb_p9_optical_transport_core.sv",
    "tests/test_p9_runner.py",
}
ALLOWED_STAGES = {f"P9-{number:02d}" for number in range(6, 26)}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def git_blob_sha(commit: str, relative: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{relative}"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"unable to read frozen Git blob {commit}:{relative}: "
            f"{result.stderr.decode('utf-8', errors='replace').strip()}"
        )
    return sha256_bytes(result.stdout)


def load_frozen_module(source: bytes, synthetic_file: Path) -> types.ModuleType:
    name = "p9_hardware_runtime_frozen_diagnostic"
    module = types.ModuleType(name)
    module.__file__ = str(synthetic_file)
    module.__package__ = None
    sys.modules[name] = module
    exec(compile(source, str(synthetic_file), "exec"), module.__dict__)
    return module


def load_current_module(path: Path) -> types.ModuleType:
    name = "p9_hardware_runtime_current_diagnostic_evaluator"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load current evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def artifact_path(record: dict[str, Any], key: str) -> Path:
    item = record.get(key)
    if not isinstance(item, dict):
        raise ValueError(f"phase-2 artifact record missing: {key}")
    relative = str(item.get("path", ""))
    expected = str(item.get("sha256", "")).lower()
    path = (ROOT / relative).resolve()
    if not path.is_file() or not inside(path, ROOT / "artifacts/p9"):
        raise ValueError(f"artifact missing or outside artifacts/p9: {key}")
    actual = sha256_file(path)
    if len(expected) != 64 or actual != expected or path.parent.name.lower() != expected:
        raise ValueError(f"content-addressed artifact mismatch: {key}")
    return path


def verify_source_inputs(
    source_manifest: dict[str, Any], source_commit: str
) -> list[dict[str, str]]:
    drift: list[dict[str, str]] = []
    unexpected: list[str] = []
    for item in source_manifest.get("inputs", []):
        if not isinstance(item, dict):
            unexpected.append("non-object source manifest entry")
            continue
        relative = str(item.get("path", "")).replace("\\", "/")
        expected = str(item.get("sha256", "")).lower()
        current = ROOT / relative
        actual = sha256_file(current) if current.is_file() else "MISSING"
        if actual == expected:
            continue
        if relative not in ALLOWED_HOST_DIAGNOSTIC_DRIFT:
            unexpected.append(f"{relative}: expected {expected}, worktree {actual}")
            continue
        blob = git_blob_sha(source_commit, relative)
        if blob != expected:
            unexpected.append(
                f"{relative}: frozen Git blob {blob} does not match manifest {expected}"
            )
            continue
        drift.append(
            {
                "path": relative,
                "frozen_sha256": expected,
                "worktree_sha256": actual,
                "frozen_git_blob_sha256": blob,
                "classification": "HOST_DIAGNOSTIC_ONLY_NO_FROZEN_HW_INPUT_CHANGE",
            }
        )
    if unexpected:
        raise ValueError("unexpected frozen-source drift: " + "; ".join(unexpected))
    return drift


def verify_plan_lane_masks(plan_meta: Path) -> None:
    record = load_json(plan_meta)
    for entry in record.get("entries", []):
        if not isinstance(entry, dict):
            raise ValueError("plan contains a non-object entry")
        if entry.get("kind") == "CASE":
            lane = int(entry.get("lane", -1))
            if lane not in {0, 1, 2, 3}:
                raise ValueError(f"plan lane mask outside 0x0..0x3: {lane:#x}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase2", type=Path, required=True)
    parser.add_argument("--formal-run-root", type=Path, required=True)
    parser.add_argument("--stage", required=True, choices=sorted(ALLOWED_STAGES))
    parser.add_argument("--diagnostic-root", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    phase2 = args.phase2.resolve()
    formal_root = args.formal_run_root.resolve()
    stage = args.stage
    record = load_json(phase2)
    run_id = str(record.get("run_id", ""))
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    diagnostic_root = (
        args.diagnostic_root.resolve()
        if args.diagnostic_root
        else (DIAGNOSTIC_ROOT / run_id / f"{timestamp}_{stage.lower().replace('-', '_')}").resolve()
    )
    if not inside(diagnostic_root, DIAGNOSTIC_ROOT):
        raise ValueError("diagnostic root must stay under evidence/hardware/p9_diagnostics")
    if diagnostic_root.exists() and any(diagnostic_root.iterdir()):
        raise ValueError(f"diagnostic root is not empty: {diagnostic_root}")
    diagnostic_root.mkdir(parents=True, exist_ok=True)
    abort_file = diagnostic_root / "authorization/ABORT_NOW.txt"

    result: dict[str, Any] = {
        "schema_version": 1,
        "status": "DIAGNOSTIC_FAIL",
        "formal_acceptance_credit": False,
        "stage": stage,
        "run_id": run_id,
        "started_utc": utc_now(),
        "diagnostic_root": str(diagnostic_root.relative_to(ROOT)).replace("\\", "/"),
        "phase2": str(phase2.relative_to(ROOT)).replace("\\", "/")
        if inside(phase2, ROOT)
        else str(phase2),
        "phase2_sha256": sha256_file(phase2),
        "wrapper_sha256": sha256_file(Path(__file__)),
        "hardware_actions_executed": False,
        "no_hardware_movement": True,
        "rotation_executed": False,
        "external_network_used": False,
        "maximum_lane_mask": "0x3",
        "errors": [],
    }
    write_json(diagnostic_root / "authorization/diagnostic_authorization.json", result)
    (diagnostic_root / "authorization/NO_MOVEMENT_NETWORK_ATTESTATION.txt").write_text(
        "NO_HARDWARE_MOVEMENT=true\nROTATION_EXECUTED=false\n"
        "EXTERNAL_NETWORK_USED=false\nLOCALHOST_HW_SERVER_USED=true\n"
        "FORMAL_ACCEPTANCE_CREDIT=false\n",
        encoding="ascii",
        newline="\n",
    )

    def handle_signal(signum: int, _frame: Any) -> None:
        abort_file.parent.mkdir(parents=True, exist_ok=True)
        abort_file.write_text(
            f"signal {signum} at {utc_now()}\n", encoding="ascii", newline="\n"
        )
        raise KeyboardInterrupt(f"signal {signum}")

    signal.signal(signal.SIGINT, handle_signal)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_signal)

    frozen: Any = None
    current: Any = None
    paths: dict[str, Path] = {}
    plans: dict[str, dict[str, Any]] = {}
    server_proc: Any = None
    server: dict[str, Any] = {"status": "NOT_RUN"}
    shutdown_before: dict[str, Any] = {"status": "NOT_RUN"}
    shutdown_after: dict[str, Any] = {"status": "NOT_RUN"}
    emergency: dict[str, Any] = {"status": "NOT_RUN"}
    frozen_stage: dict[str, Any] = {"status": "NOT_RUN"}
    current_stage: dict[str, Any] = {"status": "NOT_RUN"}
    hardware_started = False

    try:
        required_phase2 = {
            "authorized": True,
            "scope": "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION",
            "part": "xc7z010clg400-1",
            "profile": "Z7010_2LANE_DEV",
            "maximum_single_test_seconds": 1800,
            "maximum_runtime_seconds": 1800,
            "maximum_lane_mask": 3,
            "stationary": True,
            "movement_allowed": False,
            "rotation_allowed": False,
            "network_allowed": False,
            "ethernet_required": False,
        }
        mismatches = {
            key: {"expected": expected, "actual": record.get(key)}
            for key, expected in required_phase2.items()
            if record.get(key) != expected
        }
        if record.get("lane_masks") != [1, 2, 3] or record.get("allowed_lane_masks") != [1, 2, 3]:
            mismatches["lane_masks"] = {
                "expected": [1, 2, 3],
                "actual": [record.get("lane_masks"), record.get("allowed_lane_masks")],
            }
        if mismatches:
            raise ValueError(f"phase-2 authorization mismatch: {mismatches}")

        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        ).stdout.strip()
        source_commit = str(record.get("source_commit", ""))
        if current_head != source_commit:
            raise ValueError(f"HEAD {current_head} does not equal frozen source {source_commit}")

        for key in (
            "candidate_bitstream", "shutdown_bitstream", "ps_elf", "ps7_init_tcl",
            "bsp_archive", "runner_package", "hardware_config", "source_manifest",
        ):
            paths[key] = artifact_path(record, key)
        source_manifest = load_json(paths["source_manifest"])
        if source_manifest.get("status") != "PASS" or source_manifest.get("source_commit") != source_commit:
            raise ValueError("source manifest identity/status mismatch")
        drift = verify_source_inputs(source_manifest, source_commit)
        result["worktree_drift"] = drift

        expected_input_hashes = {
            str(item.get("path", "")).replace("\\", "/"): str(item.get("sha256", "")).lower()
            for item in source_manifest.get("inputs", []) if isinstance(item, dict)
        }
        runner_hash = str(record["runner_package"]["sha256"]).lower()
        if sha256_file(paths["runner_package"]) != runner_hash:
            raise ValueError("runner package SHA-256 mismatch")
        with zipfile.ZipFile(paths["runner_package"], "r") as archive:
            matches = [item for item in archive.infolist() if item.filename == FROZEN_RUNTIME_MEMBER]
            if len(matches) != 1:
                raise ValueError("runner package must contain exactly one frozen runtime member")
            frozen_source = archive.read(matches[0])
        frozen_runtime_hash = sha256_bytes(frozen_source)
        if frozen_runtime_hash != expected_input_hashes.get(FROZEN_RUNTIME_MEMBER):
            raise ValueError("frozen runtime member does not match source manifest")

        frozen = load_frozen_module(frozen_source, ROOT / FROZEN_RUNTIME_MEMBER)
        current_runtime = ROOT / FROZEN_RUNTIME_MEMBER
        current_runtime_hash = sha256_file(current_runtime)
        current = load_current_module(current_runtime)
        result["frozen_runtime_sha256"] = frozen_runtime_hash
        result["current_diagnostic_evaluator_sha256"] = current_runtime_hash
        result["runner_package_sha256"] = runner_hash

        validated_record, validated_paths, validation_errors = frozen.validate_phase2(phase2)
        expected_validation_errors = {
            f"current build input differs from frozen manifest: {relative}"
            for relative in ALLOWED_HOST_DIAGNOSTIC_DRIFT
            if any(item["path"] == relative for item in drift)
        }
        if set(validation_errors) != expected_validation_errors:
            raise ValueError(
                "frozen phase-2 validation produced unexpected errors: "
                f"expected={sorted(expected_validation_errors)} actual={validation_errors}"
            )
        if validated_record.get("run_id") != run_id:
            raise ValueError("frozen validator returned a different run id")
        paths_for_stage = {
            "candidate": validated_paths["candidate"],
            "shutdown": validated_paths["shutdown"],
            "elf": validated_paths["elf"],
            "ps7_init": validated_paths["ps7_init"],
        }

        plans = frozen.write_plans(diagnostic_root)
        plan = plans[stage]
        frozen_formal_plan = formal_root / "authorization/plans" / f"{stage}.plan.txt"
        formal_auth = load_json(formal_root / "authorization/authorization_record.json")
        expected_plan_hash = str(formal_auth.get("plan_sha256", {}).get(stage, "")).lower()
        if not frozen_formal_plan.is_file():
            raise ValueError(f"formal frozen plan is missing: {frozen_formal_plan}")
        formal_plan_hash = sha256_file(frozen_formal_plan)
        if not expected_plan_hash or plan["sha256"] != expected_plan_hash or formal_plan_hash != expected_plan_hash:
            raise ValueError(
                f"deterministic plan mismatch: generated={plan['sha256']} "
                f"formal={formal_plan_hash} authorized={expected_plan_hash}"
            )
        verify_plan_lane_masks(Path(plan["meta"]))
        result["plan_sha256"] = expected_plan_hash
        result["plan_entry_count"] = plan["entry_count"]

        for relative in (
            "raw_logs", "target_identity", "safe_idle", "raw_lane_matrix",
            "phy_rate", "selective_repeat", "sack_ack", "fault_injection",
            "dma_ddr_cache", "scheduler", "rfap", "performance",
            "stationary_30min", "shutdown", "current_evaluator", "final",
        ):
            (diagnostic_root / relative).mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        env["NO_HARDWARE"] = "0"
        env["RF_COMM_P9_HW_AUTH"] = "P9_PHASE2_IMMUTABLE_AUTHORIZED"
        env["RF_COMM_P9_DIAGNOSTIC_ONLY"] = "1"
        server_proc, server = frozen.start_hw_server(diagnostic_root / "raw_logs")
        write_json(diagnostic_root / "target_identity/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(f"hw_server start failed: {server}")
        hardware_started = True
        result["hardware_actions_executed"] = True

        shutdown_before = frozen.invoke_shutdown(
            diagnostic_root, phase2, paths_for_stage["shutdown"],
            f"{stage.lower().replace('-', '_')}_diagnostic_before", env, abort_file,
        )
        if shutdown_before.get("status") != "PASS":
            raise RuntimeError(f"{stage} diagnostic shutdown-before failed")

        frozen_stage = frozen.invoke_stage(
            stage, diagnostic_root, phase2, paths_for_stage, plan, env, abort_file
        )
        raw_result_relative = frozen_stage.get("raw_result")
        if not raw_result_relative:
            raise RuntimeError(f"{stage} frozen evaluator did not preserve a raw result path")
        frozen_stage_dir = (ROOT / str(raw_result_relative)).resolve().parent
        evaluation_copy = diagnostic_root / "current_evaluator" / stage.lower().replace("-", "_")
        shutil.copytree(frozen_stage_dir, evaluation_copy)
        current_stage = current.evaluate_stage(
            stage,
            evaluation_copy,
            frozen_stage["process"],
            evaluation_copy / "xsdb_stage_result.txt",
        )

        markers = frozen.parse_markers(frozen_stage_dir / "xsdb_stage_result.txt")
        required_markers = {
            "P9_XSDB_CABLE_ROOT_COUNT": "1",
            "P9_XSDB_JTAG_DEVICE_COUNT": "2",
            "P9_XSDB_EXACT_FPGA_MATCH_COUNT": "1",
            "P9_XSDB_IDENTITY": "PASS",
            "P9_XSDB_BOARD_ID": "210512180081",
            "P9_XSDB_IDCODE": "13722093",
            "P9_XSDB_STAGE": stage,
            "P9_XSDB_RUN_ID": run_id,
            "P9_CANDIDATE_PROGRAMMED": "1",
            "P9_PS_ELF_DOWNLOADED": "1",
            "P9_ENDPOINT_SHUTDOWN": "PASS",
            "P9_XSDB_STAGE_RESULT": "PASS",
        }
        marker_mismatches = {
            key: {"expected": value, "actual": markers.get(key)}
            for key, value in required_markers.items() if markers.get(key) != value
        }
        process_pass = (
            frozen_stage.get("process", {}).get("returncode") == 0
            and not frozen_stage.get("process", {}).get("timed_out")
            and not frozen_stage.get("process", {}).get("interrupted")
        )
        frozen_errors = list(frozen_stage.get("errors", []))
        known_frozen_evaluator_bug_only = bool(frozen_errors) and all(
            error.endswith("exact duty limits do not equal 20%/18% of 64k cycles")
            for error in frozen_errors
        )
        result["frozen_evaluator"] = {
            "status": frozen_stage.get("status"),
            "errors": frozen_errors,
            "known_strict_duty_host_bug_only": known_frozen_evaluator_bug_only,
        }
        result["current_evaluator"] = {
            "status": current_stage.get("status"),
            "errors": current_stage.get("errors", []),
        }
        result["stage_process_pass"] = process_pass
        result["marker_mismatches"] = marker_mismatches
        if not process_pass or marker_mismatches:
            raise RuntimeError(
                f"{stage} raw hardware stage did not pass: "
                f"process_pass={process_pass} marker_mismatches={marker_mismatches}"
            )
        if current_stage.get("status") != "PASS":
            raise RuntimeError(
                f"{stage} current evaluator failed: {current_stage.get('errors', [])}"
            )
        if frozen_stage.get("status") != "PASS" and not known_frozen_evaluator_bug_only:
            raise RuntimeError(
                f"{stage} frozen evaluator had errors beyond the known duty-host bug: {frozen_errors}"
            )
    except KeyboardInterrupt as exc:
        result["errors"].append(f"KeyboardInterrupt: {exc}")
    except BaseException as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if hardware_started and frozen is not None and paths.get("shutdown_bitstream", Path()).is_file():
            env = os.environ.copy()
            env["NO_HARDWARE"] = "0"
            env["RF_COMM_P9_HW_AUTH"] = "P9_PHASE2_IMMUTABLE_AUTHORIZED"
            env["RF_COMM_P9_DIAGNOSTIC_ONLY"] = "1"
            try:
                shutdown_after = frozen.invoke_shutdown(
                    diagnostic_root, phase2, paths["shutdown_bitstream"],
                    f"{stage.lower().replace('-', '_')}_diagnostic_after", env, abort_file,
                )
            except BaseException as exc:
                shutdown_after = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
                result["errors"].append("shutdown-after invocation raised an exception")
            try:
                emergency = frozen.invoke_shutdown(
                    diagnostic_root, phase2, paths["shutdown_bitstream"],
                    "diagnostic_finally_emergency", env, abort_file,
                )
            except BaseException as exc:
                emergency = {"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}
                result["errors"].append("finally-emergency shutdown invocation raised an exception")
        if server_proc is not None and frozen is not None:
            frozen.terminate_tree(server_proc)

    result["hw_server"] = server
    result["shutdown_before"] = shutdown_before
    result["shutdown_after"] = shutdown_after
    result["finally_emergency_shutdown"] = emergency
    shutdowns_pass = (
        all(entry.get("status") == "PASS"
            for entry in (shutdown_before, shutdown_after, emergency))
        if hardware_started else True
    )
    stage_pass = (
        result.get("stage_process_pass") is True
        and not result.get("marker_mismatches")
        and current_stage.get("status") == "PASS"
        and (
            frozen_stage.get("status") == "PASS"
            or result.get("frozen_evaluator", {}).get("known_strict_duty_host_bug_only") is True
        )
    )
    if hardware_started and not shutdowns_pass:
        result["errors"].append("one or more mandatory shutdown operations did not pass")
    if stage_pass and shutdowns_pass and not result["errors"]:
        result["status"] = "DIAGNOSTIC_PASS"
    result["shutdowns_pass"] = shutdowns_pass
    result["ended_utc"] = utc_now()
    write_json(diagnostic_root / "final/diagnostic_result.json", result)
    print(f"P9_DIAGNOSTIC_STATUS={result['status']}")
    print(f"P9_DIAGNOSTIC_STAGE={stage}")
    print(f"P9_DIAGNOSTIC_ROOT={diagnostic_root}")
    return 0 if result["status"] == "DIAGNOSTIC_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
