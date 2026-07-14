import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ddr_external_master_diagnostic import (
    ADDRESS_MATRIX,
    DDR_SCRATCH_END,
    DDR_SCRATCH_START,
    DiagnosticCase,
    R37_FIXTURE_SHA256,
    R37_READBACK_SHA256,
    audit_r37_prestart_evidence,
    build_minimum_matrix,
    build_pattern,
    compare_payloads,
    materialize_case,
    parse_hex32,
    render_xsdb_transaction_plan,
    validate_scratch_range,
)


R37_BUNDLE = (
    ROOT
    / "evidence/hardware/p7/stage62_microtest"
    / "p7_20260714_stage62_microtest_r37_diag_only/bundle"
)
R37_EXPECTED = R37_BUNDLE / "stage62_microtest_destination_fixture.bin"
R37_OBSERVED = R37_BUNDLE / "stage62_microtest_destination_prestart.bin"
R37_EVIDENCE = R37_BUNDLE.parent
R37_COMMAND = ROOT / "stage62_debug/iterations/iter_04/run_command.txt"
P7_EXECUTE_TCL = ROOT / "scripts/hw/p7_ps_application_execute.tcl"


class DdrExternalMasterDiagnosticTests(unittest.TestCase):
    def test_r37_fixture_and_parser_preserve_the_exact_first_mismatch(self) -> None:
        expected = R37_EXPECTED.read_bytes()
        observed = R37_OBSERVED.read_bytes()
        self.assertEqual(256, len(expected))
        self.assertEqual(0xC3, expected[9])
        self.assertEqual(0x00, observed[9])
        self.assertEqual(
            R37_FIXTURE_SHA256,
            hashlib.sha256(expected).hexdigest(),
        )
        self.assertEqual(R37_READBACK_SHA256, hashlib.sha256(observed).hexdigest())
        result = compare_payloads(expected, observed, address=DDR_SCRATCH_START)
        self.assertFalse(result["passed"])
        self.assertEqual(1, result["mismatch_count"])
        self.assertEqual(
            {
                "offset": 9,
                "absolute_address": "0x00900009",
                "expected": 0xC3,
                "observed": 0x00,
            },
            result["first_mismatch"],
        )

    def test_cli_analyze_reads_raw_binary_without_text_or_endian_conversion(self) -> None:
        command = [
            sys.executable,
            str(ROOT / "tools/ddr_external_master_diagnostic.py"),
            "analyze",
            "--expected",
            str(R37_EXPECTED),
            "--observed",
            str(R37_OBSERVED),
            "--address",
            "0x00900000",
        ]
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        parsed = json.loads(completed.stdout)
        self.assertEqual(9, parsed["first_mismatch"]["offset"])
        self.assertEqual(195, parsed["first_mismatch"]["expected"])
        self.assertEqual(0, parsed["first_mismatch"]["observed"])

    def test_patterns_are_byte_distinguishable_nonzero_and_stable(self) -> None:
        original = R37_EXPECTED.read_bytes()
        patterns = {
            name: build_pattern(name, stage62_fixture=original)
            for name in ("stage62_fixture", "a5_5a_3c_c3", "nonzero_counter", "prbs15")
        }
        self.assertEqual(4, len(set(patterns.values())))
        for payload in patterns.values():
            self.assertEqual(256, len(payload))
            self.assertNotIn(0, payload)
        self.assertEqual(bytes((0xA5, 0x5A, 0x3C, 0xC3)) * 64, patterns["a5_5a_3c_c3"])
        self.assertEqual(bytes(range(1, 256)) + b"\x01", patterns["nonzero_counter"])

    def test_address_grammar_and_scratch_window_fail_closed(self) -> None:
        self.assertEqual(DDR_SCRATCH_START, parse_hex32("0x00900000"))
        for invalid in ("9437184", "0x900000", "00900000", "0x00900000+9"):
            with self.assertRaises(ValueError):
                parse_hex32(invalid)
        for address in ADDRESS_MATRIX:
            self.assertEqual(0, address % 64)
            validate_scratch_range(address, 256)
        with self.assertRaises(ValueError):
            validate_scratch_range(DDR_SCRATCH_START - 1, 256)
        with self.assertRaises(ValueError):
            validate_scratch_range(DDR_SCRATCH_END - 128, 256)

    def test_transaction_plans_bind_file_address_width_count_barrier_and_readback(self) -> None:
        payload = bytes((index % 255) + 1 for index in range(256))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_path = root / "fixture.bin"
            readback_path = root / "readback.bin"
            write_path.write_bytes(payload)
            plans = {
                method: render_xsdb_transaction_plan(
                    write_path=write_path,
                    readback_path=readback_path,
                    payload=payload,
                    address=DDR_SCRATCH_START,
                    access_method=method,
                )
                for method in ("download", "block", "byte", "halfword", "word")
            }
        self.assertTrue(plans["download"][0].startswith("dow -data "))
        self.assertIn(" 0x00900000", plans["download"][0])
        self.assertIn("mwr -size b -bin -file", plans["block"][0])
        self.assertTrue(plans["block"][0].endswith("0x00900000 256"))
        self.assertEqual(256 + 3, len(plans["byte"]))
        self.assertEqual(128 + 3, len(plans["halfword"]))
        self.assertEqual(64 + 3, len(plans["word"]))
        for commands in plans.values():
            self.assertIn("mrd -value -size w", commands[-3])
            self.assertIn("DDR completion read failed", commands[-2])
            self.assertIn("mrd -size b -bin -file", commands[-1])
            self.assertTrue(commands[-1].endswith("0x00900000 256"))

    def test_minimum_matrix_uses_nine_new_unique_run_ids(self) -> None:
        cases = build_minimum_matrix("p7_20260714_ddr_external_r38")
        self.assertEqual(9, len(cases))
        self.assertEqual(9, len({case.run_id for case in cases}))
        self.assertEqual({1, 2, 3}, {case.repetition for case in cases})
        self.assertEqual(
            {"stage62_fixture", "a5_5a_3c_c3", "nonzero_counter"},
            {case.pattern for case in cases},
        )
        for case in cases:
            self.assertIsInstance(case, DiagnosticCase)
            case.validate()
            self.assertFalse(case.as_dict()["coverage_claimed"])
            self.assertEqual("PENDING_HW", case.as_dict()["HARDWARE_ACCEPTANCE"])
        checked_in = json.loads(
            (ROOT / "ddr_debug/offline/pending_external_master_matrix.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual([case.as_dict() for case in cases], checked_in)

    def test_r37_audit_binds_fixture_command_tcl_and_raw_readback(self) -> None:
        result = audit_r37_prestart_evidence(
            evidence_dir=R37_EVIDENCE,
            command_file=R37_COMMAND,
            tcl_file=P7_EXECUTE_TCL,
        )
        self.assertTrue(result["passed"], result["failures"])
        self.assertTrue(result["offline_audit_only"])
        self.assertFalse(result["hardware_actions_executed_now"])
        self.assertEqual(R37_FIXTURE_SHA256, result["fixture"]["sha256"])
        self.assertEqual(R37_READBACK_SHA256, result["raw_readback"]["sha256"])
        self.assertEqual(9, result["comparison"]["first_mismatch"]["offset"])
        self.assertTrue(result["host_path_findings"]["readback_precedes_cpu_release"])
        checked_in = json.loads(
            (ROOT / "ddr_debug/offline/r37_host_prestart_audit.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result, checked_in)

    def test_materialized_case_is_new_raw_and_hash_bound(self) -> None:
        case = DiagnosticCase(
            run_id="p7_20260714_ddr_external_r38_a5_rep1",
            pattern="a5_5a_3c_c3",
            address=DDR_SCRATCH_START,
            access_method="block",
            repetition=1,
        )
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp) / "case"
            manifest = materialize_case(output_dir=output_dir, case=case)
            fixture = output_dir / "ddr_external_master_fixture.bin"
            plan = output_dir / "xsdb_transaction_plan.txt"
            self.assertEqual(bytes((0xA5, 0x5A, 0x3C, 0xC3)) * 64, fixture.read_bytes())
            self.assertEqual(hashlib.sha256(fixture.read_bytes()).hexdigest(), manifest["fixture"]["sha256"])
            self.assertEqual(hashlib.sha256(plan.read_bytes()).hexdigest(), manifest["transaction_plan"]["sha256"])
            self.assertFalse(manifest["hardware_actions_executed"])
            self.assertEqual("PENDING_HW", manifest["HARDWARE_ACCEPTANCE"])
            with self.assertRaises(FileExistsError):
                materialize_case(output_dir=output_dir, case=case)


if __name__ == "__main__":
    unittest.main()
