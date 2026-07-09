#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence" / "generated"
P4_AUTO_DIR = ROOT / "evidence" / "hardware" / "p4_auto"
AUTH_DIR = P4_AUTO_DIR / "authorization"
BITSTREAM_DIR = P4_AUTO_DIR / "bitstreams"
SHUTDOWN_DIR = P4_AUTO_DIR / "shutdown"

PENDING_HW = "HARDWARE_ACCEPTANCE: PENDING_HW"
NO_HW = "NO_HARDWARE_ACTIONS_EXECUTED: true"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def rel(path: Path | str) -> str:
    path = Path(path)
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def write_text(path: Path | str, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def write_json(path: Path | str, payload: dict | list) -> None:
    write_text(path, json.dumps(payload, indent=2, ensure_ascii=False))


def write_csv(path: Path | str, fieldnames: list[str], rows: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def read_text(path: Path | str) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_or_missing(path: Path | str | None) -> str:
    if not path:
        return "MISSING"
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
        return {"cmd": " ".join(str(item) for item in cmd), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(str(item) for item in cmd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "timeout",
        }


def git_value(*args: str) -> str:
    result = run_cmd(["git", *args], timeout=30)
    return (result["stdout"] if result["returncode"] == 0 else result["stderr"] or result["stdout"]).strip()


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


def parse_marker_text(text: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key and key.upper() == key and key.replace("_", "").isalnum():
            markers[key] = value.strip().split()[0] if value.strip() else ""
    return markers


def parse_markers(path: Path | str) -> dict[str, str]:
    return parse_marker_text(read_text(path))


def markdown_header(title: str, result: str, reason: str, *, no_hw: bool = True) -> list[str]:
    return [
        f"# {title}",
        "",
        f"generated_at_utc: {now_iso()}",
        f"repo: `{ROOT}`",
        f"HEAD: `{git_value('rev-parse', 'HEAD')}`",
        f"stage: P4_AUTO_HARDWARE_ACCEPTANCE_NO_MANUAL",
        f"result: {result}",
        f"reason: {reason}",
        f"hardware_actions_executed: {str(not no_hw).lower()}",
        "user_confirmed_supply_ok: true",
        f"manual_intervention_required: false",
        f"shutdown_on_exit: required",
        f"NO_HARDWARE_ACTIONS_EXECUTED: {str(no_hw).lower()}",
        PENDING_HW,
        "",
    ]


def write_markdown(path: Path | str, title: str, result: str, reason: str, lines: list[str] | None = None, *, no_hw: bool = True) -> None:
    body = markdown_header(title, result, reason, no_hw=no_hw)
    if lines:
        body.extend(lines)
        body.append("")
    write_text(path, "\n".join(body))


def ensure_dirs() -> None:
    dirs = [
        GENERATED,
        P4_AUTO_DIR,
        AUTH_DIR,
        BITSTREAM_DIR,
        P4_AUTO_DIR / "safe_idle_direct_proxy",
        P4_AUTO_DIR / "tfdu_control_idle",
        P4_AUTO_DIR / "raw_pulse_smoke",
        P4_AUTO_DIR / "raw_lane_matrix",
        P4_AUTO_DIR / "protocol_smoke",
        P4_AUTO_DIR / "soak",
        P4_AUTO_DIR / "ila",
        SHUTDOWN_DIR,
        P4_AUTO_DIR / "failures",
    ]
    for path in dirs:
        path.mkdir(parents=True, exist_ok=True)
    write_text(
        P4_AUTO_DIR / "failures" / "README.md",
        "# P4_AUTO Failure Evidence\n\nAuthorized hardware failures and automation gaps are recorded here.\n",
    )


def project_paths() -> dict[str, Path]:
    return {
        "agents_md": ROOT / "AGENTS.md",
        "constraint_file": ROOT / "项目约束(目标）.txt",
        "active_profile": ROOT / "board_profiles" / "ACTIVE_PROFILE.json",
        "active_xdc": ROOT / "constraints" / "active" / "PORT1.generated.xdc",
        "pinmap": ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv",
        "register_map": ROOT / "config" / "register_map" / "ir_axi_regs.yaml",
        "tfdu_safety_contract": ROOT / "docs" / "tfdu6102_safety_contract.md",
        "tfdu_safety_summary": ROOT / "docs" / "TFDU6102_SAFETY_SUMMARY.md",
    }


def active_hashes() -> dict[str, str]:
    return {name: sha256_or_missing(path) for name, path in project_paths().items()}


def resolve_root_path(value: str | None) -> Path | None:
    if not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def current_gate_statuses() -> dict[str, str]:
    data = load_json(GENERATED / "offline_gate_summary.json")
    p1 = data.get("P1_OFFLINE_HARDENING") or parse_markers(GENERATED / "p1_offline_hardening_summary.md").get("P1_OFFLINE_HARDENING")
    p2 = data.get("P2_SIMULATION_BASELINE") or parse_markers(GENERATED / "p2_simulation_baseline_summary.md").get("P2_SIMULATION_BASELINE")
    p3 = data.get("P3_PRE_HW_ACCEPTANCE_PACKAGE") or parse_markers(GENERATED / "p3_pre_hw_acceptance_package_summary.md").get("P3_PRE_HW_ACCEPTANCE_PACKAGE")
    return {
        "P1_RECHECK": p1 or "UNKNOWN",
        "P2_RECHECK": p2 or "UNKNOWN",
        "P3_RECHECK": p3 or "UNKNOWN",
    }


def candidate_bitstream(stage: str = "safe_idle") -> dict[str, str]:
    summary = load_json(GENERATED / "vivado" / "nonhardware_build_summary.json")
    stage_info = summary.get("stage_bitstreams", {}).get(stage, {}) if isinstance(summary.get("stage_bitstreams"), dict) else {}
    relpath = stage_info.get("bitstream_path") or (summary.get("bitstream_path") if stage == "safe_idle" else "") or summary.get("bitstream") or ""
    if not relpath and (GENERATED / "vivado" / f"ir_top_new_{stage}.bit").exists():
        relpath = f"evidence/generated/vivado/ir_top_new_{stage}.bit"
        stage_info = {
            "p4_auto_debug_probes": f"evidence/generated/vivado/p4_auto_{stage}_debug.ltx"
            if (GENERATED / "vivado" / f"p4_auto_{stage}_debug.ltx").exists()
            else "MISSING",
            "p4_auto_debug_probes_sha256": sha256_or_missing(GENERATED / "vivado" / f"p4_auto_{stage}_debug.ltx"),
            "p4_auto_debug_instrumentation_log": f"evidence/generated/vivado/p4_auto_{stage}_debug_instrumentation.txt"
            if (GENERATED / "vivado" / f"p4_auto_{stage}_debug_instrumentation.txt").exists()
            else "MISSING",
            "p4_auto_debug_instrumentation": {},
        }
    path = ROOT / relpath if relpath else None
    return {
        "source_bitstream_path": relpath or "MISSING",
        "source_bitstream_sha256": sha256_or_missing(path),
        "source_bitstream_status": "PASS" if path and path.exists() else "SKIP_WITH_REASON",
        "debug_probes_path": stage_info.get("p4_auto_debug_probes", "MISSING"),
        "debug_probes_sha256": stage_info.get("p4_auto_debug_probes_sha256", "MISSING"),
        "debug_instrumentation_log": stage_info.get("p4_auto_debug_instrumentation_log", "MISSING"),
        "debug_instrumentation": stage_info.get("p4_auto_debug_instrumentation", {}),
        "build_log_path": "evidence/generated/vivado/nonhardware_build_summary.json"
        if (GENERATED / "vivado" / "nonhardware_build_summary.json").exists()
        else "MISSING",
    }


def tool_versions_text() -> str:
    git = run_cmd(["git", "--version"], timeout=30)
    return "\n".join(
        [
            "P4_AUTO_TOOL_VERSION_CAPTURE: DRY_RUN_ONLY",
            NO_HW,
            PENDING_HW,
            f"python: {sys.version.replace(chr(10), ' ')}",
            f"git: {(git['stdout'] or git['stderr']).strip()}",
            "vivado: SKIP_WITH_REASON not queried in dry-run",
            "xsdb: SKIP_WITH_REASON not queried in dry-run",
        ]
    )
