#!/usr/bin/env python3
"""Consolidate final P10 offline build evidence without touching hardware."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GOAL = ROOT / "goals/P10_FASTTRACK_MIDRUN_OVERRIDE_CONCISE.md"
GOAL_SHA256 = "b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603"
BRANCH = "p10/ax7020-dual-node-2lane"
INPUTS = {
    "preflight": ROOT / "evidence/generated/p10_fasttrack_concise_preflight.json",
    "regression": ROOT / "evidence/generated/p10_dual_endpoint_regression/summary.json",
    "shutdown": ROOT / "evidence/generated/p10_ax7020_shutdown_build_summary.json",
    "functional": ROOT / "evidence/generated/p10_ax7020_functional_build_summary.json",
    "runtime": ROOT / "evidence/generated/p10_ax7020_ps_runtime_build_summary.json",
    "blocker": ROOT / "evidence/generated/p10_severe_hardware_blocker.json",
}
ARCH_DOC = ROOT / "docs/hardware/P10_AX7020_DUAL_ENDPOINT_ARCHITECTURE.md"
ARCH_JSON = ROOT / "evidence/generated/p10_dual_endpoint_architecture_audit.json"
ARCH_MD = ROOT / "evidence/generated/p10_dual_endpoint_architecture_audit.md"
MANIFEST_JSON = ROOT / "evidence/generated/p10_offline_artifact_manifest.json"
FINAL_JSON = ROOT / "evidence/generated/p10_fasttrack_final_summary.json"
FINAL_MD = ROOT / "evidence/generated/p10_fasttrack_final_summary.md"
NO_HW_LOG = ROOT / "evidence/generated/p10_final_no_hardware_static_scan.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def is_ancestor(reference: str, head: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", reference, head], cwd=ROOT,
        text=True, capture_output=True, check=False,
    ).returncode == 0


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def artifact_records(inputs: dict[str, dict[str, Any]], errors: list[str]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    def add(kind: str, role: str, record: dict[str, Any]) -> None:
        path = ROOT / record.get("path", "__missing__")
        expected = record.get("sha256")
        require(path.is_file(), f"missing {kind} artifact for {role}: {path}", errors)
        actual = sha256(path) if path.is_file() else None
        require(actual == expected, f"{kind} hash mismatch for {role}", errors)
        records.append({
            "kind": kind,
            "role": role,
            "path": record.get("path"),
            "sha256": expected,
            "bytes": path.stat().st_size if path.is_file() else None,
            "verified": path.is_file() and actual == expected,
        })

    for role in inputs["shutdown"].get("roles", []):
        if role.get("artifact"):
            add("shutdown_bitstream", role["role"], role["artifact"])
    for role in inputs["functional"].get("roles", []):
        for name, record in role.get("artifacts", {}).items():
            add("functional_bitstream" if name == "bitstream" else "xsa",
                role["role"], record)
    for role in inputs["runtime"].get("roles", []):
        for name, record in role.get("artifacts", {}).items():
            add(name, role["role"], record)
    return records


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
            "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        print("P10_EVIDENCE_REFUSED: offline environment required", file=sys.stderr)
        return 2
    require(GOAL.is_file() and sha256(GOAL) == GOAL_SHA256,
            "fast-track goal hash mismatch", errors)
    require(git("branch", "--show-current") == BRANCH, "branch mismatch", errors)
    source_commit = git("rev-parse", "HEAD")
    require(is_ancestor("main", source_commit), "main is not an ancestor", errors)
    require(is_ancestor("p8e-pass", source_commit), "p8e-pass is not an ancestor", errors)
    require(is_ancestor("p9-z7010-2lane-pass", source_commit),
            "p9-z7010-2lane-pass is not an ancestor", errors)
    require(ARCH_DOC.is_file(), "architecture document missing", errors)
    for name, path in INPUTS.items():
        require(path.is_file(), f"missing input summary: {name}", errors)
    if errors:
        for error in errors:
            print(f"P10_EVIDENCE_ERROR: {error}", file=sys.stderr)
        return 1

    no_hw = subprocess.run(
        [sys.executable, "scripts/check_no_hardware_calls.py"], cwd=ROOT,
        text=True, capture_output=True, timeout=120,
        env={**os.environ, "NO_HARDWARE": "1",
             "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
    )
    no_hw_text = (
        f"RETURN_CODE={no_hw.returncode}\nSTDOUT_BEGIN\n{no_hw.stdout}\nSTDOUT_END\n"
        f"STDERR_BEGIN\n{no_hw.stderr}\nSTDERR_END\n"
    )
    NO_HW_LOG.write_text(no_hw_text, encoding="utf-8", errors="replace", newline="\n")
    require(no_hw.returncode == 0 and "NO_HARDWARE_ACTIONS_EXECUTED=1" in no_hw.stdout,
            "final no-hardware static scan failed", errors)

    inputs = {name: load(path) for name, path in INPUTS.items()}
    for name in ("regression", "shutdown", "functional", "runtime"):
        summary = inputs[name]
        require(summary.get("status") == "PASS", f"{name} status is not PASS", errors)
        require(summary.get("source_commit") == source_commit,
                f"{name} source commit mismatch", errors)
        require(summary.get("source_worktree_dirty") is False,
                f"{name} was generated from tracked-dirty source", errors)
        require(summary.get("hardware_actions_executed") is False,
                f"{name} reports a hardware action", errors)
    require(inputs["preflight"].get("status") == "PASS", "preflight is not PASS", errors)
    require(inputs["preflight"].get("ancestors", {}).get("main") is True,
            "main is not an ancestor", errors)
    require(inputs["preflight"].get("ancestors", {}).get("p8e-pass") is True,
            "p8e-pass is not an ancestor", errors)
    require(inputs["preflight"].get("ancestors", {}).get("p9-z7010-2lane-pass") is True,
            "p9-z7010-2lane-pass is not an ancestor", errors)
    require(inputs["blocker"].get("blocking_condition") == "P10-SAFETY-POWERUP-001",
            "severe blocker identity mismatch", errors)

    regression = {item["test_id"]: item for item in inputs["regression"].get("results", [])}
    for test_id in (
        "P10-RTL-DUAL-INDEPENDENT-ENDPOINT",
        "P10-REGRESSION-P9-LEGACY-MONOLITHIC",
        "P10-REGRESSION-P9-RUNNER-UNIT",
        "P10-REGISTER-MAP-SINGLE-SOURCE-VERIFY",
    ):
        require(regression.get(test_id, {}).get("status") == "PASS",
                f"missing/failing regression {test_id}", errors)

    functional_roles = {item["role"]: item for item in inputs["functional"].get("roles", [])}
    runtime_roles = {item["role"]: item for item in inputs["runtime"].get("roles", [])}
    shutdown_roles = {item["role"]: item for item in inputs["shutdown"].get("roles", [])}
    for role, value in (("fixed", "1"), ("rotating", "2")):
        require(functional_roles.get(role, {}).get("markers", {}).get("P10_ENDPOINT_ROLE_VALUE") == value,
                f"functional role binding mismatch: {role}", errors)
        require(runtime_roles.get(role, {}).get("role_value") == int(value),
                f"runtime role binding mismatch: {role}", errors)
        require(shutdown_roles.get(role, {}).get("status") == "PASS",
                f"shutdown build missing: {role}", errors)
    records = artifact_records(inputs, errors)
    require(len(records) == 10, f"expected 10 frozen artifacts, got {len(records)}", errors)
    require(len({item["path"] for item in records}) == len(records),
            "artifact paths are not unique", errors)

    source_checks = {
        "role_separated_wrapper": "ENDPOINT_ROLE" in (
            ROOT / "rtl/p10_axi_dma_endpoint_peripheral_bd.v").read_text(encoding="utf-8"),
        "two_endpoint_testbench": all(token in (
            ROOT / "sim/tb/tb_p10_dual_endpoint_pair.sv").read_text(encoding="utf-8")
            for token in ("fixed_endpoint", "rotating_endpoint")),
        "local_dma_per_xsa": all(
            role.get("xsa_audit", {}).get("checks", {}).get("dma_base") is True
            for role in functional_roles.values()),
        "ethernet_disabled": all(
            role.get("xsa_audit", {}).get("checks", {}).get("ethernet_disabled") is True
            for role in functional_roles.values()),
        "role_build_ids_differ": functional_roles.get("fixed", {}).get("markers", {}).get(
            "P10_ENDPOINT_ROLE_VALUE") != functional_roles.get("rotating", {}).get(
            "markers", {}).get("P10_ENDPOINT_ROLE_VALUE"),
        "runtime_artifacts_role_distinct": runtime_roles.get("fixed", {}).get(
            "artifacts", {}).get("elf", {}).get("sha256") != runtime_roles.get(
            "rotating", {}).get("artifacts", {}).get("elf", {}).get("sha256"),
    }
    for name, passed in source_checks.items():
        require(passed, f"architecture source check failed: {name}", errors)

    if errors:
        for error in errors:
            print(f"P10_EVIDENCE_ERROR: {error}", file=sys.stderr)
        return 1

    generated_at = datetime.now(timezone.utc).isoformat()
    current_paths = {item["path"] for item in records}
    superseded = []
    for path in sorted(p for p in (ROOT / "artifacts/p10").rglob("*") if p.is_file()):
        relative = rel(path)
        if relative not in current_paths:
            superseded.append({
                "path": relative,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "classification": "SUPERSEDED_INTERMEDIATE_OFFLINE_ARTIFACT_NOT_AUTHORIZED",
            })
    manifest = {
        "schema_version": 1,
        "manifest_id": "P10-OFFLINE-CONTENT-ADDRESSED-ARTIFACTS",
        "status": "PASS",
        "generated_at_utc": generated_at,
        "source_commit": source_commit,
        "hardware_actions_executed": False,
        "artifacts": records,
        "superseded_intermediate_artifacts": superseded,
    }
    MANIFEST_JSON.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                             encoding="utf-8", newline="\n")

    architecture = {
        "schema_version": 1,
        "test_id": "P10-DUAL-INDEPENDENT-ENDPOINT-ARCHITECTURE-AUDIT",
        "status": "PASS",
        "scope": "OFFLINE_RTL_SIMULATION_AND_ROLE_BOUND_BUILD_ONLY",
        "generated_at_utc": generated_at,
        "source_commit": source_commit,
        "source_worktree_dirty": False,
        "hardware_actions_executed": False,
        "hardware_scope_promoted": False,
        "requirement": {
            "requirement_id": "SYS-ARCH-001",
            "canonical_status": "PENDING",
            "offline_design_evidence": "PASS",
            "hardware_followup": "PENDING_P10_REMEDIATION_AND_HARDWARE_RUN",
        },
        "role_binding": {
            "fixed": {"logical_board_id": "AX7020-F", "deployment_role": 1,
                      "modules": ["F0", "F1"]},
            "rotating": {"logical_board_id": "AX7020-R", "deployment_role": 2,
                         "modules": ["R0", "R1"]},
        },
        "lanes": {"lane0": "F0-R0", "lane1": "F1-R1"},
        "independent_local_resources": [
            "PS", "DDR controller and DDR", "scatter-gather AXI DMA",
            "descriptor/session/retry state", "payload storage", "two TFDU paths",
        ],
        "cross_node_transport": "OPTICAL_DATA_AND_ACK_FRAMES_ONLY",
        "shared_ram": False,
        "ethernet": False,
        "source_checks": source_checks,
        "final_no_hardware_static_scan": {
            "status": "PASS",
            "path": rel(NO_HW_LOG),
            "sha256": sha256(NO_HW_LOG),
        },
        "portable_regression": rel(INPUTS["regression"]),
        "functional_build": rel(INPUTS["functional"]),
        "runtime_build": rel(INPUTS["runtime"]),
        "artifact_manifest": rel(MANIFEST_JSON),
        "artifact_manifest_sha256": sha256(MANIFEST_JSON),
        "architecture_document": rel(ARCH_DOC),
        "architecture_document_sha256": sha256(ARCH_DOC),
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "limitations": [
            "No physical fixed/rotating board identity was bound.",
            "No FPGA was programmed and no ELF was run.",
            "No real DDR, DMA, optical, reset-recovery, throughput, or duration result exists.",
            "No passive power-up Txd-low/SD-high guarantee is established.",
        ],
    }
    ARCH_JSON.write_text(json.dumps(architecture, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8", newline="\n")
    ARCH_MD.write_text(
        "# P10 dual-independent-endpoint architecture audit\n\n"
        "- Scoped result: `PASS` (`OFFLINE_RTL_SIMULATION_AND_ROLE_BOUND_BUILD_ONLY`)\n"
        "- `SYS-ARCH-001`: remains `PENDING` for physical dual-node evidence.\n"
        "- Fixed role: `AX7020-F`, `DEPLOYMENT_ROLE=1`, F0/F1.\n"
        "- Rotating role: `AX7020-R`, `DEPLOYMENT_ROLE=2`, R0/R1.\n"
        "- No shared RAM or Ethernet path exists between endpoint instances.\n"
        "- Portable P10 and legacy P9 regressions: `PASS`.\n"
        "- Fixed/rotating functional bit/XSA and BSP/ELF builds: `PASS`.\n"
        "- Hardware actions executed: `false`.\n"
        "- Hardware admission: `false` (`P10-SAFETY-POWERUP-001`).\n\n"
        f"Artifact manifest: `{rel(MANIFEST_JSON)}` (`{sha256(MANIFEST_JSON)}`)\n",
        encoding="utf-8", newline="\n")

    mandatory = {
        "four_direction_raw": "NOT_RUN_SEVERE_BLOCKER",
        "lane0_4mbps": "NOT_RUN_SEVERE_BLOCKER",
        "lane1_4mbps": "NOT_RUN_SEVERE_BLOCKER",
        "two_lane_8mbps_raw": "NOT_RUN_SEVERE_BLOCKER",
        "selective_repeat_sack": "PASS_OFFLINE_SIMULATION_ONLY_HARDWARE_NOT_RUN",
        "dma_ddr_cache_fixed": "NOT_RUN_SEVERE_BLOCKER",
        "dma_ddr_cache_rotating": "NOT_RUN_SEVERE_BLOCKER",
        "dual_independent_ps": "PASS_OFFLINE_BUILD_ONLY_HARDWARE_NOT_RUN",
        "no_shared_ram": "PASS_OFFLINE_ARCHITECTURE_AND_SIMULATION_HARDWARE_NOT_RUN",
        "f_to_r_object": "NOT_RUN_SEVERE_BLOCKER",
        "r_to_f_object": "NOT_RUN_SEVERE_BLOCKER",
        "object_sha256": "NONE_NO_HARDWARE_RUN",
        "endpoint_reboot_recovery": "NOT_RUN_SEVERE_BLOCKER",
        "stationary_30min": "NOT_RUN_SEVERE_BLOCKER",
        "application_goodput_f_to_r_bps": "NOT_MEASURED_NO_HARDWARE_RUN",
        "application_goodput_r_to_f_bps": "NOT_MEASURED_NO_HARDWARE_RUN",
        "shutdown_fixed": "NOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS",
        "shutdown_rotating": "NOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS",
    }
    generated_evidence = [
        rel(INPUTS["preflight"]), rel(INPUTS["regression"]),
        rel(INPUTS["shutdown"]), rel(INPUTS["functional"]),
        rel(INPUTS["runtime"]), rel(ARCH_JSON), rel(ARCH_MD),
        rel(MANIFEST_JSON), rel(INPUTS["blocker"]), rel(NO_HW_LOG),
        rel(FINAL_MD), rel(FINAL_JSON),
    ]
    final = {
        "schema_version": 2,
        "test_id": "P10-FASTTRACK-FINAL-SUMMARY",
        "generated_at_utc": generated_at,
        "stage": "P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET",
        "status": "PARTIAL",
        "source_commit": source_commit,
        "evidence_checkpoint": "COMMIT_CONTAINING_THIS_SUMMARY",
        "tag": None,
        "branch": BRANCH,
        "worktree": str(ROOT),
        "worktree_clean_after_evidence_commit_expected": True,
        "wiring_already_confirmed": True,
        "current_run_hardware_authorization": True,
        "offline_build_environment": {"NO_HARDWARE": 1,
                                      "CURRENT_RUN_HARDWARE_AUTHORIZATION": False},
        "hardware_actions_executed": False,
        "network_used": False,
        "no_hardware_movement": True,
        "max_lane_mask_used": "NONE_NO_HARDWARE_RUN",
        "allowed_lane_masks": ["0x1", "0x2", "0x3"],
        "fixed_board_id": "PENDING_PHYSICAL_ROLE_BINDING",
        "rotating_board_id": "PENDING_PHYSICAL_ROLE_BINDING",
        "logical_image_roles": {"fixed": "AX7020-F", "rotating": "AX7020-R"},
        "hardware_admission": False,
        "blocking_condition": "P10-SAFETY-POWERUP-001",
        "mandatory_results": mandatory,
        "offline_pass": [
            "Repository/main/P8E/P9 ancestry and concise preflight",
            "Confirmed independent AX7020 J10 wiring profiles and XDCs",
            "Two-instance dual-endpoint RTL simulation including both directions, both lanes, SACK, wrap, and retry",
            "Legacy P9 transport and P9 runner regressions",
            "Register-map P9-3 single-source verification",
            "Fixed and rotating shutdown bitstream builds",
            "Fixed and rotating functional synthesis/route/timing/DRC/CDC-severity builds",
            "Role-bound fixed and rotating XSA/BSP/ELF builds",
            "Offline independent-node/no-shared-RAM architecture audit",
        ],
        "fail": [
            "P10-SAFETY-POWERUP-001: passive Txd-low and SD-high are not established for unconfigured/reset/open/partial-power states",
            "P10-RX-B-R29-001: J10-26/U13 1-kohm pull-down exceeds the supplied TFDU VOH guaranteed test load",
            "Physical board/module revision identity and unique F/R JTAG binding remain unverified",
            "All mandatory hardware acceptance stages are not run",
        ],
        "nonblocking_extensions": "NOT_RUN_BECAUSE_MANDATORY_HARDWARE_ADMISSION_FAILED",
        "generated_evidence": generated_evidence,
        "unchanged_pending_scopes": [
            "ETHERNET: DEFERRED", "SPI: PENDING",
            "PHYSICAL_GLOBAL_PERMIT: PENDING_D17", "EXTERNAL_TFDU_DUTY: PENDING",
            "HANDOVER: PENDING_P11", "8X32: PENDING_P12", "600RPM: PENDING_P13",
            "PRODUCT_FINAL: PENDING",
        ],
        "required_user_resolution": [
            "Provide as-built evidence and component values proving a passive pull-down on every Txd and passive pull-up on every SD, including any existing harness bias; or authorize a documented fail-safe hardware revision/rewire.",
            "Resolve or electrically validate the J10-26/U13 Rxd 1-kohm pull-down against the exact TFDU small-board output.",
            "Provide physical revision/marking evidence that uniquely binds AX7020-F and AX7020-R before any programming.",
        ],
        "next_recommended_stage": "P10_REMEDIATION",
    }
    FINAL_JSON.write_text(json.dumps(final, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8", newline="\n")
    FINAL_MD.write_text(
        "# P10 fast-track final summary\n\n"
        "```text\n"
        "P10_FASTTRACK_AX7020_DUAL_NODE_2LANE_NO_ETHERNET:\nPARTIAL\n\n"
        f"P10_SOURCE_COMMIT:\n{source_commit}\n\n"
        "P10_EVIDENCE_CHECKPOINT:\nCOMMIT_CONTAINING_THIS_SUMMARY\n\n"
        "P10_TAG:\nNONE\n\nWORKTREE_CLEAN:\nEXPECTED_AFTER_EVIDENCE_COMMIT\n\n"
        "WIRING_ALREADY_CONFIRMED: true\nCURRENT_RUN_HARDWARE_AUTHORIZATION: true\n"
        "HARDWARE_ACTIONS_EXECUTED: false\nNETWORK_USED: false\nNO_HARDWARE_MOVEMENT: true\n"
        "MAX_LANE_MASK_USED: NONE_NO_HARDWARE_RUN\n\n"
        "FIXED_BOARD_ID:\nPENDING_PHYSICAL_ROLE_BINDING\n\n"
        "ROTATING_BOARD_ID:\nPENDING_PHYSICAL_ROLE_BINDING\n\n"
        "FOUR_DIRECTION_RAW:\nNOT_RUN_SEVERE_BLOCKER\n"
        "LANE0_4MBPS:\nNOT_RUN_SEVERE_BLOCKER\n"
        "LANE1_4MBPS:\nNOT_RUN_SEVERE_BLOCKER\n"
        "TWO_LANE_8MBPS_RAW:\nNOT_RUN_SEVERE_BLOCKER\n\n"
        "SELECTIVE_REPEAT_SACK:\nPASS_OFFLINE_SIMULATION_ONLY_HARDWARE_NOT_RUN\n"
        "DMA_DDR_CACHE_FIXED:\nNOT_RUN_SEVERE_BLOCKER\n"
        "DMA_DDR_CACHE_ROTATING:\nNOT_RUN_SEVERE_BLOCKER\n"
        "DUAL_INDEPENDENT_PS:\nPASS_OFFLINE_BUILD_ONLY_HARDWARE_NOT_RUN\n"
        "NO_SHARED_RAM:\nPASS_OFFLINE_ARCHITECTURE_AND_SIMULATION_HARDWARE_NOT_RUN\n"
        "F_TO_R_OBJECT:\nNOT_RUN_SEVERE_BLOCKER\nR_TO_F_OBJECT:\nNOT_RUN_SEVERE_BLOCKER\n"
        "OBJECT_SHA256:\nNONE_NO_HARDWARE_RUN\nENDPOINT_REBOOT_RECOVERY:\nNOT_RUN_SEVERE_BLOCKER\n"
        "STATIONARY_30MIN:\nNOT_RUN_SEVERE_BLOCKER\n\n"
        "APPLICATION_GOODPUT_F_TO_R_BPS:\nNOT_MEASURED_NO_HARDWARE_RUN\n"
        "APPLICATION_GOODPUT_R_TO_F_BPS:\nNOT_MEASURED_NO_HARDWARE_RUN\n\n"
        "SHUTDOWN_FIXED:\nNOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS\n"
        "SHUTDOWN_ROTATING:\nNOT_EXECUTED_SEVERE_BLOCKER_OFFLINE_IMAGE_BUILD_PASS\n\n"
        "PASS:\nOFFLINE_BUILD_SIMULATION_AND_ARCHITECTURE_ITEMS_IN_JSON\n"
        "FAIL:\nP10-SAFETY-POWERUP-001; P10-RX-B-R29-001; MANDATORY_HARDWARE_NOT_RUN\n"
        "NONBLOCKING_EXTENSIONS:\nNOT_RUN_BECAUSE_MANDATORY_HARDWARE_ADMISSION_FAILED\n"
        "GENERATED_EVIDENCE:\nevidence/generated/p10_fasttrack_final_summary.json\n"
        "UNCHANGED_PENDING_SCOPES:\nETHERNET; SPI; PHYSICAL_GLOBAL_PERMIT; EXTERNAL_TFDU_DUTY; HANDOVER; 8X32; 600RPM; PRODUCT_FINAL\n\n"
        "NEXT_RECOMMENDED_STAGE:\nP10_REMEDIATION\n"
        "```\n\n"
        "The fast-track authorization was recognized, but hardware admission failed closed at the severe "
        "power-up safety blocker.  Offline role-separated builds and portable regressions were completed; "
        "no hardware action, Ethernet use, movement, or optical emission occurred.\n",
        encoding="utf-8", newline="\n")
    print("P10_OFFLINE_EVIDENCE=PASS")
    print("P10_FASTTRACK_RESULT=PARTIAL")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
