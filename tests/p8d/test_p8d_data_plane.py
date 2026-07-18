from __future__ import annotations

import binascii
import hashlib
import unittest

from tools.p8d_data_plane_reference import (
    AckAggregator,
    AxisBeat,
    DescriptorRing,
    HealthWeightedScheduler,
    ProtocolError,
    SelectiveRepeatRx,
    SelectiveRepeatTx,
    VNextStreamVerifier,
    axis_backpressure_model,
    sack_decode,
    sack_encode,
    seq_before,
    seq_distance,
    seq_in_window,
    targeted_and_exhaustive,
    validate_axis_packet,
)
from tools.p8d_rfap_reference import (
    Capabilities,
    MODE_LEGACY,
    MODE_VNEXT,
    VNextHeader,
    negotiate,
)


class SequenceAndSackTests(unittest.TestCase):
    def test_modular_wrap(self) -> None:
        self.assertEqual(seq_distance(0, 0xFFFF), 1)
        self.assertTrue(seq_before(0xFFFF, 0))
        self.assertTrue(seq_in_window(1, 0xFFFF, 4))
        self.assertFalse(seq_in_window(4, 0xFFFF, 4))

    def test_sack_round_trip(self) -> None:
        received = {0xFFFF, 0, 2}
        bitmap = sack_encode(0xFFFF, received, 32)
        self.assertEqual(sack_decode(0xFFFF, bitmap, 32), received)
        with self.assertRaises(ProtocolError):
            sack_decode(0, 1 << 32, 32)

    def test_reduced_exhaustive(self) -> None:
        result = targeted_and_exhaustive()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["receive_orders"], 24)


class SelectiveRepeatTests(unittest.TestCase):
    def test_tx_sack_hole_duplicate_ack_and_migration(self) -> None:
        tx = SelectiveRepeatTx(window_size=4, sack_bits=4, initial_sequence=0xFFFE)
        entries = [tx.allocate(payload_id=i, payload_length=10, descriptor_index=i)
                   for i in range(4)]
        for entry in entries:
            tx.issue(entry.sequence, lane=0, path_epoch=3)
        completed = tx.apply_ack(ack_base=0, bitmap=0b0010, session_epoch=1,
                                 bitmap_width=4)
        self.assertEqual(set(completed), {0xFFFE, 0xFFFF, 1})
        self.assertIn(0, tx.entries)
        self.assertTrue(tx.migrate(0, 1, 4, "LANE_FAULT"))
        self.assertFalse(tx.migrate(1, 1, 4, "LATE"))
        tx.apply_ack(ack_base=1, bitmap=0, session_epoch=1, bitmap_width=4)
        self.assertEqual(tx.occupancy, 0)
        self.assertEqual(len(tx.completion_log), 4)
        tx.apply_ack(ack_base=1, bitmap=0, session_epoch=1, bitmap_width=4)
        self.assertEqual(len(tx.completion_log), 4)

    def test_retry_exhaustion_bounded(self) -> None:
        tx = SelectiveRepeatTx(window_size=2, sack_bits=2, max_retry=1, rto_cycles=1)
        entry = tx.allocate(payload_id=1, payload_length=1)
        tx.issue(entry.sequence, 0, 1)
        tx.tick()
        self.assertEqual(tx.entries[entry.sequence].retry_count, 1)
        tx.issue(entry.sequence, 1, 2)
        exhausted = tx.tick()
        self.assertEqual(exhausted, [entry.sequence])
        self.assertEqual(tx.occupancy, 0)

    def test_rx_reorder_duplicate_and_stale(self) -> None:
        rx = SelectiveRepeatRx(window_size=8, sack_bits=8, session_epoch=9,
                               path_epoch=4)
        self.assertEqual(rx.receive(sequence=1, session_epoch=9, path_epoch=4,
                                    payload_id=101, payload_length=2), "ACCEPTED")
        self.assertEqual(rx.receive(sequence=1, session_epoch=9, path_epoch=4,
                                    payload_id=101, payload_length=2), "DUPLICATE")
        self.assertEqual(rx.release_contiguous(), [])
        self.assertEqual(rx.receive(sequence=0, session_epoch=9, path_epoch=3,
                                    payload_id=100, payload_length=2), "ACCEPTED")
        self.assertEqual([item.payload_id for item in rx.release_contiguous()], [100, 101])
        self.assertEqual(rx.receive(sequence=2, session_epoch=8, path_epoch=4,
                                    payload_id=102, payload_length=2), "STALE_SESSION")
        self.assertEqual(rx.receive(sequence=2, session_epoch=9, path_epoch=2,
                                    payload_id=102, payload_length=2), "STALE_PATH_EPOCH")

    def test_ack_aggregation_bounded(self) -> None:
        agg = AckAggregator(threshold=4, max_delay_cycles=10, credit_low_watermark=2)
        self.assertFalse(agg.observe(accepted_frames=1, cycles=3, receiver_credit=10))
        self.assertTrue(agg.observe(cycles=7, receiver_credit=10))
        agg.emit()
        self.assertEqual(agg.timer_expiry_count, 1)
        self.assertTrue(agg.observe(accepted_frames=1, receiver_credit=2))


class SchedulerAxisDmaTests(unittest.TestCase):
    def test_weighted_scheduler_and_fault_isolation(self) -> None:
        scheduler = HealthWeightedScheduler(2, weights=[1, 2], quantum_bytes=64)
        for _ in range(600):
            while True:
                decision = scheduler.select(
                    cost=64, active_mask=3, ready_mask=3, health_mask=3,
                    mapping_mask=3, frame_admission_mask=3, lane_tx_permit_mask=3,
                    duty_headroom_mask=3, fault_free_mask=3,
                    global_permit_effective=True, receiver_credit=8)
                if decision.admitted:
                    break
        ratio = scheduler.scheduled_bytes[1] / scheduler.scheduled_bytes[0]
        self.assertAlmostEqual(ratio, 2.0, delta=0.05)
        decision = scheduler.select(
            cost=1, active_mask=3, ready_mask=3, health_mask=1,
            mapping_mask=3, frame_admission_mask=3, lane_tx_permit_mask=3,
            duty_headroom_mask=3, fault_free_mask=1,
            global_permit_effective=True, receiver_credit=8, last_lane=1, retry=True)
        while not decision.admitted:
            decision = scheduler.select(
                cost=1, active_mask=3, ready_mask=3, health_mask=1,
                mapping_mask=3, frame_admission_mask=3, lane_tx_permit_mask=3,
                duty_headroom_mask=3, fault_free_mask=1,
                global_permit_effective=True, receiver_credit=8, last_lane=1, retry=True)
        self.assertEqual(decision.lane, 0)
        self.assertEqual(decision.migration_reason, "RETRY_HEALTH_MIGRATION")

    def test_axis_random_backpressure(self) -> None:
        beats = [AxisBeat(i, 0xF, i == 19, 0xA5) for i in range(20)]
        validate_axis_packet(beats, 32, 80)
        result = axis_backpressure_model(beats, seed=17)
        self.assertEqual(result["loss"], 0)
        self.assertGreater(result["stalled_cycles"], 0)
        with self.assertRaises(ProtocolError):
            validate_axis_packet([AxisBeat(1, 0b0101, True, 0)], 32, 2)

    def test_independent_rings_generation_and_reclaim(self) -> None:
        tx = DescriptorRing(4, name="TX")
        rx = DescriptorRing(4, name="RX")
        td = tx.prepare(buffer_address=64, capacity=100, requested_length=80)
        rd = rx.prepare(buffer_address=128, capacity=100, requested_length=100)
        self.assertEqual(tx.hw_acquire().index, td.index)
        self.assertEqual(rx.hw_acquire().index, rd.index)
        self.assertTrue(tx.hw_complete(td.index, td.generation, actual_length=80))
        self.assertEqual(tx.reclaim().actual_length, 80)
        old_generation = rx.generation
        rx.abort_reset()
        self.assertFalse(rx.hw_complete(rd.index, old_generation, actual_length=100))
        self.assertEqual(tx.leak_count() + rx.leak_count(), 0)


class RfapStreamingTests(unittest.TestCase):
    def test_vnext_header_and_negotiation(self) -> None:
        header = VNextHeader(3, 1, 2, 3, 4, 5, 6, 0xFFFF, 7)
        self.assertEqual(VNextHeader.unpack(header.pack()), header)
        both = Capabilities((1, 2), 64, 64, True, True, True)
        legacy = Capabilities((1,), 1, 0, False, False, False)
        self.assertEqual(negotiate(both, both, MODE_VNEXT), MODE_VNEXT)
        self.assertEqual(negotiate(both, legacy, MODE_VNEXT), MODE_LEGACY)
        with self.assertRaises(ProtocolError):
            negotiate(Capabilities((2,), 64, 64, True, True, True), legacy,
                      MODE_VNEXT)

    def test_vnext_bounded_stream_atomic_publish(self) -> None:
        identity = (3, 7, 11, 13)
        payload = (b"p8d-stream-vector" * 4096)
        verifier = VNextStreamVerifier(endpoint_id=3, session_epoch=7,
                                       stream_id=11, object_id=13,
                                       max_inflight_bytes=4096)
        for offset in range(0, len(payload), 4096):
            verifier.push(identity=identity, offset=offset, data=payload[offset:offset + 4096])
        self.assertTrue(verifier.finish(
            total_length=len(payload), object_crc32=binascii.crc32(payload) & 0xFFFFFFFF,
            sha256_hex=hashlib.sha256(payload).hexdigest()))
        self.assertEqual(verifier.publish_count, 1)

    def test_partial_or_stale_stream_not_published(self) -> None:
        verifier = VNextStreamVerifier(endpoint_id=1, session_epoch=2,
                                       stream_id=3, object_id=4)
        verifier.push(identity=(1, 2, 3, 4), offset=0, data=b"partial")
        self.assertFalse(verifier.finish(total_length=100, object_crc32=0,
                                         sha256_hex="0" * 64))
        self.assertEqual(verifier.publish_count, 0)
        with self.assertRaises(ProtocolError):
            verifier.push(identity=(1, 1, 3, 4), offset=7, data=b"stale")


if __name__ == "__main__":
    unittest.main()
