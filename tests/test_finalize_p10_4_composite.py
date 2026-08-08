import os
import unittest

from scripts import finalize_p10_4_composite as closeout


class FinalizeP104CompositeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old_no_hardware = os.environ.get("NO_HARDWARE")
        cls.old_authorization = os.environ.get("CURRENT_RUN_HARDWARE_AUTHORIZATION")
        os.environ["NO_HARDWARE"] = "1"
        os.environ["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = "false"
        cls.data = closeout.collect_and_verify()
        cls.payloads = closeout.build_payloads(cls.data)

    @classmethod
    def tearDownClass(cls):
        if cls.old_no_hardware is None:
            os.environ.pop("NO_HARDWARE", None)
        else:
            os.environ["NO_HARDWARE"] = cls.old_no_hardware
        if cls.old_authorization is None:
            os.environ.pop("CURRENT_RUN_HARDWARE_AUTHORIZATION", None)
        else:
            os.environ["CURRENT_RUN_HARDWARE_AUTHORIZATION"] = cls.old_authorization

    def test_exact_stage_join(self):
        self.assertEqual(54, len(self.data["stage_results"]))
        self.assertEqual(
            self.data["expected_stages"],
            [item["stage"] for item in self.data["stage_results"]],
        )

    def test_only_two_plus_two_is_nonblocking_failure(self):
        failed = [
            item["stage"] for item in self.data["stage_results"]
            if item["status"] != "PASS"
        ]
        self.assertEqual(["two_plus_two"], failed)
        self.assertEqual(
            "UNSUPPORTED_SINGLE_BUNDLE_DIRECTION",
            self.data["by_stage"]["two_plus_two"]["semantics"]["reason"],
        )

    def test_runtime_and_cooldown_contract(self):
        ledger = self.data["combined_ledger"]
        self.assertEqual("PASS", ledger["status"])
        self.assertEqual(54, ledger["stage_count"])
        self.assertLessEqual(ledger["maximum_measured_runtime_seconds"], 1800)
        self.assertGreaterEqual(ledger["minimum_cooldown_margin_seconds"], 0)

    def test_every_stage_has_raw_shutdown_before_and_after(self):
        sources = self.data["shutdown_sources"]
        self.assertEqual(108, len(sources))
        by_stage = {}
        for item in sources:
            self.assertEqual("PASS", item["status"])
            by_stage.setdefault(item["stage"], set()).add(item["phase"])
        self.assertEqual(
            {stage: {"before", "after"} for stage in self.data["expected_stages"]},
            by_stage,
        )

    def test_all_hard_counters_are_zero(self):
        self.assertTrue(all(value == 0 for value in self.data["counters"].values()))

    def test_goal_status_is_truthful_nonblocking_pass(self):
        final = self.payloads["final"]
        self.assertEqual("PASS_WITH_NONBLOCKING_LIMITS", final["status"])
        self.assertEqual("FAIL_WITH_EVIDENCE", final["TWO_PLUS_TWO_EXPERIMENT"])
        self.assertFalse(final["TWO_PLUS_TWO_TX_EXECUTED"])
        self.assertEqual([], final["FAIL"])


if __name__ == "__main__":
    unittest.main()
