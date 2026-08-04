from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import run_p10_3f_full_hardware as runner  # noqa: E402


class P103FFullHardwareTests(unittest.TestCase):
    def test_full_stage_order_and_plans_are_deterministic(self) -> None:
        first = runner.build_plans()
        second = runner.build_plans()
        self.assertEqual(tuple(first), runner.STAGES)
        self.assertEqual(first, second)
        self.assertEqual(runner.validate_plans(first), [])
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
        capture = source.index("forensic.capture_and_archive(stage, run_root, auth, env)")
        shutdown = source.index(
            'after = guarded_shutdown(run_root, auth, artifacts, f"{stage}_after", env)'
        )
        self.assertLess(capture, shutdown)
        self.assertIn("clear_frozen_capture_before_shutdown_program\": False", source)
        self.assertLess(
            runner.STAGES.index("stream_dma_reset_fault"),
            runner.STAGES.index("stream_dma_reset_recovery_64m"),
        )
        self.assertLess(
            runner.STAGES.index("stream_service_reset_fault"),
            runner.STAGES.index("stream_service_reset_recovery_64m"),
        )

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

    def test_missing_new_authorization_fails_closed_without_hardware(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(runner.__file__)),
                "--run-id",
                "p10_3f_full_20260804T000000Z_deadbeef",
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
                          "p10_3f_full_20260804T000000Z_deadbeef").exists())


if __name__ == "__main__":
    unittest.main()
