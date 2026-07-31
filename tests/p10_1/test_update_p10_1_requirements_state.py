from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from update_p10_1_requirements_state import remove_requirement_records  # noqa: E402


class UpdateP101RequirementsStateTests(unittest.TestCase):
    def test_removes_only_exact_generated_requirement_records(self) -> None:
        source = (
            "schema_version: 1\n"
            "requirements:\n"
            "- requirement_id: KEEP-001\n"
            "  requirement_text: keep me\n"
            "- requirement_id: PERF-MEAS-001\n"
            "  requirement_text: replace me\n"
            "  artifact_hashes: []\n"
            "- requirement_id: KEEP-002\n"
            "  requirement_text: keep me too\n"
        )

        result = remove_requirement_records(source, {"PERF-MEAS-001"})

        self.assertIn("- requirement_id: KEEP-001\n", result)
        self.assertIn("- requirement_id: KEEP-002\n", result)
        self.assertNotIn("- requirement_id: PERF-MEAS-001\n", result)
        self.assertNotIn("replace me", result)

    def test_removal_is_idempotent(self) -> None:
        source = (
            "requirements:\n"
            "- requirement_id: PERF-HW-001\n"
            "  status: PENDING\n"
            "- requirement_id: KEEP-001\n"
            "  status: PASS\n"
        )

        once = remove_requirement_records(source, {"PERF-HW-001"})
        twice = remove_requirement_records(once, {"PERF-HW-001"})

        self.assertEqual(once, twice)


if __name__ == "__main__":
    unittest.main()
