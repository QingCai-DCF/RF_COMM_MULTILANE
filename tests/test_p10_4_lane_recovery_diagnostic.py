from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location(
    "run_p10_4_lane_recovery_diagnostic",
    SCRIPTS / "run_p10_4_lane_recovery_diagnostic.py",
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class P104LaneRecoveryDiagnosticTests(unittest.TestCase):
    def test_selected_configuration_is_frozen_tuning_winner(self) -> None:
        selected = MODULE.selected_config()
        self.assertEqual(selected["name"], "buffers2_batch16")
        self.assertEqual(selected["ring_depth"], 32)
        self.assertEqual(selected["buffer_count"], 2)
        self.assertEqual(selected["descriptor_batch"], 16)

    def test_diagnostic_uses_exact_full_lane_recovery_plan(self) -> None:
        selected = MODULE.selected_config()
        plan = MODULE.campaign.build_plans(selected)[MODULE.STAGE]
        rows = [line.split() for line in plan.splitlines()]
        totals = [row for row in rows if row and row[0] == "P10FF_TOTAL"]
        self.assertEqual(len(totals), 8)
        self.assertEqual(
            [int(row[5], 0) for row in totals], [1, 0, 2, 0, 4, 0, 8, 0]
        )
        self.assertTrue(all(int(row[2], 0) == 64 << 20 for row in totals))
        self.assertTrue(all(int(row[4], 0) == 15 for row in totals))

    def test_diagnostic_does_not_claim_full_campaign_pass(self) -> None:
        source = (SCRIPTS / "run_p10_4_lane_recovery_diagnostic.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"full_campaign_pass_claimed": False', source)
        self.assertIn('"diagnostic_only": True', source)
        self.assertNotIn("P10_4_HARDWARE=PASS", source)

    def test_terminal_manifest_matches_exact_result_bytes(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            root = Path(temporary)
            run_root = root / "run"
            generated = root / "generated" / "summary"
            previous = MODULE.GENERATED
            MODULE.GENERATED = generated
            try:
                summary = {"status": "PASS", "errors": []}
                errors = MODULE.publish_terminal_evidence(run_root, summary)
            finally:
                MODULE.GENERATED = previous
            self.assertEqual(errors, [])
            manifest = MODULE.campaign.load_json(
                run_root / "final/run_evidence_sha256_manifest.json"
            )
            self.assertEqual(
                MODULE.campaign.verify_evidence_manifest(run_root, manifest), []
            )
            self.assertTrue(summary["evidence_manifest_verified"])


if __name__ == "__main__":
    unittest.main()
