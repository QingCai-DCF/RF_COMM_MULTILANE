from __future__ import annotations

import hashlib
import importlib.util
import json
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
TRANSPORT_CORE = ROOT / "rtl/p9_optical_transport_core.sv"
SELECTIVE_REPEAT_RX = ROOT / "rtl/ir_selective_repeat_rx.sv"


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
            "perf_integrity_error_count": 1 if recovery else 0,
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
        self.assertEqual(len(plans["tuning"]), 9)
        self.assertNotIn(
            "tune_batch1",
            {
                item.label
                for item in plans["tuning"]
                if isinstance(item, self.runner.Case)
            },
        )
        self.assertEqual(
            self.runner.plan_hashes(["tuning"])["tuning"],
            "1e528bb0a2203deb33c74d3f3cd6c3950fb285122690a24654a3e445fc73c9c4",
        )

    def test_selected_streaming_and_abort25_plan_invariants(
        self,
    ) -> None:
        plans = self.runner.build_plans()
        failed_object = next(
            item
            for item in plans["preflight"]
            if isinstance(item, self.runner.Case)
            and item.label == "failed_object_diagnostic"
        )
        object_count = (
            failed_object.size + failed_object.rawtarget - 1
        ) // failed_object.rawtarget

        self.assertEqual(
            failed_object.flags & self.runner.FLAG_ABORT_25,
            self.runner.FLAG_ABORT_25,
        )
        self.assertEqual(
            failed_object.rawtarget,
            self.runner.SELECTED_OBJECT_BYTES,
        )
        self.assertEqual(failed_object.size % failed_object.rawtarget, 0)
        self.assertGreaterEqual(object_count, 4)
        self.assertGreaterEqual(object_count // 4, 1)
        stream = next(
            item
            for item in plans["streaming"]
            if isinstance(item, self.runner.Case)
        )
        self.assertEqual(stream.stale, 4)
        self.assertEqual(stream.ring, 32)
        self.assertEqual(stream.initialseq, 8)
        self.assertEqual(stream.rawtarget, 512 * 1024)
        streaming = [
            item
            for item in plans["streaming"]
            if isinstance(item, self.runner.Case)
        ]
        self.assertEqual({item.size for item in streaming}, {64 * 1024 * 1024})
        self.assertEqual({item.direction for item in streaming}, {0, 1})

    def test_retry_budget_counts_only_entered_hardware_stages(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hardware_root = Path(temporary)
            entered = hardware_root / "p10_1_entered" / "stages" / "preflight"
            entered.mkdir(parents=True)
            (entered / "xsdb.stdout.log").write_text("started", encoding="utf-8")
            dry_run = hardware_root / "p10_1_dry" / "stages"
            dry_run.mkdir(parents=True)
            unrelated = hardware_root / "not_a_p10_run" / "stages" / "preflight"
            unrelated.mkdir(parents=True)
            (unrelated / "log.txt").write_text("ignored", encoding="utf-8")

            self.assertEqual(
                self.runner.attempted_stage_run_ids(
                    "preflight", hardware_root=hardware_root
                ),
                ["p10_1_entered"],
            )

    def test_third_preflight_requires_explicit_run_bound_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for run_id in ("p10_1_attempt_1", "p10_1_attempt_2"):
                stage = root / run_id / "stages" / "preflight"
                stage.mkdir(parents=True)
                (stage / "xsdb.result.txt").write_text("FAIL", encoding="utf-8")
            override = root / "missing_override.json"
            record, budget, errors = self.runner.validate_retry_limit_override(
                override,
                "p10_1_attempt_3",
                ["preflight", "smoke"],
                hardware_root=root,
            )
            self.assertIsNone(record)
            self.assertEqual(len(budget["preflight"]["run_ids"]), 2)
            self.assertTrue(any("limit exhausted" in item for item in errors))

    def test_retry_override_is_exact_and_one_run_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            historical = ["p10_1_attempt_1", "p10_1_attempt_2"]
            for run_id in historical:
                stage = root / run_id / "stages" / "preflight"
                stage.mkdir(parents=True)
                (stage / "xsdb.result.txt").write_text("FAIL", encoding="utf-8")
            statement = (
                "I explicitly override Goal section 23 for exactly one additional "
                "preflight run ID p10_1_attempt_3."
            )
            payload = {
                "schema_version": 1,
                "authorization_id": self.runner.RETRY_OVERRIDE_AUTHORIZATION_ID,
                "status": "AUTHORIZED",
                "scope": self.runner.EXPECTED_SCOPE,
                "goal_sha256": self.runner.EXPECTED_GOAL_SHA256,
                "current_run_hardware_authorization": True,
                "authorized_run_id": "p10_1_attempt_3",
                "authorized_campaign_stages": ["preflight", "smoke"],
                "retry_limit_override_stages": ["preflight"],
                "historical_stage_run_ids": {"preflight": historical},
                "additional_new_run_ids_by_stage": {"preflight": 1},
                "board_identities": self.runner._expected_board_identities(),
                "maximum_single_formal_run_seconds": 1800,
                "maximum_lane_mask": 3,
                "ethernet_allowed": False,
                "movement_allowed": False,
                "rotation_allowed": False,
                "angle_adjustment_allowed": False,
                "obscuration_allowed": False,
                "module_exchange_allowed": False,
                "rewiring_allowed": False,
                "reusable_for_future_run": False,
                "user_authorization_statement": statement,
                "user_authorization_statement_sha256": hashlib.sha256(
                    statement.encode("utf-8")
                ).hexdigest(),
                "user_authorization_received_at": "2026-08-01T00:00:00+08:00",
                "override_reason": "cache-coherency remediation requires retest",
                "shutdown": {
                    "before": True,
                    "on_error": True,
                    "on_timeout": True,
                    "on_interrupt": True,
                    "normal_exit": True,
                    "after": True,
                    "program_role_bound_shutdown_bitstreams": True,
                },
            }
            override = root / "override.json"
            override.write_text(
                json.dumps(payload, sort_keys=True), encoding="utf-8"
            )
            record, _, errors = self.runner.validate_retry_limit_override(
                override,
                "p10_1_attempt_3",
                ["preflight", "smoke"],
                hardware_root=root,
            )
            self.assertEqual(errors, [])
            self.assertEqual(record, payload)

            third = root / "p10_1_attempt_3" / "stages" / "preflight"
            third.mkdir(parents=True)
            (third / "xsdb.result.txt").write_text("PASS", encoding="utf-8")
            _, _, reused_errors = self.runner.validate_retry_limit_override(
                override,
                "p10_1_attempt_4",
                ["preflight", "smoke"],
                hardware_root=root,
            )
            self.assertTrue(reused_errors)

    def test_unlimited_campaign_override_removes_only_retry_counts(self) -> None:
        override = (
            ROOT / "config/p10_1_retry_limit_override_authorization.json"
        )
        record, budget, errors = self.runner.validate_retry_limit_override(
            override,
            "p10_1_unlimited_probe",
            list(self.runner.build_plans()),
        )
        self.assertEqual(errors, [])
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record["user_retry_limit_override"], "不设上限")
        self.assertFalse(record["current_run_hardware_authorization"])
        self.assertTrue(
            record["current_run_authorization_materialized_per_run"]
        )
        self.assertEqual(
            record["effective_retry_limits"],
            {
                "jtag_connect": None,
                "program": None,
                "diagnostic_stage_new_run_id": None,
            },
        )
        self.assertEqual(record["maximum_single_formal_run_seconds"], 1800)
        self.assertEqual(record["maximum_lane_mask"], 3)
        for prohibited in (
            "ethernet_allowed",
            "movement_allowed",
            "rotation_allowed",
            "angle_adjustment_allowed",
            "obscuration_allowed",
            "module_exchange_allowed",
            "rewiring_allowed",
        ):
            self.assertFalse(record[prohibited])
        self.assertEqual(budget["preflight"]["base_goal_limit"], 2)
        self.assertIsNone(budget["preflight"]["effective_limit"])
        self.assertTrue(budget["preflight"]["override_applied"])

    def test_unlimited_override_remains_valid_after_additional_run_ids(self) -> None:
        source = json.loads(
            (
                ROOT / "config/p10_1_retry_limit_override_authorization.json"
            ).read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            override = root / "override.json"
            override.write_text(
                json.dumps(source, ensure_ascii=False), encoding="utf-8"
            )
            for ordinal in range(1, 5):
                stage = (
                    root
                    / f"p10_1_attempt_{ordinal}"
                    / "stages"
                    / "preflight"
                )
                stage.mkdir(parents=True)
                (stage / "xsdb.result.txt").write_text(
                    "PASS" if ordinal == 4 else "FAIL", encoding="utf-8"
                )
            _, budget, errors = self.runner.validate_retry_limit_override(
                override,
                "p10_1_attempt_5",
                list(self.runner.build_plans()),
                hardware_root=root,
            )
            self.assertEqual(errors, [])
            self.assertEqual(len(budget["preflight"]["run_ids"]), 4)
            self.assertIsNone(budget["preflight"]["effective_limit"])

    def test_unlimited_override_rejects_artifact_or_scope_expansion(self) -> None:
        source = json.loads(
            (
                ROOT / "config/p10_1_retry_limit_override_authorization.json"
            ).read_text(encoding="utf-8")
        )
        cases = []
        tampered_artifact = json.loads(json.dumps(source))
        tampered_artifact["artifacts"][0]["sha256"] = "0" * 64
        cases.append(tampered_artifact)
        expanded_lane = json.loads(json.dumps(source))
        expanded_lane["maximum_lane_mask"] = 7
        cases.append(expanded_lane)
        enabled_ethernet = json.loads(json.dumps(source))
        enabled_ethernet["ethernet_allowed"] = True
        cases.append(enabled_ethernet)
        with tempfile.TemporaryDirectory() as temporary:
            override = Path(temporary) / "override.json"
            for payload in cases:
                override.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
                _, _, errors = self.runner.validate_retry_limit_override(
                    override,
                    "p10_1_scope_probe",
                    list(self.runner.build_plans()),
                )
                self.assertTrue(errors)

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

    def test_cross_endpoint_elapsed_skew_is_observed_not_gated(self) -> None:
        row = self._row()
        fixed = self._result(1, row)
        rotating = self._result(2, row)
        rotating["ps_elapsed_ticks"] = 105_000_000
        rotating["pl_elapsed_ticks"] = 67_200_000
        errors, detail = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertEqual(errors, [])
        self.assertGreater(
            detail["cross_endpoint_elapsed_observation"]["ps"]["skew_percent"],
            1.0,
        )
        self.assertTrue(
            detail["local_timer_crosschecks"]["rotating"]["within_one_percent"]
        )

        rotating["pl_elapsed_ticks"] = 64_000_000
        errors, _ = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertIn("synthetic:rotating:timer_host_recomputed", errors)

    def test_recovery_pair_requires_reclaim_and_selected_reset(self) -> None:
        row = self._row(flags=self.runner.FLAG_DMA_RESET_RECEIVER)
        fixed = self._result(1, row, recovery=True)
        rotating = self._result(2, row, recovery=True)
        rotating["dma_reset_count"] = 1
        errors, detail = self.runner.evaluate_p101_pair(row, fixed, rotating)
        self.assertEqual(errors, [])
        self.assertTrue(detail["recovery_case"])
        self.assertIsNone(detail["application_goodput_bps"])
        self.assertTrue(
            detail["fixed"]["checks"]["expected_pl_object_fail_edge"]
        )

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
                "pl_elapsed_ticks": 1_600_000_000,
                "pl_timer_frequency_hz": 64_000_000,
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

    def test_duplicate_fault_stimulus_uses_sender_past_sequence(self) -> None:
        extension = RUNTIME_EXTENSION.read_text(encoding="utf-8")
        transport = TRANSPORT_CORE.read_text(encoding="utf-8")
        receiver = SELECTIVE_REPEAT_RX.read_text(encoding="utf-8")
        configure_start = extension.index(
            "static void p10_1_configure_object"
        )
        configure_end = extension.index(
            "typedef struct p10_1_runtime_buffer_slot", configure_start
        )
        configure = extension[configure_start:configure_end]
        call = (
            "p10_1_configure_object(mailbox, flags, "
            "ordinal == recovery_ordinal,\n                           local_rx);"
        )

        self.assertIn(
            "P10_1_DUPLICATE_PAST_SEQUENCE_FLAG = 1U << 3", extension
        )
        self.assertIn("uint32_t local_receiver", configure)
        self.assertIn(
            "local_receiver == 0U", configure
        )
        self.assertIn(
            "protocol_fault_flags |= "
            "P10_1_DUPLICATE_PAST_SEQUENCE_FLAG",
            configure,
        )
        self.assertNotIn("P10_1_DUPLICATE_ACK_DROP_COUNT", extension)
        self.assertNotIn("physical_fault_injection |=", configure)
        self.assertIn(call, extension)
        self.assertIn("object_initial_sequence_q - 1'b1", transport)
        self.assertIn("fault_attempt_budget_q <=", transport)
        self.assertIn("receive_distance >= 16'h8000", receiver)
        self.assertIn(
            "duplicate_count_q <= duplicate_count_q + 1'b1", receiver
        )

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

    def test_bounded_window_large_chunk_budget_is_measurement_adaptive(
        self,
    ) -> None:
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        window_start = tcl.index("proc p10_run_p101_window")
        window_end = tcl.index("proc p10_wait_p101_active", window_start)
        window = tcl[window_start:window_end]
        for marker in (
            "last_case_size",
            "last_case_elapsed_ms",
            "measured_budget",
            "P10_1_WINDOW_CHUNK_DEFERRED",
        ):
            self.assertIn(marker, window)

        # Captured baseline trace: the first 1 MiB took 4154 ms and left
        # 55846 ms.  Linear scaling alone puts 16 MiB at 66464 ms; the Tcl
        # safety budget is 25% plus 2 s, so that chunk must be deferred.
        elapsed_ms = 4154
        last_size = 1 * 1024 * 1024
        candidate = 16 * 1024 * 1024
        remaining_ms = 55_846
        measured_budget = (
            (
                elapsed_ms * candidate * 5
                + (last_size * 4 - 1)
            )
            // (last_size * 4)
            + 2000
        )
        self.assertEqual(measured_budget, 85_080)
        self.assertGreater(measured_budget + 3000, remaining_ms)

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

        pair_start = tcl.index("proc p10_wait_pair_terminal")
        pair_end = tcl.index("proc p10_execute_case", pair_start)
        pair_wait = tcl[pair_start:pair_end]
        for marker in (
            "fixed_p101_state",
            "fixed_p101_status",
            "fixed_committed_low",
            "rotating_p101_state",
            "rotating_p101_status",
            "rotating_committed_low",
        ):
            self.assertIn(marker, pair_wait)

    def test_reset_recovery_reboot_is_scoped_and_safe(self) -> None:
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        execute_start = tcl.index("proc p10_execute_case")
        execute_end = tcl.index("proc p10_p101_case", execute_start)
        execute = tcl[execute_start:execute_end]

        self.assertIn(
            "(1 << 18) | (1 << 19) | (1 << 24)", execute
        )
        self.assertIn("$command == 13", execute)
        self.assertIn(
            "p10_rebootstrap_after_reset_recovery [dict get $d label]",
            execute,
        )
        self.assertIn("} elseif {$command != 10} {", execute)

        helper_start = tcl.index(
            "proc p10_rebootstrap_after_reset_recovery"
        )
        helper_end = tcl.index("proc p10_soak_case", helper_start)
        helper = tcl[helper_start:helper_end]
        self.assertIn("P10_1_RESET_RECOVERY_REBOOT_BEGIN", helper)
        self.assertIn("p10_reboot_role fixed", helper)
        self.assertIn("p10_reboot_role rotating", helper)
        self.assertIn(
            "p10_verify_pl_safe fixed $p10_expected_build(fixed) 0x702000F0",
            helper,
        )
        self.assertIn(
            "p10_verify_pl_safe rotating $p10_expected_build(rotating) 0x702000A0",
            helper,
        )
        self.assertIn("set p10_expected_build(fixed) 0x50313046", tcl)
        self.assertIn("set p10_expected_build(rotating) 0x50313052", tcl)
        self.assertIn("P10_1_RESET_RECOVERY_REBOOT_PASS", helper)

        # Abort-only recovery flags are bits 16/17 and must not be part of the
        # reset-class rebootstrap mask; those vectors already proved a clean
        # immediate successor on the current hardware.
        self.assertNotIn("1 << 16", execute)
        self.assertNotIn("1 << 17", execute)


if __name__ == "__main__":
    unittest.main()
