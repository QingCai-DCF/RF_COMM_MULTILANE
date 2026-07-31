#!/usr/bin/env python3
"""Update canonical requirements/state after the complete P10.1 offline gate."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from p10_1_common import ROOT, rel, sha256
from p8a_common import (
    STATUS_PATH,
    TRACEABILITY_PATH,
    render_project_status,
    render_traceability,
)


REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATE = ROOT / "config/project_state.json"
BEGIN = "# BEGIN GENERATED P10.1 REQUIREMENTS"
END = "# END GENERATED P10.1 REQUIREMENTS"
PROFILE = "P10_1_DUAL_NODE_PERFORMANCE_STREAMING_OBSERVABILITY"
SCOPE = "P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_NO_HARDWARE"
STAGE = "P10_1_EXTENDED_OFFLINE_PERFORMANCE_STREAMING_OBSERVABILITY_AND_P11_READINESS"
HARDWARE_STAGE = "P10_1_HARDWARE_PERFORMANCE_STREAMING_CROSSTALK_ACCEPTANCE"

PASS_REQUIREMENTS = [
    ("PERF-MEAS-001", "Metric names, numerators, windows, units, classes, and provenance shall be explicit and schema-validated.", "p10_1_measurement_contract", "P10_1-MEASUREMENT-CONTRACT"),
    ("PERF-MEAS-002", "Diagnostic microtransfers shall never be selected as sustained application goodput or scaling evidence.", "p10_1_finalizer_fix", "P10_1-FINALIZER-FIX"),
    ("PERF-MEAS-003", "Frozen P10 performance evidence shall be reproducibly recomputed without rewriting its historical summary.", "p10_1_historical_recompute", "P10_1-HISTORICAL-RECOMPUTE"),
    ("PERF-MEAS-004", "Every formal case shall cross-check independent timer sources within the frozen tolerance or report a fixed boundary.", "p10_1_timer_crosscheck", "P10_1-TIMER-CROSSCHECK"),
    ("PERF-FINAL-001", "The metric finalizer shall deterministically select by metric, class, direction, eligibility, run, and aggregation rule.", "p10_1_finalizer_fix", "P10_1-FINALIZER-FIX"),
    ("PERF-OBS-001", "The PS service shall provide a preallocated nonblocking trace ring with generation, overflow, snapshot, and clear semantics.", "p10_1_observability", "P10_1-OBSERVABILITY"),
    ("PERF-OBS-002", "The PL data path shall provide a nonblocking event FIFO whose overflow cannot stall the fast path.", "p10_1_observability", "P10_1-OBSERVABILITY"),
    ("PERF-OBS-003", "Per-stage bytes, descriptors, stalls, queue, ACK, retry, duty, and direction counters shall use coherent snapshots.", "p10_1_observability", "P10_1-OBSERVABILITY"),
    ("PERF-AUTO-001", "Each endpoint shall support a target-resident deterministic performance data generator controlled at low frequency by the host.", "p10_1_autonomous_perf_mode", "P10_1-AUTONOMOUS-PERF-MODE"),
    ("PERF-AUTO-002", "The remote endpoint shall verify length, pattern, CRC32, SHA256, identity, generation, and exactly-once atomic commit.", "p10_1_autonomous_perf_mode", "P10_1-AUTONOMOUS-PERF-MODE"),
    ("PERF-PIPE-001", "The target service shall support multi-buffer staged ownership with explicit generation and no leak or double reclaim.", "p10_1_buffer_pipeline", "P10_1-MULTI-BUFFER-PIPELINE"),
    ("PERF-PIPE-002", "Descriptor rings shall support bounded batching, wrap, exactly-once completion, and zero descriptor leaks.", "p10_1_descriptor_batching", "P10_1-DESCRIPTOR-BATCHING"),
    ("PERF-PIPE-003", "Cache maintenance shall be modeled and implemented as a batchable ownership boundary; non-cacheable mode is diagnostic only.", "p10_1_descriptor_batching", "P10_1-DESCRIPTOR-BATCHING"),
    ("PERF-STREAM-001", "The offline architecture shall stream a 64 MiB object across descriptors with incremental integrity and atomic publication.", "p10_1_streaming_64m", "P10_1-STREAMING-64M"),
    ("PERF-STREAM-002", "Abort, reset, duplicate, missing, stale, out-of-order, and wrap cases shall produce no partial, wrong, duplicate, or stale publication.", "p10_1_streaming_64m", "P10_1-STREAMING-64M"),
    ("HWPREP-P10_1-001", "The future P10.1 hardware runner shall fail closed on authorization, identity, artifact, shutdown, lane, network, motion, and runtime errors.", "p10_1_hardware_dry_run", "P10_1-HARDWARE-RUNNER-DRY-RUN"),
]

PENDING_REQUIREMENT_IDS = {
    "PERF-HW-001",
    "P11-READY-001",
    "P11-READY-002",
    "P11-READY-003",
}
GENERATED_REQUIREMENT_IDS = {
    requirement_id for requirement_id, *_ in PASS_REQUIREMENTS
} | PENDING_REQUIREMENT_IDS


def evidence_path(stem: str) -> Path:
    return ROOT / f"evidence/generated/{stem}.json"


def artifact_record(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)}


def pass_item(
    requirement_id: str,
    text: str,
    stem: str,
    test_id: str,
) -> dict[str, Any]:
    evidence = evidence_path(stem)
    return {
        "requirement_id": requirement_id,
        "requirement_text": text,
        "profile": PROFILE,
        "verification_method": "Direct offline config generation, production-source host-native tests, Python campaigns, XSIM, routed AX7020 implementation, and hash-bound evidence.",
        "verification_stage": STAGE,
        "verification_scope": SCOPE,
        "test_id": test_id,
        "evidence_path": rel(evidence),
        "status": "PASS",
        "waiver": None,
        "artifact_hash": sha256(evidence),
        "artifact_hashes": [artifact_record(evidence)],
        "hardware_followup": "Offline PASS only. Real AX7020 application goodput, real 64 MiB streaming, rotation, handover, 8x32, 600 rpm, and product-final acceptance remain pending direct authorized hardware evidence.",
    }


def pending_item(
    requirement_id: str,
    text: str,
    profile: str,
    stage: str,
    scope: str,
    evidence: str | None,
) -> dict[str, Any]:
    return {
        "requirement_id": requirement_id,
        "requirement_text": text,
        "profile": profile,
        "verification_method": "Direct inspection and hardware acceptance after the named prerequisite, immutable artifacts, and a new current-run authorization exist.",
        "verification_stage": stage,
        "verification_scope": scope,
        "test_id": None,
        "evidence_path": evidence,
        "status": "PENDING",
        "waiver": None,
        "artifact_hashes": [],
        "hardware_followup": "Remains pending; the P10.1 offline readiness package is not direct hardware evidence.",
    }


def replace_generated_block(text: str, block: str) -> str:
    pattern = re.compile(
        rf"\n?{re.escape(BEGIN)}.*?{re.escape(END)}\n?",
        re.DOTALL,
    )
    clean = pattern.sub("\n", text).rstrip()
    return clean + "\n" + block


def remove_requirement_records(text: str, requirement_ids: set[str]) -> str:
    """Remove exact top-level requirement records while preserving all others.

    Older generated P10.1 files predate the BEGIN/END sentinels.  A later
    canonical YAML rewrite can also discard comments while retaining those
    records.  Removing by exact requirement ID before appending the generated
    block makes the updater idempotent in both cases without reformatting or
    weakening unrelated requirements.
    """

    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    marker = re.compile(r"^- requirement_id:\s*([^\s#]+)\s*(?:#.*)?(?:\r?\n)?$")
    while index < len(lines):
        match = marker.match(lines[index])
        if match is None or match.group(1) not in requirement_ids:
            output.append(lines[index])
            index += 1
            continue
        index += 1
        while index < len(lines) and marker.match(lines[index]) is None:
            index += 1
    return "".join(output)


def bind_existing_model_requirements(text: str, model_hash: str) -> str:
    for requirement_id, extra_text in (
        (
            "PERF-MODEL-001",
            " The P10.1 extension also closes a complete dual-node streaming sensitivity model without changing the original P8D scope.",
        ),
        (
            "PERF-MODEL-002",
            " The P10.1 extension directly evaluates the current two-lane 4.0 Mbit/s-per-direction scale-equivalent target without increasing duty.",
        ),
    ):
        start = text.index(f"- requirement_id: {requirement_id}")
        next_start = text.find("\n- requirement_id:", start + 1)
        if next_start < 0:
            next_start = len(text)
        record = text[start:next_start]
        if extra_text.strip() not in record:
            record = record.replace(
                "\n  profile:",
                extra_text + "\n  profile:",
                1,
            )
        pattern = re.compile(
            r"  - path: evidence/generated/p10_1_performance_model\.json\n"
            r"    sha256: [0-9a-f]{64}\n"
        )
        binding = (
            "  - path: evidence/generated/p10_1_performance_model.json\n"
            f"    sha256: {model_hash}\n"
        )
        if pattern.search(record):
            record = pattern.sub(binding, record)
        else:
            marker = "  hardware_followup:"
            record = record.replace(marker, binding + marker, 1)
        text = text[:start] + record + text[next_start:]
    return text


def update_requirements() -> None:
    missing = [
        rel(evidence_path(stem))
        for _, _, stem, _ in PASS_REQUIREMENTS
        if not evidence_path(stem).is_file()
    ]
    model = evidence_path("p10_1_performance_model")
    if not model.is_file():
        missing.append(rel(model))
    if missing:
        raise SystemExit("missing P10.1 evidence: " + ", ".join(sorted(set(missing))))
    items = [pass_item(*record) for record in PASS_REQUIREMENTS]
    items.extend(
        [
            pending_item(
                "PERF-HW-001",
                "Real AX7020 sustained application goodput shall meet at least 4.0 Mbit/s in each tested half-duplex direction under the frozen measurement contract.",
                HARDWARE_STAGE,
                HARDWARE_STAGE,
                "PENDING_CURRENT_RUN_AUTHORIZATION",
                "docs/plans/P10_1_HARDWARE_PERFORMANCE_ACCEPTANCE_PLAN.md",
            ),
            pending_item(
                "P11-READY-001",
                "P11 shall have a fifth compatible and fully inventoried TFDU6102 small board.",
                "P11_HARDWARE_READINESS",
                "P11_NOT_STARTED",
                "P11_PREREQUISITE_PENDING",
                "docs/P11_FIVE_MODULE_INVENTORY_PLAN.md",
            ),
            pending_item(
                "P11-READY-002",
                "P11 shall have accepted four-fixed-module and one-rotating-module fixtures bound to as-built geometry.",
                "P11_HARDWARE_READINESS",
                "P11_NOT_STARTED",
                "P11_PREREQUISITE_PENDING",
                "docs/P11_FIXTURE_REQUIREMENTS.md",
            ),
            pending_item(
                "P11-READY-003",
                "P11 shall have a selected and electrically verified ABZ source, pin/profile/XDC path, and phase/acquisition budget.",
                "P11_HARDWARE_READINESS",
                "P11_NOT_STARTED",
                "P11_PREREQUISITE_PENDING",
                "docs/P11_ABZ_INPUT_REQUIREMENTS.md",
            ),
        ]
    )
    body = yaml.safe_dump(
        items,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
    block = f"{BEGIN}\n{body}{END}\n"
    text = REQUIREMENTS.read_text(encoding="utf-8")
    text = remove_requirement_records(text, GENERATED_REQUIREMENT_IDS)
    text = bind_existing_model_requirements(text, sha256(model))
    # P10-PERF-MEAS-001 already binds the contract; keep that historical
    # analysis requirement aligned with the extended schema.
    contract_hash = sha256(ROOT / "config/performance/p10_1_measurement_contract.yaml")
    text = re.sub(
        r"(  - path: config/performance/p10_1_measurement_contract\.yaml\n"
        r"    sha256: )[0-9a-f]{64}",
        rf"\g<1>{contract_hash}",
        text,
        count=1,
    )
    REQUIREMENTS.write_text(
        replace_generated_block(text, block),
        encoding="utf-8",
        newline="\n",
    )


def update_state() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    p11 = evidence_path("p10_1_p11_readiness")
    if not p11.is_file():
        raise SystemExit("p10_1_p11_readiness evidence is missing")
    model_path = evidence_path("p10_1_performance_model")
    model = json.loads(model_path.read_text(encoding="utf-8"))
    if model.get("status") != "PASS":
        raise SystemExit("p10_1_performance_model evidence is not PASS")
    existing_performance = state.get("p10_1_performance_and_observability", {})
    selected = model.get("selected", {})
    state["state_revision"] = "P10-1-OFFLINE-PERFORMANCE-READY-1"
    state["current_program_stage"] = HARDWARE_STAGE
    state["p10_1_offline_status"] = "PASS"
    state["p10_1_hardware_status"] = "PENDING_CURRENT_RUN_AUTHORIZATION"
    state["p11_status"] = "NOT_STARTED"
    state["p11_hardware_ready"] = False
    state["current_run_hardware_authorization"] = False
    state["p10_1_no_hardware_actions_executed"] = True
    state["stage_status"][STAGE] = "PASS"
    evidence = model_path
    state["p10_1_performance_and_observability"] = {
        "status": "PASS",
        "verification_scope": SCOPE,
        "source_commit": source_commit,
        "evidence_path": rel(evidence),
        "evidence_sha256": sha256(evidence),
        "measurement_contract_path": "config/performance/p10_1_measurement_contract.yaml",
        "measurement_contract_sha256": sha256(
            ROOT / "config/performance/p10_1_measurement_contract.yaml"
        ),
        "prior_modeled_application_goodput_bps": existing_performance.get(
            "prior_modeled_application_goodput_bps"
        ),
        "prior_model_classification": existing_performance.get(
            "prior_model_classification"
        ),
        "modeled_application_goodput_bps": model.get(
            "modeled_application_goodput_bps"
        ),
        "scale_equivalent_4mbps_feasibility": model.get("hard_target_status"),
        "stretch_4p8mbps": model.get("stretch_target_status"),
        "selected_pipeline": {
            "buffer_count": model.get("required_buffer_count"),
            "descriptor_ring_depth": model.get("required_ring_depth"),
            "descriptor_batch": model.get("required_descriptor_batch"),
            "outstanding_frames": selected.get(
                "outstanding", model.get("required_outstanding")
            ),
            "ack_aggregation_threshold": selected.get("ack_threshold"),
        },
        "real_hardware_goodput_status": "PENDING_CURRENT_RUN_AUTHORIZATION",
        "hardware_experiments_authorized": False,
        "hardware_actions_executed": False,
    }
    state["p11_readiness"].update(
        {
            "status": "NOT_READY",
            "official_stage_status": "NOT_STARTED",
            "hardware_ready": False,
            "current_run_hardware_authorization": False,
            "evidence_path": rel(p11),
            "evidence_sha256": sha256(p11),
        }
    )
    state["last_verified_commit"] = source_commit
    STATE.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def bind_requirement_artifact(
    text: str,
    requirement_id: str,
    artifact_path: str,
    digest: str,
) -> str:
    start = text.index(f"- requirement_id: {requirement_id}")
    next_start = text.find("\n- requirement_id:", start + 1)
    if next_start < 0:
        next_start = len(text)
    record = text[start:next_start]
    pattern = re.compile(
        rf"(  - path: {re.escape(artifact_path)}\n"
        r"    sha256: )[0-9a-f]{64}"
    )
    record, count = pattern.subn(rf"\g<1>{digest}", record, count=1)
    if count != 1:
        raise RuntimeError(
            f"{requirement_id} does not bind canonical artifact {artifact_path}"
        )
    primary = re.search(
        r"  artifact_hashes:\n"
        r"  - path: [^\n]+\n"
        r"    sha256: ([0-9a-f]{64})",
        record,
    )
    if primary is None:
        raise RuntimeError(f"{requirement_id} has no primary artifact binding")
    record = re.sub(
        r"(  artifact_hash: )[0-9a-f]{64}",
        rf"\g<1>{primary.group(1)}",
        record,
        count=1,
    )
    return text[:start] + record + text[next_start:]


def update_generated_canonical_views() -> None:
    state = json.loads(STATE.read_text(encoding="utf-8"))
    STATUS_PATH.write_text(
        render_project_status(state),
        encoding="utf-8",
        newline="\n",
    )

    state_hash = sha256(STATE)
    status_hash = sha256(STATUS_PATH)
    text = REQUIREMENTS.read_text(encoding="utf-8")
    for requirement_id, path, digest in (
        ("P8A-STATE-001", "config/project_state.json", state_hash),
        ("P8A-STATE-001", "PROJECT_STATUS.md", status_hash),
        ("P8A-TRACE-001", "config/project_state.json", state_hash),
        ("P8A-SCOPE-001", "config/project_state.json", state_hash),
        ("P8A-SCOPE-001", "PROJECT_STATUS.md", status_hash),
    ):
        text = bind_requirement_artifact(
            text,
            requirement_id,
            path,
            digest,
        )
    REQUIREMENTS.write_text(text, encoding="utf-8", newline="\n")
    document = yaml.safe_load(text)
    TRACEABILITY_PATH.write_text(
        render_traceability(document),
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.write == args.check:
        raise SystemExit("choose exactly one of --write or --check")
    if args.write:
        update_requirements()
        update_state()
        update_generated_canonical_views()
    document = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    ids = [item["requirement_id"] for item in document["requirements"]]
    required = {item[0] for item in PASS_REQUIREMENTS} | {
        "PERF-MODEL-001",
        "PERF-MODEL-002",
        "PERF-HW-001",
        "P11-READY-001",
        "P11-READY-002",
        "P11-READY-003",
    }
    state = json.loads(STATE.read_text(encoding="utf-8"))
    errors = []
    if not required.issubset(ids):
        errors.append("required P10.1 requirement IDs are missing")
    if len(ids) != len(set(ids)):
        errors.append("duplicate requirement IDs exist")
    if state.get("p10_1_offline_status") != "PASS":
        errors.append("p10_1_offline_status is not PASS")
    if state.get("p10_1_hardware_status") != "PENDING_CURRENT_RUN_AUTHORIZATION":
        errors.append("p10_1_hardware_status is not pending authorization")
    if state.get("p11_status") != "NOT_STARTED" or state.get("p11_hardware_ready") is not False:
        errors.append("P11 status was incorrectly promoted")
    for error in errors:
        print(f"ERROR: {error}")
    print(f"P10_1_REQUIREMENTS_STATE={'PASS' if not errors else 'FAIL'}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
