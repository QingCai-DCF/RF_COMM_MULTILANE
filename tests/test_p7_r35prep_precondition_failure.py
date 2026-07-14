from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "generated" / "p7_r35prep_precondition_failure.json"
PACKAGE = ROOT / "evidence" / "generated" / "p7_r35prep_precondition_failure"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8", errors="strict"))
    if not isinstance(value, dict):
        raise AssertionError(f"JSON root is not an object: {path}")
    return value


class P7R35PrepPreconditionFailureTests(unittest.TestCase):
    def test_once_only_failure_is_hash_exact_and_non_hardware(self) -> None:
        manifest = load_json(MANIFEST)
        summary = load_json(PACKAGE / "complete_suite_summary.json")

        self.assertEqual("FAIL_PRECONDITION", manifest["status"])
        self.assertEqual(manifest["source_commit"], summary["source_commit"])
        self.assertEqual(manifest["source_commit_after_suites"], summary["source_commit_after_suites"])
        self.assertTrue(summary["source_commit_unchanged"])
        self.assertFalse(summary["dirty_worktree_before_suites"])
        self.assertFalse(summary["dirty_worktree_after_suites"])
        self.assertTrue(summary["NO_HARDWARE_ACTIONS_EXECUTED"])
        self.assertEqual("PENDING_HW", summary["HARDWARE_ACCEPTANCE"])
        self.assertFalse(manifest["same_source_complete_suite_rerun_permitted"])
        self.assertTrue(manifest["next_checkpoint_requires_new_source_commit"])

        suites = {item["name"]: item for item in summary["suites"]}
        self.assertEqual(1, suites["top_level_discovery"]["invocation_count"])
        self.assertEqual(190, suites["top_level_discovery"]["discovered_test_count"])
        self.assertEqual("FAIL", suites["top_level_discovery"]["status"])
        self.assertEqual(1, suites["tests_p7_discovery"]["invocation_count"])
        self.assertEqual(42, suites["tests_p7_discovery"]["discovered_test_count"])
        self.assertEqual("PASS", suites["tests_p7_discovery"]["status"])

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
        self.assertEqual(
            portable["tree_sha256"],
            hashlib.sha256("".join(sorted(records)).encode("utf-8")).hexdigest(),
        )

        stderr = (PACKAGE / "top_level_discovery.stderr.log").read_text(
            encoding="utf-8", errors="strict"
        )
        self.assertIn("AssertionError: 30 != 23", stderr)
        self.assertIn("test_real_generated_artifacts_pass_contract", stderr)
        self.assertIn("GENERATED", manifest["failure_causes"][1]["classification"])
        self.assertEqual(7, len(manifest["failure_causes"][0]["missing_hash_exact_files"]))


if __name__ == "__main__":
    unittest.main()
