from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
import re
import tempfile
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_p10_4_hardware as p10  # noqa: E402


class P104PlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.plans = p10.build_plans(p10.baseline_config())

    def records(self, stage: str) -> list[list[str]]:
        return [line.split() for line in self.plans[stage].splitlines()
                if line.strip() and not line.lstrip().startswith("#")]

    def test_stage_order_and_lint(self) -> None:
        self.assertEqual(tuple(self.plans), p10.STAGES)
        self.assertEqual(p10.validate_plans(), [])
        self.assertEqual(len(p10.STAGES), 52)
        self.assertEqual(
            self.records("counter_local_source")[0][:2],
            ["CASE", "counter_local_source_endpoint_shutdown"],
        )
        hashes = p10.allowed_plan_sha256()
        self.assertEqual(set(hashes), {
            str(item["name"]) for item in p10.candidate_configs()
        })
        self.assertTrue(all(set(item) == set(p10.STAGES)
                            for item in hashes.values()))
        self.assertNotEqual(
            hashes["p10_3_baseline"]["half_duplex"],
            hashes["buffers8_batch16"]["half_duplex"],
        )

    def test_exact_streaming_counts(self) -> None:
        stream64 = [row for row in self.records("streaming_64m")
                    if row[0] == "P10FF_TOTAL"]
        stream128 = [row for row in self.records("streaming_128m")
                     if row[0] == "P10FF_TOTAL"]
        self.assertEqual(len(stream64), 20)
        self.assertEqual(len(stream128), 6)
        self.assertEqual({int(row[2]) for row in stream64}, {64 << 20})
        self.assertEqual({int(row[2]) for row in stream128}, {128 << 20})
        self.assertEqual(sum(int(row[3]) == 0 for row in stream64), 10)
        self.assertEqual(sum(int(row[3]) == 1 for row in stream64), 10)

    def test_reset_recovery_multiplicity(self) -> None:
        for role in ("fixed", "rotating"):
            rows = self.records(f"ps_reset_{role}")
            self.assertEqual(sum(row[0] == "P101_PSRESET" for row in rows), 5)
            self.assertEqual(sum(row[0] == "P10FF_TOTAL" for row in rows), 5)
            for index in range(1, 6):
                fault = self.records(f"dma_reset_{role}_{index}")
                recovery = self.records(f"dma_recovery_{role}_{index}")
                cases = [row for row in fault if row[0] == "CASE"]
                self.assertEqual(len(cases), 1)
                self.assertTrue(int(cases[0][4]) & p10.base.p101.FLAG_DMA_RESET_SENDER)
                self.assertEqual(sum(row[0] == "P10FF_TOTAL" for row in recovery), 1)
            for index in range(1, 4):
                fault = self.records(f"pl_reset_{role}_{index}")
                recovery = self.records(f"pl_recovery_{role}_{index}")
                cases = [row for row in fault if row[0] == "CASE"]
                self.assertEqual(len(cases), 1)
                self.assertTrue(int(cases[0][4]) & p10.base.p101.FLAG_PL_RESET_LOCAL_TX)
                self.assertEqual(sum(row[0] == "P10FF_TOTAL" for row in recovery), 1)

    def test_masks_and_formal_bounds(self) -> None:
        for stage, text in self.plans.items():
            for row in (line.split() for line in text.splitlines() if line.strip()):
                if row[0] == "CASE":
                    self.assertLessEqual(int(row[5], 0), 0xF, stage)
                elif row[0] in {"P10FF_TOTAL", "P10FF_WINDOW"}:
                    self.assertLessEqual(int(row[4], 0), 0xF, stage)
        self.assertEqual(self.records("mixed_30min")[-1],
                         ["P104_MIXED_FORMAL", "mixed_30min", "1800"])
        self.assertEqual(self.records("two_plus_two"),
                         [["P104_TWO_PLUS_TWO_PROBE", "two_plus_two", "300"]])
        self.assertIn("two_plus_two", p10.NONBLOCKING_STAGES)
        source = Path(p10.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "2+2 simultaneous opposite-direction transport is unsupported",
            source,
        )
        self.assertIn("measured_model_ratio", source)
        self.assertIn("measured_airtime_ceiling_ratio", source)

    def test_tuning_is_bounded_and_safety_parameters_are_immutable(self) -> None:
        candidates = p10.candidate_configs()
        self.assertLessEqual(len(candidates), 12)
        rows = self.records("tuning")
        self.assertEqual(sum(row[0] == "P104_CONFIG" for row in rows), len(candidates))
        self.assertEqual(sum(row[0] == "P10FF_WINDOW" for row in rows), 2 * len(candidates))
        for row in rows:
            if row[0] == "P10FF_WINDOW":
                self.assertEqual(int(row[2]), 30)
            elif row[0] == "P104_CONFIG":
                self.assertEqual(int(row[6]), 32)
                self.assertEqual(int(row[7]), 32)

    def test_window_timing_separates_terminal_activity_from_evidence_latency(self) -> None:
        tcl = p10.STAGE_TCL.read_text(encoding="utf-8")
        execute = tcl[
            tcl.index("proc p10_execute_case"):
            tcl.index("proc p10_p101_case")
        ]
        window = tcl[
            tcl.index("proc p10ff_run_bounded_window"):
            tcl.index("proc p10ff_run_formal")
        ]
        self.assertIn(
            "set p10_last_case_active_elapsed_ms [expr {", execute
        )
        self.assertLess(
            execute.index("set p10_last_case_active_elapsed_ms [expr {"),
            execute.index("set fixed_dump [p10_dump_mailbox"),
        )
        self.assertIn(
            "incr active_ms $p10_last_case_active_elapsed_ms", window
        )
        self.assertIn("p10ff_assert_safety $case_label", window)
        self.assertLess(
            window.index("p10ff_assert_safety $case_label"),
            window.index("set observed_finished [clock milliseconds]"),
        )
        self.assertIn(
            "$observation_overrun_ms > $p10ff_observation_overrun_limit_ms",
            window,
        )
        self.assertIn("observation_overrun_ms:$observation_overrun_ms", window)
        self.assertIn("set p10ff_observation_overrun_limit_ms 15000", tcl)
        self.assertIn(
            'error "P10.3F post-terminal observation overrun exceeded bound"',
            window,
        )

    def test_frozen_model_check_retains_ancestor_provenance(self) -> None:
        environment = {
            **os.environ,
            "NO_HARDWARE": "1",
            "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false",
        }
        result = subprocess.run(
            [sys.executable, "scripts/model_p10_4.py", "--check"],
            cwd=ROOT,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_remediation_inputs_are_hashed_after_regenerating_gates(self) -> None:
        freeze = (
            ROOT / "scripts/freeze_p10_4_artifacts.py"
        ).read_text(encoding="utf-8")
        runner = Path(p10.__file__).read_text(encoding="utf-8")
        for name in (
            "crc_bad_diagnosis",
            "crc_bad_remediation",
            "connector_ack_quarantine",
        ):
            self.assertIn(f'"{name}"', freeze)
            self.assertIn(f'"{name}"', runner)
        self.assertLess(
            freeze.index("gates = {name: run_gate"),
            freeze.index("offline_inputs: dict[str, dict[str, Any]] = {}"),
        )

    def test_runtime_flag_bits_are_unique_and_local_pl_reset_is_bit_26(self) -> None:
        protocol = (
            ROOT / "software/ps_driver/p10_1_runtime_protocol.h"
        ).read_text(encoding="utf-8")
        assignments = re.findall(
            r"P10_1_RUNTIME_FLAG_([A-Z0-9_]+)\s*=\s*1U\s*<<\s*(\d+)",
            protocol,
        )
        by_bit: dict[int, list[str]] = {}
        for name, bit_text in assignments:
            by_bit.setdefault(int(bit_text), []).append(name)
        self.assertEqual(
            {bit: names for bit, names in by_bit.items() if len(names) != 1},
            {},
        )
        self.assertEqual(p10.base.p101.FLAG_ABORT_50, 1 << 25)
        self.assertEqual(p10.base.p101.FLAG_PL_RESET_LOCAL_TX, 1 << 26)
        tcl = p10.STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn(
            "(1 << 18) | (1 << 19) | (1 << 24) | (1 << 25) | (1 << 26)",
            tcl,
        )

    def test_protocol_faults_use_host_primed_first_object(self) -> None:
        extension = (
            ROOT / "software/ps_driver/p10_1_runtime_extension.inc"
        ).read_text(encoding="utf-8")
        primed_fault_text = (
            "(P10_1_RUNTIME_FLAG_DUPLICATE_SEGMENT |\n"
            "        P10_1_RUNTIME_FLAG_STALE_SEGMENT)) != 0U"
        )
        self.assertIn(primed_fault_text, extension)
        primed_fault = extension.index(primed_fault_text)
        object_zero = extension.index("recovery_ordinal = 0U;", primed_fault)
        generic_recovery = extension.index(
            "recovery_ordinal = result->object_count / 2U;",
            primed_fault,
        )
        self.assertLess(primed_fault, object_zero)
        self.assertLess(object_zero, generic_recovery)
        tcl = p10.STAGE_TCL.read_text(encoding="utf-8")
        execute = tcl[
            tcl.index("proc p10_execute_case"):
            tcl.index("proc p10_p101_case")
        ]
        self.assertLess(
            execute.index("p10_publish_case $receiver $d $sequence"),
            execute.index("p10_wait_receiver_primed $receiver $d"),
        )
        self.assertLess(
            execute.index("p10_wait_receiver_primed $receiver $d"),
            execute.index("p10_publish_case $sender $d $sequence"),
        )

    def test_vitis_build_selects_and_verifies_p10_4_role_headers(self) -> None:
        tcl = (
            ROOT / "scripts/vitis/build_p10_ax7020_runtime.tcl"
        ).read_text(encoding="utf-8")
        self.assertIn('if {$campaign eq "p10_4"}', tcl)
        self.assertIn(
            "board_profiles/ax7020_fixed_4lane/p10_4_runtime_role.h", tcl
        )
        self.assertIn(
            "board_profiles/ax7020_rotating_4lane/p10_4_runtime_role.h", tcl
        )
        builder = (
            ROOT / "scripts/build_p10_ps_runtime.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "workspace_header = app / \"src/p10_runtime_role.h\"", builder
        )
        self.assertIn(
            "Vitis workspace role header differs from the campaign-bound input",
            builder,
        )

    def test_local_source_shutdown_evidence_replays_pass(self) -> None:
        run_root = ROOT / (
            "evidence/hardware/p10_4/"
            "p10_4_20260805T124645Z_a32afe5b_6f915067_ace48b07"
        )
        stage_dir = run_root / "stages/counter_local_source"
        archived = json.loads(
            (stage_dir / "stage_summary.json").read_text(encoding="utf-8")
        )
        forensic_summary = json.loads(
            (run_root / "forensics/counter_local_source/summary.json").read_text(
                encoding="utf-8"
            )
        )
        with mock.patch.object(p10, "write_json"):
            replay = p10.evaluate_stage(
                "counter_local_source",
                stage_dir,
                archived["process"],
                forensic_summary,
                (stage_dir / "immutable.plan").read_text(encoding="ascii"),
            )
        self.assertEqual([], replay["errors"])
        self.assertEqual("PASS", replay["status"])

    def test_run_manifest_verifier_rejects_tamper_and_extra_files(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            run_root = Path(temporary)
            (run_root / "final").mkdir()
            (run_root / "sample.txt").write_text("stable\n", encoding="ascii")
            manifest = p10.evidence_manifest(run_root)
            self.assertEqual(p10.verify_evidence_manifest(run_root, manifest), [])
            (run_root / "sample.txt").write_text("tampered\n", encoding="ascii")
            self.assertTrue(p10.verify_evidence_manifest(run_root, manifest))
            (run_root / "sample.txt").write_text("stable\n", encoding="ascii")
            (run_root / "extra.txt").write_text("extra\n", encoding="ascii")
            self.assertTrue(p10.verify_evidence_manifest(run_root, manifest))


if __name__ == "__main__":
    unittest.main()
