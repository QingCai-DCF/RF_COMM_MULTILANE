#!/usr/bin/env python3
"""Validate and freeze the immutable P10.5 artifact bundle offline."""

from __future__ import annotations

import copy
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

import run_p10_5_hardware as campaign


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_5_artifact_freeze_raw"
FREEZE = GENERATED / "p10_5_artifact_freeze.json"
FREEZE_MD = GENERATED / "p10_5_artifact_freeze.md"
BRANCH = "p10.5/dual-direction-2plus2"
SUMMARIES = {
    "functional": GENERATED / "p10_5_functional_build_summary.json",
    "shutdown": GENERATED / "p10_5_shutdown_build_summary.json",
    "ps_runtime": GENERATED / "p10_5_ps_runtime_build_summary.json",
    "xsim": GENERATED / "p10_5_xsim/summary.json",
}
OFFLINE_INPUTS = {
    "goal": campaign.GOAL,
    "dual_direction_config": campaign.CONFIG,
    "capability_table": ROOT / "config/generated/p10_5_capability_table.json",
    "register_map": campaign.REGISTER_MAP,
    "register_manifest": ROOT / "config/register_map/generated/ir_regs_manifest.json",
    "reference_model": GENERATED / "p10_5_reference_model.json",
    "xsim_summary": GENERATED / "p10_5_xsim/summary.json",
    "ack_collision_diagnosis": GENERATED / "p10_5_ack_collision_diagnosis.json",
    "ack_collision_design": ROOT / "docs/design/P10_5_CONTROL_ACK_COLLISION_AVOIDANCE.md",
    "direction_abort_ack_liveness_diagnosis": GENERATED / "p10_5_direction_abort_ack_liveness_diagnosis.json",
    "direction_abort_ack_liveness_design": ROOT / "docs/design/P10_5_DIRECTION_ABORT_ACK_LIVENESS.md",
    "actual_wiring": campaign.AS_WIRED,
    "module_inventory": campaign.MODULE_INVENTORY,
    "runtime_rest_policy": campaign.RUNTIME_REST_POLICY,
    "p10_4_closeout": GENERATED / "p10_4_closeout.json",
    "campaign_runner": ROOT / "scripts/run_p10_5_hardware.py",
    "authorization_builder": ROOT / "scripts/create_p10_5_authorization.py",
    "artifact_freezer": ROOT / "scripts/freeze_p10_5_artifacts.py",
    "shutdown_tcl": campaign.SHUTDOWN_TCL,
    "stage_tcl": campaign.STAGE_TCL,
    "forensic_tcl": campaign.FORENSIC_TCL,
    "runtime_guard": ROOT / "scripts/p10_tfdu_runtime_guard.py",
}
# A hardware-runner-only remediation may be frozen after the FPGA/ELF source
# commit without rebuilding byte-identical target artifacts.  The descendant
# is admissible only when every intervening path is evidence, an immutable
# artifact copy, the current-run authorization, generated traceability, or one
# of the explicitly audited host harness/test files below.  Any RTL, firmware,
# constraints, board configuration, register-map, build-script, or other path
# change remains fail-closed and requires a new complete artifact build.
POST_ARTIFACT_ALLOWED_EXACT = {
    "config/project_state.json",
    "config/p10_5_current_run_hardware_authorization.json",
    "config/project_requirements.yaml",
    "docs/REQUIREMENT_TRACEABILITY_MATRIX.md",
    "docs/hardware/P10_3_AS_WIRED_RECORD.md",
    "scripts/create_p10_5_authorization.py",
    "scripts/freeze_p10_5_artifacts.py",
    "scripts/hw/p10_program_dual_shutdown.tcl",
    "scripts/run_p10_5_hardware.py",
    "tests/test_p10_5_hardware.py",
}
POST_ARTIFACT_ALLOWED_PREFIXES = (
    "artifacts/p10_5/", "evidence/", "reports/")
MODULE_IDENTITY_RECORD_PATHS = {
    "config/hardware/p10_3_actual_wiring.yaml",
    "config/hardware/tfdu_module_inventory.yaml",
}
TCLSH = Path(r"D:\Xilinx\Vivado\2023.1\tps\win64\git-2.16.2\mingw64\bin\tclsh.exe")
GATES = {
    "p10_5_runner_unit": [sys.executable, "-m", "unittest", "tests.test_p10_5_hardware"],
    "p10_5_firmware_unit": [sys.executable, "-m", "unittest", "tests.test_p10_5_firmware_contract"],
    "tcl_complete": [str(TCLSH), "scripts/hw/check_tcl_complete.tcl",
                     "scripts/hw/p10_dual_xsdb_stage.tcl",
                     "scripts/hw/p10_3f_fault_forensics.tcl",
                     "scripts/hw/p10_program_dual_shutdown.tcl"],
    "register_map": [sys.executable, "scripts/generate_register_headers.py", "--verify"],
    "p10_5_config": [sys.executable, "scripts/generate_p10_5_config.py", "--verify"],
    "p10_5_model": [sys.executable, "scripts/model_p10_5_dual_direction.py"],
    "p10_5_offline": [sys.executable, "scripts/finalize_p10_5_offline.py"],
    "p10_4_baseline": [sys.executable, "scripts/prepare_p10_5_offline.py"],
    "p10_3_baseline": [sys.executable, "scripts/verify_p10_3_existing.py"],
    "p10_2_baseline": [sys.executable, "scripts/verify_p10_2_existing.py"],
    "p10_1r_baseline": [sys.executable, "scripts/verify_p10_1r_existing.py"],
    "p8c_safety": [sys.executable, "scripts/verify_p8c_existing.py"],
    "state_requirements": [sys.executable, "scripts/check_p8a_consistency.py", "--check"],
    "traceability": [sys.executable, "scripts/generate_requirement_traceability.py", "--check"],
    "no_hardware_static": [sys.executable, "scripts/check_no_hardware_calls.py"],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path),
            "bytes": path.stat().st_size}


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {path}")
    return value


def post_artifact_path_allowed(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return normalized in POST_ARTIFACT_ALLOWED_EXACT or any(
        normalized.startswith(prefix)
        for prefix in POST_ARTIFACT_ALLOWED_PREFIXES)


def _yaml_at(commit: str, path: str) -> dict[str, Any]:
    text = subprocess.check_output(
        ["git", "show", f"{commit}:{path}"], cwd=ROOT, text=True,
        encoding="utf-8", errors="strict")
    value = yaml.safe_load(text)
    if not isinstance(value, dict):
        raise ValueError(f"YAML root is not a mapping: {path}")
    return value


def _actual_wiring_target_projection(value: dict[str, Any]) -> dict[str, Any]:
    projected = copy.deepcopy(value)
    for key in ("status", "recorded_at_local", "user_source"):
        projected.pop(key, None)
    for module in projected.get("module_positions", {}).values():
        if isinstance(module, dict):
            module.pop("small_board_id", None)
    declaration = projected.get("physical_state_declaration", {})
    if isinstance(declaration, dict):
        for key in (
                "pre_run_user_module_replacements",
                "latest_pre_run_user_module_replacement", "replacement_source",
                "replacement_power_state", "codex_physical_action_for_replacement"):
            declaration.pop(key, None)
    return projected


def _module_inventory_target_projection(value: dict[str, Any]) -> dict[str, Any]:
    projected = copy.deepcopy(value)
    for key in ("status", "last_updated_at_utc", "quarantine",
                "pending_electronic_intake", "evidence"):
        projected.pop(key, None)
    for key in list(projected):
        if "_replacement_" in key:
            projected.pop(key, None)
    installation = projected.get("p10_3_current_installation", {})
    if isinstance(installation, dict):
        installation.pop("verification", None)
        for module in installation.get("modules", {}).values():
            if isinstance(module, dict):
                module.pop("small_board_id", None)
                module.pop("inventory_status", None)
    return projected


def _module_binding(value: dict[str, Any], path: str) -> dict[str, str]:
    if path.endswith("p10_3_actual_wiring.yaml"):
        modules = value.get("module_positions", {})
    else:
        installation = value.get("p10_3_current_installation", {})
        modules = installation.get("modules", {}) if isinstance(installation, dict) else {}
    if not isinstance(modules, dict) or not modules:
        raise ValueError(f"module binding unavailable: {path}")
    binding = {
        str(name): str(item["small_board_id"])
        for name, item in modules.items()
        if isinstance(item, dict) and item.get("small_board_id")
    }
    if set(binding) != set(map(str, modules)) or len(set(binding.values())) != len(binding):
        raise ValueError(f"module binding is incomplete or non-unique: {path}")
    return binding


def _module_identity_records_allowed(source: str, head: str,
                                     changed: list[str]) -> bool:
    relevant = MODULE_IDENTITY_RECORD_PATHS.intersection(changed)
    if not relevant:
        return True
    try:
        before = {path: _yaml_at(source, path) for path in relevant}
        after = {path: _yaml_at(head, path) for path in relevant}
        projections = {
            "config/hardware/p10_3_actual_wiring.yaml":
                _actual_wiring_target_projection,
            "config/hardware/tfdu_module_inventory.yaml":
                _module_inventory_target_projection,
        }
        if any(projections[path](before[path]) != projections[path](after[path])
               for path in relevant):
            return False
        current_records = {
            path: _yaml_at(head, path) for path in MODULE_IDENTITY_RECORD_PATHS}
        bindings = [_module_binding(current_records[path], path)
                    for path in sorted(MODULE_IDENTITY_RECORD_PATHS)]
        return bindings[0] == bindings[1]
    except (KeyError, OSError, subprocess.CalledProcessError,
            UnicodeError, ValueError, yaml.YAMLError):
        return False


def post_artifact_changes(source: str, head: str) -> tuple[list[str], list[str]]:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=ACDMRTUXB",
         f"{source}..{head}"], cwd=ROOT, text=True
    ).splitlines()
    changed = [path.replace("\\", "/") for path in changed if path]
    identity_records_allowed = _module_identity_records_allowed(
        source, head, changed)
    disallowed = [
        path for path in changed
        if not post_artifact_path_allowed(path)
        and not (path in MODULE_IDENTITY_RECORD_PATHS
                 and identity_records_allowed)
    ]
    return changed, disallowed


def run_gate(name: str, command: list[str]) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    try:
        result = subprocess.run(
            command, cwd=ROOT,
            env={**os.environ, "NO_HARDWARE": "1",
                 "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
            text=True, encoding="utf-8", errors="replace",
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            timeout=1800, check=False)
        output, returncode = result.stdout, result.returncode
    except (OSError, subprocess.SubprocessError) as exc:
        output, returncode = f"EXCEPTION={exc!r}\n", -1
    log = RAW / f"{name}.log"
    log.write_text(output, encoding="utf-8", newline="\n")
    return {"status": "PASS" if returncode == 0 else "FAIL",
            "command": command, "returncode": returncode, "log": metadata(log)}


def role(summary: dict[str, Any], name: str) -> dict[str, Any]:
    found = [x for x in summary.get("roles", []) if x.get("role") == name]
    if len(found) != 1:
        raise ValueError(f"exactly one {name} role required")
    return found[0]


def artifact(role_name: str, kind: str, item: dict[str, Any],
             source: str) -> dict[str, Any]:
    path = (ROOT / item["path"]).resolve()
    expected = (ROOT / "artifacts/p10_5" / source / item["sha256"]).resolve()
    if path.parent != expected or not path.is_file() or \
            path.stat().st_size != item["bytes"] or sha256(path) != item["sha256"] or \
            item.get("read_only") is not True:
        raise ValueError(f"{role_name}:{kind} immutable artifact mismatch")
    return {"role": role_name, "kind": kind, **metadata(path), "read_only": True}


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1" or os.environ.get(
        "CURRENT_RUN_HARDWARE_AUTHORIZATION", "false"
    ).lower() != "false":
        errors.append("offline environment gates are not set")
    branch = subprocess.check_output(["git", "branch", "--show-current"],
                                     cwd=ROOT, text=True).strip()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()
    source_tree_clean = not subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=ROOT, text=True
    ).strip()
    if not source_tree_clean:
        errors.append("worktree must be clean before artifact freeze")
    if branch != BRANCH:
        errors.append(f"branch mismatch: {branch}")
    summaries: dict[str, dict[str, Any]] = {}
    for name, path in SUMMARIES.items():
        try:
            summaries[name] = load(path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{name} summary unavailable: {exc}")
    commits = {str(x.get("source_commit", "")) for x in summaries.values()}
    source = next(iter(commits), "") if len(commits) == 1 else ""
    post_artifact_files: list[str] = []
    if not re.fullmatch(r"[0-9a-f]{40}", source):
        errors.append(f"build-summary source mismatch: {sorted(commits)}")
    elif subprocess.run(
        ["git", "merge-base", "--is-ancestor", source, head], cwd=ROOT,
        check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    ).returncode != 0:
        errors.append(f"artifact source is not an ancestor of HEAD: {source} / {head}")
    else:
        post_artifact_files, disallowed = post_artifact_changes(source, head)
        errors += [f"post-artifact target-affecting change requires rebuild: {path}"
                   for path in disallowed]
    for name, summary in summaries.items():
        if summary.get("status") != "PASS":
            errors.append(f"{name} build is not PASS")
        if summary.get("source_worktree_dirty") is not False:
            errors.append(f"{name} source worktree was dirty")
        if summary.get("hardware_actions_executed") is not False:
            errors.append(f"{name} build executed hardware")
    gates = {name: run_gate(name, command) for name, command in GATES.items()}
    errors += [f"offline gate failed: {name}" for name, item in gates.items()
               if item["status"] != "PASS"]
    offline_inputs: dict[str, dict[str, Any]] = {}
    for name, path in OFFLINE_INPUTS.items():
        try:
            offline_inputs[name] = metadata(path)
        except OSError as exc:
            errors.append(f"offline input unavailable: {name}: {exc}")
    artifacts: list[dict[str, Any]] = []
    if not errors:
        try:
            for role_name in ("fixed", "rotating"):
                functional = role(summaries["functional"], role_name)
                shutdown = role(summaries["shutdown"], role_name)
                runtime = role(summaries["ps_runtime"], role_name)
                markers = functional["markers"]
                required_markers = {
                    "P10_CAMPAIGN": "p10_5",
                    "P10_PL_BUILD_ID": f"0x{campaign.EXPECTED_BUILD[role_name]:08X}",
                    "P10_FUNCTIONAL_BUILD": "PASS",
                    "P10_5_DUAL_DIRECTION_CAPABLE": "true",
                    "P10_5_CAPABILITY_WORD": "0x5035021F",
                    "P10_5_ROLE_COMMIT_ATOMIC": "true",
                    "P10_5_SINGLE_GLOBAL_PERMIT_UNCHANGED": "true",
                    "P10_CDC_CRITICAL_COUNT": "0",
                    "P10_DRC_CRITICAL_COUNT": "0",
                    "P10_DRC_ERROR_COUNT": "0",
                    "P10_REQP_1839_COUNT": "0",
                    "P10_RESOURCE_LIMITS_PASS": "1",
                }
                for key, value in required_markers.items():
                    if markers.get(key) != value:
                        raise ValueError(f"{role_name} marker {key} mismatch")
                if float(markers["P10_WNS_NS"]) < 0 or float(markers["P10_WHS_NS"]) < 0 or \
                        float(markers["P10_TNS_NS"]) != 0:
                    raise ValueError(f"{role_name} timing is not closed")
                artifacts += [
                    artifact(role_name, "shutdown_bitstream", shutdown["artifact"], source),
                    artifact(role_name, "functional_bitstream",
                             functional["artifacts"]["bitstream"], source),
                    artifact(role_name, "xsa", functional["artifacts"]["xsa"], source),
                    artifact(role_name, "bsp", runtime["artifacts"]["bsp"], source),
                    artifact(role_name, "elf", runtime["artifacts"]["elf"], source),
                ]
        except (KeyError, OSError, TypeError, ValueError) as exc:
            errors.append(f"artifact extraction failed: {exc}")
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema_version": 1, "test_id": "P10_5-IMMUTABLE-ARTIFACT-FREEZE",
        "status": status, "scope": campaign.SCOPE, "branch": branch,
        "source_commit": source, "artifact_source_commit": source,
        "harness_commit": head, "post_artifact_files": post_artifact_files,
        "goal_sha256": campaign.GOAL_SHA256,
        "acceptance_eligible": status == "PASS",
        "source_tree_clean": source_tree_clean,
        "no_hardware": True, "current_run_hardware_authorization": False,
        "hardware_actions_executed": False, "old_hardware_pass_inherited": False,
        "automation_only": True, "user_hold_points": 0,
        "maximum_lane_mask": 15, "maximum_single_formal_run_seconds": 1800,
        "maximum_continuous_module_runtime_seconds": 1800,
        "minimum_interstage_cooldown_ratio": 0.5,
        "expected_build_ids": {key: f"0x{value:08X}"
                               for key, value in campaign.EXPECTED_BUILD.items()},
        "register_map": {"version": f"0x{campaign.REGISTER_MAP_VERSION:08X}",
                         "hash_low": f"0x{campaign.REGISTER_MAP_HASH_LOW:08X}"},
        "shutdown_policy": campaign.SHUTDOWN_POLICY,
        "allowed_hardware_stages": list(campaign.STAGES),
        "allowed_plan_sha256": campaign.plan_hashes(),
        "offline_inputs": offline_inputs, "artifacts": artifacts,
        "offline_gates": gates,
        "build_evidence": {name: metadata(path) for name, path in SUMMARIES.items()
                           if path.is_file()},
        "errors": errors, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    FREEZE.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                      encoding="utf-8", newline="\n")
    lines = ["# P10.5 immutable artifact freeze", "", f"- Status: `{status}`",
             f"- Artifact source commit: `{source or 'NONE'}`",
             f"- Harness commit: `{head}`",
             "- Hardware actions executed: `false`", "", "## Artifacts", ""]
    lines += [f"- `{x['role']}:{x['kind']}` `{x['sha256']}` `{x['path']}`"
              for x in artifacts]
    if errors:
        lines += ["", "## Errors", ""] + [f"- {x}" for x in errors]
    FREEZE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"P10_5_ARTIFACT_FREEZE={status}")
    print(f"P10_5_SOURCE_COMMIT={source or 'NONE'}")
    print(f"P10_5_ARTIFACT_COUNT={len(artifacts)}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
