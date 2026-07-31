from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts/finalize_p10_1_hardware_acceptance.py"


def load_module():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location(
        "finalize_p10_1_hardware_acceptance", MODULE
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FinalizeP101HardwareAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_required_stage_order_matches_authorized_campaign(self) -> None:
        self.assertEqual(
            self.module.REQUIRED_STAGES,
            (
                "preflight",
                "smoke",
                "baseline",
                "tuning",
                "pipeline",
                "streaming",
                "faults",
                "crosstalk",
                "half_duplex",
                "oneplusone",
                "formal",
            ),
        )

    def test_crosstalk_classification_uses_all_four_rx_observations(self) -> None:
        stage = {
            "raw_matrix": [
                {
                    "label": "xtalk_tx_f0_raw64",
                    "fixed_rx": [0, 0, 0, 0],
                    "rotating_rx": [0, 0, 64, 0],
                },
                {
                    "label": "xtalk_tx_f1_raw1024",
                    "fixed_rx": [0, 0, 0, 0],
                    "rotating_rx": [0, 0, 0, 1024],
                },
                {
                    "label": "xtalk_tx_r0_raw64",
                    "fixed_rx": [64, 0, 0, 0],
                    "rotating_rx": [0, 0, 0, 0],
                },
                {
                    "label": "xtalk_tx_r1_raw1024",
                    "fixed_rx": [0, 1024, 0, 0],
                    "rotating_rx": [0, 0, 0, 0],
                },
            ],
            "semantics": {
                "frame_matrix": [
                    {
                        "target_valid_frames": 1,
                        "non_target_crc_valid_frames": 0,
                    }
                ]
            },
        }
        result = self.module.crosstalk_classification(stage)
        self.assertEqual(result["near_end_echo_class"], "LOW")
        self.assertEqual(result["cross_lane_crosstalk_class"], "LOW")
        self.assertEqual(result["all_rx_ready_risk"], "ACCEPTABLE")
        self.assertEqual(result["non_target_crc_valid_false_frames"], 0)

    def test_non_target_crc_valid_frame_blocks_classification(self) -> None:
        result = self.module.crosstalk_classification(
            {
                "raw_matrix": [],
                "semantics": {
                    "frame_matrix": [
                        {
                            "target_valid_frames": 1,
                            "non_target_crc_valid_frames": 1,
                        }
                    ]
                },
            }
        )
        self.assertEqual(result["all_rx_ready_risk"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
