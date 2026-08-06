import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import run_p10_4_lane2_raw_retest as runner


class P104Lane2RawRetestTests(unittest.TestCase):
    def setUp(self) -> None:
        runner.configure_raw_helpers()

    def test_exact_two_direction_plan(self) -> None:
        plans = runner.raw.build_plans()
        self.assertEqual(tuple(plans), runner.DIRECTIONS)
        for index, direction in enumerate(runner.DIRECTIONS):
            cases = plans[direction]
            self.assertEqual([item.command for item in cases], [11, 2, 2])
            self.assertEqual([item.rawtarget for item in cases], [0, 64, 1024])
            self.assertEqual([item.lane for item in cases], [0, 4, 4])
            self.assertEqual([item.direction for item in cases], [0, index, index])

    def test_pulse_exposure_is_bounded(self) -> None:
        requested = 64 + 1024
        high_seconds = requested * 8 / 64_000_000
        self.assertAlmostEqual(high_seconds * 1_000_000, 136.0)
        self.assertLess(high_seconds, 0.001)
        self.assertEqual(8 / 1024 * 100, 0.78125)

    def test_run_id_is_content_bound(self) -> None:
        freeze = runner.p104.load_json(runner.p104.FREEZE)
        value = runner.expected_run_id(freeze)
        self.assertRegex(value, runner.RUN_RE)
        self.assertIn("l2b0008raw", value)
        self.assertIn(freeze["source_commit"][:8], value)

    def test_current_replacement_binding(self) -> None:
        self.assertEqual(runner.FIXED_MODULE_ID, "B0008")
        self.assertEqual(runner.ROTATING_MODULE_ID, "B0023")
        self.assertEqual(
            runner.raw.p103.EXPECTED_MODULE_BINDING["F2"]["small_board_id"],
            "B0008",
        )
        self.assertNotEqual(runner.AUTH.name, "p10_4_lane2_raw_retest_current_run_authorization.json")
        self.assertNotEqual(
            runner.GENERATED.name,
            "p10_4_lane2_raw_connectivity_retest",
        )

    def test_scope_is_raw_only(self) -> None:
        source = Path(runner.__file__).read_text(encoding="utf-8")
        self.assertIn("FRAMED_TRAFFIC=false", source)
        self.assertIn('LANE_MASK = 0x4', source)
        self.assertIn('TCL_STAGE = "P10_4-BASELINE_SMOKE"', source)
        self.assertNotIn("P10FF_WINDOW", source)


if __name__ == "__main__":
    unittest.main()
