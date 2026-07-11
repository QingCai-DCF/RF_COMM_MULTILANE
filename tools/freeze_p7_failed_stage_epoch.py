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
    summary_path = epoch / "001_p7_safe_idle" / "p7_jtag_axi_stage_summary.json"
    ledger_path = epoch / "sequence_execution_ledger.json"
    summary = read_json(summary_path)
    ledger = read_json(ledger_path)
    source = str(ledger.get("source_commit", "")).lower()
    if summary.get("P7_JTAG_AXI_SAFE_STAGE") != "FAIL_STAGE":
        raise ValueError("only an exact FAIL_STAGE epoch may be frozen by this helper")
    if str(summary.get("safety_validation", {}).get("source_commit_requested", "")).lower() != source:
        raise ValueError("summary/ledger source commit mismatch")
    if ledger.get("status") != "FAIL" or ledger.get("attempt_count") != 1 or ledger.get("completed_stage_count") != 0:
        raise ValueError("outer ledger is not the exact one-attempt, zero-completion FAIL boundary")

    destination = epoch / "historical_preflight_inputs"
    destination.mkdir(parents=False, exist_ok=False)
    safety = summary["safety_validation"]
    transaction = summary["transaction_validation"]
    records = [
        copy_record(root, destination, "offline_checkpoint", resolve_recorded(root, ledger["offline_checkpoint"]["path"])),
        copy_record(root, destination, "sequence_plan", resolve_recorded(root, ledger["sequence_plan"]["path"])),
        copy_record(root, destination, "stage_authorization", resolve_recorded(root, safety["authorization"]["path"])),
        copy_record(root, destination, "stage_transactions", resolve_recorded(root, transaction["path"])),
        copy_record(
            root,
            destination,
            "generation_manifest",
            root / "build" / "p7_authorized_sequence" / args.run_id / "p7_authorized_sequence_generation_manifest.json",
        ),
        copy_record(root, destination, "recovery_p4_authorization", root / ".hardware_authorization" / "P4_APPROVED.txt"),
    ]

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

    recoveries = sorted(path.name for path in epoch.glob("recovery_shutdown_after_failed_stage1_*") if path.is_dir())
    if len(recoveries) != 2:
        raise ValueError(f"expected exactly two r4 recovery directories, found {len(recoveries)}")
    manifest = {
        "schema": "rf-comm-p7-historical-failed-stage-inputs-v1",
        "run_id": args.run_id,
        "source_commit": source,
        "stage_index": 0,
        "stage_id": "p7_safe_idle",
        "result": "FAIL_STAGE",
        "mutation_attempted": True,
        "candidate_mutation_attempted": True,
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
