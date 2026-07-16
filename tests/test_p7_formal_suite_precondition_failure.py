import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = (
    ROOT
    / "evidence"
    / "generated"
    / "p7_formal_1ca54d2_suite_precondition_failure"
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P7FormalSuitePreconditionFailureTests(unittest.TestCase):
    def test_failure_is_hash_exact_non_hardware_and_requires_new_checkpoint(self) -> None:
        classification = load_json(PACKAGE / "classification.json")
        self.assertEqual(
            classification["schema"],
            "rf-comm-p7-complete-suite-failure-classification-v1",
        )
        self.assertEqual(
            classification["source_commit"],
            "1ca54d2c55d65ce9d95aeb1ad60f3c8789700ea1",
        )
        self.assertEqual(
            classification["status"],
            "COMPLETE_SUITES_FAIL_CANONICAL_GATE_NOT_RUN",
        )
        self.assertFalse(classification["hardware_actions_executed"])
        self.assertFalse(classification["hardware_connection_attempted"])
        self.assertFalse(classification["formal_hardware_attempt_consumed"])
        self.assertFalse(classification["hardware_run_identity_generated"])
        self.assertEqual(classification["HARDWARE_ACCEPTANCE"], "PENDING_HW")
        self.assertFalse(classification["coverage_claimed"])
        self.assertFalse(classification["canonical_gate_started"])
        self.assertFalse(classification["same_source_complete_suite_rerun_permitted"])
        self.assertTrue(classification["next_checkpoint_requires_new_source_commit"])
        self.assertEqual(
            {item["classification"] for item in classification["failures"]},
            {
                "CLEAN_WORKTREE_BUILD_MATERIALIZATION_PRECONDITION",
                "STALE_TEST_EXPECTATION_AFTER_TERMINAL_LEDGER_FREEZE",
            },
        )
        for record in classification["frozen_files"]:
            path = PACKAGE / record["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_size, record["bytes"])
            self.assertEqual(sha256(path), record["sha256"])

        suite = load_json(PACKAGE / "complete_suite_summary.json")
        self.assertEqual(suite["status"], "FAIL")
        self.assertEqual(suite["source_commit"], classification["source_commit"])
        self.assertTrue(suite["source_commit_unchanged"])
        self.assertFalse(suite["dirty_worktree_before_suites"])
        self.assertFalse(suite["dirty_worktree_after_suites"])
        self.assertTrue(suite["NO_HARDWARE_ACTIONS_EXECUTED"])
        self.assertEqual(suite["HARDWARE_ACCEPTANCE"], "PENDING_HW")
        self.assertEqual(suite["FULL_SUITE_INVOCATION_COUNT"], 2)
        self.assertEqual(suite["total_discovered_test_count"], 330)
        by_name = {item["name"]: item for item in suite["suites"]}
        self.assertEqual(by_name["top_level_discovery"]["status"], "FAIL")
        self.assertEqual(by_name["top_level_discovery"]["returncode"], 1)
        self.assertEqual(by_name["top_level_discovery"]["discovered_test_count"], 287)
        self.assertEqual(by_name["tests_p7_discovery"]["status"], "PASS")
        self.assertEqual(by_name["tests_p7_discovery"]["returncode"], 0)
        self.assertEqual(by_name["tests_p7_discovery"]["discovered_test_count"], 43)


if __name__ == "__main__":
    unittest.main()
