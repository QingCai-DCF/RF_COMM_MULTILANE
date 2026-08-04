from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_p10_3f_full_hardware as runner  # noqa: E402


class P103FFullHardwareTests(unittest.TestCase):
    def test_current_build_expectation_adapter_is_scoped(self) -> None:
        original = runner.base.EXPECTED_ROLE

        def inspect_current() -> str:
            for role, build_id in runner.EXPECTED_BUILD.items():
                self.assertEqual(
                    runner.base.EXPECTED_ROLE[role]["firmware"], build_id
                )
                self.assertEqual(
                    runner.base.EXPECTED_ROLE[role]["build"], build_id
                )
            return "CURRENT"

        self.assertEqual(
            runner.with_current_build_expectations(inspect_current), "CURRENT"
        )
        self.assertIs(runner.base.EXPECTED_ROLE, original)

        def fail_during_evaluation() -> None:
            raise RuntimeError("synthetic evaluator failure")

        with self.assertRaisesRegex(RuntimeError, "synthetic evaluator failure"):
            runner.with_current_build_expectations(fail_during_evaluation)
        self.assertIs(runner.base.EXPECTED_ROLE, original)

    def test_full_stage_order_and_plans_are_deterministic(self) -> None:
        first = runner.build_plans()
        second = runner.build_plans()
        self.assertEqual(tuple(first), runner.STAGES)
        self.assertEqual(first, second)
        self.assertEqual(runner.validate_plans(first), [])
        staircase_end = max(runner.STAGES.index(stage)
                            for stage in runner.STAIRCASE_STAGES)
        self.assertLess(staircase_end, runner.STAGES.index("fault_capture"))
        self.assertLess(staircase_end, runner.STAGES.index("raw_8x8"))
        self.assertLess(staircase_end, runner.STAGES.index("two_lane_regression"))
        for stage, text in first.items():
            self.assertTrue(text.endswith("\n"), stage)
            text.encode("ascii")

    def test_bounded_long_test_vectors_preserve_required_aggregates(self) -> None:
        plans = runner.build_plans()
        self.assertEqual(
            plans["two_lane_regression"].count("P10FF_TOTAL "), 2
        )
        self.assertEqual(plans["streaming_64m"].count("P10FF_TOTAL "), 10)
        self.assertIn("stream_dma_reset_sender", plans["stream_dma_reset_fault"])
        self.assertIn(
            "stream_clean_after_dma_reset",
            plans["stream_dma_reset_recovery_64m"],
        )
        self.assertIn(
            "stream_service_reset_receiver",
            plans["stream_service_reset_fault"],
        )
        self.assertIn(
            "stream_clean_after_service_reset",
            plans["stream_service_reset_recovery_64m"],
        )
        self.assertIn("P10FF_WINDOW sustained_300s_f2r 300 0 15", plans["performance"])
        self.assertIn("P10FF_WINDOW sustained_300s_r2f 300 1 15", plans["performance"])
        self.assertIn("P10FF_FORMAL stationary_30min 1800", plans["formal_30min"])
        self.assertNotIn("67108864", plans["formal_30min"])

        ranges: list[tuple[int, int, str]] = []
        for stage, text in plans.items():
            for line in text.splitlines():
                fields = line.split()
                if not fields or fields[0].startswith("#"):
                    continue
                if fields[0] == "CASE" and stage not in runner.BASE_STAGES:
                    if int(fields[2], 0) in (3, 13):
                        self.assertLessEqual(
                            int(fields[9], 0), runner.MAX_COMMAND_BYTES
                        )
                if fields[0] == "P10FF_TOTAL":
                    total = int(fields[2], 0)
                    first = int(fields[6], 0)
                    count = total // runner.MAX_COMMAND_BYTES
                    ranges.append((first, first + count - 1, f"{stage}:{fields[1]}"))
        ranges.sort()
        for prior, current in zip(ranges, ranges[1:]):
            self.assertLess(prior[1], current[0], f"{prior[2]} / {current[2]}")

    def test_functional_diagnostics_remain_explicitly_bounded_and_snapshotted(self) -> None:
        plans = runner.build_plans()
        maximum = 0
        for stage in runner.BASE_STAGES:
            for line in plans[stage].splitlines():
                fields = line.split()
                if fields and fields[0] == "CASE" and int(fields[2], 0) in (3, 13):
                    maximum = max(maximum, int(fields[9], 0))
        self.assertEqual(maximum, runner.MAX_FUNCTIONAL_DIAGNOSTIC_BYTES)
        tcl = runner.STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("if {$p10_campaign_p103f} {", tcl)
        self.assertIn("p10ff_assert_safety $case_label", tcl)
        self.assertIn("if {$p10_campaign_p103f} {", tcl)
        self.assertIn("p10ff_run_window [lindex $record 1]", tcl)
        self.assertIn("$lane < 1", tcl)
        self.assertIn("set next_object_id $p10ff_window_next_object_id", tcl)

    def test_controlled_fault_kills_before_forensic_archive_and_shutdown_reprogram(self) -> None:
        plans = runner.build_plans()
        self.assertIn(
            "P10FF_ABORT_FAULT controlled_terminal_abort 0 15 262144",
            plans["fault_capture"],
        )
        tcl = runner.STAGE_TCL.read_text(encoding="utf-8")
        for token in (
            "proc p10ff_abort_fault",
            "proc p10ff_verify_terminal_fault",
            "P10_3F_FAULT_KILL_BEFORE_FORENSIC_READ=PASS",
            "controlled fault observed no final physical TX event",
            "controlled fault pre-read shutdown evidence failed",
            "P10_3F_FAULT_CAPTURE_LEFT_FROZEN=1",
        ):
            self.assertIn(token, tcl)
        source = Path(runner.__file__).read_text(encoding="utf-8")
        capture = source.index("forensic_summary = capture_and_archive(")
        shutdown = source.index(
            'after = guarded_shutdown(run_root, auth, artifacts, f"{stage}_after", env)'
        )
        self.assertLess(capture, shutdown)
        self.assertIn("clear_frozen_capture_before_shutdown_program\": False", source)
        forensic_tcl = runner.FORENSIC_TCL.read_text(encoding="utf-8")
        self.assertIn("proc p10ff_abort_before_capture", forensic_tcl)
        self.assertIn("P10_FF_ABORT_BEFORE_CAPTURE=PASS", forensic_tcl)
        self.assertIn("abort_capture", forensic_tcl)
        self.assertIn("force_terminal_fault=True", source)
        self.assertIn("raise RuntimeError(f\"{stage} forensic archive failed\")", source)
        self.assertLess(
            runner.STAGES.index("stream_dma_reset_fault"),
            runner.STAGES.index("stream_dma_reset_recovery_64m"),
        )
        self.assertLess(
            runner.STAGES.index("stream_service_reset_fault"),
            runner.STAGES.index("stream_service_reset_recovery_64m"),
        )

    def test_custom_observation_shape_is_exact_and_bounded(self) -> None:
        plan = runner.build_plans()["staircase_1k"]
        rows = []
        sequence = 1
        for line in plan.splitlines():
            fields = line.split()
            if not fields or fields[0] != "CASE":
                continue
            row = {"label": fields[1], "window": "NA", "sequence": sequence}
            row.update(dict(zip(
                runner.base.CASE_ROW_FIELDS,
                (int(value, 0) for value in fields[2:29]),
            )))
            rows.append(row)
            sequence += 1
        rows.append({
            "label": "staircase_1k_endpoint_shutdown",
            "window": "NA",
            "sequence": sequence,
            "command": 10,
        })
        self.assertEqual(
            runner.validate_custom_observation_shape("staircase_1k", rows, plan),
            [],
        )
        rows[0]["size"] = runner.MAX_COMMAND_BYTES + 1
        self.assertTrue(any(
            "differs from immutable plan" in error
            for error in runner.validate_custom_observation_shape(
                "staircase_1k", rows, plan
            )
        ))

    def test_manifest_verification_rejects_tamper_and_extra_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run_root = Path(directory) / "p10_3f_full_test"
            (run_root / "final").mkdir(parents=True)
            evidence = run_root / "evidence.bin"
            evidence.write_bytes(b"immutable")
            runner.evidence_manifest(run_root, "PASS")
            self.assertEqual(runner.verify_evidence_manifest(run_root), [])
            evidence.write_bytes(b"tampered")
            self.assertTrue(any(
                "hash/size mismatch" in error
                for error in runner.verify_evidence_manifest(run_root)
            ))
            evidence.write_bytes(b"immutable")
            runner.evidence_manifest(run_root, "PASS")
            (run_root / "late.txt").write_text("late", encoding="ascii")
            self.assertTrue(any(
                "file-set mismatch" in error
                for error in runner.verify_evidence_manifest(run_root)
            ))

    def test_goal_named_publication_set_is_complete(self) -> None:
        required = {
            "module_intake", "raw_8x8", "per_lane_phy",
            "two_lane_regression", "four_lane_raw", "mask_matrix",
            "degraded_modes", "arq_scheduler", "dma_ddr_cache",
            "streaming_64m", "performance", "formal_30min",
        }
        self.assertEqual(set(runner.PUBLISHED_STAGE_GROUPS), required)
        source = Path(runner.__file__).read_text(encoding="utf-8")
        self.assertIn('GENERATED / f"p10_3_{name}"', source)
        for name in (
            "p10_3_shutdown", "p10_3_evidence_consistency",
            "p10_3_final_summary",
            "p10_3f_hardware/final/summary",
        ):
            self.assertIn(name, source)

    def test_tcl_sources_are_parser_complete(self) -> None:
        result = subprocess.run(
            runner.OFFLINE_GATE_COMMANDS["tcl_syntax_complete"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("TCL_COMPLETENESS_GATE=PASS", result.stdout)

    def test_exact_board_module_and_forbidden_scope(self) -> None:
        self.assertEqual(
            runner.MODULE_BINDING,
            {
                "F0": "A0019",
                "F1": "B0012",
                "F2": "B0001",
                "F3": "B0020",
                "R0": "A0010",
                "R1": "A0017",
                "R2": "B0023",
                "R3": "B0025",
            },
        )
        self.assertEqual(runner.EXPECTED_FIXED_SERIAL, "210249855178")
        self.assertEqual(runner.EXPECTED_ROTATING_SERIAL, "210512180081")
        self.assertEqual(runner.MAX_COMMAND_BYTES, 256 * 1024)
        self.assertEqual(runner.STAGE_TIMEOUT["formal_30min"], 2100)
        source = Path(runner.__file__).read_text(encoding="utf-8")
        for token in (
            '"ethernet": True',
            '"movement": True',
            '"rotation": True',
            '"realignment": True',
            '"rewiring": True',
            '"lane_mask_above_0xF": True',
            '"two_hour_test": True',
            '"p11": True',
            '"manual_instrumentation": "OMITTED_BY_USER"',
        ):
            self.assertIn(token, source)

    def test_base_artifact_bundle_is_exact_and_old_hardware_is_not_inherited(self) -> None:
        freeze, artifacts, errors = runner.validate_artifact_freeze()
        self.assertEqual(errors, [])
        self.assertEqual(freeze["source_commit"],
                         "5b2e9e8a22038b15308faf435163f1787054f41d")
        self.assertEqual(freeze["allowed_hardware_stages"], ["staircase", "formal"])
        self.assertFalse(freeze["old_hardware_pass_inherited"])
        self.assertEqual(len(artifacts), 10)

    def test_goal_named_static_intake_matches_current_canonical_inputs(self) -> None:
        self.assertEqual(runner.validate_static_intake_evidence(), [])
        self.assertTrue(set(runner.STATIC_INTAKE_FILES).issubset(runner.HOST_INPUTS))
        self.assertIn(
            ROOT / "scripts/prepare_p10_3_offline.py", runner.HOST_INPUTS
        )

    def test_missing_new_authorization_fails_closed_without_hardware(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(runner.__file__)),
                "--run-id",
                "p10_3f_full_20260804T000000Z_deadbeef_deadbeef_deadbeef",
                "--authorization",
                str(ROOT / "config/does_not_exist.json"),
                "--validate-only",
            ],
            cwd=ROOT,
            env={
                **os.environ,
                "NO_HARDWARE": "1",
                "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
            },
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("authorization/campaign freeze read failed", result.stdout)
        self.assertFalse((ROOT / "evidence/hardware/p10_3f_full/"
                          "p10_3f_full_20260804T000000Z_deadbeef_"
                          "deadbeef_deadbeef").exists())


if __name__ == "__main__":
    unittest.main()
