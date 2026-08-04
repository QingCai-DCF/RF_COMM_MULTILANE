#!/usr/bin/env python3
"""Finalize P10.3F offline requirements and evidence without hardware."""

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


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
FREEZE = GENERATED / "p10_3_fault_forensics_artifact_freeze.json"
OFFLINE = GENERATED / "p10_3_fault_forensics_offline.json"
REQUIREMENTS = ROOT / "config/project_requirements.yaml"
TRACEABILITY = ROOT / "docs/REQUIREMENT_TRACEABILITY_MATRIX.md"
FINAL = GENERATED / "p10_3_fault_forensics_final_summary.json"
FINAL_MD = GENERATED / "p10_3_fault_forensics_final_summary.md"
CONSISTENCY = GENERATED / "p10_3_fault_forensics_evidence_consistency.json"
OFFLINE_IDS = (
    "P10_3F-OFF-001", "P10_3F-OFF-002", "P10_3F-OFF-003", "P10_3F-OFF-004",
)
HARDWARE_IDS = ("P10_3F-HW-001", "P10_3F-HW-002", "P10_3F-HW-003")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root is not an object: {rel(path)}")
    return value


def evidence_record(path: Path) -> dict[str, str]:
    return {"path": rel(path), "sha256": sha256(path)}


def update_requirement_block(text: str, requirement_id: str,
                             records: list[dict[str, str]]) -> str:
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines)
                  if line == f"- requirement_id: {requirement_id}"), None)
    if start is None:
        raise ValueError(f"missing requirement {requirement_id}")
    end = next((index for index in range(start + 1, len(lines))
                if lines[index].startswith("- requirement_id: ") or
                lines[index].startswith("# END ")), len(lines))
    block = lines[start:end]
    status_indexes = [index for index, line in enumerate(block)
                      if line.startswith("  status:")]
    artifact_indexes = [index for index, line in enumerate(block)
                        if line.startswith("  artifact_hashes:")]
    if len(status_indexes) != 1 or len(artifact_indexes) != 1:
        raise ValueError(f"malformed requirement block {requirement_id}")
    block[status_indexes[0]] = "  status: PASS"
    artifact_start = artifact_indexes[0]
    artifact_end = artifact_start + 1
    while artifact_end < len(block) and (
        block[artifact_end].startswith("  - ") or block[artifact_end].startswith("    ")
    ):
        artifact_end += 1
    replacement = ["  artifact_hashes:"]
    for record in records:
        replacement.extend([
            f"  - path: {record['path']}",
            f"    sha256: {record['sha256']}",
        ])
    block[artifact_start:artifact_end] = replacement
    return "\n".join(lines[:start] + block + lines[end:]) + "\n"


def main() -> int:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() not in {
        "false", "0", "no",
    }:
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    try:
        freeze = load_json(FREEZE)
        offline = load_json(OFFLINE)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
        freeze, offline = {}, {}
    if freeze.get("status") != "PASS" or freeze.get("acceptance_eligible") is not True:
        errors.append("artifact freeze is not PASS/eligible")
    if offline.get("status") != "PASS":
        errors.append("offline summary is not PASS")
    if freeze.get("source_commit") != offline.get("source_commit"):
        errors.append("freeze/offline source commit mismatch")
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    if freeze.get("source_commit") != head:
        errors.append("HEAD does not equal frozen source commit before finalization")
    if errors:
        print("P10_3F_FINALIZE=FAIL")
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    artifacts = [item for item in freeze.get("artifacts", []) if isinstance(item, dict)]
    functional = [item for item in artifacts if item.get("kind") == "functional_bitstream"]
    common_paths = [
        ROOT / "rtl/p10_fault_forensics.sv",
        ROOT / "sim/tb/tb_p10_fault_forensics.sv",
        ROOT / "sim/tb/tb_p10_forensic_safety_integration.sv",
        ROOT / "config/safety/p10_3_fault_forensics.yaml",
        ROOT / "config/performance/p10_3f_staircase.yaml",
        ROOT / "scripts/archive_p10_fault_forensics.py",
        ROOT / "scripts/run_p10_3f_staircase_hardware.py",
        ROOT / "evidence/generated/p10_3_fault_forensics_xsim/summary.json",
        OFFLINE,
    ]
    records = [evidence_record(path) for path in common_paths]
    records.extend({"path": item["path"], "sha256": item["sha256"]}
                   for item in functional)
    requirement_text = REQUIREMENTS.read_text(encoding="utf-8")
    for requirement_id in OFFLINE_IDS:
        requirement_text = update_requirement_block(
            requirement_text, requirement_id, records
        )
    REQUIREMENTS.write_text(requirement_text, encoding="utf-8", newline="\n")
    document = yaml.safe_load(requirement_text)
    by_id = {item["requirement_id"]: item for item in document["requirements"]}
    for requirement_id in OFFLINE_IDS:
        if by_id[requirement_id]["status"] != "PASS" or not by_id[requirement_id]["artifact_hashes"]:
            errors.append(f"offline requirement did not advance: {requirement_id}")
    for requirement_id in HARDWARE_IDS:
        if by_id[requirement_id]["status"] != "PENDING":
            errors.append(f"hardware requirement was promoted: {requirement_id}")

    trace = subprocess.run(
        [sys.executable, "scripts/generate_requirement_traceability.py", "--write"],
        cwd=ROOT, env={**os.environ, "NO_HARDWARE": "1",
                      "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        timeout=120, check=False,
    )
    if trace.returncode != 0:
        errors.append(f"traceability generation failed: {trace.stdout.strip()}")
    status = "PASS" if not errors else "FAIL"
    payload = {
        "schema_version": 1,
        "test_id": "P10_3F-OFFLINE-FINAL",
        "status": status,
        "scope": "P10_3_FIRST_FAULT_FORENSICS_OFFLINE_FOLLOWUP",
        "source_commit": freeze["source_commit"],
        "evidence_checkpoint_parent": head,
        "artifact_freeze": {"path": rel(FREEZE), "sha256": sha256(FREEZE)},
        "offline_evidence": {"path": rel(OFFLINE), "sha256": sha256(OFFLINE)},
        "requirements": {
            "offline_pass": list(OFFLINE_IDS),
            "hardware_pending": list(HARDWARE_IDS),
        },
        "artifacts": artifacts,
        "first_fault_capture_persistence": {
            "functional_reset": True,
            "functional_shutdown": True,
            "fpga_reconfiguration": False,
            "power_loss": False,
        },
        "no_hardware": True,
        "current_run_hardware_authorization": False,
        "hardware_actions_executed": False,
        "manual_instrumentation": "OMITTED_BY_USER",
        "old_hardware_pass_inherited": False,
        "new_hardware_pass": False,
        "next_required_action": "new current-run authorization bound to this immutable artifact bundle",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "errors": errors,
    }
    FINAL.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    lines = [
        "# P10.3F offline final summary", "", f"- Status: `{status}`",
        f"- Frozen source commit: `{freeze['source_commit']}`",
        "- Hardware actions executed: `false`",
        "- Manual instrumentation: `OMITTED_BY_USER`",
        "- New hardware PASS: `false`",
        "- Old hardware PASS inherited: `false`",
        "- PL reconfiguration or power loss preserves capture: `false`", "",
        "A frozen capture must be archived before loading the independent shutdown image.",
    ]
    if errors:
        lines.extend(["", "## Errors", ""] + [f"- {error}" for error in errors])
    FINAL_MD.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    consistency_errors: list[str] = []
    if sha256(FREEZE) != payload["artifact_freeze"]["sha256"]:
        consistency_errors.append("artifact freeze hash mismatch")
    if sha256(OFFLINE) != payload["offline_evidence"]["sha256"]:
        consistency_errors.append("offline evidence hash mismatch")
    if not TRACEABILITY.is_file():
        consistency_errors.append("traceability matrix missing")
    consistency = {
        "schema_version": 1,
        "test_id": "P10_3F-EVIDENCE-CONSISTENCY",
        "status": "PASS" if status == "PASS" and not consistency_errors else "FAIL",
        "source_commit": freeze["source_commit"],
        "hardware_actions_executed": False,
        "files": [evidence_record(path) for path in
                  (FREEZE, OFFLINE, FINAL, REQUIREMENTS, TRACEABILITY) if path.is_file()],
        "errors": consistency_errors + errors,
    }
    CONSISTENCY.write_text(
        json.dumps(consistency, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"P10_3F_FINALIZE={consistency['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    for error in consistency["errors"]:
        print(f"ERROR: {error}")
    return 0 if consistency["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
