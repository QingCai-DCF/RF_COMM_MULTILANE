from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: str) -> dict:
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


class P10_1RHardwareFinalizationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.summary = load_json("evidence/generated/p10_1r_final_summary.json")
        cls.consistency = load_json(
            "evidence/generated/p10_1r_hardware_evidence_consistency.json"
        )
        cls.state = load_json("config/project_state.json")
        cls.authorization = load_json(
            "config/p10_1r_current_run_hardware_authorization.json"
        )
        cls.requirements = yaml.safe_load(
            (ROOT / "config/project_requirements.yaml").read_text(encoding="utf-8")
        )

    def test_all_mandatory_gates_pass(self) -> None:
        self.assertEqual("PASS", self.summary["status"])
        self.assertTrue(self.summary["mandatory_exit_gates"])
        self.assertEqual(
            {"PASS"}, set(self.summary["mandatory_exit_gates"].values())
        )

    def test_authorization_is_consumed_and_closed(self) -> None:
        self.assertFalse(self.authorization["current_run_hardware_authorization"])
        self.assertTrue(self.authorization["consumed"])
        self.assertTrue(self.authorization["full_campaign_completed"])
        self.assertFalse(self.authorization["reusable_for_future_run"])

    def test_pass_is_scoped_and_does_not_start_p11(self) -> None:
        self.assertEqual("PASS", self.state["p10_1r_status"])
        self.assertEqual("NOT_STARTED", self.state["p11_status"])
        self.assertFalse(self.summary["network_used"])
        self.assertTrue(self.summary["no_hardware_movement"])
        self.assertFalse(self.summary["wiring_changed"])
        self.assertGreaterEqual(
            self.summary["metrics"]["sustained_application_goodput_bps"][
                "fixed_to_rotating"
            ],
            4_000_000,
        )
        self.assertGreaterEqual(
            self.summary["metrics"]["sustained_application_goodput_bps"][
                "rotating_to_fixed"
            ],
            4_000_000,
        )

    def test_hardware_consistency_binds_all_stage_runs(self) -> None:
        self.assertEqual("PASS", self.consistency["status"])
        self.assertEqual(
            {
                "preflight",
                "echo_tail",
                "crosstalk",
                "phy_sanity",
                "ack_tuning",
                "performance",
                "streaming_64m",
                "formal_30min",
            },
            set(self.consistency["runs"]),
        )
        for run in self.consistency["runs"].values():
            self.assertEqual("PASS", run["shutdown_fixed"])
            self.assertEqual("PASS", run["shutdown_rotating"])

    def test_p10_1r_requirements_are_closed(self) -> None:
        ids = {
            "P10_1R-ECHO-001",
            "P10_1R-ECHO-002",
            "P10_1R-ECHO-003",
            "P10_1R-ECHO-004",
            "P10_1R-ECHO-005",
            "P10_1R-ECHO-006",
            "P10_1R-ACK-001",
            "P10_1R-ACK-002",
            "P10_1R-ACK-003",
            "P10_1R-ACK-004",
            "P10_1R-HOST-001",
            "P10_1R-PERF-001",
            "P10_1R-PERF-002",
            "P10_1R-STREAM-001",
            "P10_1R-STREAM-002",
            "P10_1R-SOAK-001",
        }
        by_id = {
            item["requirement_id"]: item
            for item in self.requirements["requirements"]
            if item.get("requirement_id") in ids
        }
        self.assertEqual(ids, set(by_id))
        self.assertTrue(all(item["status"] == "PASS" for item in by_id.values()))
        self.assertTrue(all(item["artifact_hashes"] for item in by_id.values()))

    def test_led_claim_remains_evidence_limited(self) -> None:
        self.assertEqual(
            "PENDING_USER_VISUAL_OR_ELECTRICAL_OBSERVATION",
            self.summary["shutdown_led_physical_confirmation"],
        )


if __name__ == "__main__":
    unittest.main()
