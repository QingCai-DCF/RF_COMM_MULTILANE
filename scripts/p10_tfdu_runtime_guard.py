#!/usr/bin/env python3
"""Fail-closed TFDU continuous-runtime and inter-stage cooldown guard."""

from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml


Clock = Callable[[], float]
Sleeper = Callable[[float], None]
UtcClock = Callable[[], datetime]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def load_policy(path: Path) -> dict[str, Any]:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("runtime/rest policy must be a mapping")
    required = {
        "policy_id",
        "maximum_continuous_runtime_seconds",
        "cooldown_ratio_numerator",
        "cooldown_ratio_denominator",
    }
    missing = sorted(required - set(document))
    if missing:
        raise ValueError(f"runtime/rest policy missing fields: {missing}")
    maximum = float(document["maximum_continuous_runtime_seconds"])
    numerator = int(document["cooldown_ratio_numerator"])
    denominator = int(document["cooldown_ratio_denominator"])
    if maximum <= 0 or maximum > 1800:
        raise ValueError("maximum continuous runtime must be in (0, 1800]")
    if numerator <= 0 or denominator <= 0 or numerator * 2 < denominator:
        raise ValueError("cooldown ratio must be at least one half")
    return document


class RuntimeRestGuard:
    """Track stages with a monotonic clock and persist an auditable ledger."""

    def __init__(
        self,
        policy: dict[str, Any],
        ledger_path: Path,
        modules: Iterable[str],
        *,
        clock: Clock = time.monotonic,
        sleeper: Sleeper = time.sleep,
        utc_clock: UtcClock = _utc_now,
    ) -> None:
        self.policy = policy
        self.ledger_path = ledger_path
        self.modules = tuple(modules)
        if not self.modules or len(set(self.modules)) != len(self.modules):
            raise ValueError("module accounting must contain unique module IDs")
        self.clock = clock
        self.sleeper = sleeper
        self.utc_clock = utc_clock
        self.maximum = float(policy["maximum_continuous_runtime_seconds"])
        self.ratio = (
            int(policy["cooldown_ratio_numerator"])
            / int(policy["cooldown_ratio_denominator"])
        )
        self.entries: list[dict[str, Any]] = []
        self._active: dict[str, Any] | None = None
        self._cooldown_due_monotonic: float | None = None
        self._cooldown_start_monotonic: float | None = None
        self._failed_closed = False
        self._persist()

    def _persist(self) -> None:
        if self._failed_closed or any(e.get("status") == "FAIL" for e in self.entries):
            status = "FAIL"
        elif self._active is not None or self._cooldown_due_monotonic is not None:
            status = "PENDING"
        else:
            status = "PASS"
        document = {
            "schema_version": 1,
            "policy_id": self.policy["policy_id"],
            "maximum_continuous_runtime_seconds": self.maximum,
            "cooldown_ratio": self.ratio,
            "conservative_module_accounting": list(self.modules),
            "status": status,
            "active_stage": None if self._active is None else self._active["stage"],
            "stages": self.entries,
        }
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.ledger_path.write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    def wait_for_cooldown(self) -> dict[str, Any] | None:
        if self._active is not None:
            raise RuntimeError("cannot cool down while a stage is active")
        if self._cooldown_due_monotonic is None:
            return None
        entry = self.entries[-1]
        assert self._cooldown_start_monotonic is not None
        cooldown_start = self._cooldown_start_monotonic
        while True:
            remaining = self._cooldown_due_monotonic - self.clock()
            if remaining <= 0:
                break
            self.sleeper(min(remaining, 30.0))
        completed = self.clock()
        actual = max(0.0, completed - cooldown_start)
        required = float(entry["required_cooldown_seconds"])
        entry["cooldown_completed_utc"] = _utc_text(self.utc_clock())
        entry["actual_cooldown_seconds"] = round(actual, 6)
        entry["cooldown_status"] = "PASS" if actual + 1e-6 >= required else "FAIL"
        entry["status"] = (
            "PASS"
            if entry["cooldown_status"] == "PASS"
            and entry.get("runtime_limit_status") == "PASS"
            and entry.get("shutdown_verified") is True
            else "FAIL"
        )
        self._cooldown_due_monotonic = None
        self._cooldown_start_monotonic = None
        if entry["status"] != "PASS":
            self._failed_closed = True
        self._persist()
        if entry["cooldown_status"] != "PASS":
            raise RuntimeError("required inter-stage cooldown was not satisfied")
        return entry

    def begin_stage(self, stage: str, planned_runtime_seconds: float) -> None:
        if self._active is not None:
            raise RuntimeError("another TFDU stage is already active")
        if self._failed_closed:
            raise RuntimeError("runtime guard is fail-closed after a prior safety failure")
        if self._cooldown_due_monotonic is not None:
            raise RuntimeError("required cooldown is incomplete")
        planned = float(planned_runtime_seconds)
        if planned <= 0 or planned > self.maximum:
            raise RuntimeError(
                f"planned stage runtime {planned}s exceeds {self.maximum}s limit"
            )
        self._active = {
            "stage": stage,
            "modules": list(self.modules),
            "planned_runtime_seconds": planned,
            "start_utc": _utc_text(self.utc_clock()),
            "_start_monotonic": self.clock(),
        }
        self._persist()

    def finish_stage(
        self,
        *,
        shutdown_verified: bool,
        measured_runtime_seconds: float | None = None,
        tx_capable_runtime_seconds: float | None = None,
    ) -> dict[str, Any]:
        if self._active is None:
            raise RuntimeError("no active TFDU stage")
        stopped = self.clock()
        finished_utc = self.utc_clock()
        entry = self._active
        self._active = None
        wall_elapsed = max(0.0, stopped - float(entry.pop("_start_monotonic")))
        if measured_runtime_seconds is None:
            elapsed = wall_elapsed
            measurement = "conservative_wall_clock"
        else:
            elapsed = float(measured_runtime_seconds)
            if elapsed <= 0.0 or elapsed > wall_elapsed + 1.0:
                entry.update({
                    "shutdown_verified": bool(shutdown_verified),
                    "shutdown_verified_utc": (
                        _utc_text(finished_utc) if shutdown_verified else None
                    ),
                    "measured_runtime_seconds": elapsed,
                    "wall_runtime_seconds": round(wall_elapsed, 6),
                    "runtime_measurement_source":
                        "invalid_hardware_stage_active_evidence",
                    "runtime_limit_status": "FAIL",
                    "required_cooldown_seconds": None,
                    "cooldown_completed_utc": None,
                    "actual_cooldown_seconds": None,
                    "cooldown_status": "FAIL",
                    "status": "FAIL",
                })
                self.entries.append(entry)
                self._failed_closed = True
                self._persist()
                raise RuntimeError("invalid externally measured active runtime")
            measurement = "hardware_stage_active_evidence"
        if tx_capable_runtime_seconds is None:
            tx_capable_elapsed = elapsed
            limit_measurement = measurement
        else:
            tx_capable_elapsed = float(tx_capable_runtime_seconds)
            if tx_capable_elapsed <= 0.0 or tx_capable_elapsed > elapsed + 1e-6:
                required = math.ceil(elapsed * self.ratio * 1000.0) / 1000.0
                entry.update({
                    "shutdown_verified": bool(shutdown_verified),
                    "shutdown_verified_utc": (
                        _utc_text(finished_utc) if shutdown_verified else None
                    ),
                    "measured_runtime_seconds": round(elapsed, 6),
                    "tx_capable_runtime_seconds": tx_capable_elapsed,
                    "wall_runtime_seconds": round(wall_elapsed, 6),
                    "runtime_measurement_source": measurement,
                    "runtime_limit_measurement_source":
                        "invalid_hardware_tx_capable_interval",
                    "runtime_limit_status": "FAIL",
                    "required_cooldown_seconds": required,
                    "cooldown_completed_utc": None,
                    "actual_cooldown_seconds": None,
                    "cooldown_status": "PENDING" if shutdown_verified else "FAIL",
                    "status": "FAIL",
                })
                self.entries.append(entry)
                self._failed_closed = True
                if shutdown_verified:
                    self._cooldown_start_monotonic = stopped
                    self._cooldown_due_monotonic = stopped + required
                self._persist()
                raise RuntimeError("invalid hardware TX-capable runtime")
            limit_measurement = "hardware_reported_tx_capable_interval"
        required = math.ceil(elapsed * self.ratio * 1000.0) / 1000.0
        entry.update({
            "shutdown_verified": bool(shutdown_verified),
            "shutdown_verified_utc": _utc_text(finished_utc) if shutdown_verified else None,
            "measured_runtime_seconds": round(elapsed, 6),
            "tx_capable_runtime_seconds": round(tx_capable_elapsed, 6),
            "wall_runtime_seconds": round(wall_elapsed, 6),
            "runtime_measurement_source": measurement,
            "runtime_limit_measurement_source": limit_measurement,
            "runtime_limit_status": (
                "PASS" if tx_capable_elapsed <= self.maximum else "FAIL"
            ),
            "required_cooldown_seconds": required,
            "cooldown_completed_utc": None,
            "actual_cooldown_seconds": None,
            "cooldown_status": "PENDING" if shutdown_verified else "FAIL",
            "status": (
                "PENDING"
                if shutdown_verified and tx_capable_elapsed <= self.maximum
                else "FAIL"
            ),
        })
        self.entries.append(entry)
        if shutdown_verified:
            self._cooldown_start_monotonic = stopped
            self._cooldown_due_monotonic = stopped + required
        if not shutdown_verified or tx_capable_elapsed > self.maximum:
            self._failed_closed = True
        self._persist()
        if not shutdown_verified:
            raise RuntimeError("shutdown-after unconfirmed; no later TX is permitted")
        if tx_capable_elapsed > self.maximum:
            raise RuntimeError("measured continuous runtime exceeded 30 minutes")
        return entry

    def public_ledger(self) -> dict[str, Any]:
        return json.loads(self.ledger_path.read_text(encoding="utf-8"))
