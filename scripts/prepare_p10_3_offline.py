#!/usr/bin/env python3
"""Generate P10.3 repository, wiring, and module-intake evidence (offline-build-only)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

import run_p10_3_ax7020_4lane_hardware as p103


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
EXPECTED_BRANCH = "p10.3/ax7020-stationary-4lane-hardware"
P10_2_TAG_OBJECT = "bf7c966fcda3e17665c7eae4c0179aec99f020ff"
P10_2_TAG_TARGET = "08771d6bf9e852c9d34bcff61add1598e120b70a"
P10_1R_PASS_OBJECT = "c78066152e2d5ac0c673e21896fb90b9a78f7489"
P10_1R_PASS_TARGET = "9321ca2f1797eb12bfb02848c3ee27145e1e8eb4"
P10_1R_CLOSED_OBJECT = "c0998935ddd19f44177540ea260a917c9ac54bad"
P10_1R_CLOSED_TARGET = "e90a2203c4d6b71f93e0ee1c5bf93bb263c8a1b8"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def metadata(path: Path) -> dict[str, Any]:
    return {"path": rel(path), "sha256": sha256(path), "bytes": path.stat().st_size}


def write_pair(stem: str, payload: dict[str, Any], title: str) -> None:
    GENERATED.mkdir(parents=True, exist_ok=True)
    json_path = GENERATED / f"{stem}.json"
    md_path = GENERATED / f"{stem}.md"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    lines = [f"# {title}", "", f"- Status: `{payload['status']}`",
             f"- Test ID: `{payload['test_id']}`",
             "- Hardware actions executed: `false`", ""]
    if "source_commit" in payload:
        lines.append(f"- Source commit: `{payload['source_commit']}`")
    if "sha256" in payload:
        lines.append(f"- Canonical SHA256: `{payload['sha256']}`")
    errors = payload.get("errors", [])
    if errors:
        lines += ["", "## Errors", ""] + [f"- {error}" for error in errors]
    lines += ["", "```json", json.dumps(payload, indent=2, sort_keys=True,
                                           ensure_ascii=False), "```", ""]
    md_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def tool_version(command: list[str]) -> dict[str, Any]:
    try:
        result = subprocess.run(
            command, cwd=ROOT, text=True, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, timeout=60, check=False,
        )
        output = result.stdout.strip().splitlines()
        return {"command": command, "returncode": result.returncode,
                "first_lines": output[:5]}
    except (OSError, subprocess.SubprocessError) as exc:
        return {"command": command, "returncode": None, "error": str(exc)}


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() not in {
        "false", "0", "no",
    }:
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    branch = git("branch", "--show-current")
    head = git("rev-parse", "HEAD")
    initial_status = git("status", "--porcelain")
    if branch != EXPECTED_BRANCH:
        errors.append(f"branch mismatch: {branch}")
    if initial_status:
        errors.append("offline intake requires a clean worktree before generating evidence")
    errors.extend(p103.validate_goal_files())
    errors.extend(p103.validate_baseline_refs())
    wiring, inventory, intake_errors = p103.validate_wiring_inventory()
    errors.extend(intake_errors)
    errors.extend(p103.validate_plans(p103.build_plans()))
    tag_records = {
        "p10_2": {
            "tag": p103.P10_2_TAG,
            "object": git("rev-parse", p103.P10_2_TAG),
            "target": git("rev-list", "-n", "1", p103.P10_2_TAG),
            "expected_object": P10_2_TAG_OBJECT,
            "expected_target": P10_2_TAG_TARGET,
        },
        "p10_1r_pass": {
            "tag": p103.P10_1R_PASS_TAG,
            "object": git("rev-parse", p103.P10_1R_PASS_TAG),
            "target": git("rev-list", "-n", "1", p103.P10_1R_PASS_TAG),
            "expected_object": P10_1R_PASS_OBJECT,
            "expected_target": P10_1R_PASS_TARGET,
        },
        "p10_1r_closed": {
            "tag": p103.P10_1R_CLOSED_TAG,
            "object": git("rev-parse", p103.P10_1R_CLOSED_TAG),
            "target": git("rev-list", "-n", "1", p103.P10_1R_CLOSED_TAG),
            "expected_object": P10_1R_CLOSED_OBJECT,
            "expected_target": P10_1R_CLOSED_TARGET,
        },
    }
    for name, record in tag_records.items():
        if record["object"] != record["expected_object"] or \
                record["target"] != record["expected_target"]:
            errors.append(f"immutable tag binding mismatch: {name}")
    inputs = [
        ROOT / "PROJECT_CONSTRAINTS.txt", ROOT / "AGENTS.md",
        ROOT / "config/project_state.json", ROOT / "config/project_requirements.yaml",
        ROOT / "config/register_map/ir_axi_regs.yaml", p103.WIRING, p103.INVENTORY,
        ROOT / "board_profiles/ax7020_fixed_4lane/profile.yaml",
        ROOT / "board_profiles/ax7020_rotating_4lane/profile.yaml",
        ROOT / "board_profiles/ax7020_fixed_4lane/ax7020_fixed_4lane.generated.xdc",
        ROOT / "board_profiles/ax7020_rotating_4lane/ax7020_rotating_4lane.generated.xdc",
    ]
    input_records = [metadata(path) for path in inputs]
    repo = {
        "schema_version": 1,
        "test_id": "P10_3-REPOSITORY-INTAKE",
        "status": "PASS" if not errors else "FAIL",
        "scope": p103.SCOPE,
        "worktree": str(ROOT),
        "branch": branch,
        "source_commit": head,
        "git_status_before_generation": initial_status.splitlines(),
        "source_tree_clean_before_generation": not bool(initial_status),
        "goal": metadata(p103.GOAL),
        "external_goal": {
            "path": str(p103.EXTERNAL_GOAL),
            "sha256": sha256(p103.EXTERNAL_GOAL),
            "bytes": p103.EXTERNAL_GOAL.stat().st_size,
        },
        "immutable_tags": tag_records,
        "inputs": input_records,
        "tools": {
            "python": tool_version([sys.executable, "--version"]),
            "git": tool_version(["git", "--version"]),
            "vivado": tool_version([r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat", "-version"]),
            "xsct": tool_version([r"D:\Xilinx\Vitis\2023.1\bin\xsct.bat", "-eval", "puts [version -short]"]),
        },
        "current_run_hardware_authorization": False,
        "no_hardware": True,
        "hardware_actions_executed": False,
        "network_used": False,
        "started_at_utc": utc_now(),
        "errors": errors,
    }
    wiring_payload = {
        "schema_version": 1,
        "test_id": "P10_3-WIRE-001",
        "status": "PASS" if not intake_errors else "FAIL",
        "scope": "P10_3_ACTUAL_WIRING_FREEZE",
        "source_commit": head,
        "canonical_path": rel(p103.WIRING),
        "sha256": sha256(p103.WIRING),
        "bytes": p103.WIRING.stat().st_size,
        "physical_wiring_completed": wiring.get("physical_state_declaration", {}).get(
            "P10_3_PHYSICAL_WIRING_COMPLETED"
        ),
        "board_binding": wiring.get("boards"),
        "lane_pairs": wiring.get("lane_pairs"),
        "module_positions": wiring.get("module_positions"),
        "signal_positions": wiring.get("signal_positions"),
        "package_pins": wiring.get("package_pins"),
        "electrical_contract": wiring.get("electrical_contract"),
        "power_and_ground": wiring.get("power_and_ground"),
        "historical_power_off_during_wiring": wiring.get("physical_state_declaration", {}).get(
            "powered_off_during_historical_wiring"
        ),
        "no_hardware": True,
        "hardware_actions_executed": False,
        "errors": intake_errors,
    }
    active = inventory.get("p10_3_current_installation", {}).get("modules", {})
    identities = [item.get("small_board_id") for item in active.values()
                  if isinstance(item, dict)]
    inventory_payload = {
        "schema_version": 1,
        "test_id": "P10_3-INV-001",
        "status": "PASS" if not intake_errors and len(active) == 8 and
                  len(identities) == len(set(identities)) else "FAIL",
        "scope": "P10_3_MODULE_INVENTORY",
        "source_commit": head,
        "canonical_path": rel(p103.INVENTORY),
        "sha256": sha256(p103.INVENTORY),
        "bytes": p103.INVENTORY.stat().st_size,
        "active_modules": active,
        "active_module_count": len(active),
        "unique_small_board_id_count": len(set(identities)),
        "lane_pairs": inventory.get("p10_3_current_installation", {}).get("lane_pairs"),
        "old_f1_active": inventory.get("p10_3_current_installation", {}).get("old_f1_active"),
        "old_f1_status": inventory.get("p10_3_current_installation", {}).get("old_f1_status"),
        "quarantine": inventory.get("quarantine"),
        "electronic_intake_status": "PENDING_HARDWARE_STAGE",
        "no_hardware": True,
        "hardware_actions_executed": False,
        "errors": intake_errors,
    }
    write_pair("p10_3_repo_intake", repo, "P10.3 repository intake")
    write_pair("p10_3_wiring", wiring_payload, "P10.3 actual wiring freeze")
    write_pair("p10_3_module_inventory", inventory_payload, "P10.3 eight-module inventory")
    print(f"P10_3_REPO_INTAKE={repo['status']}")
    print(f"P10_3_WIRING={wiring_payload['status']}")
    print(f"P10_3_MODULE_INVENTORY={inventory_payload['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    for error in errors:
        print(f"ERROR: {error}")
    return 0 if repo["status"] == wiring_payload["status"] == \
        inventory_payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
