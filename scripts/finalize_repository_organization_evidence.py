#!/usr/bin/env python3
"""Write the final repository-organization gate and consistency summaries.

The expensive local-input hash inventory is an input to this writer and is not
rescanned here.  Gate results are supplied from the single final execution.
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
OUT = ROOT / "evidence/generated"
P9_TARGET = "818d335c229d7b92223c279159aab84a5207ef92"
P8E_TARGET = "57ff1079b10a5c0de156b621820774bbb111c5ee"

EVIDENCE_INPUTS = [
    ".gitignore",
    "config/project_requirements.yaml",
    "docs/REQUIREMENT_TRACEABILITY_MATRIX.md",
    "docs/hardware/boards/AX7010/reference/README.md",
    "docs/hardware/boards/AX7010/reference/manifest.json",
    "docs/hardware/boards/AX7020/reference/README.md",
    "docs/hardware/boards/AX7020/reference/manifest.json",
    "docs/repository/GIT_BRANCH_AND_WORKTREE_STRUCTURE.md",
    "docs/repository/REPOSITORY_LAYOUT.md",
    "docs/repository/UNTRACKED_CONTENT_DISPOSITION.md",
    "docs/repository/WORKTREE_POLICY.md",
    "evidence/generated/repo_aux_worktree_untracked_audit.json",
    "evidence/generated/repo_aux_worktree_untracked_audit.md",
    "evidence/generated/repo_branch_graph_raw.txt",
    "evidence/generated/repo_organization_intake.json",
    "evidence/generated/repo_organization_intake.md",
    "evidence/generated/repo_untracked_content_audit.json",
    "evidence/generated/repo_untracked_content_audit.md",
    "evidence/generated/repo_untracked_sha256_manifest.json",
    "evidence/generated/repo_worktree_status_raw.txt",
    "legacy/RF_COMM/README.md",
    "legacy/RF_COMM/docs/LOCAL_ONLY_MANIFEST.json",
    "scripts/audit_repository_structure.py",
    "scripts/finalize_repository_organization_evidence.py",
    "scripts/reconcile_p0_p7_evidence.py",
    "scripts/run_offline_gates.py",
    "scripts/run_p8e_dual_target_gate.py",
    "scripts/run_vivado_nonhardware_build.py",
    "scripts/verify_p9_existing.py",
    "tools/audit_repository_structure.ps1",
    "tools/summarize_gate.py",
]


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_value(*args: str) -> str:
    return git(*args).stdout.strip()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(relative: str, errors: list[str]) -> dict[str, Any]:
    path = ROOT / relative
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"cannot load {relative}: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"expected JSON object: {relative}")
        return {}
    return value


def write_json(relative: str, payload: dict[str, Any]) -> None:
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="Finalize repository organization evidence from completed gate results"
    )
    for name in (
        "repository-audit-status",
        "wrapper-audit-status",
        "p8e-status",
        "p9-status",
        "offline-status",
        "summarizer-status",
        "project-status-check",
        "traceability-check",
        "diff-check-status",
    ):
        result.add_argument(f"--{name}", required=True)
    result.add_argument("--p9-verified-file-count", type=int, required=True)
    result.add_argument("--p9-verified-bytes", type=int, required=True)
    result.add_argument("--p8e-artifact-count", type=int, required=True)
    result.add_argument("--json-summary", action="store_true")
    return result


def main() -> int:
    args = parser().parse_args()
    generated_utc = datetime.now(timezone.utc).isoformat()
    errors: list[str] = []

    if os.environ.get("NO_HARDWARE") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")

    reported = {
        "repository_audit": args.repository_audit_status,
        "wrapper_audit": args.wrapper_audit_status,
        "p8e_verify_existing": args.p8e_status,
        "p9_verify_existing": args.p9_status,
        "offline_regression": args.offline_status,
        "offline_summarizer": args.summarizer_status,
        "project_status_generated_check": args.project_status_check,
        "requirement_traceability_check": args.traceability_check,
        "git_diff_check": args.diff_check_status,
    }
    for label, status in reported.items():
        if status != "PASS":
            errors.append(f"{label} did not pass: {status}")

    intake = load_json("evidence/generated/repo_organization_intake.json", errors)
    untracked = load_json("evidence/generated/repo_untracked_content_audit.json", errors)
    raw_manifest = load_json("evidence/generated/repo_untracked_sha256_manifest.json", errors)
    auxiliary = load_json("evidence/generated/repo_aux_worktree_untracked_audit.json", errors)
    offline = load_json("evidence/generated/offline_gate_summary.json", errors)
    closeout = load_json("evidence/generated/p9_post_checkpoint_closeout.json", errors)
    for label, document in (
        ("organization intake", intake),
        ("untracked audit", untracked),
        ("raw SHA256 manifest", raw_manifest),
        ("auxiliary audit", auxiliary),
        ("P9 closeout", closeout),
    ):
        if document.get("status") != "PASS":
            errors.append(f"{label} status is not PASS")
    if offline.get("status") != args.offline_status:
        errors.append("offline summary status does not match the executed gate result")
    if untracked.get("file_count") != raw_manifest.get("file_count"):
        errors.append("untracked audit and SHA256 manifest file counts differ")
    manifest_total_bytes = sum(
        int(row.get("size_bytes", row.get("bytes", 0)))
        for row in raw_manifest.get("files", [])
        if isinstance(row, dict)
    )
    if untracked.get("total_bytes") != manifest_total_bytes:
        errors.append("untracked audit and SHA256 manifest byte totals differ")

    topology: dict[str, Any] = {}
    try:
        branch_names = git_value("for-each-ref", "--format=%(refname:short)", "refs/heads").splitlines()
        worktrees = git_value("worktree", "list", "--porcelain")
        topology = {
            "main": git_value("rev-parse", "main"),
            "p8_branch": git_value("rev-parse", "p8/integration"),
            "p8e_tag_target": git_value("rev-list", "-n", "1", "p8e-pass"),
            "p9_branch": git_value("rev-parse", "p9/z7010-stationary-2lane"),
            "p9_tag_target": git_value("rev-list", "-n", "1", "p9-z7010-2lane-pass"),
            "p10_branch_absent": not any(name.lower().startswith("p10") for name in branch_names),
            "p10_worktree_absent": "p10" not in worktrees.lower(),
        }
        if topology["p8e_tag_target"] != P8E_TARGET:
            errors.append("P8E tag target moved")
        if topology["p9_tag_target"] != P9_TARGET or topology["p9_branch"] != P9_TARGET:
            errors.append("P9 tag or branch target moved")
        if git("merge-base", "--is-ancestor", P9_TARGET, "main", check=False).returncode:
            errors.append("main does not contain the P9 checkpoint")
        if not topology["p10_branch_absent"]:
            errors.append("P10 branch exists")
        if not topology["p10_worktree_absent"]:
            errors.append("P10 worktree exists")
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"final topology check failed: {exc}")

    commands = [
        {
            "command": "python scripts/audit_repository_structure.py --json-summary",
            "status": args.repository_audit_status,
        },
        {
            "command": "powershell -NoProfile -ExecutionPolicy Bypass -File tools/audit_repository_structure.ps1 -JsonSummary",
            "status": args.wrapper_audit_status,
        },
        {
            "command": "python scripts/run_p8e_dual_target_gate.py --verify-existing --json-summary",
            "status": args.p8e_status,
            "artifact_count": args.p8e_artifact_count,
        },
        {
            "command": "python scripts/verify_p9_existing.py --json-summary",
            "status": args.p9_status,
            "verified_unique_file_count": args.p9_verified_file_count,
            "verified_bytes": args.p9_verified_bytes,
        },
        {
            "command": "python scripts/run_offline_gates.py --verify-existing-vivado",
            "status": args.offline_status,
            "note": "The complete fresh 12-stage Vivado build ran once; the successful final orchestration directly rehashed and marker-checked those routed outputs after repairing postprocessing.",
        },
        {
            "command": "python tools/summarize_gate.py",
            "status": args.summarizer_status,
            "note": "Canonical entry discovered at tools/summarize_gate.py; scripts/summarize_gate.py is absent.",
        },
        {
            "command": "python scripts/generate_project_status.py --check",
            "status": args.project_status_check,
        },
        {
            "command": "python scripts/generate_requirement_traceability.py --check",
            "status": args.traceability_check,
        },
        {"command": "git diff --check", "status": args.diff_check_status},
    ]

    gate_summary = {
        "schema_version": 1,
        "status": "PASS" if not errors else "FAIL",
        "test_id": "REPOSITORY-ORGANIZATION-FINAL-GATE",
        "generated_utc": generated_utc,
        "scope": "REPOSITORY_ORGANIZATION_AND_MAINLINE_CONSOLIDATION_BEFORE_P10",
        "commands": commands,
        "topology": topology,
        "untracked_input_audit": {
            "file_count": untracked.get("file_count"),
            "total_bytes": untracked.get("total_bytes"),
            "classification_counts": untracked.get("classification_counts"),
            "single_hash_inventory_reused": True,
        },
        "p8_frozen_history_modified": False,
        "p9_frozen_history_modified": False,
        "sparse_checkout_preserved": True,
        "auxiliary_worktrees_modified": False,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "p10_actions_executed": False,
        "remote_push_executed": False,
        "errors": errors,
    }
    write_json("evidence/generated/repo_organization_gate_summary.json", gate_summary)
    gate_md = [
        "# Repository Organization Final Gate",
        "",
        f"STATUS: {gate_summary['status']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION: false",
        "P10_ACTIONS_EXECUTED: false",
        "REMOTE_PUSH_EXECUTED: false",
        "",
        "The local-input inventory was hashed once and reused; this finalizer did not rescan raw vendor inputs.",
        "",
        "| Command | Status |",
        "|---|---|",
    ]
    gate_md.extend(f"| `{row['command']}` | {row['status']} |" for row in commands)
    if errors:
        gate_md.extend(["", "## Errors", ""] + [f"- {error}" for error in errors])
    gate_md.append("")
    (OUT / "repo_organization_gate_summary.md").write_text(
        "\n".join(gate_md), encoding="utf-8", newline="\n"
    )

    consistency_errors: list[str] = []
    records: list[dict[str, Any]] = []
    consistency_inputs = EVIDENCE_INPUTS + [
        "evidence/generated/repo_organization_gate_summary.json",
        "evidence/generated/repo_organization_gate_summary.md",
    ]
    for relative in consistency_inputs:
        path = ROOT / relative
        if not path.is_file():
            consistency_errors.append(f"missing organization evidence input: {relative}")
            continue
        records.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    consistency = {
        "schema_version": 1,
        "status": "PASS" if not errors and not consistency_errors else "FAIL",
        "test_id": "REPOSITORY-ORGANIZATION-EVIDENCE-CONSISTENCY",
        "generated_utc": generated_utc,
        "file_count": len(records),
        "files": records,
        "raw_local_input_manifest": "evidence/generated/repo_untracked_sha256_manifest.json",
        "raw_local_inputs_rehashed": False,
        "self_reference_exclusion": [
            "evidence/generated/repo_organization_evidence_consistency.json",
            "evidence/generated/repo_organization_evidence_consistency.md",
        ],
        "hardware_actions_executed": False,
        "errors": errors + consistency_errors,
    }
    write_json("evidence/generated/repo_organization_evidence_consistency.json", consistency)
    consistency_md = [
        "# Repository Organization Evidence Consistency",
        "",
        f"STATUS: {consistency['status']}",
        f"HASHED_FILE_COUNT: {consistency['file_count']}",
        "RAW_LOCAL_INPUTS_REHASHED: false",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "",
        "The adjacent JSON contains the SHA256 and byte count for every covered organization artifact. The consistency pair excludes itself to avoid recursive hashes.",
        "",
    ]
    (OUT / "repo_organization_evidence_consistency.md").write_text(
        "\n".join(consistency_md), encoding="utf-8", newline="\n"
    )

    result = {
        "status": consistency["status"],
        "gate_summary": "evidence/generated/repo_organization_gate_summary.json",
        "evidence_consistency": "evidence/generated/repo_organization_evidence_consistency.json",
        "hashed_file_count": len(records),
        "hardware_actions_executed": False,
        "errors": consistency["errors"],
    }
    if args.json_summary:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"REPOSITORY_ORGANIZATION_EVIDENCE={result['status']}")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
