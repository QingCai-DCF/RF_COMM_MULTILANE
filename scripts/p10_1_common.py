#!/usr/bin/env python3
"""Shared deterministic helpers for the P10.1 offline engineering gate."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
GENERATED = ROOT / "evidence/generated"
RAW = GENERATED / "p10_1_raw"
DETERMINISTIC_TIMESTAMP = "2026-07-31T00:00:00Z"


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{rel(path)} must contain a mapping")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{rel(path)} must contain a JSON object")
    return value


def stable_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stable_json(value), encoding="utf-8", newline="\n")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_pair(stem: str, title: str, payload: dict[str, Any], body: Iterable[str] = ()) -> tuple[Path, Path]:
    """Write one machine-readable and one human-readable evidence artifact."""
    json_path = GENERATED / f"{stem}.json"
    md_path = GENERATED / f"{stem}.md"
    write_json(json_path, payload)
    lines = [
        f"# {title}",
        "",
        f"- Status: `{payload.get('status', 'UNSPECIFIED')}`",
        f"- Test ID: `{payload.get('test_id', 'UNSPECIFIED')}`",
        f"- Hardware actions executed: `{str(payload.get('hardware_actions_executed', False)).lower()}`",
        f"- Current-run hardware authorization: `{str(payload.get('current_run_hardware_authorization', False)).lower()}`",
    ]
    errors = payload.get("errors", [])
    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {item}" for item in errors)
    body_lines = list(body)
    if body_lines:
        lines.extend(["", *body_lines])
    lines.extend(["", "## Machine-readable evidence", "", f"`{rel(json_path)}`"])
    write_text(md_path, "\n".join(lines))
    return json_path, md_path


def git_output(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def offline_environment_errors() -> list[str]:
    errors: list[str] = []
    if os.environ.get("NO_HARDWARE", "1") != "1":
        errors.append("NO_HARDWARE must be 1")
    if os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION", "false").lower() != "false":
        errors.append("CURRENT_RUN_HARDWARE_AUTHORIZATION must be false")
    return errors


def evidence_base(test_id: str, **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "test_id": test_id,
        "generated_at_utc": DETERMINISTIC_TIMESTAMP,
        "no_hardware": True,
        "hardware_actions_executed": False,
        "current_run_hardware_authorization": False,
        **extra,
    }


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    low = int(position)
    high = min(low + 1, len(ordered) - 1)
    weight = position - low
    return ordered[low] * (1.0 - weight) + ordered[high] * weight


def statistics(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "min": None, "p50": None, "p95": None, "p99": None, "max": None}
    return {
        "count": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "p50": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values),
    }
