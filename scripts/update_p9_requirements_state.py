#!/usr/bin/env python3
"""Advance canonical P9 state and its hardware requirement traceability."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from p8a_common import P9_SCOPE, render_project_status, render_traceability

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "config/project_state.json"
REQ_PATH = ROOT / "config/project_requirements.yaml"
STATUS_PATH = ROOT / "PROJECT_STATUS.md"
TRACE_PATH = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
AUTH_PATH = ROOT / "config/p9_current_run_authorization.json"
PROFILE = "Z7010_2LANE_DEV"
FOLLOWUP = (
    "This PASS is limited to one stationary Zynq-7010 board and two lanes. "
    "Z7020, eight lanes, rotating hardware, external duty/optical measurements, "
    "the physical GLOBAL_PERMIT implementation, Ethernet, and product-final acceptance remain pending."
)

SPECS: dict[str, tuple[str, str, str]] = {
    "P9-HW-001": ("Immutable candidate, shutdown, XSA, BSP, runner, and ELF provenance is hash-bound.", "P9-02-IMMUTABLE-ARTIFACT-FREEZE", "p9_artifact_freeze_summary"),
    "P9-HW-002": ("Safe boot, shutdown-before, shutdown-on-exit, and shutdown-after are confirmed.", "P9-HW-002-SHUTDOWN", "p9_shutdown_summary"),
    "P9-HW-003": ("The formal run is bound to the current user authorization and immutable artifacts.", "P9-HW-003", "p9_authorization_summary"),
    "P9-PHY-001": ("Fresh AB/BA raw counters pass for both logical lanes and four physical directions.", "P9-PHY-001", "p9_raw_lane_matrix_summary"),
    "P9-PHY-002": ("Lane 0 operates at the configured 4 Mbit/s raw PHY rate.", "P9-PHY-002", "p9_phy_4mbps_summary"),
    "P9-PHY-003": ("Lane 1 operates at the configured 4 Mbit/s raw PHY rate.", "P9-PHY-003", "p9_phy_4mbps_summary"),
    "P9-PHY-004": ("Both lanes concurrently provide 8 Mbit/s aggregate raw capability.", "P9-PHY-004", "p9_phy_4mbps_summary"),
    "P9-SAFE-001": ("All four TFDU paths observe the hardware startup wait before readiness.", "P9-SAFE-001", "p9_tfdu_safety_summary"),
    "P9-SAFE-002": ("Hardware runtime continuous-high telemetry remains at or below one microsecond.", "P9-SAFE-002", "p9_tfdu_safety_summary"),
    "P9-SAFE-003": ("Exact 1 ms rolling-duty runtime accounting remains below the strict hard limit and design target.", "P9-SAFE-003", "p9_tfdu_safety_summary"),
    "P9-SAFE-004": ("Disarm reaches final TX kill, aborts the active train, and explicit re-arm does not resume it.", "P9-SAFE-004", "p9_tfdu_safety_summary"),
    "P9-L2-001": ("The real optical runtime exercises a 32-outstanding selective-repeat window.", "P9-L2-001", "p9_selective_repeat_summary"),
    "P9-L2-002": ("The real optical runtime exercises 32-bit SACK and bounded ACK aggregation.", "P9-L2-002", "p9_sack_ack_summary"),
    "P9-L2-003": ("Sequence wrap, loss, reorder, stale, CRC, duplicate, and retry recovery preserve exactly-once delivery.", "P9-L2-003", "p9_sack_ack_summary"),
    "P9-L3-001": ("The two-lane hardware scheduler runs single-lane, equal, and weighted profiles.", "P9-L3-001", "p9_scheduler_migration_summary"),
    "P9-L3-002": ("Unavailable, invalid-mapping, and duty-throttled lanes are isolated from scheduling.", "P9-L3-002", "p9_scheduler_migration_summary"),
    "P9-L3-003": ("Only unacknowledged work migrates to the healthy lane and clean acknowledged work never migrates.", "P9-L3-003", "p9_scheduler_migration_summary"),
    "P9-DMA-001": ("The PS runtime uses the implemented AXI DMA scatter-gather engine and DDR buffers.", "P9-DMA-001", "p9_dma_ddr_cache_summary"),
    "P9-DMA-002": ("Cache flush, invalidate, barrier, cache-enabled, and cache-disabled ownership paths are exercised.", "P9-DMA-002", "p9_dma_ddr_cache_summary"),
    "P9-DMA-003": ("Each real DMA descriptor completes and is reclaimed exactly once without leak.", "P9-DMA-003", "p9_dma_ddr_cache_summary"),
    "P9-DMA-004": ("Idle/queued reset, abort, soft reset, stale completion, reboot, and recovery are verified.", "P9-DMA-004", "p9_dma_ddr_cache_summary"),
    "P9-RFAP-001": ("RFAP v1 is parsed, reassembled, integrity checked, and atomically published at runtime.", "P9-RFAP-001", "p9_rfap_runtime_summary"),
    "P9-RFAP-002": ("RFAP vNext streaming is parsed and atomically published through the frozen PS/PL runtime.", "P9-RFAP-002", "p9_rfap_runtime_summary"),
    "P9-RFAP-003": ("Fresh A-to-B and B-to-A objects preserve CRC32, SHA-256, and zero partial publish.", "P9-RFAP-003", "p9_rfap_runtime_summary"),
    "P9-PERF-001": ("PS preparation, DMA, PL completion, integrity, frame, and application throughput are characterized.", "P9-PERF-001", "p9_performance_summary"),
    "P9-SOAK-001": ("The exact 1800-second stationary two-lane formal soak completes without mandatory-gate violation.", "P9-SOAK-001", "p9_stationary_30min_summary"),
    "P9-EVID-001": ("The complete formal run has raw logs, immutable hashes, shutdown evidence, and consistent summaries.", "P9-EVID-001", "p9_evidence_consistency_summary"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def current_commit() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def record(path: Path) -> dict[str, str]:
    return {"path": path.resolve().relative_to(ROOT.resolve()).as_posix(), "sha256": sha256(path)}


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


def refresh_state_evidence_hashes(state: dict[str, Any]) -> None:
    for section in ("p8c_acceptance", "p8d_acceptance", "p8e_acceptance"):
        value = state.get(section)
        if not isinstance(value, dict):
            continue
        for path_key, hash_key in (
            ("evidence_path", "evidence_sha256"),
            ("safety_config_path", "safety_config_sha256"),
            ("data_plane_config_path", "data_plane_config_sha256"),
            ("artifact_manifest_path", "artifact_manifest_sha256"),
            ("build_matrix_path", "build_matrix_sha256"),
            ("clock_reset_path", "clock_reset_sha256"),
        ):
            path_value = value.get(path_key)
            path = ROOT / str(path_value or "")
            if path.is_file() and hash_key in value:
                value[hash_key] = sha256(path)


def write_all(state: dict[str, Any], document: dict[str, Any]) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
    STATUS_PATH.write_text(render_project_status(state), encoding="utf-8", newline="\n")
    refresh_pass_hashes(document)
    REQ_PATH.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
                        encoding="utf-8", newline="\n")
    TRACE_PATH.write_text(render_traceability(document), encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--in-progress", action="store_true")
    mode.add_argument("--finalize-pass", action="store_true")
    parser.add_argument("--source-commit", default="HEAD")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--phase2", type=Path)
    args = parser.parse_args(argv)
    source_commit = subprocess.check_output(
        ["git", "rev-parse", args.source_commit], cwd=ROOT, text=True).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", source_commit):
        raise RuntimeError("source commit must resolve to a full Git hash")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    document = yaml.safe_load(REQ_PATH.read_text(encoding="utf-8"))
    document["document_version"] = "7.0"
    by_id = {item["requirement_id"]: item for item in document["requirements"]}
    stage_key = "P9_Z7010_STATIONARY_2LANE_PLATFORM_LIMITED_HARDWARE_VALIDATION"

    if args.in_progress:
        state["state_revision"] = "P9-0"
        state["p9_status"] = "IN_PROGRESS"
        state["stage_status"][stage_key] = "IN_PROGRESS"
        state["current_program_stage"] = stage_key
        state["current_run_hardware_authorization"] = True
        state["p9_current_run_authorization"] = {
            "status": "VALIDATED_PHASE1_SCOPE_AUTHORIZATION",
            "path": "config/p9_current_run_authorization.json",
            "sha256": sha256(AUTH_PATH),
        }
        state["pending_gates"] = [item for item in state.get("pending_gates", [])
                                  if item.get("gate_id") != "P9"]
        state["pending_gates"].insert(0, {"gate_id": "P9", "status": "IN_PROGRESS_CURRENT_RUN_AUTHORIZED"})
        for profile in state.get("current_profiles", []):
            if profile.get("profile") == PROFILE:
                profile["status"] = "P9_PLATFORM_LIMITED_HARDWARE_VALIDATION_IN_PROGRESS"
        for req_id, (text, _test, _stem) in SPECS.items():
            item = by_id.get(req_id)
            if item is None:
                item = {"requirement_id": req_id}
                document["requirements"].append(item)
                by_id[req_id] = item
            item.update({
                "requirement_text": text, "profile": PROFILE,
                "verification_method": "Fresh direct Z7010/JTAG/AXI-DMA/DDR/optical runtime evidence under immutable authorization.",
                "verification_stage": "P9", "verification_scope": P9_SCOPE,
                "test_id": None, "evidence_path": None, "status": "PENDING",
                "waiver": None, "artifact_hashes": [], "hardware_followup": FOLLOWUP,
            })
            item.pop("artifact_hash", None)
    else:
        if not args.run_id or args.phase2 is None:
            raise RuntimeError("--run-id and --phase2 are required for P9 PASS finalization")
        phase2_path = args.phase2.resolve()
        phase2 = json.loads(phase2_path.read_text(encoding="utf-8"))
        final_path = ROOT / "evidence/generated/p9_final_summary.json"
        final = json.loads(final_path.read_text(encoding="utf-8"))
        if final.get("P9_STATUS") != "PASS" or final.get("run_id") != args.run_id or \
                final.get("source_commit") != source_commit or \
                final.get("HARDWARE_ACTIONS_EXECUTED") is not True:
            raise RuntimeError("P9 final summary is not a matching formal hardware PASS")
        if phase2.get("run_id") != args.run_id or phase2.get("source_commit") != source_commit:
            raise RuntimeError("phase-2 authorization does not match P9 final summary")
        state["state_revision"] = "P9-1"
        state["p9_status"] = "PASS"
        state["stage_status"][stage_key] = "PASS"
        state["current_program_stage"] = "P10A_Z7020_SINGLE_BOARD_MIGRATION"
        state["current_run_hardware_authorization"] = True
        state["p9_acceptance"] = {
            "status": "PASS", "profile": PROFILE, "scope": P9_SCOPE,
            "test_id": "P9-FINAL", "run_id": args.run_id,
            "source_commit": source_commit,
            "evidence_path": "evidence/generated/p9_evidence_consistency_summary.json",
            "evidence_sha256": sha256(ROOT / "evidence/generated/p9_evidence_consistency_summary.json"),
            "phase2_authorization_path": phase2_path.relative_to(ROOT).as_posix(),
            "phase2_authorization_sha256": sha256(phase2_path),
            "candidate_bitstream_sha256": phase2["candidate_bitstream"]["sha256"],
            "shutdown_bitstream_sha256": phase2["shutdown_bitstream"]["sha256"],
            "ps_elf_sha256": phase2["ps_elf"]["sha256"],
            "hardware_actions_executed": True,
            "no_hardware_movement": True,
            "scope_exclusions": ["Z7020", "EIGHT_LANE", "ROTATION", "ETHERNET",
                                 "PHYSICAL_GLOBAL_PERMIT_D17", "FINAL_PRODUCT"],
        }
        state["completed_gates"] = [item for item in state.get("completed_gates", [])
                                    if item.get("gate_id") != "P9"]
        state["completed_gates"].append({"gate_id": "P9", "status": "PASS"})
        state["pending_gates"] = [item for item in state.get("pending_gates", [])
                                  if item.get("gate_id") != "P9"]
        state["last_verified_commit"] = source_commit
        for profile in state.get("current_profiles", []):
            if profile.get("profile") == PROFILE:
                profile["status"] = "PLATFORM_LIMITED_HARDWARE_PASS"

        frozen = [phase2["candidate_bitstream"], phase2["shutdown_bitstream"], phase2["ps_elf"]]
        frozen_records = [{"path": item["path"], "sha256": item["sha256"]} for item in frozen]
        for req_id, (text, test_id, stem) in SPECS.items():
            evidence_path = ROOT / f"evidence/generated/{stem}.json"
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            if evidence.get("status") != "PASS":
                raise RuntimeError(f"P9 requirement evidence is not PASS: {req_id}")
            bindings = [record(evidence_path), *frozen_records]
            item = by_id[req_id]
            item.update({
                "requirement_text": text, "profile": PROFILE,
                "verification_method": "Fresh direct Z7010/JTAG/AXI-DMA/DDR/optical runtime evidence under immutable authorization.",
                "verification_stage": "P9", "verification_scope": P9_SCOPE,
                "test_id": test_id, "evidence_path": evidence_path.relative_to(ROOT).as_posix(),
                "status": "PASS", "waiver": None,
                "artifact_hash": bindings[0]["sha256"], "artifact_hashes": bindings,
                "hardware_followup": FOLLOWUP,
            })

    refresh_state_evidence_hashes(state)
    write_all(state, document)
    if args.finalize_pass:
        # The immutable phase-2 record intentionally binds the pre-run
        # IN_PROGRESS state.  After direct hardware PASS publication, refresh
        # the final report with hashes of the newly generated canonical PASS
        # state and regenerate the run manifest last.  P9 requirement entries
        # bind the subsystem summaries, so this creates no hash cycle.
        from p9_hardware_runtime import evidence_manifest, write_final_summary_files

        final_path = ROOT / "evidence/generated/p9_final_summary.json"
        final = json.loads(final_path.read_text(encoding="utf-8"))
        final.update({
            "PROJECT_STATE_SHA256": sha256(STATE_PATH),
            "PROJECT_REQUIREMENTS_SHA256": sha256(REQ_PATH),
            "PROJECT_STATUS_SHA256": sha256(STATUS_PATH),
            "REQUIREMENT_TRACEABILITY_SHA256": sha256(TRACE_PATH),
            "CANONICAL_STATE_REVISION": state["state_revision"],
            "CANONICAL_STATE_AFTER_ACCEPTANCE": True,
        })
        run_root = ROOT / "evidence/hardware/p9" / args.run_id
        if not run_root.is_dir():
            raise RuntimeError("matching P9 hardware run directory is missing")
        write_final_summary_files(run_root, final)
        (run_root / "final/orchestrator_result.json").write_text(
            json.dumps(final, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8", newline="\n")
        evidence_manifest(run_root)
    print(f"P9_MACHINE_STATE={'PASS' if args.finalize_pass else 'IN_PROGRESS'}")
    print(f"P9_REQUIREMENTS_UPDATED={len(SPECS)}")
    print(f"P9_SOURCE_COMMIT={source_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
