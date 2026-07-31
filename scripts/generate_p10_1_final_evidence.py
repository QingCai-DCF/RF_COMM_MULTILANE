#!/usr/bin/env python3
"""Freeze P10.1 regression, evidence-consistency, and final summary evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from p10_1_common import (
    GENERATED,
    RAW,
    ROOT,
    evidence_base,
    load_json,
    rel,
    sha256,
    write_json,
    write_pair,
)


REGRESSION_COMMANDS = RAW / "p10_1_regression_commands.json"
MANIFEST = RAW / "p10_1_evidence_sha256_manifest.json"
REQUIRED_STEMS = [
    "p10_1_repo_intake",
    "p10_1_source_architecture_audit",
    "p10_1_measurement_contract",
    "p10_1_historical_recompute",
    "p10_1_finalizer_fix",
    "p10_1_timer_crosscheck",
    "p10_1_observability",
    "p10_1_autonomous_perf_mode",
    "p10_1_buffer_pipeline",
    "p10_1_descriptor_batching",
    "p10_1_streaming_64m",
    "p10_1_performance_model",
    "p10_1_host_native",
    "p10_1_xsim",
    "p10_1_fixed_build",
    "p10_1_rotating_build",
    "p10_1_software_build",
    "p10_1_hardware_dry_run",
    "p10_1_p11_readiness",
]
EXCLUDE_FROM_MANIFEST = {
    "p10_1_evidence_sha256_manifest.json",
    "p10_1_evidence_consistency.json",
    "p10_1_evidence_consistency.md",
    "p10_1_final_summary.json",
    "p10_1_final_summary.md",
}


def verify_hash_records(value: Any, errors: list[str], context: str) -> None:
    if isinstance(value, dict):
        if set(("path", "sha256")).issubset(value):
            path_value = value.get("path")
            digest = value.get("sha256")
            if isinstance(path_value, str) and isinstance(digest, str):
                path = (ROOT / path_value).resolve()
                try:
                    path.relative_to(ROOT.resolve())
                except ValueError:
                    return
                if not path.is_file():
                    errors.append(f"{context}: referenced path missing: {path_value}")
                elif sha256(path) != digest.lower():
                    errors.append(f"{context}: referenced SHA256 mismatch: {path_value}")
        for key, item in value.items():
            verify_hash_records(item, errors, f"{context}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            verify_hash_records(item, errors, f"{context}[{index}]")


def evidence_files() -> list[Path]:
    paths = [
        path
        for path in GENERATED.rglob("p10_1*")
        if path.is_file()
        and path.name not in EXCLUDE_FROM_MANIFEST
        and "xsim_work" not in path.parts
        and path.suffix.lower() not in {".exe", ".elf", ".map", ".wdb"}
    ]
    paths.extend(
        ROOT / name
        for name in (
            "config/performance/p10_1_measurement_contract.yaml",
            "config/performance/p10_1_pipeline.yaml",
            "config/performance/p10_1_streaming.yaml",
            "config/performance/p10_1_test_matrix.yaml",
            "config/register_map/ir_axi_regs.yaml",
            "config/project_state.json",
            "config/project_requirements.yaml",
            "PROJECT_STATUS.md",
            "docs/REQUIREMENT_TRACEABILITY_MATRIX.md",
        )
    )
    return sorted(set(path for path in paths if path.is_file()))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    if not REGRESSION_COMMANDS.is_file():
        errors.append("regression command ledger is missing")
        commands: list[dict[str, Any]] = []
    else:
        raw = load_json(REGRESSION_COMMANDS)
        commands = raw.get("commands", [])
        if not isinstance(commands, list):
            errors.append("regression command ledger is invalid")
            commands = []
    command_failures = [
        item.get("name", item.get("command", "unknown"))
        for item in commands
        if item.get("status") != "PASS"
    ]
    errors.extend(f"regression command failed: {name}" for name in command_failures)
    regression = evidence_base(
        "P10_1-OFFLINE-REGRESSION",
        status="PASS" if not errors else "FAIL",
        command_count=len(commands),
        commands=commands,
        baseline_rechecks={
            "P10": next(
                (item["status"] for item in commands if item.get("name") == "p10_verify_existing"),
                "MISSING",
            ),
            "P9": next(
                (item["status"] for item in commands if item.get("name") == "p9_verify_existing"),
                "MISSING",
            ),
            "P8E": next(
                (item["status"] for item in commands if item.get("name") == "p8e_verify_existing"),
                "MISSING",
            ),
            "P8C": next(
                (item["status"] for item in commands if item.get("name") == "p8c_verify_existing"),
                "MISSING",
            ),
        },
        raw_ledger={"path": rel(REGRESSION_COMMANDS), "sha256": sha256(REGRESSION_COMMANDS)}
        if REGRESSION_COMMANDS.is_file()
        else None,
        errors=errors.copy(),
    )
    write_pair("p10_1_regression", "P10.1 focused offline regression", regression)

    consistency_errors: list[str] = []
    evidence_payloads: dict[str, dict[str, Any]] = {}
    for stem in REQUIRED_STEMS:
        json_path = GENERATED / f"{stem}.json"
        md_path = GENERATED / f"{stem}.md"
        if not json_path.is_file():
            consistency_errors.append(f"missing {rel(json_path)}")
            continue
        if not md_path.is_file():
            consistency_errors.append(f"missing {rel(md_path)}")
        try:
            payload = load_json(json_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            consistency_errors.append(f"invalid {rel(json_path)}: {exc}")
            continue
        evidence_payloads[stem] = payload
        if payload.get("status") != "PASS":
            consistency_errors.append(f"{stem} status is not PASS")
        if payload.get("hardware_actions_executed") is not False:
            consistency_errors.append(f"{stem} does not prove zero hardware actions")
        if payload.get("current_run_hardware_authorization") is not False:
            consistency_errors.append(f"{stem} has non-false current authorization")
        verify_hash_records(payload, consistency_errors, stem)
    for stem in ("p10_1_regression",):
        payload = load_json(GENERATED / f"{stem}.json")
        evidence_payloads[stem] = payload
        if payload.get("status") != "PASS":
            consistency_errors.append(f"{stem} status is not PASS")
    state = load_json(ROOT / "config/project_state.json")
    if state.get("p10_1_offline_status") != "PASS":
        consistency_errors.append("canonical state does not record P10.1 offline PASS")
    if state.get("p10_1_hardware_status") != "PENDING_CURRENT_RUN_AUTHORIZATION":
        consistency_errors.append("P10.1 hardware status was promoted")
    if state.get("p11_status") != "NOT_STARTED" or state.get("p11_hardware_ready") is not False:
        consistency_errors.append("P11 status was promoted")
    files = evidence_files()
    manifest_payload = {
        "schema_version": 1,
        "file_count": len(files),
        "hardware_actions_executed": False,
        "files": [
            {
                "path": rel(path),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in files
        ],
    }
    write_json(MANIFEST, manifest_payload)
    consistency = evidence_base(
        "P10_1-EVIDENCE-CONSISTENCY",
        status="PASS" if not consistency_errors else "FAIL",
        required_pair_count=len(REQUIRED_STEMS) + 1,
        verified_stems=[*REQUIRED_STEMS, "p10_1_regression"],
        sha256_manifest={"path": rel(MANIFEST), "sha256": sha256(MANIFEST)},
        p10_1_hardware_status=state.get("p10_1_hardware_status"),
        p11_status=state.get("p11_status"),
        p11_hardware_ready=state.get("p11_hardware_ready"),
        errors=consistency_errors,
    )
    write_pair(
        "p10_1_evidence_consistency",
        "P10.1 evidence consistency",
        consistency,
    )

    model = evidence_payloads.get("p10_1_performance_model", {})
    stream = evidence_payloads.get("p10_1_streaming_64m", {})
    autonomous = evidence_payloads.get("p10_1_autonomous_perf_mode", {})
    descriptor = evidence_payloads.get("p10_1_descriptor_batching", {})
    build_fixed = evidence_payloads.get("p10_1_fixed_build", {})
    build_rotating = evidence_payloads.get("p10_1_rotating_build", {})
    dry_run = evidence_payloads.get("p10_1_hardware_dry_run", {})
    intake = evidence_payloads.get("p10_1_repo_intake", {})
    final_errors = errors + consistency_errors
    exit_gates = {
        "P10_BASELINE_RECHECK": regression["baseline_rechecks"]["P10"],
        "P10_AUTHORIZATION_CLOSED": "PASS"
        if state.get("current_run_hardware_authorization") is False
        and state.get("last_hardware_authorization_consumed") is True
        else "FAIL",
        "P10_PASS_TAG_IMMUTABLE": "PASS"
        if intake.get("p10_tags", {}).get("pass", {}).get("object_type") == "tag"
        else "FAIL",
        "P10_CLOSED_TAG_IMMUTABLE": "PASS"
        if intake.get("p10_tags", {}).get("closed", {}).get("object_type") == "tag"
        else "FAIL",
        "MEASUREMENT_CONTRACT": evidence_payloads.get("p10_1_measurement_contract", {}).get("status", "FAIL"),
        "HISTORICAL_RECOMPUTE": evidence_payloads.get("p10_1_historical_recompute", {}).get("status", "FAIL"),
        "GOODPUT_FINALIZER_FIX": evidence_payloads.get("p10_1_finalizer_fix", {}).get("status", "FAIL"),
        "DIAGNOSTIC_EXCLUSION": evidence_payloads.get("p10_1_finalizer_fix", {}).get("status", "FAIL"),
        "TIMER_CROSSCHECK": evidence_payloads.get("p10_1_timer_crosscheck", {}).get("status", "FAIL"),
        "PS_TRACE_RING": evidence_payloads.get("p10_1_observability", {}).get("status", "FAIL"),
        "PL_EVENT_FIFO": evidence_payloads.get("p10_1_observability", {}).get("status", "FAIL"),
        "COUNTER_SNAPSHOT": evidence_payloads.get("p10_1_observability", {}).get("status", "FAIL"),
        "BOARD_AUTONOMOUS_GENERATOR": autonomous.get("status", "FAIL"),
        "REMOTE_AUTONOMOUS_VERIFIER": autonomous.get("status", "FAIL"),
        "HOST_NOT_IN_FAST_PATH": "PASS" if autonomous.get("host_in_fast_path") is False else "FAIL",
        "MULTI_BUFFER_PIPELINE": evidence_payloads.get("p10_1_buffer_pipeline", {}).get("status", "FAIL"),
        "DESCRIPTOR_BATCHING": descriptor.get("status", "FAIL"),
        "CACHE_BATCHING_MODEL": descriptor.get("status", "FAIL"),
        "AXIS_SUSTAINED_NO_LOSS": evidence_payloads.get("p10_1_xsim", {}).get("status", "FAIL"),
        "STREAMING_64M_MODEL": stream.get("status", "FAIL"),
        "STREAM_ABORT_RESET_ATOMICITY": stream.get("status", "FAIL"),
        "DESCRIPTOR_LEAK_ZERO": "PASS" if stream.get("descriptor_leak_count") == 0 else "FAIL",
        "DOUBLE_COMPLETION_ZERO": "PASS" if stream.get("double_completion_count") == 0 else "FAIL",
        "P10_1_PERFORMANCE_MODEL": model.get("status", "FAIL"),
        "P10_1_4MBPS_SCALE_EQUIVALENT_FEASIBILITY": model.get("hard_target_status", "FAIL"),
        "AX7020_FIXED_BUILD": build_fixed.get("status", "FAIL"),
        "AX7020_ROTATING_BUILD": build_rotating.get("status", "FAIL"),
        "TIMING_CDC_DRC": "PASS"
        if build_fixed.get("timing_cdc_drc_reqp_status") == "PASS"
        and build_rotating.get("timing_cdc_drc_reqp_status") == "PASS"
        else "FAIL",
        "TFDU_SAFETY_REGRESSION": regression["baseline_rechecks"]["P8C"],
        "RESOURCE_LIMITS": "PASS"
        if build_fixed.get("resource_status") == "PASS"
        and build_rotating.get("resource_status") == "PASS"
        else "FAIL",
        "SOFTWARE_BUILD": evidence_payloads.get("p10_1_software_build", {}).get("status", "FAIL"),
        "HARDWARE_RUNNER_DRY_RUN": dry_run.get("status", "FAIL"),
        "NO_AUTH_FAIL_CLOSED": "PASS" if dry_run.get("no_authorization_fail_closed") is True else "FAIL",
        "P11_READINESS_PACKAGE": evidence_payloads.get("p10_1_p11_readiness", {}).get("status", "FAIL"),
        "OFFLINE_REGRESSION": regression.get("status", "FAIL"),
        "NO_HARDWARE_STATIC_SCAN": next(
            (item["status"] for item in commands if item.get("name") == "no_hardware_static_scan"),
            "FAIL",
        ),
        "EVIDENCE_CONSISTENCY": consistency.get("status", "FAIL"),
    }
    final_errors.extend(
        f"mandatory gate failed: {name}"
        for name, value in exit_gates.items()
        if value != "PASS"
    )
    final = evidence_base(
        "P10_1-FINAL-OFFLINE-CHECKPOINT",
        status="PASS" if not final_errors else "FAIL",
        base_main_commit="7863618197a9b3a9ad54469628de1cc0351b4ba7",
        branch="p10.1/performance-streaming-observability-offline",
        source_commit=state.get("p10_1_performance_and_observability", {}).get("source_commit"),
        exit_gates=exit_gates,
        historical_5p7k_fields="DIAGNOSTIC_MICROTRANSFER",
        modeled_application_goodput_bps=model.get("modeled_application_goodput_bps"),
        scale_equivalent_4mbps=model.get("hard_target_status"),
        stretch_4p8mbps=model.get("stretch_target_status"),
        primary_modeled_bottleneck=model.get("primary_modeled_bottleneck"),
        required_buffer_count=model.get("required_buffer_count"),
        required_ring_depth=model.get("required_ring_depth"),
        required_descriptor_batch=model.get("required_descriptor_batch"),
        optional_128m_status=stream.get("optional_128m", {}).get("status"),
        p11_hardware_ready=False,
        p11_missing_prerequisites=evidence_payloads.get("p10_1_p11_readiness", {}).get("missing_prerequisites", []),
        no_hardware_actions_executed=True,
        sha256_manifest={"path": rel(MANIFEST), "sha256": sha256(MANIFEST)},
        generated_evidence=[
            f"evidence/generated/{stem}.json"
            for stem in [
                *REQUIRED_STEMS,
                "p10_1_regression",
                "p10_1_evidence_consistency",
                "p10_1_final_summary",
            ]
        ],
        next_recommended_stage="P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE_ONLY_AFTER_NEW_AUTHORIZATION",
        errors=final_errors,
    )
    write_pair(
        "p10_1_final_summary",
        "P10.1 extended offline performance checkpoint",
        final,
    )
    print(f"P10_1_FINAL_SUMMARY={final['status']}")
    print(f"P10_1_EVIDENCE_CONSISTENCY={consistency['status']}")
    if args.json_summary:
        print(json.dumps(final, sort_keys=True))
    return 0 if final["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
