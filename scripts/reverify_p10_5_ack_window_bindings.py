#!/usr/bin/env python3
"""Reverify and bind P8D requirements affected by the P10.5 ACK/window fix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import reverify_p10_p8d_source_bindings as legacy
from p8a_common import render_traceability


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated/p10_5_ack_window_source_reverification"
SUMMARY = OUT / "summary.json"
SUMMARY_MD = OUT / "summary.md"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
TRACEABILITY = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
STAGE = "P10_5_ACK_WINDOW_SOURCE_REVERIFY"
TEST_ID = "P10_5-P8D-ACK-WINDOW-SOURCE-REVERIFICATION"

REQUIREMENT_ARTIFACTS = {
    "L2-ARQ-001": [
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_selective_repeat_rx.sv",
    ],
    "L2-ARQ-002": [
        "config/p8d_data_plane.yaml",
        "rtl/ir_data_plane_top.sv",
    ],
    "L2-SACK-002": [
        "rtl/ir_ack_aggregator.sv",
        "sim/tb/tb_ir_sack_ack_aggregation.sv",
    ],
    "L2-STALE-001": [
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_selective_repeat_rx.sv",
    ],
    "L2-RETRY-001": [
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_health_weighted_scheduler.sv",
        "config/p8d_data_plane.yaml",
    ],
}

REQUIREMENT_TESTS = {
    "L2-ARQ-001": [
        "tb_ir_selective_repeat_tx",
        "tb_ir_data_plane_integration_2lane",
        "tb_ir_data_plane_integration_8lane",
    ],
    "L2-ARQ-002": [
        "tb_ir_selective_repeat_tx",
        "tb_ir_data_plane_integration_2lane",
        "tb_ir_data_plane_integration_8lane",
    ],
    "L2-SACK-002": ["tb_ir_sack_ack_aggregation"],
    "L2-STALE-001": [
        "tb_ir_selective_repeat_tx",
        "tb_ir_data_plane_integration_2lane",
        "tb_ir_data_plane_integration_8lane",
    ],
    "L2-RETRY-001": [
        "tb_ir_selective_repeat_tx",
        "tb_ir_scheduler_migration",
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def update_requirements(summary: dict[str, Any]) -> None:
    document = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    by_id = {item["requirement_id"]: item for item in document["requirements"]}
    summary_path = legacy.rel(SUMMARY)
    summary_sha = legacy.sha256(SUMMARY)
    for requirement_id, paths in REQUIREMENT_ARTIFACTS.items():
        requirement = by_id[requirement_id]
        if requirement.get("status") != "PASS":
            raise RuntimeError(f"{requirement_id} is not PASS")
        history = requirement.setdefault("reverification_history", [])
        previous = {
            "stage": STAGE,
            "previous_source_commit": requirement.get("source_commit"),
            "previous_evidence_path": requirement.get("evidence_path"),
            "previous_artifact_hash": requirement.get("artifact_hash"),
        }
        if not history or history[-1] != previous:
            history.append(previous)
        records = [
            {"path": path, "sha256": legacy.sha256(ROOT / path)}
            for path in paths
        ]
        records.append({"path": summary_path, "sha256": summary_sha})
        requirement.update({
            "test_id": TEST_ID,
            "evidence_path": summary_path,
            "artifact_hashes": records,
            "artifact_hash": records[0]["sha256"],
            "source_commit": summary["verified_source_commit"],
            "reverification_stage": STAGE,
        })
    REQUIREMENTS.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
        newline="\n",
    )
    TRACEABILITY.write_text(
        render_traceability(document), encoding="utf-8", newline="\n"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--update-requirements", action="store_true")
    args = parser.parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        print("P10_5_ACK_WINDOW_REVERIFY_REFUSED=offline environment required")
        return 2
    missing = [str(path) for path in legacy.TOOLS.values() if not path.is_file()]
    if missing:
        print("P10_5_ACK_WINDOW_REVERIFY_REFUSED=missing XSIM tools")
        return 2
    source_paths = sorted(
        {path for spec in legacy.TESTS for path in spec["sources"]}
        | {path for paths in REQUIREMENT_ARTIFACTS.values() for path in paths}
        | {legacy.rel(Path(__file__).resolve())}
    )
    if not legacy.source_tree_is_clean(source_paths):
        print("P10_5_ACK_WINDOW_REVERIFY_REFUSED=bound source worktree dirty")
        return 2

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    raw = OUT / "raw" / run_id
    raw.mkdir(parents=True, exist_ok=False)
    config = legacy.run_command(
        [
            os.sys.executable,
            "scripts/generate_p8d_data_plane_config.py",
            "--verify",
            "--json-summary",
        ],
        ROOT,
        raw / "canonical_config.log",
        timeout=120,
    )
    simulations = [legacy.run_xsim(spec, raw) for spec in legacy.TESTS]
    status = "PASS" if (
        config["returncode"] == 0
        and all(item["status"] == "PASS" for item in simulations)
    ) else "FAIL"
    summary = {
        "schema_version": 1,
        "stage": STAGE,
        "test_id": TEST_ID,
        "profile": "P8D_MULTI_PROFILE_OFFLINE",
        "verification_scope": "PORTABLE_FUNCTION_PASS / OFFLINE_RTL_SOFTWARE_MODEL",
        "status": status,
        "generated_at_utc": utc_now(),
        "verified_source_commit": source_commit,
        "source_worktree_clean": True,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "hardware_scope_promoted": False,
        "claim_boundary": (
            "Refreshes only current-source P8D bindings affected by the P10.5 "
            "ACK aggregation and 32-frame window-boundary remediation."
        ),
        "requirements": REQUIREMENT_TESTS,
        "bound_artifacts": [
            {"path": path, "sha256": legacy.sha256(ROOT / path)}
            for path in sorted(
                {path for paths in REQUIREMENT_ARTIFACTS.values() for path in paths}
            )
        ],
        "canonical_config": {
            key: value
            for key, value in config.items()
            if key not in ("stdout", "stderr")
        },
        "simulations": simulations,
        "raw_run": legacy.rel(raw),
    }
    legacy.write_json(SUMMARY, summary)
    legacy.write_text(
        SUMMARY_MD,
        "\n".join([
            "# P10.5 ACK/window P8D source-binding re-verification",
            "",
            f"- Status: `{status}`",
            f"- Verified source commit: `{source_commit}`",
            "- Hardware actions executed: `false`",
            f"- Raw run: `{legacy.rel(raw)}`",
            "",
            "| Simulation | Result |",
            "|---|---|",
            *[f"| `{item['top']}` | `{item['status']}` |" for item in simulations],
            "",
        ]),
    )
    if status == "PASS" and args.update_requirements:
        update_requirements(summary)
    print(f"P10_5_ACK_WINDOW_SOURCE_REVERIFICATION={status}")
    print(
        "P10_5_ACK_WINDOW_REQUIREMENTS_UPDATED="
        f"{1 if status == 'PASS' and args.update_requirements else 0}"
    )
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
