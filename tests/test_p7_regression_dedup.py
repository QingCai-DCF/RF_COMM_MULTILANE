from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import run_p7_gate as subject  # noqa: E402


class P7RegressionDedupTests(unittest.TestCase):
    def _fixture(self, root: Path, source_commit: str) -> Path:
        suites = []
        definitions = (
            ("top_level_discovery", 123, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-p", "test*.py", "-v"]),
            ("tests_p7_discovery", 39, [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests/p7", "-p", "test_*.py", "-v"]),
        )
        for name, count, command in definitions:
            stdout = root / f"{name}.stdout.log"
            stderr = root / f"{name}.stderr.log"
            stdout.write_text("", encoding="utf-8")
            stderr.write_text(f"Ran {count} tests in 1.0s\n\nOK\n", encoding="utf-8")
            suites.append(
                {
                    "name": name,
                    "command": subprocess.list2cmdline(command),
                    "invocation_count": 1,
                    "discovered_test_count": count,
                    "returncode": 0,
                    "status": "PASS",
                    "stdout": {"path": str(stdout), "sha256": subject.sha(stdout), "bytes": stdout.stat().st_size},
                    "stderr": {"path": str(stderr), "sha256": subject.sha(stderr), "bytes": stderr.stat().st_size},
                }
            )
        payload = {
            "schema": subject.REGRESSION_SCHEMA,
            "status": "PASS",
            "source_commit": source_commit,
            "dirty_worktree_before_suites": False,
            "NO_HARDWARE_ACTIONS_EXECUTED": True,
            "HARDWARE_ACCEPTANCE": "PENDING_HW",
            "FULL_SUITE_INVOCATION_COUNT": 2,
            "total_discovered_test_count": 162,
            "suite_invocation_count_by_name": {
                "top_level_discovery": 1,
                "tests_p7_discovery": 1,
            },
            "suites": suites,
        }
        path = root / "summary.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_checkpoint_accepts_exactly_once_complete_suites_and_rejects_log_tamper(self) -> None:
        (ROOT / "build").mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "build") as temp:
            root = Path(temp)
            source_commit = "a" * 40
            summary = self._fixture(root, source_commit)
            passed, result = subject.validate_regression_summary(
                summary, subject.sha(summary), source_commit
            )
            self.assertTrue(passed, result)
            Path(result["payload"]["suites"][0]["stderr"]["path"]).write_text(
                "tampered", encoding="utf-8"
            )
            passed, result = subject.validate_regression_summary(
                summary, subject.sha(summary), source_commit
            )
            self.assertFalse(passed)
            self.assertTrue(any("log hash mismatch" in item for item in result["errors"]))


if __name__ == "__main__":
    unittest.main()
