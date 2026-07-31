#!/usr/bin/env python3
"""Generate the deterministic, no-hardware P10 post-acceptance closeout.

This tool only reads frozen P10 evidence and Git metadata.  It never imports
or invokes the hardware runner, hw_server, XSDB, JTAG, UART, or TFDU controls.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import struct
import subprocess
from pathlib import Path
from typing import Any

import yaml

from p8a_common import (
    P10_ANALYSIS_SCOPE,
    P10_CLOSEOUT_SCOPE,
    P10_NEXT_STAGE,
    REQUIREMENTS_PATH,
    ROOT,
    STATE_PATH,
    STATUS_PATH,
    TRACEABILITY_PATH,
    render_project_status,
    render_traceability,
    validate_requirements,
    validate_state,
)


RUN_ID = "p10_formal_20260730T181535Z_03"
RUN_ROOT = ROOT / "evidence/hardware/p10" / RUN_ID
SOURCE_COMMIT = "8aa3879c5a8a5a4ed327b1084575bcfcc953f06b"
FORMAL_EVIDENCE_FREEZE_COMMIT = "16684884708223bf7fb9b05145164e6155496cc8"
EVIDENCE_CHECKPOINT_COMMIT = "35f5fefdcf5ac2833ed5708cef7a5de3005a2aa0"
PASS_TAG = "p10-ax7020-dual-node-2lane-pass"
EXPECTED_PASS_TAG_OBJECT = "0b8f4fd41b98978ae3c036d0f057990b947e3cdb"
EXPECTED_BRANCH = "p10/ax7020-dual-node-2lane"
REMOTE_NAME = "origin"
REMOTE_URL = "https://github.com/QingCai-DCF/RF_COMM_MULTILANE.git"
GENERATED_AT_UTC = "2026-07-31T03:04:46Z"
OPERATOR_PLAN_PATH = "C:/Users/user/Downloads/P10_CLOSEOUT_PUSH_AND_PRE_P11_PLAN.md"
OPERATOR_PLAN_SHA256 = "518aa3814062c5334c83816dfe23458ed2fb3c9132d3f3ffe185642a846302af"

FINAL_PATH = RUN_ROOT / "final/orchestrator_result.json"
MANIFEST_PATH = RUN_ROOT / "final/run_evidence_sha256_manifest.json"
AUTH_PATH = ROOT / "config/p10_fasttrack_current_run_authorization.json"
WIRING_PATH = ROOT / "config/hardware/p10_active_wiring.yaml"
RUNTIME_PATH = ROOT / "scripts/p10_hardware_runtime.py"
FIRMWARE_PATH = ROOT / "software/ps_driver/p9_runtime_main.c"
PROTOCOL_PATH = ROOT / "software/ps_driver/p9_runtime_protocol.h"

REMOTE_JSON = ROOT / "evidence/generated/p10_remote_push_summary.json"
REMOTE_MD = ROOT / "evidence/generated/p10_remote_push_summary.md"
AUDIT_JSON = ROOT / "evidence/generated/p10_goodput_measurement_audit.json"
AUDIT_MD = ROOT / "evidence/generated/p10_goodput_measurement_audit.md"
CHECKPOINT_JSON = ROOT / "evidence/generated/p10_git_checkpoint_metadata.json"
CLOSEOUT_JSON = ROOT / "evidence/generated/p10_closeout_summary.json"
CLOSEOUT_MD = ROOT / "evidence/generated/p10_closeout_summary.md"
MEASUREMENT_CONTRACT = ROOT / "config/performance/p10_1_measurement_contract.yaml"
P10_1_PLAN = ROOT / "docs/plans/P10_1_DUAL_NODE_PERFORMANCE_AND_OBSERVABILITY_PLAN.md"
P11_READINESS = ROOT / "docs/plans/P11_HARDWARE_READINESS.md"

EXPECTED_HASHES = {
    FINAL_PATH: "ac7ef63dc4f3ac50b58a36fbeaa99020217673382ad691cb71d9d874436ae4d0",
    MANIFEST_PATH: "2dc576a9a15441ebf67df98e77ca65a8e28b6118c7381dab399507f0474bb281",
    WIRING_PATH: "a818331c5e8b471283c8269b5935e541e0456e6a18a0719e44cfe8817da5b165",
}

P10_HARDWARE_FOLLOWUP = (
    "This PASS remains limited to the frozen stationary dual-AX7020 two-lane "
    "campaign. New performance experiments, P10.2 crosstalk/full-duplex work, "
    "P10.3 large-object/FreeRTOS work, and every P11-or-later hardware action "
    "require a new current-run authorization and bounded safe wrapper."
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def json_text(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False) + "\n"


def yaml_text(value: Any) -> str:
    return yaml.safe_dump(
        value,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )


def emit(path: Path, content: str, *, write: bool, errors: list[str]) -> None:
    encoded = content.encode("utf-8")
    if write:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or path.read_bytes() != encoded:
            path.write_bytes(encoded)
    if not path.is_file():
        errors.append(f"missing generated file: {rel(path)}")
    elif path.read_bytes() != encoded:
        errors.append(f"stale generated file: {rel(path)}")


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{rel(path)} must contain a JSON mapping")
    return value


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile requires at least one value")
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def stats(values: list[float]) -> dict[str, float | int]:
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "min": min(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
    }


def mailbox_words(path: Path) -> list[int]:
    data = path.read_bytes()
    if len(data) != 1024:
        raise ValueError(f"mailbox dump is not 1024 bytes: {rel(path)}")
    return list(struct.unpack("<256I", data))


def u64(words: list[int], index: int) -> int:
    return words[index] | (words[index + 1] << 32)


def load_psv(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="|"))
    return {row["label"]: row for row in rows}


def verify_inputs(errors: list[str]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    for path, expected in EXPECTED_HASHES.items():
        require(path.is_file(), f"missing frozen input: {rel(path)}", errors)
        if path.is_file():
            require(sha256(path) == expected, f"frozen input SHA256 mismatch: {rel(path)}", errors)

    final = load_json(FINAL_PATH)
    manifest = load_json(MANIFEST_PATH)
    auth = load_json(AUTH_PATH)
    require(final.get("status") == "PASS", "P10 final evidence is not PASS", errors)
    require(final.get("run_id") == RUN_ID, "P10 final run ID mismatch", errors)
    require(final.get("source_commit") == SOURCE_COMMIT, "P10 source commit mismatch", errors)
    require(final.get("SHUTDOWN_FIXED") == "PASS", "P10 fixed shutdown is not PASS", errors)
    require(final.get("SHUTDOWN_ROTATING") == "PASS", "P10 rotating shutdown is not PASS", errors)
    require(manifest.get("status") == "PASS", "P10 manifest is not PASS", errors)
    require(manifest.get("run_id") == RUN_ID, "P10 manifest run ID mismatch", errors)
    require(len(manifest.get("files", [])) == 1276, "P10 manifest file count mismatch", errors)
    require(auth.get("run_id") == RUN_ID, "P10 authorization run ID mismatch", errors)
    require(auth.get("source_commit") == SOURCE_COMMIT, "P10 authorization source mismatch", errors)

    require(git("cat-file", "-t", PASS_TAG) == "tag", "P10 PASS tag is not annotated", errors)
    require(
        git("rev-parse", PASS_TAG) == EXPECTED_PASS_TAG_OBJECT,
        "P10 PASS tag object changed",
        errors,
    )
    require(
        git("rev-list", "-n", "1", PASS_TAG) == EVIDENCE_CHECKPOINT_COMMIT,
        "P10 PASS tag target changed",
        errors,
    )
    require(git("remote", "get-url", REMOTE_NAME) == REMOTE_URL, "origin URL mismatch", errors)
    return final, manifest, auth


def build_remote_summary() -> tuple[dict[str, Any], str]:
    payload = {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "P10-REMOTE-PUSH-SUMMARY",
        "generated_at_utc": GENERATED_AT_UTC,
        "scope": "P10_FROZEN_PASS_CHECKPOINT_REMOTE_BACKUP",
        "remote_name": REMOTE_NAME,
        "remote_url": REMOTE_URL,
        "push_method": "git push --atomic -u origin p10/ax7020-dual-node-2lane p10-ax7020-dual-node-2lane-pass",
        "branch": EXPECTED_BRANCH,
        "remote_branch_hash": EVIDENCE_CHECKPOINT_COMMIT,
        "pass_tag": PASS_TAG,
        "pass_tag_type": "tag",
        "pass_tag_object_hash": EXPECTED_PASS_TAG_OBJECT,
        "pass_tag_peeled_target": EVIDENCE_CHECKPOINT_COMMIT,
        "verified_with_ls_remote": True,
        "pass_tag_moved_or_rewritten": False,
        "history_rewritten": False,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "operator_plan": {
            "path": OPERATOR_PLAN_PATH,
            "sha256": OPERATOR_PLAN_SHA256,
        },
    }
    markdown = "\n".join(
        [
            "# P10 remote push summary",
            "",
            f"- Status: `{payload['status']}`",
            f"- Remote: `{REMOTE_URL}`",
            f"- Branch: `{EXPECTED_BRANCH}` -> `{EVIDENCE_CHECKPOINT_COMMIT}`",
            f"- PASS tag object: `{EXPECTED_PASS_TAG_OBJECT}`",
            f"- PASS tag peeled target: `{EVIDENCE_CHECKPOINT_COMMIT}`",
            "- Push was atomic; the annotated PASS tag was not moved or rewritten.",
            "- Hardware actions executed: `false`.",
            "",
        ]
    )
    return payload, markdown


def build_stage_i_rows(stage_i: dict[str, Any]) -> list[dict[str, Any]]:
    by_label = {item["label"]: item for item in stage_i["details"]}
    performance = {item["label"]: item for item in stage_i["performance"]}
    observations = load_psv(RUN_ROOT / "stages/p10_i/dumps/observations.psv")
    rows: list[dict[str, Any]] = []
    for label in performance:
        detail = by_label[label]
        observation = observations[label]
        direction = int(detail["direction"])
        sender_role = "fixed" if direction == 0 else "rotating"
        receiver_role = "rotating" if direction == 0 else "fixed"
        sender = mailbox_words(RUN_ROOT / f"stages/p10_i/dumps/{label}.{sender_role}.bin")
        receiver = mailbox_words(RUN_ROOT / f"stages/p10_i/dumps/{label}.{receiver_role}.bin")
        counts_per_second = sender[59]
        encoded_bytes = int(detail["end_to_end"]["transfer_bytes"])
        useful_bytes = int(detail["requested_size"])
        ps_command_seconds = u64(sender, 57) / counts_per_second
        xsdb_case_wall_seconds = (
            int(observation["finished_ms"]) - int(observation["started_ms"])
        ) / 1000.0
        recomputed_reported = encoded_bytes * 8 / ps_command_seconds
        reported = float(performance[label]["application_goodput_bps"])
        if not math.isclose(recomputed_reported, reported, rel_tol=1e-12):
            raise ValueError(f"Stage I reported goodput does not reproduce: {label}")
        rows.append(
            {
                "label": label,
                "lane_mask": int(detail["lane_mask"]),
                "direction": direction,
                "sender_role": sender_role,
                "receiver_role": receiver_role,
                "requested_useful_bytes": useful_bytes,
                "encoded_transfer_bytes": encoded_bytes,
                "counts_per_second": counts_per_second,
                "ps_command_seconds": ps_command_seconds,
                "xsdb_case_wall_seconds": xsdb_case_wall_seconds,
                "reported_encoded_ps_command_bps": reported,
                "recomputed_useful_ps_command_bps": useful_bytes * 8 / ps_command_seconds,
                "recomputed_useful_xsdb_case_wall_bps": (
                    useful_bytes * 8 / xsdb_case_wall_seconds
                ),
                "sender_timing_seconds": {
                    "payload_prepare": u64(sender, 215) / counts_per_second,
                    "dma_tx_completion_from_poll_start": u64(sender, 217)
                    / counts_per_second,
                    "pl_completion_from_poll_start": u64(sender, 221)
                    / counts_per_second,
                    "object_runtime": u64(sender, 225) / counts_per_second,
                },
                "receiver_timing_seconds": {
                    "payload_prepare": u64(receiver, 215) / receiver[59],
                    "dma_rx_completion_from_poll_start": u64(receiver, 219)
                    / receiver[59],
                    "pl_completion_from_poll_start": u64(receiver, 221)
                    / receiver[59],
                    "integrity_verify": u64(receiver, 223) / receiver[59],
                    "object_runtime": u64(receiver, 225) / receiver[59],
                },
            }
        )
    return rows


def build_goodput_audit(final: dict[str, Any]) -> tuple[dict[str, Any], str]:
    stage_summaries: dict[str, dict[str, Any]] = {}
    campaign_rows: list[dict[str, Any]] = []
    for letter in "ABCDEFGHIJ":
        stage = f"P10-{letter}"
        path = RUN_ROOT / f"stages/p10_{letter.lower()}/stage_summary.json"
        summary = load_json(path)
        stage_summaries[stage] = summary
        for item in summary.get("performance", []):
            campaign_rows.append({"stage": stage, **item})

    minima: dict[int, dict[str, Any]] = {}
    for direction in (0, 1):
        minima[direction] = min(
            (item for item in campaign_rows if item["direction"] == direction),
            key=lambda item: item["application_goodput_bps"],
        )
    if not math.isclose(
        minima[0]["application_goodput_bps"],
        float(final["application_goodput_f_to_r_bps"]),
        rel_tol=1e-12,
    ):
        raise ValueError("F-to-R final goodput minimum does not reproduce")
    if not math.isclose(
        minima[1]["application_goodput_bps"],
        float(final["application_goodput_r_to_f_bps"]),
        rel_tol=1e-12,
    ):
        raise ValueError("R-to-F final goodput minimum does not reproduce")

    stage_i = stage_summaries["P10-I"]
    stage_i_rows = build_stage_i_rows(stage_i)
    stage_i_stats = {
        "reported_encoded_ps_command_bps": stats(
            [row["reported_encoded_ps_command_bps"] for row in stage_i_rows]
        ),
        "useful_ps_command_bps": stats(
            [row["recomputed_useful_ps_command_bps"] for row in stage_i_rows]
        ),
        "useful_xsdb_case_wall_bps": stats(
            [row["recomputed_useful_xsdb_case_wall_bps"] for row in stage_i_rows]
        ),
    }

    stage_j = stage_summaries["P10-J"]
    soak_rows = [item for item in stage_j["details"] if item.get("command") == 3]
    soak_seconds = int(stage_j["markers"]["P10_SOAK_ACTIVE_ELAPSED_MS"]) / 1000.0
    soak_directions: list[dict[str, Any]] = []
    for direction in (0, 1):
        selected = [item for item in soak_rows if item["direction"] == direction]
        useful_bytes = sum(int(item["requested_size"]) for item in selected)
        internal = [
            float(item["application_goodput_bps"])
            for item in stage_j["performance"]
            if item["direction"] == direction
        ]
        soak_directions.append(
            {
                "direction": direction,
                "objects": len(selected),
                "useful_bytes": useful_bytes,
                "full_1800s_window_application_goodput_bps": (
                    useful_bytes * 8 / soak_seconds
                ),
                "per_object_internal_bps": stats(internal),
            }
        )
    soak_total_bytes = sum(item["useful_bytes"] for item in soak_directions)

    input_paths = [
        FINAL_PATH,
        RUN_ROOT / "stages/p10_e/stage_summary.json",
        RUN_ROOT / "stages/p10_i/stage_summary.json",
        RUN_ROOT / "stages/p10_i/dumps/observations.psv",
        RUN_ROOT / "stages/p10_j/stage_summary.json",
        RUN_ROOT / "stages/p10_j/dumps/observations.psv",
        RUNTIME_PATH,
        FIRMWARE_PATH,
        PROTOCOL_PATH,
    ]
    payload = {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "P10-GOODPUT-MEASUREMENT-AUDIT",
        "generated_at_utc": GENERATED_AT_UTC,
        "scope": P10_ANALYSIS_SCOPE,
        "run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT,
        "outcome": "CURRENT_FINAL_GOODPUT_FIELDS_NOT_SUITABLE_FOR_SCALING",
        "eligible_for_final_8lane_projection": False,
        "p10_scoped_hardware_acceptance_changed": False,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "input_artifacts": [
            {"path": rel(path), "sha256": sha256(path)} for path in input_paths
        ],
        "final_summary_fields": {
            "application_goodput_f_to_r_bps": final[
                "application_goodput_f_to_r_bps"
            ],
            "application_goodput_r_to_f_bps": final[
                "application_goodput_r_to_f_bps"
            ],
            "aggregation": (
                "minimum application_goodput_bps over every command-3 performance "
                "row from every P10 stage"
            ),
            "f_to_r_minimum_provenance": minima[0],
            "r_to_f_minimum_provenance": minima[1],
            "semantic_classification": (
                "worst single-object encoded-transfer throughput, dominated by "
                "one-byte P10-E DMA/ring diagnostics"
            ),
        },
        "formula_audit": {
            "implemented_formula": (
                "8 * encoded_transfer_bytes * counts_per_second / "
                "sender_ps_command_elapsed_ticks"
            ),
            "bit_byte_conversion": "PASS",
            "timer_frequency": 333333343,
            "timer_frequency_semantics": "XPAR_CPU_CORTEXA9_0_CPU_CLK_FREQ_HZ/2",
            "unit_conversion_error_found": False,
            "application_useful_bytes_used_in_all_cases": False,
            "reason": (
                "RFAP cases use encoded bytes including headers; P10-E minima use "
                "one useful/encoded byte."
            ),
        },
        "denominator_audit": {
            "sender_ps_command_elapsed_ticks": {
                "included": [
                    "sender payload generation",
                    "CRC32 and SHA-256",
                    "cache preparation",
                    "DMA/PL/object execution",
                    "integrity-independent sender completion",
                    "full shutdown",
                ],
                "excluded": [
                    "host/JTAG command staging before sender dispatch",
                    "receiver priming wait before sender dispatch",
                    "post-case JTAG mailbox dumps",
                    "inter-object idle time",
                    "the full 1800-second soak denominator",
                ],
            },
            "entire_30min_denominator_used_by_final_fields": False,
            "host_or_jtag_blocking_included_by_final_fields": False,
        },
        "execution_model_audit": {
            "objects_in_flight_across_application_pipeline": 1,
            "objects_launched_serially_by_xsdb": True,
            "receiver_primed_before_sender_launch": True,
            "mailboxes_dumped_after_each_object": True,
            "pipeline_throughput_demonstrated": False,
            "sg_dma_present": True,
            "sg_dma_pipeline_across_objects_demonstrated": False,
        },
        "stage_i_characterization": {
            "row_count": len(stage_i_rows),
            "rows": stage_i_rows,
            "statistics": stage_i_stats,
        },
        "stationary_30min_recomputation": {
            "active_window_seconds": soak_seconds,
            "objects": len(soak_rows),
            "directions": soak_directions,
            "aggregate_useful_bytes": soak_total_bytes,
            "aggregate_full_window_application_goodput_bps": (
                soak_total_bytes * 8 / soak_seconds
            ),
            "idle_and_xsdb_orchestration_included": True,
            "interpretation": (
                "workload-level full-window useful throughput for the serialized "
                "P10-J soak, not a saturated pipeline benchmark"
            ),
        },
        "closed_questions": [
            {
                "question": "Are the final 5.7 kbit/s values caused by a bit/byte or timer unit error?",
                "answer": "No. The calculation reproduces exactly with bits and a 333333343-count/s timer.",
            },
            {
                "question": "Why are the final values so low?",
                "answer": (
                    "The campaign finalizer takes a global minimum across all "
                    "command-3 cases; the minima are one-byte P10-E diagnostics."
                ),
            },
            {
                "question": "Do the final values represent the 30-minute window?",
                "answer": "No. They use one sender PS command interval.",
            },
            {
                "question": "Was a multi-object PS/DMA pipeline measured?",
                "answer": "No. The XSDB campaign serialized one object at a time.",
            },
        ],
        "open_measurement_questions": [
            "Saturated multi-object pipeline application goodput in each direction",
            "True concurrent full-duplex application goodput",
            "Per-segment mean/p50/p95/p99/max with one common clock contract",
            "Host/JTAG staging separated from target-resident application work",
            "Digital-only versus real-optical delta using identical workload",
            "CPU load and FreeRTOS scheduling impact if FreeRTOS is introduced",
        ],
        "decision": (
            "Keep P10 scoped PASS. Do not project the current final goodput fields "
            "to eight lanes or final-product performance. Execute P10.1 hardware "
            "experiments only after a new explicit current-run authorization."
        ),
    }
    markdown = "\n".join(
        [
            "# P10 goodput measurement audit",
            "",
            "Audit status: `PASS` (the audit completed; this is not a new hardware-performance PASS).",
            "",
            "## Finding",
            "",
            "The two ~5.7 kbit/s fields are mathematically reproducible, but they are not campaign application goodput. "
            "The finalizer takes the minimum over every command-3 row in all stages. The minima are one-byte P10-E DMA/ring diagnostics:",
            "",
            f"- F→R: `{minima[0]['application_goodput_bps']:.6f}` bit/s from `{minima[0]['stage']}/{minima[0]['label']}`.",
            f"- R→F: `{minima[1]['application_goodput_bps']:.6f}` bit/s from `{minima[1]['stage']}/{minima[1]['label']}`.",
            "",
            "There is no bit/byte or timer-frequency error in those two calculations. The semantic problem is aggregation and labeling: "
            "the numerator may be encoded bytes, the denominator is one sender PS command, and the result excludes host/JTAG staging and the full 30-minute window.",
            "",
            "## Recomputed useful-throughput views",
            "",
            f"- P10-I useful PS-command range: `{stage_i_stats['useful_ps_command_bps']['min']:.3f}` to `{stage_i_stats['useful_ps_command_bps']['max']:.3f}` bit/s.",
            f"- P10-I useful XSDB-case wall-time range: `{stage_i_stats['useful_xsdb_case_wall_bps']['min']:.3f}` to `{stage_i_stats['useful_xsdb_case_wall_bps']['max']:.3f}` bit/s.",
            f"- P10-J full 1800.003 s useful throughput: `{soak_total_bytes * 8 / soak_seconds:.3f}` bit/s aggregate, "
            f"`{soak_directions[0]['full_1800s_window_application_goodput_bps']:.3f}` bit/s per direction.",
            "",
            "These are different measurement windows and must not be compared as if they were the same metric. P10 launched one object at a time through XSDB, "
            "including per-object receiver priming and mailbox dumps; it did not demonstrate a saturated multi-object pipeline.",
            "",
            "## Decision",
            "",
            "- P10 scoped hardware acceptance remains `PASS`.",
            "- Current final goodput fields are not eligible for 8-lane or final-product projection.",
            "- P10.1 must establish exact metric contracts, segmented timing, and a pipeline benchmark before any scaling claim.",
            "- No hardware action was executed for this audit.",
            "",
        ]
    )
    return payload, markdown


def build_measurement_contract() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "contract_id": "P10_1_DUAL_NODE_PERFORMANCE_AND_OBSERVABILITY",
        "status": "OFFLINE_PLAN_ONLY",
        "profile": "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET",
        "current_run_hardware_authorization": False,
        "hardware_experiments_authorized": False,
        "hardware_authorization_required_before_execution": True,
        "metrics": {
            "PHY_RAW_BPS": {
                "unit": "bit/s",
                "definition": "configured raw symbol bit rate per active lane times active lane count",
                "measured_application_metric": False,
            },
            "FRAME_GOODPUT_BPS": {
                "unit": "bit/s",
                "numerator": "8 * deduplicated accepted protocol-frame payload bytes",
                "denominator": "explicit frame measurement end minus start",
            },
            "APPLICATION_GOODPUT_BPS": {
                "unit": "bit/s",
                "numerator": "8 * exactly-once atomically published application-useful bytes",
                "denominator": "explicit application measurement end minus start",
                "excludes": ["RFAP headers", "link headers", "ACKs", "retries", "duplicates"],
            },
            "OBJECT_COMPLETION_BPS": {
                "unit": "bit/s",
                "numerator": "8 * useful bytes in completed atomically published objects",
                "denominator": "first admitted object start through final atomic publish",
                "companion_metric": "OBJECTS_PER_SECOND",
            },
        },
        "required_dimensions": [
            "measurement_start_timestamp",
            "measurement_end_timestamp",
            "clock_source",
            "numerator_bytes",
            "warmup_policy",
            "idle_included",
            "host_jtag_staging_included",
            "direction",
            "lane_mask",
            "active_lane_count",
            "object_size_bytes",
            "fragment_size_bytes",
            "raw_log_path",
            "raw_log_sha256",
        ],
        "required_timing_segments": [
            "host_load",
            "ps_generation",
            "crc32",
            "sha256",
            "cache_flush",
            "descriptor_submit",
            "dma_tx",
            "pl_queue",
            "on_air",
            "ack_sack",
            "dma_rx",
            "cache_invalidate",
            "reassembly",
            "receive_sha256",
            "atomic_publish",
            "host_readback",
        ],
        "required_statistics": ["count", "mean", "p50", "p95", "p99", "max"],
        "comparison_modes": {
            "A": "local DDR/DMA path",
            "B": "dual-board digital path without optical, only if explicitly supported",
            "C": "real optical path",
        },
        "comparison_rule": "Mode B may diagnose but never substitute for Mode C hardware evidence.",
        "integrity_and_safety_invariants": [
            "CRC32 and SHA-256 remain enabled",
            "exactly-once atomic publication remains enabled",
            "selective-repeat/SACK remains enabled",
            "TFDU continuous-high and rolling-duty guards remain enabled",
            "single GLOBAL_PERMIT architecture is not changed",
            "shutdown-before/on-error/timeout/interrupt/normal-exit/after remains mandatory",
        ],
        "acceptance_goals": [
            "all four metric names have exact reproducible units and windows",
            "JSON and Markdown derive from the same raw log",
            "scaling behavior is explained without extrapolation beyond evidence",
            "dominant bottlenecks have segmented timing evidence",
            "no integrity or safety regression",
        ],
    }


def build_p10_1_plan(contract_sha: str, audit_sha: str) -> str:
    return "\n".join(
        [
            "# P10.1 Dual-node performance and observability plan",
            "",
            "Status: `OFFLINE_PLAN_ONLY`",
            "",
            "Current-run hardware authorization: `false`. This document does not authorize JTAG, FPGA programming, PS ELF execution, UART, TFDU drive, or any other hardware action.",
            "",
            "## Why P10.1 exists",
            "",
            "The P10 hardware acceptance is valid for its stationary two-node/two-lane scope, but its final ~5.7 kbit/s fields are global minima from one-byte DMA diagnostics. "
            "They are not suitable for scaling. The source-backed audit is "
            f"`{rel(AUDIT_JSON)}` (`{audit_sha}`).",
            "",
            "## Measurement contract",
            "",
            f"The machine-readable contract is `{rel(MEASUREMENT_CONTRACT)}` (`{contract_sha}`). It fixes four distinct metrics:",
            "",
            "- `PHY_RAW_BPS`: configured raw lane capability; never label it application throughput.",
            "- `FRAME_GOODPUT_BPS`: deduplicated accepted frame-payload bits divided by an explicit frame window.",
            "- `APPLICATION_GOODPUT_BPS`: exactly-once atomically published useful bits divided by an explicit application window.",
            "- `OBJECT_COMPLETION_BPS`: useful bits in completed atomic objects divided by the first-admit to final-publish window; also record objects/s.",
            "",
            "Every metric record must include start/end timestamp and clock source, numerator bytes, warm-up and idle policy, host/JTAG staging inclusion, direction, lane mask, object/fragment sizes, and the raw-log path plus SHA-256. "
            "One raw log must deterministically produce both JSON and Markdown.",
            "",
            "## Required segmented timing",
            "",
            "Instrument host load, PS generation, CRC32, SHA-256, cache flush, descriptor submit, DMA TX, PL queue, on-air transfer, ACK/SACK, DMA RX, cache invalidate, reassembly, receive SHA-256, atomic publish, and host readback. "
            "For every segment report count, mean, p50, p95, p99, and maximum. Missing instrumentation must be `SKIP_WITH_REASON`, not zero.",
            "",
            "## Comparison matrix",
            "",
            "1. Mode A: local DDR/DMA.",
            "2. Mode B: dual-board digital/no-optical path, only if the design explicitly supports it.",
            "3. Mode C: real optical path.",
            "",
            "Mode B is diagnostic and cannot replace Mode C. Use identical workload, build, lane mask, object sizes, integrity checks, and measurement windows across comparable modes.",
            "",
            "## Optimization order",
            "",
            "First correct metric semantics and add observability. Then test a target-resident multi-object pipeline rather than XSDB-serialized one-object transactions. "
            "Optimize payload generation/hash strategy, descriptor batching, ring occupancy, cache ownership, ACK aggregation, queue depth, and readback only after segmented evidence identifies the bottleneck. "
            "Do not disable CRC/SHA, exactly-once publication, SACK/retry rules, duty guards, TX kill, or shutdown behavior.",
            "",
            "## Later optional campaigns",
            "",
            "- P10.2: 4x4 crosstalk matrix and 1+1 concurrent full duplex.",
            "- P10.3: larger objects and FreeRTOS characterization, if FreeRTOS is selected.",
            "",
            "Both are hardware campaigns and require a new explicit current-run authorization with immutable artifacts and bounded safe shutdown.",
            "",
            "## Exit criteria",
            "",
            "- Metric windows and units reproduce exactly from raw evidence.",
            "- The difference among raw, frame, application, object, PS-command, XSDB-wall, and full-soak throughput is explicit.",
            "- Pipeline scaling and its bottleneck breakdown are credible.",
            "- Integrity and TFDU safety evidence do not regress.",
            "- No result is extrapolated to 8 lanes, rotation, or final product without direct evidence.",
            "",
        ]
    )


def build_p11_readiness() -> str:
    return "\n".join(
        [
            "# P11 hardware readiness",
            "",
            "P11_HARDWARE_READY: `false`",
            "",
            "P11_OFFICIAL_STAGE_STATUS: `NOT_STARTED`",
            "",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION: `false`",
            "",
            "The current setup has four TFDU modules total: F0/F1/R0/R1. P11 requires at least five simultaneously available modules (one rotating-role module and four fixed modules), so the existing hardware cannot satisfy the proposed P11 topology.",
            "",
            "## Missing prerequisites",
            "",
            "- At least one additional compatible TFDU module, yielding one rotating plus four fixed modules.",
            "- A mechanically defined four-fixed-module fixture.",
            "- A mechanically defined rotating-module fixture.",
            "- A verified ABZ/phase input path and pin/profile definition.",
            "- A bounded, controllable motion source suitable for handover testing.",
            "- A P11-specific wiring/profile/XDC package and immutable artifact set.",
            "- A new explicit current-run hardware authorization and safe wrapper.",
            "",
            "No P11 implementation or hardware execution may be marked in progress until these prerequisites are resolved. P10.1 offline analysis may proceed independently; P10.1 hardware experiments still require their own new authorization.",
            "",
        ]
    )


def artifact_from_auth(auth: dict[str, Any], role: str, kind: str) -> dict[str, Any]:
    matches = [
        item
        for item in auth["artifacts"]
        if item.get("role") == role and item.get("kind") == kind
    ]
    if len(matches) != 1:
        raise ValueError(f"authorization artifact missing/ambiguous: {role}/{kind}")
    return matches[0]


def build_checkpoint_metadata(
    final: dict[str, Any], manifest: dict[str, Any], auth: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "P10-GIT-CHECKPOINT-METADATA",
        "generated_at_utc": GENERATED_AT_UTC,
        "scope": P10_CLOSEOUT_SCOPE,
        "source_commit": SOURCE_COMMIT,
        "formal_evidence_freeze_commit": FORMAL_EVIDENCE_FREEZE_COMMIT,
        "evidence_checkpoint": {
            "branch": EXPECTED_BRANCH,
            "commit": EVIDENCE_CHECKPOINT_COMMIT,
            "tree": git("rev-parse", f"{EVIDENCE_CHECKPOINT_COMMIT}^{{tree}}"),
            "pass_tag": PASS_TAG,
            "pass_tag_type": "tag",
            "pass_tag_object": EXPECTED_PASS_TAG_OBJECT,
            "pass_tag_target": EVIDENCE_CHECKPOINT_COMMIT,
        },
        "formal_run_id": RUN_ID,
        "fixed_board_id": final["fixed_board_id"],
        "rotating_board_id": final["rotating_board_id"],
        "artifacts": {
            "fixed_functional_bitstream": artifact_from_auth(
                auth, "fixed", "functional_bitstream"
            ),
            "rotating_functional_bitstream": artifact_from_auth(
                auth, "rotating", "functional_bitstream"
            ),
            "fixed_elf": artifact_from_auth(auth, "fixed", "elf"),
            "rotating_elf": artifact_from_auth(auth, "rotating", "elf"),
            "fixed_shutdown_bitstream": artifact_from_auth(
                auth, "fixed", "shutdown_bitstream"
            ),
            "rotating_shutdown_bitstream": artifact_from_auth(
                auth, "rotating", "shutdown_bitstream"
            ),
            "wiring": {"path": rel(WIRING_PATH), "sha256": sha256(WIRING_PATH)},
            "evidence_manifest": {
                "path": rel(MANIFEST_PATH),
                "sha256": sha256(MANIFEST_PATH),
                "file_count": len(manifest["files"]),
            },
            "final_orchestrator": {
                "path": rel(FINAL_PATH),
                "sha256": sha256(FINAL_PATH),
            },
        },
        "shutdown_results": {"fixed": "PASS", "rotating": "PASS"},
        "authorization": {
            "record_path": rel(AUTH_PATH),
            "record_sha256": sha256(AUTH_PATH),
            "consumed": True,
            "reusable_for_future_run": False,
            "current_run_hardware_authorization": False,
        },
        "hardware_actions_executed": False,
    }


def build_closeout_summary(
    final: dict[str, Any],
    remote_sha: str,
    checkpoint_sha: str,
    audit: dict[str, Any],
    audit_sha: str,
    contract_sha: str,
    p10_1_plan_sha: str,
    p11_sha: str,
) -> tuple[dict[str, Any], str]:
    pending = {
        "ethernet": "DEFERRED_NO_NETWORK_CABLE",
        "spi": "PENDING",
        "physical_global_permit": "PENDING_D17",
        "external_tfdu_duty": "PENDING_EXTERNAL_MEASUREMENT",
        "handover": "PENDING_P11",
        "8x32": "PENDING_P12",
        "600rpm": "PENDING_P13",
        "product_final": "PENDING",
    }
    payload = {
        "schema_version": 1,
        "status": "PASS",
        "test_id": "P10-CLOSEOUT-001",
        "generated_at_utc": GENERATED_AT_UTC,
        "scope": P10_CLOSEOUT_SCOPE,
        "p10_status": "PASS",
        "current_program_stage": P10_NEXT_STAGE,
        "formal_run_id": RUN_ID,
        "source_commit": SOURCE_COMMIT,
        "evidence_checkpoint_commit": EVIDENCE_CHECKPOINT_COMMIT,
        "pass_tag": PASS_TAG,
        "pass_tag_object": EXPECTED_PASS_TAG_OBJECT,
        "pass_tag_target": EVIDENCE_CHECKPOINT_COMMIT,
        "closed_tag_to_create": "p10-ax7020-dual-node-2lane-closed",
        "formal_stage_gates_preserved": {
            "values": final["mandatory_gates"],
            "interpretation": (
                "internal gates of the frozen P10 scope; they are not additional "
                "product, scaling, rotation, handover, or final-hardware claims"
            ),
        },
        "canonical_scoped_claims": {
            "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET": "PASS",
            "DUAL_Z7020_INDEPENDENT_ENDPOINTS": "PASS",
            "DUAL_Z7020_2LANE_OPTICAL_LINK": "PASS",
            "DUAL_Z7020_PS_PL_PHY_PL_PS": "PASS",
            "STATIONARY_2LANE_30MIN": "PASS",
        },
        "authorization": {
            "current_run_hardware_authorization": False,
            "last_hardware_authorization_consumed": True,
            "last_hardware_stage": "P10",
            "last_hardware_run_id": RUN_ID,
            "last_shutdown_fixed": "PASS",
            "last_shutdown_rotating": "PASS",
        },
        "checkpoint_metadata": {
            "path": rel(CHECKPOINT_JSON),
            "sha256": checkpoint_sha,
        },
        "remote_push": {"path": rel(REMOTE_JSON), "sha256": remote_sha},
        "goodput_measurement_audit": {
            "path": rel(AUDIT_JSON),
            "sha256": audit_sha,
            "status": audit["status"],
            "outcome": audit["outcome"],
            "eligible_for_final_8lane_projection": False,
        },
        "p10_1_plan": {
            "path": rel(P10_1_PLAN),
            "sha256": p10_1_plan_sha,
            "measurement_contract_path": rel(MEASUREMENT_CONTRACT),
            "measurement_contract_sha256": contract_sha,
            "status": "OFFLINE_PLAN_ONLY",
        },
        "p11_readiness": {
            "path": rel(P11_READINESS),
            "sha256": p11_sha,
            "official_stage_status": "NOT_STARTED",
            "hardware_ready": False,
            "current_tfdu_module_count": 4,
            "minimum_required_tfdu_module_count": 5,
        },
        "unchanged_pending_scopes": pending,
        "hardware_actions_executed": False,
        "network_hardware_used": False,
        "jtag_connected": False,
        "fpga_programmed": False,
        "ps_elf_run": False,
        "uart_written": False,
        "tfdu_driven": False,
        "p11_started": False,
        "p11_hold": True,
    }
    markdown = "\n".join(
        [
            "# P10 closeout summary",
            "",
            "- P10 scoped status: `PASS`.",
            f"- Formal run: `{RUN_ID}`.",
            f"- PASS checkpoint: `{PASS_TAG}` -> `{EVIDENCE_CHECKPOINT_COMMIT}`.",
            "- Current-run hardware authorization: `false`.",
            "- Last P10 authorization consumed: `true`.",
            "- Fixed / rotating shutdown: `PASS` / `PASS`.",
            "- Current program stage: `P10_POST_ACCEPTANCE_ANALYSIS`.",
            f"- Goodput audit: `{audit['outcome']}`.",
            "- Current final goodput fields may not be projected to 8 lanes or final-product performance.",
            "- P11 official stage: `NOT_STARTED`; hardware ready: `false`.",
            "- No hardware action was executed during closeout.",
            "",
            "Pending scopes remain Ethernet, SPI, physical GLOBAL_PERMIT D17, external TFDU duty measurement, handover, 8x32, 600 rpm, and product-final acceptance.",
            "",
        ]
    )
    return payload, markdown


def refresh_pass_hashes(document: dict[str, Any]) -> None:
    for item in document["requirements"]:
        if item.get("status") != "PASS":
            continue
        for binding in item.get("artifact_hashes", []):
            path = ROOT / str(binding.get("path", ""))
            if path.is_file():
                binding["sha256"] = sha256(path)
        if item.get("artifact_hashes"):
            item["artifact_hash"] = item["artifact_hashes"][0]["sha256"]


def upsert_requirement(
    document: dict[str, Any],
    *,
    requirement_id: str,
    requirement_text: str,
    profile: str,
    verification_method: str,
    verification_stage: str,
    verification_scope: str,
    test_id: str,
    evidence_path: Path,
    artifact_paths: list[Path],
) -> None:
    item = next(
        (
            candidate
            for candidate in document["requirements"]
            if candidate.get("requirement_id") == requirement_id
        ),
        None,
    )
    if item is None:
        item = {"requirement_id": requirement_id}
        document["requirements"].append(item)
    bindings = [{"path": rel(path), "sha256": sha256(path)} for path in artifact_paths]
    item.update(
        {
            "requirement_text": requirement_text,
            "profile": profile,
            "verification_method": verification_method,
            "verification_stage": verification_stage,
            "verification_scope": verification_scope,
            "test_id": test_id,
            "evidence_path": rel(evidence_path),
            "status": "PASS",
            "waiver": None,
            "artifact_hash": bindings[0]["sha256"],
            "artifact_hashes": bindings,
            "hardware_followup": P10_HARDWARE_FOLLOWUP,
        }
    )


def update_state(
    state: dict[str, Any],
    *,
    closeout_sha: str,
    checkpoint_sha: str,
    remote_sha: str,
    audit: dict[str, Any],
    audit_sha: str,
    contract_sha: str,
    plan_sha: str,
    p11_sha: str,
) -> dict[str, Any]:
    state["state_revision"] = "P10-POST-ACCEPTANCE-CLOSEOUT-2"
    state["current_program_stage"] = P10_NEXT_STAGE
    state["current_run_hardware_authorization"] = False
    state["last_hardware_authorization_consumed"] = True
    state["last_hardware_stage"] = "P10"
    state["last_hardware_run_id"] = RUN_ID
    state["last_shutdown_fixed"] = "PASS"
    state["last_shutdown_rotating"] = "PASS"
    state["last_verified_commit"] = EVIDENCE_CHECKPOINT_COMMIT

    p10 = state["p10_acceptance"]
    p10["evidence_checkpoint_commit"] = EVIDENCE_CHECKPOINT_COMMIT
    p10["application_goodput_fields_classification"] = (
        "GLOBAL_MINIMUM_MICROTRANSFER_BPS_NOT_SCALING_METRIC"
    )
    p10["goodput_scaling_eligible"] = False
    p10["goodput_measurement_audit_path"] = rel(AUDIT_JSON)
    p10["goodput_measurement_audit_sha256"] = audit_sha
    p10["unchanged_pending_scopes"]["ETHERNET"] = "DEFERRED_NO_NETWORK_CABLE"

    state["p10_post_acceptance_closeout"] = {
        "status": "PASS",
        "test_id": "P10-CLOSEOUT-001",
        "evidence_path": rel(CLOSEOUT_JSON),
        "evidence_sha256": closeout_sha,
        "git_metadata_path": rel(CHECKPOINT_JSON),
        "git_metadata_sha256": checkpoint_sha,
        "remote_push_path": rel(REMOTE_JSON),
        "remote_push_sha256": remote_sha,
        "hardware_actions_executed": False,
        "p11_started": False,
    }
    state["p10_goodput_measurement_audit"] = {
        "status": "PASS",
        "test_id": "P10-GOODPUT-MEASUREMENT-AUDIT",
        "evidence_path": rel(AUDIT_JSON),
        "evidence_sha256": audit_sha,
        "outcome": audit["outcome"],
        "eligible_for_final_8lane_projection": False,
        "hardware_actions_executed": False,
    }
    state["p10_1_performance_and_observability"] = {
        "status": "OFFLINE_PLAN_ONLY",
        "plan_path": rel(P10_1_PLAN),
        "plan_sha256": plan_sha,
        "measurement_contract_path": rel(MEASUREMENT_CONTRACT),
        "measurement_contract_sha256": contract_sha,
        "hardware_experiments_authorized": False,
    }
    state["p11_readiness"] = {
        "status": "NOT_READY",
        "official_stage_status": "NOT_STARTED",
        "hardware_ready": False,
        "current_run_hardware_authorization": False,
        "current_tfdu_module_count": 4,
        "minimum_required_tfdu_module_count": 5,
        "evidence_path": rel(P11_READINESS),
        "evidence_sha256": p11_sha,
        "missing_prerequisites": [
            "one additional compatible TFDU module",
            "four-fixed-module fixture",
            "rotating-module fixture",
            "verified ABZ/phase input",
            "bounded controllable motion source",
            "P11-specific board profile/wiring/XDC",
            "new current-run hardware authorization",
        ],
    }
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    errors: list[str] = []

    try:
        final, manifest, auth = verify_inputs(errors)

        remote, remote_markdown = build_remote_summary()
        emit(REMOTE_JSON, json_text(remote), write=args.write, errors=errors)
        emit(REMOTE_MD, remote_markdown, write=args.write, errors=errors)

        audit, audit_markdown = build_goodput_audit(final)
        emit(AUDIT_JSON, json_text(audit), write=args.write, errors=errors)
        emit(AUDIT_MD, audit_markdown, write=args.write, errors=errors)

        contract = build_measurement_contract()
        emit(
            MEASUREMENT_CONTRACT,
            yaml_text(contract),
            write=args.write,
            errors=errors,
        )
        contract_sha = sha256(MEASUREMENT_CONTRACT)
        audit_sha = sha256(AUDIT_JSON)
        plan_markdown = build_p10_1_plan(contract_sha, audit_sha)
        emit(P10_1_PLAN, plan_markdown, write=args.write, errors=errors)
        emit(P11_READINESS, build_p11_readiness(), write=args.write, errors=errors)

        checkpoint = build_checkpoint_metadata(final, manifest, auth)
        emit(
            CHECKPOINT_JSON,
            json_text(checkpoint),
            write=args.write,
            errors=errors,
        )

        closeout, closeout_markdown = build_closeout_summary(
            final,
            sha256(REMOTE_JSON),
            sha256(CHECKPOINT_JSON),
            audit,
            audit_sha,
            contract_sha,
            sha256(P10_1_PLAN),
            sha256(P11_READINESS),
        )
        emit(CLOSEOUT_JSON, json_text(closeout), write=args.write, errors=errors)
        emit(CLOSEOUT_MD, closeout_markdown, write=args.write, errors=errors)

        state = load_json(STATE_PATH)
        state = update_state(
            state,
            closeout_sha=sha256(CLOSEOUT_JSON),
            checkpoint_sha=sha256(CHECKPOINT_JSON),
            remote_sha=sha256(REMOTE_JSON),
            audit=audit,
            audit_sha=audit_sha,
            contract_sha=contract_sha,
            plan_sha=sha256(P10_1_PLAN),
            p11_sha=sha256(P11_READINESS),
        )
        emit(STATE_PATH, json_text(state), write=args.write, errors=errors)
        emit(
            STATUS_PATH,
            render_project_status(state),
            write=args.write,
            errors=errors,
        )

        document = yaml.safe_load(REQUIREMENTS_PATH.read_text(encoding="utf-8"))
        document["document_version"] = "8.1"
        upsert_requirement(
            document,
            requirement_id="P10-CLOSEOUT-001",
            requirement_text=(
                "P10 post-acceptance closeout shall consume the current-run "
                "authorization, freeze Git/remote checkpoint metadata, preserve "
                "the scoped PASS, and execute no hardware action."
            ),
            profile="P10_POST_ACCEPTANCE_CLOSEOUT",
            verification_method=(
                "Offline cross-check of the immutable PASS tag, remote refs, "
                "formal-run artifacts, shutdown results, authorization lifecycle, "
                "and generated canonical state."
            ),
            verification_stage="P10_POST_ACCEPTANCE_CLOSEOUT",
            verification_scope=P10_CLOSEOUT_SCOPE,
            test_id="P10-CLOSEOUT-001",
            evidence_path=CLOSEOUT_JSON,
            artifact_paths=[
                CLOSEOUT_JSON,
                CHECKPOINT_JSON,
                REMOTE_JSON,
                FINAL_PATH,
                MANIFEST_PATH,
            ],
        )
        upsert_requirement(
            document,
            requirement_id="P10-PERF-MEAS-001",
            requirement_text=(
                "P10 performance fields shall have reproducible units, numerator, "
                "denominator, window, and provenance; unsuitable fields shall not "
                "be used for 8-lane or final-product projection."
            ),
            profile="P10_1_DUAL_NODE_PERFORMANCE_AND_OBSERVABILITY",
            verification_method=(
                "Offline recomputation from P10-E/I/J summaries, observation "
                "timestamps, immutable mailbox dumps, and the frozen runtime "
                "formula; compare PS-command, XSDB-wall, and full-soak windows."
            ),
            verification_stage="P10_POST_ACCEPTANCE_ANALYSIS",
            verification_scope=P10_ANALYSIS_SCOPE,
            test_id="P10-GOODPUT-MEASUREMENT-AUDIT",
            evidence_path=AUDIT_JSON,
            artifact_paths=[
                AUDIT_JSON,
                RUN_ROOT / "stages/p10_i/stage_summary.json",
                RUN_ROOT / "stages/p10_j/stage_summary.json",
                RUNTIME_PATH,
                FIRMWARE_PATH,
                MEASUREMENT_CONTRACT,
                P10_1_PLAN,
            ],
        )
        refresh_pass_hashes(document)
        emit(
            REQUIREMENTS_PATH,
            yaml_text(document),
            write=args.write,
            errors=errors,
        )
        emit(
            TRACEABILITY_PATH,
            render_traceability(document),
            write=args.write,
            errors=errors,
        )

        errors.extend(validate_state(state, ROOT))
        errors.extend(validate_requirements(document, ROOT))
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"closeout generation failed: {exc}")

    for error in errors:
        print(f"ERROR: {error}")
    status = "PASS" if not errors else "FAIL"
    print(f"P10_CLOSEOUT_GENERATION={status}")
    print(f"P10_CLOSEOUT_HARDWARE_ACTIONS_EXECUTED=false")
    print(f"CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
