#!/usr/bin/env python3
"""Fail-closed P10.3F staircase/formal hardware runner.

The script is inert unless an exact immutable current-run authorization,
``--execute-hardware``, and the two hardware environment gates are all present.
Every functional-image exit archives first-fault state before the independent
dual shutdown bitstreams are programmed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from archive_p10_fault_forensics import parse_psv, write_archive
from p10_hardware_runtime import (
    EXPECTED_FIXED_SERIAL,
    EXPECTED_ROTATING_SERIAL,
    XSDB,
    extract_ps7_init,
    invoke_shutdown,
    parse_markers,
    run_bounded,
    start_hw_server,
    terminate_tree,
)


ROOT = Path(__file__).resolve().parents[1]
SCOPE = "P10_3_FIRST_FAULT_FORENSICS_STAIRCASE_HARDWARE_FOLLOWUP"
GOAL = ROOT / "goals/P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE_GOAL.md"
GOAL_SHA256 = "6d92924f15ce64eec6e64ab1cf316c14397533e1dc08f3560d6c55d8c7bdd281"
FREEZE = ROOT / "evidence/generated/p10_3_fault_forensics_artifact_freeze.json"
AUTH = ROOT / "config/p10_3f_current_run_hardware_authorization.json"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
FORENSIC_TCL = ROOT / "scripts/hw/p10_3f_fault_forensics.tcl"
HW_ROOT = ROOT / "evidence/hardware/p10_3_fault_forensics"
EXPECTED_BUILD = {"fixed": 0x50334646, "rotating": 0x50334652}
RUN_RE = re.compile(r"^p10_3f_[0-9]{8}T[0-9]{6}Z_[0-9a-f]{8}$")
LEVELS = (
    (0, 1024, 0xF3000100),
    (1, 4096, 0xF3000401),
    (2, 16384, 0xF3001002),
    (3, 65536, 0xF3004003),
    (4, 262144, 0xF3010004),
)
TARGET_DUTY = 11520
HARD_DUTY = 12799


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def artifact_key(item: dict[str, Any]) -> str:
    return f"{item['role']}:{item['kind']}"


def load_and_validate_authorization(
    path: Path, run_id: str
) -> tuple[dict[str, Any], dict[str, Path], list[str]]:
    errors: list[str] = []
    try:
        freeze = load_json(FREEZE)
        record = load_json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return {}, {}, [f"authorization/freeze read failed: {exc}"]
    expected_scalar = {
        "schema_version": 1,
        "authorization_id": "P10_3F-CURRENT-RUN-IMMUTABLE",
        "scope": SCOPE,
        "run_id": run_id,
        "authorized": True,
        "consumed": False,
        "current_run_hardware_authorization": True,
        "no_hardware": False,
        "source_commit": freeze.get("source_commit"),
        "goal_sha256": GOAL_SHA256,
        "fixed_jtag_serial": EXPECTED_FIXED_SERIAL,
        "rotating_jtag_serial": EXPECTED_ROTATING_SERIAL,
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "ethernet_allowed": False,
        "movement_or_rewiring_allowed": False,
    }
    for key, expected in expected_scalar.items():
        if record.get(key) != expected:
            errors.append(f"authorization {key} mismatch")
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("P10.3F artifact freeze is not acceptance eligible")
    if record.get("artifact_freeze_sha256") != sha256(FREEZE):
        errors.append("authorization artifact-freeze hash mismatch")
    required_policy = {
        "shutdown_before": True,
        "archive_before_independent_shutdown": True,
        "shutdown_on_error_timeout_ctrl_c_and_normal_exit": True,
        "verify_both_shutdown_markers": True,
        "clear_frozen_capture_before_shutdown_program": False,
    }
    if record.get("shutdown_policy") != required_policy:
        errors.append("authorization shutdown/archive policy mismatch")
    if record.get("allowed_stages") != ["staircase", "formal"]:
        errors.append("authorization stage set mismatch")
    frozen_records = freeze.get("artifacts", [])
    auth_records = record.get("artifacts", [])
    frozen_by_key = {
        artifact_key(item): item for item in frozen_records if isinstance(item, dict)
    }
    auth_by_key = {
        artifact_key(item): item for item in auth_records if isinstance(item, dict)
    }
    required = {
        f"{role}:{kind}"
        for role in ("fixed", "rotating")
        for kind in ("shutdown_bitstream", "functional_bitstream", "xsa", "bsp", "elf")
    }
    if set(frozen_by_key) != required or set(auth_by_key) != required:
        errors.append("authorization/freeze artifact set mismatch")
    artifacts: dict[str, Path] = {}
    for key in sorted(required & set(frozen_by_key) & set(auth_by_key)):
        frozen_item = frozen_by_key[key]
        auth_item = auth_by_key[key]
        if auth_item != frozen_item:
            errors.append(f"authorization artifact record differs from freeze: {key}")
            continue
        candidate = (ROOT / frozen_item["path"]).resolve()
        try:
            candidate.relative_to((ROOT / "artifacts/p10_3_fault_forensics").resolve())
        except ValueError:
            errors.append(f"artifact escapes P10.3F content store: {key}")
            continue
        if not candidate.is_file() or sha256(candidate) != frozen_item.get("sha256") or \
                candidate.stat().st_size != frozen_item.get("bytes"):
            errors.append(f"artifact hash/size mismatch: {key}")
            continue
        artifacts[key] = candidate
    return record, artifacts, errors


def case_line(label: str, size: int, direction: int, object_id: int) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", label):
        raise ValueError("unsafe staircase label")
    values = (
        "CASE", label, 3, 0, 2, 15, direction, 2, 0x01010101, size,
        32, 1, 0, 0, 120000, 0xA1030001, 0x103, object_id,
        0, 0, 0, 0, 1024, 0, 0, 0, 0, 0, 0,
    )
    return " ".join(str(value) for value in values)


def staircase_plan(level: int, size: int, tag: int) -> str:
    base = 0x7F000000 + level * 0x10
    return "\n".join((
        "# P10.3F immutable two-direction staircase level",
        f"P10FF_CHECKPOINT staircase_{size}B 0x{tag:08X}",
        case_line(f"staircase_{size}B_f2r", size, 0, base),
        case_line(f"staircase_{size}B_r2f", size, 1, base + 1),
        "",
    ))


def formal_plan() -> str:
    return "# P10.3F exact 1800-second bounded formal\n" \
        "P10FF_FORMAL stationary_30min 1800\n"


def parse_snapshot(path: Path, role: str) -> list[str]:
    errors: list[str] = []
    values = [int(value, 0) for value in path.read_text(encoding="ascii").strip().split("|")]
    if len(values) != 130:
        return [f"{path.name}: snapshot length {len(values)}"]
    generation, schema, *words = values
    if generation & 1 or schema != 0x50310201 or words[127] != schema:
        errors.append(f"{path.name}: atomic schema/generation mismatch")
    if ((words[0] >> 24) & 0xFF, (words[0] >> 16) & 0xFF,
            (words[0] >> 8) & 0xFF, words[0] & 0xFF) != (247, 32, 4, 8):
        errors.append(f"{path.name}: four-lane capability mismatch")
    if ((words[1] >> 8) & 0xF) != 0:
        errors.append(f"{path.name}: safety fault mask nonzero")
    if (words[124], words[125], words[126]) != (64000, HARD_DUTY, TARGET_DUTY):
        errors.append(f"{path.name}: duty contract mismatch")
    first = 0 if role == "fixed" else 4
    for module in range(first, first + 4):
        base = 56 + 8 * module
        if words[base + 2] > 64:
            errors.append(f"{path.name}: module{module} continuous high >64 cycles")
        if words[base + 3] > TARGET_DUTY:
            errors.append(f"{path.name}: module{module} duty target exceeded")
        if words[base + 3] > HARD_DUTY or words[base + 7] != 0:
            errors.append(f"{path.name}: module{module} hard duty fault")
    for index, name in ((120, "overlap"), (121, "admission"),
                        (122, "non_target"), (123, "cross_lane")):
        if words[index]:
            errors.append(f"{path.name}: {name} violation={words[index]}")
    return errors


def invoke_stage(
    label: str,
    tcl_stage: str,
    plan_text: str,
    run_root: Path,
    auth: Path,
    artifacts: dict[str, Path],
    ps7: dict[str, Path],
    env: dict[str, str],
    timeout: int,
) -> tuple[dict[str, Any], Path]:
    stage_dir = run_root / "stages" / label
    dump_dir = stage_dir / "dumps"
    dump_dir.mkdir(parents=True, exist_ok=False)
    plan = stage_dir / "immutable.plan"
    write_text(plan, plan_text)
    result_file = stage_dir / "xsdb.result.txt"
    command = [
        str(XSDB), str(STAGE_TCL), "tcp:localhost:3121",
        EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL,
        str(artifacts["fixed:functional_bitstream"]),
        str(artifacts["rotating:functional_bitstream"]),
        str(artifacts["fixed:elf"]), str(artifacts["rotating:elf"]),
        str(ps7["fixed"]), str(ps7["rotating"]), str(plan), str(dump_dir),
        str(run_root / "authorization/ABORT_NOW.txt"), str(result_file),
        tcl_stage, str(auth), run_root.name,
        f"0x{EXPECTED_BUILD['fixed']:08X}",
        f"0x{EXPECTED_BUILD['rotating']:08X}",
    ]
    process = run_bounded(
        command, stage_dir / "xsdb.stdout.log", stage_dir / "xsdb.stderr.log",
        timeout, env,
    )
    return process, stage_dir


def evaluate_stage(
    label: str, stage_dir: Path, process: dict[str, Any], formal: bool
) -> dict[str, Any]:
    markers = parse_markers(stage_dir / "xsdb.result.txt")
    errors: list[str] = []
    if process.get("returncode") != 0 or process.get("timed_out"):
        errors.append("XSDB process failed or timed out")
    if markers.get("P10_XSDB_STAGE_RESULT") != "PASS" or \
            markers.get("P10_SAFE_BOOT") != "PASS":
        errors.append("stage/safe-boot PASS marker missing")
    snapshots = sorted((stage_dir / "dumps").glob("*.p10_2.psv"))
    if not snapshots:
        errors.append("no atomic safety snapshots")
    for path in snapshots:
        role = "fixed" if ".fixed." in path.name else \
            "rotating" if ".rotating." in path.name else ""
        if not role:
            errors.append(f"unbound snapshot role: {path.name}")
        else:
            errors.extend(parse_snapshot(path, role))
    observations_path = stage_dir / "dumps/observations.psv"
    observations: list[dict[str, str]] = []
    if observations_path.is_file():
        with observations_path.open(encoding="utf-8", newline="") as handle:
            observations = list(csv.DictReader(handle, delimiter="|"))
    if formal:
        if markers.get("P10_3F_FORMAL_RESULT") != "PASS" or \
                int(markers.get("P10_3F_FORMAL_ELAPSED_MS", "0")) not in range(
                    1_800_000, 1_800_501
                ):
            errors.append("formal duration/result marker mismatch")
        goodput: dict[str, float] = {}
        for suffix in ("formal_f2r", "formal_r2f"):
            requested = sum(
                int(row["size"], 0) for row in observations
                if suffix in row.get("window", "")
            )
            goodput[suffix] = requested * 8 / 840
            if goodput[suffix] < 8_000_000:
                errors.append(f"{suffix} application goodput below 8 Mbit/s")
    else:
        body = [row for row in observations
                if not row.get("label", "").endswith("endpoint_shutdown")]
        if len(body) != 2 or {int(row["direction"], 0) for row in body} != {0, 1}:
            errors.append("staircase level did not complete exactly both directions")
        goodput = {}
    summary = {
        "schema_version": 1,
        "test_id": f"P10_3F-{label.upper()}",
        "status": "PASS" if not errors else "FAIL",
        "process": process,
        "markers": markers,
        "snapshot_count": len(snapshots),
        "observation_count": len(observations),
        "application_goodput_bps": goodput,
        "errors": errors,
    }
    write_json(stage_dir / "stage_summary.json", summary)
    return summary


def capture_and_archive(
    label: str,
    run_root: Path,
    auth: Path,
    env: dict[str, str],
) -> dict[str, Any]:
    out = run_root / "forensics" / label
    out.mkdir(parents=True, exist_ok=True)
    capture_result = out / "capture.result.txt"
    command = [
        str(XSDB), str(FORENSIC_TCL), "capture", "tcp:localhost:3121",
        EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL, str(out), str(auth),
        run_root.name, f"0x{EXPECTED_BUILD['fixed']:08X}",
        f"0x{EXPECTED_BUILD['rotating']:08X}", str(capture_result),
    ]
    process = run_bounded(
        command, out / "capture.stdout.log", out / "capture.stderr.log", 180, env
    )
    errors: list[str] = []
    archives: list[dict[str, Any]] = []
    if process.get("returncode") != 0 or process.get("timed_out") or \
            parse_markers(capture_result).get("P10_FF_FORENSIC_RESULT") != "PASS":
        errors.append("forensic XSDB capture failed")
    if not errors:
        try:
            for role in ("fixed", "rotating"):
                archives.append(write_archive(parse_psv(out / f"{role}.p10ff.psv"), out))
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(f"forensic binary/JSON archive failed: {exc}")
    frozen = [item for item in archives if item["status"] == "FROZEN"]
    commit_process = None
    if frozen and not errors:
        digest = {item["role"]: item["binary_sha256"] for item in frozen}
        commit_result = out / "commit.result.txt"
        command = [
            str(XSDB), str(FORENSIC_TCL), "commit", "tcp:localhost:3121",
            EXPECTED_FIXED_SERIAL, EXPECTED_ROTATING_SERIAL, str(out), str(auth),
            run_root.name, f"0x{EXPECTED_BUILD['fixed']:08X}",
            f"0x{EXPECTED_BUILD['rotating']:08X}", str(commit_result),
            digest.get("fixed", "NONE"), digest.get("rotating", "NONE"),
        ]
        commit_process = run_bounded(
            command, out / "commit.stdout.log", out / "commit.stderr.log", 180, env
        )
        if commit_process.get("returncode") != 0 or commit_process.get("timed_out") or \
                parse_markers(commit_result).get("P10_FF_FORENSIC_RESULT") != "PASS":
            errors.append("forensic archive commit failed")
    summary = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "label": label,
        "capture_process": process,
        "commit_process": commit_process,
        "archives": archives,
        "frozen_roles": [item["role"] for item in frozen],
        "explicit_clear_executed": False,
        "errors": errors,
    }
    write_json(out / "summary.json", summary)
    return summary


def guarded_shutdown(
    run_root: Path,
    auth: Path,
    artifacts: dict[str, Path],
    label: str,
    env: dict[str, str],
) -> dict[str, Any]:
    try:
        return invoke_shutdown(run_root, auth, artifacts, label, env, retry_limit=2)
    except BaseException as exc:
        result = {"status": "FAIL", "label": label, "exception": repr(exc)}
        write_json(run_root / "shutdown" / label / "wrapper_exception.json", result)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorization", type=Path, default=AUTH)
    parser.add_argument("--run-id")
    parser.add_argument("--execute-hardware", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    if not args.run_id or not RUN_RE.fullmatch(args.run_id):
        print("P10_3F_RUNNER_REFUSED=VALID_UNIQUE_RUN_ID_REQUIRED", file=sys.stderr)
        return 3
    auth = args.authorization.resolve()
    record, artifacts, errors = load_and_validate_authorization(auth, args.run_id)
    if args.validate_only:
        print(json.dumps({"status": "PASS" if not errors else "FAIL",
                          "errors": errors}, indent=2))
        return 0 if not errors else 3
    if not args.execute_hardware:
        errors.append("--execute-hardware is required")
    if os.environ.get("NO_HARDWARE") != "0" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "true":
        errors.append("NO_HARDWARE=0 and CURRENT_RUN_HARDWARE_AUTHORIZATION=true required")
    run_root = HW_ROOT / args.run_id
    if run_root.exists():
        errors.append("run_id evidence directory already exists")
    if errors:
        print(json.dumps({"status": "FAIL_PRECONDITION", "errors": errors}, indent=2),
              file=sys.stderr)
        return 3

    for name in ("authorization", "artifacts", "stages", "forensics", "shutdown",
                 "raw_logs", "final"):
        (run_root / name).mkdir(parents=True, exist_ok=False)
    shutil.copy2(auth, run_root / "authorization/immutable_authorization.json")
    shutil.copy2(FREEZE, run_root / "artifacts/artifact_freeze.json")
    ps7: dict[str, Path] = {}
    for role in ("fixed", "rotating"):
        destination = run_root / "artifacts" / role / "ps7_init.tcl"
        extract_ps7_init(artifacts[f"{role}:xsa"], destination)
        ps7[role] = destination
    env = {
        **os.environ,
        "NO_HARDWARE": "0",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "true",
        "RF_COMM_P10_HW_AUTH": "P10_3F_IMMUTABLE_AUTHORIZED",
    }
    server_proc = None
    stage_results: list[dict[str, Any]] = []
    forensic_results: list[dict[str, Any]] = []
    shutdown_results: list[dict[str, Any]] = []
    campaign_errors: list[str] = []
    functional_loaded = False
    try:
        server_proc, server = start_hw_server(run_root / "raw_logs")
        write_json(run_root / "raw_logs/hw_server.json", server)
        if server.get("status") != "PASS":
            raise RuntimeError(server.get("reason", "hw_server unavailable"))
        initial = guarded_shutdown(run_root, auth, artifacts, "initial", env)
        shutdown_results.append(initial)
        if initial.get("status") != "PASS":
            raise RuntimeError("initial dual shutdown unconfirmed")
        for level, size, tag in LEVELS:
            before = guarded_shutdown(
                run_root, auth, artifacts, f"staircase_{level}_before", env
            )
            shutdown_results.append(before)
            if before.get("status") != "PASS":
                raise RuntimeError(f"staircase level {level} shutdown-before failed")
            functional_loaded = True
            process, stage_dir = invoke_stage(
                f"staircase_{level}_{size}B", "P10_3F-STAIRCASE",
                staircase_plan(level, size, tag), run_root, auth, artifacts, ps7,
                env, 900,
            )
            forensic = capture_and_archive(
                f"staircase_{level}_{size}B", run_root, auth, env
            )
            forensic_results.append(forensic)
            after = guarded_shutdown(
                run_root, auth, artifacts, f"staircase_{level}_after", env
            )
            shutdown_results.append(after)
            functional_loaded = False
            stage = evaluate_stage(
                f"staircase_{level}_{size}B", stage_dir, process, formal=False
            )
            stage["forensics_status"] = forensic["status"]
            stage["shutdown_after_status"] = after.get("status")
            stage_results.append(stage)
            if forensic["status"] != "PASS" or forensic["frozen_roles"] or \
                    after.get("status") != "PASS" or stage["status"] != "PASS":
                raise RuntimeError(f"staircase level {level} failed closed")

        before = guarded_shutdown(run_root, auth, artifacts, "formal_before", env)
        shutdown_results.append(before)
        if before.get("status") != "PASS":
            raise RuntimeError("formal shutdown-before failed")
        functional_loaded = True
        process, stage_dir = invoke_stage(
            "formal_1800s", "P10_3F-FORMAL", formal_plan(), run_root, auth,
            artifacts, ps7, env, 2100,
        )
        forensic = capture_and_archive("formal_1800s", run_root, auth, env)
        forensic_results.append(forensic)
        after = guarded_shutdown(run_root, auth, artifacts, "formal_after", env)
        shutdown_results.append(after)
        functional_loaded = False
        stage = evaluate_stage("formal_1800s", stage_dir, process, formal=True)
        stage["forensics_status"] = forensic["status"]
        stage["shutdown_after_status"] = after.get("status")
        stage_results.append(stage)
        if forensic["status"] != "PASS" or forensic["frozen_roles"] or \
                after.get("status") != "PASS" or stage["status"] != "PASS":
            raise RuntimeError("formal stage failed closed")
    except KeyboardInterrupt:
        campaign_errors.append("Ctrl+C")
    except Exception as exc:
        campaign_errors.append(str(exc))
    finally:
        if functional_loaded:
            try:
                forensic_results.append(capture_and_archive(
                    "finally_before_shutdown", run_root, auth, env
                ))
            except BaseException as exc:
                campaign_errors.append(f"finally forensic archive failed: {exc}")
        emergency = guarded_shutdown(run_root, auth, artifacts, "finally", env)
        shutdown_results.append(emergency)
        if emergency.get("status") != "PASS":
            campaign_errors.append("finally dual shutdown unconfirmed")
        if server_proc is not None:
            try:
                terminate_tree(server_proc)
            except Exception as exc:
                campaign_errors.append(f"hw_server termination failed: {exc}")
    status = "PASS" if not campaign_errors and len(stage_results) == 6 and all(
        item["status"] == "PASS" for item in stage_results
    ) and all(item.get("status") == "PASS" for item in shutdown_results) else "FAIL"
    summary = {
        "schema_version": 1,
        "test_id": "P10_3F-STAIRCASE-FORMAL-HARDWARE",
        "status": status,
        "scope": SCOPE,
        "run_id": args.run_id,
        "source_commit": record["source_commit"],
        "hardware_actions_executed": True,
        "ethernet_used": False,
        "maximum_lane_mask": 15,
        "maximum_single_formal_run_seconds": 1800,
        "stages": stage_results,
        "forensics": forensic_results,
        "shutdowns": shutdown_results,
        "errors": campaign_errors,
        "generated_at_utc": utc_now(),
    }
    write_json(run_root / "final/summary.json", summary)
    print(f"P10_3F_HARDWARE_RESULT={status}")
    print(f"P10_3F_RUN_ID={args.run_id}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
