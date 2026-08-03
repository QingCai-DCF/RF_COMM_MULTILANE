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

    def test_goal_and_artifact_bundle_contract_is_fail_closed(self) -> None:
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
        with self.assertRaisesRegex(RuntimeError, "artifact-freeze SHA256 mismatch"):
            self.runner.load_freeze("0" * 64)

    def test_standing_authorization_sources_are_exact_and_unbounded(self) -> None:
        sources = self.runner.STANDING_AUTHORIZATION_SOURCES
        self.assertEqual(
            sources[0]["source_thread_id"],
            "019fc130-82cb-7653-bda1-69a0ccfee3fd",
        )
        self.assertEqual(sources[0]["scope"], self.runner.EXPECTED_SCOPE)
        self.assertTrue(sources[0]["artifact_bundle_iteration_authorized"])
        self.assertEqual(sources[1]["user_quotes"], ["不设上限"])
        self.assertIsNone(sources[1]["campaign_new_run_id_limit"])

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
        self.assertEqual(
            [item[1] for item in items],
            ["echo_F1", "echo_R1", "echo_F0", "echo_R0"],
        )
        self.assertTrue(all(item[4] == "1000" for item in items))

    def test_echo_failure_captures_terminal_state_before_shutdown(self) -> None:
        tcl = TCL_PATH.read_text(encoding="utf-8")
        self.assertIn("P10_1R_ECHO_SWEEP_FAIL=", tcl)
        self.assertIn("P10_1R_ECHO_SWEEP_FAILURE_SNAPSHOT=", tcl)
        self.assertIn("fixed_status=0x%08X", tcl)
        self.assertIn("rotating_status=0x%08X", tcl)
        self.assertIn("fixed_phy_status=0x%08X", tcl)
        self.assertIn("rotating_phy_status=0x%08X", tcl)
        self.assertIn("fixed_error_detail=0x%08X", tcl)
        self.assertIn("rotating_error_detail=0x%08X", tcl)
        self.assertIn("p10_read32 fixed 0x000201CC", tcl)
        self.assertIn("p10_read32 rotating 0x000201CC", tcl)
        self.assertIn("sender_raw_while_tx=%u", tcl)
        self.assertIn("receiver_raw=%u", tcl)
        self.assertIn("sender_last_txd_rise=%u", tcl)
        self.assertIn("sender_last_txd_fall=%u", tcl)
        self.assertIn("sender_raw_sent=%u", tcl)
        self.assertIn("fixed_physical_tx=%s", tcl)
        self.assertIn("sender_dump=%s", tcl)
        self.assertIn("P10_1R_ECHO_DIRECTION_FAILURE_${module}=", tcl)
        self.assertIn("P10_1R_ECHO_DIRECTION_RESULT_${module}=FAIL", tcl)
        self.assertIn("proc p10_rebootstrap_after_echo_direction", tcl)
        self.assertIn("P10_1R_ECHO_DIRECTION_ISOLATION_PASS=", tcl)
        self.assertIn("P10_1R_ECHO_MATRIX_RESULT=FAIL:", tcl)
        snapshot = tcl.index("set fixed_failure_snapshot")
        marker = tcl.index("P10_1R_ECHO_SWEEP_FAILURE_SNAPSHOT=")
        shutdown_request = tcl.index(
            "P10_ENDPOINT_SHUTDOWN_REQUESTED_ON_ERROR=1", marker
        )
        self.assertLess(snapshot, marker)
        self.assertLess(marker, shutdown_request)

    def test_echo_rebootstrap_ignores_only_bounded_stale_fault(self) -> None:
        tcl = TCL_PATH.read_text(encoding="utf-8")
        wait_start = tcl.index("proc p10_wait_ready")
        wait_end = tcl.index("proc p10_dump_mailbox", wait_start)
        wait = tcl[wait_start:wait_end]
        reboot_start = tcl.index("proc p10_reboot_role")
        reboot_end = tcl.index(
            "proc p10_rebootstrap_after_reset_recovery", reboot_start
        )
        reboot = tcl[reboot_start:reboot_end]

        self.assertIn("{stale_fault_grace_ms 0}", wait)
        self.assertIn("$stale_fault_grace_ms > 2000", wait)
        self.assertIn(
            "$state == 5 && [clock milliseconds] < $stale_fault_deadline",
            wait,
        )
        self.assertIn("P10_SERVICE_STALE_FAULT_IGNORED_", wait)
        self.assertIn("if {$state == 5} {", wait)
        self.assertIn("p10_wait_ready $role $label 1000", reboot)

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

    def test_formal_stream_is_one_large_autonomous_host_command(self) -> None:
        protocol = PROTOCOL.read_text(encoding="utf-8")
        extension = EXTENSION.read_text(encoding="utf-8")
        tcl = TCL_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "P10_1_RUNTIME_MAX_STREAM_BYTES UINT32_C(0x20000000)", protocol
        )
        self.assertIn("total > P10_1_RUNTIME_MAX_STREAM_BYTES", extension)
        self.assertIn("proc p10_run_p101_formal_window", tcl)
        self.assertIn("set stream_bytes 436207616", tcl)
        self.assertIn(
            'p10_run_p101_formal_window "${label}_formal_f2r" 840 0 3', tcl
        )
        self.assertIn(
            'p10_run_p101_formal_window "${label}_formal_r2f" 840 1 3', tcl
        )

        detail = {
            "direction": 0,
            "fixed": {
                "host_command_count": 1,
                "fast_path_segment_count": 6656,
                "checks": {"host_not_fast_path": True},
            },
            "rotating": {},
        }
        self.assertEqual(
            self.runner.formal_host_metrics([detail]),
            {
                "host_blocking_commands": 1,
                "host_fast_path_dependency_count": 0,
                "minimum_segments_per_host_command": 6656,
            },
        )
        self.assertGreater(
            self.runner.formal_host_metrics([detail] * 24)[
                "host_blocking_commands"
            ],
            4,
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
            (stage / "xsdb.result.txt").write_text(
                "\n".join(
                    f"P10_1R_ECHO_DIRECTION_RESULT_{module}=PASS"
                    for module in ("F0", "R0", "F1", "R1")
                )
                + "\n",
                encoding="ascii",
            )
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
            self.assertTrue(result["guard_assessment_complete"])
            self.assertEqual(result["evidence_class"], "RAW_PHYSICAL_ONLY")
            self.assertFalse(result["data_path_acceptance_claimed"])

    def test_echo_failure_snapshot_parser_preserves_direct_physical_facts(self) -> None:
        parsed = self.runner.parse_echo_failure_snapshot(
            "echo_F1:module=F1,sample=0,sender=fixed,receiver=rotating,"
            "sender_raw=1,sender_raw_while_tx=1,sender_blanked_raw=1,"
            "sender_accepted_remote=0,receiver_raw=0,receiver_accepted_remote=0,"
            "sender_last_txd_rise=34007980,sender_last_txd_fall=34007985,"
            "sender_first_rxd_after_tx=0,sender_last_rxd_after_tx=0,"
            "sender_raw_sent=1,receiver_raw_sent=0,"
            "fixed_physical_tx=0,1,0,0,rotating_physical_tx=0,0,0,0,"
            "sender_dump=C:/sender.psv,receiver_dump=C:/receiver.psv"
        )
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["module"], "F1")
        self.assertEqual(parsed["receiver_raw"], 0)
        self.assertEqual(parsed["sender_last_txd_fall"] - parsed["sender_last_txd_rise"], 5)
        self.assertEqual(parsed["fixed_physical_tx"], [0, 1, 0, 0])
        self.assertEqual(parsed["rotating_physical_tx"], [0, 0, 0, 0])

    def test_echo_evaluator_keeps_all_direction_verdicts_after_failures(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            stage = Path(directory)
            dumps = stage / "dumps"
            dumps.mkdir()
            modules = ("F0", "R0", "F1", "R1")
            for module in modules:
                (dumps / f"echo_{module}.echo_tail.psv").write_text(
                    "sample|module\n", encoding="ascii"
                )
            (stage / "xsdb.result.txt").write_text(
                "\n".join(
                    [
                        *(f"P10_1R_ECHO_DIRECTION_RESULT_{module}=FAIL" for module in modules),
                        "P10_1R_ECHO_DIRECTION_FAILURE_F1=echo_F1:module=F1,"
                        "sample=0,sender=fixed,receiver=rotating,sender_raw=1,"
                        "receiver_raw=0",
                    ]
                )
                + "\n",
                encoding="ascii",
            )
            errors, result = self.runner.evaluate_echo(stage)
            self.assertTrue(errors)
            self.assertEqual(set(result["modules"]), set(modules))
            self.assertTrue(all(
                item["physical_direction_status"] == "FAIL"
                for item in result["modules"].values()
            ))
            self.assertEqual(
                result["modules"]["F1"]["failure_snapshot"]["receiver_raw"],
                0,
            )
            self.assertFalse(result["guard_assessment_complete"])
            self.assertIsNone(result["configured_guard_is_safe"])

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

    def test_authorization_consumption_is_terminal_and_idempotent(self) -> None:
        active = {
            "status": "AUTHORIZED",
            "run_id": "p10_1r_test",
            "current_run_hardware_authorization": True,
            "consumed": False,
            "reusable_for_future_run": False,
        }
        consumed = self.runner.consumed_authorization_payload(
            active,
            run_id="p10_1r_test",
            campaign_status="FAIL",
            selected_stages=["echo_tail"],
            consumed_at_utc="2026-08-02T00:00:00+00:00",
            final_evidence_path="evidence/final.json",
            final_evidence_sha256="a" * 64,
            shutdown_fixed="PASS",
            shutdown_rotating="PASS",
            hardware_actions_executed=True,
        )
        self.assertEqual(
            consumed["status"], "CONSUMED_AFTER_P10_1R_HARDWARE_FAIL"
        )
        self.assertFalse(consumed["current_run_hardware_authorization"])
        self.assertTrue(consumed["consumed"])
        self.assertFalse(consumed["full_campaign_completed"])
        self.assertEqual(consumed["consumed_by_run_id"], "p10_1r_test")
        self.assertEqual(
            self.runner.consumed_authorization_payload(
                consumed,
                run_id="p10_1r_test",
                campaign_status="FAIL",
                selected_stages=["echo_tail"],
                consumed_at_utc="2026-08-02T00:00:00+00:00",
                final_evidence_path="evidence/final.json",
                final_evidence_sha256="a" * 64,
                shutdown_fixed="PASS",
                shutdown_rotating="PASS",
                hardware_actions_executed=True,
            ),
            consumed,
        )

    def test_stage_scoped_pass_does_not_claim_campaign_acceptance(self) -> None:
        active = {
            "status": "AUTHORIZED",
            "run_id": "p10_1r_test",
            "authorized_stages": ["echo_tail"],
            "current_run_hardware_authorization": True,
            "consumed": False,
            "reusable_for_future_run": False,
        }
        consumed = self.runner.consumed_authorization_payload(
            active,
            run_id="p10_1r_test",
            campaign_status="PASS",
            selected_stages=["echo_tail"],
            consumed_at_utc="2026-08-03T00:00:00+00:00",
            final_evidence_path="evidence/final.json",
            final_evidence_sha256="a" * 64,
            shutdown_fixed="PASS",
            shutdown_rotating="PASS",
            hardware_actions_executed=True,
        )
        self.assertEqual(
            consumed["campaign_disposition"],
            "AUTHORIZED_STAGE_SET_COMPLETE_CAMPAIGN_REMAINS_PARTIAL",
        )
        self.assertFalse(consumed["full_campaign_completed"])
        self.assertEqual(consumed["consumed_stage_set"], ["echo_tail"])

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

        # ``clock milliseconds`` already exceeds Tcl's 32-bit ``integer``
        # class.  Formal absolute deadlines therefore must be validated as
        # wide integers or every real run fails before its first TX window.
        self.assertIn(
            "![string is wideinteger -strict $absolute_deadline]", text
        )
        self.assertNotIn(
            "![string is integer -strict $absolute_deadline]", text
        )

    def test_p10_1r_pl_build_identity_is_explicit_end_to_end(self) -> None:
        self.assertEqual(
            self.runner.EXPECTED_PL_BUILD_IDS,
            {"fixed": 0x50325346, "rotating": 0x50325352},
        )
        self.assertIn(
            "#define P10_EXPECTED_PL_BUILD_ID 0x50325346U",
            FIXED_ROLE.read_text(encoding="utf-8"),
        )
        self.assertIn(
            "#define P10_EXPECTED_PL_BUILD_ID 0x50325352U",
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
        self.assertIn('"15000000", "1895825408"', runner)
        self.assertIn('"15000000", "1895825409"', runner)
        self.assertIn("$size != 15000000", tcl)
        self.assertIn("ps_runtime_words_csv", tcl)
        self.assertIn("pl_perf_snapshot_words_csv", tcl)


if __name__ == "__main__":
    unittest.main()
