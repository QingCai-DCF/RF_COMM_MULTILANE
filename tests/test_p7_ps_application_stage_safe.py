from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest import mock

try:
    import tkinter
except ImportError:  # pragma: no cover - Tcl runtime is optional outside release gates.
    tkinter = None


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "hw" / "run_p7_ps_application_stage_safe.py"
SPEC = importlib.util.spec_from_file_location("p7_ps_safe_stage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
stage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage
SPEC.loader.exec_module(stage)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tcl_interpreter():
    if tkinter is None:
        raise unittest.SkipTest("Python Tcl runtime is unavailable")
    try:
        return tkinter.Tcl()
    except Exception as exc:  # pragma: no cover - platform Tcl installation failure.
        raise unittest.SkipTest(f"Python Tcl runtime is unavailable: {exc}") from exc


def install_captured_tcl_exit(interp) -> None:
    interp.eval(
        "proc exit {code} {\n"
        "  set ::p7_captured_exit_code $code\n"
        "  return -code error \"__P7_CAPTURED_EXIT__$code\"\n"
        "}"
    )


class P7PsApplicationSafeStageTests(unittest.TestCase):
    def test_shutdown_command_matches_the_17_argument_jtag_tcl_contract(self) -> None:
        args = stage.build_parser().parse_args([])
        args.vivado_path = str(ROOT / "synthetic-vivado.bat")
        args.authorization_file = str(ROOT / ".hardware_authorization" / "synthetic.txt")
        args.board_id = "210512180081"
        args.expected_part = "xc7z010clg400-1"
        args.expected_target = "localhost:3121/xilinx_tcf/Digilent/210512180081"
        args.hw_server_url = "localhost:3121"
        args.jtag_frequency_hz = 1_000_000
        args.shutdown_bitstream = str(ROOT / "shutdown_bitstream" / "tfdu_shutdown_j10_j11.bit")
        args.max_runtime_sec = 900
        result = ROOT / "synthetic-shutdown-result.txt.partial"
        command = stage.build_shutdown_command(args, result)
        tclargs = command[command.index("-tclargs") + 1 :]
        self.assertEqual(17, len(tclargs))
        self.assertEqual("1", tclargs[13])
        self.assertEqual(str(stage.process_support.MAX_TRANSACTION_BYTES), tclargs[14])
        self.assertEqual("900", tclargs[15])
        self.assertEqual(str(Path(args.shutdown_bitstream).resolve()), tclargs[16])

    def test_all_modes_build_bounded_atomic_mailbox_descriptor_bundles(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "input.bin"
            input_path.write_bytes(bytes(range(251)) * 20)
            expected_counts = {
                "functional": range(1, 9),
                "fault-fallback": range(7, 8),
                "queue": range(8, 9),
                "abort-restart": range(3, 4),
            }
            for mode, allowed in expected_counts.items():
                bundle = stage.build_stage_bundle(
                    bundle_dir=root / mode,
                    mode=mode,
                    input_path=input_path,
                    max_runtime_sec=900,
                    calibration_sec=0,
                    acceptance_sec=0,
                    sample_interval_sec=10,
                    idle_margin_sec=10,
                    stationary_object_bytes=4096,
                )
                self.assertIn(len(bundle.cases), allowed)
                self.assertEqual(stage.PLAN_MAGIC, bundle.plan_path.read_text(encoding="utf-8").splitlines()[0])
                self.assertEqual(bundle.plan_sha256, sha256(bundle.plan_path))
                manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
                self.assertTrue(manifest["atomic_files"])
                self.assertEqual("PENDING_HW", manifest["HARDWARE_ACCEPTANCE"])
                self.assertEqual(stage.P7_COUNTS_PER_SECOND, manifest["schedule"]["counts_per_second"])
                self.assertIn(f"COUNTS_PER_SECOND {stage.P7_COUNTS_PER_SECOND}", bundle.plan_path.read_text(encoding="utf-8"))
                descriptors = (bundle.directory / "descriptors.bin").read_bytes()
                self.assertEqual(8 * 256, len(descriptors))
                for case in bundle.cases:
                    ready = struct.unpack_from("<I", descriptors, case.slot * 256 + 12)[0]
                    free = struct.unpack_from(
                        "<I", (bundle.directory / f"descriptor_free_{case.slot}.bin").read_bytes(), 12
                    )[0]
                    self.assertEqual(0, ready)
                    self.assertEqual(0, free)
                    publication = manifest["cases"][case.slot]["ready_publication"]
                    self.assertTrue(publication["published_after_body"])
                    self.assertEqual(1, publication["value"])
                    self.assertLess(case.request.trace_address + case.trace_capacity * 64, 0x20000000)
                self.assertFalse(list(bundle.directory.glob("*.partial")))
                if mode == "functional":
                    sizes = [0, 1, 30, 214, 215, 216, 247, 248, 430, 431, 432, 1024]
                    self.assertEqual([size for size in sizes for _ in range(4)], [len(case.request.data) for case in bundle.boundary_cases])
                    self.assertEqual([policy for _ in sizes for policy in (1, 2, 3, 4)], [case.request.lane_policy for case in bundle.boundary_cases])
                    self.assertEqual(6, len(manifest["boundary_descriptor_batches"]))
                    self.assertIsNotNone(bundle.functional_checkpoint)
                    assert bundle.functional_checkpoint is not None
                    self.assertEqual((4096, 3, 49), (
                        len(bundle.functional_checkpoint.request.data),
                        bundle.functional_checkpoint.request.lane_policy,
                        bundle.functional_checkpoint.request.object_id,
                    ))
                    self.assertEqual(list(range(1, 49)), [case.request.object_id for case in bundle.boundary_cases])
                    for case in bundle.boundary_cases:
                        publication = manifest["boundary_cases"][case.slot]["ready_publication"]
                        self.assertTrue(publication["published_after_body"])
                        self.assertEqual(1, publication["value"])
                else:
                    self.assertEqual([], bundle.boundary_cases)
                    self.assertIsNone(bundle.functional_checkpoint)
                if mode == "queue":
                    self.assertIsNotNone(bundle.queue_overflow_candidate)
                    candidate = bundle.queue_overflow_candidate
                    assert candidate is not None
                    self.assertEqual(9, candidate.request.object_id)
                    self.assertNotIn(9, {case.request.object_id for case in bundle.cases})
                    overflow = manifest["queue_overflow_candidate"]
                    self.assertEqual("FULL", overflow["admission_contract"]["expected_result"])
                    self.assertEqual(0, overflow["admission_contract"]["expected_ddr_write_count"])
                    self.assertTrue(overflow["admission_contract"]["ring_must_remain_byte_identical"])
                    stage.verify_bundle_integrity(bundle)
                else:
                    self.assertIsNone(bundle.queue_overflow_candidate)

    def test_stationary_schedule_is_exact_and_leaves_idle_margin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "input.bin"
            input_path.write_bytes(b"stationary-seed")
            bundle = stage.build_stage_bundle(
                bundle_dir=root / "stationary",
                mode="stationary",
                input_path=input_path,
                max_runtime_sec=1800,
                calibration_sec=300,
                acceptance_sec=1500,
                sample_interval_sec=30,
                idle_margin_sec=60,
                stationary_object_bytes=64 * 1024,
            )
            manifest = json.loads(bundle.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(8, len(bundle.cases))
        self.assertEqual([1024 * 1024, 64 * 1024, 64 * 1024, 64 * 1024, 1024 * 1024, 4096, 64 * 1024, 64 * 1024], [len(case.request.data) for case in bundle.cases])
        self.assertEqual(
            {"counter", "prbs15", "deterministic_random", "binary_all_byte_values_repeated"},
            {case.pattern for case in bundle.cases},
        )
        self.assertEqual([1, 3, 3, 2, 4, 3, 1, 2], [case.request.lane_policy for case in bundle.cases])
        self.assertEqual({1, 2, 3, 4}, {case.request.lane_policy for case in bundle.cases})
        self.assertEqual(1800, manifest["schedule"]["calibration_plus_acceptance"])
        self.assertEqual(1740, manifest["schedule"]["scheduling_cutoff_sec"])
        self.assertLess(manifest["schedule"]["scheduling_cutoff_sec"], 1800)

    def test_canonical_samples_use_fixed_terminal_end_tick_membership(self) -> None:
        cps = 1000
        runtime_start = 10_000
        relative_ends = (29_900, 30_000, 30_100, 59_900)
        objects = []
        for sequence, relative_end in enumerate(relative_ends, 1):
            objects.append(
                {
                    "sequence": sequence,
                    "session_epoch": 1,
                    "object_id": 100 + sequence,
                    "start_ticks": runtime_start + relative_end - 100,
                    "end_ticks": runtime_start + relative_end,
                    "bytes_completed": sequence,
                    "fragments_completed": sequence,
                    "lane0_fragments": sequence,
                    "lane1_fragments": 0,
                    "replicated_fragments": 0,
                    "fallback_count": 0,
                    "p6_retry_count": 0,
                    "p6_retry_exhausted": 0,
                    "p6_tx_fail": 0,
                    "p6_crc_bad": 0,
                    "p6_payload_mismatch": 0,
                    "max_txd_high_cycles": 8,
                    "duty_violations": 0,
                }
            )
        samples, failures = stage._canonical_stationary_samples(
            objects,
            runtime_start_ticks=runtime_start,
            counts_per_second=cps,
            sample_interval_seconds=30,
            runtime_seconds=60,
        )
        self.assertEqual([], failures)
        self.assertEqual([2, 4], [item["objects"] for item in samples])
        self.assertEqual([3, 10], [item["bytes"] for item in samples])
        self.assertEqual([2, 2], [item["latency_count"] for item in samples])
        # Harvest order/time is irrelevant: immutable end_ticks place the
        # 29.9/30.0 completions in the first exact threshold.
        delayed, delayed_failures = stage._canonical_stationary_samples(
            list(reversed(objects)),
            runtime_start_ticks=runtime_start,
            counts_per_second=cps,
            sample_interval_seconds=30,
            runtime_seconds=60,
        )
        self.assertEqual([], delayed_failures)
        self.assertEqual(samples, delayed)

    def test_mailbox_binds_firmware_stationary_admission_cutoff(self) -> None:
        raw = stage.pack_mailbox(
            max_runtime_seconds=1800,
            scheduling_cutoff_seconds=1740,
            admission_guard_seconds=1,
        )
        decoded = stage.unpack_mailbox(raw)
        self.assertEqual(1740, decoded["scheduling_cutoff_seconds"])
        self.assertEqual(1, decoded["admission_guard_seconds"])
        self.assertEqual(0, decoded["failure_snapshot_address"])
        self.assertEqual(0, decoded["failure_snapshot_bytes"])
        self.assertEqual(0, decoded["failure_snapshot_status"])
        self.assertEqual(0, decoded["failure_snapshot_magic_readback"])
        with self.assertRaises(ValueError):
            stage.pack_mailbox(
                max_runtime_seconds=1800,
                scheduling_cutoff_seconds=1740,
                admission_guard_seconds=0,
            )

    def test_fault_and_abort_modes_encode_expected_terminal_contracts(self) -> None:
        functional = stage.build_cases("functional", b"seed", 4096)
        fault = stage.build_cases("fault-fallback", b"seed", 4096)
        abort = stage.build_cases("abort-restart", b"seed", 4096)
        self.assertEqual(8, len(functional))
        self.assertEqual([1, 2, 3, 4], [case.request.lane_policy for case in functional[:4]])
        self.assertEqual([54, 55, 56, 57, 50, 51, 52, 53], [case.request.object_id for case in functional])
        self.assertTrue(all(len(case.request.data) == 1024 * 1024 for case in functional[:4]))
        self.assertTrue(all(len(case.request.data) == 64 * 1024 for case in functional[4:]))
        self.assertTrue(any(case.expected_status == stage.P7_DESCRIPTOR_FAILED and case.expected_error == 8 for case in fault))
        self.assertTrue(any(case.request.unavailable_lane_mask in (1, 2) for case in fault))
        self.assertEqual([3, 3, 4, 4, 1, 2, 3], [case.request.lane_policy for case in fault])
        self.assertEqual(3, sum(case.expected_status == stage.P7_DESCRIPTOR_FAILED for case in fault))
        self.assertTrue(all(len(case.request.data) == 64 * 1024 for case in fault))
        self.assertEqual(stage.P7_DESCRIPTOR_ABORTED, abort[0].expected_status)
        self.assertEqual(15, abort[0].expected_error)
        self.assertTrue(all(len(case.request.data) == 1024 * 1024 for case in abort))
        self.assertGreater(abort[1].request.session_epoch, abort[0].request.session_epoch)
        self.assertEqual(abort[1].request.session_epoch, abort[2].request.session_epoch)
        self.assertEqual(abort[1].request.object_id, abort[2].request.object_id)
        self.assertEqual((6, 19), (abort[2].expected_status, abort[2].expected_error))

    def test_completed_bundle_postprocessing_validates_mailbox_descriptor_trace_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "input.bin"
            input_path.write_bytes(b"abc")
            bundle = stage.build_stage_bundle(
                bundle_dir=root / "bundle",
                mode="functional",
                input_path=input_path,
                max_runtime_sec=900,
                calibration_sec=0,
                acceptance_sec=0,
                sample_interval_sec=10,
                idle_margin_sec=10,
                stationary_object_bytes=4096,
            )
            for case in bundle.cases:
                raw = bytearray(case.request.pack())
                words = list(struct.unpack("<64I", raw))
                words[3] = stage.P7_DESCRIPTOR_COMPLETE
                words[17] = 0
                words[18] = len(case.request.data)
                words[19] = case.trace_capacity
                words[20] = case.trace_capacity
                words[21] = zlib.crc32(case.request.data) & 0xFFFFFFFF
                words[22] = case.trace_capacity
                words[32:40] = words[24:32]
                words[40:48] = words[24:32]
                if case.request.lane_policy == 1:
                    words[55] = case.trace_capacity
                elif case.request.lane_policy == 2:
                    words[56] = case.trace_capacity
                elif case.request.lane_policy == 4:
                    words[55] = case.trace_capacity
                    words[56] = case.trace_capacity
                    words[57] = case.trace_capacity
                else:
                    words[55] = (case.trace_capacity + 1) // 2
                    words[56] = case.trace_capacity // 2
                words[58] = case.slot * 100 + 1
                words[60] = case.slot * 100 + 99
                words[63] = (54 + case.slot) if case.slot < 4 else (50 + case.slot - 4)
                (bundle.directory / f"descriptor_result_{case.slot}.bin").write_bytes(struct.pack("<64I", *words))
                (bundle.directory / f"output_result_{case.slot}.bin").write_bytes(case.request.data)
                traces = bytearray(case.trace_capacity * 64)
                for index in range(case.trace_capacity):
                    trace_words = [0] * 16
                    trace_words[0] = stage.P7_TRACE_MAGIC
                    trace_words[1] = case.request.session_epoch
                    trace_words[2] = case.request.object_id
                    trace_words[3] = (case.trace_capacity << 16) | index
                    if case.request.lane_policy == 1:
                        trace_words[4] = 1
                    elif case.request.lane_policy == 2:
                        trace_words[4] = 2
                    elif case.request.lane_policy == 4:
                        trace_words[4] = 3
                    else:
                        trace_words[4] = 1 if index % 2 == 0 else 2
                    trace_words[5] = 1
                    trace_words[6] = 1
                    trace_words[8] = index * 10 + 1
                    trace_words[10] = index * 10 + 2
                    struct.pack_into("<16I", traces, index * 64, *trace_words)
                (bundle.directory / f"trace_result_{case.slot}.bin").write_bytes(traces)
            for case in bundle.boundary_cases:
                words = list(struct.unpack("<64I", case.request.pack()))
                words[3] = stage.P7_DESCRIPTOR_COMPLETE
                words[18] = len(case.request.data)
                words[19] = case.trace_capacity
                words[20] = case.trace_capacity
                words[21] = zlib.crc32(case.request.data) & 0xFFFFFFFF
                words[22] = case.trace_capacity
                words[32:40] = words[24:32]
                words[40:48] = words[24:32]
                if case.request.lane_policy == 1:
                    words[55] = case.trace_capacity
                elif case.request.lane_policy == 2:
                    words[56] = case.trace_capacity
                elif case.request.lane_policy == 4:
                    words[55] = case.trace_capacity
                    words[56] = case.trace_capacity
                    words[57] = case.trace_capacity
                else:
                    words[55] = (case.trace_capacity + 1) // 2
                    words[56] = case.trace_capacity // 2
                words[58] = 1000 + case.slot * 100
                words[60] = 1050 + case.slot * 100
                words[63] = case.slot + 1
                prefix = f"boundary_{case.slot}"
                (bundle.directory / f"{prefix}_descriptor_result.bin").write_bytes(struct.pack("<64I", *words))
                (bundle.directory / f"{prefix}_output_result.bin").write_bytes(case.request.data)
                traces = bytearray(case.trace_capacity * 64)
                for index in range(case.trace_capacity):
                    trace_words = [0] * 16
                    trace_words[0] = stage.P7_TRACE_MAGIC
                    trace_words[1] = case.request.session_epoch
                    trace_words[2] = case.request.object_id
                    trace_words[3] = (case.trace_capacity << 16) | index
                    if case.request.lane_policy == 1:
                        trace_words[4] = 1
                    elif case.request.lane_policy == 2:
                        trace_words[4] = 2
                    elif case.request.lane_policy == 4:
                        trace_words[4] = 3
                    else:
                        trace_words[4] = 1 if index % 2 == 0 else 2
                    trace_words[5] = 1
                    trace_words[6] = 1
                    trace_words[8] = index * 10 + 1
                    trace_words[10] = index * 10 + 2
                    struct.pack_into("<16I", traces, index * 64, *trace_words)
                (bundle.directory / f"{prefix}_trace_result.bin").write_bytes(traces)
            checkpoint = bundle.functional_checkpoint
            assert checkpoint is not None
            checkpoint_words = list(struct.unpack("<64I", checkpoint.request.pack()))
            checkpoint_words[3] = stage.P7_DESCRIPTOR_COMPLETE
            checkpoint_words[18] = len(checkpoint.request.data)
            checkpoint_words[19] = checkpoint.trace_capacity
            checkpoint_words[20] = checkpoint.trace_capacity
            checkpoint_words[21] = zlib.crc32(checkpoint.request.data) & 0xFFFFFFFF
            checkpoint_words[22] = checkpoint.trace_capacity
            checkpoint_words[32:40] = checkpoint_words[24:32]
            checkpoint_words[40:48] = checkpoint_words[24:32]
            checkpoint_words[55] = (checkpoint.trace_capacity + 1) // 2
            checkpoint_words[56] = checkpoint.trace_capacity // 2
            checkpoint_words[58] = 9000
            checkpoint_words[60] = 9100
            checkpoint_words[63] = 49
            checkpoint_prefix = "functional_checkpoint_4k"
            (bundle.directory / f"{checkpoint_prefix}_descriptor_result.bin").write_bytes(
                struct.pack("<64I", *checkpoint_words)
            )
            (bundle.directory / f"{checkpoint_prefix}_output_result.bin").write_bytes(checkpoint.request.data)
            checkpoint_trace = bytearray(checkpoint.trace_capacity * 64)
            for index in range(checkpoint.trace_capacity):
                trace_words = [0] * 16
                trace_words[0] = stage.P7_TRACE_MAGIC
                trace_words[1] = checkpoint.request.session_epoch
                trace_words[2] = checkpoint.request.object_id
                trace_words[3] = (checkpoint.trace_capacity << 16) | index
                trace_words[4] = 1 if index % 2 == 0 else 2
                trace_words[5] = 1
                trace_words[6] = 1
                trace_words[8] = index * 10 + 1
                trace_words[10] = index * 10 + 2
                struct.pack_into("<16I", checkpoint_trace, index * 64, *trace_words)
            (bundle.directory / f"{checkpoint_prefix}_trace_result.bin").write_bytes(checkpoint_trace)
            mailbox = bytearray(
                stage.pack_mailbox(
                    control_command=stage.P7_CONTROL_SHUTDOWN,
                    max_runtime_seconds=900,
                    calibration_window_seconds=0,
                    sample_interval_seconds=10,
                )
            )
            struct.pack_into("<I", mailbox, 8, 4)
            struct.pack_into("<I", mailbox, 18 * 4, 0)
            struct.pack_into("<I", mailbox, 9 * 4, len(bundle.cases) + len(bundle.boundary_cases) + 1)
            total_fragments = sum(case.trace_capacity for case in bundle.cases + bundle.boundary_cases) + checkpoint.trace_capacity
            total_bytes = sum(len(case.request.data) for case in bundle.cases + bundle.boundary_cases) + len(checkpoint.request.data)
            struct.pack_into("<I", mailbox, 11 * 4, total_fragments)
            struct.pack_into("<I", mailbox, 12 * 4, total_bytes & 0xFFFFFFFF)
            struct.pack_into("<I", mailbox, 13 * 4, total_bytes >> 32)
            struct.pack_into("<I", mailbox, 22 * 4, 1)
            struct.pack_into("<I", mailbox, 23 * 4, len(bundle.cases) + len(bundle.boundary_cases) + 1)
            struct.pack_into("<I", mailbox, 34 * 4, 2)
            (bundle.directory / "mailbox_final.bin").write_bytes(mailbox)
            result = stage.postprocess_bundle(
                bundle,
                "functional",
                "P7_FUNCTIONAL_LARGE_POLICY_MATRIX_COMPLETE=1\n"
                "P7_FUNCTIONAL_BOUNDARY_MATRIX_COMPLETE=1\n"
                "P7_FUNCTIONAL_BOUNDARY_BATCHES=6\n"
                "P7_FUNCTIONAL_BOUNDARY_CASES=48\n"
                "P7_FUNCTIONAL_CHECKPOINT_4K_COMPLETE=1\n"
                "P7_FUNCTIONAL_EXECUTION_ORDER=BOUNDARY48_THEN_4K_THEN_64K4_THEN_1M4\n",
            )
        self.assertTrue(result["passed"], result["failures"])

    def test_nonzero_raw_exit_can_never_be_promoted_by_pass_markers(self) -> None:
        raw = "\n".join(
            [
                "P7_PS_STAGE_RESULT=PASS",
                "P7_PS_CANDIDATE_PROGRAMMED=1",
                "P7_PS_ELF_DOWNLOADED=1",
                "P7_PS_MODE=functional",
                "P7_HW_TARGET=target",
                "P7_HW_PART=part",
            ]
        )
        passed, failures = stage.evaluate_ps_process(
            125,
            "P7_PS_STAGE_RESULT=PASS\n",
            raw,
            mode="functional",
            target="target",
            part="part",
        )
        self.assertFalse(passed)
        self.assertTrue(any("nonzero exit code" in item for item in failures))

    def test_ps_result_binds_canonical_part_vivado_identity_and_xsdb_idcode(self) -> None:
        raw_lines = [
            "P7_PS_STAGE_RESULT=PASS",
            "P7_PS_CANDIDATE_PROGRAMMED=1",
            "P7_PS_ELF_DOWNLOADED=1",
            "P7_PS_MODE=functional",
            "P7_HW_TARGET=target",
            f"P7_HW_PART={stage.CANONICAL_FULL_PART}",
            f"P7_HW_CANONICAL_PART={stage.CANONICAL_FULL_PART}",
            f"P7_HW_LIVE_PART={stage.CANONICAL_LIVE_PART}",
            f"P7_HW_LIVE_DEVICE={stage.CANONICAL_LIVE_DEVICE}",
            f"P7_HW_LIVE_IDCODE={stage.CANONICAL_LIVE_IDCODE_BINARY}",
            "P7_XSDB_LIVE_DEVICE_MATCH=1",
            f"P7_XSDB_LIVE_DEVICE={stage.CANONICAL_LIVE_PART}",
            "P7_XSDB_LIVE_BOARD_ID=board",
            f"P7_XSDB_LIVE_IDCODE=0x{stage.CANONICAL_LIVE_IDCODE_HEX}",
            f"P7_XSDB_PREFLIGHT_IDCODE={stage.CANONICAL_LIVE_IDCODE_BINARY}",
            "P7_XSDB_TARGET_SELECTION=EXACT_CABLE_DEVICE_IDCODE_AND_UNIQUE_NODE_IDS",
        ]
        passed, failures = stage.evaluate_ps_process(
            0,
            "P7_PS_STAGE_RESULT=PASS\n",
            "\n".join(raw_lines),
            mode="functional",
            target="target",
            part=stage.CANONICAL_FULL_PART,
            board_id="board",
        )
        self.assertTrue(passed, failures)
        for key, replacement in (
            ("P7_HW_LIVE_PART", "xc7z020"),
            ("P7_XSDB_LIVE_DEVICE", "xc7z020"),
            ("P7_XSDB_LIVE_IDCODE", "0x03722093"),
        ):
            mutated = [
                f"{key}={replacement}" if line.startswith(key + "=") else line
                for line in raw_lines
            ]
            rejected, identity_failures = stage.evaluate_ps_process(
                0,
                "P7_PS_STAGE_RESULT=PASS\n",
                "\n".join(mutated),
                mode="functional",
                target="target",
                part=stage.CANONICAL_FULL_PART,
                board_id="board",
            )
            self.assertFalse(rejected)
            self.assertTrue(identity_failures)

    def test_core_readiness_attestation_is_hash_and_source_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "readiness.json"
            sources = {}
            for source in stage.CORE_READINESS_SOURCES:
                sources[source] = sha256(ROOT / source)
            payload = {
                "schema": "rf-comm-p7-ps-core-hardware-readiness-v1",
                "P7_PS_CORE_HARDWARE_READINESS": "PASS",
                "hardware_actions_executed": False,
                "checks": {key: True for key in stage.CORE_READINESS_CHECKS},
                "sources": sources,
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            args = stage.build_parser().parse_args(
                [
                    "--core-readiness-attestation",
                    str(path),
                    "--core-readiness-attestation-sha256",
                    sha256(path),
                ]
            )
            with mock.patch.object(stage, "KNOWN_UNSAFE_CORE_FINGERPRINT", "0" * 64):
                report = stage.validate_core_readiness(args)
            self.assertEqual("PASS", report["status"])
            self.assertEqual([], report["errors"])
            payload["checks"][stage.CORE_READINESS_CHECKS[0]] = False
            path.write_text(json.dumps(payload), encoding="utf-8")
            args.core_readiness_attestation_sha256 = sha256(path)
            with mock.patch.object(stage, "KNOWN_UNSAFE_CORE_FINGERPRINT", "0" * 64):
                blocked = stage.validate_core_readiness(args)
        self.assertEqual("BLOCKED", blocked["status"])
        self.assertTrue(any(stage.CORE_READINESS_CHECKS[0] in item for item in blocked["errors"]))

    def test_explicitly_denylisted_core_snapshot_is_unconditionally_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "readiness.json"
            payload = {
                "schema": "rf-comm-p7-ps-core-hardware-readiness-v1",
                "P7_PS_CORE_HARDWARE_READINESS": "PASS",
                "hardware_actions_executed": False,
                "checks": {key: True for key in stage.CORE_READINESS_CHECKS},
                "sources": {source: sha256(ROOT / source) for source in stage.CORE_READINESS_SOURCES},
            }
            path.write_text(json.dumps(payload), encoding="utf-8")
            args = stage.build_parser().parse_args(
                [
                    "--core-readiness-attestation",
                    str(path),
                    "--core-readiness-attestation-sha256",
                    sha256(path),
                ]
            )
            current = stage.validate_core_readiness(args)
            self.assertEqual("PASS", current["status"])
            with mock.patch.object(stage, "KNOWN_UNSAFE_CORE_FINGERPRINT", current["source_fingerprint"]):
                report = stage.validate_core_readiness(args)
        self.assertEqual(current["source_fingerprint"], report["source_fingerprint"])
        self.assertEqual("BLOCKED", report["status"])
        self.assertTrue(any("unresolved P0" in item for item in report["errors"]))

    def test_lane1_promotion_commit_must_exist_and_be_authorized_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            active_path = root / "ACTIVE_PROFILE.json"
            promotion_path = root / "promotion.json"
            source_path = root / "p5.json"
            source_path.write_text("{}\n", encoding="utf-8")
            promotion_commit = "1" * 40
            authorized_commit = "2" * 40
            active_path.write_text(
                json.dumps(
                    {
                        "default_no_hardware": True,
                        "lane1_reliable_enabled": True,
                        "lane1_reliability_promotion": {
                            "status": "PASS",
                            "source_commit": promotion_commit,
                            "evidence": str(promotion_path),
                            "requires_fresh_p7_regression_before_acceptance": True,
                        },
                    }
                ),
                encoding="utf-8",
            )
            promotion_path.write_text(
                json.dumps(
                    {
                        "P7_LANE1_RELIABILITY_PROMOTION_GATE": "PASS",
                        "source_commit": promotion_commit,
                        "hardware_actions_executed": False,
                        "source_evidence_contains_hardware_actions": True,
                        "checks": {"p5_p6": True},
                        "sources": {
                            "p5": {"path": str(source_path), "sha256": sha256(source_path)}
                        },
                    }
                ),
                encoding="utf-8",
            )
            args = stage.build_parser().parse_args(
                [
                    "--active-profile",
                    str(active_path),
                    "--active-profile-sha256",
                    sha256(active_path),
                    "--lane1-promotion-summary",
                    str(promotion_path),
                    "--lane1-promotion-summary-sha256",
                    sha256(promotion_path),
                    "--source-commit",
                    authorized_commit,
                ]
            )
            ok = mock.Mock(returncode=0)
            unknown = mock.Mock(returncode=128)
            nonancestor = mock.Mock(returncode=1)
            with mock.patch.object(stage, "ACTIVE_PROFILE_DEFAULT", active_path), mock.patch.object(
                stage, "LANE1_PROMOTION_DEFAULT", promotion_path
            ):
                with mock.patch.object(stage.subprocess, "run", side_effect=[ok, ok]):
                    self.assertEqual([], stage._active_profile_errors(args))
                with mock.patch.object(stage.subprocess, "run", return_value=unknown):
                    unknown_errors = stage._active_profile_errors(args)
                with mock.patch.object(stage.subprocess, "run", side_effect=[ok, nonancestor]):
                    ancestor_errors = stage._active_profile_errors(args)
        self.assertTrue(any("unknown" in item for item in unknown_errors))
        self.assertTrue(any("not an ancestor" in item for item in ancestor_errors))

    def test_ps_timer_frequency_is_bound_in_argv_and_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "input.bin"
            input_path.write_bytes(b"timer-contract")
            bundle = stage.build_stage_bundle(
                bundle_dir=root / "bundle",
                mode="functional",
                input_path=input_path,
                max_runtime_sec=900,
                calibration_sec=0,
                acceptance_sec=0,
                sample_interval_sec=10,
                idle_margin_sec=10,
                stationary_object_bytes=64 * 1024,
            )
            args = stage.build_parser().parse_args([])
            args.xsdb_path = str(root / "xsdb.bat")
            args.authorization_file = str(root / "authorization.txt")
            args.bitstream = str(root / "candidate.bit")
            args.elf = str(root / "runtime.elf")
            args.ps7_init = str(root / "ps7_init.tcl")
            args.shutdown_bitstream = str(root / "shutdown.bit")
            args.max_runtime_sec = 900
            args.mode = "functional"
            args.idle_deadline_margin_sec = 10
            command = stage.build_ps_command(args, bundle, root / "preflight.txt", root / "raw.log")
            self.assertEqual(20, len(command))
            self.assertEqual(str(stage.P7_COUNTS_PER_SECOND), command[-1])

            Path(args.authorization_file).write_text("placeholder\n", encoding="utf-8")
            fields = {
                "PS7_INIT_PATH": args.ps7_init,
                "PS7_INIT_SHA256": args.ps7_init_sha256,
                "P6_PS_BUILD_SUMMARY_PATH": args.p6_build_summary,
                "P6_PS_BUILD_SUMMARY_SHA256": args.p6_build_summary_sha256,
                "P7_PS_BUILD_SUMMARY_PATH": args.p7_build_summary,
                "P7_PS_BUILD_SUMMARY_SHA256": args.p7_build_summary_sha256,
                "P7_INPUT_PATH": args.input_file,
                "P7_INPUT_SHA256": args.input_sha256,
                "P7_PS_MODE": args.mode,
                "P7_PS_CORE_READINESS": "PASS",
                "P7_PS_CORE_READINESS_PATH": args.core_readiness_attestation,
                "P7_PS_CORE_READINESS_SHA256": args.core_readiness_attestation_sha256,
                "ACTIVE_PROFILE_PATH": args.active_profile,
                "ACTIVE_PROFILE_SHA256": args.active_profile_sha256,
                "P7_LANE1_PROMOTION_SUMMARY_PATH": args.lane1_promotion_summary,
                "P7_LANE1_PROMOTION_SUMMARY_SHA256": args.lane1_promotion_summary_sha256,
                "P7_FROZEN_SHUTDOWN_PATH": str(stage.frozen_shutdown_path(args)),
                "P7_FROZEN_SHUTDOWN_SHA256": args.shutdown_bitstream_sha256,
            }
            with mock.patch.object(stage, "parse_authorization_file", return_value=(fields, [], [])):
                missing = stage._authorization_extension_errors(args)
            self.assertTrue(any("P7_COUNTS_PER_SECOND" in item and "missing" in item for item in missing))
            fields["P7_COUNTS_PER_SECOND"] = "1"
            with mock.patch.object(stage, "parse_authorization_file", return_value=(fields, [], [])):
                mismatched = stage._authorization_extension_errors(args)
            self.assertTrue(any("P7_COUNTS_PER_SECOND" in item and "mismatch" in item for item in mismatched))
            fields["P7_COUNTS_PER_SECOND"] = str(stage.P7_COUNTS_PER_SECOND)
            with mock.patch.object(stage, "parse_authorization_file", return_value=(fields, [], [])):
                matched = stage._authorization_extension_errors(args)
            self.assertFalse(any("P7_COUNTS_PER_SECOND" in item for item in matched))

    def test_default_and_blocked_execute_paths_launch_no_hardware_process(self) -> None:
        for argv, expected_status, expected_rc in (
            (["--json-summary"], "DRY_RUN_ONLY", 0),
            (["--execute-hardware", "--json-summary"], "BLOCKED", 2),
        ):
            output = io.StringIO()
            with mock.patch.object(stage.process_support.subprocess, "Popen") as popen:
                with contextlib.redirect_stdout(output):
                    rc = stage.main(argv)
            self.assertEqual(expected_rc, rc)
            self.assertFalse(popen.called)
            self.assertIn(f'"P7_PS_APPLICATION_SAFE_STAGE": "{expected_status}"', output.getvalue())

    def test_stationary_active_watchdog_kills_before_post_safe_reap_grace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "active_watchdog_child.py"
            script.write_text(
                "import time\nprint('P7_STATIONARY_SERVICE_READY_ACTIVE=1', flush=True)\ntime.sleep(30)\n",
                encoding="utf-8",
            )
            with mock.patch.object(stage, "MAX_SERVICE_RUNTIME_SEC", 0), mock.patch.object(
                stage, "STATIONARY_ACTIVE_WATCHDOG_TOLERANCE_SEC", 0.2
            ), mock.patch.object(stage, "STATIONARY_SETUP_WATCHDOG_SEC", 2):
                result = stage._atomic_process(
                    name="watchdog_test",
                    command=[sys.executable, str(script)],
                    evidence_dir=root,
                    timeout_sec=999,
                    abort_file=root / "ABORT_NOW.txt",
                    watch_abort=True,
                    stationary_active_watchdog=True,
                )
        self.assertEqual(124, result.returncode)
        self.assertTrue(result.timed_out)
        self.assertTrue(result.process_tree_terminated)
        self.assertTrue(result.process_tree_reaped)
        self.assertEqual("stationary_active_window_exceeded", result.watchdog_reason)
        self.assertEqual([sys.executable, str(script)], result.argv)
        self.assertNotEqual("UNKNOWN", result.started_at_utc)
        self.assertNotEqual("UNKNOWN", result.ended_at_utc)

    def test_stationary_terminal_observation_switches_to_post_safe_reap_grace(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            script = root / "terminal_observed_child.py"
            script.write_text(
                "import time\n"
                "print('P7_STATIONARY_SERVICE_READY_ACTIVE=1', flush=True)\n"
                "print('P7_STATIONARY_SERVICE_TERMINAL_OBSERVED=1', flush=True)\n"
                "time.sleep(30)\n",
                encoding="utf-8",
            )
            with mock.patch.object(stage, "MAX_SERVICE_RUNTIME_SEC", 0), mock.patch.object(
                stage, "STATIONARY_ACTIVE_WATCHDOG_TOLERANCE_SEC", 0.2
            ), mock.patch.object(stage, "POST_SAFE_REAP_GRACE_SEC", 0.3), mock.patch.object(
                stage, "STATIONARY_SETUP_WATCHDOG_SEC", 2
            ):
                result = stage._atomic_process(
                    name="terminal_observed_watchdog_test",
                    command=[sys.executable, str(script)],
                    evidence_dir=root,
                    timeout_sec=999,
                    abort_file=root / "ABORT_NOW.txt",
                    watch_abort=True,
                    stationary_active_watchdog=True,
                )
        self.assertEqual(124, result.returncode)
        self.assertTrue(result.timed_out)
        self.assertTrue(result.process_tree_reaped)
        self.assertEqual("post_safe_evidence_reap_timeout", result.watchdog_reason)

    def test_stationary_post_launch_read_exception_reaps_child(self) -> None:
        class FakeProcess:
            pid = 4545
            returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.returncode = -9
                return -9

        fake = FakeProcess()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(
                stage.process_support, "launch_contained_process", return_value=fake
            ), mock.patch.object(
                stage.Path, "read_text", side_effect=OSError("live stdout read failed")
            ), mock.patch.object(
                stage.process_support,
                "terminate_process_tree",
                side_effect=lambda process: setattr(process, "returncode", -9) is None,
            ) as terminate, mock.patch.object(
                stage.process_support, "verify_process_tree_reaped", return_value=True
            ):
                result = stage._run_stationary_watchdog_process(
                    name="stationary_exception_reap",
                    command=["fixed.exe", "fixed"],
                    stdout_path=root / "stdout.log",
                    stderr_path=root / "stderr.log",
                    abort_file=root / "ABORT_NOW.txt",
                    watch_abort=True,
                )
        self.assertEqual(127, result.returncode)
        self.assertTrue(result.process_tree_reaped)
        terminate.assert_called_once_with(fake)

    def test_atomic_writer_replaces_without_partial_residue(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            stage.atomic_write_json(path, {"value": 1})
            stage.atomic_write_json(path, {"value": 2})
            self.assertEqual({"value": 2}, json.loads(path.read_text(encoding="utf-8")))
            self.assertFalse(list(path.parent.glob("*.partial")))

    def test_post_shutdown_raw_evidence_manifest_hashes_every_committed_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "bundle").mkdir()
            (root / "raw.log").write_text("raw\n", encoding="utf-8")
            (root / "bundle" / "descriptor_result_0.bin").write_bytes(b"descriptor")
            manifest_path = stage.write_evidence_sha256_manifest(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            records = {item["path"]: item for item in manifest["records"]}
            self.assertEqual({"raw.log", "bundle/descriptor_result_0.bin"}, set(records))
            self.assertEqual(sha256(root / "raw.log"), records["raw.log"]["sha256"])
            (root / "orphan.partial").write_bytes(b"partial")
            updated_path = stage.write_evidence_sha256_manifest(root)
            updated = json.loads(updated_path.read_text(encoding="utf-8"))
            self.assertEqual(1, updated["partial_file_count"])
            self.assertEqual(["orphan.partial"], updated["partial_files"])

    def test_shutdown_image_is_frozen_and_restorable_after_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "canonical.bit"
            original = b"verified-shutdown-image"
            source.write_bytes(original)
            args = stage.build_parser().parse_args(
                ["--shutdown-bitstream", str(source), "--shutdown-bitstream-sha256", sha256(source)]
            )
            with mock.patch.object(stage, "FROZEN_SHUTDOWN_DIR", root / "frozen"):
                frozen, retained = stage.freeze_shutdown_bit(args)
                source.write_bytes(b"mutated-canonical")
                frozen.write_bytes(b"mutated-frozen")
                stage.restore_frozen_shutdown(frozen, retained, args.shutdown_bitstream_sha256)
                self.assertEqual(original, frozen.read_bytes())
                self.assertIn(args.shutdown_bitstream_sha256, frozen.name)

    def test_bundle_integrity_recheck_rejects_post_build_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "input.bin"
            input_path.write_bytes(b"bundle-integrity")
            bundle = stage.build_stage_bundle(
                bundle_dir=root / "bundle",
                mode="functional",
                input_path=input_path,
                max_runtime_sec=900,
                calibration_sec=0,
                acceptance_sec=0,
                sample_interval_sec=10,
                idle_margin_sec=10,
                stationary_object_bytes=64 * 1024,
            )
            stage.verify_bundle_integrity(bundle)
            target = bundle.directory / "input_0.bin"
            target.write_bytes(target.read_bytes() + b"tamper")
            with self.assertRaisesRegex(RuntimeError, "bundle.*integrity"):
                stage.verify_bundle_integrity(bundle)

    def test_queue_overflow_candidate_identity_tamper_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_path = root / "input.bin"
            input_path.write_bytes(b"overflow-candidate")
            bundle = stage.build_stage_bundle(
                bundle_dir=root / "bundle",
                mode="queue",
                input_path=input_path,
                max_runtime_sec=900,
                calibration_sec=0,
                acceptance_sec=0,
                sample_interval_sec=10,
                idle_margin_sec=10,
                stationary_object_bytes=64 * 1024,
            )
            candidate = bundle.directory / "queue_overflow_candidate_descriptor_free.bin"
            raw = bytearray(candidate.read_bytes())
            struct.pack_into("<I", raw, 20, 10)
            candidate.write_bytes(raw)
            with self.assertRaisesRegex(RuntimeError, "overflow candidate"):
                stage.verify_bundle_integrity(bundle)

    def test_completed_all_zero_trace_is_rejected(self) -> None:
        case = stage.build_cases("functional", b"trace", 64 * 1024)[0]
        with tempfile.TemporaryDirectory() as temp:
            trace_path = Path(temp) / "trace.bin"
            trace_path.write_bytes(b"\x00" * (case.trace_capacity * 64))
            traces, failures = stage._parse_trace(trace_path, case)
        self.assertEqual([], traces)
        self.assertTrue(any("sparse/all-zero" in item for item in failures))

    def test_stationary_final_trace_and_descriptor_reject_old_object_identity(self) -> None:
        case = stage.build_cases("stationary", b"stationary-identity", 64 * 1024)[5]
        effective = stage.replace(case, request=stage.replace(case.request, object_id=1005))
        with tempfile.TemporaryDirectory() as temp:
            trace_path = Path(temp) / "trace.bin"
            raw = bytearray(case.trace_capacity * 64)
            for index in range(case.trace_capacity):
                words = [0] * 16
                words[0] = stage.P7_TRACE_MAGIC
                words[1] = case.request.session_epoch
                words[2] = case.request.object_id
                words[3] = (case.trace_capacity << 16) | index
                words[4] = 1 if index % 2 == 0 else 2
                words[5] = 1
                words[6] = 1
                words[8] = 2 * index + 1
                words[10] = 2 * index + 2
                struct.pack_into("<16I", raw, index * 64, *words)
            trace_path.write_bytes(raw)
            _, trace_failures = stage._parse_trace(trace_path, effective)
        self.assertTrue(any("object mismatch" in item for item in trace_failures))
        stale_descriptor = case.request.pack()
        validation = stage.validate_completed(effective.request, stale_descriptor, effective.request.data)
        self.assertTrue(any("object_id" in item for item in validation["failures"]))

    def test_stationary_terminal_bundles_drive_complete_metrics_and_count_fallback_events_once(self) -> None:
        data = bytes(index & 0xFF for index in range(646))
        case = stage._make_case(
            slot=0,
            name="stationary_metric_fixture",
            data=data,
            session_epoch=0x50370001,
            object_id=1001,
            lane_policy=3,
            unavailable_lane_mask=1,
            unavailable_after_fragment=0,
        )
        self.assertEqual(4, case.trace_capacity)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bundle = stage.StageBundle(
                directory=root,
                plan_path=root / "plan.txt",
                plan_sha256="0" * 64,
                manifest_path=root / "manifest.json",
                manifest_sha256="1" * 64,
                cases=[case],
                boundary_cases=[],
                functional_checkpoint=None,
                queue_overflow_candidate=None,
                scheduling_cutoff_sec=1740,
            )
            descriptor_words = list(struct.unpack("<64I", case.request.pack()))
            descriptor_words[3] = stage.P7_DESCRIPTOR_COMPLETE
            descriptor_words[17] = 0
            descriptor_words[18] = len(data)
            descriptor_words[19] = case.trace_capacity
            descriptor_words[20] = case.trace_capacity
            descriptor_words[21] = zlib.crc32(data) & 0xFFFFFFFF
            descriptor_words[22] = case.trace_capacity
            descriptor_words[23] = 1  # one newly unavailable lane, not two redirected fragments
            descriptor_words[32:40] = descriptor_words[24:32]
            descriptor_words[40:48] = descriptor_words[24:32]
            descriptor_words[53] = 4
            descriptor_words[56] = case.trace_capacity
            descriptor_words[58] = 90
            descriptor_words[60] = 150
            descriptor_words[63] = 1
            descriptor_raw = struct.pack("<64I", *descriptor_words)
            (root / "stationary_00000001_descriptor_result.bin").write_bytes(descriptor_raw)
            (root / "stationary_00000001_output_result.bin").write_bytes(data)
            trace_raw = bytearray(case.trace_capacity * 64)
            for index in range(case.trace_capacity):
                words = [0] * 16
                words[0] = stage.P7_TRACE_MAGIC
                words[1] = case.request.session_epoch
                words[2] = case.request.object_id
                words[3] = (case.trace_capacity << 16) | index
                words[4] = 2
                words[5] = 1
                words[6] = 1
                words[8] = 100 + 10 * index
                words[10] = 105 + 10 * index
                struct.pack_into("<16I", trace_raw, index * 64, *words)
            (root / "stationary_00000001_trace_result.bin").write_bytes(trace_raw)
            output_sha = hashlib.sha256(data).hexdigest()
            item = {
                "sequence": 1,
                "slot": 0,
                "generation": 0,
                "session_epoch": case.request.session_epoch,
                "object_id": case.request.object_id,
                "status": stage.P7_DESCRIPTOR_COMPLETE,
                "error_code": 0,
                "bytes_completed": len(data),
                "fragments_completed": case.trace_capacity,
                "fragments_total": case.trace_capacity,
                "fragment_attempts": case.trace_capacity,
                "fallback_count": 1,
                "output_sha256": output_sha,
                "p6_retry_count": 0,
                "p6_retry_exhausted": 0,
                "p6_tx_fail": 0,
                "p6_crc_bad": 0,
                "p6_payload_mismatch": 0,
                "max_txd_high_cycles": 4,
                "duty_violations": 0,
                "lane0_fragments": 0,
                "lane1_fragments": case.trace_capacity,
                "replicated_fragments": 0,
                "start_ticks": 90,
                "end_ticks": 150,
                "completion_sequence": 1,
            }
            raw_text = "\n".join(
                [
                    "P7_STATIONARY_TERMINAL_BUNDLE_00000001_CAPTURED=1",
                    f"P7_HOST_TO_PS_INPUT_BYTES={len(data)}",
                    "P7_HOST_TO_PS_INPUT_DURATION_MS=2",
                    f"P7_HOST_TO_PS_INPUT_BYTES_PER_SEC={len(data) * 500}",
                    f"P7_HOST_TO_PS_INPUT_BPS={len(data) * 4000}",
                ]
            )
            trace_summary, fragment_ticks, trace_failures = stage._stationary_trace_evidence(
                bundle, [item], raw_text
            )
            self.assertEqual([], trace_failures)
            self.assertTrue(trace_summary["passed"])
            self.assertEqual(2, trace_summary["records"][0]["redirected_fragments"])
            self.assertEqual(1, trace_summary["records"][0]["fallback_count"])
            mailbox = {
                "objects_requested": 1,
                "objects_completed": 1,
                "objects_failed": 0,
                "queue_high_watermark": 1,
                "backpressure_events": 0,
                "runtime_elapsed_ticks": 1800 * stage.P7_COUNTS_PER_SECOND,
                "shutdown_result": 0,
            }
            metrics, metric_failures = stage._stationary_application_metrics(
                bundle, [item], mailbox, raw_text, trace_summary, fragment_ticks
            )
        self.assertEqual([], metric_failures)
        self.assertTrue(metrics["validated"])
        self.assertEqual(len(data) * 500, metrics["host_to_ps_bytes_per_sec"])
        self.assertEqual(1, metrics["fallback_lane0_to_lane1"])
        self.assertEqual(4, metrics["fragment_latency_sample_count"])

    def test_xsdb_tcl_is_guarded_and_treats_plan_as_data(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_ps_application_execute.tcl").read_text(encoding="utf-8")
        lower = tcl.lower()
        self.assertLess(tcl.index("RF_COMM_HW_AUTH"), tcl.index("connect -url"))
        self.assertLess(tcl.index("P7_HW_PREFLIGHT_RESULT"), tcl.index("connect -url"))
        self.assertNotIn("source $plan", lower)
        self.assertNotIn("eval $", lower)
        self.assertNotIn("exec $", lower)
        self.assertIn("source $ps7_init_file", tcl)
        self.assertIn("dow -data", tcl)
        self.assertIn("P7_CALIBRATION_WINDOW_COMPLETE=1", tcl)
        self.assertIn("P7_ACCEPTANCE_WINDOW_COMPLETE=1", tcl)
        self.assertIn("descriptor_free_${slot}.bin", tcl)
        self.assertIn("mwr [expr {$descriptor_address + 0x0C}] 1", tcl)
        self.assertIn("status changed across terminal snapshot", tcl)
        self.assertIn("mrd -size b -bin -file", tcl)
        self.assertIn("address does not match fixed slot geometry", tcl)
        self.assertIn("bundle case file size does not match", tcl)
        self.assertIn("P7_XSDB_LIVE_DEVICE_MATCH=1", tcl)
        self.assertGreater(tcl.index("P7_XSDB_LIVE_DEVICE_MATCH=1"), tcl.index("connect -url"))
        self.assertIn("jtag targets -target-properties", tcl)
        self.assertIn("proc p7_unique_targets_by_id", tcl)
        self.assertIn("P7_XSDB_APU_DISTINCT_TARGET_COUNT=", tcl)
        self.assertIn("P7_XSDB_TARGET_SELECTION=EXACT_CABLE_DEVICE_IDCODE_AND_UNIQUE_NODE_IDS", tcl)
        self.assertIn('set p7_canonical_part "xc7z010clg400-1"', tcl)
        self.assertIn('set p7_live_part "xc7z010"', tcl)
        self.assertIn('set p7_live_device "xc7z010_1"', tcl)
        self.assertIn('set p7_live_idcode "13722093"', tcl)
        self.assertIn("P7_HW_CANONICAL_PART=", tcl)
        self.assertIn("P7_HW_LIVE_PART=", tcl)
        self.assertIn("targets [dict get $fpga_target target_id]", tcl)
        self.assertIn("targets [dict get $cpu_target target_id]", tcl)
        self.assertNotIn("targets -set -filter", tcl)
        self.assertIn(
            "p7_wait_service_ready $abort_file $result_handle P7_PS_SERVICE\n"
            "  if {$mode eq \"stationary\"}",
            tcl,
        )
        boundary_position = tcl.index("for {set batch 0} {$batch < 6} {incr batch}")
        checkpoint_position = tcl.index(
            "dow -data [file join $bundle_dir functional_checkpoint_4k_input.bin]",
            boundary_position,
        )
        small_position = tcl.index("foreach source_slot {4 5 6 7}", checkpoint_position)
        large_position = tcl.index("foreach source_slot {0 1 2 3}", small_position)
        self.assertLess(boundary_position, checkpoint_position)
        self.assertLess(checkpoint_position, small_position)
        self.assertLess(small_position, large_position)
        self.assertIn("P7_FUNCTIONAL_EXECUTION_ORDER=BOUNDARY48_THEN_4K_THEN_64K4_THEN_1M4", tcl)
        self.assertIn('P7_STATIONARY_WALL_SECONDS=%.3f" $stationary_wall_seconds', tcl)
        self.assertIn('P7_STATIONARY_DRAIN_COMPLETE_ELAPSED=%.3f" $drain_elapsed_sec', tcl)
        self.assertIn("$stationary_wall_seconds < 1800.0 || $stationary_wall_seconds > 1801.5", tcl)
        self.assertIn("P7_STATIONARY_PRIMARY_TIME_SOURCE=PS_RUNTIME_ELAPSED_TICKS", tcl)
        self.assertIn("P7_STATIONARY_HOST_TIME_ROLE=INDEPENDENT_WATCHDOG_AND_INPUT_PRELOAD", tcl)
        self.assertIn("P7_STATIONARY_HOST_WATCHDOG_CORROBORATION=PASS", tcl)
        self.assertIn("$service_start_ms + 1000 * $max_runtime_sec + 2000", tcl)
        self.assertNotIn("$max_runtime_sec + 30", tcl)
        self.assertIn("P7_SAMPLE_00060_SAFE_TERMINAL_STATE=1", tcl)
        self.assertIn("P7_STATIONARY_SERVICE_TERMINAL_OBSERVED=1", tcl)
        self.assertIn("proc p7_stationary_chunked_dump", tcl)
        self.assertIn("set chunk_limit 4096", tcl)
        self.assertIn("$terminal_prefix $slot $result_handle $abort_file", tcl)
        self.assertIn('"" -1 $result_handle $abort_file', tcl)
        self.assertIn("P7_SAMPLE_SEQUENCE_WRITER=HOST_POST_TERMINAL", tcl)
        self.assertIn("mwr 0x00020084 $sample_index", tcl)
        self.assertIn("proc p7_publish_source_descriptor_to_target", tcl)
        self.assertIn("p7_publish_source_descriptor_to_target $bundle_dir $slot 0", tcl)
        self.assertIn("p7_publish_source_descriptor_to_target $bundle_dir 1 0", tcl)
        self.assertIn("p7_publish_source_descriptor_to_target $bundle_dir 2 1", tcl)
        self.assertNotIn("p7_publish_phase_descriptors $bundle_dir [list $slot]", tcl)
        self.assertIn("proc p7_queue_admit_candidate", tcl)
        self.assertIn("P7_QUEUE_OVERFLOW_ADMISSION=FULL", tcl)
        self.assertIn("P7_QUEUE_OVERFLOW_DDR_WRITE=0", tcl)
        self.assertIn("queue_overflow_ring_before.bin", tcl)
        self.assertIn("queue_overflow_ring_after.bin", tcl)
        self.assertNotIn(r"string map {\ /}", tcl)
        self.assertEqual(3, tcl.count('string map [list "\\\\" "/"]'))
        self.assertEqual(2, tcl.count("P7_PS_STAGE_ERROR=[p7_sanitize_error $error_text]"))
        self.assertNotIn("P7_PS_STAGE_ERROR=[string map", tcl)
        wrapper = MODULE_PATH.read_text(encoding="utf-8")
        self.assertEqual(
            2,
            wrapper.count(
                '"programming_attempted": process_support.shutdown_programming_attempted('
            ),
        )
        self.assertGreaterEqual(wrapper.count('"programming_attempted": False'), 3)
        self.assertEqual(2, wrapper.count("expected_shutdown_bit=frozen_shutdown"))
        self.assertEqual(2, wrapper.count('"result_file": str(before_final)'))
        self.assertEqual(3, wrapper.count('"result_file": str(after_final)'))

    def test_xsdb_tcl_path_mapping_and_error_sanitizer_execute_in_tcl(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_ps_application_execute.tcl").read_text(encoding="utf-8")
        interp = tcl_interpreter()
        self.assertEqual(1, int(interp.call("info", "complete", tcl)))
        prefix = tcl[: tcl.index("proc p7_require_path")]
        interp.eval(prefix)
        normalized = str(interp.call("p7_normal_path", r"C:\Temp\P7 Runtime.elf"))
        self.assertNotIn("\\", normalized)
        self.assertTrue(normalized.endswith("c:/temp/p7 runtime.elf"), normalized)
        original = "ORIGINAL_PS_FAILURE first line\nsecond line\rthird line"
        self.assertEqual(
            "ORIGINAL_PS_FAILURE first line second line third line",
            str(interp.call("p7_sanitize_error", original)),
        )
        with self.assertRaises(tkinter.TclError):
            interp.eval(r"string map {\ /} {C:\Temp\broken.elf}")

    def test_xsdb_target_uniqueness_is_by_numeric_target_id_not_property_row_count(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_ps_application_execute.tcl").read_text(encoding="utf-8")
        interp = tcl_interpreter()
        prefix = tcl[: tcl.index("proc p7_read32")]
        interp.eval(prefix)
        count = int(
            interp.eval(
                "llength [p7_unique_targets_by_id [list "
                "[dict create target_id 7 name APU] "
                "[dict create target_id 7 name APU] "
                "[dict create target_id 8 name APU]]]"
            )
        )
        self.assertEqual(2, count)
        with self.assertRaises(tkinter.TclError):
            interp.eval("p7_unique_targets_by_id [list [dict create name APU]]")

    def test_xsdb_child_targets_bind_to_the_proven_single_device_connection(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_ps_application_execute.tcl").read_text(encoding="utf-8")
        interp = tcl_interpreter()
        interp.eval(tcl[: tcl.index("proc p7_read32")])
        interp.eval(
            "set rows [list "
            "[dict create target_id 1 name APU] "
            "[dict create target_id 2 name {ARM Cortex-A9 MPCore #0}] "
            "[dict create target_id 3 name xc7z010 jtag_device_id 44 jtag_cable_serial SERIAL] "
            "[dict create target_id 4 name xc7z010 jtag_device_id 45 jtag_cable_serial OTHER]]"
        )
        interp.eval("set sets [p7_classify_debug_targets $rows 44 SERIAL xc7z010]")
        self.assertEqual("1", interp.eval("llength [dict get $sets apu]"))
        self.assertEqual("1", interp.eval("llength [dict get $sets cpu0]"))
        self.assertEqual("1", interp.eval("llength [dict get $sets fpga]"))
        self.assertEqual("0", interp.eval("llength [dict get $sets dap]"))

    def test_functional_boundary_failure_preserves_status_error_descriptor_output_and_trace(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_ps_application_execute.tcl").read_text(encoding="utf-8")
        status = tcl.index("P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=$status")
        descriptor_capture = tcl.index("P7_FUNCTIONAL_BOUNDARY_FAILURE_DESCRIPTOR_CAPTURED=1")
        output_capture = tcl.index("P7_FUNCTIONAL_BOUNDARY_FAILURE_OUTPUT_CAPTURED=1")
        trace_capture = tcl.index("P7_FUNCTIONAL_BOUNDARY_FAILURE_TRACE_CAPTURED=1")
        snapshot_capture = tcl.index(
            "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_CAPTURED=1"
        )
        snapshot_wipe = tcl.index(
            "P7_FUNCTIONAL_BOUNDARY_FAILURE_INTEGRITY_SNAPSHOT_WIPED=1"
        )
        terminal_error = tcl.index(
            'error "P7 functional boundary case failed:', snapshot_wipe
        )
        self.assertLess(status, descriptor_capture)
        self.assertLess(descriptor_capture, output_capture)
        self.assertLess(output_capture, trace_capture)
        self.assertLess(trace_capture, snapshot_capture)
        self.assertLess(snapshot_capture, snapshot_wipe)
        self.assertLess(snapshot_wipe, terminal_error)
        self.assertIn("P7_FUNCTIONAL_BOUNDARY_FAILURE_STATUS=$status", tcl)
        self.assertIn("P7_FUNCTIONAL_BOUNDARY_FAILURE_ERROR_CODE=$error_code", tcl)
        self.assertIn("boundary_${boundary_index}_descriptor_failure.bin", tcl)
        self.assertIn("boundary_${boundary_index}_output_failure.bin", tcl)
        self.assertIn("boundary_${boundary_index}_trace_failure.bin", tcl)
        self.assertIn("boundary_${boundary_index}_integrity_snapshot_failure.bin", tcl)
        self.assertIn("boundary_${boundary_index}_integrity_snapshot_wipe_verify.bin", tcl)
        self.assertIn("p7_atomic_dump $failure_descriptor $descriptor_address 256", tcl)
        self.assertIn("p7_atomic_dump $failure_output $boundary_output($boundary_index)", tcl)
        self.assertIn("p7_atomic_dump $failure_trace $boundary_trace($boundary_index)", tcl)
        self.assertIn("$boundary_trace_capacity($boundary_index) * 64", tcl)
        self.assertIn("p7_atomic_dump $failure_snapshot $firmware_snapshot_address 320", tcl)
        self.assertIn("p7_zero_words_and_verify $firmware_snapshot_address 320", tcl)
        self.assertIn("p7_atomic_dump $failure_snapshot_wipe $firmware_snapshot_address 320", tcl)
        self.assertIn("[p7_read32 $firmware_snapshot_address] != 0x53463750", tcl)
        self.assertIn("set firmware_snapshot_address [p7_read32 0x0002009C]", tcl)
        self.assertIn("set firmware_snapshot_bytes [p7_read32 0x000200A0]", tcl)
        self.assertIn("set firmware_snapshot_status [p7_read32 0x000200A4]", tcl)
        self.assertIn("set firmware_snapshot_magic_readback [p7_read32 0x000200A8]", tcl)
        self.assertIn("set failure_snapshot_address 0x00021000", tcl)
        self.assertIn("$firmware_snapshot_status != 1", tcl)
        self.assertIn("$firmware_snapshot_address != $failure_snapshot_address", tcl)
        self.assertIn("$firmware_snapshot_bytes != 320", tcl)
        self.assertIn("$firmware_snapshot_magic_readback != 0x53463750", tcl)
        self.assertNotIn("dow -data $failure_descriptor $descriptor_address", tcl)
        self.assertNotIn("dow -data $failure_output $boundary_output($boundary_index)", tcl)
        self.assertNotIn("dow -data $failure_trace $boundary_trace($boundary_index)", tcl)

    def test_xsdb_tcl_failure_result_preserves_original_error_before_hardware(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_ps_application_execute.tcl").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_path = root / "failure.txt"
            interp = tcl_interpreter()
            install_captured_tcl_exit(interp)
            interp.setvar("env(RF_COMM_HW_AUTH)", "P7_STATIONARY_APP_LAYER_APPROVED")
            interp.setvar(
                "argv",
                (
                    str(root),
                    str(root / "missing-auth.txt"),
                    str(root / "missing-preflight.txt"),
                    str(root / "missing.bit"),
                    str(root / "missing.elf"),
                    str(root / "missing-ps7-init.tcl"),
                    str(root / "missing-bundle"),
                    str(root / "missing-plan.txt"),
                    str(result_path),
                    "localhost:3121",
                    "210512180081",
                    "xc7z010clg400-1",
                    "localhost:3121/xilinx_tcf/Digilent/210512180081",
                    "0",
                    "functional",
                    "10",
                    str(root / "missing-shutdown.bit"),
                    "333333343",
                ),
            )
            with self.assertRaises(tkinter.TclError) as raised:
                interp.eval(tcl)
            self.assertIn("__P7_CAPTURED_EXIT__42", str(raised.exception))
            self.assertEqual("42", str(interp.getvar("p7_captured_exit_code")))
            result = result_path.read_text(encoding="utf-8")
        self.assertIn("P7_PS_STAGE_RESULT=FAIL", result)
        self.assertIn("P7_PS_STAGE_ERROR=P7 service runtime must be in 1..1800 seconds", result)
        self.assertNotIn("char map list unbalanced", result)

    def test_stationary_sampling_and_requeue_cutoff_use_fresh_ps_ticks(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_ps_application_execute.tcl").read_text(encoding="utf-8")
        self.assertIn('if {[llength $argv] != 18}', tcl)
        self.assertIn('set counts_per_second [lindex $argv 17]', tcl)
        self.assertIn('$counts_per_second != 333333343', tcl)
        self.assertIn('p7_require_value $auth_text P7_COUNTS_PER_SECOND $counts_per_second', tcl)
        self.assertIn('$plan_value(COUNTS_PER_SECOND) != $counts_per_second', tcl)
        self.assertIn("proc p7_read_runtime_elapsed_ticks", tcl)
        reader = tcl[tcl.index("proc p7_read_runtime_elapsed_ticks") : tcl.index("proc p7_le32")]
        sequence_before = reader.index("set sequence_before [p7_read32 0x00020088]")
        low = reader.index("set low [p7_read32 0x00020074]")
        high = reader.index("set high [p7_read32 0x00020078]")
        sequence_after = reader.index("set sequence_after [p7_read32 0x00020088]")
        stable_check = reader.index("$sequence_before == $sequence_after")
        regression_check = reader.index("$value < $p7_last_runtime_elapsed_ticks")
        self.assertLess(sequence_before, low)
        self.assertLess(low, high)
        self.assertLess(high, sequence_after)
        self.assertLess(sequence_after, stable_check)
        self.assertLess(stable_check, regression_check)
        self.assertIn("mwr 0x0002008C $p7_runtime_elapsed_request", reader)
        self.assertIn("p7_read32 0x00020090", reader)
        self.assertIn("snapshot request was not acknowledged", reader)
        self.assertIn("set final_elapsed_ticks [p7_read_runtime_elapsed_ticks 0]", tcl)
        self.assertIn("p7_stationary_sample_from_ledger", tcl)
        self.assertIn("ELAPSED_TICKS_$threshold_ticks", tcl)
        self.assertIn("QUEUE_OBS_NOT_BEFORE_TICKS_$observation_not_before_ticks", tcl)
        self.assertIn("while {$sample_index < 59}", tcl)
        self.assertNotIn("set next_sample_ms", tcl)
        self.assertNotIn("$now_ms >= $next_sample_ms", tcl)
        terminal_dump = tcl.index("p7_dump_case $bundle_dir $slot $case_input($slot)")
        self.assertIn("P7_STATIONARY_TERMINAL_BUNDLE_%08u_CAPTURED=1", tcl[terminal_dump:])
        self.assertIn("completion_sequence", tcl[terminal_dump - 1000 : terminal_dump])
        prepare = tcl.index("p7_prepare_stationary_slot", terminal_dump)
        fresh_read = tcl.index("set elapsed_ticks [p7_read_runtime_elapsed_ticks]", prepare)
        cutoff_check = tcl.index("$elapsed_ticks + $ready_publish_guard_ticks < $scheduling_cutoff_ticks", fresh_read)
        publish = tcl.index("p7_commit_stationary_slot", cutoff_check)
        post_read = tcl.index("set last_requeue_post_ticks [p7_read_runtime_elapsed_ticks]", publish)
        fatal_check = tcl.index("P7 stationary READY publication crossed the PS-time scheduling cutoff", post_read)
        self.assertLess(terminal_dump, prepare)
        self.assertLess(prepare, fresh_read)
        self.assertLess(fresh_read, cutoff_check)
        self.assertLess(cutoff_check, publish)
        self.assertLess(publish, post_read)
        self.assertLess(post_read, fatal_check)
        self.assertIn("P7_STATIONARY_REQUEUE_CUTOFF_VIOLATION=1", tcl)
        self.assertIn("P7_STATIONARY_REQUEUE_CUTOFF_VIOLATION=0", tcl)
        self.assertIn("p7_descriptor_admission_allowed", (ROOT / "software" / "ps_driver" / "p7_app_service.c").read_text(encoding="utf-8"))
        self.assertNotIn("if {$elapsed_sec < $plan_value(SCHEDULING_CUTOFF_SECONDS)}", tcl)

    def test_runtime_elapsed_writer_uses_direct_barriered_seqlock(self) -> None:
        service = (ROOT / "software" / "ps_driver" / "p7_app_service.c").read_text(encoding="utf-8")
        start = service.index("static void p7_publish_runtime_elapsed(")
        end = service.index("static uint64_t p7_get_ticks", start)
        writer = service[start:end]
        odd = writer.index("runtime_elapsed_sequence = sequence + 1U")
        low = writer.index("runtime_elapsed_ticks_low =")
        high = writer.index("runtime_elapsed_ticks_high =")
        even = writer.index("runtime_elapsed_sequence = sequence + 2U")
        barriers = [match.start() for match in re.finditer(r"\bdmb\(\);", writer)]
        self.assertGreaterEqual(len(barriers), 3)
        self.assertLess(odd, barriers[0])
        self.assertLess(barriers[0], low)
        self.assertLess(low, high)
        self.assertLess(high, barriers[1])
        self.assertLess(barriers[1], even)
        self.assertLess(even, barriers[2])
        runtime_check = service[service.index("static int p7_runtime_expired(") : service.index("static int p7_runtime_has_budget")]
        self.assertLess(
            runtime_check.index("p7_read_runtime_elapsed_request(mailbox)"),
            runtime_check.index("p7_get_ticks()"),
        )
        self.assertLess(
            runtime_check.index("p7_get_ticks()"),
            runtime_check.index("p7_publish_runtime_elapsed(mailbox, elapsed, request)"),
        )
        self.assertIn("if (request != mailbox->runtime_elapsed_ack)", service)
        final_block = service[service.rindex("final_runtime_request =") : service.rindex("return shutdown_status")]
        self.assertLess(final_block.index("p7_publish_runtime_elapsed("), final_block.index("mailbox->service_state ="))
        generic_start = service.index("static void p7_publish_mailbox(")
        generic_end = service.index("static void p7_assign_terminal_sequence", generic_start)
        self.assertNotIn("runtime_elapsed_sequence", service[generic_start:generic_end])
        self.assertEqual(1, service.count("mailbox->runtime_elapsed_ticks_low ="))
        self.assertEqual(1, service.count("mailbox->runtime_elapsed_ticks_high ="))

    def test_ps_service_retry_budget_latency_and_failure_snapshot_are_unambiguous(self) -> None:
        service = (ROOT / "software" / "ps_driver" / "p7_app_service.c").read_text(encoding="utf-8")
        runtime = (ROOT / "software" / "ps_driver" / "p7_runtime_main.c").read_text(encoding="utf-8")
        self.assertLess(
            runtime.index("Xil_DCacheDisable();"),
            runtime.index("volatile p7_mailbox_control_t *mailbox"),
        )
        process_start = service.index("static int p7_process_descriptor(")
        process_end = service.index("static uint32_t p7_queue_occupancy", process_start)
        process = service[process_start:process_end]
        self.assertNotIn("for (attempts =", process)
        self.assertIn("result.retry_count > request.max_retries", process)
        self.assertIn("uint32_t attempts = 1U", process)
        self.assertLess(
            process.index("object_start = p7_get_ticks()"),
            process.index("p7_integrity_checked("),
        )
        integrity_start = service.index("static int p7_integrity_checked(")
        integrity_end = service.index("static int p7_p6_open(", integrity_start)
        integrity = service[integrity_start:integrity_end]
        self.assertIn("uint8_t snapshot[256] __attribute__((aligned(64)))", integrity)
        invalidate = integrity.index("p7_invalidate(data + offset, chunk);")
        snapshot = integrity.index("memcpy(snapshot, data + offset, chunk);")
        crc = integrity.index("crc ^= snapshot[index];")
        sha = integrity.index("p7_sha256_update(&sha, snapshot, chunk);")
        self.assertLess(invalidate, snapshot)
        self.assertLess(snapshot, crc)
        self.assertLess(crc, sha)
        self.assertNotIn("crc ^= data[offset + index];", integrity)
        self.assertNotIn("p7_sha256_update(&sha, data + offset, chunk);", integrity)
        retained = integrity.index("memcpy(retained_snapshot + offset, snapshot, retained);")
        self.assertLess(snapshot, retained)
        self.assertLess(retained, crc)
        publish = process.index("p7_publish_integrity_failure_snapshot(")
        failed = process.index("failed:")
        wipe = process.index("p7_wipe_partial(", failed)
        self.assertLess(publish, failed)
        self.assertLess(failed, wipe)
        header = (ROOT / "software" / "ps_driver" / "p7_app_service.h").read_text(encoding="utf-8")
        self.assertIn("P7_FAILURE_SNAPSHOT_MAGIC", header)
        self.assertIn("P7_FAILURE_SNAPSHOT_MAX_BYTES", header)
        self.assertIn("failure_snapshot_address", header)
        self.assertIn("failure_snapshot_bytes", header)
        self.assertIn("failure_snapshot_status", header)
        self.assertIn("failure_snapshot_magic_readback", header)
        self.assertIn("P7_FAILURE_SNAPSHOT_STATUS_PUBLISHED", header)
        self.assertIn("P7_FAILURE_SNAPSHOT_STATUS_MARKER_READBACK_FAILED", header)
        self.assertIn("P7_FAILURE_SNAPSHOT_BASEADDR", header)
        self.assertIn("P7_FAILURE_SNAPSHOT_BASEADDR UINT32_C(0x00021000)", header)
        self.assertIn("P7_FAILURE_SNAPSHOT_TOTAL_BYTES", header)
        self.assertIn("failure snapshot must not overlap the descriptor queue", service)
        self.assertIn("failure snapshot must remain in reserved OCM", service)
        self.assertIn("memset((void *)(uintptr_t)P7_FAILURE_SNAPSHOT_BASEADDR, 0,", service)
        self.assertIn("P7_FAILURE_SNAPSHOT_STATUS_PUBLISHED, address, total_bytes,", service)
        self.assertIn("Xil_In32(address)", service)
        diagnostic = service.index("p7_publish_failure_snapshot_diagnostic(")
        terminal = process.index("p7_publish_descriptor(", process.index("failed:"))
        self.assertLess(diagnostic, process_start + terminal)
        submit_start = service.index("static int p7_p6_submit(")
        submit_end = service.index("static int p7_p6_poll(", submit_start)
        submit = service[submit_start:submit_end]
        self.assertIn("p7_p6_snapshot_and_shutdown(context)", submit)
        snapshot_start = service.index("static void p7_p6_snapshot_and_shutdown(")
        snapshot = service[snapshot_start:submit_start]
        self.assertLess(
            snapshot.index("ir_driver_p6_read_result(context->io, &context->p6)"),
            snapshot.index("p7_stop_and_shutdown(context->service)"),
        )
        self.assertNotIn("(void)ir_driver_shutdown(&io)", runtime)

    def test_wrapper_never_sets_external_authorization_and_keeps_runtime_cap(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('os.environ["RF_COMM_HW_AUTH"] =', text)
        self.assertNotIn('env["RF_COMM_HW_AUTH"] =', text)
        self.assertEqual(1800, stage.MAX_SERVICE_RUNTIME_SEC)
        self.assertEqual(1800, stage.CALIBRATION_SEC + stage.ACCEPTANCE_SEC)
        direct_args = stage.build_parser().parse_args(
            [
                "--mode",
                "functional",
                "--max-runtime-sec",
                "900",
                "--vivado-path",
                r"D:\Xilinx\Vivado\2023.1\bin\vivado.exe",
            ]
        )
        with mock.patch.object(stage, "_profile_errors", return_value=[]), mock.patch.object(
            stage, "_active_profile_errors", return_value=[]
        ), mock.patch.object(stage, "_immutable_errors", return_value=[]), mock.patch.object(
            stage, "_summary_errors", return_value=[]
        ), mock.patch.object(stage, "_authorization_extension_errors", return_value=[]):
            direct_errors = stage._stage_validation(direct_args, {"errors": []})
        self.assertTrue(any("vivado.exe is forbidden" in item for item in direct_errors))
        stationary = stage.ps_wrapper_wall_budget(
            mode="stationary",
            max_runtime_sec=1800,
            preflight_timeout_sec=60,
            shutdown_timeout_sec=30,
        )
        self.assertEqual(1800, stationary["service_active_window_seconds"])
        self.assertTrue(stationary["stationary_active_window_is_not_extended"])
        self.assertEqual(2221.5, stationary["candidate_process_bound_seconds"])
        self.assertEqual(90, stationary["vivado_containment_allowance_seconds"])
        self.assertEqual(30, stationary["vivado_success_containment_window_seconds_each"])
        self.assertEqual(40, stationary["vivado_failure_containment_window_seconds_each"])
        self.assertEqual(1, stationary["xsdb_containment_allowance_seconds"])
        self.assertEqual(20, stationary["forced_cleanup_reserve_seconds"])
        self.assertEqual(2573, stationary["minimum_outer_wrapper_timeout_seconds"])
        nonstationary = stage.ps_wrapper_wall_budget(
            mode="functional",
            max_runtime_sec=900,
            preflight_timeout_sec=60,
            shutdown_timeout_sec=30,
        )
        self.assertEqual(1371, nonstationary["minimum_outer_wrapper_timeout_seconds"])


if __name__ == "__main__":
    unittest.main()
