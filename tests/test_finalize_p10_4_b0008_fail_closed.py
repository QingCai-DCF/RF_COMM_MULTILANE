#!/usr/bin/env python3
"""Offline-only tests for the terminal P10.4 B0008 closeout."""

from __future__ import annotations

import importlib.util
import os
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts/finalize_p10_4_b0008_fail_closed.py"
SPEC = importlib.util.spec_from_file_location("p10_4_b0008_closeout", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
closeout = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(closeout)


class P104B0008FailClosedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        os.environ["NO_HARDWARE"] = "1"
        os.environ["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
        cls.data = closeout.collect_and_verify()
        cls.payloads = closeout.build_payloads(cls.data)

    def test_all_immutable_manifests_and_authorizations_verify(self) -> None:
        self.assertEqual(set(self.data["manifests"]), {
            "qualification", "full_campaign", "isolated_lane_recovery",
            "isolated_echo_crosstalk",
        })
        self.assertTrue(all(item["status"] == "PASS" for item in self.data["manifests"].values()))
        self.assertTrue(all(item["consumed"] for item in self.data["authorizations"].values()))
        self.assertTrue(all(
            item["current_run_hardware_authorization"] is False
            for item in self.data["authorizations"].values()
        ))

    def test_short_qualification_is_not_promoted_beyond_raw_physical(self) -> None:
        vectors = self.data["qualification_vectors"]
        self.assertEqual(len(vectors), 4)
        self.assertTrue(all(item["status"] == "PASS" for item in vectors))
        self.assertTrue(all(item["evidence_class"] == "RAW_PHYSICAL_ONLY" for item in vectors))
        blocker = self.payloads["blocker"]
        self.assertIn("DATA_PATH_PASS", blocker["not_claimed"])
        self.assertIn("COMPONENT_SPECIFIC_ROOT_CAUSE", blocker["not_claimed"])

    def test_three_current_failures_close_on_terminal_64_to_zero_vector(self) -> None:
        blocker = self.payloads["blocker"]
        self.assertEqual(blocker["reproduction_count_after_short_qualification"], 3)
        self.assertEqual(blocker["terminal_matrix_measurement"], {
            "direction": "F2_TO_R2",
            "requested_raw_pulses": 64,
            "sender_physical_tx": 64,
            "receiver_raw_rx": 0,
            "evidence_class": "RAW_PHYSICAL_ONLY",
        })
        self.assertEqual(blocker["module_binding"]["F2"], "B0008")
        self.assertEqual(blocker["module_binding"]["R2"], "B0023")

    def test_safety_and_shutdown_are_not_conflated_with_connectivity(self) -> None:
        blocker = self.payloads["blocker"]
        safety = blocker["safety_observation"]
        self.assertEqual(safety["continuous_high_max_cycles"], 8)
        self.assertEqual(safety["rolling_duty_max_cycles"], 504)
        self.assertEqual(safety["hard_fault_count"], 0)
        self.assertFalse(safety["external_electrical_or_optical_waveform_measured"])
        shutdown = self.payloads["shutdown"]
        self.assertEqual(shutdown["status"], "PASS")
        self.assertEqual(shutdown["SHUTDOWN_FIXED"], "PASS")
        self.assertEqual(shutdown["SHUTDOWN_ROTATING"], "PASS")

    def test_requirement_dispositions_are_truthful(self) -> None:
        rows = self.payloads["audit"]["requirement_disposition"]
        counts = {"PASS": 0, "FAIL": 0, "PENDING": 0}
        for row in rows:
            counts[row["status"]] += 1
        self.assertEqual(counts, {"PASS": 8, "FAIL": 3, "PENDING": 5})
        by_id = {row["requirement_id"]: row["status"] for row in rows}
        self.assertEqual(by_id["P10_4-PERF-001"], "PASS")
        self.assertEqual(by_id["P10_4-PERF-002"], "PASS")
        self.assertEqual(by_id["P10_4-PERF-003"], "FAIL")
        self.assertEqual(by_id["P10_4-DEG-001"], "FAIL")
        self.assertEqual(by_id["P10_4-XTALK-001"], "FAIL")
        self.assertEqual(by_id["P10_4-SOAK-001"], "PENDING")

    def test_p10_3_pass_is_preserved_while_p10_4_fails(self) -> None:
        final = self.payloads["final"]
        self.assertEqual(final[closeout.SCOPE], "FAIL")
        self.assertTrue(final["old_p10_3_pass_preserved"])
        self.assertFalse(final["p11_or_product_scope_promoted"])
        self.assertEqual(final["P11_STATUS"], "NOT_STARTED")
        self.assertEqual(final["NEXT_RECOMMENDED_STAGE"], "P10_4_REMEDIATION")


if __name__ == "__main__":
    unittest.main()
