from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path


MAIN = Path(r"C:\Users\user\Documents\RF_COMM_MULTILANE")
SOURCE = Path(r"C:\Users\user\.codex\worktrees\r40validate_3718276\RF_COMM_MULTILANE")
RUN_ID = "p7_20260715_stationary_app_r40_diag_suffix55"
SOURCE_COMMIT = "37182768047dc4afdc18699a1142852418b382b5"
LEDGER_SHA256 = "756c83030a6224b0381b7a90f0bf9085e3fe59eebe09957a9b68008ae9ca77a5"
PLAN_SHA256 = "27de005c49a34c2d663b596ab94ef415c6cdbe5a4e5086c79d6c19a127803b0e"
OFFLINE_SHA256 = "cf6a6d6c839f1e0251279964f5b73b56967f5440e3687253fb78b149ea0886a5"
RAW_TREE_SHA256 = "2702bb0019ddb5899a82c6aa8d6eea775612168a8e0d4d962f0c5fee0db270a2"
SHUTDOWN_SHA256 = "bac60b58912f0acd771dc830a6761535ec8f6a92befb1ae4cb7d928745af5810"
EXPECTED_ORDINALS = [1, 2, 3, 4, *range(55, 66)]

RAW_ROOT = SOURCE / "evidence/hardware/p7/authorized_sequence" / RUN_ID
BUILD_ROOT = SOURCE / "build/p7_authorized_sequence" / RUN_ID
PACKAGE = MAIN / "evidence/generated/p7_r40_diagnostic_pass_package"
CLASSIFICATION = MAIN / "evidence/generated/p7_r40_diagnostic_pass.json"
REPLAY = MAIN / "evidence/generated/p7_r40_summarizer_replay"
REPLAY_RESULT = MAIN / "evidence/generated/p7_r40_summarizer_replay_result.json"


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


def tree_record(root: Path) -> dict[str, object]:
    files = sorted(
        (path for path in root.rglob("*") if path.is_file()),
        key=lambda path: path.relative_to(root).as_posix(),
    )
    if any(path.is_symlink() for path in files):
        raise RuntimeError(f"symbolic files are forbidden in {root}")
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
    if not source.is_file() or source.is_symlink():
        raise RuntimeError(f"required regular file is missing: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if sha256_file(source) != sha256_file(destination):
        raise RuntimeError(f"copy hash mismatch: {source}")
    return file_record(destination, PACKAGE)


def deterministic_zip(destination: Path, entries: list[tuple[Path, str]]) -> list[dict[str, object]]:
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


def marker_map(path: Path) -> dict[str, str]:
    return {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in path.read_text(encoding="utf-8", errors="strict").splitlines()
        if "=" in line
    }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def frozen_name(role: str, path: Path) -> str:
    suffix = "".join(path.suffixes)
    safe_role = re.sub(r"[^a-zA-Z0-9_.-]+", "_", role)
    return f"{safe_role}_{sha256_file(path)}{suffix}"


def main() -> int:
    require(not PACKAGE.exists(), f"package already exists: {PACKAGE}")
    require(not CLASSIFICATION.exists(), f"classification already exists: {CLASSIFICATION}")
    require(not REPLAY_RESULT.exists(), f"replay result already exists: {REPLAY_RESULT}")
    require(RAW_ROOT.is_dir(), f"raw evidence root missing: {RAW_ROOT}")
    require(REPLAY.is_dir(), f"summarizer replay missing: {REPLAY}")
    PACKAGE.mkdir(parents=True)

    ledger_path = RAW_ROOT / "sequence_execution_ledger.json"
    require(sha256_file(ledger_path) == LEDGER_SHA256, "ledger hash changed")
    ledger = json.loads(ledger_path.read_text(encoding="utf-8", errors="strict"))
    require(ledger["status"] == "DIAGNOSTIC_PASS", "ledger is not DIAGNOSTIC_PASS")
    require(ledger["source_commit"] == SOURCE_COMMIT, "source commit mismatch")
    require(ledger["plan_mode"] == "DIAGNOSTIC_SUFFIX_55", "plan mode mismatch")
    require(ledger["coverage_claimed"] is False, "diagnostic coverage was claimed")
    require(ledger["HARDWARE_ACCEPTANCE"] == "PENDING_HW", "acceptance was promoted")
    require(ledger["full_stage_ordinals"] == EXPECTED_ORDINALS, "planned ordinals changed")
    require(ledger["attempt_count"] == 15, "attempt count mismatch")
    require(ledger["completed_stage_count"] == 15, "completed stage count mismatch")
    require(66 not in ledger["full_stage_ordinals"], "stage 66 is present")
    require(ledger["network_used"] is False, "network use was recorded")
    require(ledger["motion_used"] is False, "motion use was recorded")

    copy_exact(ledger_path, PACKAGE / "sequence_execution_ledger.json")

    raw_tree = tree_record(RAW_ROOT)
    require(raw_tree["file_count"] == 836, "raw file count changed")
    require(raw_tree["byte_count"] == 797132623, "raw byte count changed")
    require(raw_tree["partial_file_count"] == 0, "partial raw evidence exists")
    require(raw_tree["tree_sha256"] == RAW_TREE_SHA256, "raw evidence tree changed")
    raw_tree_payload = {
        "schema": "rf-comm-p7-original-raw-tree-manifest-v1",
        "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT,
        "original_root": str(RAW_ROOT),
        **raw_tree,
    }
    write_json(PACKAGE / "original_raw_tree_manifest.json", raw_tree_payload)

    stage_rows: list[dict[str, object]] = []
    summary_zip_entries: list[tuple[Path, str]] = []
    raw_zip_entries: list[tuple[Path, str]] = []
    support_records: list[dict[str, object]] = []
    for attempt in ledger["attempts"]:
        ordinal = int(attempt["full_stage_ordinal"])
        stage_id = str(attempt["stage_id"])
        stage_slug = f"{ordinal:03d}_{stage_id}"
        require(attempt["state"] == "TERMINAL", f"stage {ordinal} is not terminal")
        require(attempt["result"] == "PASS", f"stage {ordinal} is not PASS")
        require(attempt["failures"] == [], f"stage {ordinal} ledger failures exist")
        process = attempt["process"]
        require(process["returncode"] == 0, f"stage {ordinal} child rc is not zero")
        require(process["timed_out"] is False, f"stage {ordinal} timed out")
        require(process["process_tree_reaped"] is True, f"stage {ordinal} was not reaped")
        require(process["containment_closed"] is True, f"stage {ordinal} containment is open")
        require(process["descendant_count_after"] == 0, f"stage {ordinal} descendants remain")

        summary_path = Path(attempt["summary_file"]["path"])
        require(sha256_file(summary_path) == attempt["summary_file"]["sha256"], f"stage {ordinal} summary hash mismatch")
        require(summary_path.stat().st_size == attempt["summary_file"]["bytes"], f"stage {ordinal} summary size mismatch")
        summary = json.loads(summary_path.read_text(encoding="utf-8", errors="strict"))
        status_key = "P7_JTAG_AXI_SAFE_STAGE" if ordinal <= 61 else "P7_PS_APPLICATION_SAFE_STAGE"
        acceptance = summary.get("HARDWARE_ACCEPTANCE", summary.get("hardware_acceptance"))
        require(summary[status_key] == "PASS", f"stage {ordinal} summary status mismatch")
        require(acceptance == "PENDING_HW", f"stage {ordinal} acceptance was promoted")
        require(summary["stage_validation_errors"] == [], f"stage {ordinal} validation errors exist")
        if ordinal >= 62:
            require(summary["ps_failures"] == [], f"stage {ordinal} PS failures exist")

        shutdown_rows: dict[str, object] = {}
        for shutdown_name in ("shutdown_before", "shutdown_after"):
            shutdown = summary[shutdown_name]
            require(shutdown["attempted"] is True, f"stage {ordinal} {shutdown_name} not attempted")
            require(shutdown["programming_attempted"] is True, f"stage {ordinal} {shutdown_name} did not program")
            require(shutdown["passed"] is True, f"stage {ordinal} {shutdown_name} failed")
            require(shutdown["returncode"] == 0, f"stage {ordinal} {shutdown_name} rc is not zero")
            require(shutdown["timed_out"] is False, f"stage {ordinal} {shutdown_name} timed out")
            require(shutdown["process_tree_reaped"] is True, f"stage {ordinal} {shutdown_name} was not reaped")
            require(shutdown["containment_closed"] is True, f"stage {ordinal} {shutdown_name} containment is open")
            require(shutdown["descendant_count_after"] == 0, f"stage {ordinal} {shutdown_name} descendants remain")
            result_path = Path(shutdown["result_file"])
            markers = marker_map(result_path)
            require(markers.get("P7_TCL_PROGRAMMING_ATTEMPTED") == "1", f"stage {ordinal} {shutdown_name} programming marker missing")
            require(markers.get("P7_SHUTDOWN_RESULT") == "PASS", f"stage {ordinal} {shutdown_name} PASS marker missing")
            programmed = Path(markers["TFDU_SHUTDOWN_PROGRAMMED"])
            require(programmed.is_file(), f"stage {ordinal} {shutdown_name} shutdown artifact missing")
            require(sha256_file(programmed) == SHUTDOWN_SHA256, f"stage {ordinal} {shutdown_name} shutdown hash mismatch")
            destination = PACKAGE / "stage_records" / stage_slug / result_path.name
            copied = copy_exact(result_path, destination)
            support_records.append({"ordinal": ordinal, "kind": shutdown_name, **copied})
            shutdown_rows[shutdown_name] = "PASS"

        ledger_shutdown = attempt["shutdown_after"]
        require(ledger_shutdown["present"] is True, f"stage {ordinal} ledger shutdown missing")
        require(ledger_shutdown["passed"] is True, f"stage {ordinal} ledger shutdown failed")
        require(ledger_shutdown["returncode"] == 0, f"stage {ordinal} ledger shutdown rc is not zero")
        require(ledger_shutdown["tfdu_shutdown_programmed_exact"] is True, f"stage {ordinal} ledger shutdown path mismatch")
        require(ledger_shutdown["p7_tcl_programming_attempted"] == "1", f"stage {ordinal} ledger programming marker mismatch")
        require(ledger_shutdown["p7_shutdown_result"] == "PASS", f"stage {ordinal} ledger shutdown result mismatch")

        stage_dir = summary_path.parent
        preflight_names = ["p7_preflight_result.txt", "p7_hw_preflight_result.txt"]
        preflight_path = next((stage_dir / name for name in preflight_names if (stage_dir / name).is_file()), None)
        require(preflight_path is not None, f"stage {ordinal} preflight result missing")
        destination = PACKAGE / "stage_records" / stage_slug / preflight_path.name
        copied = copy_exact(preflight_path, destination)
        support_records.append({"ordinal": ordinal, "kind": "preflight_result", **copied})

        raw_manifest_path = stage_dir / "p7_raw_evidence_sha256_manifest.json"
        if raw_manifest_path.is_file():
            destination = PACKAGE / "stage_records" / stage_slug / raw_manifest_path.name
            copied = copy_exact(raw_manifest_path, destination)
            support_records.append({"ordinal": ordinal, "kind": "raw_evidence_manifest", **copied})

        raw_names = ["p7_jtag_axi_raw_result.txt", "p7_ps_application_raw_result.log"]
        raw_result_path = next((stage_dir / name for name in raw_names if (stage_dir / name).is_file()), None)
        require(raw_result_path is not None, f"stage {ordinal} raw result missing")
        raw_zip_entries.append((raw_result_path, f"raw_results/{stage_slug}/{raw_result_path.name}"))
        summary_zip_entries.append((summary_path, f"stage_summaries/{stage_slug}/{summary_path.name}"))

        stage_rows.append(
            {
                "ordinal": ordinal,
                "stage_id": stage_id,
                "result": "PASS",
                "summary_archive_path": f"stage_summaries/{stage_slug}/{summary_path.name}",
                "summary_bytes": summary_path.stat().st_size,
                "summary_sha256": sha256_file(summary_path),
                **shutdown_rows,
                "HARDWARE_ACCEPTANCE": acceptance,
            }
        )

    summaries = deterministic_zip(PACKAGE / "stage_summaries.zip", summary_zip_entries)
    raw_results = deterministic_zip(PACKAGE / "raw_results.zip", raw_zip_entries)
    write_json(
        PACKAGE / "stage_evidence_manifest.json",
        {
            "schema": "rf-comm-p7-diagnostic-stage-evidence-manifest-v1",
            "run_id": RUN_ID,
            "stage_count": len(stage_rows),
            "stage_ordinals": EXPECTED_ORDINALS,
            "stage_rows": stage_rows,
            "summary_archive": {
                "path": "stage_summaries.zip",
                "bytes": (PACKAGE / "stage_summaries.zip").stat().st_size,
                "sha256": sha256_file(PACKAGE / "stage_summaries.zip"),
                "entries": summaries,
            },
            "raw_result_archive": {
                "path": "raw_results.zip",
                "bytes": (PACKAGE / "raw_results.zip").stat().st_size,
                "sha256": sha256_file(PACKAGE / "raw_results.zip"),
                "entries": raw_results,
            },
            "support_records": support_records,
        },
    )

    executor_stdout = BUILD_ROOT / "sequence_executor.stdout.log"
    executor_stderr = BUILD_ROOT / "sequence_executor.stderr.log"
    outer = json.loads(executor_stdout.read_text(encoding="utf-8", errors="strict"))
    require(outer["P7_AUTHORIZED_HARDWARE_SEQUENCE"] == "DIAGNOSTIC_PASS", "outer semantic status mismatch")
    require(outer["coverage_claimed"] is False, "outer result claimed coverage")
    require(outer["HARDWARE_ACCEPTANCE"] == "PENDING_HW", "outer result promoted acceptance")
    require(outer["validation_errors"] == [], "outer validation errors exist")
    require(outer["execution_ledger"]["sha256"] == LEDGER_SHA256, "outer ledger binding mismatch")
    copy_exact(executor_stdout, PACKAGE / "executor/sequence_executor.stdout.log")
    copy_exact(executor_stderr, PACKAGE / "executor/sequence_executor.stderr.log")
    write_json(
        PACKAGE / "executor/outer_monitor_observation.json",
        {
            "schema": "rf-comm-p7-outer-monitor-observation-v1",
            "run_id": RUN_ID,
            "launch_at_utc": "2026-07-15T03:05:08.9001250Z",
            "end_at_utc": "2026-07-15T05:04:18.1653301Z",
            "tool_cell_exit_code_observed": True,
            "tool_cell_exit_code": 0,
            "executor_process_exit_code_observed": False,
            "executor_process_exit_code": None,
            "missing_reason": "PowerShell Start-Process exit-code capture field was blank; no process exit code is inferred",
            "semantic_result": "DIAGNOSTIC_PASS",
            "semantic_result_source": "executor/sequence_executor.stdout.log",
            "ledger_child_returncodes_all_zero": True,
        },
    )

    historical_dir = PACKAGE / "historical_preflight_inputs"
    historical_dir.mkdir()
    historical_records: list[dict[str, object]] = []

    def freeze(role: str, path: Path, scope: str) -> None:
        destination = historical_dir / frozen_name(role, path)
        if destination.exists():
            raise RuntimeError(f"duplicate frozen destination: {destination}")
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

    auth_root = MAIN / ".hardware_authorization"
    for path in sorted(auth_root.glob(f"{RUN_ID}_*.txt")):
        if path.name == f"{RUN_ID}_sequence_plan.txt":
            continue
        match = re.search(r"_(\d{3})_", path.name)
        require(match is not None, f"authorization ordinal missing: {path}")
        freeze(f"stage_authorization_{match.group(1)}", path, "MAIN_PREPARATION")
    sequence_plan = auth_root / f"{RUN_ID}_sequence_plan.txt"
    require(sha256_file(sequence_plan) == PLAN_SHA256, "sequence plan hash changed")
    freeze("sequence_plan", sequence_plan, "MAIN_PREPARATION")

    for path in sorted((MAIN / "evidence/generated").glob("p7_r40_diag_suffix55_*.json")):
        freeze(f"preparation_{path.stem}", path, "MAIN_PREPARATION")
    checkpoint_classification = MAIN / "evidence/generated/p7_r40validate_3718276_checkpoint.json"
    freeze("offline_checkpoint_classification", checkpoint_classification, "MAIN_PREPARATION")
    checkpoint_dir = MAIN / "evidence/generated/p7_r40validate_3718276_checkpoint"
    for path in sorted(item for item in checkpoint_dir.rglob("*") if item.is_file()):
        role = "offline_checkpoint_" + re.sub(
            r"[^a-zA-Z0-9]+", "_", path.relative_to(checkpoint_dir).as_posix()
        ).strip("_")
        freeze(role, path, "MAIN_PREPARATION")

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
        "historical_app_service_source": SOURCE / "software/ps_driver/p7_app_service.c",
        "historical_app_service_header": SOURCE / "software/ps_driver/p7_app_service.h",
        "historical_stage62_diagnostic_source": SOURCE / "software/ps_driver/p7_stage62_diagnostic.c",
        "historical_stage62_diagnostic_header": SOURCE / "software/ps_driver/p7_stage62_diagnostic.h",
        "active_profile": SOURCE / "board_profiles/ACTIVE_PROFILE.json",
        "stage_profile": SOURCE / "profiles/p7/p7_stationary_app_30min.json",
        "active_xdc": SOURCE / "constraints/active/PORT1.generated.xdc",
        "pinmap": SOURCE / "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
        "register_map": SOURCE / "config/register_map/ir_axi_regs.yaml",
        "offline_gate_summary": SOURCE / "evidence/generated/p7_offline_gate_summary.json",
        "core_readiness": SOURCE / "evidence/generated/p7_ps_core_hardware_readiness.json",
        "p7_build_summary": SOURCE / "evidence/generated/p7_ps_runtime_build_summary.json",
        "plan_artifact": SOURCE / "evidence/hardware/p7/artifacts/p7_plan_c6db9d8348c3bc518fa5985595adfcdada1a08f11c9246c6103ec378b43b58dd.md",
        "jtag_bitstream": SOURCE / "evidence/hardware/p6/bitstreams/p6_jtag_dynamic_transport_798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f.bit",
        "jtag_ltx": SOURCE / "evidence/hardware/p6/bitstreams/p6_jtag_dynamic_transport_76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083.ltx",
        "ps_bitstream": SOURCE / "evidence/hardware/p6/bitstreams/p6_ps_dynamic_transport_bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868.bit",
        "xsa": SOURCE / "evidence/hardware/p6/bitstreams/p6_ps_dynamic_transport_3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8.xsa",
        "elf": SOURCE / "evidence/hardware/p7/artifacts/p7_runtime_d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da.elf",
        "linker_map": SOURCE / "evidence/hardware/p7/artifacts/p7_runtime_a282a162efff2d7d1fdef7abf32774659cb1b2448050cc95887e0aea3fa5ebde.map",
        "shutdown_bitstream": SOURCE / "shutdown_bitstream/tfdu_shutdown_j10_j11.bit",
        "generation_manifest": BUILD_ROOT / "p7_authorized_sequence_generation_manifest.json",
        "ps_seed": BUILD_ROOT / "inputs/p7_ps_seed_247.bin",
    }
    ps7_candidates = [
        path
        for path in (SOURCE / "build").rglob("ps7_init.tcl")
        if sha256_file(path) == "86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d"
    ]
    require(bool(ps7_candidates), "exact ps7_init.tcl was not found")
    source_inputs["ps7_init"] = sorted(ps7_candidates)[0]
    for role, path in source_inputs.items():
        freeze(role, path, "EXECUTION_SOURCE")

    write_json(
        historical_dir / "manifest.json",
        {
            "schema": "rf-comm-p7-diagnostic-historical-input-freeze-v1",
            "run_id": RUN_ID,
            "source_commit": SOURCE_COMMIT,
            "result": "DIAGNOSTIC_PASS",
            "coverage_claimed": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "file_count": len(historical_records),
            "files": historical_records,
        },
    )

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

    replay_tree = tree_record(REPLAY)
    replay_files = {
        "final_summary": REPLAY / "p7_final_summary.json",
        "evidence_consistency": REPLAY / "p7_evidence_consistency_summary.json",
        "shutdown_evidence": REPLAY / "p7_shutdown_evidence_summary.json",
        "authorization_summary": REPLAY / "p7_hardware_authorization_summary.json",
        "stationary_summary": REPLAY / "p7_stationary_30min_summary.json",
    }
    replay_payloads = {
        key: json.loads(path.read_text(encoding="utf-8", errors="strict"))
        for key, path in replay_files.items()
    }
    require(replay_payloads["final_summary"]["result"] == "FAIL", "summarizer did not fail closed")
    require(replay_payloads["evidence_consistency"]["result"] == "FAIL", "consistency did not fail closed")
    require(replay_payloads["shutdown_evidence"]["result"] == "PASS", "shutdown replay did not pass")
    require(replay_payloads["stationary_summary"]["result"] == "PENDING_HW", "stationary replay was promoted")
    hardware_envelope = json.loads(
        (REPLAY / "p7_hardware_evidence_summary.json").read_text(
            encoding="utf-8", errors="strict"
        )
    )
    require(hardware_envelope["hardware_actions_executed_by_summarizer"] is False, "summarizer claims hardware actions")
    replay_result = {
        "schema": "rf-comm-p7-r40-summarizer-replay-v1",
        "run_id": RUN_ID,
        "invocation_count": 1,
        "summarizer_sha256": sha256_file(SOURCE / "tools/summarize_p7_hardware.py"),
        "summarizer_exit_code_observed": True,
        "summarizer_exit_code": 1,
        "hardware_actions_executed_by_summarizer": False,
        "interpretation": "EXPECTED_FAIL_CLOSED_FORMAL_ACCEPTANCE_SUMMARY_OVER_DIAGNOSTIC_ONLY_SUFFIX",
        "diagnostic_hardware_result_is_taken_from": "portable ledger and exact stage summaries, not from formal acceptance summarizer",
        "output_tree": {key: value for key, value in replay_tree.items() if key != "files"},
        **{
            key: {
                "path": path.relative_to(MAIN).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "result": replay_payloads[key].get("result"),
                "error_count": len(replay_payloads[key].get("errors", [])),
            }
            for key, path in replay_files.items()
        },
        "r40_interpretation": {
            "diagnostic_status": "DIAGNOSTIC_PASS",
            "coverage_claimed": False,
            "formal_acceptance_coverage_contributed": False,
            "stage66_attempt_count": 0,
            "stationary_started": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        },
    }
    write_json(REPLAY_RESULT, replay_result)

    classification = {
        "schema": "rf-comm-p7-diagnostic-pass-package-v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": RUN_ID,
        "run_status": "COMPLETED_DIAGNOSTIC_PASS_NEVER_REUSE_OR_RESUME",
        "source_commit": SOURCE_COMMIT,
        "plan_mode": "DIAGNOSTIC_SUFFIX_55",
        "sequence_plan_sha256": PLAN_SHA256,
        "offline_checkpoint_sha256": OFFLINE_SHA256,
        "execution": {
            "hardware_launch_count": 1,
            "resume_argument_count": 0,
            "semantic_status": "DIAGNOSTIC_PASS",
            "ledger_status": "DIAGNOSTIC_PASS",
            "outer_tool_cell_exit_code_observed": True,
            "outer_tool_cell_exit_code": 0,
            "executor_process_exit_code_observed": False,
            "executor_process_exit_code": None,
            "executor_process_exit_code_note": "monitor field was blank; no process exit code is inferred",
            "child_returncodes_all_zero": True,
            "launch_at_utc": "2026-07-15T03:05:08.9001250Z",
            "end_at_utc": "2026-07-15T05:04:18.1653301Z",
        },
        "diagnostic_contract": {
            "diagnostic_only": True,
            "coverage_claimed": False,
            "formal_acceptance_coverage_contributed": False,
            "mandatory_safety_prefix": [1, 2, 3, 4],
            "diagnostic_suffix": list(range(55, 66)),
            "stationary_allowed": False,
            "stage66_attempt_count": 0,
            "stationary_started": False,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
        },
        "ledger": {
            "path": "evidence/generated/p7_r40_diagnostic_pass_package/sequence_execution_ledger.json",
            "bytes": ledger_path.stat().st_size,
            "sha256": LEDGER_SHA256,
            "attempt_count": 15,
            "completed_stage_count": 15,
            "full_stage_ordinals": EXPECTED_ORDINALS,
            "terminal_pass_ordinals": EXPECTED_ORDINALS,
            "failed_ordinal": None,
        },
        "stages": {
            "manifest_path": "evidence/generated/p7_r40_diagnostic_pass_package/stage_evidence_manifest.json",
            "manifest_sha256": sha256_file(PACKAGE / "stage_evidence_manifest.json"),
            "stage_count": 15,
            "pass_count": 15,
            "fail_count": 0,
            "validation_error_count": 0,
            "ps_failure_count": 0,
        },
        "safety": {
            "network_used": False,
            "ethernet_used": False,
            "motion_used": False,
            "lane_count": 2,
            "max_lane_mask": "0x3",
            "external_hw_server_pid": 45220,
            "external_hw_server_touched": False,
            "authorization_environment_present_after_run": False,
            "authorization_lock_present_after_run": False,
            "project_hardware_process_count_after_run": 0,
        },
        "shutdown": {
            "shutdown_before_pass_count": 15,
            "shutdown_after_pass_count": 15,
            "shutdown_artifact_sha256": SHUTDOWN_SHA256,
            "all_programming_attempted": True,
            "all_returncodes_zero": True,
            "all_process_trees_reaped": True,
            "all_containment_closed": True,
            "independent_recovery_required": False,
            "independent_recovery_run": False,
            "safe_shutdown_complete": True,
        },
        "raw_evidence": {
            "original_root": str(RAW_ROOT),
            "manifest_path": "evidence/generated/p7_r40_diagnostic_pass_package/original_raw_tree_manifest.json",
            "manifest_sha256": sha256_file(PACKAGE / "original_raw_tree_manifest.json"),
            "file_count": raw_tree["file_count"],
            "byte_count": raw_tree["byte_count"],
            "partial_file_count": raw_tree["partial_file_count"],
            "tree_sha256": raw_tree["tree_sha256"],
            "portable_package_embeds_entire_raw_tree": False,
        },
        "immutable_artifacts": {
            "jtag_bitstream_sha256": "798b0194029638fa27a254dd58db5d6fd28b65d91c5cf2c9e32c0f9076ee3c0f",
            "jtag_ltx_sha256": "76fe1ec47871946a7d357b0caa1f669500de827b796d6154dcc54678e0ac7083",
            "ps_bitstream_sha256": "bd9bce92e5966e811e10873a960909851922789d8242726869b9726b58aaa868",
            "xsa_sha256": "3e9e338241759c900629bb27f3e10982a4b5f9b4a9bea7c49f35e6759467aff8",
            "elf_sha256": "d47f28ff987b2f719a5497c92539afc4f8734db756df2eb80adc5651fea996da",
            "linker_map_sha256": "a282a162efff2d7d1fdef7abf32774659cb1b2448050cc95887e0aea3fa5ebde",
            "ps7_init_sha256": "86d8d72f45bc942af5c790c8c74f86dbe85fb9a561fccbc8b9b4190be835552d",
            "shutdown_bitstream_sha256": SHUTDOWN_SHA256,
        },
        "historical_preflight_freeze": {
            "manifest_path": "evidence/generated/p7_r40_diagnostic_pass_package/historical_preflight_inputs/manifest.json",
            "manifest_sha256": sha256_file(historical_dir / "manifest.json"),
            "file_count": len(historical_records),
        },
        "summarizer_replay": {
            "result_path": "evidence/generated/p7_r40_summarizer_replay_result.json",
            "result_sha256": sha256_file(REPLAY_RESULT),
            "exit_code": 1,
            "formal_acceptance_result": "FAIL",
            "shutdown_result": "PASS",
            "stationary_result": "PENDING_HW",
            "interpretation": "FAIL_CLOSED_AS_EXPECTED_FOR_DIAGNOSTIC_ONLY_INPUT; not a diagnostic stage failure",
        },
        "portable_package": {
            "path": "evidence/generated/p7_r40_diagnostic_pass_package",
            **{key: value for key, value in package_tree.items() if key != "files"},
        },
        "next_required_step": "COMMIT_R40_DIAGNOSTIC_EVIDENCE_THEN_PREPARE_A_NEW_CLEAN_FORMAL_FULL_1_TO_66_CHECKPOINT; R40 contributes zero acceptance coverage",
        "HARDWARE_ACCEPTANCE": "PENDING_HW",
        "STATIONARY_30MIN": "NOT_RUN",
    }
    write_json(CLASSIFICATION, classification)

    print(
        json.dumps(
            {
                "P7_R40_DIAGNOSTIC_PACKAGE": "PASS",
                "package": str(PACKAGE),
                "package_tree_sha256": package_tree["tree_sha256"],
                "package_file_count": package_tree["file_count"],
                "package_byte_count": package_tree["byte_count"],
                "original_raw_tree_sha256": raw_tree["tree_sha256"],
                "original_raw_file_count": raw_tree["file_count"],
                "stage_count": len(stage_rows),
                "coverage_claimed": False,
                "HARDWARE_ACCEPTANCE": "PENDING_HW",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
