#!/usr/bin/env python3
"""Freeze the exact inputs of one immutable P7 failed-stage epoch.

This helper is intentionally fail-closed: it reads paths from the recorded
outer ledger and stage summary, refuses an existing destination, and binds the
historical Tcl bytes to the recorded source commit rather than the worktree.
It never invokes a hardware tool.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def resolve_recorded(root: Path, raw: Any) -> Path:
    path = Path(str(raw))
    return path.resolve(strict=False) if path.is_absolute() else (root / path).resolve(strict=False)


def resolve_generation_manifest(
    root: Path,
    run_id: str,
    *,
    source_commit: str,
    sequence_plan_path: Path,
    sequence_plan_sha256: str,
) -> Path:
    """Find the unique generator manifest bound to the executed plan.

    A pre-hardware plan can become stale after a source/checkpoint change.  A
    replacement plan must use a new bundle directory rather than overwriting
    the stale bundle, so the run ID alone is not a sufficient provenance key.
    """

    build_root = root / "build" / "p7_authorized_sequence"
    matches: list[Path] = []
    if build_root.is_dir():
        for bundle in build_root.iterdir():
            if not bundle.is_dir() or bundle.is_symlink() or not bundle.name.startswith(run_id):
                continue
            candidate = bundle / "p7_authorized_sequence_generation_manifest.json"
            if not candidate.is_file() or candidate.is_symlink():
                continue
            payload = read_json(candidate)
            plan = payload.get("sequence_plan")
            if (
                payload.get("schema") == "rf-comm-p7-authorized-sequence-generator-v1"
                and str(payload.get("source_commit", "")).lower() == source_commit.lower()
                and isinstance(plan, dict)
                and str(plan.get("sha256", "")).lower() == sequence_plan_sha256.lower()
                and resolve_recorded(root, plan.get("path")) == sequence_plan_path.resolve(strict=False)
            ):
                matches.append(candidate.resolve(strict=True))
    if len(matches) != 1:
        raise ValueError(
            "executed sequence plan must bind exactly one generation manifest; "
            f"observed {len(matches)} matches"
        )
    return matches[0]


def copy_record(root: Path, destination: Path, role: str, original: Path) -> dict[str, Any]:
    original = original.resolve(strict=True)
    data = original.read_bytes()
    digest = sha256_bytes(data)
    suffix = original.suffix or ".bin"
    stem_by_role = {
        "offline_checkpoint": "p7_offline_gate_summary",
        "sequence_plan": "p7_sequence_plan",
        "stage_authorization": "p7_stage_001_authorization",
        "stage_transactions": "p7_stage_001_transactions",
        "stage_execution_plan": "p7_stage_execution_plan",
        "stage_bundle_manifest": "p7_stage_bundle_manifest",
        "generation_manifest": "p7_generation_manifest",
        "recovery_p4_authorization": "p4_recovery_authorization",
    }
    frozen = destination / f"{stem_by_role[role]}_{digest}{suffix}"
    shutil.copyfile(original, frozen)
    try:
        original_text = original.relative_to(root).as_posix()
    except ValueError:
        original_text = str(original)
    return {
        "role": role,
        "original_path": original_text,
        "frozen_path": frozen.relative_to(root).as_posix(),
        "bytes": len(data),
        "sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    root = args.repo_root.resolve(strict=True)
    epoch = root / "evidence" / "hardware" / "p7" / "authorized_sequence" / args.run_id
    ledger_path = epoch / "sequence_execution_ledger.json"
    ledger = read_json(ledger_path)
    failed_index = ledger.get("failed_stage_index")
    attempts = ledger.get("attempts")
    if (
        not isinstance(failed_index, int)
        or isinstance(failed_index, bool)
        or not isinstance(attempts, list)
        or failed_index < 0
        or failed_index >= len(attempts)
        or not isinstance(attempts[failed_index], dict)
    ):
        raise ValueError("outer ledger failed-stage index/attempt list is malformed")
    failed_attempt = attempts[failed_index]
    stage_id = str(failed_attempt.get("stage_id", ""))
    stage_ordinal = failed_index + 1
    full_stage_ordinal_raw = failed_attempt.get("full_stage_ordinal", stage_ordinal)
    if (
        not isinstance(full_stage_ordinal_raw, int)
        or isinstance(full_stage_ordinal_raw, bool)
        or full_stage_ordinal_raw < 1
    ):
        raise ValueError("outer ledger failed attempt full-stage ordinal is malformed")
    full_stage_ordinal = full_stage_ordinal_raw
    ledger_full_ordinals = ledger.get("full_stage_ordinals")
    if ledger_full_ordinals is not None:
        if (
            not isinstance(ledger_full_ordinals, list)
            or failed_index >= len(ledger_full_ordinals)
            or ledger_full_ordinals[failed_index] != full_stage_ordinal
        ):
            raise ValueError("outer ledger failed attempt/full-stage ordinal matrix mismatch")
    summary_file = failed_attempt.get("summary_file")
    if not isinstance(summary_file, dict):
        raise ValueError("outer ledger failed attempt summary record is missing")
    summary_path = resolve_recorded(root, summary_file.get("path"))
    expected_stage_dir = (epoch / f"{full_stage_ordinal:03d}_{stage_id}").resolve(strict=False)
    if summary_path.parent != expected_stage_dir:
        raise ValueError("outer ledger failed attempt summary path does not bind the failed stage directory")
    summary = read_json(summary_path)
    source = str(ledger.get("source_commit", "")).lower()
    is_ps = summary_path.name == "p7_ps_application_stage_summary.json"
    if not is_ps and summary_path.name != "p7_jtag_axi_stage_summary.json":
        raise ValueError("outer ledger failed attempt summary filename is unsupported")
    summary_result = str(
        summary.get("P7_PS_APPLICATION_SAFE_STAGE" if is_ps else "P7_JTAG_AXI_SAFE_STAGE", "")
    )
    if summary_result not in {"FAIL_STAGE", "FAIL_SHUTDOWN_AFTER"}:
        raise ValueError(
            "only an exact FAIL_STAGE or FAIL_SHUTDOWN_AFTER epoch may be frozen by this helper"
        )
    if str(summary.get("safety_validation", {}).get("source_commit_requested", "")).lower() != source:
        raise ValueError("summary/ledger source commit mismatch")
    if (
        ledger.get("status") != "FAIL"
        or ledger.get("attempt_count") != stage_ordinal
        or ledger.get("completed_stage_count") != failed_index
        or ledger.get("next_stage_index") != failed_index
    ):
        raise ValueError("outer ledger does not bind a contiguous PASS prefix followed by one failed stage")

    destination = epoch / "historical_preflight_inputs"
    destination.mkdir(parents=False, exist_ok=False)
    safety = summary["safety_validation"]
    sequence_plan_path = resolve_recorded(root, ledger["sequence_plan"]["path"])
    generation_manifest_path = resolve_generation_manifest(
        root,
        args.run_id,
        source_commit=source,
        sequence_plan_path=sequence_plan_path,
        sequence_plan_sha256=str(ledger["sequence_plan"]["sha256"]),
    )
    records = [
        copy_record(root, destination, "offline_checkpoint", resolve_recorded(root, ledger["offline_checkpoint"]["path"])),
        copy_record(root, destination, "sequence_plan", sequence_plan_path),
        copy_record(root, destination, "stage_authorization", resolve_recorded(root, safety["authorization"]["path"])),
        copy_record(
            root,
            destination,
            "generation_manifest",
            generation_manifest_path,
        ),
        copy_record(root, destination, "recovery_p4_authorization", root / ".hardware_authorization" / "P4_APPROVED.txt"),
    ]
    if is_ps:
        records.extend(
            [
                copy_record(
                    root,
                    destination,
                    "stage_execution_plan",
                    resolve_recorded(root, summary["execution_plan"]["path"]),
                ),
                copy_record(
                    root,
                    destination,
                    "stage_bundle_manifest",
                    resolve_recorded(root, summary["bundle_manifest"]["path"]),
                ),
            ]
        )
    else:
        transaction = summary["transaction_validation"]
        records.append(
            copy_record(
                root,
                destination,
                "stage_transactions",
                resolve_recorded(root, transaction["path"]),
            )
        )

    tcl_relative = "scripts/hw/p7_jtag_axi_transactions.tcl"
    committed = subprocess.run(
        ["git", "show", f"{source}:{tcl_relative}"],
        cwd=root,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if committed.returncode != 0:
        raise RuntimeError(f"unable to read historical Tcl from {source}")
    tcl_bytes = committed.stdout
    blob_sha1 = hashlib.sha1(f"blob {len(tcl_bytes)}\0".encode("ascii") + tcl_bytes).hexdigest()
    tcl_sha256 = sha256_bytes(tcl_bytes)
    frozen_tcl = destination / f"p7_jtag_axi_transactions_{source[:8]}_{blob_sha1}.tcl"
    frozen_tcl.write_bytes(tcl_bytes)
    records.append(
        {
            "role": "historical_stage_tcl",
            "original_path": tcl_relative,
            "frozen_path": frozen_tcl.relative_to(root).as_posix(),
            "git_blob_sha1": blob_sha1,
            "bytes": len(tcl_bytes),
            "sha256": tcl_sha256,
        }
    )

    if stage_id != "p7_safe_idle":
        historical_sources = (
            (
                ("historical_stage_wrapper_python", "scripts/hw/run_p7_ps_application_stage_safe.py"),
                ("historical_process_support_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                ("historical_ps_execute_tcl", "scripts/hw/p7_ps_application_execute.tcl"),
                ("historical_ps_mailbox_backend", "tools/p7_ps_mailbox_backend.py"),
            )
            if is_ps
            else (
                ("historical_stage_wrapper_python", "scripts/hw/run_p7_jtag_axi_stage_safe.py"),
                ("historical_backend_python", "tools/p7_jtag_backend.py"),
                ("historical_lane_phy_rtl", "rtl/tfdu_lane_phy.sv"),
            )
        )
        for role, relative in historical_sources:
            committed_source = subprocess.run(
                ["git", "show", f"{source}:{relative}"],
                cwd=root,
                capture_output=True,
                check=False,
                timeout=30,
            )
            if committed_source.returncode != 0:
                raise RuntimeError(f"unable to read historical source from {source}: {relative}")
            source_bytes = committed_source.stdout
            source_blob = hashlib.sha1(
                f"blob {len(source_bytes)}\0".encode("ascii") + source_bytes
            ).hexdigest()
            source_sha = sha256_bytes(source_bytes)
            frozen_source = destination / f"{Path(relative).stem}_{source[:8]}_{source_blob}{Path(relative).suffix}"
            frozen_source.write_bytes(source_bytes)
            records.append(
                {
                    "role": role,
                    "original_path": relative,
                    "frozen_path": frozen_source.relative_to(root).as_posix(),
                    "git_blob_sha1": source_blob,
                    "bytes": len(source_bytes),
                    "sha256": source_sha,
                }
            )

    recoveries = sorted(
        path.name
        for path in epoch.glob(f"recovery_shutdown_after_failed_stage{full_stage_ordinal:03d}_*")
        if path.is_dir()
    )
    if not recoveries:
        raise ValueError("failed stage has no independent shutdown recovery directory")
    final_recovery = epoch / recoveries[-1] / "program_tfdu_shutdown_safe.summary.txt"
    final_text = final_recovery.read_text(encoding="utf-8", errors="strict")
    if "SHUTDOWN_EXIT=0" not in final_text or "PROGRAM_TFDU_SHUTDOWN_SAFE_STATUS=PASS" not in final_text:
        raise ValueError("final independent recovery does not prove shutdown PASS")
    failed_stage_mutation_attempted = any(
        summary.get(key) is True
        for key in (
            "programmed_fpga",
            "programmed_candidate",
            "programmed_shutdown_before",
            "programmed_shutdown_after",
            "started_ps_elf",
            "drove_tfdu_txd",
            "enabled_tfdu_receiver",
        )
    )
    manifest = {
        "schema": "rf-comm-p7-historical-failed-stage-inputs-v1",
        "run_id": args.run_id,
        "source_commit": source,
        "stage_index": failed_index,
        "full_stage_ordinal": full_stage_ordinal,
        "stage_id": stage_id,
        "result": summary_result,
        "mutation_attempted": failed_stage_mutation_attempted,
        "candidate_mutation_attempted": bool(
            summary.get("programmed_candidate") is True
            or summary.get("programmed_fpga") is True
            or summary.get("started_ps_elf") is True
        ),
        "coverage_claimed": False,
        "recovery_directories": recoveries,
        "files": records,
    }
    manifest_path = destination / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"P7_FAILED_STAGE_FREEZE=PASS")
    print(f"RUN_ID={args.run_id}")
    print(f"SOURCE_COMMIT={source}")
    print(f"FROZEN_FILE_COUNT={len(records)}")
    print(f"MANIFEST={manifest_path}")
    print(f"MANIFEST_SHA256={sha256_bytes(manifest_path.read_bytes())}")
    print("NO_HARDWARE_ACTIONS_EXECUTED=1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
