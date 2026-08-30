import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from p10_tfdu_runtime_guard import RuntimeRestGuard, load_policy


class FakeTime:
    def __init__(self) -> None:
        self.monotonic = 100.0
        self.utc = datetime(2026, 8, 8, tzinfo=timezone.utc)

    def clock(self) -> float:
        return self.monotonic

    def utc_clock(self) -> datetime:
        return self.utc

    def sleep(self, seconds: float) -> None:
        self.monotonic += seconds
        self.utc += timedelta(seconds=seconds)


class RuntimeRestGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = load_policy(ROOT / "config/safety/p10_tfdu_runtime_rest_policy.yaml")
        self.temp = tempfile.TemporaryDirectory()
        self.fake = FakeTime()
        self.guard = RuntimeRestGuard(
            self.policy,
            Path(self.temp.name) / "ledger.json",
            ("F0", "F1", "F2", "F3", "R0", "R1", "R2", "R3"),
            clock=self.fake.clock,
            sleeper=self.fake.sleep,
            utc_clock=self.fake.utc_clock,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_half_runtime_cooldown_is_enforced(self) -> None:
        self.guard.begin_stage("raw_forward", 300)
        self.fake.sleep(12.345)
        entry = self.guard.finish_stage(shutdown_verified=True)
        self.assertEqual(entry["required_cooldown_seconds"], 6.173)
        with self.assertRaisesRegex(RuntimeError, "cooldown"):
            self.guard.begin_stage("raw_reverse", 300)
        self.guard.wait_for_cooldown()
        self.guard.begin_stage("raw_reverse", 300)

    def test_stage_over_30_minutes_is_rejected_before_tx(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "exceeds"):
            self.guard.begin_stage("unsafe", 1800.001)

    def test_missing_shutdown_fails_closed(self) -> None:
        self.guard.begin_stage("stage", 300)
        self.fake.sleep(1)
        with self.assertRaisesRegex(RuntimeError, "shutdown-after"):
            self.guard.finish_stage(shutdown_verified=False)
        with self.assertRaisesRegex(RuntimeError, "fail-closed"):
            self.guard.begin_stage("later", 300)

    def test_public_ledger_has_no_process_local_clock_fields(self) -> None:
        self.guard.begin_stage("stage", 300)
        self.fake.sleep(2)
        self.guard.finish_stage(shutdown_verified=True)
        self.guard.wait_for_cooldown()
        ledger = self.guard.public_ledger()
        self.assertEqual(ledger["status"], "PASS")
        self.assertNotIn("_shutdown_monotonic", ledger["stages"][0])

    def test_hardware_measured_runtime_sets_rest_and_preserves_wall_time(self) -> None:
        self.guard.begin_stage("stage", 300)
        self.fake.sleep(20)
        entry = self.guard.finish_stage(
            shutdown_verified=True, measured_runtime_seconds=12.25)
        self.assertEqual(entry["measured_runtime_seconds"], 12.25)
        self.assertEqual(entry["wall_runtime_seconds"], 20.0)
        self.assertEqual(entry["required_cooldown_seconds"], 6.125)
        self.assertEqual(entry["runtime_measurement_source"],
                         "hardware_stage_active_evidence")

    def test_exact_tx_capable_limit_uses_conservative_envelope_for_rest(self) -> None:
        self.guard.begin_stage("formal", 1800)
        self.fake.sleep(1800.5)
        entry = self.guard.finish_stage(
            shutdown_verified=True,
            measured_runtime_seconds=1800.336,
            tx_capable_runtime_seconds=1800.0,
        )
        self.assertEqual(entry["tx_capable_runtime_seconds"], 1800.0)
        self.assertEqual(entry["measured_runtime_seconds"], 1800.336)
        self.assertEqual(entry["runtime_limit_status"], "PASS")
        self.assertEqual(entry["required_cooldown_seconds"], 900.168)
        self.guard.wait_for_cooldown()
        self.assertEqual(self.guard.public_ledger()["status"], "PASS")

    def test_over_limit_shutdown_still_rests_and_remains_fail_closed(self) -> None:
        self.guard.begin_stage("formal", 1800)
        self.fake.sleep(1800.5)
        with self.assertRaisesRegex(RuntimeError, "exceeded"):
            self.guard.finish_stage(
                shutdown_verified=True,
                measured_runtime_seconds=1800.336,
                tx_capable_runtime_seconds=1800.001,
            )
        self.guard.wait_for_cooldown()
        ledger = self.guard.public_ledger()
        self.assertEqual(ledger["status"], "FAIL")
        self.assertEqual(ledger["stages"][0]["runtime_limit_status"], "FAIL")
        self.assertEqual(ledger["stages"][0]["cooldown_status"], "PASS")
        self.assertEqual(ledger["stages"][0]["required_cooldown_seconds"], 900.168)
        with self.assertRaisesRegex(RuntimeError, "fail-closed"):
            self.guard.begin_stage("later", 1)

    def test_invalid_tx_interval_still_rests_from_conservative_envelope(self) -> None:
        self.guard.begin_stage("stage", 300)
        self.fake.sleep(100)
        with self.assertRaisesRegex(RuntimeError, "invalid hardware TX-capable"):
            self.guard.finish_stage(
                shutdown_verified=True,
                measured_runtime_seconds=90.0,
                tx_capable_runtime_seconds=90.001,
            )
        self.guard.wait_for_cooldown()
        ledger = self.guard.public_ledger()
        self.assertEqual(ledger["status"], "FAIL")
        self.assertEqual(ledger["stages"][0]["required_cooldown_seconds"], 45.0)
        self.assertEqual(ledger["stages"][0]["cooldown_status"], "PASS")

    def test_invalid_external_measurement_is_archived_fail_closed(self) -> None:
        self.guard.begin_stage("stage", 300)
        self.fake.sleep(2)
        with self.assertRaisesRegex(RuntimeError, "invalid externally"):
            self.guard.finish_stage(
                shutdown_verified=True, measured_runtime_seconds=4)
        ledger = self.guard.public_ledger()
        self.assertEqual(ledger["status"], "FAIL")
        self.assertEqual(ledger["stages"][0]["status"], "FAIL")


if __name__ == "__main__":
    unittest.main()
