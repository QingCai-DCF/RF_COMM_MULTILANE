#!/usr/bin/env python3
"""Transport-neutral P7 object engine and backend contract."""
from __future__ import annotations

import hashlib
import math
import statistics
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import IntEnum
from pathlib import Path
from typing import Any, Callable

from p7_app_protocol import AppFragment, ProtocolError, Reassembler, atomic_commit, crc32, segment_object


class LanePolicy(IntEnum):
    LANE0_ONLY = 1
    LANE1_ONLY = 2
    STRIPE_ROUND_ROBIN = 3
    REPLICATE_0X3 = 4


@dataclass(slots=True)
class BackendCapabilities:
    name: str
    max_payload_bytes: int = 247
    allowed_lane_masks: tuple[int, ...] = (0x1, 0x2, 0x3)
    network_enabled: bool = False
    hardware: bool = False
    ps_runtime: bool = False


@dataclass(slots=True)
class FragmentResult:
    accepted: bool
    rx_payload: bytes = b""
    lane_mask: int = 0
    latency_us: float = 0.0
    retry_count: int = 0
    retry_exhausted: int = 0
    tx_fail: int = 0
    crc_bad: int = 0
    payload_mismatch: int = 0
    txd_high_consecutive_max: int = 0
    duty_violation: int = 0
    error: str = ""


class TransportBackend(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def get_capabilities(self) -> BackendCapabilities: ...

    @abstractmethod
    def submit_fragment(self, payload: bytes, lane_mask: int) -> int: ...

    @abstractmethod
    def poll_fragment_result(self, token: int, timeout_s: float) -> FragmentResult: ...

    @abstractmethod
    def read_fragment(self, token: int) -> bytes: ...

    @abstractmethod
    def abort(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def get_metrics(self) -> dict[str, int | float | str]: ...


class LocalStubBackend(TransportBackend):
    """Deterministic, synchronous backend used only by offline conformance."""

    def __init__(self, *, name: str = "local_stub", ps_runtime: bool = False):
        self._caps = BackendCapabilities(name=name, ps_runtime=ps_runtime)
        self._opened = False
        self._aborted = False
        self._next_token = 1
        self._payloads: dict[int, bytes] = {}
        self._lanes: dict[int, int] = {}
        self._metrics = {"submitted": 0, "completed": 0, "aborted": 0}

    def open(self) -> None:
        self._opened = True
        self._aborted = False

    def get_capabilities(self) -> BackendCapabilities:
        return self._caps

    def submit_fragment(self, payload: bytes, lane_mask: int) -> int:
        if not self._opened or self._aborted:
            raise RuntimeError("backend is not open")
        if lane_mask not in self._caps.allowed_lane_masks:
            raise ValueError("lane mask is outside the two-lane scope")
        if not 1 <= len(payload) <= self._caps.max_payload_bytes:
            raise ValueError("payload is outside the P6 contract")
        token = self._next_token
        self._next_token += 1
        self._payloads[token] = bytes(payload)
        self._lanes[token] = lane_mask
        self._metrics["submitted"] += 1
        return token

    def poll_fragment_result(self, token: int, timeout_s: float) -> FragmentResult:
        if timeout_s <= 0:
            return FragmentResult(False, error="TIMEOUT")
        payload = self._payloads.get(token)
        if payload is None:
            return FragmentResult(False, error="UNKNOWN_TOKEN")
        self._metrics["completed"] += 1
        return FragmentResult(True, payload, self._lanes[token], latency_us=25.0)

    def read_fragment(self, token: int) -> bytes:
        return self._payloads[token]

    def abort(self) -> None:
        self._aborted = True
        self._metrics["aborted"] += 1

    def close(self) -> None:
        self._opened = False

    def get_metrics(self) -> dict[str, int | float | str]:
        return dict(self._metrics)


class MockJtagBackend(LocalStubBackend):
    def __init__(self) -> None:
        super().__init__(name="mock_jtag_axi")


class MockPsMailboxBackend(LocalStubBackend):
    def __init__(self) -> None:
        super().__init__(name="mock_ps_mailbox", ps_runtime=True)


class TcpStubDisabled(TransportBackend):
    """Compilation/API placeholder.  It intentionally has no socket code."""

    def open(self) -> None:
        raise RuntimeError("TCP_STUB_DISABLED_NO_NETWORK_CABLE")

    def get_capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(name="tcp_stub_disabled", network_enabled=False)

    def submit_fragment(self, payload: bytes, lane_mask: int) -> int:
        raise RuntimeError("TCP_STUB_DISABLED_NO_NETWORK_CABLE")

    def poll_fragment_result(self, token: int, timeout_s: float) -> FragmentResult:
        return FragmentResult(False, error="TCP_STUB_DISABLED_NO_NETWORK_CABLE")

    def read_fragment(self, token: int) -> bytes:
        raise RuntimeError("TCP_STUB_DISABLED_NO_NETWORK_CABLE")

    def abort(self) -> None: pass

    def close(self) -> None: pass

    def get_metrics(self) -> dict[str, int | float | str]:
        return {"network_used": 0, "status": "DISABLED"}


@dataclass(slots=True)
class FaultInjection:
    unavailable_mask: int = 0
    after_fragment: int = 0

    def active_mask(self, fragment_index: int) -> int:
        return self.unavailable_mask if fragment_index >= self.after_fragment else 0


@dataclass(slots=True)
class ApplicationMetrics:
    objects_requested: int = 0
    objects_completed: int = 0
    objects_failed: int = 0
    fragments_generated: int = 0
    fragments_submitted: int = 0
    fragments_completed: int = 0
    fragments_retried: int = 0
    fragments_duplicated: int = 0
    fragments_rejected: int = 0
    fragments_out_of_order: int = 0
    bytes_requested: int = 0
    bytes_completed: int = 0
    whole_object_crc_failures: int = 0
    sha256_mismatches: int = 0
    lane0_fragments: int = 0
    lane1_fragments: int = 0
    replicated_fragments: int = 0
    fallback_lane0_to_lane1: int = 0
    fallback_lane1_to_lane0: int = 0
    queue_high_watermark: int = 0
    backpressure_events: int = 0
    p6_retry_count: int = 0
    p6_retry_exhausted: int = 0
    p6_tx_fail: int = 0
    p6_crc_bad: int = 0
    p6_payload_mismatch: int = 0
    max_txd_high_cycles: int = 0
    duty_violation_count: int = 0
    _fragment_latencies_us: list[float] = field(default_factory=list, repr=False)
    _object_latencies_ms: list[float] = field(default_factory=list, repr=False)
    _start_ns: int = 0
    _end_ns: int = 0

    @staticmethod
    def _percentile(values: list[float], quantile: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
        return float(ordered[index])

    def snapshot(self) -> dict[str, int | float | str]:
        duration_s = max(0.0, (self._end_ns - self._start_ns) / 1e9)
        result: dict[str, int | float | str] = {
            key: value for key, value in asdict(self).items() if not key.startswith("_")
        }
        frag = self._fragment_latencies_us
        obj = self._object_latencies_ms
        result.update({
            "timestamp_source": "host_monotonic_ns",
            "duration_seconds": duration_s,
            "application_goodput_bps": 0.0 if duration_s == 0 else self.bytes_completed * 8.0 / duration_s,
            "fragment_latency_min_us": min(frag) if frag else 0.0,
            "fragment_latency_mean_us": statistics.fmean(frag) if frag else 0.0,
            "fragment_latency_p50_us": self._percentile(frag, 0.50),
            "fragment_latency_p95_us": self._percentile(frag, 0.95),
            "fragment_latency_p99_us": self._percentile(frag, 0.99),
            "fragment_latency_max_us": max(frag) if frag else 0.0,
            "object_latency_min_ms": min(obj) if obj else 0.0,
            "object_latency_mean_ms": statistics.fmean(obj) if obj else 0.0,
            "object_latency_p95_ms": self._percentile(obj, 0.95),
            "object_latency_max_ms": max(obj) if obj else 0.0,
        })
        return result


@dataclass(slots=True)
class ObjectResult:
    passed: bool
    output: bytes
    input_sha256: str
    output_sha256: str
    input_crc32: int
    output_crc32: int
    error: str = ""


class ApplicationTransport:
    def __init__(self, backend: TransportBackend, *, fragment_timeout_s: float = 5.0):
        self.backend = backend
        self.fragment_timeout_s = fragment_timeout_s
        self.metrics = ApplicationMetrics()
        self._aborted = False

    @staticmethod
    def preferred_lane(policy: LanePolicy, fragment_index: int) -> int:
        if policy == LanePolicy.LANE0_ONLY:
            return 0x1
        if policy == LanePolicy.LANE1_ONLY:
            return 0x2
        if policy == LanePolicy.STRIPE_ROUND_ROBIN:
            return 0x1 if fragment_index % 2 == 0 else 0x2
        if policy == LanePolicy.REPLICATE_0X3:
            return 0x3
        raise ValueError("invalid lane policy")

    def _select_lane(self, preferred: int, unavailable: int) -> int:
        usable = preferred & ~unavailable & 0x3
        if usable:
            return usable
        alternate = (~unavailable) & 0x3
        if preferred == 0x1 and alternate & 0x2:
            self.metrics.fallback_lane0_to_lane1 += 1
            return 0x2
        if preferred == 0x2 and alternate & 0x1:
            self.metrics.fallback_lane1_to_lane0 += 1
            return 0x1
        if preferred == 0x3:
            if alternate & 0x1:
                self.metrics.fallback_lane1_to_lane0 += 1
                return 0x1
            if alternate & 0x2:
                self.metrics.fallback_lane0_to_lane1 += 1
                return 0x2
        return 0

    def abort(self) -> None:
        self._aborted = True
        self.backend.abort()

    def send_object(
        self,
        data: bytes,
        *,
        session_epoch: int,
        object_id: int,
        lane_policy: LanePolicy,
        fault: FaultInjection | None = None,
        abort_after_fragment: int | None = None,
    ) -> ObjectResult:
        fault = fault or FaultInjection()
        self.metrics.objects_requested += 1
        self.metrics.bytes_requested += len(data)
        self.metrics._start_ns = self.metrics._start_ns or time.monotonic_ns()
        object_start = time.monotonic_ns()
        input_sha = hashlib.sha256(data).hexdigest()
        input_crc = crc32(data)
        reassembler = Reassembler(expected_session_epoch=session_epoch)
        fragments = segment_object(data, session_epoch=session_epoch, object_id=object_id)
        self.metrics.fragments_generated += len(fragments)
        self.backend.open()
        try:
            for fragment in fragments:
                index = fragment.header.fragment_index
                if self._aborted or (abort_after_fragment is not None and index == abort_after_fragment):
                    self.abort()
                    raise RuntimeError("OBJECT_ABORTED")
                preferred = self.preferred_lane(lane_policy, index)
                lane = self._select_lane(preferred, fault.active_mask(index))
                if lane == 0:
                    raise RuntimeError("ALL_LANES_UNAVAILABLE")
                encoded = fragment.encode()
                start_ns = time.monotonic_ns()
                token = self.backend.submit_fragment(encoded, lane)
                self.metrics.fragments_submitted += 1
                result = self.backend.poll_fragment_result(token, self.fragment_timeout_s)
                elapsed_us = (time.monotonic_ns() - start_ns) / 1000.0
                result.latency_us = max(result.latency_us, elapsed_us)
                self.metrics._fragment_latencies_us.append(result.latency_us)
                self.metrics.p6_retry_count += result.retry_count
                self.metrics.p6_retry_exhausted += result.retry_exhausted
                self.metrics.p6_tx_fail += result.tx_fail
                self.metrics.p6_crc_bad += result.crc_bad
                self.metrics.p6_payload_mismatch += result.payload_mismatch
                self.metrics.max_txd_high_cycles = max(
                    self.metrics.max_txd_high_cycles, result.txd_high_consecutive_max
                )
                self.metrics.duty_violation_count += result.duty_violation
                if not result.accepted or any((
                    result.retry_exhausted,
                    result.tx_fail,
                    result.crc_bad,
                    result.payload_mismatch,
                    result.duty_violation,
                )):
                    self.metrics.fragments_rejected += 1
                    raise RuntimeError(result.error or "P6_FRAGMENT_FAILED")
                rx_payload = self.backend.read_fragment(token)
                if rx_payload != result.rx_payload:
                    raise RuntimeError("BACKEND_RESULT_READ_MISMATCH")
                state = reassembler.add(rx_payload)
                if state == "DUPLICATE_SAME":
                    self.metrics.fragments_duplicated += 1
                self.metrics.fragments_completed += 1
                if lane & 0x1:
                    self.metrics.lane0_fragments += 1
                if lane & 0x2:
                    self.metrics.lane1_fragments += 1
                if lane == 0x3:
                    self.metrics.replicated_fragments += 1
            output = reassembler.data()
            output_crc = crc32(output)
            output_sha = hashlib.sha256(output).hexdigest()
            if output_crc != input_crc:
                self.metrics.whole_object_crc_failures += 1
                raise RuntimeError("WHOLE_OBJECT_CRC_MISMATCH")
            if output_sha != input_sha:
                self.metrics.sha256_mismatches += 1
                raise RuntimeError("SHA256_MISMATCH")
            self.metrics.objects_completed += 1
            self.metrics.bytes_completed += len(output)
            self.metrics._object_latencies_ms.append((time.monotonic_ns() - object_start) / 1e6)
            self.metrics._end_ns = time.monotonic_ns()
            return ObjectResult(True, output, input_sha, output_sha, input_crc, output_crc)
        except (RuntimeError, ProtocolError, ValueError) as exc:
            self.metrics.objects_failed += 1
            self.metrics.fragments_out_of_order += reassembler.out_of_order
            self.metrics._end_ns = time.monotonic_ns()
            return ObjectResult(False, b"", input_sha, "", input_crc, 0, str(exc))
        finally:
            self.backend.close()

    def send_file(self, input_path: Path, output_path: Path, **kwargs: Any) -> ObjectResult:
        result = self.send_object(input_path.read_bytes(), **kwargs)
        if result.passed:
            atomic_commit(output_path, result.output)
        return result


@dataclass(slots=True)
class QueuedObject:
    data: bytes
    session_epoch: int
    object_id: int
    lane_policy: LanePolicy


class DescriptorQueue:
    def __init__(self, transport: ApplicationTransport, *, depth: int = 8):
        if depth < 1 or depth > 8:
            raise ValueError("queue depth must be in 1..8")
        self.transport = transport
        self.depth = depth
        self._queue: list[QueuedObject] = []

    def submit(self, item: QueuedObject) -> bool:
        if len(self._queue) >= self.depth:
            self.transport.metrics.backpressure_events += 1
            return False
        self._queue.append(item)
        self.transport.metrics.queue_high_watermark = max(
            self.transport.metrics.queue_high_watermark, len(self._queue)
        )
        return True

    def drain(self, *, stop: Callable[[], bool] | None = None) -> list[ObjectResult]:
        results: list[ObjectResult] = []
        while self._queue:
            if stop is not None and stop():
                break
            item = self._queue.pop(0)
            results.append(self.transport.send_object(
                item.data,
                session_epoch=item.session_epoch,
                object_id=item.object_id,
                lane_policy=item.lane_policy,
            ))
        return results
