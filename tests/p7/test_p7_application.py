from __future__ import annotations

import hashlib
import os
import random
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from p7_app_protocol import (  # noqa: E402
    HEADER_BYTES,
    AppFragment,
    AppHeader,
    ProtocolError,
    Reassembler,
    crc32,
    segment_object,
)
from p7_app_transport import (  # noqa: E402
    ApplicationTransport,
    DescriptorQueue,
    FaultInjection,
    LanePolicy,
    LocalStubBackend,
    MockJtagBackend,
    MockPsMailboxBackend,
    QueuedObject,
    TcpStubDisabled,
)
from p7_ps_mailbox_backend import (  # noqa: E402
    DescriptorRequest,
    P7_DESCRIPTOR_COMPLETE,
    P7_DESCRIPTOR_FREE,
    P7_DESCRIPTOR_READY,
    P7_DESCRIPTOR_STATUS_OFFSET,
    P7_KNOWN_GOOD_TXD_HIGH_CYCLES,
    P7_QUEUE_DEPTH,
    P7_SERVICE_BOOTING,
    descriptor_ready_publication,
    descriptor_status_address,
    decode_runtime_elapsed_snapshot,
    fragment_count_for_length,
    pack_mailbox,
    pack_ready_publication_word,
    sha256_words,
    unpack_descriptor,
    unpack_mailbox,
    unpack_stable_terminal_descriptor,
    validate_completed,
)


_DESCRIPTOR_WORDS = struct.Struct("<64I")


def pattern(name: str, length: int) -> bytes:
    if name == "all_zero":
        return bytes(length)
    if name == "all_ff":
        return bytes([0xFF]) * length
    if name == "aa":
        return bytes([0xAA]) * length
    if name == "55":
        return bytes([0x55]) * length
    if name == "counter":
        return bytes(index & 0xFF for index in range(length))
    if name == "all_byte_values":
        return bytes(index & 0xFF for index in range(length))
    if name == "utf8_text":
        seed = "红外 RFAP v1 — deterministic\n".encode()
        return (seed * ((length + len(seed) - 1) // len(seed)))[:length]
    if name == "binary_with_nul":
        seed = b"\x00\xff\x00RFAP\x00\x80"
        return (seed * ((length + len(seed) - 1) // len(seed)))[:length]
    if name in {"prbs7", "prbs15"}:
        width = 7 if name == "prbs7" else 15
        state = (1 << width) - 1
        out = bytearray()
        for _ in range(length):
            value = 0
            for bit in range(8):
                tap = ((state >> (width - 1)) ^ (state >> (width - 2))) & 1
                state = ((state << 1) | tap) & ((1 << width) - 1)
                value |= (state & 1) << bit
            out.append(value)
        return bytes(out)
    if name == "deterministic_random":
        rng = random.Random(0x5037)
        return bytes(rng.randrange(256) for _ in range(length))
    raise ValueError(name)


def completed_descriptor_image(
    request: DescriptorRequest, *, completion_sequence: int = 1
) -> bytes:
    words = list(_DESCRIPTOR_WORDS.unpack(request.pack_body()))
    fragment_count = fragment_count_for_length(len(request.data))
    words[3] = P7_DESCRIPTOR_COMPLETE
    words[17] = 0
    words[18] = len(request.data)
    words[19] = fragment_count
    words[20] = fragment_count
    words[21] = crc32(request.data)
    words[22] = fragment_count
    words[32:40] = sha256_words(request.data)
    words[40:48] = sha256_words(request.data)
    words[53] = P7_KNOWN_GOOD_TXD_HIGH_CYCLES
    if request.lane_policy == 1:
        words[55:58] = [fragment_count, 0, 0]
    elif request.lane_policy == 2:
        words[55:58] = [0, fragment_count, 0]
    elif request.lane_policy == 3:
        words[55:58] = [(fragment_count + 1) // 2, fragment_count // 2, 0]
    elif request.lane_policy == 4:
        words[55:58] = [fragment_count, fragment_count, fragment_count]
    words[63] = completion_sequence
    return _DESCRIPTOR_WORDS.pack(*words)


class ProtocolTests(unittest.TestCase):
    def test_size_matrix(self) -> None:
        sizes = (0, 1, 2, 30, 214, 215, 216, 246, 247, 248, 430, 431, 432, 1024, 4096, 65536, 1048576)
        for size in sizes:
            with self.subTest(size=size):
                data = pattern("counter", size)
                fragments = segment_object(data, session_epoch=7, object_id=size + 1)
                reassembler = Reassembler(expected_session_epoch=7)
                for fragment in fragments:
                    self.assertLessEqual(len(fragment.encode()), 247)
                    reassembler.add(fragment.encode())
                self.assertEqual(reassembler.data(), data)

    def test_pattern_matrix(self) -> None:
        names = (
            "all_zero", "all_ff", "aa", "55", "counter", "all_byte_values",
            "prbs7", "prbs15", "deterministic_random", "utf8_text", "binary_with_nul",
        )
        for name in names:
            with self.subTest(pattern=name):
                data = pattern(name, 1024)
                fragments = segment_object(data, session_epoch=11, object_id=12)
                self.assertEqual(crc32(data), fragments[0].header.object_crc32)

    def test_empty_object_is_header_only(self) -> None:
        fragment = segment_object(b"", session_epoch=1, object_id=2)[0]
        self.assertEqual(len(fragment.encode()), HEADER_BYTES)
        self.assertEqual(fragment.header.chunk_length, 0)

    def test_duplicate_same_is_idempotent(self) -> None:
        fragments = segment_object(pattern("counter", 430), session_epoch=1, object_id=2)
        r = Reassembler(expected_session_epoch=1)
        self.assertEqual(r.add(fragments[0].encode()), "ACCEPTED")
        self.assertEqual(r.add(fragments[0].encode()), "DUPLICATE_SAME")
        self.assertEqual(r.add(fragments[1].encode()), "COMPLETE")
        self.assertEqual(r.duplicates, 1)

    def test_completed_object_replay_same_is_idempotent(self) -> None:
        fragment = segment_object(b"done", session_epoch=1, object_id=2)[0]
        r = Reassembler(expected_session_epoch=1)
        self.assertEqual(r.add(fragment.encode()), "COMPLETE")
        self.assertEqual(r.add(fragment.encode()), "DUPLICATE_SAME_COMPLETE")
        self.assertEqual(r.data(), b"done")

    def test_duplicate_different_rejected(self) -> None:
        fragments = segment_object(pattern("counter", 430), session_epoch=1, object_id=2)
        r = Reassembler(expected_session_epoch=1)
        r.add(fragments[0].encode())
        bad = bytearray(fragments[0].encode())
        bad[-1] ^= 1
        with self.assertRaisesRegex(ProtocolError, "different data"):
            r.add(bytes(bad))

    def test_missing_fragment_never_complete(self) -> None:
        fragments = segment_object(pattern("counter", 431), session_epoch=1, object_id=2)
        r = Reassembler(expected_session_epoch=1)
        r.add(fragments[0].encode())
        with self.assertRaisesRegex(ProtocolError, "Partial|partial"):
            r.data()

    def test_out_of_order_rejected(self) -> None:
        fragments = segment_object(pattern("counter", 431), session_epoch=1, object_id=2)
        r = Reassembler(expected_session_epoch=1)
        with self.assertRaisesRegex(ProtocolError, "strict-order"):
            r.add(fragments[1].encode())

    def test_stale_session_rejected(self) -> None:
        fragment = segment_object(b"x", session_epoch=1, object_id=2)[0]
        with self.assertRaisesRegex(ProtocolError, "stale"):
            Reassembler(expected_session_epoch=2).add(fragment.encode())

    def test_invalid_header_fields(self) -> None:
        valid = bytearray(segment_object(b"x", session_epoch=1, object_id=2)[0].encode())
        mutations = {
            "magic": (0, 0),
            "version": (4, 2),
            "header_len": (6, 31),
            "reserved": (26, 1),
        }
        for name, (offset, value) in mutations.items():
            with self.subTest(name=name):
                raw = valid.copy()
                raw[offset] = value
                with self.assertRaises(ProtocolError):
                    AppFragment.decode(bytes(raw))

    def test_object_crc_failure(self) -> None:
        fragments = segment_object(b"hello", session_epoch=1, object_id=2)
        h = fragments[0].header
        bad = AppFragment(AppHeader(
            session_epoch=h.session_epoch,
            object_id=h.object_id,
            total_length=h.total_length,
            fragment_index=h.fragment_index,
            fragment_count=h.fragment_count,
            chunk_length=h.chunk_length,
            object_crc32=h.object_crc32 ^ 1,
            flags=h.flags,
        ), fragments[0].chunk)
        with self.assertRaisesRegex(ProtocolError, "CRC32"):
            Reassembler(expected_session_epoch=1).add(bad.encode())


class TransportTests(unittest.TestCase):
    def test_backend_conformance(self) -> None:
        for backend in (LocalStubBackend(), MockJtagBackend(), MockPsMailboxBackend()):
            with self.subTest(backend=backend.get_capabilities().name):
                transport = ApplicationTransport(backend)
                data = pattern("deterministic_random", 4096)
                result = transport.send_object(
                    data, session_epoch=0x100, object_id=1, lane_policy=LanePolicy.STRIPE_ROUND_ROBIN
                )
                self.assertTrue(result.passed, result.error)
                self.assertEqual(result.output, data)
                self.assertEqual(result.input_sha256, result.output_sha256)
                self.assertLessEqual(abs(transport.metrics.lane0_fragments - transport.metrics.lane1_fragments), 1)

    def test_replication_semantics(self) -> None:
        transport = ApplicationTransport(LocalStubBackend())
        result = transport.send_object(
            pattern("counter", 1024), session_epoch=1, object_id=2, lane_policy=LanePolicy.REPLICATE_0X3
        )
        self.assertTrue(result.passed)
        self.assertEqual(transport.metrics.replicated_fragments, transport.metrics.fragments_completed)
        self.assertEqual(transport.metrics.lane0_fragments, transport.metrics.lane1_fragments)

    def test_lane_fallback(self) -> None:
        data = pattern("counter", 65536)
        t0 = ApplicationTransport(LocalStubBackend())
        r0 = t0.send_object(
            data, session_epoch=1, object_id=2, lane_policy=LanePolicy.STRIPE_ROUND_ROBIN,
            fault=FaultInjection(unavailable_mask=0x1, after_fragment=3),
        )
        self.assertTrue(r0.passed)
        self.assertGreater(t0.metrics.fallback_lane0_to_lane1, 0)
        t1 = ApplicationTransport(LocalStubBackend())
        r1 = t1.send_object(
            data, session_epoch=1, object_id=3, lane_policy=LanePolicy.STRIPE_ROUND_ROBIN,
            fault=FaultInjection(unavailable_mask=0x2, after_fragment=3),
        )
        self.assertTrue(r1.passed)
        self.assertGreater(t1.metrics.fallback_lane1_to_lane0, 0)

    def test_both_lanes_unavailable_bounded_failure(self) -> None:
        transport = ApplicationTransport(LocalStubBackend())
        result = transport.send_object(
            b"abc", session_epoch=1, object_id=2, lane_policy=LanePolicy.STRIPE_ROUND_ROBIN,
            fault=FaultInjection(unavailable_mask=0x3),
        )
        self.assertFalse(result.passed)
        self.assertIn("ALL_LANES_UNAVAILABLE", result.error)
        self.assertEqual(transport.metrics.fragments_submitted, 0)

    def test_abort_and_restart_new_epoch(self) -> None:
        data = pattern("counter", 4096)
        failed = ApplicationTransport(LocalStubBackend()).send_object(
            data, session_epoch=1, object_id=2, lane_policy=LanePolicy.LANE0_ONLY, abort_after_fragment=3
        )
        self.assertFalse(failed.passed)
        restarted = ApplicationTransport(LocalStubBackend()).send_object(
            data, session_epoch=2, object_id=2, lane_policy=LanePolicy.LANE1_ONLY
        )
        self.assertTrue(restarted.passed)

    def test_atomic_file_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "input.bin"
            output = Path(tmp) / "output.bin"
            source.write_bytes(pattern("binary_with_nul", 1024))
            result = ApplicationTransport(LocalStubBackend()).send_file(
                source, output, session_epoch=1, object_id=2, lane_policy=LanePolicy.LANE0_ONLY
            )
            self.assertTrue(result.passed)
            self.assertEqual(source.read_bytes(), output.read_bytes())
            self.assertFalse(list(Path(tmp).glob("*.partial")))

    def test_queue_backpressure_and_order(self) -> None:
        transport = ApplicationTransport(LocalStubBackend())
        queue = DescriptorQueue(transport, depth=2)
        self.assertTrue(queue.submit(QueuedObject(b"a", 1, 1, LanePolicy.LANE0_ONLY)))
        self.assertTrue(queue.submit(QueuedObject(b"b", 1, 2, LanePolicy.LANE1_ONLY)))
        self.assertFalse(queue.submit(QueuedObject(b"c", 1, 3, LanePolicy.STRIPE_ROUND_ROBIN)))
        results = queue.drain()
        self.assertEqual([result.output for result in results], [b"a", b"b"])
        self.assertEqual(transport.metrics.queue_high_watermark, 2)
        self.assertEqual(transport.metrics.backpressure_events, 1)

    def test_tcp_stub_cannot_open(self) -> None:
        backend = TcpStubDisabled()
        self.assertFalse(backend.get_capabilities().network_enabled)
        with self.assertRaisesRegex(RuntimeError, "NO_NETWORK_CABLE"):
            backend.open()


class PsMailboxCodecTests(unittest.TestCase):
    def test_descriptor_roundtrip(self) -> None:
        data = pattern("deterministic_random", 4096)
        request = DescriptorRequest(
            session_epoch=7, object_id=9, input_address=0x01000000,
            output_address=0x02000000, data=data, lane_policy=3,
            trace_address=0x03000000, trace_capacity=32,
        )
        decoded = unpack_descriptor(request.pack_body())
        self.assertEqual(decoded["status"], P7_DESCRIPTOR_FREE)
        self.assertEqual(decoded["object_length"], len(data))
        self.assertEqual(decoded["expected_sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(tuple(decoded["words"][24:32]), sha256_words(data))

    def test_descriptor_ready_is_a_separate_last_publication(self) -> None:
        request = DescriptorRequest(
            1, 2, 0x01000000, 0x02000000, b"publication", 1
        )
        body = request.pack_body()
        self.assertEqual(unpack_descriptor(body)["status"], P7_DESCRIPTOR_FREE)

        torn = bytearray(256)
        torn[:128] = body[:128]
        self.assertEqual(unpack_descriptor(bytes(torn))["status"], P7_DESCRIPTOR_FREE)

        ready_word = pack_ready_publication_word()
        self.assertEqual(struct.unpack("<I", ready_word)[0], P7_DESCRIPTOR_READY)
        published = bytearray(body)
        published[
            P7_DESCRIPTOR_STATUS_OFFSET : P7_DESCRIPTOR_STATUS_OFFSET + 4
        ] = ready_word
        self.assertEqual(
            unpack_descriptor(bytes(published))["status"], P7_DESCRIPTOR_READY
        )
        self.assertEqual(descriptor_status_address(0), 0x0002010C)
        self.assertEqual(descriptor_status_address(7), 0x0002080C)
        self.assertEqual(
            descriptor_ready_publication(7), (0x0002080C, ready_word)
        )

    def test_invalid_ps_ranges_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "aligned"):
            DescriptorRequest(1, 1, 0x01000001, 0x02000000, b"x", 1).pack()
        with self.assertRaisesRegex(ValueError, "overlap"):
            DescriptorRequest(1, 1, 0x01000000, 0x01000000, b"x", 1).pack()
        with self.assertRaisesRegex(ValueError, "lane policy"):
            DescriptorRequest(1, 1, 0x01000000, 0x02000000, b"x", 5).pack()

    def test_uint32_identity_boundaries(self) -> None:
        for value in (0, 0xFFFFFFFF):
            with self.subTest(value=value):
                request = DescriptorRequest(
                    value, value, 0x01000000, 0x02000000, b"x", 1
                )
                decoded = unpack_descriptor(request.pack_body())
                self.assertEqual(decoded["session_epoch"], value)
                self.assertEqual(decoded["object_id"], value)
        for value in (-1, 0x100000000):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "session_epoch.*uint32"):
                    DescriptorRequest(
                        value, 1, 0x01000000, 0x02000000, b"x", 1
                    ).pack_body()

    def test_trace_geometry_overlap_and_end_boundary(self) -> None:
        data = b"x" * 216
        exact = DescriptorRequest(
            1,
            1,
            0x01000000,
            0x02000000,
            data,
            1,
            trace_address=0x03000000,
            trace_capacity=2,
        )
        self.assertEqual(unpack_descriptor(exact.pack_body())["trace_capacity"], 2)
        with self.assertRaisesRegex(ValueError, "smaller than fragment count"):
            DescriptorRequest(
                1,
                1,
                0x01000000,
                0x02000000,
                data,
                1,
                trace_address=0x03000000,
                trace_capacity=1,
            ).pack_body()
        with self.assertRaisesRegex(ValueError, "trace range overlaps"):
            DescriptorRequest(
                1,
                1,
                0x01000000,
                0x02000000,
                data,
                1,
                trace_address=0x01000000,
                trace_capacity=2,
            ).pack_body()

        tail = DescriptorRequest(
            1,
            1,
            0x01000000,
            0x02000000,
            b"",
            1,
            trace_address=0x1FFFFFC0,
            trace_capacity=1,
        )
        tail.pack_body()
        with self.assertRaisesRegex(ValueError, "outside validated PS DDR"):
            DescriptorRequest(
                1,
                1,
                0x01000000,
                0x02000000,
                b"x" * 216,
                1,
                trace_address=0x1FFFFFC0,
                trace_capacity=2,
            ).pack_body()

    def test_mailbox_codec(self) -> None:
        decoded = unpack_mailbox(pack_mailbox(queue_depth=P7_QUEUE_DEPTH))
        self.assertEqual(decoded["service_state"], P7_SERVICE_BOOTING)
        self.assertEqual(decoded["queue_depth"], P7_QUEUE_DEPTH)
        self.assertEqual(decoded["queue_occupancy"], 0)
        self.assertEqual(decoded["max_runtime_seconds"], 1800)
        self.assertEqual(decoded["runtime_flags"] & 1, 1)
        self.assertEqual(decoded["calibration_window_seconds"], 300)
        self.assertEqual(decoded["sample_interval_seconds"], 10)

    def test_mailbox_runtime_bounds(self) -> None:
        self.assertEqual(
            unpack_mailbox(pack_mailbox(queue_depth=1))["queue_depth"], 1
        )
        with self.assertRaisesRegex(ValueError, "1..8"):
            pack_mailbox(queue_depth=0)
        with self.assertRaisesRegex(ValueError, "control command"):
            pack_mailbox(control_command=6)
        with self.assertRaisesRegex(ValueError, "runtime"):
            pack_mailbox(max_runtime_seconds=1801)
        with self.assertRaisesRegex(ValueError, "calibration"):
            pack_mailbox(max_runtime_seconds=30, calibration_window_seconds=31)
        with self.assertRaisesRegex(ValueError, "sample"):
            pack_mailbox(
                max_runtime_seconds=30,
                calibration_window_seconds=0,
                sample_interval_seconds=31,
            )

    def test_runtime_elapsed_seqlock_rejects_rollover_tears_and_regression(self) -> None:
        previous = (7 << 32) | 0xFFFFFF00
        current = (8 << 32) | 0x00000100
        self.assertEqual(
            current,
            decode_runtime_elapsed_snapshot(42, 0x00000100, 8, 42, previous=previous),
        )
        # A read spanning odd -> even publication must never be accepted.
        with self.assertRaisesRegex(ValueError, "stable even sequence"):
            decode_runtime_elapsed_snapshot(41, 0x00000100, 7, 42, previous=previous)
        # Monotonic defense rejects the exact low-new/high-old rollover tear
        # that could otherwise move a post-cutoff sample ~2^32 ticks backward.
        with self.assertRaisesRegex(ValueError, "regressed"):
            decode_runtime_elapsed_snapshot(42, 0x00000100, 7, 42, previous=previous)

    def test_completed_descriptor_integrity(self) -> None:
        data = pattern("binary_with_nul", 1024)
        request = DescriptorRequest(1, 2, 0x01000000, 0x02000000, data, 3)
        raw = completed_descriptor_image(request, completion_sequence=7)
        stable = unpack_stable_terminal_descriptor(
            P7_DESCRIPTOR_COMPLETE,
            raw,
            struct.pack("<I", P7_DESCRIPTOR_COMPLETE),
        )
        self.assertEqual(stable["completion_sequence"], 7)
        self.assertTrue(
            validate_completed(
                request, raw, data, expected_completion_sequence=7
            )["passed"]
        )

    def test_terminal_snapshot_rejects_torn_reads(self) -> None:
        request = DescriptorRequest(1, 2, 0x01000000, 0x02000000, b"x", 1)
        raw = completed_descriptor_image(request)
        with self.assertRaisesRegex(ValueError, "changed during snapshot"):
            unpack_stable_terminal_descriptor(
                P7_DESCRIPTOR_COMPLETE, raw, P7_DESCRIPTOR_READY
            )
        with self.assertRaisesRegex(ValueError, "does not match snapshot"):
            unpack_stable_terminal_descriptor(
                P7_DESCRIPTOR_READY, raw, P7_DESCRIPTOR_READY
            )

    def test_completed_descriptor_rejects_stale_identity_and_sequence(self) -> None:
        data = pattern("counter", 1024)
        request = DescriptorRequest(5, 7, 0x01000000, 0x02000000, data, 3)
        stale_request = DescriptorRequest(
            5, 8, 0x01000000, 0x02000000, data, 3
        )
        stale = completed_descriptor_image(stale_request, completion_sequence=4)
        result = validate_completed(
            request, stale, data, expected_completion_sequence=5
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("object_id=" in item for item in result["failures"]))
        self.assertTrue(
            any("completion_sequence=" in item for item in result["failures"])
        )

    def test_completed_descriptor_rejects_safety_and_lane_mismatch(self) -> None:
        data = pattern("counter", 1024)
        request = DescriptorRequest(1, 2, 0x01000000, 0x02000000, data, 3)
        baseline = list(_DESCRIPTOR_WORDS.unpack(completed_descriptor_image(request)))

        unsafe = baseline.copy()
        unsafe[53] = P7_KNOWN_GOOD_TXD_HIGH_CYCLES + 1
        result = validate_completed(request, _DESCRIPTOR_WORDS.pack(*unsafe), data)
        self.assertFalse(result["passed"])
        self.assertTrue(
            any("max_txd_high_cycles" in item for item in result["failures"])
        )

        repeated_at_p7 = baseline.copy()
        repeated_at_p7[22] += 1
        result = validate_completed(
            request, _DESCRIPTOR_WORDS.pack(*repeated_at_p7), data
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("exactly one P7 submission" in item for item in result["failures"]))

        no_p6_retry_budget = DescriptorRequest(
            1, 2, 0x01000000, 0x02000000, data, 3, max_retries=0
        )
        over_budget = list(
            _DESCRIPTOR_WORDS.unpack(completed_descriptor_image(no_p6_retry_budget))
        )
        over_budget[48] = 1
        result = validate_completed(
            no_p6_retry_budget, _DESCRIPTOR_WORDS.pack(*over_budget), data
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("acceptance cap" in item for item in result["failures"]))

        wrong_lane = baseline.copy()
        wrong_lane[55] -= 1
        result = validate_completed(
            request, _DESCRIPTOR_WORDS.pack(*wrong_lane), data
        )
        self.assertFalse(result["passed"])
        self.assertTrue(any("lane0_fragments" in item for item in result["failures"]))


if __name__ == "__main__":
    unittest.main()
