from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/finalize_p10_1_hardware_campaign.py"


def load_module():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "finalize_p10_1_hardware_campaign", MODULE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FinalizeP101HardwareCampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()
        cls.selection = cls.module.load_json(cls.module.SELECTION)
        (
            cls.validation_errors,
            cls.stages,
            cls.stage_records,
            cls.core_records,
            cls.run_audit,
        ) = cls.module.validate_selected_runs(cls.selection)

    def test_terminal_selection_has_one_source_for_every_required_stage(self) -> None:
        selected = [
            stage
            for run in self.selection["runs"]
            for stage in run["selected_stages"]
        ]
        self.assertCountEqual(selected, self.module.REQUIRED_STAGES)
        self.assertEqual(len(selected), len(set(selected)))

    def test_selected_raw_hashes_authorizations_and_shutdowns_validate(self) -> None:
        self.assertEqual(self.validation_errors, [])
        self.assertEqual(len(self.run_audit), 5)
        self.assertTrue(
            all(item["shutdown_fixed"] == "PASS" for item in self.run_audit)
        )
        self.assertTrue(
            all(item["shutdown_rotating"] == "PASS" for item in self.run_audit)
        )

    def test_cross_run_endpoint_coverage_is_520(self) -> None:
        details = self.module.all_paired_details(self.stages)
        self.assertEqual(len(details), 260)
        self.assertEqual(len(details) * 2, 520)
        self.assertEqual(
            self.module.lane_maxima(details, "duty_hard_fault_after"),
            [0, 0, 0, 0],
        )
        self.assertEqual(
            self.module.lane_maxima(details, "tx_high_max_after"),
            [16, 16, 16, 16],
        )

    def test_formal_goodput_and_bottleneck_are_directly_reproducible(self) -> None:
        directions = self.module.window_by_direction(self.stages["formal"])
        self.assertAlmostEqual(
            directions[0]["active_application_goodput_bps"],
            2_587_436.3002872,
        )
        self.assertAlmostEqual(
            directions[1]["active_application_goodput_bps"],
            2_585_671.4991892674,
        )
        self.assertFalse(directions[0]["host_not_in_fast_path"])
        self.assertFalse(directions[1]["host_not_in_fast_path"])
        self.assertGreater(
            self.module.summarize_formal_bottleneck(
                self.stages["formal"], 0
            )["ack_wait_to_pl_elapsed_ratio"],
            0.90,
        )

    def test_frozen_offline_tag_blob_is_pass(self) -> None:
        value, record = self.module.git_json_record(
            self.module.OFFLINE_EVIDENCE,
            "evidence/generated/p10_1_final_summary.json",
        )
        self.assertEqual(value["status"], "PASS")
        self.assertEqual(record["evidence_role"], "FROZEN_GIT_BLOB")
        self.assertEqual(len(record["sha256"]), 64)

    def test_terminal_summary_preserves_failure_and_consumed_authorization(self) -> None:
        summary = self.module.load_json(
            self.module.GENERATED
            / "p10_1_hw_campaign_terminal_summary.json"
        )
        authorization = self.module.load_json(self.module.CURRENT_AUTHORIZATION)
        self.assertEqual(summary["status"], "FAIL")
        self.assertEqual(summary["SHUTDOWN_FIXED"], "PASS")
        self.assertEqual(summary["SHUTDOWN_ROTATING"], "PASS")
        self.assertEqual(summary["non_target_crc_valid_false_frames"], 16_984)
        self.assertFalse(summary["p11_hardware_ready"])
        self.assertFalse(authorization["current_run_hardware_authorization"])
        self.assertTrue(authorization["consumed"])
        self.assertEqual(
            summary["artifact_hashes"]["fixed:elf"]["sha256"],
            "17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728",
        )
        self.assertEqual(
            summary["artifact_hashes"]["rotating:elf"]["sha256"],
            "88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0",
        )


if __name__ == "__main__":
    unittest.main()
