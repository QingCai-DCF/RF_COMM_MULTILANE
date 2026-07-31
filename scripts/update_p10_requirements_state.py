#!/usr/bin/env python3
"""Close P10 canonical state from one immutable formal A-J hardware run."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from p8a_common import (
    P10_NEXT_STAGE,
    P10_REQUIREMENT_IDS,
    P10_SCOPE,
    P10_STAGE,
    render_project_status,
    render_traceability,
    validate_requirements,
    validate_state,
)

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "config/project_state.json"
REQ_PATH = ROOT / "config/project_requirements.yaml"
STATUS_PATH = ROOT / "PROJECT_STATUS.md"
TRACE_PATH = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
AUTH_PATH = ROOT / "config/p10_fasttrack_current_run_authorization.json"
GENERATED_SUMMARY = ROOT / "evidence/generated/p10_fasttrack_final_summary.json"
PROFILE = "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET"
FOLLOWUP = (
    "This PASS is limited to two stationary AX7020 endpoints, two optical lanes, "
    "lane masks at or below 0x3, and no Ethernet or motion. Ethernet, SPI, the "
    "physical GLOBAL_PERMIT D17 implementation, external TFDU duty measurement, "
    "handover, 8x32 hardware, 600 rpm operation, and product-final acceptance remain pending."
)

SPECS: dict[str, tuple[str, str, str]] = {
    "P10-HW-001": (
        "Role-bound fixed and rotating AX7020 artifacts complete safe boot and bounded shutdown.",
        "P10-A-HARDWARE",
        "p10_a",
    ),
    "P10-PHY-001": (
        "All four physical optical directions pass fresh raw-lane transfer and crosstalk isolation.",
        "P10-B-HARDWARE",
        "p10_b",
    ),
    "P10-PHY-002": (
        "Lane 0 and lane 1 each pass bidirectional 4 Mbit/s operation and concurrent 8 Mbit/s raw capability.",
        "P10-C-HARDWARE",
        "p10_c",
    ),
    "P10-L2-001": (
        "Selective repeat, 32-bit SACK, ACK aggregation, wrap, loss, reorder, duplicate, stale, and retry behavior pass.",
        "P10-D-HARDWARE",
        "p10_d",
    ),
    "P10-DMA-001": (
        "Both endpoints pass real AXI DMA scatter-gather, role-local DDR, cache ownership, reset, and descriptor accounting.",
        "P10-E-HARDWARE",
        "p10_e",
    ),
    "P10-SYS-001": (
        "Two independent PS runtimes and resets operate without shared RAM across the optical PS-PL-PHY-PL-PS path.",
        "P10-F-HARDWARE",
        "p10_f",
    ),
    "P10-OBJ-001": (
        "Fresh fixed-to-rotating and rotating-to-fixed objects preserve CRC32, SHA-256, and atomic exactly-once publication.",
        "P10-F-HARDWARE",
        "p10_f",
    ),
    "P10-REC-001": (
        "Endpoint reboot and reset recovery reject stale completion and deliver a fresh post-recovery object.",
        "P10-G-HARDWARE",
        "p10_g",
    ),
    "P10-SCHED-001": (
        "Lane selection, equal weighting, lane fault isolation, retry migration, and acknowledged-frame immobility pass.",
        "P10-H-HARDWARE",
        "p10_h",
    ),
    "P10-PERF-001": (
        "P10 characterizes PHY, frame, application, DMA, PS, and airtime performance without promoting the final-product threshold.",
        "P10-I-HARDWARE",
        "p10_i",
    ),
    "P10-SOAK-001": (
        "The single formal stationary two-lane run remains clean for at least 1800 active seconds with no Ethernet or motion.",
        "P10-J-HARDWARE",
        "p10_j",
    ),
    "P10-EVID-001": (
        "One complete formal A-J run has consistent summaries, raw logs, SHA-256 manifest, and double final shutdown evidence.",
        "P10-FASTTRACK-FINAL",
        "final",
    ),
}

EXTRA_BINDINGS: dict[str, tuple[str, ...]] = {
    "P10-HW-001": ("config/p10_fasttrack_current_run_authorization.json",),
    "P10-SYS-001": ("evidence/generated/p10_dual_endpoint_architecture_audit.json",),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def full_commit(value: str) -> str:
    commit = subprocess.check_output(
        ["git", "rev-parse", f"{value}^{{commit}}"], cwd=ROOT, text=True
    ).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise RuntimeError(f"not a full Git commit: {value}")
    return commit


def record(path: Path) -> dict[str, str]:
    return {
        "path": path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "sha256": sha256(path),
    }


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


def verify_manifest(run_root: Path, manifest: dict[str, Any]) -> None:
    if manifest.get("status") != "PASS" or manifest.get("test_id") != "P10-EVIDENCE-MANIFEST":
        raise RuntimeError("P10 run evidence manifest is not PASS")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) < 1:
        raise RuntimeError("P10 run evidence manifest has no files")
    for entry in files:
        path = run_root / str(entry.get("path", ""))
        if not path.is_file() or sha256(path) != entry.get("sha256"):
            raise RuntimeError(f"P10 run evidence manifest mismatch: {entry.get('path')}")


def require_formal_pass(run_root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    final_path = run_root / "final/orchestrator_result.json"
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    final = json.loads(final_path.read_text(encoding="utf-8"))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    auth = json.loads(AUTH_PATH.read_text(encoding="utf-8"))
    required_gates = {
        "F_R_BUILD_ROLE_SAFE_BOOT_SHUTDOWN",
        "FOUR_DIRECTION_RAW",
        "LANE0_4MBPS",
        "LANE1_4MBPS",
        "TWO_LANE_8MBPS_RAW",
        "SELECTIVE_REPEAT_SACK",
        "DMA_DDR_CACHE_FIXED",
        "DMA_DDR_CACHE_ROTATING",
        "DUAL_INDEPENDENT_PS",
        "F_TO_R_OBJECT",
        "R_TO_F_OBJECT",
        "ENDPOINT_REBOOT_RECOVERY",
        "SCHEDULER_LANE_FAULT",
        "PERFORMANCE",
        "STATIONARY_30MIN",
    }
    if final.get("status") != "PASS" or final.get("formal_campaign") is not True:
        raise RuntimeError("P10 final summary is not one formal PASS campaign")
    if final.get("campaign_errors") != []:
        raise RuntimeError("P10 final summary contains campaign errors")
    if set(final.get("stage_status", {})) != {f"P10-{letter}" for letter in "ABCDEFGHIJ"}:
        raise RuntimeError("P10 final summary does not contain exactly stages A-J")
    if any(value != "PASS" for value in final["stage_status"].values()):
        raise RuntimeError("one or more P10 stages are not PASS")
    gates = final.get("mandatory_gates", {})
    if not required_gates.issubset(gates) or any(gates[name] != "PASS" for name in required_gates):
        raise RuntimeError("one or more P10 mandatory gates are not PASS")
    expected = {
        "SHUTDOWN_FIXED": "PASS",
        "SHUTDOWN_ROTATING": "PASS",
        "hardware_actions_executed": True,
        "network_used": False,
        "hardware_movement": False,
        "rotation_executed": False,
        "rewiring_executed": False,
        "maximum_lane_mask_used": "0x3",
    }
    for key, value in expected.items():
        if final.get(key) != value:
            raise RuntimeError(f"P10 final summary {key} mismatch")
    if final.get("run_id") != auth.get("run_id") or final.get("source_commit") != auth.get("source_commit"):
        raise RuntimeError("P10 final summary does not match immutable authorization")
    if manifest.get("run_id") != final.get("run_id"):
        raise RuntimeError("P10 evidence manifest run_id mismatch")
    verify_manifest(run_root, manifest)
    return final, manifest, auth


def update_profile(state: dict[str, Any], role: str, serial: str) -> None:
    profile_id = f"P10_AX7020_{'FIXED' if role == 'fixed' else 'ROTATING'}_2LANE"
    stem = "ax7020_fixed_2lane" if role == "fixed" else "ax7020_rotating_2lane"
    item = next(
        (entry for entry in state["current_profiles"] if entry.get("profile") == profile_id),
        None,
    )
    if item is None:
        item = {"profile": profile_id}
        state["current_profiles"].append(item)
    item.update(
        {
            "status": "SCOPED_STATIONARY_2LANE_HARDWARE_PASS",
            "active_profile_path": f"board_profiles/{stem}/profile.yaml",
            "pinmap_path": f"board_profiles/{stem}/pinmap.csv",
            "xdc_path": f"board_profiles/{stem}/{stem}.generated.xdc",
            "available_physical_lanes": 2,
            "part": "xc7z020clg400-2",
            "jtag_cable_serial": serial,
            "board_document_status": "REFERENCE_PASS_PHYSICAL_REVISION_GAPS_NONBLOCKING",
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--evidence-commit", default="HEAD")
    args = parser.parse_args(argv)

    evidence_commit = full_commit(args.evidence_commit)
    run_root = ROOT / "evidence/hardware/p10" / args.run_id
    if not run_root.is_dir():
        raise RuntimeError("P10 formal run directory is missing")
    final, manifest, auth = require_formal_pass(run_root)
    if args.run_id != final["run_id"]:
        raise RuntimeError("--run-id does not match P10 final summary")

    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    document = yaml.safe_load(REQ_PATH.read_text(encoding="utf-8"))
    document["document_version"] = "8.0"

    state["state_revision"] = "P10-AX7020-DUAL-NODE-2LANE-CLOSEOUT-1"
    state["p10_status"] = "PASS"
    state["stage_status"][P10_STAGE] = "PASS"
    state["current_program_stage"] = P10_NEXT_STAGE
    state["current_run_hardware_authorization"] = False
    state["last_hardware_authorization_consumed"] = True
    state["last_verified_commit"] = evidence_commit
    update_profile(state, "fixed", auth["fixed_board"]["serial"])
    update_profile(state, "rotating", auth["rotating_board"]["serial"])

    state["completed_gates"] = [
        item for item in state.get("completed_gates", []) if item.get("gate_id") != "P10"
    ]
    state["completed_gates"].append({"gate_id": "P10", "status": "PASS"})
    state["pending_gates"] = [
        item for item in state.get("pending_gates", []) if item.get("gate_id") != "P10"
    ]

    auth_commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", AUTH_PATH.relative_to(ROOT).as_posix()],
        cwd=ROOT,
        text=True,
    ).strip()
    state["p10_current_run_authorization"] = {
        "status": "CONSUMED_AFTER_P10_ACCEPTANCE",
        "path": AUTH_PATH.relative_to(ROOT).as_posix(),
        "sha256": sha256(AUTH_PATH),
        "authorization_commit": auth_commit,
        "consumed": True,
        "consumed_by_run_id": args.run_id,
        "reusable_for_future_run": False,
    }

    final_path = run_root / "final/orchestrator_result.json"
    manifest_path = run_root / "final/run_evidence_sha256_manifest.json"
    unchanged_pending = {
        "ETHERNET": "DEFERRED_NO_NETWORK_CABLE",
        "SPI": "PENDING",
        "PHYSICAL_GLOBAL_PERMIT": "PENDING_D17",
        "EXTERNAL_TFDU_DUTY": "PENDING_EXTERNAL_MEASUREMENT",
        "HANDOVER": "PENDING_P11",
        "8X32": "PENDING_P12",
        "600RPM": "PENDING_P13",
        "PRODUCT_FINAL": "PENDING",
    }
    state["p10_acceptance"] = {
        "status": "PASS",
        "profile": PROFILE,
        "scope": P10_SCOPE,
        "test_id": "P10-FASTTRACK-FINAL",
        "run_id": args.run_id,
        "source_commit": final["source_commit"],
        "formal_evidence_freeze_commit": evidence_commit,
        "evidence_checkpoint_tag": "p10-ax7020-dual-node-2lane-pass",
        "evidence_path": final_path.relative_to(ROOT).as_posix(),
        "evidence_sha256": sha256(final_path),
        "evidence_manifest_path": manifest_path.relative_to(ROOT).as_posix(),
        "evidence_manifest_sha256": sha256(manifest_path),
        "evidence_manifest_file_count": len(manifest["files"]),
        "generated_summary_path": GENERATED_SUMMARY.relative_to(ROOT).as_posix(),
        "generated_summary_sha256": sha256(GENERATED_SUMMARY),
        "fixed_board_id": final["fixed_board_id"],
        "rotating_board_id": final["rotating_board_id"],
        "hardware_actions_executed": True,
        "network_used": False,
        "no_hardware_movement": True,
        "rotation_executed": False,
        "rewiring_executed": False,
        "maximum_lane_mask_used": "0x3",
        "shutdown_fixed": "PASS",
        "shutdown_rotating": "PASS",
        "application_goodput_f_to_r_bps": final["application_goodput_f_to_r_bps"],
        "application_goodput_r_to_f_bps": final["application_goodput_r_to_f_bps"],
        "mandatory_claims": {
            "P10_AX7020_DUAL_NODE_2LANE_NO_ETHERNET": "PASS",
            "DUAL_Z7020_INDEPENDENT_ENDPOINTS": "PASS",
            "DUAL_Z7020_2LANE_OPTICAL_LINK": "PASS",
            "DUAL_Z7020_PS_PL_PHY_PL_PS": "PASS",
            "STATIONARY_2LANE_30MIN": "PASS",
        },
        "unchanged_pending_scopes": unchanged_pending,
        "scope_exclusions": [
            "ETHERNET",
            "SPI",
            "PHYSICAL_GLOBAL_PERMIT_D17",
            "EXTERNAL_TFDU_DUTY_MEASUREMENT",
            "HANDOVER",
            "EIGHT_LANE_8X32",
            "ROTATION_600RPM",
            "PRODUCT_FINAL",
        ],
    }

    by_id = {item["requirement_id"]: item for item in document["requirements"]}
    for req_id, (text, test_id, stage_dir) in SPECS.items():
        if stage_dir == "final":
            evidence_path = final_path
        else:
            evidence_path = run_root / "stages" / stage_dir / "stage_summary.json"
            stage = json.loads(evidence_path.read_text(encoding="utf-8"))
            if stage.get("status") != "PASS" or stage.get("test_id") != test_id:
                raise RuntimeError(f"P10 stage evidence is not a matching PASS: {req_id}")
        binding_paths = [
            evidence_path,
            final_path,
            manifest_path,
            *(ROOT / path for path in EXTRA_BINDINGS.get(req_id, ())),
        ]
        bindings = []
        seen_paths: set[Path] = set()
        for binding_path in binding_paths:
            resolved = binding_path.resolve()
            if resolved not in seen_paths:
                bindings.append(record(binding_path))
                seen_paths.add(resolved)
        item = by_id.get(req_id)
        if item is None:
            item = {"requirement_id": req_id}
            document["requirements"].append(item)
            by_id[req_id] = item
        item.update(
            {
                "requirement_text": text,
                "profile": PROFILE,
                "verification_method": (
                    "Fresh direct dual-AX7020/JTAG/AXI-DMA/DDR/optical evidence "
                    "from one immutable formal P10 A-J run, bound to the "
                    "role-separated architecture and authorization artifacts."
                ),
                "verification_stage": "P10",
                "verification_scope": P10_SCOPE,
                "test_id": test_id,
                "evidence_path": evidence_path.relative_to(ROOT).as_posix(),
                "status": "PASS",
                "waiver": None,
                "artifact_hash": bindings[0]["sha256"],
                "artifact_hashes": bindings,
                "hardware_followup": FOLLOWUP,
            }
        )

    if set(SPECS) != P10_REQUIREMENT_IDS:
        raise RuntimeError("P10 requirement specification set is incomplete")
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    STATUS_PATH.write_text(render_project_status(state), encoding="utf-8", newline="\n")
    refresh_pass_hashes(document)
    REQ_PATH.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=True, width=120),
        encoding="utf-8",
        newline="\n",
    )
    TRACE_PATH.write_text(render_traceability(document), encoding="utf-8", newline="\n")

    errors = validate_state(state, ROOT) + validate_requirements(document, ROOT)
    if errors:
        raise RuntimeError("P10 canonical closeout validation failed:\n" + "\n".join(errors))
    print("P10_MACHINE_STATE=PASS")
    print(f"P10_REQUIREMENTS_UPDATED={len(SPECS)}")
    print(f"P10_RUN_ID={args.run_id}")
    print(f"P10_SOURCE_COMMIT={final['source_commit']}")
    print(f"P10_FORMAL_EVIDENCE_FREEZE_COMMIT={evidence_commit}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
