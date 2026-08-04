from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_p10_3_lane2_raw_retest.py"
P103_RUNNER = ROOT / "scripts/run_p10_3_ax7020_4lane_hardware.py"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"


def load_runner():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("p10_3_lane2_raw_retest", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class P103Lane2RawRetestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def test_plan_is_exactly_two_bounded_raw_only_directions(self) -> None:
        plans = self.runner.build_plans()
        self.assertEqual(tuple(plans), ("f2_to_r2", "r2_to_f2"))
        self.assertEqual(self.runner.validate_plans(), [])
        for name, expected_direction in (("f2_to_r2", 0), ("r2_to_f2", 1)):
            items = plans[name]
            self.assertEqual([item.command for item in items], [11, 2, 2])
            self.assertEqual([item.rawtarget for item in items[1:]], [64, 1024])
            self.assertTrue(all(item.lane == 4 for item in items[1:]))
            self.assertTrue(all(item.direction == expected_direction
                                for item in items[1:]))
            self.assertTrue(all(item.rate == 2 for item in items[1:]))
            self.assertTrue(all(item.spacing == 1024 for item in items[1:]))
            self.assertTrue(all(item.timeout == 30_000 for item in items[1:]))

    def test_replacement_binding_is_new_r2_without_relabeling_old_evidence(self) -> None:
        self.assertEqual(
            self.runner.p103.EXPECTED_MODULE_BINDING["R2"]["small_board_id"],
            "B0023",
        )
        inventory = (
            ROOT / "config/hardware/tfdu_module_inventory.yaml"
        ).read_text(encoding="utf-8")
        self.assertIn('installed_small_board_id: "B0023"', inventory)
        self.assertIn('removed_small_board_id: "B0015"', inventory)
        historical = (
            ROOT / "evidence/generated/p10_3_lane2_directional_connectivity_blocker.json"
        ).read_text(encoding="utf-8")
        self.assertIn('"R2": "B0015"', historical)

    def test_tcl_accepts_only_the_named_bounded_diagnostic_entry(self) -> None:
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("LANE2_RAW_RETEST", tcl)
        self.assertIn("LANE3_RAW_RETEST", tcl)
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn('TCL_STAGE = f"P10_3-LANE{lane}_RAW_RETEST"', source)
        self.assertIn('"allowed_lane_masks": [LANE_MASK]', source)
        self.assertIn('"campaign_wide_unlimited_override": False', source)
        self.assertIn('"framed_or_protocol_test": True', source)

    def test_wrapper_requires_safe_shutdown_on_every_exit_class(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        for marker in (
            '"before": True', '"between_directions": True',
            '"on_error": True', '"on_timeout": True',
            '"on_ctrl_c": True', '"on_normal_exit": True',
            '"after": True', '"verify_both": True',
            '"finally_emergency"',
        ):
            self.assertIn(marker, source)
        self.assertIn("deliberately continue", source)

    def test_lane3_mode_is_exactly_the_missing_reverse_direction(self) -> None:
        try:
            self.runner.configure_lane(3)
            plans = self.runner.build_plans()
            self.assertEqual(tuple(plans), ("r3_to_f3",))
            self.assertEqual(self.runner.validate_plans(), [])
            items = plans["r3_to_f3"]
            self.assertEqual([item.command for item in items], [11, 2, 2])
            self.assertEqual([item.rawtarget for item in items[1:]], [64, 1024])
            self.assertTrue(all(item.lane == 8 for item in items[1:]))
            self.assertTrue(all(item.direction == 1 for item in items[1:]))
            self.assertEqual(self.runner.TCL_STAGE, "P10_3-LANE3_RAW_RETEST")
            self.assertEqual(
                self.runner.AUTH.name,
                "p10_3_lane3_raw_diagnostic_current_run_authorization.json",
            )
        finally:
            self.runner.configure_lane(2)

    def test_main_campaign_plan_remains_full_and_separate(self) -> None:
        p103_source = P103_RUNNER.read_text(encoding="utf-8")
        self.assertIn('"formal_30min"', p103_source)
        self.assertNotIn('"lane2_raw_retest", "formal_30min"', p103_source)
        self.assertNotIn("lane2_raw_retest", self.runner.p103.STAGES)


if __name__ == "__main__":
    unittest.main()
