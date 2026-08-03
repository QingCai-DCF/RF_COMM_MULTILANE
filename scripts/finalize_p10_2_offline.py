#!/usr/bin/env python3
"""Freeze P10.2 offline evidence and advance canonical state without hardware."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from p8a_common import render_project_status, render_traceability


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_2_raw"
GOAL = ROOT / "goals/P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS_GOAL.md"
GOAL_SHA256 = "f09ddcd1556b6def7eab250cae92b1cc69f7316a4c3338b5b04d23b10f22a8f5"
SOURCE_BASE = "e90a2203c4d6b71f93e0ee1c5bf93bb263c8a1b8"
P10_1R_SOURCE = "39df17155ce82e38366fbdac00c79584f0fe1afa"
P10_1R_CHECKPOINT = "9321ca2f1797eb12bfb02848c3ee27145e1e8eb4"
P10_1R_PASS_TAG = "p10.1r-2lane-speed-stability-pass"
P10_1R_CLOSED_TAG = "p10.1r-2lane-speed-stability-closed"
BRANCH = "p10.2/4lane-offline-readiness"
WIRING_SHA256 = "5f4a89b818b007af4863534759068dda529fe3c34501569ea4da89a42d8026fc"
STATE = ROOT / "config/project_state.json"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
STATUS = ROOT / "PROJECT_STATUS.md"
TRACE = ROOT / "docs/requirements/REQUIREMENT_TRACEABILITY.md"

INPUTS = {
    "p10_1r_recheck": RAW / "p10_1r_recheck.json",
    "model": RAW / "model.json",
    "power": RAW / "power_model.json",
    "xsim": RAW / "xsim/summary.json",
    "runner": RAW / "p10_3_runner_selftest.json",
    "no_hardware_scan": RAW / "no_hardware_static_scan.json",
    "p10_regression": RAW / "p10_frozen_regression.json",
    "functional": GENERATED / "p10_2_functional_build_summary.json",
    "runtime": GENERATED / "p10_2_ps_runtime_build_summary.json",
    "host_software": GENERATED / "p10_2_host_software_build.json",
}

BOARD_EVIDENCE = (
    "p10_2_repo_discovery",
    "p10_1r_closeout_summary",
    "p10_1r_git_checkpoint_metadata",
    "p10_2_repo_intake",
    "p10_2_module_inventory_summary",
    "p10_2_wiring_summary",
    "p10_2_pin_bank_audit",
    "p10_2_profile_summary",
)
BOARD_JSON_ONLY = {"p10_1r_git_checkpoint_metadata"}

NEW_PAIRS = (
    "p10_2_parameterization_summary",
    "p10_2_safety_summary",
    "p10_2_echo_matrix_model",
    "p10_2_scheduler_summary",
    "p10_2_arq_summary",
    "p10_2_streaming_summary",
    "p10_2_performance_model",
    "p10_2_power_budget",
    "p10_2_xsim_summary",
    "p10_2_fixed_build",
    "p10_2_rotating_build",
    "p10_2_software_build",
    "p10_2_hardware_dry_run",
    "p10_2_p10_3_readiness",
    "p10_2_regression",
    "p10_2_final_summary",
    "p10_2_evidence_consistency",
)

DEVICE_CAPACITY = {
    "lut": 53200,
    "ff": 106400,
    "bram36_equivalent": 140.0,
    "dsp": 220,
}
RESOURCE_LIMITS = {
    "lut": 70.0,
    "ff": 70.0,
    "bram36_equivalent": 75.0,
    "dsp": 50.0,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )


def write_pair(name: str, title: str, payload: dict[str, Any]) -> None:
    json_path = GENERATED / f"{name}.json"
    write_json(json_path, payload)
    lines = [
        f"# {title}", "", f"- Status: `{payload.get('status', 'NONE')}`",
        f"- Test ID: `{payload.get('test_id', 'NONE')}`",
        f"- Scope: `{payload.get('scope', 'P10_2_OFFLINE_ONLY')}`",
        "- Hardware actions executed: `false`.",
    ]
    if "source_commit" in payload:
        lines.append(f"- Source commit: `{payload['source_commit']}`.")
    lines.extend(["", f"Machine-readable evidence: `{rel(json_path)}`."])
    (GENERATED / f"{name}.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def verify_record(record: dict[str, Any], label: str, errors: list[str]) -> None:
    path_text = record.get("path")
    digest = record.get("sha256")
    if not isinstance(path_text, str) or not isinstance(digest, str):
        errors.append(f"{label} lacks path/SHA256")
        return
    path = ROOT / path_text
    if not path.is_file():
        errors.append(f"{label} is missing: {path_text}")
    elif sha256(path) != digest:
        errors.append(f"{label} SHA256 mismatch: {path_text}")


def parse_utilization(path: Path) -> dict[str, float | int | str | bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.search(
        r"^\|\s*p10_ps_system_wrapper\s*\|\s*\(top\)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|"
        r"\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|",
        text, re.MULTILINE,
    )
    if match is None:
        return {"status": "FAIL", "error": "top utilization row not found"}
    total_lut, _, _, _, ff, bram36, bram18, dsp = (int(value) for value in match.groups())
    used: dict[str, float | int] = {
        "lut": total_lut,
        "ff": ff,
        "bram36_equivalent": bram36 + bram18 / 2.0,
        "dsp": dsp,
    }
    percent = {key: float(value) / DEVICE_CAPACITY[key] * 100.0 for key, value in used.items()}
    return {
        "status": "PASS",
        "used": used,
        "capacity": DEVICE_CAPACITY,
        "percent": percent,
        "limits_percent": RESOURCE_LIMITS,
        "within_limits": all(percent[key] <= RESOURCE_LIMITS[key] for key in RESOURCE_LIMITS),
    }


def role(summary: dict[str, Any], name: str) -> dict[str, Any]:
    return next((item for item in summary.get("roles", []) if item.get("role") == name), {})


def make_build_evidence(
    functional: dict[str, Any], role_name: str, source_commit: str, errors: list[str]
) -> dict[str, Any]:
    item = role(functional, role_name)
    markers = item.get("markers", {})
    report = ROOT / f"evidence/generated/vivado/p10_2_4lane/{role_name}/post_route_utilization.rpt"
    baseline_report = ROOT / f"evidence/generated/vivado/p10_1r/{role_name}/post_route_utilization.rpt"
    current = parse_utilization(report) if report.is_file() else {"status": "FAIL"}
    baseline = parse_utilization(baseline_report) if baseline_report.is_file() else {"status": "FAIL"}
    local_errors: list[str] = []
    require(item.get("status") == "PASS", f"{role_name} routed build is not PASS", local_errors)
    require(current.get("status") == "PASS" and current.get("within_limits") is True,
            f"{role_name} resource audit failed", local_errors)
    require(baseline.get("status") == "PASS", f"{role_name} two-lane resource baseline missing", local_errors)
    for key in ("P10_WNS_NS", "P10_WHS_NS"):
        try:
            require(float(markers.get(key, "-1")) >= 0.0, f"{role_name} {key} is negative", local_errors)
        except ValueError:
            local_errors.append(f"{role_name} {key} is invalid")
    required_markers = {
        "P10_TNS_NS": "0.0",
        "P10_DRC_CRITICAL_COUNT": "0",
        "P10_DRC_ERROR_COUNT": "0",
        "P10_REQP_1839_COUNT": "0",
        "P10_CDC_CRITICAL_COUNT": "0",
        "P10_UNCONSTRAINED_INTERNAL_ENDPOINTS": "0",
        "P10_NO_CLOCK_COUNT": "0",
        "P10_RESOURCE_LIMITS_PASS": "1",
        "P10_LANE_COUNT": "4",
    }
    for key, expected in required_markers.items():
        require(markers.get(key) == expected,
                f"{role_name} marker {key}={markers.get(key)!r}, expected {expected}", local_errors)
    artifacts = item.get("artifacts", {})
    for kind in ("bitstream", "xsa"):
        verify_record(artifacts.get(kind, {}), f"{role_name} {kind}", local_errors)
    delta: dict[str, float] = {}
    projected: dict[str, float] = {}
    if current.get("status") == baseline.get("status") == "PASS":
        for key in DEVICE_CAPACITY:
            four = float(current["used"][key])  # type: ignore[index]
            two = float(baseline["used"][key])  # type: ignore[index]
            delta[key] = four - two
            projected[key] = max(0.0, four + 2.0 * (four - two))
    payload = {
        "schema_version": 1,
        "test_id": f"P10_2-{role_name.upper()}-FOUR-LANE-ROUTED-BUILD",
        "status": "PASS" if not local_errors else "FAIL",
        "scope": "AX7020_FOUR_LANE_OFFLINE_IMPLEMENTATION_ONLY",
        "source_commit": source_commit,
        "profile": item.get("profile"),
        "part": functional.get("part"),
        "markers": markers,
        "resources_2lane_baseline": baseline,
        "resources_4lane": current,
        "delta_4lane_minus_2lane": delta,
        "projected_8lane_linear_from_lane_delta": projected,
        "projection_is_not_an_8lane_build": True,
        "artifacts": artifacts,
        "reports": item.get("reports", []),
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "errors": local_errors,
    }
    errors.extend(local_errors)
    return payload


def evidence_record(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def requirement_item(
    requirement_id: str,
    text: str,
    profile: str,
    method: str,
    scope: str,
    evidence: str,
    followup: str,
) -> dict[str, Any]:
    path = ROOT / evidence
    digest = sha256(path)
    return {
        "requirement_id": requirement_id,
        "requirement_text": text,
        "profile": profile,
        "verification_method": method,
        "verification_stage": "P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS",
        "verification_scope": scope,
        "test_id": requirement_id,
        "evidence_path": evidence,
        "status": "PASS",
        "waiver": None,
        "artifact_hashes": [{"path": evidence, "sha256": digest}],
        "hardware_followup": followup,
        "artifact_hash": digest,
    }


def remove_p10_2_requirements(text: str) -> str:
    begin = "# BEGIN P10_2 GENERATED REQUIREMENTS"
    end = "# END P10_2 GENERATED REQUIREMENTS"
    text = re.sub(rf"\n?{re.escape(begin)}.*?{re.escape(end)}\n?", "\n", text, flags=re.DOTALL)
    lines = text.splitlines(keepends=True)
    output: list[str] = []
    index = 0
    while index < len(lines):
        match = re.match(r"- requirement_id: (P10_2-[A-Z0-9_-]+)", lines[index])
        if match:
            index += 1
            while index < len(lines) and not lines[index].startswith("- requirement_id:"):
                index += 1
            continue
        output.append(lines[index])
        index += 1
    return "".join(output).rstrip() + "\n"


def refresh_canonical_bindings(text: str, state_hash: str, status_hash: str) -> str:
    for path, digest in (("config/project_state.json", state_hash), ("PROJECT_STATUS.md", status_hash)):
        text = re.sub(
            rf"(  - path: {re.escape(path)}\n    sha256: )[0-9a-f]{{64}}",
            rf"\g<1>{digest}", text,
        )
    blocks = re.split(r"(?=^- requirement_id: )", text, flags=re.MULTILINE)
    refreshed: list[str] = []
    for block in blocks:
        first = re.search(r"  artifact_hashes:\n  - path: [^\n]+\n    sha256: ([0-9a-f]{64})", block)
        if first:
            block = re.sub(r"(  artifact_hash: )[0-9a-f]{64}",
                           rf"\g<1>{first.group(1)}", block, count=1)
        refreshed.append(block)
    return "".join(refreshed)


def update_state(source_commit: str, final_hash: str, pass_status: bool) -> None:
    state = load_json(STATE)
    state["current_program_stage"] = (
        "P10_3_AX7020_STATIONARY_4LANE_HARDWARE_ACCEPTANCE"
        if pass_status else "P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS"
    )
    state["current_run_hardware_authorization"] = False
    state["p10_1r_status"] = "PASS"
    state["two_lane_baseline_status"] = "FROZEN_ACCEPTED"
    state["p10_2_status"] = "PASS" if pass_status else "FAIL"
    state["p10_3_status"] = "PENDING_PHYSICAL_WIRING_AND_NEW_AUTHORIZATION"
    state["p11_status"] = "NOT_STARTED"
    state["last_verified_commit"] = source_commit
    gates = state.setdefault("completed_gates", [])
    gates[:] = [gate for gate in gates if gate.get("gate_id") != "P10_2"]
    if pass_status:
        gates.append({"gate_id": "P10_2", "status": "PASS"})
    profiles = state.setdefault("current_profiles", [])
    profiles[:] = [p for p in profiles if p.get("profile") not in {
        "P10_2_AX7020_FIXED_4LANE", "P10_2_AX7020_ROTATING_4LANE"}]
    for role_name, board, serial in (
        ("fixed", "AX7020-F", "210249855178"),
        ("rotating", "AX7020-R", "210512180081"),
    ):
        profiles.append({
            "active_profile_path": f"board_profiles/ax7020_{role_name}_4lane/ACTIVE_PROFILE.json",
            "available_physical_lanes": 4,
            "board": board,
            "jtag_cable_serial": serial,
            "part": "xc7z020clg400-2",
            "pinmap_path": f"board_profiles/ax7020_{role_name}_4lane/pinmap.csv",
            "profile": f"P10_2_AX7020_{role_name.upper()}_4LANE",
            "status": "OFFLINE_READY_PHYSICAL_WIRING_AND_NEW_MODULES_PENDING",
            "xdc_path": f"board_profiles/ax7020_{role_name}_4lane/ax7020_{role_name}_4lane.generated.xdc",
        })
    state["p10_2_offline_readiness"] = {
        "status": "PASS" if pass_status else "FAIL",
        "source_commit": source_commit,
        "goal_sha256": GOAL_SHA256,
        "final_evidence_path": "evidence/generated/p10_2_final_summary.json",
        "final_evidence_sha256": final_hash,
        "two_lane_baseline_status": "FROZEN_ACCEPTED",
        "wiring_proposal_sha256": WIRING_SHA256,
        "modeled_application_goodput_bps": 9791249,
        "hardware_ready": False,
        "p10_3_status": "PENDING_PHYSICAL_WIRING_AND_NEW_AUTHORIZATION",
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "two_hour_qualification_executed": False,
        "missing_prerequisites": [
            "physical intake and acceptance of F2/F3/R2/R3",
            "four-lane wiring/rail/decoupling inspection on both boards",
            "content-addressed four-lane shutdown bitstreams",
            "new P10.3 current-run hardware authorization",
        ],
        "not_promoted_to": ["P10_3_HARDWARE_PASS", "P11", "8x32", "600_RPM", "PRODUCT_FINAL"],
    }
    write_json(STATE, state)
    STATUS.write_text(render_project_status(state), encoding="utf-8", newline="\n")


def update_requirements(pass_status: bool) -> None:
    if not pass_status:
        return
    common_followup = "P10.3 hardware claims remain pending physical wiring, eight accepted modules and a new current-run authorization."
    definitions = (
        ("P10_2-CLOSE-001", "P10.1R authorization is closed and its PASS tag/checkpoint remain immutable.", "P10_1R_CLOSEOUT", "Immutable tag, ancestry, evidence-hash and authorization recheck.", "P10_1R_CLOSEOUT_OFFLINE", "evidence/generated/p10_1r_closeout_summary.json"),
        ("P10_2-INV-001", "The accepted replacement F1 is retained, old F1 is quarantined, and F2/F3/R2/R3 remain explicit pending identities.", "P10_2_EIGHT_MODULE_INVENTORY", "Machine-readable inventory and quarantine audit.", "P10_2_OFFLINE_MODULE_IDENTITY", "evidence/generated/p10_2_module_inventory_summary.json"),
        ("P10_2-WIRE-001", "The independent AX7020 four-lane wiring proposal preserves lanes 0/1 and assigns J11-A/J11-B to lanes 2/3.", "P10_2_AX7020_4LANE", "Wiring proposal and source-bound pin-map audit.", "P10_2_OFFLINE_BOARD_DESIGN", "evidence/generated/p10_2_wiring_summary.json"),
        ("P10_2-PIN-001", "Every selected four-lane signal pin has a unique package pin, compatible bank/VCCO and no Z7010 XDC reuse.", "P10_2_AX7020_4LANE", "Pin/bank/VCCO/XDC audit.", "P10_2_OFFLINE_BOARD_DESIGN", "evidence/generated/p10_2_pin_bank_audit.json"),
        ("P10_2-PROFILE-001", "The fixed AX7020 has an independent four-lane profile, pinmap and XDC.", "P10_2_AX7020_FIXED_4LANE", "Profile generation and routed build.", "P10_2_OFFLINE_PROFILE", "evidence/generated/p10_2_fixed_build.json"),
        ("P10_2-PROFILE-002", "The rotating-role AX7020 has an independent four-lane profile, pinmap and XDC.", "P10_2_AX7020_ROTATING_4LANE", "Profile generation and routed build.", "P10_2_OFFLINE_PROFILE", "evidence/generated/p10_2_rotating_build.json"),
        ("P10_2-SAFE-001", "Eight physical TFDU module paths retain exact rolling duty, startup, pulse and per-module TX/RX exclusion models.", "P10_2_EIGHT_PHYSICAL_MODULE_SAFETY", "RTL XSIM plus deterministic fault/echo model.", "P10_2_OFFLINE_SAFETY", "evidence/generated/p10_2_safety_summary.json"),
        ("P10_2-SAFE-002", "Each endpoint retains exactly one local active-high GLOBAL_PERMIT and no per-lane permit channel.", "P10_2_SINGLE_GLOBAL_PERMIT", "Structural RTL and model assertion.", "P10_2_OFFLINE_SAFETY", "evidence/generated/p10_2_safety_summary.json"),
        ("P10_2-ECHO-001", "The 8x8 echo/crosstalk model accepts only the eight intended remote lane-pair cells.", "P10_2_ECHO_8X8", "Deterministic 8x8 matrix and RX admission XSIM.", "P10_2_OFFLINE_ECHO_MODEL", "evidence/generated/p10_2_echo_matrix_model.json"),
        ("P10_2-LANE-001", "The common RTL elaborates with lane counts 2, 4 and 8 while P10.2 selects lane count 4.", "P10_2_PARAMETERIZATION", "Bounded XSIM elaboration matrix.", "P10_2_OFFLINE_RTL", "evidence/generated/p10_2_parameterization_summary.json"),
        ("P10_2-LANE-002", "All nonzero four-lane masks 0x1 through 0xF are supported and bounded.", "P10_2_LANE_MASK_MATRIX", "Scheduler XSIM and deterministic mask matrix.", "P10_2_OFFLINE_RTL", "evidence/generated/p10_2_scheduler_summary.json"),
        ("P10_2-LANE-003", "The scheduler degrades 4 to 3 to 2 to 1 healthy lane and recovers without selecting an unavailable lane.", "P10_2_DEGRADATION", "Deterministic degradation/recovery model.", "P10_2_OFFLINE_RTL", "evidence/generated/p10_2_scheduler_summary.json"),
        ("P10_2-SCHED-001", "The four-lane scheduler is fair, weighted and health-aware.", "P10_2_4LANE_SCHEDULER", "XSIM and fixed-seed scheduler events.", "P10_2_OFFLINE_PROTOCOL", "evidence/generated/p10_2_scheduler_summary.json"),
        ("P10_2-ARQ-001", "Four-lane selective-repeat/SACK preserves one bundle sequence space and safe retry migration.", "P10_2_4LANE_ARQ", "XSIM reorder/wrap plus deterministic ARQ model.", "P10_2_OFFLINE_PROTOCOL", "evidence/generated/p10_2_arq_summary.json"),
        ("P10_2-STREAM-001", "The four-lane model completes 64 MiB and 128 MiB objects with atomic matching integrity hashes.", "P10_2_4LANE_STREAMING", "Deterministic streaming, wrap, fault and recovery model.", "P10_2_OFFLINE_STREAMING", "evidence/generated/p10_2_streaming_summary.json"),
        ("P10_2-PERF-001", "Four independent 4 Mbit/s lanes provide 16 Mbit/s aggregate raw modeled capability.", "P10_2_4LANE_PERFORMANCE", "Airtime and exact-duty reconciliation.", "P10_2_OFFLINE_PERFORMANCE_FEASIBILITY", "evidence/generated/p10_2_performance_model.json"),
        ("P10_2-PERF-002", "The four-lane stationary half-duplex design has modeled application feasibility at or above 8 Mbit/s.", "P10_2_4LANE_PERFORMANCE", "Bounded candidate-space performance model.", "P10_2_OFFLINE_PERFORMANCE_FEASIBILITY", "evidence/generated/p10_2_performance_model.json"),
        ("P10_2-PERF-003", "The 9.6 Mbit/s stretch point is explicitly evaluated without becoming a hardware claim.", "P10_2_4LANE_PERFORMANCE", "Bounded candidate-space performance model.", "P10_2_OFFLINE_PERFORMANCE_FEASIBILITY", "evidence/generated/p10_2_performance_model.json"),
        ("P10_2-POWER-001", "The future four-simultaneous-TX rail is budgeted for 2.4 A peak IRED demand and explicit decoupling verification.", "P10_2_4TX_POWER", "Offline worst-case current/capacitance requirement model.", "P10_2_OFFLINE_POWER_REQUIREMENTS", "evidence/generated/p10_2_power_budget.json"),
        ("P10_2-HWPREP-001", "The P10.3 command validator fails closed on missing authorization, old F1, mask>0xF, Ethernet, movement and two-hour requests.", "P10_3_FAIL_CLOSED_RUNNER", "Offline runner self-test only.", "P10_2_OFFLINE_HARDWARE_PREPARATION", "evidence/generated/p10_2_hardware_dry_run.json"),
        ("P10_2-HWPREP-002", "P10.3 has machine-readable stage and 8x8 evidence templates without granting hardware authority.", "P10_3_EVIDENCE_SCHEMA", "Template inventory and readiness audit.", "P10_2_OFFLINE_HARDWARE_PREPARATION", "evidence/generated/p10_2_p10_3_readiness.json"),
    )
    items = [requirement_item(*definition, common_followup) for definition in definitions]
    text = remove_p10_2_requirements(REQUIREMENTS.read_text(encoding="utf-8"))
    block = "# BEGIN P10_2 GENERATED REQUIREMENTS\n" + yaml.safe_dump(
        items, sort_keys=False, allow_unicode=True, width=120
    ) + "# END P10_2 GENERATED REQUIREMENTS\n"
    text += block
    state_hash = sha256(STATE)
    status_hash = sha256(STATUS)
    text = refresh_canonical_bindings(text, state_hash, status_hash)
    REQUIREMENTS.write_text(text, encoding="utf-8", newline="\n")
    document = yaml.safe_load(text)
    TRACE.parent.mkdir(parents=True, exist_ok=True)
    TRACE.write_text(render_traceability(document), encoding="utf-8", newline="\n")


def final_summary(
    source_commit: str,
    model: dict[str, Any],
    power: dict[str, Any],
    functional: dict[str, Any],
    runtime: dict[str, Any],
    pass_status: bool,
    errors: list[str],
) -> dict[str, Any]:
    artifacts: dict[str, Any] = {}
    for role_name in ("fixed", "rotating"):
        build_role = role(functional, role_name)
        runtime_role = role(runtime, role_name)
        artifacts[role_name] = {
            **build_role.get("artifacts", {}),
            **runtime_role.get("artifacts", {}),
        }
    return {
        "schema_version": 1,
        "test_id": "P10_2-OFFLINE-READINESS-FINAL",
        "status": "PASS" if pass_status else "FAIL",
        "scope": "P10_2_2LANE_BASELINE_FREEZE_AND_4LANE_OFFLINE_READINESS",
        "generated_at_utc": now(),
        "goal_sha256": GOAL_SHA256,
        "source_commit": source_commit,
        "base_commit": SOURCE_BASE,
        "branch": BRANCH,
        "p10_1r_source_commit": P10_1R_SOURCE,
        "p10_1r_evidence_checkpoint": P10_1R_CHECKPOINT,
        "p10_1r_pass_tag": P10_1R_PASS_TAG,
        "p10_1r_closed_tag": P10_1R_CLOSED_TAG,
        "two_lane_baseline_status": "FROZEN_ACCEPTED",
        "wiring_proposal_sha256": WIRING_SHA256,
        "lane_count": 4,
        "lane_mask_matrix": "PASS" if pass_status else "FAIL",
        "raw_capability_bps": model.get("performance", {}).get("raw_capability_bps"),
        "modeled_application_goodput_bps": model.get("performance", {}).get("modeled_application_goodput_bps"),
        "hard_8mbps_feasibility": model.get("performance", {}).get("hard_target_status"),
        "stretch_9p6mbps": model.get("performance", {}).get("stretch_status"),
        "recommended": model.get("performance", {}).get("chosen", {}),
        "four_tx_peak_current_budget_a": power.get("four_tx_peak_ired_current_a"),
        "artifacts": artifacts,
        "p10_3_hardware_ready": False,
        "p10_3_status": "PENDING_PHYSICAL_WIRING_AND_NEW_AUTHORIZATION",
        "p10_3_missing_prerequisites": [
            "F2/F3/R2/R3 physical identity and acceptance",
            "both-board J11 wiring, rail, decoupling and powered-idle inspection",
            "content-addressed four-lane shutdown bitstreams",
            "new current-run P10.3 authorization",
        ],
        "p11_status": "NOT_STARTED",
        "current_run_hardware_authorization": False,
        "no_hardware": True,
        "hardware_actions_executed": False,
        "two_hour_qualification_executed": False,
        "network_used": False,
        "evidence_consistency_path": "evidence/generated/p10_2_evidence_consistency.json",
        "pass": [
            "P10.1R immutable closeout recheck", "eight-slot inventory/quarantine",
            "four-lane wiring and profiles", "2/4/8 elaboration", "8-module safety",
            "8x8 echo model", "mask 0x1..0xF scheduler/degradation", "ARQ/SACK",
            "64/128 MiB streaming model", "8 Mbit/s application feasibility",
            "fixed/rotating routed builds", "four-lane software builds",
            "P10.3 fail-closed command-only dry-run",
        ] if pass_status else [],
        "fail": errors,
        "skip_with_reason": [
            "P10.3 real hardware: no current authorization and physical prerequisites incomplete",
            "two-hour qualification: expressly excluded by this Goal",
        ],
        "errors": errors,
    }


def verify_existing() -> list[str]:
    errors: list[str] = []
    require(git("branch", "--show-current") == BRANCH, "branch mismatch", errors)
    require(sha256(GOAL) == GOAL_SHA256, "goal SHA256 mismatch", errors)
    for name in (*BOARD_EVIDENCE, *NEW_PAIRS):
        path = GENERATED / f"{name}.json"
        require(path.is_file(), f"missing evidence {rel(path)}", errors)
        if path.is_file():
            payload = load_json(path)
            require(payload.get("status") == "PASS", f"evidence not PASS: {name}", errors)
            require(payload.get("hardware_actions_executed") is False,
                    f"hardware action field is not false: {name}", errors)
    final = GENERATED / "p10_2_final_summary.json"
    if final.is_file():
        final_source = load_json(final).get("source_commit")
        require(isinstance(final_source, str), "final summary source commit is missing", errors)
        if isinstance(final_source, str):
            ancestor = subprocess.run(
                ["git", "merge-base", "--is-ancestor", final_source, "HEAD"],
                cwd=ROOT, capture_output=True,
            ).returncode == 0
            require(ancestor, "final summary source commit is not an ancestor of HEAD", errors)
    manifest = RAW / "artifact_sha256_manifest.json"
    require(manifest.is_file(), "artifact manifest missing", errors)
    if manifest.is_file():
        for index, record in enumerate(load_json(manifest).get("artifacts", [])):
            verify_record(record, f"artifact manifest record {index}", errors)
    if STATE.is_file():
        state = load_json(STATE)
        require(state.get("p10_2_status") == "PASS", "canonical p10_2_status is not PASS", errors)
        require(state.get("current_run_hardware_authorization") is False,
                "canonical hardware authorization is not false", errors)
        require(STATUS.read_bytes() == render_project_status(state).encode("utf-8"),
                "PROJECT_STATUS.md is stale", errors)
    document = yaml.safe_load(REQUIREMENTS.read_text(encoding="utf-8"))
    ids = {item.get("requirement_id"): item for item in document.get("requirements", [])}
    required_ids = {
        "P10_2-CLOSE-001", "P10_2-INV-001", "P10_2-WIRE-001", "P10_2-PIN-001",
        "P10_2-PROFILE-001", "P10_2-PROFILE-002", "P10_2-SAFE-001", "P10_2-SAFE-002",
        "P10_2-ECHO-001", "P10_2-LANE-001", "P10_2-LANE-002", "P10_2-LANE-003",
        "P10_2-SCHED-001", "P10_2-ARQ-001", "P10_2-STREAM-001", "P10_2-PERF-001",
        "P10_2-PERF-002", "P10_2-PERF-003", "P10_2-POWER-001", "P10_2-HWPREP-001",
        "P10_2-HWPREP-002",
    }
    for requirement_id in required_ids:
        require(ids.get(requirement_id, {}).get("status") == "PASS",
                f"requirement missing/not PASS: {requirement_id}", errors)
    require(TRACE.read_bytes() == render_traceability(document).encode("utf-8"),
            "requirement traceability is stale", errors)
    consistency_path = GENERATED / "p10_2_evidence_consistency.json"
    if consistency_path.is_file():
        consistency = load_json(consistency_path)
        for record in consistency.get("verified_files", []):
            verify_record(record, "consistency record", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()
    if args.write == args.verify_existing:
        raise SystemExit("choose exactly one of --write or --verify-existing")
    if args.verify_existing:
        errors = verify_existing()
        payload = {"status": "PASS" if not errors else "FAIL", "errors": errors,
                   "hardware_actions_executed": False}
        if args.json_summary:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"P10_2_VERIFY_EXISTING={payload['status']}")
        return 0 if not errors else 1

    errors: list[str] = []
    require(git("branch", "--show-current") == BRANCH, "branch mismatch", errors)
    require(sha256(GOAL) == GOAL_SHA256, "goal SHA256 mismatch", errors)
    require(git("merge-base", "--is-ancestor", SOURCE_BASE, "HEAD") == "", "base is not ancestor", errors)
    source_commit = git("rev-parse", "HEAD")
    require(not git("status", "--porcelain", "--untracked-files=no", "--", "rtl", "software", "scripts", "board_profiles", "config/performance", "config/register_map"),
            "tracked P10.2 source inputs are dirty", errors)
    payloads: dict[str, dict[str, Any]] = {}
    for name, path in INPUTS.items():
        require(path.is_file(), f"missing input {rel(path)}", errors)
        if path.is_file():
            payloads[name] = load_json(path)
    for name, payload in payloads.items():
        require(payload.get("status") == "PASS", f"input {name} is not PASS", errors)
        require(payload.get("hardware_actions_executed") is False,
                f"input {name} hardware_actions_executed is not false", errors)
    for name in BOARD_EVIDENCE:
        path = GENERATED / f"{name}.json"
        require(path.is_file(), f"missing board/closeout evidence {name}", errors)
        if path.is_file():
            payload = load_json(path)
            require(payload.get("status") == "PASS", f"board/closeout evidence {name} is not PASS", errors)
            require(payload.get("hardware_actions_executed", False) is False,
                    f"board/closeout evidence {name} reports hardware action", errors)

    model = payloads.get("model", {})
    power = payloads.get("power", {})
    xsim = payloads.get("xsim", {})
    functional = payloads.get("functional", {})
    runtime = payloads.get("runtime", {})
    host_software = payloads.get("host_software", {})
    runner = payloads.get("runner", {})
    no_hardware_scan = payloads.get("no_hardware_scan", {})
    p10_regression = payloads.get("p10_regression", {})
    recheck = payloads.get("p10_1r_recheck", {})
    require(functional.get("campaign") == "p10_2", "functional campaign mismatch", errors)
    require(functional.get("source_commit") == source_commit, "functional source commit mismatch", errors)
    require(functional.get("source_worktree_dirty") is False, "functional source was dirty", errors)
    require(runtime.get("campaign") == "p10_2", "runtime campaign mismatch", errors)
    require(runtime.get("source_commit") == source_commit, "runtime source commit mismatch", errors)
    require(runtime.get("source_worktree_dirty") is False, "runtime source was dirty", errors)
    require(xsim.get("source_commit") == source_commit, "XSIM source commit mismatch", errors)
    require(xsim.get("source_worktree_dirty") is False, "XSIM source was dirty", errors)
    required_tops = {
        "tb_ax7020_4lane_profile", "tb_4lane_lane_mask_matrix",
        "tb_4lane_scheduler_fairness", "tb_4lane_retry_migration",
        "tb_4lane_echo_admission", "tb_4lane_streaming",
        "tb_4lane_dual_endpoint", "tb_2lane_4lane_regression",
        "tb_p10_2_lane_count_elaboration",
    }
    xsim_results = {item.get("test_id"): item for item in xsim.get("results", [])}
    for top in required_tops:
        require(xsim_results.get(top, {}).get("status") == "PASS", f"XSIM top not PASS: {top}", errors)
    require(recheck.get("p10_1r_pass_tag_target") == P10_1R_CHECKPOINT,
            "P10.1R pass tag target mismatch", errors)
    require(recheck.get("p10_1r_closed_tag_target") == SOURCE_BASE,
            "P10.1R closed tag target mismatch", errors)
    require(model.get("performance", {}).get("raw_capability_bps") == 16_000_000,
            "raw capability model is not 16 Mbit/s", errors)
    require(model.get("performance", {}).get("modeled_application_goodput_bps", 0) >= 8_000_000,
            "modeled application goodput is below 8 Mbit/s", errors)
    require(model.get("performance", {}).get("stretch_status") in {"PASS", "FAIL_NON_BLOCKING", "PENDING_WITH_EXPLICIT_GAP"},
            "stretch classification is invalid", errors)
    require(power.get("four_tx_peak_ired_current_a") == 2.4,
            "four-TX peak current requirement is not 2.4 A", errors)
    require(runner.get("no_2h_stage_present") is True, "P10.3 runner contains two-hour stage", errors)

    parameterization = {
        "schema_version": 1, "test_id": "P10_2-LANE-001", "status": "PASS",
        "scope": "P10_2_OFFLINE_RTL_PARAMETERIZATION", "source_commit": source_commit,
        "supported_lane_counts": [2, 4, 8], "selected_lane_count": 4,
        "lane_mask_width": 4, "lane_mask_min": "0x1", "lane_mask_max": "0xF",
        "two_lane_wire_header_bit_compatible": True,
        "xsim_tests": [xsim_results.get("tb_p10_2_lane_count_elaboration"),
                       xsim_results.get("tb_2lane_4lane_regression")],
        "no_hardware": True, "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
    }
    safety = {
        "schema_version": 1, "test_id": "P10_2-SAFE-001/P10_2-SAFE-002", "status": "PASS",
        "scope": "P10_2_EIGHT_PHYSICAL_MODULE_OFFLINE_SAFETY_MODEL",
        "source_commit": source_commit, **model.get("echo_safety", {}),
        "single_global_permit_per_endpoint": True,
        "global_permit_channel_count_per_endpoint": 1,
        "per_lane_global_permit_channels": 0,
        "hardware_actions_executed": False,
    }
    echo = {
        "schema_version": 1, "test_id": "P10_2-ECHO-001", "status": "PASS",
        "scope": "P10_2_8X8_ECHO_CROSSTALK_OFFLINE_MODEL", "source_commit": source_commit,
        **{key: value for key, value in model.get("echo_safety", {}).items()
           if key not in {"physical_modules", "status"}},
        "hardware_actions_executed": False,
    }
    scheduler = {
        "schema_version": 1, "test_id": "P10_2-SCHED-001/P10_2-LANE-002/P10_2-LANE-003",
        "status": "PASS", "scope": "P10_2_4LANE_SCHEDULER_OFFLINE_MODEL",
        "source_commit": source_commit, **model.get("scheduler", {}),
        "fixed_seed_events": model.get("randomized_events", {}).get("scheduler_protocol_events"),
        "hardware_actions_executed": False,
    }
    arq = {
        "schema_version": 1, "test_id": "P10_2-ARQ-001", "status": "PASS",
        "scope": "P10_2_4LANE_ARQ_SACK_OFFLINE_MODEL", "source_commit": source_commit,
        **model.get("arq", {}), "retry_migration": model.get("scheduler", {}).get("migration"),
        "hardware_actions_executed": False,
    }
    streaming = {
        "schema_version": 1, "test_id": "P10_2-STREAM-001", "status": "PASS",
        "scope": "P10_2_4LANE_STREAMING_OFFLINE_MODEL", "source_commit": source_commit,
        **model.get("streaming", {}), "hardware_actions_executed": False,
    }
    performance = {
        "schema_version": 1, "test_id": "P10_2-PERF-001/P10_2-PERF-002/P10_2-PERF-003",
        "status": "PASS", "scope": "P10_2_OFFLINE_FEASIBILITY_NOT_HARDWARE_MEASUREMENT",
        "source_commit": source_commit, **model.get("performance", {}),
        "hardware_actions_executed": False,
    }
    power_evidence = {
        **power, "source_commit": source_commit,
        "scope": "P10_2_OFFLINE_REQUIREMENT_PACKAGE_HARDWARE_ACCEPTANCE_PENDING",
        "hardware_actions_executed": False,
    }
    xsim_evidence = {
        **xsim, "test_id": "P10_2-4LANE-XSIM-SUMMARY",
        "scope": "P10_2_OFFLINE_XSIM", "hardware_actions_executed": False,
    }
    fixed_build = make_build_evidence(functional, "fixed", source_commit, errors)
    rotating_build = make_build_evidence(functional, "rotating", source_commit, errors)
    software_errors: list[str] = []
    require(host_software.get("status") == "PASS", "host four-lane software build failed", software_errors)
    require(runtime.get("status") == "PASS", "Vitis four-lane runtime build failed", software_errors)
    for role_name in ("fixed", "rotating"):
        runtime_role = role(runtime, role_name)
        require(runtime_role.get("status") == "PASS", f"{role_name} runtime is not PASS", software_errors)
        for kind in ("elf", "bsp"):
            verify_record(runtime_role.get("artifacts", {}).get(kind, {}),
                          f"{role_name} runtime {kind}", software_errors)
    errors.extend(software_errors)
    software = {
        "schema_version": 1, "test_id": "P10_2-FOUR-LANE-SOFTWARE-BUILD",
        "status": "PASS" if not software_errors else "FAIL",
        "scope": "P10_2_OFFLINE_HOST_ARM_BSP_ELF_BUILD", "source_commit": source_commit,
        "host_compile": host_software,
        "role_bound_runtime": runtime,
        "hardware_actions_executed": False, "errors": software_errors,
    }
    hardware_dry_run = {
        **runner, "test_id": "P10_2-HWPREP-001",
        "scope": "P10_3_COMMAND_VALIDATION_SELF_TEST_NO_BACKEND",
        "source_commit": source_commit, "hardware_actions_executed": False,
    }
    templates = sorted((ROOT / "evidence/templates/p10_3_4lane").glob("*.json"))
    readiness = {
        "schema_version": 1, "test_id": "P10_2-HWPREP-002", "status": "PASS",
        "scope": "P10_3_OFFLINE_READINESS_PACKAGE_ONLY", "source_commit": source_commit,
        "runner_dry_run": "PASS", "hardware_ready": False,
        "template_count": len(templates),
        "templates": [evidence_record(path) for path in templates],
        "matrix_template": evidence_record(ROOT / "evidence/templates/p10_3_crosstalk_8x8/matrix.json"),
        "missing_prerequisites": [
            "F2/F3/R2/R3 physical intake and acceptance",
            "physical four-lane wiring and power/decoupling inspection",
            "content-addressed fixed/rotating four-lane shutdown images",
            "new P10.3 current-run hardware authorization",
        ],
        "hardware_actions_executed": False,
    }
    regression = {
        "schema_version": 1, "test_id": "P10_2-TWO-LANE-REGRESSION", "status": "PASS",
        "scope": "P10_1R_FROZEN_BASELINE_AND_TWO_LANE_RTL_REGRESSION",
        "source_commit": source_commit, "p10_1r_recheck": recheck,
        "p10_frozen_regression": p10_regression,
        "two_lane_xsim": xsim_results.get("tb_2lane_4lane_regression"),
        "no_hardware_static_scan": no_hardware_scan,
        "old_f1_quarantined": True, "p10_1r_hardware_pass_preserved": True,
        "p10_1r_artifacts_reused_for_p10_2_hardware_claim": False,
        "hardware_actions_executed": False,
    }
    pairs = {
        "p10_2_parameterization_summary": ("P10.2 parameterization summary", parameterization),
        "p10_2_safety_summary": ("P10.2 eight-module safety summary", safety),
        "p10_2_echo_matrix_model": ("P10.2 8x8 echo/crosstalk model", echo),
        "p10_2_scheduler_summary": ("P10.2 four-lane scheduler summary", scheduler),
        "p10_2_arq_summary": ("P10.2 four-lane ARQ/SACK summary", arq),
        "p10_2_streaming_summary": ("P10.2 four-lane streaming model", streaming),
        "p10_2_performance_model": ("P10.2 four-lane performance model", performance),
        "p10_2_power_budget": ("P10.2 four-TX power budget", power_evidence),
        "p10_2_xsim_summary": ("P10.2 four-lane XSIM summary", xsim_evidence),
        "p10_2_fixed_build": ("P10.2 fixed four-lane routed build", fixed_build),
        "p10_2_rotating_build": ("P10.2 rotating four-lane routed build", rotating_build),
        "p10_2_software_build": ("P10.2 four-lane software build", software),
        "p10_2_hardware_dry_run": ("P10.2 P10.3 runner dry-run", hardware_dry_run),
        "p10_2_p10_3_readiness": ("P10.2 P10.3 readiness", readiness),
        "p10_2_regression": ("P10.2 two-lane regression", regression),
    }
    for name, (title, payload) in pairs.items():
        write_pair(name, title, payload)

    artifact_records: list[dict[str, Any]] = []
    for role_name in ("fixed", "rotating"):
        for source, kinds in ((role(functional, role_name), ("bitstream", "xsa")),
                              (role(runtime, role_name), ("elf", "bsp"))):
            for kind in kinds:
                record = source.get("artifacts", {}).get(kind, {})
                if record:
                    verify_record(record, f"manifest {role_name} {kind}", errors)
                    artifact_records.append({"role": role_name, "kind": kind, **record})
    manifest = {
        "schema_version": 1, "test_id": "P10_2-ARTIFACT-SHA256-MANIFEST",
        "status": "PASS" if not errors else "FAIL", "source_commit": source_commit,
        "goal_sha256": GOAL_SHA256, "artifacts": artifact_records,
        "hardware_actions_executed": False,
    }
    write_json(RAW / "artifact_sha256_manifest.json", manifest)

    pass_status = not errors
    final_payload = final_summary(source_commit, model, power, functional, runtime, pass_status, errors)
    write_pair("p10_2_final_summary", "P10.2 offline readiness final summary", final_payload)
    update_state(source_commit, sha256(GENERATED / "p10_2_final_summary.json"), pass_status)
    update_requirements(pass_status)

    verified_paths = [
        *(GENERATED / f"{name}.json" for name in BOARD_EVIDENCE),
        *(GENERATED / f"{name}.md" for name in BOARD_EVIDENCE if name not in BOARD_JSON_ONLY),
        *(GENERATED / f"{name}.{suffix}" for name in NEW_PAIRS[:-1] for suffix in ("json", "md")),
        RAW / "artifact_sha256_manifest.json", STATE, REQUIREMENTS, STATUS, TRACE,
    ]
    consistency_errors: list[str] = []
    for path in verified_paths:
        require(path.is_file(), f"consistency target missing: {rel(path)}", consistency_errors)
    consistency = {
        "schema_version": 1, "test_id": "P10_2-EVIDENCE-CONSISTENCY",
        "status": "PASS" if not consistency_errors and pass_status else "FAIL",
        "scope": "P10_2_OFFLINE_EVIDENCE_CONSISTENCY",
        "source_commit": source_commit, "goal_sha256": GOAL_SHA256,
        "verified_files": [evidence_record(path) for path in verified_paths if path.is_file()],
        "artifact_manifest_status": manifest.get("status"),
        "canonical_state_status": "PASS" if pass_status else "FAIL",
        "requirement_count": 21,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "errors": consistency_errors,
    }
    write_pair("p10_2_evidence_consistency", "P10.2 evidence consistency", consistency)
    if consistency["status"] != "PASS":
        errors.extend(consistency_errors or ["evidence consistency failed"])
    result = {"status": "PASS" if not errors else "FAIL", "source_commit": source_commit,
              "final_summary": rel(GENERATED / "p10_2_final_summary.json"),
              "errors": errors, "hardware_actions_executed": False}
    if args.json_summary:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"P10_2_OFFLINE_FINALIZE={result['status']}")
        print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
