from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "generated" / "p7_r35validate_7c6b50f_precondition.json"
PACKAGE = ROOT / "evidence" / "generated" / "p7_r35validate_7c6b50f_precondition"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON root is not an object: {path}")
    return value


class P7R35ValidatePreconditionTests(unittest.TestCase):
    def test_passed_suites_and_failed_gate_are_hash_exact(self) -> None:
        manifest = load_json(MANIFEST)
        regression = load_json(PACKAGE / "complete_suite_summary.json")
        gate = load_json(PACKAGE / "canonical_gate_summary.json")
        readiness = load_json(PACKAGE / "ps_core_readiness.json")
        board = load_json(PACKAGE / "generated_board_contract.json")
        p6_build = load_json(PACKAGE / "fresh_p6_cache_bypass_build_summary.json")
        p7_build = load_json(PACKAGE / "fresh_p7_cache_bypass_build_summary.json")

        self.assertEqual("PASS", regression["status"])
        self.assertEqual(manifest["source_commit"], regression["source_commit"])
        self.assertTrue(regression["source_commit_unchanged"])
        self.assertFalse(regression["dirty_worktree_before_suites"])
        self.assertFalse(regression["dirty_worktree_after_suites"])
        self.assertEqual({"top_level_discovery": 1, "tests_p7_discovery": 1}, regression["suite_invocation_count_by_name"])
        self.assertEqual(233, regression["total_discovered_test_count"])
        self.assertEqual("FAIL", gate["P7_OFFLINE_GATE"])
        self.assertEqual(["P7_PS_CORE_HARDWARE_READINESS"], [name for name, passed in gate["checks"].items() if not passed])
        self.assertEqual("FAIL", readiness["P7_PS_CORE_HARDWARE_READINESS"])
        self.assertEqual(
            ["stage62_only_microtest_bypasses_pl_and_is_disassembly_bound"],
            [name for name, passed in readiness["checks"].items() if not passed],
        )
        self.assertEqual(0, readiness["unit_tests"]["invocation_count_in_core_gate"])
        self.assertEqual("PASS", board["status"])
        self.assertEqual([], board["errors"])
        self.assertEqual("PASS", p6_build["P6_PS_CANDIDATE_BUILD"])
        self.assertTrue(p6_build["cache_bypass"])
        self.assertEqual("PASS", p7_build["P7_PS_RUNTIME_BUILD"])
        self.assertTrue(p7_build["cache_bypass"])
        self.assertFalse(p7_build["hardware_actions_executed"])

        portable = manifest["portable_raw_evidence"]
        records: list[str] = []
        byte_count = 0
        for record in portable["files"]:
            path = PACKAGE / record["path"]
            self.assertTrue(path.is_file(), path)
            self.assertEqual(record["bytes"], path.stat().st_size)
            self.assertEqual(record["sha256"], sha256(path))
            byte_count += path.stat().st_size
            records.append(f"{record['path']}\t{record['bytes']}\t{record['sha256']}\n")
        self.assertEqual(portable["file_count"], len(records))
        self.assertEqual(portable["byte_count"], byte_count)
        self.assertEqual(portable["tree_sha256"], hashlib.sha256("".join(sorted(records)).encode("utf-8")).hexdigest())

        wrapper = (ROOT / "scripts" / "hw" / "run_p7_ps_application_stage_safe.py").read_text(encoding="utf-8")
        self.assertIn('(\"P7_EXECUTION_SCOPE\", \"STAGE62_ONLY\")', wrapper)
        self.assertIn('(\"P7_EXECUTION_SCOPE\", \"P7_PS_APPLICATION_STAGE\")', wrapper)


if __name__ == "__main__":
    unittest.main()
