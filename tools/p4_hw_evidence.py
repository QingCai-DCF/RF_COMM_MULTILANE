#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence" / "generated"
P4_DIR = ROOT / "evidence" / "hardware" / "p4"
NO_HW_LINE = "NO_HARDWARE_ACTIONS_EXECUTED: true"
PENDING_HW_LINE = "HARDWARE_ACCEPTANCE: PENDING_HW"


P4_SUBDIRS = [
    P4_DIR,
    P4_DIR / "raw_pulse_smoke",
    P4_DIR / "raw_lane_matrix",
    P4_DIR / "protocol_smoke",
    P4_DIR / "soak",
    P4_DIR / "shutdown",
    P4_DIR / "failures",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path | str) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def read_text(path: Path | str) -> str:
    return Path(path).read_text(encoding="utf-8", errors="ignore")


def write_text(path: Path | str, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def write_json(path: Path | str, payload: dict) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_or_missing(path: Path | str) -> str:
    path = Path(path)
    if not path.exists() or not path.is_file():
        return "MISSING"
    return sha256(path)


def run_cmd(cmd: list[str], timeout: int = 120) -> dict:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError as exc:
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": 127,
            "stdout": "",
            "stderr": str(exc),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "timeout",
        }


def git_value(*args: str) -> str:
    proc = run_cmd(["git", *args], timeout=30)
    if proc["returncode"] != 0:
        return (proc["stderr"] or proc["stdout"]).strip()
    return proc["stdout"].strip()


def load_json(path: Path | str) -> dict:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def json_from_stdout(stdout: str) -> dict:
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


def parse_markers_from_text(text: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().split()[0] if value.strip() else ""
        if key and key.replace("_", "").isalnum() and key.upper() == key:
            markers[key] = value
    return markers


def parse_markers(path: Path | str) -> dict[str, str]:
    path = Path(path)
    if not path.exists():
        return {}
    return parse_markers_from_text(read_text(path))


def ensure_p4_dirs() -> None:
    for item in P4_SUBDIRS:
        item.mkdir(parents=True, exist_ok=True)
    write_text(
        P4_DIR / "failures" / "README.md",
        """# P4 Failure Evidence

This directory is reserved for P4 failure evidence from an authorized hardware
run. A no-authorization dry run must not create false hardware failures here.
""",
    )


def markdown_header(title: str, result: str, reason: str, *, no_hw: bool = True) -> list[str]:
    return [
        f"# {title}",
        "",
        f"generated_at_utc: {now_iso()}",
        f"repo: `{ROOT}`",
        f"HEAD: `{git_value('rev-parse', 'HEAD')}`",
        f"RESULT: {result}",
        f"REASON: {reason}",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hw).lower()}",
        PENDING_HW_LINE,
        "",
    ]


def write_markdown(path: Path | str, title: str, result: str, reason: str, lines: list[str] | None = None, *, no_hw: bool = True) -> None:
    body = markdown_header(title, result, reason, no_hw=no_hw)
    if lines:
        body.extend(lines)
        body.append("")
    write_text(path, "\n".join(body))


def active_hashes() -> dict[str, str]:
    paths = {
        "agents_md": ROOT / "AGENTS.md",
        "constraint_file": ROOT / "项目约束(目标）.txt",
        "active_profile": ROOT / "board_profiles" / "ACTIVE_PROFILE.json",
        "active_xdc": ROOT / "constraints" / "active" / "PORT1.generated.xdc",
        "pinmap": ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv",
        "tfdu_safety_contract": ROOT / "docs" / "tfdu6102_safety_contract.md",
        "tfdu_safety_summary": ROOT / "docs" / "TFDU6102_SAFETY_SUMMARY.md",
    }
    return {name: sha256_or_missing(path) for name, path in paths.items()}


def current_gate_statuses() -> dict[str, str]:
    data = load_json(GENERATED / "offline_gate_summary.json")
    p1 = data.get("P1_OFFLINE_HARDENING")
    p2 = data.get("P2_SIMULATION_BASELINE")
    p3 = data.get("P3_PRE_HW_ACCEPTANCE_PACKAGE")
    if not p1:
        p1 = parse_markers(GENERATED / "p1_offline_hardening_summary.md").get("P1_OFFLINE_HARDENING", "UNKNOWN")
    if not p2:
        p2 = parse_markers(GENERATED / "p2_simulation_baseline_summary.md").get("P2_SIMULATION_BASELINE", "UNKNOWN")
    if not p3:
        p3 = parse_markers(GENERATED / "p3_pre_hw_acceptance_package_summary.md").get("P3_PRE_HW_ACCEPTANCE_PACKAGE", "UNKNOWN")
    return {
        "P1_RECHECK": p1 or "UNKNOWN",
        "P2_RECHECK": p2 or "UNKNOWN",
        "P3_RECHECK": p3 or "UNKNOWN",
    }


def candidate_bitstream_metadata() -> dict[str, str]:
    summary = load_json(GENERATED / "vivado" / "nonhardware_build_summary.json")
    candidate = summary.get("bitstream_path") or summary.get("bitstream") or ""
    candidate_path = ROOT / candidate if candidate else None
    return {
        "bitstream_candidate_path": candidate or "SKIP_WITH_REASON: no non-hardware bitstream candidate recorded",
        "bitstream_candidate_sha256": sha256_or_missing(candidate_path) if candidate_path else "SKIP_WITH_REASON",
        "bitstream_candidate_status": "BITSTREAM_GENERATED_NO_HW" if candidate else "SKIP_WITH_REASON",
    }


def write_repo_intake() -> dict:
    status = git_value("status", "--short")
    statuses = current_gate_statuses()
    lines = [
        f"branch: `{git_value('branch', '--show-current')}`",
        f"dirty_state: `{'clean' if not status else 'dirty'}`",
        f"P1_RECHECK: {statuses['P1_RECHECK']}",
        f"P2_RECHECK: {statuses['P2_RECHECK']}",
        f"P3_RECHECK: {statuses['P3_RECHECK']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Git Status",
        "",
        "```text",
        status or "(clean)",
        "```",
    ]
    write_markdown(
        GENERATED / "p4_repo_intake.md",
        "P4 Repo Intake",
        "PASS",
        "repository state and prior gate markers recorded without hardware access",
        lines,
    )
    return {"result": "PASS", "path": rel(GENERATED / "p4_repo_intake.md"), **statuses}


def write_recheck_summary(command_results: list[dict]) -> dict:
    statuses = current_gate_statuses()
    failures = [item for item in command_results if item.get("returncode", 1) != 0]
    prereq_pass = all(statuses.get(key) in {"PASS", "PASS_WITH_SKIPS"} for key in ["P1_RECHECK", "P2_RECHECK", "P3_RECHECK"])
    result = "PASS" if prereq_pass and not failures else "FAIL"
    lines = [
        f"P1_RECHECK: {statuses['P1_RECHECK']}",
        f"P2_RECHECK: {statuses['P2_RECHECK']}",
        f"P3_RECHECK: {statuses['P3_RECHECK']}",
        "NO_HARDWARE_ACTIONS_EXECUTED: true",
        "HARDWARE_ACCEPTANCE: PENDING_HW",
        "",
        "## Commands",
        "",
    ]
    for item in command_results:
        lines.append(f"- `{item.get('cmd')}` -> rc={item.get('returncode')}")
    lines.extend(["", "## Command Evidence", "", "```json", json.dumps(command_results, indent=2, ensure_ascii=False)[-12000:], "```"])
    write_markdown(
        GENERATED / "p4_recheck_p1_p2_p3_summary.md",
        "P4 Recheck P1 P2 P3 Summary",
        result,
        "P1/P2/P3 recheck markers are acceptable" if result == "PASS" else "P1/P2/P3 recheck blocked P4",
        lines,
    )
    return {"result": result, "path": rel(GENERATED / "p4_recheck_p1_p2_p3_summary.md"), **statuses}


def tool_versions_text() -> str:
    py = sys.version.replace("\n", " ")
    git = run_cmd(["git", "--version"], timeout=30)
    return "\n".join(
        [
            "P4_TOOL_VERSION_CAPTURE: SKIP_NOT_AUTHORIZED",
            "NO_HARDWARE_ACTIONS_EXECUTED: true",
            "HARDWARE_ACCEPTANCE: PENDING_HW",
            f"python: {py}",
            f"git: {(git['stdout'] or git['stderr']).strip()}",
            "vivado: SKIP_NOT_AUTHORIZED",
            "vitis_xsct: SKIP_NOT_AUTHORIZED",
            "system_debugger: SKIP_NOT_AUTHORIZED",
        ]
    )
