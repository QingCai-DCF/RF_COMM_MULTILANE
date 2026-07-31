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

    def test_empty_crosstalk_matrix_is_not_measured(self) -> None:
        result = self.module.crosstalk_classification(
            {"raw_matrix": [], "semantics": {"frame_matrix": []}}
        )
        self.assertEqual(result["near_end_echo_class"], "NOT_MEASURED")
        self.assertEqual(result["cross_lane_crosstalk_class"], "NOT_MEASURED")
        self.assertEqual(result["all_rx_ready_risk"], "NOT_MEASURED")

    def test_common_context_uses_run_authorization_artifacts(self) -> None:
        authorization = {
            "source_commit": "authorized-source",
            "artifacts": [
                {
                    "role": "fixed",
                    "kind": "functional_bitstream",
                    "path": "authorized-fixed.bit",
                    "sha256": "a" * 64,
                    "bytes": 123,
                },
                {
                    "role": "fixed",
                    "kind": "elf",
                    "path": "authorized-fixed.elf",
                    "sha256": "b" * 64,
                    "bytes": 456,
                },
            ],
            "input_hashes": {},
        }
        latest = {
            "artifacts": [
                {
                    "role": "fixed",
                    "kind": "performance_bitstream",
                    "path": "newer-fixed.bit",
                    "sha256": "c" * 64,
                    "bytes": 789,
                }
            ]
        }
        context = self.module.common_context("run-1", authorization, latest)
        self.assertEqual(
            context["artifact_hashes"]["fixed:performance_bitstream"]["path"],
            "authorized-fixed.bit",
        )
        self.assertEqual(
            context["artifact_hashes"]["fixed:elf"]["path"],
            "authorized-fixed.elf",
        )
        self.assertNotIn(
            "newer-fixed.bit",
            {
                item["path"]
                for item in context["artifact_hashes"].values()
            },
        )

    def test_missing_stage_is_fail_with_not_run_disposition(self) -> None:
        run_root = ROOT / "does-not-exist"
        orchestrator_path = ROOT / "PROJECT_STATUS.md"
        payload, source = self.module.stage_record(
            run_root,
            "formal",
            orchestrator={"stages": {"formal": "NOT_RUN"}},
            orchestrator_path=orchestrator_path,
        )
        self.assertEqual(payload["status"], "FAIL")
        self.assertEqual(payload["execution_status"], "NOT_RUN")
        self.assertEqual(payload["disposition"], "NOT_RUN_DUE_PRIOR_STAGE_FAILURE")
        self.assertEqual(source["stage"], "formal")


if __name__ == "__main__":
    unittest.main()
