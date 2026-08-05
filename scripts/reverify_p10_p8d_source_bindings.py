#!/usr/bin/env python3
"""Directly reverify P8D PASS bindings changed by a P10 data-plane update."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from p8a_common import render_traceability


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated/p10_3_retry_path_diversity_source_reverification"
SUMMARY = OUT / "summary.json"
SUMMARY_MD = OUT / "summary.md"
REQ_PATH = ROOT / "config/project_requirements.yaml"
TRACE_PATH = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
VIVADO_BIN = Path(r"D:\Xilinx\Vivado\2023.1\bin")
TOOLS = {name: VIVADO_BIN / f"{name}.bat" for name in ("xvlog", "xelab", "xsim")}
STAGE = "P10_3_RETRY_PATH_DIVERSITY_SOURCE_REVERIFY"
TEST_ID = "P10_3-P8D-RETRY-PATH-DIVERSITY-REVERIFICATION"

CORE_RTL = [
    "rtl/ir_seq_math_pkg.sv",
    "rtl/ir_ack_aggregator.sv",
    "rtl/ir_health_weighted_scheduler.sv",
    "rtl/ir_selective_repeat_tx.sv",
    "rtl/ir_selective_repeat_rx.sv",
    "rtl/ir_data_plane_top.sv",
]

TESTS: list[dict[str, Any]] = [
    {
        "top": "tb_ir_scheduler_migration",
        "sources": [
            "rtl/ir_health_weighted_scheduler.sv",
            "rtl/ir_retry_migration.sv",
            "sim/tb/tb_ir_scheduler_migration.sv",
        ],
        "required_markers": [
            "P8D_HEALTH_AWARE_WEIGHTED_SCHEDULER_PASS=1",
            "P8D_SCHEDULER_FAIRNESS_PASS=1",
            "P8D_RETRY_ALTERNATE_LANE_PASS=1",
            "P8D_RETRY_MIGRATION_ACKED_BLOCK_PASS=1",
            "TB_IR_SCHEDULER_MIGRATION_PASS=1",
        ],
    },
    {
        "top": "tb_ir_selective_repeat_tx",
        "sources": [
            "rtl/ir_seq_math_pkg.sv",
            "rtl/ir_selective_repeat_tx.sv",
            "sim/tb/tb_ir_selective_repeat_tx.sv",
        ],
        "required_markers": [
            "P8D_GLOBAL_OUTSTANDING_32_PASS=1",
            "P8D_RETRY_EXHAUSTION_BOUNDED_PASS=1",
            "P8D_ACKED_FRAME_SINGLE_COMPLETION_PASS=1",
            "TB_IR_SELECTIVE_REPEAT_TX_PASS=1",
        ],
    },
    {
        "top": "tb_ir_sack_ack_aggregation",
        "sources": [
            "rtl/ir_seq_math_pkg.sv",
            "rtl/ir_sack_codec.sv",
            "rtl/ir_ack_aggregator.sv",
            "sim/tb/tb_ir_sack_ack_aggregation.sv",
        ],
        "required_markers": [
            "P8D_SACK_ENCODE_DECODE_PASS=1",
            "P8D_ACK_AGGREGATION_BOUNDED_DELAY_PASS=1",
            "TB_IR_SACK_ACK_AGGREGATION_PASS=1",
        ],
    },
    {
        "top": "tb_ir_data_plane_integration_2lane",
        "sources": [
            *CORE_RTL,
            "sim/tb/p8d_data_plane_integration_common.sv",
            "sim/tb/tb_ir_data_plane_integration_2lane.sv",
        ],
        "required_markers": [
            "P8D_DATA_PLANE_GLOBAL_WINDOW_SAFETY_INTEGRATION_PASS=1",
            "P8D_DATA_PLANE_DUPLICATE_APPLICATION_DELIVERY_ZERO_PASS=1",
            "TB_IR_DATA_PLANE_INTEGRATION_2LANE_PASS=1",
        ],
    },
    {
        "top": "tb_ir_data_plane_integration_8lane",
        "sources": [
            *CORE_RTL,
            "sim/tb/p8d_data_plane_integration_common.sv",
            "sim/tb/tb_ir_data_plane_integration_8lane.sv",
        ],
        "required_markers": [
            "P8D_DATA_PLANE_GLOBAL_WINDOW_SAFETY_INTEGRATION_PASS=1",
            "P8D_DATA_PLANE_DUPLICATE_APPLICATION_DELIVERY_ZERO_PASS=1",
            "TB_IR_DATA_PLANE_INTEGRATION_8LANE_PASS=1",
        ],
    },
]

BOUND_ARTIFACTS = {
    "L2-ARQ-002": ["config/p8d_data_plane.yaml", "rtl/ir_data_plane_top.sv"],
    "L2-SACK-001": ["rtl/ir_sack_codec.sv", "config/p8d_data_plane.yaml"],
    "L2-SACK-002": ["rtl/ir_ack_aggregator.sv", "sim/tb/tb_ir_sack_ack_aggregation.sv"],
    "L2-MIG-001": [
        "rtl/ir_retry_migration.sv",
        "rtl/ir_health_weighted_scheduler.sv",
        "sim/tb/tb_ir_scheduler_migration.sv",
    ],
    "L2-RETRY-001": [
        "rtl/ir_selective_repeat_tx.sv",
        "rtl/ir_health_weighted_scheduler.sv",
        "config/p8d_data_plane.yaml",
    ],
    "SCHED-001": [
        "rtl/ir_health_weighted_scheduler.sv",
        "tools/p8d_data_plane_reference.py",
        "sim/tb/tb_ir_scheduler_migration.sv",
    ],
    "SCHED-002": [
        "rtl/ir_health_weighted_scheduler.sv",
        "sim/tb/tb_ir_scheduler_migration.sv",
    ],
    "SCHED-003": [
        "rtl/ir_health_weighted_scheduler.sv",
        "config/p8d_data_plane.yaml",
        "sim/tb/tb_ir_scheduler_migration.sv",
    ],
    "PERF-MODEL-001": [
        "scripts/model_p8d_airtime.py",
        "config/p8d_data_plane.yaml",
        "evidence/generated/p10_1_performance_model.json",
    ],
}
INVALIDATED_P10_3F_OFFLINE_REQUIREMENTS = (
    "P10_3F-OFF-001",
    "P10_3F-OFF-002",
    "P10_3F-OFF-003",
    "P10_3F-OFF-004",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False) + "\n")


def normalize_captured_text(value: str) -> str:
    """Keep raw tool content while making committed logs pass diff checks."""
    return "\n".join(line.rstrip() for line in value.splitlines())


def run_command(command: list[str], cwd: Path, log: Path, timeout: int = 600) -> dict[str, Any]:
    started = utc_now()
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            shell=False,
            env={
                **os.environ,
                "NO_HARDWARE": "1",
                "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
            },
        )
        returncode = result.returncode
        stdout = result.stdout
        stderr = result.stderr
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        timed_out = True
    content = "\n".join([
        "COMMAND=" + subprocess.list2cmdline(command),
        f"RETURN_CODE={returncode}",
        f"STARTED_UTC={started}",
        f"FINISHED_UTC={utc_now()}",
        f"TIMED_OUT={1 if timed_out else 0}",
        "STDOUT_BEGIN",
        normalize_captured_text(stdout),
        "STDOUT_END",
        "STDERR_BEGIN",
        normalize_captured_text(stderr),
        "STDERR_END",
        "",
    ])
    write_text(log, content)
    return {
        "command": subprocess.list2cmdline(command),
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout": stdout,
        "stderr": stderr,
        "log": rel(log),
        "log_sha256": sha256(log),
    }


def run_xsim(spec: dict[str, Any], raw: Path) -> dict[str, Any]:
    top = str(spec["top"])
    work = ROOT / "build/p10_3_retry_path_diversity_source_reverification" / raw.name / top / "work"
    work.mkdir(parents=True, exist_ok=False)
    snapshot = top + "_snapshot"
    phases = [
        (
            "compile",
            [
                str(TOOLS["xvlog"]),
                "--sv",
                "-i",
                str(ROOT / "rtl"),
                *[str(ROOT / source) for source in spec["sources"]],
            ],
        ),
        ("elaborate", [str(TOOLS["xelab"]), top, "-debug", "typical", "-s", snapshot]),
        ("run", [str(TOOLS["xsim"]), snapshot, "-runall"]),
    ]
    records: dict[str, Any] = {}
    combined = ""
    passed = True
    for phase, command in phases:
        result = run_command(command, work, raw / top / f"{phase}.log")
        combined += result["stdout"] + "\n" + result["stderr"] + "\n"
        records[phase] = {key: value for key, value in result.items() if key not in ("stdout", "stderr")}
        if result["returncode"] != 0 or result["timed_out"]:
            passed = False
            break
    missing = [marker for marker in spec["required_markers"] if marker not in combined]
    fatal = bool(re.search(r"(^|\n)(Fatal:|FATAL_ERROR|ERROR:.*\$fatal|.*EXPECT_FAIL:)", combined))
    if missing or fatal:
        passed = False
    return {
        "top": top,
        "status": "PASS" if passed else "FAIL",
        "sources": spec["sources"],
        "required_markers": spec["required_markers"],
        "missing_markers": missing,
        "fatal_detected": fatal,
        "phases": records,
    }


def source_tree_is_clean(paths: list[str]) -> bool:
    status = subprocess.check_output(
        ["git", "status", "--porcelain", "--untracked-files=no", "--", *paths],
        cwd=ROOT,
        text=True,
    )
    return not status.strip()


def update_requirements(summary: dict[str, Any]) -> None:
    document = yaml.safe_load(REQ_PATH.read_text(encoding="utf-8"))
    by_id = {item["requirement_id"]: item for item in document["requirements"]}
    summary_rel = rel(SUMMARY)
    summary_hash = sha256(SUMMARY)
    for requirement_id, paths in BOUND_ARTIFACTS.items():
        requirement = by_id[requirement_id]
        if requirement.get("status") != "PASS":
            raise RuntimeError(f"{requirement_id} is not PASS and cannot be refreshed")
        history = requirement.setdefault("reverification_history", [])
        if requirement.get("evidence_path") != summary_rel:
            previous = {
                "stage": STAGE,
                "previous_source_commit": requirement.get("source_commit"),
                "previous_evidence_path": requirement.get("evidence_path"),
                "previous_artifact_hash": requirement.get("artifact_hash"),
            }
            if not history or history[-1] != previous:
                history.append(previous)
        records = [{"path": path, "sha256": sha256(ROOT / path)} for path in paths]
        records.append({"path": summary_rel, "sha256": summary_hash})
        requirement["artifact_hashes"] = records
        requirement["artifact_hash"] = records[0]["sha256"]
        requirement["test_id"] = TEST_ID
        requirement["evidence_path"] = summary_rel
        requirement["source_commit"] = summary["verified_source_commit"]
        requirement["reverification_stage"] = STAGE
    # The scheduler RTL change invalidates the old P10.3F artifact bundle.
    # Leave direct hardware requirements pending and return the artifact-bound
    # offline requirements to PENDING until a new clean build/freeze promotes
    # them through finalize_p10_3f_offline.py.
    for requirement_id in INVALIDATED_P10_3F_OFFLINE_REQUIREMENTS:
        requirement = by_id[requirement_id]
        requirement["status"] = "PENDING"
        requirement["artifact_hashes"] = []
        requirement.pop("artifact_hash", None)
    REQ_PATH.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
        newline="\n",
    )
    TRACE_PATH.write_text(render_traceability(document), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--update-requirements", action="store_true")
    args = parser.parse_args()
    if os.environ.get("NO_HARDWARE", "1") != "1":
        print("P10_P8D_REVERIFY_REFUSED: NO_HARDWARE=1 is required", file=sys.stderr)
        return 2
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_P8D_REVERIFY_REFUSED: CURRENT_RUN_HARDWARE_AUTHORIZATION=false is required", file=sys.stderr)
        return 2
    missing_tools = [str(path) for path in TOOLS.values() if not path.is_file()]
    if missing_tools:
        print("P10_P8D_REVERIFY_REFUSED: missing XSIM tools: " + ", ".join(missing_tools), file=sys.stderr)
        return 2
    source_paths = sorted(
        {path for spec in TESTS for path in spec["sources"]}
        | {path for paths in BOUND_ARTIFACTS.values() for path in paths}
        | {rel(Path(__file__).resolve())}
    )
    if not source_tree_is_clean(source_paths):
        print("P10_P8D_REVERIFY_REFUSED: bound source worktree is dirty", file=sys.stderr)
        return 2

    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    raw = OUT / "raw" / run_id
    raw.mkdir(parents=True, exist_ok=False)
    config_result = run_command(
        [sys.executable, "scripts/generate_p8d_data_plane_config.py", "--verify", "--json-summary"],
        ROOT,
        raw / "canonical_config.log",
        timeout=120,
    )
    simulations = [run_xsim(spec, raw) for spec in TESTS]
    airtime_json = raw / "airtime_sweep.json"
    airtime_csv = raw / "airtime_sweep.csv"
    airtime_result = run_command(
        [
            sys.executable,
            "scripts/model_p8d_airtime.py",
            "--json-summary",
            "--output-json",
            str(airtime_json),
            "--output-csv",
            str(airtime_csv),
        ],
        ROOT,
        raw / "airtime_model.log",
        timeout=600,
    )
    airtime_document = json.loads(airtime_json.read_text(encoding="utf-8")) \
        if airtime_json.is_file() else {}
    airtime = airtime_document.get("summary", airtime_document)
    airtime_pass = (
        airtime_result["returncode"] == 0
        and airtime.get("status") == "PASS"
        and airtime.get("8LANE_16MBPS_ARCHITECTURE_FEASIBILITY") == "PASS"
    )
    status = "PASS" if (
        config_result["returncode"] == 0
        and all(item["status"] == "PASS" for item in simulations)
        and airtime_pass
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
            "Refreshes only current-source P8D requirement bindings affected by the P10.3 retry "
            "path-diversity scheduler/config change. It does not promote hardware, rotation, P11, "
            "or final-product scope."
        ),
        "requirements": {
            "L2-ARQ-002": ["tb_ir_selective_repeat_tx", "tb_ir_data_plane_integration_2lane", "tb_ir_data_plane_integration_8lane"],
            "L2-SACK-001": ["tb_ir_sack_ack_aggregation", "canonical_config"],
            "L2-SACK-002": ["tb_ir_sack_ack_aggregation"],
            "L2-MIG-001": ["tb_ir_scheduler_migration"],
            "L2-RETRY-001": ["tb_ir_selective_repeat_tx", "tb_ir_scheduler_migration"],
            "SCHED-001": ["tb_ir_scheduler_migration", "tb_ir_data_plane_integration_2lane", "tb_ir_data_plane_integration_8lane"],
            "SCHED-002": ["tb_ir_scheduler_migration"],
            "SCHED-003": ["tb_ir_scheduler_migration"],
            "PERF-MODEL-001": ["airtime_model", "canonical_config"],
        },
        "invalidated_until_new_artifact_freeze": list(
            INVALIDATED_P10_3F_OFFLINE_REQUIREMENTS
        ),
        "bound_artifacts": [
            {"path": path, "sha256": sha256(ROOT / path)}
            for path in sorted({path for paths in BOUND_ARTIFACTS.values() for path in paths})
        ],
        "canonical_config": {key: value for key, value in config_result.items() if key not in ("stdout", "stderr")},
        "airtime_model": {
            "status": "PASS" if airtime_pass else "FAIL",
            "result": {key: value for key, value in airtime_result.items()
                       if key not in ("stdout", "stderr")},
            "summary": airtime,
            "json": rel(airtime_json) if airtime_json.is_file() else None,
            "csv": rel(airtime_csv) if airtime_csv.is_file() else None,
        },
        "simulations": simulations,
        "raw_run": rel(raw),
    }
    write_json(SUMMARY, summary)
    write_text(
        SUMMARY_MD,
        "\n".join([
            "# P10 P8D source-binding re-verification",
            "",
            f"- Status: `{status}`",
            f"- Verified source commit: `{source_commit}`",
            "- Hardware actions executed: `false`",
            "- Scope: refresh only current-source P8D bindings affected by the P10.3 retry path-diversity change; no hardware scope is promoted.",
            f"- Raw run: `{rel(raw)}`",
            "",
            "| Simulation | Result |",
            "|---|---|",
            *[f"| `{item['top']}` | `{item['status']}` |" for item in simulations],
            "",
        ]),
    )
    if status == "PASS" and args.update_requirements:
        update_requirements(summary)
    print(f"P10_P8D_SOURCE_REVERIFICATION={status}")
    print(f"P10_P8D_SOURCE_REVERIFICATION_SUMMARY={rel(SUMMARY)}")
    print(f"P10_P8D_REQUIREMENTS_UPDATED={1 if status == 'PASS' and args.update_requirements else 0}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
