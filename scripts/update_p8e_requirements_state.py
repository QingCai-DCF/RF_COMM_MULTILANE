#!/usr/bin/env python3
"""Close P8E requirements and advance canonical machine state after a PASS."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from p8a_common import render_project_status, render_traceability, validate_state

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "config/project_state.json"
REQ_PATH = ROOT / "config/project_requirements.yaml"
STATUS_PATH = ROOT / "PROJECT_STATUS.md"
TRACE_PATH = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
FINAL_PATH = ROOT / "evidence/generated/p8e_final_summary.json"
PRECOMPLETION_PATH = ROOT / "evidence/generated/p8e_precompletion_reverification_summary.json"
PRECOMPLETION_MD_PATH = ROOT / "evidence/generated/p8e_precompletion_reverification_summary.md"

SCOPE = "PORTABLE_ARCHITECTURE_PASS / OFFLINE_ROUTED_IMPLEMENTATION"
FOLLOWUP = (
    "Z7020 board pins and board I/O timing remain PENDING_D12; real AXI DMA/DDR/cache, "
    "GLOBAL_PERMIT physical implementation, TFDU electrical/optical measurement, rotation, "
    "and final-product hardware acceptance remain pending their canonical later stages."
)

SPECS: dict[str, dict[str, Any]] = {
    "BUILD-001": {"text": "Z7010 and exact-part Z7020 use a common-source reproducible build matrix.",
                  "test": "P8E-DUAL-TARGET-BUILD-MATRIX", "evidence": "p8e_build_matrix_summary",
                  "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["config/p8e_build_matrix.yaml", "rtl/top/ir_endpoint_core.sv"]},
    "BUILD-002": {"text": "Fixed and rotating endpoint role wrappers remain thin consumers of one common core.",
                  "test": "P8E-SOURCE-MANIFEST-COMMON-CORE", "evidence": "p8e_source_manifest_summary",
                  "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["rtl/top/ir_fixed_endpoint_core.sv", "rtl/top/ir_rotating_endpoint_core.sv"]},
    "TIMING-001": {"text": "All formal core clocks have nonnegative routed setup and hold slack with zero TNS.",
                   "test": "P8E-DUAL-TARGET-BUILD-MATRIX", "evidence": "p8e_build_matrix_summary",
                   "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["scripts/vivado/run_p8e_build.tcl", "constraints/core/common_clocks.xdc"]},
    "TIMING-002": {"text": "The 64 MHz protocol/PHY target is preserved in every implementation profile.",
                   "test": "P8E-CANONICAL-BUILD-CONFIG", "evidence": "p8e_timing_architecture_summary",
                   "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["config/p8e_build_matrix.yaml", "config/p8e_clock_reset.yaml"]},
    "TIMING-003": {"text": "Routed implementation has zero unconstrained internal endpoints.",
                   "test": "P8E-CONSTRAINT-LINT", "evidence": "p8e_constraint_audit_summary",
                   "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["constraints/core/common_clocks.xdc", "scripts/check_p8e_constraints.py"]},
    "TIMING-004": {"text": "Timing closure is robust across the documented Default and Performance_Explore strategies.",
                   "test": "P8E-DUAL-TARGET-BUILD-MATRIX", "evidence": "p8e_build_matrix_summary",
                   "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["config/p8e_build_matrix.yaml", "scripts/run_p8e_build_matrix.py"]},
    "CDC-001": {"text": "All active CDC crossings are classified by the routed CDC and clock-interaction audits.",
                "test": "P8E-CDC-RDC-CLOSURE", "evidence": "p8e_cdc_rdc_summary",
                "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["config/p8e_clock_reset.yaml", "constraints/core/cdc_exceptions.xdc"]},
    "CDC-002": {"text": "Unsafe multi-bit direct CDC crossings are zero.",
                "test": "P8E-CDC-RDC-CLOSURE", "evidence": "p8e_cdc_rdc_summary",
                "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["rtl/common/toggle_handshake.sv", "rtl/common/async_fifo.sv"]},
    "CDC-003": {"text": "Reset deassertion is synchronized independently in each active clock domain.",
                "test": "P8E-CDC-RDC-CLOSURE", "evidence": "p8e_cdc_rdc_summary",
                "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["rtl/common/reset_sync.sv", "sim/tb/tb_p8e_cdc_reset_matrix.sv"]},
    "CDC-004": {"text": "Independent reset cannot commit a stale completion into the new generation.",
                "test": "P8E-DUAL-ENDPOINT-DIGITAL-SIM", "evidence": "p8e_dual_endpoint_sim_summary",
                "profile": "Z7020_DUAL_ENDPOINT_DIGITAL_LINK_SIM", "artifacts": ["sim/tb/tb_p8e_dual_endpoint.sv", "tools/p8e_dual_endpoint_reference.py"]},
    "RDC-001": {"text": "Reset-domain crossings are structurally audited and exercise independent recovery.",
                "test": "P8E-CDC-RDC-CLOSURE", "evidence": "p8e_cdc_rdc_summary",
                "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["config/p8e_clock_reset.yaml", "sim/tb/tb_p8e_cdc_reset_matrix.sv"]},
    "DRC-001": {"text": "Vivado REQP-1839 violations are zero without suppression or waiver.",
                "test": "P8E-RESET-BRAM-REQP1839", "evidence": "p8e_reset_bram_summary",
                "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["rtl/ir_shared_payload_store.sv", "rtl/ir_tfdu_exact_duty_accountant.sv"]},
    "DRC-002": {"text": "Critical DRC and critical methodology violations are zero.",
                "test": "P8E-DUAL-TARGET-BUILD-MATRIX", "evidence": "p8e_build_matrix_summary",
                "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["scripts/vivado/run_p8e_build.tcl", "scripts/run_p8e_build_matrix.py"]},
    "RESOURCE-001": {"text": "Exact-part Z7020 utilization remains below canonical resource limits.",
                     "test": "P8E-RESOURCE-MARGIN", "evidence": "p8e_resource_margin_summary",
                     "profile": "Z7020_FIXED_AND_ROTATING_CORE_OFFLINE", "artifacts": ["config/p8e_build_matrix.yaml", "rtl/ir_p8d_resource_tops.sv"]},
    "RESOURCE-002": {"text": "The Z7010 profile fits without deleting mandatory safety, CRC, SACK, or recovery semantics.",
                     "test": "P8E-RESOURCE-MARGIN", "evidence": "p8e_resource_margin_summary",
                     "profile": "Z7010_2LANE_DEV_IMPLEMENTATION", "artifacts": ["rtl/top/z7010_2lane_dev_top.sv", "rtl/ir_p8d_resource_tops.sv"]},
    "RESOURCE-003": {"text": "Resource margin is explicitly reported for every profile and implementation strategy.",
                     "test": "P8E-RESOURCE-MARGIN", "evidence": "p8e_resource_margin_summary",
                     "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["config/p8e_build_matrix.yaml"]},
    "AXIDMA-001": {"text": "A vendor-isolation AXI DMA interface adapter is statically integrated offline.",
                   "test": "P8E-AXI-DMA-STATIC-ADAPTER", "evidence": "p8e_axi_dma_static_integration_summary",
                   "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["rtl/platform/axi_dma_adapter.sv", "docs/design/P8E_AXI_DMA_STATIC_INTEGRATION.md"]},
    "AXIDMA-002": {"text": "AXI-Stream and descriptor contracts preserve TLAST, TKEEP, backpressure, completion, abort, and generation semantics.",
                   "test": "P8E-AXI-DMA-STATIC-ADAPTER", "evidence": "p8e_axi_dma_static_integration_summary",
                   "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["rtl/platform/axi_dma_adapter.sv", "sim/tb/tb_axi_dma_adapter.sv"]},
    "PROFILE-001": {"text": "The canonical Z7010 board XDC is isolated from every Z7020 profile.",
                    "test": "P8E-CONSTRAINT-LINT", "evidence": "p8e_constraint_audit_summary",
                    "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["constraints/active/PORT1.generated.xdc", "scripts/check_p8e_constraints.py"]},
    "PROFILE-002": {"text": "Unknown Z7020 board pins and board I/O timing remain PENDING_D12 and are not invented.",
                    "test": "P8E-Z7020-IO-BUDGET", "evidence": "p8e_io_budget_summary",
                    "profile": "Z7020_FIXED_AND_ROTATING_D12_INPUT", "artifacts": ["config/board_requirements/z7020_fixed_io_requirements.yaml", "config/board_requirements/z7020_rotating_io_requirements.yaml"]},
    "REPRO-001": {"text": "The clean-checkout batch implementation and evidence flow is reproducible and content-addressed.",
                  "test": "P8E-EVIDENCE-CONSISTENCY", "evidence": "p8e_evidence_consistency_summary",
                  "profile": "P8E_MULTI_PROFILE_OFFLINE", "artifacts": ["scripts/run_p8e_dual_target_gate.py", "scripts/run_p8e_build_matrix.py"]},
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def records(paths: list[str]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in paths:
        path = ROOT / item
        if not path.is_file():
            raise FileNotFoundError(item)
        result.append({"path": item, "sha256": sha256(path)})
    return result


def git_blob_sha256_candidates(commit: str, path: str) -> set[str]:
    blob = subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT)
    checkout_bytes = blob.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    return {hashlib.sha256(blob).hexdigest(), hashlib.sha256(checkout_bytes).hexdigest()}


def direct_reverification(requirement: dict[str, Any], verified_commit: str) -> dict[str, Any]:
    old_evidence = requirement.get("evidence_path")
    if not isinstance(old_evidence, str):
        raise RuntimeError(f"{requirement['requirement_id']} lacks prior evidence")
    basename = Path(old_evidence).name
    if requirement.get("verification_stage") == "P8D":
        candidate = ROOT / "evidence/generated/p8e_raw/r8d" / basename
        if not candidate.is_file():
            raise FileNotFoundError(candidate.relative_to(ROOT).as_posix())
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if payload.get("status") != "PASS" or payload.get("source_commit") != verified_commit:
            raise RuntimeError(
                f"{requirement['requirement_id']} P8D direct re-verification is not PASS at {verified_commit}"
            )
        checks = {"summary_status": "PASS"}
    elif requirement.get("verification_stage") == "P8C" and basename == "p8c_exact_sliding_duty_rtl_summary.json":
        matches = list((ROOT / "evidence/generated/p8e_raw/r8d").rglob(basename))
        if len(matches) != 1:
            raise RuntimeError(f"expected one isolated P8C exact-duty summary, found {len(matches)}")
        candidate = matches[0]
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        checks = {
            "reduced_exact_duty": payload.get("reduced", {}).get("status"),
            "full_scale_exact_duty": payload.get("full_scale", {}).get("status"),
            "rtl_python_trace": payload.get("trace_comparison", {}).get("status"),
        }
        if payload.get("source_commit") != verified_commit or set(payload.get("failures", [])) != {
            "parent_offline_provenance"
        } or any(value != "PASS" for value in checks.values()):
            raise RuntimeError(
                f"{requirement['requirement_id']} focused P8C exact-duty evidence is insufficient"
            )
    else:
        raise RuntimeError(
            f"no direct precompletion re-verification rule for {requirement['requirement_id']}"
        )
    return {
        "direct_evidence_path": candidate.relative_to(ROOT).as_posix(),
        "direct_evidence_sha256": sha256(candidate),
        "direct_evidence_status": "PASS",
        "checks": checks,
    }


def prepare_reverification(verified_commit: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", verified_commit):
        raise RuntimeError("--verified-source-commit must be a full lowercase Git commit")
    git("cat-file", "-e", f"{verified_commit}^{{commit}}")
    document = yaml.safe_load(REQ_PATH.read_text(encoding="utf-8"))
    affected: list[tuple[dict[str, Any], list[str], dict[str, Any]]] = []
    for requirement in document.get("requirements", []):
        if requirement.get("status") != "PASS":
            continue
        changed_paths: list[str] = []
        for artifact in requirement.get("artifact_hashes", []):
            item = artifact.get("path")
            if not isinstance(item, str) or item.startswith("evidence/") or not (ROOT / item).is_file():
                continue
            if artifact.get("sha256") != sha256(ROOT / item):
                if sha256(ROOT / item) not in git_blob_sha256_candidates(verified_commit, item):
                    raise RuntimeError(
                        f"{requirement['requirement_id']} current {item} differs from verified commit {verified_commit}"
                    )
                changed_paths.append(item)
        if changed_paths:
            affected.append((requirement, changed_paths,
                             direct_reverification(requirement, verified_commit)))
    if not affected:
        raise RuntimeError("no stale PASS artifact bindings require P8E precompletion re-verification")

    summary = {
        "schema_version": 1,
        "stage": "P8E_DUAL_TARGET_BUILD_CDC_RESOURCE_TIMING",
        "test_id": "P8E-PRECOMPLETION-DIRECT-REVERIFICATION",
        "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "status": "PASS",
        "verified_source_commit": verified_commit,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "scope": (
            "Direct current-source P8C exact-duty and P8D functional re-verification used only to refresh "
            "stale canonical PASS artifact bindings before the parent full regression. The failed parent "
            "provenance result is not promoted and must be closed by the final P8E full gate."
        ),
        "requirements": [
            {
                "requirement_id": requirement["requirement_id"],
                "status": "PASS",
                "changed_artifacts": records(changed_paths),
                **direct,
            }
            for requirement, changed_paths, direct in affected
        ],
    }
    PRECOMPLETION_PATH.parent.mkdir(parents=True, exist_ok=True)
    PRECOMPLETION_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8", newline="\n")
    PRECOMPLETION_MD_PATH.write_text(
        "# P8E Precompletion Direct Re-verification\n\n```json\n"
        + json.dumps(summary, indent=2, ensure_ascii=False) + "\n```\n",
        encoding="utf-8", newline="\n",
    )
    precompletion_rel = PRECOMPLETION_PATH.relative_to(ROOT).as_posix()
    precompletion_hash = sha256(PRECOMPLETION_PATH)
    for requirement, _changed_paths, _direct in affected:
        history = requirement.setdefault("reverification_history", [])
        previous = {
            "stage": "P8E_PRECOMPLETION",
            "previous_source_commit": requirement.get("source_commit"),
            "previous_evidence_path": requirement.get("evidence_path"),
            "previous_artifact_hash": requirement.get("artifact_hash"),
        }
        if not history or history[-1] != previous:
            history.append(previous)
        refreshed = []
        seen: set[str] = set()
        for artifact in requirement.get("artifact_hashes", []):
            item = artifact.get("path")
            if isinstance(item, str) and not item.startswith("evidence/") and (ROOT / item).is_file() and item not in seen:
                refreshed.append({"path": item, "sha256": sha256(ROOT / item)})
                seen.add(item)
        refreshed.append({"path": precompletion_rel, "sha256": precompletion_hash})
        requirement["artifact_hashes"] = refreshed
        requirement["artifact_hash"] = refreshed[0]["sha256"]
        requirement["evidence_path"] = precompletion_rel
        requirement["source_commit"] = verified_commit
        requirement["reverification_stage"] = "P8E_PRECOMPLETION"

    REQ_PATH.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
                        encoding="utf-8", newline="\n")
    TRACE_PATH.write_text(render_traceability(document), encoding="utf-8", newline="\n")
    print(f"P8E_PRECOMPLETION_REVERIFICATION=PASS")
    print(f"P8E_PRECOMPLETION_VERIFIED_SOURCE_COMMIT={verified_commit}")
    print(f"P8E_PRECOMPLETION_REQUIREMENT_COUNT={len(affected)}")


def refresh_existing_pass_hashes(document: dict[str, Any], source_commit: str) -> None:
    p8d_root = ROOT / "evidence/generated/p8e_raw/r8d"
    p8e_regression = "evidence/generated/p8e_p0_p8d_regression_summary.json"
    for requirement in document.get("requirements", []):
        if requirement.get("status") != "PASS":
            continue
        original_artifacts = requirement.get("artifact_hashes", [])
        changed_source = any(
            isinstance(artifact.get("path"), str)
            and not artifact["path"].startswith("evidence/")
            and (ROOT / artifact["path"]).is_file()
            and artifact.get("sha256") != sha256(ROOT / artifact["path"])
            for artifact in original_artifacts
        )
        p8d_reverified = requirement.get("verification_stage") == "P8D"
        prepared_reverification = requirement.get("reverification_stage") == "P8E_PRECOMPLETION"
        # Current P8D semantics were timing-refactored in P8E, so bind those
        # requirements to the isolated full current-source P8D rerun.
        if p8d_reverified:
            old = requirement.get("evidence_path")
            if isinstance(old, str):
                candidate = p8d_root / Path(old).name
                if candidate.is_file():
                    requirement["evidence_path"] = candidate.relative_to(ROOT).as_posix()
                    requirement["source_commit"] = source_commit
                    requirement["reverification_stage"] = "P8E"
        # Any earlier-stage requirement whose bound source changed needs fresh
        # current-source regression evidence.  Never pair a new artifact hash
        # with the historical source commit or its old generated summary.
        if (changed_source or prepared_reverification) and not p8d_reverified:
            requirement["evidence_path"] = p8e_regression
            requirement["source_commit"] = source_commit
            requirement["reverification_stage"] = "P8E"
        refreshed: list[dict[str, str]] = []
        seen: set[str] = set()
        for artifact in original_artifacts:
            item = artifact.get("path")
            if not isinstance(item, str):
                continue
            if p8d_reverified and item.startswith("evidence/generated/p8d_"):
                candidate = p8d_root / Path(item).name
                if candidate.is_file():
                    item = candidate.relative_to(ROOT).as_posix()
            elif (changed_source or prepared_reverification) and item.startswith("evidence/"):
                continue
            if (ROOT / item).is_file() and item not in seen:
                refreshed.append({"path": item, "sha256": sha256(ROOT / item)})
                seen.add(item)
        evidence = requirement.get("evidence_path")
        if isinstance(evidence, str) and (ROOT / evidence).is_file() and evidence not in seen:
            refreshed.append({"path": evidence, "sha256": sha256(ROOT / evidence)})
        if refreshed:
            requirement["artifact_hashes"] = refreshed
            requirement["artifact_hash"] = refreshed[0]["sha256"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit")
    parser.add_argument("--prepare-reverification", action="store_true")
    parser.add_argument("--verified-source-commit")
    args = parser.parse_args()
    if args.prepare_reverification:
        if not args.verified_source_commit:
            parser.error("--prepare-reverification requires --verified-source-commit")
        prepare_reverification(args.verified_source_commit)
        return 0
    source_commit = args.source_commit or git("rev-parse", "HEAD")
    final = json.loads(FINAL_PATH.read_text(encoding="utf-8"))
    if final.get("status") != "PASS" or final.get("source_commit") != source_commit:
        raise RuntimeError("P8E final PASS/source commit evidence is required before state promotion")
    if final.get("NO_HARDWARE_ACTIONS_EXECUTED") is not True or \
            final.get("CURRENT_RUN_HARDWARE_AUTHORIZATION") is not False:
        raise RuntimeError("P8E hardware-scope flags are not fail-closed")

    document = yaml.safe_load(REQ_PATH.read_text(encoding="utf-8"))
    refresh_existing_pass_hashes(document, source_commit)
    by_id = {item["requirement_id"]: item for item in document["requirements"]}
    for requirement_id, spec in SPECS.items():
        evidence_path = f"evidence/generated/{spec['evidence']}.json"
        artifact_paths = [*spec["artifacts"], evidence_path]
        artifact_records = records(artifact_paths)
        item = by_id.get(requirement_id)
        if item is None:
            item = {"requirement_id": requirement_id}
            document["requirements"].append(item)
            by_id[requirement_id] = item
        item.update({
            "requirement_text": spec["text"], "profile": spec["profile"],
            "verification_method": "Direct generated-config, XSIM, routed Vivado report, offline software, regression, and content-hash evidence.",
            "verification_stage": "P8E", "verification_scope": SCOPE,
            "test_id": spec["test"], "evidence_path": evidence_path,
            "source_commit": source_commit, "status": "PASS", "waiver": None,
            "artifact_hash": artifact_records[0]["sha256"],
            "artifact_hashes": artifact_records, "hardware_followup": FOLLOWUP,
        })

    REQ_PATH.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
                        encoding="utf-8", newline="\n")
    TRACE_PATH.write_text(render_traceability(document), encoding="utf-8", newline="\n")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    state.update({
        "state_revision": "P8E-1", "current_program_stage": "P9_Z7010_PLATFORM_LIMITED_HARDWARE_VALIDATION",
        "p8e_status": "PASS", "p8_portable_architecture_status": "PASS",
        "p9_status": "PENDING_CURRENT_RUN_AUTHORIZATION",
        "current_run_hardware_authorization": False, "p8e_no_hardware_actions_executed": True,
        "last_verified_commit": source_commit,
    })
    state["stage_status"]["P8E_DUAL_TARGET_BUILD_TIMING_CDC"] = "PASS"
    completed = [item for item in state.get("completed_gates", []) if item.get("gate_id") != "P8E"]
    completed.append({"gate_id": "P8E", "status": "PASS"})
    state["completed_gates"] = completed
    pending = [item for item in state.get("pending_gates", []) if item.get("gate_id") != "P8E"]
    if not any(item.get("gate_id") == "P9" for item in pending):
        pending.insert(0, {"gate_id": "P9", "status": "PENDING_CURRENT_RUN_AUTHORIZATION"})
    state["pending_gates"] = pending
    state["current_profiles"] = [
        {
            "profile": "Z7010_2LANE_DEV", "status": "PLATFORM_LIMITED_OFFLINE_IMPLEMENTATION_PASS",
            "active_profile_path": "board_profiles/ACTIVE_PROFILE.json",
            "pinmap_path": "board_profiles/ax7010_tfdu_j10_j11_pinmap.csv",
            "xdc_path": "constraints/active/PORT1.generated.xdc", "available_physical_lanes": 2,
        },
        {
            "profile": "Z7020_FIXED_8LANE_32MODULE_CORE", "status": "EXACT_PART_CORE_OFFLINE_PASS_HARDWARE_PENDING",
            "active_profile_path": None, "pinmap_path": None, "xdc_path": None,
            "available_physical_lanes": 8, "part": "xc7z020clg400-2", "board_inputs": "PENDING_D12",
        },
        {
            "profile": "Z7020_ROTATING_8LANE_CORE", "status": "EXACT_PART_CORE_OFFLINE_PASS_HARDWARE_PENDING",
            "active_profile_path": None, "pinmap_path": None, "xdc_path": None,
            "available_physical_lanes": 8, "part": "xc7z020clg400-2", "board_inputs": "PENDING_D12",
        },
    ]
    state["p8e_acceptance"] = {
        "status": "PASS", "profile": "P8E_MULTI_PROFILE_OFFLINE",
        "scope": SCOPE, "test_id": final["test_id"], "source_commit": source_commit,
        "evidence_path": "evidence/generated/p8e_final_summary.json",
        "evidence_sha256": sha256(FINAL_PATH),
        "artifact_manifest_path": "evidence/generated/p8e_raw/artifact_sha256_manifest.json",
        "artifact_manifest_sha256": sha256(ROOT / "evidence/generated/p8e_raw/artifact_sha256_manifest.json"),
        "build_matrix_path": "config/p8e_build_matrix.yaml", "build_matrix_sha256": sha256(ROOT / "config/p8e_build_matrix.yaml"),
        "clock_reset_path": "config/p8e_clock_reset.yaml", "clock_reset_sha256": sha256(ROOT / "config/p8e_clock_reset.yaml"),
        "hardware_actions_executed": False, "hardware_scope_promoted": False,
        "scope_exclusions": ["REAL_AXI_DMA_DDR", "Z7020_BOARD_IO", "Z7010_HARDWARE_RERUN",
            "GLOBAL_PERMIT_PHYSICAL_IMPLEMENTATION", "TFDU_EXTERNAL_MEASUREMENT",
            "ROTATION_HARDWARE", "FINAL_PRODUCT_HARDWARE"],
    }
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
    errors = validate_state(state, ROOT)
    if errors:
        raise RuntimeError("state validation failed: " + "; ".join(errors))
    STATUS_PATH.write_text(render_project_status(state), encoding="utf-8", newline="\n")
    print("P8E_MACHINE_STATE=PASS")
    print(f"P8E_REQUIREMENTS_UPDATED={len(SPECS)}")
    print(f"P8E_SOURCE_COMMIT={source_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
