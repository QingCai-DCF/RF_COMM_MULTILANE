from __future__ import annotations

import hashlib
import random
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from p10_1_metrics import (  # noqa: E402
    MetricValidationError,
    finalize_metrics,
    make_metric_record,
)


ARTIFACT = hashlib.sha256(b"p10.1 metric test vector").hexdigest()


class MetricFinalizerTests(unittest.TestCase):
    def record(self, direction: str, case: str, bytes_: int, seconds: float, **kwargs):
        frequency = 64_000_000
        return make_metric_record(
            metric_name="APPLICATION_GOODPUT_BPS",
            measurement_class=kwargs.pop("measurement_class", "APPLICATION_SUSTAINED"),
            direction=direction,
            committed_application_bytes=bytes_,
            elapsed_ticks=round(seconds * frequency),
            timer_frequency=frequency,
            run_id=kwargs.pop("run_id", "formal"),
            case_id=case,
            artifact_sha256=ARTIFACT,
            **kwargs,
        )

    def test_diagnostic_never_overrides_sustained(self):
        records = [
            self.record(
                "F_TO_R", "one_byte", 1, 0.0014,
                measurement_class="DIAGNOSTIC_MICROTRANSFER", diagnostic_only=True,
            ),
            self.record("F_TO_R", "sustained_a", 32 * 1024 * 1024, 52.0),
            self.record("R_TO_F", "sustained_b", 32 * 1024 * 1024, 51.0),
        ]
        result = finalize_metrics(records, formal_run_id="formal")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["directions"]["F_TO_R"]["record_count"], 1)
        self.assertEqual(result["diagnostic_records_excluded"], 1)

    def test_missing_metric_is_pending_not_zero(self):
        result = finalize_metrics(
            [self.record("F_TO_R", "only", 16 * 1024 * 1024, 31.0)],
            formal_run_id="formal",
        )
        self.assertEqual(result["status"], "PENDING_MISSING_ELIGIBLE_DIRECTION")
        self.assertNotIn("R_TO_F", result["directions"])

    def test_failed_partial_zero_and_timer_crosscheck_are_ineligible(self):
        cases = [
            self.record("F_TO_R", "failed", 16 * 1024 * 1024, 30.0, status="FAIL"),
            self.record("F_TO_R", "partial", 1 * 1024 * 1024, 1.0),
            self.record("F_TO_R", "bad_timer", 16 * 1024 * 1024, 30.0,
                        timer_crosscheck_status="FAIL"),
        ]
        self.assertTrue(all(not item.eligible_for_scaling for item in cases))
        with self.assertRaises(MetricValidationError):
            self.record("F_TO_R", "zero", 0, 0.0)

    def test_warmup_idle_and_host_staging_are_explicit(self):
        value = self.record(
            "F_TO_R", "policies", 16 * 1024 * 1024, 30.0,
            warmup_included=True, idle_included=True, host_staging_included=True,
        )
        self.assertTrue(value.warmup_included)
        self.assertTrue(value.idle_included)
        self.assertTrue(value.host_staging_included)

    def test_timer_wrap_uses_unwrapped_64_bit_delta(self):
        frequency = 64_000_000
        start = (1 << 64) - 20
        elapsed = 40
        record = make_metric_record(
            metric_name="APPLICATION_GOODPUT_BPS",
            measurement_class="OBJECT_SINGLE",
            direction="F_TO_R",
            committed_application_bytes=1024,
            elapsed_ticks=elapsed,
            timer_frequency=frequency,
            start_timestamp=start,
            run_id="wrap",
            case_id="wrap",
            artifact_sha256=ARTIFACT,
        )
        self.assertEqual(record.end_timestamp, start + elapsed)

    def test_units_and_timestamp_mismatch_rejected(self):
        record = self.record("F_TO_R", "valid", 16 * 1024 * 1024, 30.0)
        value = record.to_dict()
        value["units"] = "byte/s"
        with self.assertRaises(MetricValidationError):
            type(record).from_dict(value)
        value = record.to_dict()
        value["elapsed_seconds"] += 1.0
        with self.assertRaises(MetricValidationError):
            type(record).from_dict(value)

    def test_multi_run_and_all_artifact_hashes_preserved(self):
        records = [
            self.record("F_TO_R", "formal_a", 16 * 1024 * 1024, 30.0),
            self.record("R_TO_F", "formal_b", 16 * 1024 * 1024, 30.0),
            self.record("F_TO_R", "other_a", 16 * 1024 * 1024, 35.0, run_id="other"),
        ]
        result = finalize_metrics(records, formal_run_id="formal")
        self.assertEqual(len(result["all_records"]), 3)
        self.assertEqual(result["directions"]["F_TO_R"]["record_count"], 1)

    def test_seeded_50k_finalizer_cases_are_deterministic(self):
        rng = random.Random(20260731)
        counts = {"eligible": 0, "diagnostic": 0}
        for index in range(50_000):
            diagnostic = index % 11 == 0
            bytes_ = 1 if diagnostic else rng.choice([1024, 1024 * 1024, 16 * 1024 * 1024])
            seconds = rng.choice([0.001, 1.0, 30.0, 45.0])
            record = self.record(
                "F_TO_R" if index & 1 == 0 else "R_TO_F",
                f"random_{index}",
                bytes_,
                seconds,
                measurement_class=(
                    "DIAGNOSTIC_MICROTRANSFER" if diagnostic else "APPLICATION_SUSTAINED"
                ),
                diagnostic_only=diagnostic,
            )
            counts["eligible"] += int(record.eligible_for_scaling)
            counts["diagnostic"] += int(record.diagnostic_only)
        self.assertEqual(counts, {"eligible": 30307, "diagnostic": 4546})


if __name__ == "__main__":
    unittest.main()
