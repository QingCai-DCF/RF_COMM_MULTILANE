import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts/p10_1r_hardware_acceptance.py"
TCL_PATH = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"
PROTOCOL = ROOT / "software/ps_driver/p10_1_runtime_protocol.h"
EXTENSION = ROOT / "software/ps_driver/p10_1_runtime_extension.inc"
RUNTIME_MAIN = ROOT / "software/ps_driver/p9_runtime_main.c"
FIXED_ROLE = ROOT / "board_profiles/ax7020_fixed_2lane/p10_runtime_role.h"
ROTATING_ROLE = ROOT / "board_profiles/ax7020_rotating_2lane/p10_runtime_role.h"


def load_runner():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "p10_1r_hardware_acceptance_test_module", RUNNER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P101RHardwareAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def test_goal_and_artifact_freeze_are_exact(self) -> None:
        self.assertEqual(
            self.runner.sha256(self.runner.GOAL),
            self.runner.EXPECTED_GOAL_SHA256,
        )
        self.assertEqual(self.runner.EXPECTED_ARTIFACT_PURPOSE, "FINAL_ACCEPTANCE")
        self.assertTrue(self.runner.EXPECTED_ACCEPTANCE_ELIGIBLE)
        self.assertEqual(
            self.runner.EXPECTED_ALLOWED_HARDWARE_STAGES,
            self.runner.STAGES,
        )
        freeze, artifacts = self.runner.load_freeze()
        self.assertEqual(freeze["status"], "PASS")
        self.assertEqual(
            freeze["source_commit"],
            "e38b0772f02c898ebe9b53f6ac3c1bda06a4210c",
        )
        self.assertEqual(len(artifacts), 10)

    def test_plan_scope_is_stationary_half_duplex_only(self) -> None:
        plans = self.runner.build_plans()
        self.assertEqual(tuple(plans), self.runner.STAGES)
        all_text = "".join(
            self.runner.plan_text(items) for items in plans.values()
        )
        self.assertNotIn("P101_1PLUS1", all_text)
        for items in plans.values():
            for item in items:
                if isinstance(item, self.runner.Case):
                    self.assertLessEqual(item.lane, 3)
                    self.assertIn(item.direction, (0, 1))

    def test_echo_plan_has_exactly_1000_samples_per_module(self) -> None:
        items = self.runner.build_plans()["echo_tail"]
        self.assertEqual(len(items), 4)
        self.assertEqual({item[1] for item in items}, {
            "echo_F0", "echo_F1", "echo_R0", "echo_R1"
        })
        self.assertTrue(all(item[4] == "1000" for item in items))

    def test_streaming_plan_has_goal_recovery_matrix(self) -> None:
        items = self.runner.build_plans()["streaming_64m"]
        cases = [item for item in items if isinstance(item, self.runner.Case)]
        normal = [item for item in cases if item.label.startswith("stream64_")]
        self.assertEqual(sum(item.direction == 0 for item in normal), 5)
        self.assertEqual(sum(item.direction == 1 for item in normal), 5)
        abort50 = next(item for item in cases if item.label == "stream_abort50_f2r")
        self.assertEqual(abort50.flags, self.runner.FLAG_ABORT_50)
        self.assertTrue(any(
            not isinstance(item, self.runner.Case)
            and item[0] == "P101_PSRESET"
            for item in items
        ))
        self.assertTrue(any(
            item.flags & self.runner.p101.FLAG_DMA_RESET_SENDER
            for item in cases
        ))

    def test_abort50_is_a_distinct_firmware_recovery_flag(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        extension = EXTENSION.read_text(encoding="utf-8")
        self.assertIn(
            "P10_1_RUNTIME_FLAG_EXPECT_ABORT_50 = 1U << 25", protocol
        )
        self.assertIn(
            "P10_1_RUNTIME_FLAG_EXPECT_ABORT_50", extension
        )
        self.assertIn(
            "recovery_ordinal = result->object_count / 2U", extension
        )

    def test_snapshot_parser_is_fail_closed(self) -> None:
        words = [0] * 40
        words[35:40] = [4096, 256, 131072, 4, 3]
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "snapshot.psv"
            path.write_text(
                "|".join(str(value) for value in [2, 0x52310101, *words]),
                encoding="ascii",
            )
            parsed = self.runner.parse_snapshot(path)
            self.assertEqual(parsed["configured_guard_cycles"], 4096)
            self.assertEqual(parsed["decoder_clear_cycles"], 4)
            self.assertEqual(parsed["admission_config_flags"], 3)
            path.write_text("2|0", encoding="ascii")
            with self.assertRaises(ValueError):
                self.runner.parse_snapshot(path)

    def test_echo_evaluator_uses_nearest_rank_and_zero_acceptance(self) -> None:
        header = (
            "sample|module|direction|lane_mask|tail_cycles|sender_raw|"
            "sender_raw_while_tx|sender_blanked_raw|sender_blanked_frame|"
            "sender_blanked_crc_valid|sender_local_source_reject|"
            "sender_accepted_remote|receiver_raw|receiver_accepted_remote|"
            "sender_last_txd_rise|sender_last_txd_fall|"
            "sender_first_rxd_after_tx|sender_last_rxd_after_tx|"
            "sender_overlap_violation|sender_admission_violation|"
            "sender_non_target_accepted|sender_cross_lane_accepted|"
            "receiver_overlap_violation|receiver_admission_violation|"
            "receiver_non_target_accepted|receiver_cross_lane_accepted"
        ).split("|")
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            stage = Path(directory)
            dumps = stage / "dumps"
            dumps.mkdir()
            for module, direction, lane in (
                ("F0", 0, 1), ("F1", 0, 2),
                ("R0", 1, 1), ("R1", 1, 2),
            ):
                path = dumps / f"echo_{module}.echo_tail.psv"
                with path.open("w", encoding="ascii", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=header, delimiter="|")
                    writer.writeheader()
                    for sample in range(1000):
                        row = {name: 0 for name in header}
                        row.update({
                            "sample": sample,
                            "module": module,
                            "direction": direction,
                            "lane_mask": lane,
                            "tail_cycles": 0,
                            "sender_raw": 1,
                            "sender_blanked_raw": 1,
                            "receiver_raw": 1,
                        })
                        writer.writerow(row)
            errors, result = self.runner.evaluate_echo(stage)
            self.assertEqual(errors, [])
            self.assertEqual(result["sample_count"], 4000)
            self.assertEqual(result["modules"]["F0"]["p99_cycles"], 0)
            self.assertEqual(result["modules"]["F0"]["p99_9_cycles"], 0)
            self.assertTrue(result["configured_guard_is_safe"])

    def test_runner_has_all_hardware_gates_and_finally_shutdown(self) -> None:
        text = RUNNER_PATH.read_text(encoding="utf-8")
        for marker in (
            "--execute-hardware",
            "NO_HARDWARE",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION",
            "initial_shutdown",
            "shutdown-before unconfirmed",
            "finally_emergency",
            "SHUTDOWN_FIXED",
            "SHUTDOWN_ROTATING",
            "retry_limit=3",
        ):
            self.assertIn(marker, text)
        self.assertNotIn(
            "local-source rejection was not directly observed",
            text,
        )
        self.assertIn('"local_source_rejection_enabled"', text)
        self.assertNotIn("git push", text)
        self.assertNotIn("lane mask >", text)

    def test_tcl_has_atomic_snapshot_and_absolute_formal_boundaries(self) -> None:
        text = TCL_PATH.read_text(encoding="utf-8")
        for marker in (
            "p10_read_p10_1r_snapshot",
            "p10_record_p10_1r_telemetry",
            "P101R_ECHO_SWEEP",
            "$started + 120000",
            "$started + 960000",
            "$started + 1800000",
            "P10_1R-(PREFLIGHT|ECHO_TAIL|CROSSTALK|PHY_SANITY|ACK_TUNING|PERFORMANCE|STREAMING_64M|FORMAL_30MIN)",
        ):
            self.assertIn(marker, text)

    def test_p10_1r_pl_build_identity_is_explicit_end_to_end(self) -> None:
        self.assertEqual(
            self.runner.EXPECTED_PL_BUILD_IDS,
            {"fixed": 0x50325246, "rotating": 0x50325252},
        )
        self.assertIn(
            "#define P10_EXPECTED_PL_BUILD_ID 0x50325246U",
            FIXED_ROLE.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "#define P10_EXPECTED_PL_BUILD_ID 0x50325252U",
            ROTATING_ROLE.read_text(encoding="utf-8"),
        )
        runtime = RUNTIME_MAIN.read_text(encoding="utf-8")
        self.assertIn("return P10_EXPECTED_PL_BUILD_ID;", runtime)
        self.assertNotIn(
            "if (P10_ENDPOINT_ROLE == 1) return UINT32_C(0x50313046)",
            runtime,
        )
        tcl = TCL_PATH.read_text(encoding="utf-8")
        self.assertIn("[llength $argv] ni {16 18}", tcl)
        self.assertIn("$p10_expected_build(fixed)", tcl)
        self.assertIn("$p10_expected_build(rotating)", tcl)
        runner = RUNNER_PATH.read_text(encoding="utf-8")
        self.assertIn("EXPECTED_ROLE_IDENTITIES", runner)
        self.assertIn("EXPECTED_PL_BUILD_IDS['fixed']", runner)
        self.assertIn("EXPECTED_PL_BUILD_IDS['rotating']", runner)


if __name__ == "__main__":
    unittest.main()
