from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import validate_p7_r72_failure_package as subject  # noqa: E402


class P7R72FailurePackageTests(unittest.TestCase):
    def test_exact_failure_package_is_machine_validated(self) -> None:
        result = subject.validate_package()
        self.assertEqual("PASS", result["P7_R72_STAGE66_FAILURE_PACKAGE_VALIDATION"])
        self.assertEqual("FAIL_RECOVERED", result["result"])
        self.assertFalse(result["hardware_actions_executed"])
        self.assertFalse(result["coverage_claimed"])
        self.assertEqual("PENDING_HW", result["HARDWARE_ACCEPTANCE"])
        self.assertEqual([], result["errors"])

    def test_package_tamper_fails_closed_without_hardware(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            copied = Path(directory) / "package"
            shutil.copytree(subject.DEFAULT_PACKAGE, copied)
            observation = copied / "postprocess_observation.json"
            observation.write_bytes(observation.read_bytes() + b"\n")
            result = subject.validate_package(copied)
        self.assertEqual("FAIL", result["P7_R72_STAGE66_FAILURE_PACKAGE_VALIDATION"])
        self.assertFalse(result["hardware_actions_executed"])
        self.assertTrue(result["errors"])


if __name__ == "__main__":
    unittest.main()
