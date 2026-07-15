#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MAIN = Path(r"C:\Users\user\Documents\RF_COMM_MULTILANE")
SOURCE = Path(r"C:\Users\user\.codex\worktrees\r41formal_946ccba\RF_COMM_MULTILANE")
RUN_ID = "p7_20260715_stationary_app_r41_formal_full"
SOURCE_COMMIT = "946ccbad66d64d715ad6745449b95f6c261ddf76"
PLAN_SHA256 = "a37d652de98239b8e654a9467b21bdcb660c3d896ad40e1415de7c8e1ed5f794"
LEDGER_SHA256 = "a86ec2a8e326a5354e9e79abed71ca938a3aa7a54b6936bc961beaf668ddba64"
RAW_TREE_SHA256 = "3501544a5fcd13458cbeb280e3e0a617430e8d8671ef8be5d90f5b6e7ebefa91"
OFFLINE_CHECKPOINT_SHA256 = "308e6215272df86b2c9a3a382f00b37e221449ed39bf83af80f089dd0c50830d"
SHUTDOWN_SHA256 = "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810"
FAILING_TCL_SHA256 = "9c0251d30b723c015b87e7fc399212d719c75f70a7f6fb57da2d2888868fd5ec"
EXPECTED_ORDINALS = list(range(1, 67))

RAW_ROOT = SOURCE / "evidence/hardware/p7/authorized_sequence" / RUN_ID
BUILD_ROOT = SOURCE / "build/p7_authorized_sequence" / RUN_ID
PACKAGE = MAIN / "evidence/generated/p7_r41_formal_failure_package"
CLASSIFICATION = MAIN / "evidence/generated/p7_r41_formal_failure.json"
REPLAY = MAIN / "evidence/generated/p7_r41_summarizer_replay"
REPLAY_RESULT = MAIN / "evidence/generated/p7_r41_summarizer_replay_result.json"
CHECKPOINT = MAIN / "evidence/generated/p7_r41validate_946ccba_checkpoint.json"
CHECKPOINT_DIR = MAIN / "evidence/generated/p7_r41validate_946ccba_checkpoint"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_record(path: Path, root: Path) -> dict[str, object]:
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def tree_record(root: Path, *, exclude: set[str] | None = None) -> dict[str, object]:
    excluded = exclude or set()
    files = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.relative_to(root).as_posix() not in excluded
        ),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    require(not any(path.is_symlink() for path in files), f"symbolic files are forbidden in {root}")
    records = [file_record(path, root) for path in files]
    canonical = "".join(
        f"{record['path']}\t{record['bytes']}\t{record['sha256']}\n"
        for record in records
    )
    return {
        "file_count": len(records),
        "byte_count": sum(int(record["bytes"]) for record in records),
        "partial_file_count": sum(
            str(record["path"]).endswith(".partial") for record in records
        ),
        "tree_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "canonicalization": "relative_path TAB byte_count TAB sha256 LF; POSIX paths sorted ascending",
        "files": records,
    }


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def copy_exact(source: Path, destination: Path) -> dict[str, object]:
    require(source.is_file() and not source.is_symlink(), f"required file missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    require(sha256_file(source) == sha256_file(destination), f"copy hash mismatch: {source}")
    return file_record(destination, PACKAGE)


def copy_tree_exact(source: Path, destination: Path) -> dict[str, object]:
    require(source.is_dir(), f"required directory missing: {source}")
    for path in sorted(item for item in source.rglob("*") if item.is_file()):
        require(not path.is_symlink(), f"symbolic file is forbidden: {path}")
        copy_exact(path, destination / path.relative_to(source))
    return tree_record(destination)


def deterministic_zip(
    destination: Path, entries: list[tuple[Path, str]]
) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        for source, archive_name in entries:
            info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            with source.open("rb") as input_stream, archive.open(
                info, "w", force_zip64=True
            ) as output_stream:
                shutil.copyfileobj(input_stream, output_stream, 4 * 1024 * 1024)
            records.append(
                {
                    "archive_path": archive_name,
                    "source_path": source.relative_to(RAW_ROOT).as_posix(),
                    "bytes": source.stat().st_size,
                    "sha256": sha256_file(source),
                }
            )
    return records


def frozen_name(role: str, path: Path) -> str:
    suffix = "".join(path.suffixes)
    safe_role = re.sub(r"[^a-zA-Z0-9_.-]+", "_", role)
    return f"{safe_role}_{sha256_file(path)}{suffix}"


def argument(argv: list[str], flag: str) -> Path:
    require(flag in argv, f"missing historical argument {flag}")
    index = argv.index(flag)
    require(index + 1 < len(argv), f"historical argument has no value: {flag}")
    return Path(argv[index + 1])


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    require(isinstance(value, dict), f"JSON root is not an object: {path}")
    return value


def marker_map(path: Path) -> dict[str, str]:
    return {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in path.read_text(encoding="utf-8", errors="strict").splitlines()
        if "=" in line
    }


def main() -> int:
    require(not PACKAGE.exists(), f"package already exists: {PACKAGE}")
    require(not CLASSIFICATION.exists(), f"classification already exists: {CLASSIFICATION}")
    require(not REPLAY_RESULT.exists(), f"replay result already exists: {REPLAY_RESULT}")
    require(RAW_ROOT.is_dir(), f"raw root missing: {RAW_ROOT}")
    require(REPLAY.is_dir(), f"summarizer replay missing: {REPLAY}")
    require(sha256_file(CHECKPOINT) == OFFLINE_CHECKPOINT_SHA256, "offline checkpoint changed")
    PACKAGE.mkdir(parents=True)

    ledger_path = RAW_ROOT / "sequence_execution_ledger.json"
    require(sha256_file(ledger_path) == LEDGER_SHA256, "ledger changed after terminal failure")
    ledger = load_json(ledger_path)
    require(ledger["status"] == "FAIL", "r41 ledger is not FAIL")
    require(ledger["plan_mode"] == "FULL_ACCEPTANCE", "r41 was not the formal full plan")
    require(ledger["source_commit"] == SOURCE_COMMIT, "r41 source commit changed")
    require(ledger["full_stage_ordinals"] == EXPECTED_ORDINALS, "formal ordinals changed")
    require(ledger["attempt_count"] == 66, "formal attempt count changed")
    require(ledger["completed_stage_count"] == 65, "formal completed count changed")
    require(ledger["next_stage_index"] == 65, "formal failed stage index changed")
    require(ledger["network_used"] is False, "r41 recorded network use")
    require(ledger["motion_used"] is False, "r41 recorded motion use")
    attempts = ledger["attempts"]
    require(len(attempts) == 66, "r41 attempt records are incomplete")
    for ordinal, attempt in enumerate(attempts, 1):
        require(attempt["full_stage_ordinal"] == ordinal, f"stage {ordinal} ordinal mismatch")
        require(attempt["state"] == "TERMINAL", f"stage {ordinal} is not terminal")
        expected = "PASS" if ordinal <= 65 else "FAIL"
        require(attempt["result"] == expected, f"stage {ordinal} is not {expected}")
        process = attempt["process"]
        require(process["process_tree_reaped"] is True, f"stage {ordinal} process tree not reaped")
        require(process["containment_closed"] is True, f"stage {ordinal} containment open")
        require(process["descendant_count_after"] == 0, f"stage {ordinal} descendants remain")
        require(process["timed_out"] is False, f"stage {ordinal} timed out")
        require(process["returncode"] == (0 if ordinal <= 65 else 1), f"stage {ordinal} rc mismatch")
        shutdown = attempt["shutdown_after"]
        require(shutdown["present"] is True, f"stage {ordinal} shutdown missing")
        require(shutdown["passed"] is True, f"stage {ordinal} shutdown failed")
        require(shutdown["returncode"] == 0, f"stage {ordinal} shutdown rc mismatch")

    copy_exact(ledger_path, PACKAGE / "sequence_execution_ledger.json")
    raw_tree = tree_record(RAW_ROOT)
    require(raw_tree["file_count"] == 1808, "r41 raw file count changed")
    require(raw_tree["byte_count"] == 834_613_170, "r41 raw byte count changed")
    require(raw_tree["partial_file_count"] == 0, "r41 contains partial evidence")
    require(raw_tree["tree_sha256"] == RAW_TREE_SHA256, "r41 raw tree changed")
    write_json(
        PACKAGE / "original_raw_tree_manifest.json",
        {
            "schema": "rf-comm-p7-original-raw-tree-manifest-v1",
            "run_id": RUN_ID,
            "source_commit": SOURCE_COMMIT,
            "original_root": str(RAW_ROOT),
            **raw_tree,
        },
    )

    summary_entries: list[tuple[Path, str]] = []
    raw_entries: list[tuple[Path, str]] = []
    support_entries: list[tuple[Path, str]] = []
    stage_rows: list[dict[str, object]] = []
    for attempt in attempts:
        ordinal = int(attempt["full_stage_ordinal"])
        stage_id = str(attempt["stage_id"])
        slug = f"{ordinal:03d}_{stage_id}"
        summary_path = Path(attempt["summary_file"]["path"])
        require(
            sha256_file(summary_path) == attempt["summary_file"]["sha256"],
            f"stage {ordinal} summary hash mismatch",
        )
        summary = load_json(summary_path)
        status_key = "P7_JTAG_AXI_SAFE_STAGE" if ordinal <= 61 else "P7_PS_APPLICATION_SAFE_STAGE"
        expected = "PASS" if ordinal <= 65 else "FAIL_STAGE"
        require(summary[status_key] == expected, f"stage {ordinal} summary status mismatch")
        acceptance = summary.get("HARDWARE_ACCEPTANCE", summary.get("hardware_acceptance"))
        require(acceptance == "PENDING_HW", f"stage {ordinal} promoted acceptance")
        stage_dir = summary_path.parent
        raw_names = ("p7_jtag_axi_raw_result.txt", "p7_ps_application_raw_result.log")
        raw_path = next((stage_dir / name for name in raw_names if (stage_dir / name).is_file()), None)
        require(raw_path is not None, f"stage {ordinal} raw result missing")
        summary_entries.append((summary_path, f"stage_summaries/{slug}/{summary_path.name}"))
        raw_entries.append((raw_path, f"raw_results/{slug}/{raw_path.name}"))
        for name in (
            "p7_preflight_result.txt",
            "p7_hw_preflight_result.txt",
            "p7_shutdown_before_result.txt",
            "shutdown_before_result.txt",
            "p7_shutdown_after_result.txt",
            "shutdown_after_result.txt",
            "p7_raw_evidence_sha256_manifest.json",
        ):
            path = stage_dir / name
            if path.is_file():
                support_entries.append((path, f"stage_support/{slug}/{name}"))
        stage_rows.append(
            {
                "ordinal": ordinal,
                "stage_id": stage_id,
                "ledger_result": attempt["result"],
                "summary_status": summary[status_key],
                "HARDWARE_ACCEPTANCE": acceptance,
                "summary_archive_path": f"stage_summaries/{slug}/{summary_path.name}",
                "summary_bytes": summary_path.stat().st_size,
                "summary_sha256": sha256_file(summary_path),
                "raw_archive_path": f"raw_results/{slug}/{raw_path.name}",
                "raw_bytes": raw_path.stat().st_size,
                "raw_sha256": sha256_file(raw_path),
            }
        )

    zipped_summaries = deterministic_zip(PACKAGE / "stage_summaries.zip", summary_entries)
    zipped_raw = deterministic_zip(PACKAGE / "raw_results.zip", raw_entries)
    zipped_support = deterministic_zip(PACKAGE / "stage_support.zip", support_entries)
    write_json(
        PACKAGE / "stage_evidence_manifest.json",
        {
            "schema": "rf-comm-p7-formal-failure-stage-evidence-manifest-v1",
            "run_id": RUN_ID,
            "stage_count": 66,
            "pass_count": 65,
            "fail_count": 1,
            "failed_ordinal": 66,
            "stage_rows": stage_rows,
            "summary_archive": {
                **file_record(PACKAGE / "stage_summaries.zip", PACKAGE),
                "entries": zipped_summaries,
            },
            "raw_archive": {
                **file_record(PACKAGE / "raw_results.zip", PACKAGE),
                "entries": zipped_raw,
            },
            "support_archive": {
                **file_record(PACKAGE / "stage_support.zip", PACKAGE),
                "entries": zipped_support,
            },
        },
    )

    stage66_dir = RAW_ROOT / "066_p7_ps_stationary"
    stage66_tree = copy_tree_exact(stage66_dir, PACKAGE / "stage66")
    wrapper_root = RAW_ROOT / ".sequence_execution_ledger_wrapper_logs"
    copy_exact(wrapper_root / "066_p7_ps_stationary.stdout.log", PACKAGE / "executor/stage66_wrapper.stdout.log")
    copy_exact(wrapper_root / "066_p7_ps_stationary.stderr.log", PACKAGE / "executor/stage66_wrapper.stderr.log")

    recovery_dirs = sorted(RAW_ROOT.glob("recovery_shutdown_after_failed_stage066_*"))
    require(len(recovery_dirs) == 1, "r41 must have exactly one independent recovery")
    recovery_tree = copy_tree_exact(recovery_dirs[0], PACKAGE / "recovery")
    recovery_markers = marker_map(recovery_dirs[0] / "program_tfdu_shutdown_safe.summary.txt")
    recovery_stdout = (recovery_dirs[0] / "program_tfdu_shutdown_safe.stdout.log").read_text(
        encoding="utf-8", errors="strict"
    )
    emitted_recovery_markers = [
        line
        for line in recovery_stdout.splitlines()
        if line.startswith("TFDU_SHUTDOWN_PROGRAMMED ")
    ]
    require(recovery_markers.get("HARDWARE_AUTHORIZATION_EXIT") == "0", "recovery authorization failed")
    require(recovery_markers.get("SHUTDOWN_EXIT") == "0", "recovery shutdown exit failed")
    require(recovery_markers.get("PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS") == "PASS", "recovery status failed")
    require(len(emitted_recovery_markers) == 1, "recovery emitted shutdown marker count is not one")

    historical_dir = PACKAGE / "historical_preflight_inputs"
    historical_dir.mkdir()
    historical_records: list[dict[str, object]] = []

    def freeze(role: str, path: Path, scope: str) -> None:
        destination = historical_dir / frozen_name(role, path)
        require(not destination.exists(), f"duplicate frozen destination: {destination}")
        copy_exact(path, destination)
        historical_records.append(
            {
                "role": role,
                "source_scope": scope,
                "original_path": str(path),
                "frozen_path": destination.relative_to(MAIN).as_posix(),
                "bytes": destination.stat().st_size,
                "sha256": sha256_file(destination),
            }
        )

    source_auth = SOURCE / ".hardware_authorization"
    authorization_paths = sorted(source_auth.glob(f"{RUN_ID}_[0-9][0-9][0-9]_*.txt"))
    require(len(authorization_paths) == 66, "r41 authorization count changed")
    for path in authorization_paths:
        match = re.search(r"_(\d{3})_", path.name)
        require(match is not None, f"authorization ordinal missing: {path}")
        freeze(f"stage_authorization_{match.group(1)}", path, "EXECUTION_SOURCE")
    sequence_plan = source_auth / f"{RUN_ID}_sequence_plan.txt"
    require(sha256_file(sequence_plan) == PLAN_SHA256, "r41 sequence plan changed")
    freeze("sequence_plan", sequence_plan, "EXECUTION_SOURCE")
    freeze("offline_checkpoint_classification", CHECKPOINT, "MAIN_CHECKPOINT")
    for path in sorted(item for item in CHECKPOINT_DIR.rglob("*") if item.is_file()):
        role = "offline_checkpoint_" + re.sub(
            r"[^a-zA-Z0-9]+", "_", path.relative_to(CHECKPOINT_DIR).as_posix()
        ).strip("_")
        freeze(role, path, "MAIN_CHECKPOINT")
    for path in sorted((MAIN / "evidence/generated").glob("p7_r41*.json")):
        if path in {CLASSIFICATION, REPLAY_RESULT, CHECKPOINT}:
            continue
        freeze("preparation_" + path.stem, path, "MAIN_PREPARATION")

    first_argv = list(attempts[0]["process"]["argv"])
    last_argv = list(attempts[-1]["process"]["argv"])
    build_summary_path = argument(last_argv, "--p7-build-summary")
    build_summary = load_json(build_summary_path)
    linker_map = SOURCE / str(build_summary["artifacts"]["linker_map"]["immutable"])
    source_inputs = {
        "historical_sequence_executor": SOURCE / "tools/run_p7_authorized_hardware_sequence.py",
        "historical_plan_generator": SOURCE / "tools/generate_p7_authorized_sequence_plan.py",
        "historical_summarizer": SOURCE / "tools/summarize_p7_hardware.py",
        "historical_jtag_stage_wrapper": SOURCE / "scripts/hw/run_p7_jtag_axi_stage_safe.py",
        "historical_ps_stage_wrapper": SOURCE / "scripts/hw/run_p7_ps_application_stage_safe.py",
        "historical_shutdown_wrapper": SOURCE / "scripts/hw/program_tfdu_shutdown_safe.ps1",
        "historical_shutdown_tcl": SOURCE / "scripts/legacy_safe_tools/program_tfdu_shutdown.tcl",
        "historical_p4_authorizer": SOURCE / "tools/p4_hw_authorization.py",
        "historical_ps_mailbox_backend": SOURCE / "tools/p7_ps_mailbox_backend.py",
        "historical_ps_execute_tcl": SOURCE / "scripts/hw/p7_ps_application_execute.tcl",
        "historical_jtag_transactions_tcl": SOURCE / "scripts/hw/p7_jtag_axi_transactions.tcl",
        "historical_app_service_source": SOURCE / "software/ps_driver/p7_app_service.c",
        "historical_app_service_header": SOURCE / "software/ps_driver/p7_app_service.h",
        "historical_stage62_diagnostic_source": SOURCE / "software/ps_driver/p7_stage62_diagnostic.c",
        "historical_stage62_diagnostic_header": SOURCE / "software/ps_driver/p7_stage62_diagnostic.h",
        "active_profile": argument(last_argv, "--active-profile"),
        "stage_profile": argument(last_argv, "--profile"),
        "active_xdc": argument(last_argv, "--active-xdc"),
        "pinmap": argument(last_argv, "--pinmap"),
        "register_map": argument(last_argv, "--register-map"),
        "offline_gate_summary": SOURCE / "evidence/generated/p7_offline_gate_summary.json",
        "core_readiness": argument(last_argv, "--core-readiness-attestation"),
        "p6_build_summary": argument(last_argv, "--p6-build-summary"),
        "p7_build_summary": build_summary_path,
        "lane1_promotion_summary": argument(last_argv, "--lane1-promotion-summary"),
        "plan_artifact": argument(last_argv, "--plan-file"),
        "jtag_bitstream": argument(first_argv, "--bitstream"),
        "jtag_ltx": argument(first_argv, "--ltx"),
        "ps_bitstream": argument(last_argv, "--bitstream"),
        "xsa": argument(last_argv, "--xsa"),
        "elf": argument(last_argv, "--elf"),
        "linker_map": linker_map,
        "ps7_init": argument(last_argv, "--ps7-init"),
        "shutdown_bitstream": argument(last_argv, "--shutdown-bitstream"),
        "generation_manifest": BUILD_ROOT / "p7_authorized_sequence_generation_manifest.json",
        "ps_seed": argument(last_argv, "--input-file"),
        "recovery_p4_authorization": MAIN / ".hardware_authorization/P4_APPROVED.txt",
    }
    for role, path in source_inputs.items():
        freeze(role, path, "EXECUTION_SOURCE" if role != "recovery_p4_authorization" else "MAIN_RECOVERY")
    require(
        next(record for record in historical_records if record["role"] == "historical_ps_execute_tcl")["sha256"]
        == FAILING_TCL_SHA256,
        "failing Tcl source hash changed",
    )
    write_json(
        historical_dir / "manifest.json",
        {
            "schema": "rf-comm-p7-formal-failure-historical-input-freeze-v1",
            "run_id": RUN_ID,
            "source_commit": SOURCE_COMMIT,
            "result": "FORMAL_FAIL",
            "coverage_claimed": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "file_count": len(historical_records),
            "files": historical_records,
        },
    )

    replay_files = {
        "final_summary": REPLAY / "p7_final_summary.json",
        "evidence_consistency": REPLAY / "p7_evidence_consistency_summary.json",
        "shutdown_evidence": REPLAY / "p7_shutdown_evidence_summary.json",
        "authorization_summary": REPLAY / "p7_hardware_authorization_summary.json",
        "stationary_summary": REPLAY / "p7_stationary_30min_summary.json",
    }
    replay_payloads = {name: load_json(path) for name, path in replay_files.items()}
    require(replay_payloads["final_summary"]["result"] == "FAIL", "summarizer final result changed")
    require(replay_payloads["shutdown_evidence"]["result"] == "PASS", "summarizer shutdown result changed")
    require(replay_payloads["stationary_summary"]["result"] == "FAIL", "summarizer stationary result changed")
    for name, path in replay_files.items():
        copy_exact(path, PACKAGE / "summarizer" / path.name)
    replay_stdout = MAIN / "evidence/generated/p7_r41_summarizer_replay.stdout.log"
    replay_stderr = MAIN / "evidence/generated/p7_r41_summarizer_replay.stderr.log"
    copy_exact(replay_stdout, PACKAGE / "summarizer/invocation.stdout.log")
    copy_exact(replay_stderr, PACKAGE / "summarizer/invocation.stderr.log")
    replay_tree = tree_record(REPLAY)
    replay_result = {
        "schema": "rf-comm-p7-r41-summarizer-replay-v1",
        "run_id": RUN_ID,
        "invocation_count": 1,
        "summarizer_sha256": sha256_file(SOURCE / "tools/summarize_p7_hardware.py"),
        "summarizer_exit_code_observed": True,
        "summarizer_exit_code": 1,
        "hardware_actions_executed_by_summarizer": False,
        "interpretation": "FORMAL_RUN_FAILED_AT_STAGE66_AND_STATIONARY_DID_NOT_COMPLETE",
        "output_tree": {key: value for key, value in replay_tree.items() if key != "files"},
        **{
            name: {
                "path": path.relative_to(MAIN).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "result": replay_payloads[name].get("result"),
                "error_count": len(replay_payloads[name].get("errors", [])),
            }
            for name, path in replay_files.items()
        },
    }
    write_json(REPLAY_RESULT, replay_result)

    stage66_raw = stage66_dir / "p7_ps_application_raw_result.log"
    stage66_text = stage66_raw.read_text(encoding="utf-8", errors="strict")
    require("P7_PS_STAGE_ERROR=integer value too large to represent" in stage66_text, "r41 error changed")
    object_pattern = re.compile(r"START_TICKS_(\d+),END_TICKS_(\d+),COMPLETION_SEQUENCE_(\d+)")
    tick_pairs = [(int(start), int(end)) for start, end, _ in object_pattern.findall(stage66_text)]
    require(len(tick_pairs) == 4, "r41 stationary terminal-object count changed")
    latencies = [end - start for start, end in tick_pairs]
    require(
        latencies == [17_875_676_347, 26_957_722_756, 51_321_168_692, 45_147_234_789],
        "r41 terminal latencies changed",
    )
    failing_tcl = SOURCE / "scripts/hw/p7_ps_application_execute.tcl"
    fixed_tcl = MAIN / "scripts/hw/p7_ps_application_execute.tcl"
    reproducer = MAIN / "tests/fixtures/p7_stationary_wide_latency_reproducer.tcl"
    xsct_stdout = MAIN / "evidence/generated/p7_r41_wide_latency_xsct.stdout.log"
    xsct_stderr = MAIN / "evidence/generated/p7_r41_wide_latency_xsct.stderr.log"
    xsct_text = xsct_stdout.read_text(encoding="utf-8", errors="strict")
    require("P7_R41_OLD_SORT_ERROR=integer value too large to represent" in xsct_text, "XSCT old path did not reproduce")
    require("P7_R41_FIXED_SORT_RC=0" in xsct_text, "XSCT fixed comparator failed")
    require("P7_R41_WIDE_LATENCY_REPRODUCER=PASS" in xsct_text, "XSCT reproducer did not pass")
    require("set sorted [lsort -integer $values]" in failing_tcl.read_text(encoding="utf-8"), "historical failing call missing")
    require("set sorted [lsort -command p7_compare_wide_integer $values]" in fixed_tcl.read_text(encoding="utf-8"), "fixed comparator call missing")
    root_cause_files = {
        "failing_tcl": failing_tcl,
        "fixed_tcl": fixed_tcl,
        "reproducer": reproducer,
        "xsct_stdout": xsct_stdout,
        "xsct_stderr": xsct_stderr,
    }
    root_cause_records = {}
    for role, path in root_cause_files.items():
        destination = PACKAGE / "root_cause" / f"{role}{''.join(path.suffixes)}"
        root_cause_records[role] = copy_exact(path, destination)
    root_cause = {
        "schema": "rf-comm-p7-r41-stage66-root-cause-v1",
        "status": "CONFIRMED_HOST_TCL_SIGNED_32_BIT_LATENCY_SORT_OVERFLOW",
        "failure_stage_ordinal": 66,
        "stationary_attempt_count": 1,
        "stationary_completed": False,
        "raw_error": "integer value too large to represent",
        "first_failing_sample_sequence": 2,
        "r41_runtime_start_ticks": 80_953,
        "sample_2_previous_threshold_ticks": 10_000_000_290,
        "sample_2_threshold_ticks": 20_000_000_580,
        "terminal_tick_pairs": [
            {"start_ticks": start, "end_ticks": end, "latency_ticks": end - start}
            for start, end in tick_pairs
        ],
        "first_sample_2_latency_ticks": latencies[0],
        "signed_32_bit_max": 0x7FFFFFFF,
        "historical_source_sha256": FAILING_TCL_SHA256,
        "fixed_source_sha256": sha256_file(fixed_tcl),
        "xsct_2023_1_old_path_reproduced_exact_error": True,
        "xsct_2023_1_fixed_comparator_passed": True,
        "hardware_rerun_performed": False,
        "acceptance_claimed": False,
        "files": root_cause_records,
    }
    write_json(PACKAGE / "root_cause/root_cause.json", root_cause)

    copy_exact(Path(__file__), PACKAGE / "packaging_script.py")
    payload_tree = tree_record(PACKAGE)
    write_json(
        PACKAGE / "package_manifest.json",
        {
            "schema": "rf-comm-p7-portable-package-manifest-v1",
            "run_id": RUN_ID,
            "source_commit": SOURCE_COMMIT,
            "manifest_excludes_itself": True,
            **payload_tree,
        },
    )
    package_tree = tree_record(PACKAGE)

    stage66_summary = load_json(stage66_dir / "p7_ps_application_stage_summary.json")
    classification = {
        "schema": "rf-comm-p7-r41-formal-failure-package-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": RUN_ID,
        "run_status": "IMMUTABLE_FORMAL_FAIL_NEVER_RESUME_RESTART_COPY_OR_REUSE",
        "source_commit": SOURCE_COMMIT,
        "plan_mode": "FULL_ACCEPTANCE",
        "sequence_plan_sha256": PLAN_SHA256,
        "offline_checkpoint_sha256": OFFLINE_CHECKPOINT_SHA256,
        "coverage_claimed": False,
        "formal_acceptance_coverage_contributed": False,
        "execution": {
            "hardware_launch_count": 1,
            "resume_argument_count": 0,
            "attempt_count": 66,
            "completed_stage_count": 65,
            "terminal_pass_ordinals": list(range(1, 66)),
            "failed_ordinal": 66,
            "failed_stage_id": "p7_ps_stationary",
            "failed_stage_process_returncode": 1,
            "failed_stage_timed_out": False,
            "failed_stage_process_tree_reaped": True,
            "failed_stage_containment_closed": True,
        },
        "stationary": {
            "authorized_attempt_count": 1,
            "attempt_consumed": True,
            "future_attempt_permitted_under_current_constraint": False,
            "completed_1800_seconds": False,
            "pass": False,
            "sample_count": stage66_text.count("P7_SAMPLE_"),
            "terminal_object_count": len(tick_pairs),
            "raw_error": "integer value too large to represent",
            "runner_status": stage66_summary["P7_PS_APPLICATION_SAFE_STAGE"],
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        },
        "shutdown": {
            "stage66_shutdown_before_passed": stage66_summary["shutdown_before"]["passed"],
            "stage66_shutdown_after_passed": stage66_summary["shutdown_after"]["passed"],
            "independent_recovery_run": True,
            "independent_recovery_status": recovery_markers["PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS"],
            "independent_recovery_shutdown_exit": int(recovery_markers["SHUTDOWN_EXIT"]),
            "independent_recovery_emitted_marker_count": len(emitted_recovery_markers),
            "recovery_changes_failed_stage_result": False,
            "safe_shutdown_complete": True,
        },
        "safety": {
            "ethernet_used": False,
            "motion_used": False,
            "lane_count": 2,
            "max_lane_mask": "0x3",
            "external_hw_server_pid": 45220,
            "external_hw_server_touched": False,
            "project_hardware_process_count_after_recovery": 0,
        },
        "raw_evidence": {
            "original_root": str(RAW_ROOT),
            "manifest_path": "evidence/generated/p7_r41_formal_failure_package/original_raw_tree_manifest.json",
            "manifest_sha256": sha256_file(PACKAGE / "original_raw_tree_manifest.json"),
            "file_count": raw_tree["file_count"],
            "byte_count": raw_tree["byte_count"],
            "partial_file_count": raw_tree["partial_file_count"],
            "tree_sha256": raw_tree["tree_sha256"],
            "portable_package_embeds_entire_raw_tree": False,
            "stage66_portable_tree": {key: value for key, value in stage66_tree.items() if key != "files"},
            "recovery_portable_tree": {key: value for key, value in recovery_tree.items() if key != "files"},
        },
        "root_cause": {
            "path": "evidence/generated/p7_r41_formal_failure_package/root_cause/root_cause.json",
            "sha256": sha256_file(PACKAGE / "root_cause/root_cause.json"),
            "status": root_cause["status"],
            "hardware_rerun_performed": False,
        },
        "summarizer_replay": {
            "result_path": REPLAY_RESULT.relative_to(MAIN).as_posix(),
            "result_sha256": sha256_file(REPLAY_RESULT),
            "invocation_count": 1,
            "exit_code": 1,
            "formal_result": "FAIL",
            "stationary_result": "FAIL",
            "shutdown_result": "PASS",
        },
        "historical_preflight_freeze": {
            "manifest_path": "evidence/generated/p7_r41_formal_failure_package/historical_preflight_inputs/manifest.json",
            "manifest_sha256": sha256_file(historical_dir / "manifest.json"),
            "file_count": len(historical_records),
        },
        "portable_package": {
            "path": "evidence/generated/p7_r41_formal_failure_package",
            **{key: value for key, value in package_tree.items() if key != "files"},
        },
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "STATIONARY_30MIN": "FAIL_INCOMPLETE",
        "next_step": "FREEZE_AND_COMMIT_FAILURE_EVIDENCE_AND_HOST_TCL_FIX_WITHOUT_ANY_FURTHER_HARDWARE_OR_STAGE66_ATTEMPT",
    }
    write_json(CLASSIFICATION, classification)
    print(
        json.dumps(
            {
                "P7_R41_FORMAL_FAILURE_PACKAGE": "PASS",
                "run_status": classification["run_status"],
                "ledger_sha256": LEDGER_SHA256,
                "raw_tree_sha256": raw_tree["tree_sha256"],
                "package_tree_sha256": package_tree["tree_sha256"],
                "package_file_count": package_tree["file_count"],
                "package_byte_count": package_tree["byte_count"],
                "stages_1_to_65": "PASS",
                "stage_66": "FAIL",
                "stationary_1800_seconds_completed": False,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
