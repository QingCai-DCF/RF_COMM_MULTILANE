#!/usr/bin/env python3
"""P10.1 metric validation and deterministic, class-aware finalization."""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from typing import Any, Iterable


METRIC_NAMES = {
    "PHY_RAW_BPS",
    "FRAME_GOODPUT_BPS",
    "APPLICATION_GOODPUT_BPS",
    "OBJECT_COMPLETION_BPS",
    "ENDPOINT_TO_ENDPOINT_GOODPUT_BPS",
    "HOST_ORCHESTRATED_GOODPUT_BPS",
}
MEASUREMENT_CLASSES = {
    "PHY_RAW",
    "FRAME_SUSTAINED",
    "APPLICATION_SUSTAINED",
    "OBJECT_SINGLE",
    "HOST_ORCHESTRATED",
    "DIAGNOSTIC_MICROTRANSFER",
    "SOAK_WINDOW",
}
DIRECTIONS = {"F_TO_R", "R_TO_F", "AGGREGATE"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MIN_SCALING_BYTES = 16 * 1024 * 1024
MIN_SCALING_SECONDS = 30.0


class MetricValidationError(ValueError):
    pass


@dataclass(frozen=True)
class MetricRecord:
    schema_version: int
    metric_name: str
    measurement_class: str
    direction: str
    lane_mask: int
    committed_application_bytes: int
    wire_bytes: int
    frame_payload_bytes: int
    object_count: int
    start_event: str
    end_event: str
    start_timestamp: int
    end_timestamp: int
    timer_source: str
    timer_frequency: int
    elapsed_seconds: float
    units: str
    warmup_included: bool
    idle_included: bool
    host_staging_included: bool
    diagnostic_only: bool
    eligible_for_scaling: bool
    integrity_error_count: int
    retry_exhausted_count: int
    timer_crosscheck_status: str
    run_id: str
    case_id: str
    artifact_sha256: str
    value_bps: float
    status: str = "PASS"

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "MetricRecord":
        required = {field.name for field in cls.__dataclass_fields__.values()}
        missing = required - set(value)
        if missing:
            raise MetricValidationError("missing metric fields: " + ", ".join(sorted(missing)))
        record = cls(**{name: value[name] for name in required})
        record.validate()
        return record

    def expected_scaling_eligibility(self) -> bool:
        return (
            self.status == "PASS"
            and self.metric_name == "APPLICATION_GOODPUT_BPS"
            and self.measurement_class == "APPLICATION_SUSTAINED"
            and not self.diagnostic_only
            and (
                self.committed_application_bytes >= MIN_SCALING_BYTES
                or self.elapsed_seconds >= MIN_SCALING_SECONDS
            )
            and self.integrity_error_count == 0
            and self.retry_exhausted_count == 0
            and self.timer_crosscheck_status == "PASS"
        )

    def validate(self) -> None:
        errors: list[str] = []
        if self.schema_version != 2:
            errors.append("schema_version must be 2")
        if self.metric_name not in METRIC_NAMES:
            errors.append(f"invalid metric_name {self.metric_name}")
        if self.measurement_class not in MEASUREMENT_CLASSES:
            errors.append(f"invalid measurement_class {self.measurement_class}")
        if self.direction not in DIRECTIONS:
            errors.append(f"invalid direction {self.direction}")
        if self.lane_mask < 0 or self.lane_mask & ~0x3:
            errors.append("lane_mask exceeds P10 two-lane scope")
        for name in (
            "committed_application_bytes", "wire_bytes", "frame_payload_bytes",
            "object_count", "start_timestamp", "end_timestamp", "timer_frequency",
            "integrity_error_count", "retry_exhausted_count",
        ):
            if not isinstance(getattr(self, name), int) or getattr(self, name) < 0:
                errors.append(f"{name} must be a non-negative integer")
        if self.timer_frequency <= 0:
            errors.append("timer_frequency must be positive")
        if self.end_timestamp < self.start_timestamp:
            errors.append("end_timestamp precedes start_timestamp")
        if not math.isfinite(self.elapsed_seconds) or self.elapsed_seconds <= 0:
            errors.append("elapsed_seconds must be finite and positive")
        if self.units != "bit/s":
            errors.append("units must be bit/s")
        if not math.isfinite(self.value_bps) or self.value_bps < 0:
            errors.append("value_bps must be finite and non-negative")
        if not self.start_event or not self.end_event or not self.timer_source:
            errors.append("event and timer source names must be non-empty")
        if not self.run_id or not self.case_id:
            errors.append("run_id and case_id must be non-empty")
        if not SHA256_RE.fullmatch(self.artifact_sha256):
            errors.append("artifact_sha256 must be a lowercase SHA256")
        expected_elapsed = (self.end_timestamp - self.start_timestamp) / self.timer_frequency
        tolerance = max(1e-12, self.elapsed_seconds * 1e-9)
        if abs(expected_elapsed - self.elapsed_seconds) > tolerance:
            errors.append("elapsed_seconds does not match timestamps and frequency")
        if self.metric_name in {
            "APPLICATION_GOODPUT_BPS",
            "OBJECT_COMPLETION_BPS",
            "ENDPOINT_TO_ENDPOINT_GOODPUT_BPS",
        }:
            expected_bps = self.committed_application_bytes * 8.0 / self.elapsed_seconds
            value_tolerance = max(1e-6, expected_bps * 1e-9)
            if abs(expected_bps - self.value_bps) > value_tolerance:
                errors.append("value_bps does not match committed application bytes")
        expected_eligible = self.expected_scaling_eligibility()
        if self.eligible_for_scaling != expected_eligible:
            errors.append(
                f"eligible_for_scaling={self.eligible_for_scaling} but contract requires {expected_eligible}"
            )
        if errors:
            raise MetricValidationError("; ".join(errors))

    def to_dict(self) -> dict[str, Any]:
        return {name: getattr(self, name) for name in self.__dataclass_fields__}


def make_metric_record(
    *,
    metric_name: str,
    measurement_class: str,
    direction: str,
    committed_application_bytes: int,
    elapsed_ticks: int,
    timer_frequency: int,
    run_id: str,
    case_id: str,
    artifact_sha256: str,
    lane_mask: int = 3,
    wire_bytes: int | None = None,
    frame_payload_bytes: int | None = None,
    object_count: int = 1,
    start_timestamp: int = 0,
    warmup_included: bool = False,
    idle_included: bool = False,
    host_staging_included: bool = False,
    diagnostic_only: bool = False,
    integrity_error_count: int = 0,
    retry_exhausted_count: int = 0,
    timer_crosscheck_status: str = "PASS",
    timer_source: str = "PL_64MHZ",
    status: str = "PASS",
) -> MetricRecord:
    if elapsed_ticks <= 0:
        raise MetricValidationError("elapsed_ticks must be positive")
    elapsed_seconds = elapsed_ticks / timer_frequency
    if metric_name == "FRAME_GOODPUT_BPS":
        numerator = frame_payload_bytes if frame_payload_bytes is not None else committed_application_bytes
    elif metric_name == "PHY_RAW_BPS":
        numerator = wire_bytes if wire_bytes is not None else committed_application_bytes
    else:
        numerator = committed_application_bytes
    eligible = (
        status == "PASS"
        and metric_name == "APPLICATION_GOODPUT_BPS"
        and measurement_class == "APPLICATION_SUSTAINED"
        and not diagnostic_only
        and (committed_application_bytes >= MIN_SCALING_BYTES or elapsed_seconds >= MIN_SCALING_SECONDS)
        and integrity_error_count == 0
        and retry_exhausted_count == 0
        and timer_crosscheck_status == "PASS"
    )
    record = MetricRecord(
        schema_version=2,
        metric_name=metric_name,
        measurement_class=measurement_class,
        direction=direction,
        lane_mask=lane_mask,
        committed_application_bytes=committed_application_bytes,
        wire_bytes=committed_application_bytes if wire_bytes is None else wire_bytes,
        frame_payload_bytes=committed_application_bytes if frame_payload_bytes is None else frame_payload_bytes,
        object_count=object_count,
        start_event="APPLICATION_FIRST_BYTE" if measurement_class != "HOST_ORCHESTRATED" else "HOST_START",
        end_event="REMOTE_ATOMIC_COMMIT" if measurement_class != "HOST_ORCHESTRATED" else "HOST_READBACK_END",
        start_timestamp=start_timestamp,
        end_timestamp=start_timestamp + elapsed_ticks,
        timer_source=timer_source,
        timer_frequency=timer_frequency,
        elapsed_seconds=elapsed_seconds,
        units="bit/s",
        warmup_included=warmup_included,
        idle_included=idle_included,
        host_staging_included=host_staging_included,
        diagnostic_only=diagnostic_only,
        eligible_for_scaling=eligible,
        integrity_error_count=integrity_error_count,
        retry_exhausted_count=retry_exhausted_count,
        timer_crosscheck_status=timer_crosscheck_status,
        run_id=run_id,
        case_id=case_id,
        artifact_sha256=artifact_sha256,
        value_bps=numerator * 8.0 / elapsed_seconds,
        status=status,
    )
    record.validate()
    return record


def adapt_legacy_p10_record(record: dict[str, Any], classification: dict[str, Any]) -> MetricRecord:
    """Adapt legacy schema only with an explicit, source-audited classification."""
    required_classification = {
        "measurement_class", "committed_application_bytes", "wire_bytes",
        "frame_payload_bytes", "object_count", "elapsed_ticks", "timer_frequency",
        "artifact_sha256", "run_id", "case_id", "direction", "diagnostic_only",
    }
    missing = required_classification - set(classification)
    if missing:
        raise MetricValidationError(
            "legacy classification missing: " + ", ".join(sorted(missing))
        )
    reported = record.get("application_goodput_bps")
    if not isinstance(reported, (int, float)):
        raise MetricValidationError("legacy record lacks numeric application_goodput_bps")
    adapted = make_metric_record(
        metric_name="APPLICATION_GOODPUT_BPS",
        measurement_class=str(classification["measurement_class"]),
        direction=str(classification["direction"]),
        committed_application_bytes=int(classification["committed_application_bytes"]),
        wire_bytes=int(classification["wire_bytes"]),
        frame_payload_bytes=int(classification["frame_payload_bytes"]),
        object_count=int(classification["object_count"]),
        elapsed_ticks=int(classification["elapsed_ticks"]),
        timer_frequency=int(classification["timer_frequency"]),
        run_id=str(classification["run_id"]),
        case_id=str(classification["case_id"]),
        artifact_sha256=str(classification["artifact_sha256"]),
        diagnostic_only=bool(classification["diagnostic_only"]),
        idle_included=bool(classification.get("idle_included", False)),
        host_staging_included=bool(classification.get("host_staging_included", False)),
        timer_crosscheck_status=str(classification.get("timer_crosscheck_status", "NOT_AVAILABLE_LEGACY")),
    )
    tolerance = max(1e-6, abs(float(reported)) * 1e-9)
    if abs(adapted.value_bps - float(reported)) > tolerance:
        raise MetricValidationError("explicit legacy classification does not reproduce reported value")
    return adapted


def finalize_metrics(
    records: Iterable[MetricRecord | dict[str, Any]],
    *,
    formal_run_id: str,
    metric_name: str = "APPLICATION_GOODPUT_BPS",
    measurement_class: str = "APPLICATION_SUSTAINED",
    aggregation: str = "MIN_MEDIAN_MAX",
) -> dict[str, Any]:
    parsed = [
        item if isinstance(item, MetricRecord) else MetricRecord.from_dict(item)
        for item in records
    ]
    if aggregation != "MIN_MEDIAN_MAX":
        raise MetricValidationError(f"unsupported formal aggregation {aggregation}")
    selected = [
        item for item in parsed
        if item.run_id == formal_run_id
        and item.metric_name == metric_name
        and item.measurement_class == measurement_class
        and item.eligible_for_scaling
    ]
    groups: dict[str, list[MetricRecord]] = {}
    for item in selected:
        groups.setdefault(item.direction, []).append(item)
    summaries: dict[str, dict[str, Any]] = {}
    for direction in sorted(groups):
        direction_records = sorted(groups[direction], key=lambda item: (item.value_bps, item.case_id))
        rates = [item.value_bps for item in direction_records]
        summaries[direction] = {
            "status": "PASS",
            "record_count": len(rates),
            "minimum_bps": min(rates),
            "median_bps": statistics.median(rates),
            "maximum_bps": max(rates),
            "records": [item.to_dict() for item in direction_records],
        }
    missing_directions = sorted({"F_TO_R", "R_TO_F"} - set(summaries))
    return {
        "schema_version": 2,
        "status": "PASS" if not missing_directions else "PENDING_MISSING_ELIGIBLE_DIRECTION",
        "formal_run_id": formal_run_id,
        "metric_name": metric_name,
        "measurement_class": measurement_class,
        "aggregation": aggregation,
        "selection_rule": "exact run_id + metric_name + measurement_class + direction + eligible_for_scaling",
        "diagnostic_records_excluded": sum(item.diagnostic_only for item in parsed),
        "ineligible_records_excluded": sum(not item.eligible_for_scaling for item in parsed),
        "missing_directions": missing_directions,
        "directions": summaries,
        "all_records": [item.to_dict() for item in parsed],
    }
