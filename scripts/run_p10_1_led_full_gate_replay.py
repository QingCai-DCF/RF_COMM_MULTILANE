#!/usr/bin/env python3
"""Replay the complete offline gates in an isolated detached worktree.

The LED follow-up has its own routed artifacts and evidence namespace.  The
canonical P10.1 gate rewrites canonical generated evidence, so this wrapper
runs it only in a disposable detached worktree and records the result back in
the LED-specific evidence namespace.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evidence/generated/p10_1_led_full_offline_gate_replay"
RAW = OUT / "raw"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git(*args: str, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
        errors="replace",
    )


def run_command(
    name: str,
    command: list[str],
    *,
    cwd: Path,
    timeout_s: int,
) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        env={
            **os.environ,
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        },
        errors="replace",
    )
    finished = datetime.now(timezone.utc)
    log_path = RAW / f"{name}.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "COMMAND=" + subprocess.list2cmdline(command) + "\n"
        + f"WORKTREE={cwd}\n"
        + f"STARTED_UTC={started.isoformat(timespec='seconds')}\n"
        + f"FINISHED_UTC={finished.isoformat(timespec='seconds')}\n"
        + f"RETURN_CODE={result.returncode}\n"
        + "STDOUT_BEGIN\n" + result.stdout + "STDOUT_END\n"
        + "STDERR_BEGIN\n" + result.stderr + "STDERR_END\n",
        encoding="utf-8",
        newline="\n",
    )
    combined = result.stdout + result.stderr
    return {
        "name": name,
        "command": subprocess.list2cmdline(command),
        "return_code": result.returncode,
        "status": "PASS" if result.returncode == 0 else "FAIL",
        "started_utc": started.isoformat(timespec="seconds"),
        "finished_utc": finished.isoformat(timespec="seconds"),
        "duration_seconds": round((finished - started).total_seconds(), 3),
        "log": log_path.resolve().relative_to(ROOT.resolve()).as_posix(),
        "log_sha256": sha256(log_path),
        "markers": {
            "p10_1_offline_gate_pass": "P10_1_OFFLINE_GATE=PASS" in combined,
            "hardware_actions_false": "HARDWARE_ACTIONS_EXECUTED=false" in combined,
            "current_authorization_false": (
                "CURRENT_RUN_HARDWARE_AUTHORIZATION=false" in combined
            ),
        },
    }


def write_outputs(payload: dict[str, Any]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    json_path = OUT / "summary.json"
    md_path = OUT / "summary.md"
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    lines = [
        "# P10.1 AX7020 PL activity LED full offline gate replay",
        "",
        f"- Status: `{payload['status']}`",
        f"- Detached source commit: `{payload['source_commit']}`",
        "- Hardware actions executed: `false`",
        "- Current-run hardware authorization: `false`",
        "- Replay environment: disposable detached Git worktree",
        "",
        "## Commands",
        "",
    ]
    for item in payload["commands"]:
        lines.append(
            f"- `{item['name']}`: `{item['status']}` "
            f"(`{item['duration_seconds']} s`, `{item['log']}`)"
        )
    if payload["errors"]:
        lines += ["", "## Errors", ""]
        lines.extend(f"- {item}" for item in payload["errors"])
    lines += [
        "",
        "This replay is offline evidence only. It does not reuse or promote any "
        "historical hardware result for the LED-enabled artifacts.",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def archive_existing_output() -> str | None:
    """Retain every previous PASS/FAIL replay before writing a new latest result."""
    summary_path = OUT / "summary.json"
    if not summary_path.is_file():
        return None
    try:
        previous = json.loads(summary_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        previous = {}
    stamp = re.sub(
        r"[^0-9A-Za-z]+",
        "",
        str(previous.get("generated_at_utc", "undated")),
    )
    status = re.sub(r"[^0-9A-Za-z]+", "", str(previous.get("status", "UNKNOWN")))
    base_name = f"{stamp}_{status}"
    archive_root = OUT / "runs"
    archive_root.mkdir(parents=True, exist_ok=True)
    destination = archive_root / base_name
    suffix = 1
    while destination.exists():
        suffix += 1
        destination = archive_root / f"{base_name}_{suffix}"
    destination.mkdir()
    for name in ("summary.json", "summary.md", "raw"):
        source = OUT / name
        if source.exists():
            shutil.move(str(source), str(destination / name))
    return destination.resolve().relative_to(ROOT.resolve()).as_posix()


def preserve_detached_evidence(
    *,
    name: str,
    worktree: Path,
    candidates: list[str],
) -> list[dict[str, Any]]:
    preserved: list[dict[str, Any]] = []
    destination_root = RAW / f"{name}_generated"
    for candidate in candidates:
        source = worktree / candidate
        if not source.is_file():
            continue
        destination_root.mkdir(parents=True, exist_ok=True)
        destination = destination_root / source.name
        shutil.copy2(source, destination)
        preserved.append(
            {
                "source_path": candidate,
                "path": destination.resolve().relative_to(ROOT.resolve()).as_posix(),
                "sha256": sha256(destination),
                "bytes": destination.stat().st_size,
            }
        )
    return preserved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-commit",
        default="HEAD",
        help="Committed source/evidence foundation to replay (default: HEAD).",
    )
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args()

    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    status_before = git("status", "--porcelain").stdout.strip()
    if status_before:
        errors.append("source worktree must be clean before isolated replay")
    try:
        source_commit = git("rev-parse", f"{args.source_commit}^{{commit}}").stdout.strip()
    except subprocess.CalledProcessError as exc:
        errors.append(f"invalid source commit: {exc.stderr.strip()}")
        source_commit = ""

    archived_previous = archive_existing_output() if not errors else None
    commands: list[dict[str, Any]] = []
    cleanup_errors: list[str] = []
    detached_status: dict[str, list[str]] = {}
    if not errors:
        parent = ROOT.parent.resolve()
        specifications = [
            {
                "name": "p10_1_full_offline_gate",
                "worktree_prefix": "P10L1_",
                "command": [
                    sys.executable,
                    "scripts/run_p10_1_offline_gate.py",
                    "--full",
                    "--json-summary",
                ],
                "evidence": [
                    "evidence/generated/p10_1_final_summary.json",
                    "evidence/generated/p10_1_evidence_consistency.json",
                    "evidence/generated/p10_1_raw/p10_1_evidence_sha256_manifest.json",
                ],
            },
            {
                "name": "canonical_p0_p8b_offline_regression",
                "worktree_prefix": "P10L2_",
                "command": [
                    sys.executable,
                    "scripts/run_offline_gates.py",
                    "--include-p8b",
                    "--json-summary",
                ],
                "evidence": [
                    "evidence/generated/offline_gate_summary.json",
                    "evidence/generated/offline_gate_summary.md",
                    "evidence/generated/vivado/nonhardware_build_summary.json",
                    "evidence/generated/vivado/nonhardware_build_summary.md",
                    "evidence/generated/p8b_final_summary.json",
                    "evidence/generated/p8b_final_summary.md",
                    "evidence/generated/plan_completion_audit.md",
                    "evidence/generated/p8b_state_consistency_summary.json",
                    "evidence/generated/p8b_state_consistency_summary.md",
                    "evidence/generated/p8b_simulation_gate_summary.json",
                    "evidence/generated/p8b_simulation_gate_summary.md",
                    "evidence/generated/p8b_xsim/mapping_unit.log",
                    "evidence/generated/p8b_xsim/phase_trajectory.log",
                ],
            },
        ]
        for specification in specifications:
            name = str(specification["name"])
            disposable_root = Path(
                tempfile.mkdtemp(
                    # Keep the detached path deliberately short. Vivado nests
                    # debug-core synthesis paths deeply and fails closed on
                    # Windows when the fully expanded path exceeds 260 bytes.
                    prefix=str(specification["worktree_prefix"]),
                    dir=parent,
                )
            ).resolve()
            # Git requires the worktree destination not to exist.
            disposable_root.rmdir()
            worktree_added = False
            try:
                git("worktree", "add", "--detach", str(disposable_root), source_commit)
                worktree_added = True
                command_result = run_command(
                    name,
                    list(specification["command"]),
                    cwd=disposable_root,
                    timeout_s=10800,
                )
                command_result["preserved_generated_evidence"] = preserve_detached_evidence(
                    name=name,
                    worktree=disposable_root,
                    candidates=list(specification["evidence"]),
                )
                commands.append(command_result)
                detached_status[name] = git(
                    "status", "--porcelain", cwd=disposable_root
                ).stdout.splitlines()
            except (
                OSError,
                subprocess.CalledProcessError,
                subprocess.TimeoutExpired,
            ) as exc:
                errors.append(f"{name} isolated replay execution failed: {exc}")
                detached_status[name] = []
            finally:
                if worktree_added:
                    removal = git(
                        "worktree",
                        "remove",
                        "--force",
                        str(disposable_root),
                        check=False,
                    )
                    if removal.returncode != 0:
                        cleanup_errors.append(
                            removal.stderr.strip()
                            or f"git worktree remove failed for {name}"
                        )
                git("worktree", "prune", check=False)
                if disposable_root.exists():
                    # This exact path was created by this process under the
                    # repository parent and was detached from Git above.
                    shutil.rmtree(disposable_root)

    for item in commands:
        if item["status"] != "PASS":
            errors.append(f"{item['name']} returned {item['return_code']}")
    if commands:
        gate_markers = commands[0]["markers"]
        for marker, present in gate_markers.items():
            if not present:
                errors.append(f"missing P10.1 full-gate marker: {marker}")
    errors.extend(f"cleanup: {item}" for item in cleanup_errors)

    payload = {
        "schema_version": 1,
        "test_id": "P10_1-LED-FULL-OFFLINE-GATE-REPLAY",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PASS" if not errors else "FAIL",
        "source_commit": source_commit or None,
        "source_branch": git("branch", "--show-current").stdout.strip(),
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        "network_used": False,
        "commands": commands,
        "detached_generated_changes": detached_status,
        "archived_previous_replay": archived_previous,
        "cleanup_status": "PASS" if not cleanup_errors else "FAIL",
        "errors": errors,
    }
    write_outputs(payload)
    print(f"P10_1_LED_FULL_OFFLINE_REPLAY={payload['status']}")
    print("HARDWARE_ACTIONS_EXECUTED=false")
    print("CURRENT_RUN_HARDWARE_AUTHORIZATION=false")
    if args.json_summary:
        print(json.dumps(payload, sort_keys=True))
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
