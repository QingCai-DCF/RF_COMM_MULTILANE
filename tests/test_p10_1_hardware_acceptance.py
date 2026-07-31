from __future__ import annotations

import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/p10_hardware_runtime.py"
RUNNER = ROOT / "scripts/p10_1_hardware_acceptance.py"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
RUNTIME_EXTENSION = ROOT / "software/ps_driver/p10_1_runtime_extension.inc"


def load_runner():
    runtime_spec = importlib.util.spec_from_file_location(
        "p10_hardware_runtime", RUNTIME
    )
    assert runtime_spec is not None and runtime_spec.loader is not None
    runtime = importlib.util.module_from_spec(runtime_spec)
    sys.modules[runtime_spec.name] = runtime
    runtime_spec.loader.exec_module(runtime)

    runner_spec = importlib.util.spec_from_file_location(
        "p10_1_hardware_acceptance", RUNNER
    )
    assert runner_spec is not None and runner_spec.loader is not None
    runner = importlib.util.module_from_spec(runner_spec)
    sys.modules[runner_spec.name] = runner
    runner_spec.loader.exec_module(runner)
    return runner


class P101HardwareAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def _row(self, *, flags: int = 0, direction: int = 0) -> dict[str, int | str]:
        return {
            "label": "synthetic",
            "flags": flags,
            "direction": direction,
            "lane": 3,
            "size": 1024 * 1024,
            "ring": 16,
            "initialseq": 4,
            "stale": 4,
            "sequence": 7,
        }

    def _result(
        self,
        role: int,
        row: dict[str, int | str],
        *,
        recovery: bool = False,
        service_reset: bool = False,
    ) -> dict[str, object]:
        size = int(row["size"])
        result: dict[str, object] = {
            "magic": self.runner.P10_1_MAGIC,
            "schema_version": self.runner.P10_1_SCHEMA,
            "endpoint_role": role,
            "service_state": 4 if service_reset else (7 if recovery else 6),
            "status": 0,
            "command_sequence": int(row["sequence"]),
            "lane_mask": int(row["lane"]),
            "direction": int(row["direction"]),
            "total_bytes": size,
            "ring_depth": int(row["ring"]),
            "descriptor_batch": int(row["initialseq"]),
            "buffer_count": int(row["stale"]),
            "host_command_count": 1,
            "fast_path_segment_count": 4,
            "timer_crosscheck_pass": 1,
            "descriptor_leak_count": 0,
            "double_completion_count": 0,
            "partial_commit_count": 0,
            "duplicate_commit_count": 0,
            "stale_commit_count": 0,
            "integrity_error_count": 0,
            "crc_bad_count": 0,
            "sha_mismatch_count": 0,
            "retry_exhausted_count": 0,
            "perf_integrity_error_count": 0,
            "perf_retry_exhausted_count": 0,
            "perf_descriptor_leak_count": 0,
            "perf_double_completion_count": 0,
            "perf_application_accepted": size,
            "perf_application_committed": size,
            "perf_frame_acked": size,
            "perf_wire_bytes": size + 32 if role == 1 else 24,
            "perf_descriptor_submitted": 4,
            "perf_descriptor_completed": 4,
            "shutdown_attempt_count": 1,
            "shutdown_verified_count": 1,
            "final_pl_status": 0x2,
            "final_phy_status": 0,
            "application_bytes_accepted": (
                0 if recovery or service_reset else size
            ),
            "application_bytes_committed": (
                0 if recovery or service_reset else size
            ),
            "wire_bytes": size + 32 if role == 1 else 24,
            "atomic_commit_count": 0 if recovery or service_reset else 1,
            "remote_commit_confirmed": (
                0 if recovery or service_reset else 1
            ),
            "objects_submitted": 0 if recovery else 4,
            "objects_completed": 0 if recovery else 4,
            "object_count": 4,
            "descriptors_submitted": 4,
            "descriptors_completed": 4,
            "abort_count": 1 if recovery else 0,
            "descriptors_reclaimed_by_reset": 4 if recovery else 0,
            "dma_reset_count": 0,
            "pl_reset_count": 0,
            "injected_fault_observed_count": 0,
            "input_crc32": 0x12345678,
            "output_crc32": 0x12345678,
            "input_sha256_words": list(range(8)),
            "output_sha256_words": list(range(8)),
            "ps_elapsed_ticks": 100_000_000,
            "ps_timer_frequency_hz": 100_000_000,
            "pl_elapsed_ticks": 64_000_000,
            "pl_timer_frequency_hz": 64_000_000,
        }
        return result

    def test_plan_is_complete_deterministic_and_bounded(self) -> None:
        plans = self.runner.build_plans()
        self.assertEqual(
            list(plans),
            [
                "preflight",
                "smoke",
                "baseline",
                "tuning",
                "pipeline",
                "streaming",
                "faults",
                "crosstalk",
                "half_duplex",
                "oneplusone",
                "formal",
            ],
        )
        self.assertEqual(
            self.runner.plan_hashes(list(plans)),
            self.runner.plan_hashes(list(plans)),
        )
        for plan in plans.values():
            for item in plan:
                if isinstance(item, self.runner.Case):
                    item.validate()
                    self.assertLessEqual(item.lane, 3)
        self.assertEqual(
            plans["formal"], [("P101_FORMAL", "stationary_30min", "1800")]
        )
        self.assertEqual(len(plans["tuning"]), 10)
        streaming = [
            item
            for item in plans["streaming"]
            if isinstance(item, self.runner.Case)
        ]
        self.assertEqual({item.size for item in streaming}, {64 * 1024 * 1024})
        self.assertEqual({item.direction for item in streaming}, {0, 1})

    def test_binary_parser_uses_frozen_schema_offsets(self) -> None:
        words = [0] * 512
        words[0] = self.runner.P10_1_MAGIC
        words[1] = self.runner.P10_1_SCHEMA
        words[3] = 2
        words[30] = 0x89ABCDEF
        words[31] = 0x01234567
        words[164] = 17
        words[165] = 19
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "p101.bin"
            path.write_bytes(struct.pack("<512I", *words))
            parsed = self.runner.parse_p101(path)
        self.assertEqual(parsed["endpoint_role"], 2)
        self.assertEqual(parsed["ps_elapsed_ticks"], 0x0123456789ABCDEF)
        self.assertEqual(parsed["descriptors_reclaimed_by_reset"], 17)
        self.assertEqual(parsed["injected_fault_observed_count"], 19)

    def test_normal_pair_requires_atomic_cross_board_integrity(self) -> None:
        row = self._row()
        fixed = self._result(1, row)
        rotating = self._result(2, row)
        errors, detail = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertEqual(errors, [])
        self.assertFalse(detail["recovery_case"])
        self.assertGreater(detail["application_goodput_bps"], 0)

        rotating["output_sha256_words"] = [9] * 8
        errors, _ = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertIn("synthetic:receiver stream SHA mismatch", errors)

    def test_recovery_pair_requires_reclaim_and_selected_reset(self) -> None:
        row = self._row(flags=self.runner.FLAG_DMA_RESET_RECEIVER)
        fixed = self._result(1, row, recovery=True)
        rotating = self._result(2, row, recovery=True)
        rotating["dma_reset_count"] = 1
        errors, detail = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertEqual(errors, [])
        self.assertTrue(detail["recovery_case"])
        self.assertIsNone(detail["application_goodput_bps"])

        rotating["descriptors_reclaimed_by_reset"] = 0
        errors, _ = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertIn(
            "synthetic:rotating:descriptor_reclaim_recorded", errors
        )

    def test_service_reset_snapshot_must_be_active_and_uncommitted(self) -> None:
        row = self._row(flags=self.runner.FLAG_PS_RESET_SENDER)
        fixed = self._result(1, row, service_reset=True)
        rotating = self._result(2, row, service_reset=True)
        errors, detail = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertEqual(errors, [])
        self.assertTrue(detail["service_reset_case"])

        fixed["application_bytes_committed"] = 1
        errors, _ = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertIn("synthetic:fixed:zero_commit_bytes", errors)

    def test_window_aggregation_uses_wall_and_active_time(self) -> None:
        rows = []
        details = []
        markers = {}
        for spec in self.runner._window_specs("baseline"):
            label = spec["label"]
            duration_ms = spec["duration_seconds"] * 1000
            row = {
                "label": f"{label}_00000",
                "window": label,
                "command": 13,
                "direction": spec["direction"],
                "lane": spec["lane_mask"],
                "started_ms": 1000,
                "finished_ms": duration_ms,
            }
            sender = {
                "application_bytes_committed": 16 * 1024 * 1024,
                "ps_elapsed_ticks": 25_000_000,
                "ps_timer_frequency_hz": 1_000_000,
                "host_command_count": 1,
                "fast_path_segment_count": 256,
                "objects_completed": 64,
            }
            rows.append(row)
            details.append(
                {
                    "label": row["label"],
                    "fixed": sender,
                    "rotating": sender.copy(),
                }
            )
            markers[
                "P10_1_WINDOW_PASS_" + self.runner._marker_label(label)
            ] = f"cases:1,elapsed_ms:{duration_ms}"
        errors, windows = self.runner._aggregate_windows(
            "baseline", rows, details, markers
        )
        self.assertEqual(errors, [])
        self.assertEqual(len(windows), 6)
        self.assertTrue(all(item["host_not_in_fast_path"] for item in windows))
        self.assertGreater(
            windows[0]["wall_application_goodput_bps"], 4_000_000
        )

    def test_runtime_and_tcl_fail_closed_contract_is_present(self) -> None:
        runner = RUNNER.read_text(encoding="utf-8")
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        extension = RUNTIME_EXTENSION.read_text(encoding="utf-8")
        for marker in (
            "NO_HARDWARE",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION",
            "initial_shutdown",
            "finally_emergency",
            "maximum_lane_mask",
            "ethernet_allowed",
            "rewiring_allowed",
        ):
            self.assertIn(marker, runner)
        for marker in (
            "P101_WINDOW",
            "P101_PSRESET",
            "P101_FORMAL",
            "P101_1PLUS1_PROBE",
            "P10_1_WINDOW_PASS_",
            "P10_1_FORMAL_RESULT",
        ):
            self.assertIn(marker, tcl)
        self.assertNotIn("socket", tcl.lower())
        self.assertNotIn("ethernet", tcl.lower())
        self.assertIn("if (recovery_flags != 0U &&", extension)

    def test_cacheable_runtime_state_is_cleaned_before_xsdb_polling(self) -> None:
        extension = RUNTIME_EXTENSION.read_text(encoding="utf-8")
        publish_start = extension.index("static void p10_1_publish_state")
        publish_end = extension.index(
            "static void p10_1_store64", publish_start
        )
        publish = extension[publish_start:publish_end]
        state_write = publish.index("result->service_state = state;")
        cache_clean = publish.index(
            "Xil_DCacheFlushRange((UINTPTR)result, sizeof(*result));"
        )
        self.assertIn("if (g_cache_enabled != 0U)", publish)
        self.assertLess(state_write, cache_clean)
        self.assertGreaterEqual(publish.count("dsb();"), 2)

    def test_receiver_prime_timeout_preserves_machine_diagnostics(self) -> None:
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        wait_start = tcl.index("proc p10_wait_receiver_primed")
        wait_end = tcl.index("proc p10_record_observation", wait_start)
        wait = tcl[wait_start:wait_end]
        for marker in (
            "main_state=0x%08X",
            "response=0x%08X",
            "pl_status=0x%08X",
            "phy=0x%08X",
            "p10_1_magic=0x%08X",
            "p10_1_state=0x%08X",
            "p10_1_status=0x%08X",
            "p10_1_sequence=0x%08X",
        ):
            self.assertIn(marker, wait)


if __name__ == "__main__":
    unittest.main()
