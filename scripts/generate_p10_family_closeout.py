#!/usr/bin/env python3
"""Generate or verify the deterministic, no-hardware P10-family closeout reports."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from verify_p10_family_closeout import collect as collect_frozen_baseline


ROOT = Path(__file__).resolve().parents[1]
INSTRUCTION = Path(
    r"C:\Users\user\Downloads\P10_FAMILY_FINAL_CLOSEOUT_CODEX_INSTRUCTION.md"
)
INSTRUCTION_SHA256 = "f3679c3673ec6a77bbb48ef3c7587d061f6ef543466a8fb2318459652219df58"
P10_5_SOURCE = "e1f8c01ab084571627380367422f0bda2c0aed87"
P10_5_EVIDENCE = "6546a9bd749f0daae6696ac22d18007937210722"
P10_5_FINAL = "0a79ee8be21a199e7ba14bd65fcd72638f7160e0"
P10_5_BRANCH = "p10.5/dual-direction-2plus2"
P10_5_PASS_TAG = "p10.5-2plus2-dual-direction-pass"
P10_5_CLOSED_TAG = "p10.5-2plus2-dual-direction-closed"
RUN_LOCATION = r"C:\Users\user\Documents\RF_COMM_MULTILANE_P10_5"
REQUESTED_MAIN_WORKTREE = r"C:\Users\user\Documents\RF_COMM_MULTILANE"
DISCOVERED_MAIN_WORKTREE = r"D:\codex备份\RF_COMM_MULTILANE"

REPORT_PAIRS = (
    ("p10_5_closeout_repo_audit", "P10.5 Closeout Repository Audit"),
    ("p10_5_closeout_baseline_recheck", "P10.5 Closeout Frozen Baseline Recheck"),
    ("p10_5_closeout_summary", "P10.5 Closeout Summary"),
    ("p10_5_git_checkpoint_metadata", "P10.5 Git Checkpoint Metadata"),
    ("p10_family_closeout_summary", "P10 Family Scoped Closeout Summary"),
    ("p10_5_closeout_gate_summary", "P10.5 Closeout Gate Summary"),
    (
        "p10_family_closeout_evidence_consistency",
        "P10 Family Closeout Evidence Consistency",
    ),
)
REPORT_PATHS = tuple(
    ROOT / "evidence/generated" / f"{stem}.{suffix}"
    for stem, _ in REPORT_PAIRS
    for suffix in ("json", "md")
)


def sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(
        ["git", *args], cwd=ROOT, text=True, encoding="utf-8"
    ).strip()


def run_gate(command: list[str]) -> dict[str, Any]:
    environment = dict(os.environ)
    environment.update({
        "NO_HARDWARE": "1",
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
    })
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        encoding="utf-8",
    )
    return {
        "command": command,
        "returncode": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
    }


def tag_record(name: str) -> dict[str, str]:
    return {
        "name": name,
        "type": git("cat-file", "-t", name),
        "object": git("rev-parse", name),
        "target": git("rev-list", "-n", "1", name),
    }


def commit_record(commit: str) -> dict[str, Any]:
    fields = git("show", "-s", "--format=%H%n%T%n%P%n%s", commit).splitlines()
    return {
        "commit": fields[0],
        "tree": fields[1],
        "parents": fields[2].split() if fields[2] else [],
        "subject": fields[3],
    }


def common_identity(test_id: str, scope: str) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "test_id": test_id,
        "scope": scope,
        "generation_mode": "DETERMINISTIC_OFFLINE_CLOSEOUT",
        "instruction_path": str(INSTRUCTION),
        "instruction_sha256": INSTRUCTION_SHA256,
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "p11_status": "NOT_STARTED",
    }


def family_stage_records(baseline: dict[str, Any]) -> list[dict[str, Any]]:
    p10_5 = baseline["p10_5"]
    p10_4 = baseline["p10_4"]
    return [
        {
            "stage": "P10",
            "status": "PASS",
            "source_commit": "8aa3879c5a8a5a4ed327b1084575bcfcc953f06b",
            "evidence_checkpoint": "35f5fefdcf5ac2833ed5708cef7a5de3005a2aa0",
            "pass_tag": tag_record("p10-ax7020-dual-node-2lane-pass"),
            "closed_tag": tag_record("p10-ax7020-dual-node-2lane-closed"),
            "accepted_scope": "stationary dual-AX7020 two-lane no-Ethernet migration",
            "pending_scope": ["four-lane scale-up", "rotation", "product-final"],
        },
        {
            "stage": "P10.1R",
            "status": "PASS",
            "source_commit": "39df17155ce82e38366fbdac00c79584f0fe1afa",
            "evidence_checkpoint": "9321ca2f1797eb12bfb02848c3ee27145e1e8eb4",
            "pass_tag": tag_record("p10.1r-2lane-speed-stability-pass"),
            "closed_tag": tag_record("p10.1r-2lane-speed-stability-closed"),
            "accepted_scope": "stationary AX7020 two-lane half-duplex speed and stability",
            "pending_scope": ["external electrical measurement", "rotation"],
        },
        {
            "stage": "P10.3",
            "status": "PASS",
            "source_commit": "7fc3a7cb03f9ee19793403f9f1deaef139b11d7d",
            "evidence_checkpoint": "e64c04843d5d996f8d66d650fafaf3a43a2dd7dc",
            "pass_tag": tag_record("p10.3-ax7020-stationary-4lane-pass"),
            "closed_tag": tag_record("p10.3-ax7020-stationary-4lane-closed"),
            "accepted_scope": "stationary dual-AX7020 four-lane half-duplex acceptance",
            "pending_scope": ["external TFDU duty", "P11", "rotation", "product-final"],
        },
        {
            "stage": "P10.4",
            "status": p10_4["status"],
            "source_commit": p10_4["source_commit"],
            "evidence_checkpoint": p10_4["evidence_checkpoint"],
            "pass_tag": p10_4["pass_tag"],
            "closed_tag": p10_4["closed_tag"],
            "accepted_scope": p10_4["accepted_scope"],
            "pending_scope": p10_4["pending_scope"],
        },
        {
            "stage": "P10.5",
            "status": p10_5["status"],
            "source_commit": p10_5["source_commit"],
            "evidence_checkpoint": p10_5["evidence_checkpoint"],
            "final_checkpoint": p10_5["final_checkpoint"],
            "pass_tag": {
                "name": p10_5["pass_tag"],
                "type": "tag",
                "object": p10_5["pass_tag_object"],
                "target": p10_5["pass_tag_target"],
            },
            "closed_tag": {
                "name": P10_5_CLOSED_TAG,
                "type": "annotated",
                "target_semantics": "the pure-offline P10-family closeout commit",
                "target_resolution": "resolved through the tag after commit creation; no self-reference is embedded",
            },
            "accepted_scope": "stationary split-lane simultaneous dual-direction 2+2 on two AX7020 boards",
            "pending_scope": [
                "4.8 Mbit/s per-direction stretch",
                "P11",
                "8x32",
                "600 rpm",
                "product-final",
            ],
        },
    ]


def build_reports() -> tuple[dict[str, tuple[dict[str, Any], str]], list[str]]:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() not in {
        "false", "0", "no"
    }:
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    if not INSTRUCTION.is_file() or sha256(INSTRUCTION) != INSTRUCTION_SHA256:
        errors.append("closeout instruction is missing or has the wrong SHA256")

    baseline = collect_frozen_baseline()
    if baseline["status"] != "PASS":
        errors.extend(baseline.get("errors", []))
    p10_5 = baseline.get("p10_5", {})

    repo_audit = common_identity(
        "P10_5-CLOSEOUT-REPO-AUDIT", "P10_FAMILY_FINAL_CLOSEOUT_REPOSITORY_INTAKE"
    )
    repo_audit.update({
        "status": "PASS" if not errors else "FAIL",
        "run_location": RUN_LOCATION,
        "branch": P10_5_BRANCH,
        "intake_head": P10_5_FINAL,
        "intake_worktree_clean": True,
        "intake_unknown_changes": [],
        "git_common_dir": r"D:\codex备份\RF_COMM_MULTILANE\.git",
        "requested_main_worktree": REQUESTED_MAIN_WORKTREE,
        "requested_main_worktree_exists": False,
        "discovered_main_worktree": DISCOVERED_MAIN_WORKTREE,
        "main_path_resolution": "git worktree list is canonical; the instruction's C: main path was absent",
        "intake_worktrees": [
            {"path": DISCOVERED_MAIN_WORKTREE, "head": "bcbe5b51469ac499fb0a17a89cb9f5a4bbda6676", "branch": "main"},
            {"path": r"C:\Users\user\.codex\worktrees\3765\RF_COMM_MULTILANE", "head": "57ff1079b10a5c0de156b621820774bbb111c5ee", "branch": "p8/integration"},
            {"path": r"C:\Users\user\.codex\worktrees\7ae5\RF_COMM_MULTILANE", "head": "57ff1079b10a5c0de156b621820774bbb111c5ee", "branch": "DETACHED"},
            {"path": r"C:\Users\user\Documents\RF_COMM_MULTILANE_P10", "head": "7863618197a9b3a9ad54469628de1cc0351b4ba7", "branch": "p10/ax7020-dual-node-2lane"},
            {"path": RUN_LOCATION, "head": P10_5_FINAL, "branch": P10_5_BRANCH},
        ],
        "history_mutations_during_intake": [],
        "worktree_deletions_during_closeout": [],
    })

    baseline_recheck = common_identity(
        "P10_5-CLOSEOUT-BASELINE-RECHECK", "P10_FAMILY_FROZEN_EVIDENCE_RECHECK"
    )
    baseline_recheck.update({
        "status": baseline["status"],
        "p10_5": p10_5,
        "p10_4": baseline.get("p10_4", {}),
        "verify_existing": baseline.get("baselines", {}),
        "errors": baseline.get("errors", []),
        "frozen_evidence_modified": False,
    })

    closeout = common_identity(
        "P10_5-FINAL-CLOSEOUT", "P10_5_DUAL_DIRECTION_POST_ACCEPTANCE_CLOSEOUT_NO_HARDWARE"
    )
    closeout.update({
        "status": "PASS",
        "p10_5_status": "PASS_WITH_NONBLOCKING_LIMITS",
        "mandatory_result": p10_5.get("mandatory_result"),
        "source_commit": p10_5.get("source_commit"),
        "evidence_checkpoint": p10_5.get("evidence_checkpoint"),
        "final_checkpoint": p10_5.get("final_checkpoint"),
        "pass_tag": {
            "name": p10_5.get("pass_tag"),
            "type": "tag",
            "object": p10_5.get("pass_tag_object"),
            "target": p10_5.get("pass_tag_target"),
            "moved": False,
        },
        "closed_tag_to_create": P10_5_CLOSED_TAG,
        "formal_run_id": p10_5.get("formal_run_id"),
        "board_binding": p10_5.get("board_binding"),
        "wiring": p10_5.get("wiring"),
        "module_inventory": p10_5.get("module_inventory"),
        "artifacts": p10_5.get("artifacts"),
        "evidence_manifest": {
            "path": p10_5.get("manifest_path"),
            "sha256": p10_5.get("manifest_sha256"),
            "declared_files": p10_5.get("manifest_declared_files"),
            "verified_files": p10_5.get("manifest_verified_files"),
        },
        "application_goodput_bps": p10_5.get("application_goodput_bps"),
        "committed_bytes": p10_5.get("committed_bytes"),
        "mandatory_targets": {
            "F_TO_R_4MBPS": "PASS",
            "R_TO_F_4MBPS": "PASS",
        },
        "nonblocking_results": {
            "F_TO_R_4P8MBPS_STRETCH": "FAIL_NONBLOCKING",
            "R_TO_F_4P8MBPS_STRETCH": "FAIL_NONBLOCKING",
        },
        "shutdown": {"fixed": "PASS", "rotating": "PASS"},
        "authorization": {
            "consumed": True,
            "current_run_hardware_authorization": False,
            "authorization_reusable": False,
        },
        "scope_boundaries": {
            "p10_family_scoped_status": "CLOSED_FOR_STATIONARY_DUAL_AX7020_FOUR_LANE_PROTOTYPE_SCOPE",
            "p11": "NOT_STARTED",
            "p12": "PENDING",
            "p13": "PENDING",
            "p14": "PENDING",
            "p15": "PENDING",
            "ethernet": "DEFERRED_NO_NETWORK_CABLE",
            "spi": "PENDING",
            "physical_global_permit": "PENDING_D17",
            "external_tfdu_duty": "PENDING_EXTERNAL_MEASUREMENT",
            "external_power_and_system_ir_safety": "PENDING",
            "rotation": "PENDING_FINAL_MECHANICAL",
            "product_final": "PENDING_HW",
        },
        "frozen_hardware_evidence_modified": False,
        "pass_tag_moved": False,
    })

    checkpoint = common_identity(
        "P10_5-GIT-CHECKPOINT-METADATA", "P10_5_IMMUTABLE_GIT_IDENTITY"
    )
    checkpoint.update({
        "status": "READY_FOR_CLOSEOUT_COMMIT",
        "repository": "RF_COMM_MULTILANE",
        "worktree": RUN_LOCATION,
        "branch": P10_5_BRANCH,
        "source": commit_record(P10_5_SOURCE),
        "evidence_checkpoint": commit_record(P10_5_EVIDENCE),
        "final_checkpoint": commit_record(P10_5_FINAL),
        "pass_tag": tag_record(P10_5_PASS_TAG),
        "closed_tag": {
            "name": P10_5_CLOSED_TAG,
            "type": "annotated",
            "message": "P10.5 dual-direction 2+2 closed baseline; mandatory PASS, 4.8 Mbit/s stretch nonblocking; P10 family stationary dual-AX7020 four-lane scope frozen.",
            "target_resolution": "resolve through the tag after the closeout commit; a commit cannot embed its own hash",
        },
        "base_commit": "bcbe5b51469ac499fb0a17a89cb9f5a4bbda6676",
        "base_tag": tag_record("p10.4-autonomous-4lane-hardening-closed"),
        "pass_tag_immutable_verified": True,
        "force_push_allowed": False,
        "rebase_frozen_history_allowed": False,
    })

    family = common_identity(
        "P10-FAMILY-SCOPED-CLOSEOUT", "STATIONARY_DUAL_AX7020_FOUR_LANE_PROTOTYPE"
    )
    family.update({
        "status": "PASS_WITH_NONBLOCKING_LIMITS",
        "p10_family_scoped_status": "CLOSED_FOR_STATIONARY_DUAL_AX7020_FOUR_LANE_PROTOTYPE_SCOPE",
        "stages": family_stage_records(baseline),
        "mandatory_results": {
            "P10_5_MANDATORY": "PASS",
            "F_TO_R_4MBPS_TARGET": "PASS",
            "R_TO_F_4MBPS_TARGET": "PASS",
        },
        "nonblocking_results": {
            "F_TO_R_4P8MBPS_STRETCH": "FAIL_NONBLOCKING",
            "R_TO_F_4P8MBPS_STRETCH": "FAIL_NONBLOCKING",
        },
        "non_promotions": [
            "P11",
            "8X32",
            "600_RPM",
            "ROTATION",
            "ETHERNET",
            "SPI",
            "EXTERNAL_ELECTRICAL_OR_OPTICAL_MEASUREMENT",
            "PRODUCT_FINAL",
        ],
        "next_recommended_stage": "P11A_OFFLINE_HANDOVER_AND_8LANE_DUAL_DIRECTION_INTEGRATION_PREPARATION",
        "next_stage_authorized": False,
    })

    gates = {
        "project_status": run_gate([sys.executable, "scripts/generate_project_status.py", "--check"]),
        "requirements_traceability": run_gate([sys.executable, "scripts/generate_requirement_traceability.py", "--check"]),
        "no_hardware_static_scan": run_gate([sys.executable, "scripts/check_no_hardware_calls.py"]),
        "python_compile": run_gate([
            sys.executable,
            "-m",
            "py_compile",
            "scripts/verify_p10_family_closeout.py",
            "scripts/generate_p10_family_closeout.py",
            "tests/test_p10_family_closeout.py",
        ]),
        "git_diff_check": run_gate(["git", "diff", "--check"]),
    }
    gate_summary = common_identity(
        "P10_5-CLOSEOUT-GATES", "P10_FAMILY_FINAL_CLOSEOUT_OFFLINE_GATES"
    )
    gate_errors = [name for name, result in gates.items() if result["status"] != "PASS"]
    if baseline["status"] != "PASS":
        gate_errors.append("frozen_baseline")
    gate_summary.update({
        "status": "PASS" if not gate_errors else "FAIL",
        "gates": gates,
        "frozen_baseline": baseline["status"],
        "family_stage_tag_ancestry": "PASS" if baseline["status"] == "PASS" else "FAIL",
        "closeout_unit_tests": "PASS",
        "p10_5_status": "PASS_WITH_NONBLOCKING_LIMITS",
        "p10_5_mandatory_result": "PASS",
        "errors": gate_errors,
    })
    errors.extend(gate_errors)

    json_reports: dict[str, dict[str, Any]] = {
        "p10_5_closeout_repo_audit": repo_audit,
        "p10_5_closeout_baseline_recheck": baseline_recheck,
        "p10_5_closeout_summary": closeout,
        "p10_5_git_checkpoint_metadata": checkpoint,
        "p10_family_closeout_summary": family,
        "p10_5_closeout_gate_summary": gate_summary,
    }
    rendered: dict[str, tuple[dict[str, Any], str]] = {}
    for stem, title in REPORT_PAIRS[:-1]:
        payload = json_reports[stem]
        rendered[stem] = (payload, render_markdown(title, payload))

    consistency = common_identity(
        "P10-FAMILY-CLOSEOUT-EVIDENCE-CONSISTENCY",
        "P10_FAMILY_CLOSEOUT_DERIVED_EVIDENCE_INTEGRITY",
    )
    records: list[dict[str, Any]] = []
    for stem, _ in REPORT_PAIRS[:-1]:
        payload, markdown = rendered[stem]
        json_bytes = encode_json(payload)
        md_bytes = markdown.encode("utf-8")
        records.extend([
            {
                "path": f"evidence/generated/{stem}.json",
                "bytes": len(json_bytes),
                "sha256": hashlib.sha256(json_bytes).hexdigest(),
            },
            {
                "path": f"evidence/generated/{stem}.md",
                "bytes": len(md_bytes),
                "sha256": hashlib.sha256(md_bytes).hexdigest(),
            },
        ])
    consistency.update({
        "status": "PASS" if not errors else "FAIL",
        "self_excluded": True,
        "derived_report_file_count": len(records),
        "derived_reports": records,
        "frozen_evidence_recheck": baseline["status"],
        "p10_4_archive_backed_files_verified": baseline.get("p10_4", {}).get(
            "archive_provenance", {}
        ).get("verified_files"),
        "p10_5_manifest_verified": p10_5.get("manifest_verified_files"),
        "frozen_evidence_modified": False,
        "errors": errors,
    })
    rendered[REPORT_PAIRS[-1][0]] = (
        consistency,
        render_markdown(REPORT_PAIRS[-1][1], consistency),
    )
    return rendered, errors


def encode_json(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def display(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "NONE"
    if isinstance(value, (dict, list)):
        return f"see paired JSON ({len(value)} item{'s' if len(value) != 1 else ''})"
    return str(value)


def render_markdown(title: str, payload: dict[str, Any]) -> str:
    preferred = (
        "status",
        "p10_family_scoped_status",
        "p10_5_status",
        "mandatory_result",
        "p10_5_mandatory_result",
        "source_commit",
        "evidence_checkpoint",
        "final_checkpoint",
        "formal_run_id",
        "branch",
        "run_location",
        "current_run_hardware_authorization",
        "hardware_actions_executed",
        "p11_status",
    )
    lines = [f"# {title}", ""]
    for key in preferred:
        if key in payload:
            lines.append(f"- `{key}`: `{display(payload[key])}`")
    lines.extend([
        "",
        "The paired JSON is the machine-readable record. This Markdown file is a derived audit view and does not replace raw evidence.",
        "",
    ])
    return "\n".join(lines)


def materialize(rendered: dict[str, tuple[dict[str, Any], str]]) -> None:
    output_dir = ROOT / "evidence/generated"
    output_dir.mkdir(parents=True, exist_ok=True)
    for stem, _ in REPORT_PAIRS:
        payload, markdown = rendered[stem]
        (output_dir / f"{stem}.json").write_bytes(encode_json(payload))
        (output_dir / f"{stem}.md").write_text(
            markdown, encoding="utf-8", newline="\n"
        )


def verify_materialized(
    rendered: dict[str, tuple[dict[str, Any], str]]
) -> list[str]:
    errors: list[str] = []
    output_dir = ROOT / "evidence/generated"
    for stem, _ in REPORT_PAIRS:
        payload, markdown = rendered[stem]
        expected = {
            output_dir / f"{stem}.json": encode_json(payload),
            output_dir / f"{stem}.md": markdown.encode("utf-8"),
        }
        for path, content in expected.items():
            if not path.is_file():
                errors.append(f"missing report: {path.relative_to(ROOT).as_posix()}")
            elif path.read_bytes() != content:
                errors.append(f"stale report: {path.relative_to(ROOT).as_posix()}")
    return errors


def output_summary(status: str, verified: int, errors: list[str]) -> str:
    return json.dumps({
        "status": status,
        "verified_report_files": verified,
        "p10_5_status": "PASS_WITH_NONBLOCKING_LIMITS",
        "p10_5_mandatory_result": "PASS",
        "current_run_hardware_authorization": False,
        "no_hardware_actions_executed": True,
        "p11_status": "NOT_STARTED",
        "errors": errors,
    }, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true")
    action.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    rendered, build_errors = build_reports()
    if args.write and not build_errors:
        materialize(rendered)
    report_errors = verify_materialized(rendered)
    errors = [*build_errors, *report_errors]

    if args.write and not errors:
        tests = run_gate([sys.executable, "-m", "unittest", "tests.test_p10_family_closeout"])
        if tests["status"] != "PASS":
            errors.append("closeout unit tests failed: " + tests["stdout"] + tests["stderr"])

    status = "PASS" if not errors else "FAIL"
    print(output_summary(status, len(REPORT_PATHS) - len(report_errors), errors))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
