#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence" / "generated"
P6_DIR = ROOT / "evidence" / "hardware" / "p6"
P6_SIM_DIR = ROOT / "evidence" / "simulation" / "p6"
P6_PROFILES = ROOT / "profiles" / "p6"
P6_STAGE = "P6_LOCAL_TRANSPORT_AND_PS_DRIVER_STABILIZATION_NO_ETHERNET"

PASS = "PASS"
FAIL = "FAIL"
PASS_WITH_NOTES = "PASS_WITH_NOTES"
SKIP = "SKIP_WITH_REASON"
BLOCKED = "BLOCKED_BY_RUNTIME_ENVIRONMENT"
NOT_RUN_RUNTIME_LIMIT = "NOT_RUN_RUNTIME_LIMIT"
NOT_RUN_PREREQ = "NOT_RUN_PREREQUISITE_BLOCKED"

P6_CONTEXT = {
    "CURRENT_KNOWN_HEAD": "4768ef76c1d9bc6042d4058f52eef5fc0da5ca01",
    "PREVIOUS_STAGE": "P5_2LANE_PROTOCOL_STABILIZATION",
    "PREVIOUS_RESULT": "PASS_WITH_NOTES",
    "USER_CONFIRMED_SUPPLY_OK": True,
    "NETWORK_CABLE_CONNECTED": False,
    "HARDWARE_MOVEMENT_ALLOWED": False,
    "AVAILABLE_LANES": 2,
    "MAX_LANE_MASK": "0x3",
    "SESSION": "0x2201",
}

PAYLOAD_LENGTHS = [1, 2, 3, 4, 7, 8, 15, 16, 31, 32, 63, 64, 127, 128, 191, 247]
PAYLOAD_PATTERNS = [
    "zeros",
    "ones",
    "0xAA",
    "0x55",
    "counter",
    "walking_one",
    "walking_zero",
    "prbs7",
    "prbs15",
    "deterministic_random",
]
LANE_MASKS = ["0x1", "0x2", "0x3"]
ALLOWED_RESULTS = {PASS, PASS_WITH_NOTES, FAIL, BLOCKED, NOT_RUN_RUNTIME_LIMIT, SKIP, NOT_RUN_PREREQ}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


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


def write_csv(path: Path | str, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_text(path: Path | str) -> str:
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def load_json(path: Path | str) -> Any:
    path = Path(path)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


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


def run_cmd(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    try:
        proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout)
        return {
            "cmd": " ".join(str(part) for part in cmd),
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    except FileNotFoundError as exc:
        return {"cmd": " ".join(str(part) for part in cmd), "returncode": 127, "stdout": "", "stderr": str(exc)}
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": " ".join(str(part) for part in cmd),
            "returncode": 124,
            "stdout": exc.stdout or "",
            "stderr": exc.stderr or "timeout",
        }


def git_value(*args: str) -> str:
    result = run_cmd(["git", *args], timeout=30)
    return (result["stdout"] if result["returncode"] == 0 else result["stderr"] or result["stdout"]).strip()


def json_from_stdout(stdout: str) -> dict[str, Any]:
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


def ensure_dirs() -> None:
    for path in [
        GENERATED,
        P6_DIR,
        P6_DIR / "authorization",
        P6_DIR / "bitstreams",
        P6_DIR / "safe_idle_recheck",
        P6_DIR / "tfdu_control_idle_recheck",
        P6_DIR / "jtag_axi_payload_ram_smoke",
        P6_DIR / "protocol" / "lane0_dynamic_payload",
        P6_DIR / "protocol" / "lane1_dynamic_payload",
        P6_DIR / "protocol" / "two_lane_dynamic_payload",
        P6_DIR / "ps_driver_runtime",
        P6_DIR / "host_file_transport_jtag",
        P6_DIR / "lane_fallback_regression",
        P6_DIR / "soak" / "two_lane_2h_stationary",
        P6_DIR / "failures",
        P6_SIM_DIR / "dynamic_payload",
        P6_PROFILES,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def project_paths() -> dict[str, Path]:
    constraint_file = ROOT / "PROJECT_CONSTRAINTS.txt"
    for candidate in ROOT.glob("*.txt"):
        if candidate.name.startswith("项目约束"):
            constraint_file = candidate
            break
    return {
        "constraint_file": constraint_file,
        "active_profile": ROOT / "board_profiles" / "ACTIVE_PROFILE.json",
        "pinmap": ROOT / "board_profiles" / "ax7010_tfdu_j10_j11_pinmap.csv",
        "active_xdc": ROOT / "constraints" / "active" / "PORT1.generated.xdc",
        "register_map": ROOT / "config" / "register_map" / "ir_axi_regs.yaml",
        "tfdu_safety_contract": ROOT / "docs" / "tfdu6102_safety_contract.md",
        "tfdu_safety_summary": ROOT / "docs" / "TFDU6102_SAFETY_SUMMARY.md",
        "shutdown_bitstream": ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit",
    }


def active_hashes() -> dict[str, str]:
    return {name: sha256_or_missing(path) for name, path in project_paths().items()}


def markdown_header(title: str, result: str, reason: str, *, script_hw: bool, source_hw: bool) -> list[str]:
    return [
        f"# {title}",
        "",
        f"generated_at_utc: {now_iso()}",
        f"repo: `{ROOT}`",
        f"HEAD: `{git_value('rev-parse', 'HEAD')}`",
        f"stage: {P6_STAGE}",
        f"result: {result}",
        f"reason: {reason}",
        f"script_hardware_actions_executed: {str(script_hw).lower()}",
        f"source_evidence_contains_hardware_actions: {str(source_hw).lower()}",
        "stage_programmed_fpga: false" if not script_hw else "stage_programmed_fpga: see stage section",
        "stage_drove_tfdu_txd: false" if not script_hw else "stage_drove_tfdu_txd: see stage section",
        "stage_enabled_tfdu_receiver: false" if not script_hw else "stage_enabled_tfdu_receiver: see stage section",
        "shutdown_on_exit_observed: false" if not script_hw else "shutdown_on_exit_observed: see stage section",
        "product_final_acceptance: pending",
        "user_confirmed_supply_ok: true",
        "network_cable_connected: false",
        "hardware_movement_allowed: false",
        "available_lanes: 2",
        "max_lane_mask: 0x3",
        "",
    ]


def write_markdown(
    path: Path | str,
    title: str,
    result: str,
    reason: str,
    lines: list[str] | None = None,
    *,
    script_hw: bool = False,
    source_hw: bool = False,
) -> None:
    body = markdown_header(title, result, reason, script_hw=script_hw, source_hw=source_hw)
    if lines:
        body.extend(lines)
        body.append("")
    write_text(path, "\n".join(body))


def parse_marker_text(text: str) -> dict[str, str]:
    markers: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("|"):
            continue
        separator = ":" if ":" in line else "=" if "=" in line else ""
        if not separator:
            continue
        key, value = line.split(separator, 1)
        key = key.strip().strip("-").strip()
        normalized_key = key.upper().replace("-", "_").replace(" ", "_")
        if normalized_key.replace("_", "").isalnum():
            markers[normalized_key] = value.strip().split()[0] if value.strip() else ""
    return markers


def parse_markers(path: Path | str) -> dict[str, str]:
    return parse_marker_text(read_text(path))


def status_is_passish(value: str | None) -> bool:
    return bool(value) and value.startswith("PASS")


def mask_to_int(value: Any) -> int | None:
    try:
        return int(value, 0) if isinstance(value, str) else int(value)
    except Exception:
        return None


def p6_stage_placeholder(
    marker: str,
    evidence_dir: Path | str,
    summary_path: Path | str,
    status: str,
    reason: str,
    *,
    source_hw: bool = False,
) -> dict[str, Any]:
    evidence_dir = ROOT / evidence_dir if not Path(evidence_dir).is_absolute() else Path(evidence_dir)
    summary_path = ROOT / summary_path if not Path(summary_path).is_absolute() else Path(summary_path)
    evidence_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        marker: status,
        "reason": reason,
        "script_hardware_actions_executed": False,
        "source_evidence_contains_hardware_actions": source_hw,
        "stage_programmed_fpga": False,
        "stage_drove_tfdu_txd": False,
        "stage_enabled_tfdu_receiver": False,
        "shutdown_on_exit_observed": False,
        "product_final_acceptance": "pending",
        "evidence_dir": rel(evidence_dir),
        "summary": rel(summary_path),
    }
    lines = [
        f"{marker}: {status}",
        f"reason: {reason}",
        "script_hardware_actions_executed: false",
        f"source_evidence_contains_hardware_actions: {str(source_hw).lower()}",
        "stage_programmed_fpga: false",
        "stage_drove_tfdu_txd: false",
        "stage_enabled_tfdu_receiver: false",
        "shutdown_on_exit_observed: false",
        "product_final_acceptance: pending",
        "",
        "## Boundary",
        "",
        "- No Ethernet, DHCP, static-IP board link, motion, rotation, 4-lane/8-lane, or lane mask above 0x3 was used.",
        "- This item is not product-final acceptance.",
    ]
    write_json(evidence_dir / "p6_stage_result.json", payload)
    write_markdown(summary_path, marker.replace("_", " ").title(), status, reason, lines, source_hw=source_hw)
    write_markdown(evidence_dir / "summary.md", marker.replace("_", " ").title(), status, reason, lines, source_hw=source_hw)
    return payload


def seeded_payload(length: int, pattern: str, seed: int = 0x2201) -> bytes:
    if pattern == "zeros":
        return bytes([0] * length)
    if pattern == "ones":
        return bytes([0xFF] * length)
    if pattern == "0xAA":
        return bytes([0xAA] * length)
    if pattern == "0x55":
        return bytes([0x55] * length)
    if pattern == "counter":
        return bytes((i & 0xFF) for i in range(length))
    if pattern == "walking_one":
        return bytes((1 << (i % 8)) for i in range(length))
    if pattern == "walking_zero":
        return bytes((~(1 << (i % 8))) & 0xFF for i in range(length))
    if pattern == "prbs7":
        state = 0x5A
        out = []
        for _ in range(length):
            byte = 0
            for bit in range(8):
                new_bit = ((state >> 6) ^ (state >> 5)) & 1
                state = ((state << 1) & 0x7F) | new_bit
                byte |= (state & 1) << bit
            out.append(byte)
        return bytes(out)
    if pattern == "prbs15":
        state = 0x4A5A
        out = []
        for _ in range(length):
            byte = 0
            for bit in range(8):
                new_bit = ((state >> 14) ^ (state >> 13)) & 1
                state = ((state << 1) & 0x7FFF) | new_bit
                byte |= (state & 1) << bit
            out.append(byte)
        return bytes(out)
    if pattern == "deterministic_random":
        state = seed & 0xFFFFFFFF
        out = []
        for _ in range(length):
            state = (1664525 * state + 1013904223) & 0xFFFFFFFF
            out.append((state >> 24) & 0xFF)
        return bytes(out)
    raise ValueError(f"unsupported payload pattern: {pattern}")


def crc32_hex(data: bytes) -> str:
    import zlib

    return f"0x{zlib.crc32(data) & 0xFFFFFFFF:08x}"
