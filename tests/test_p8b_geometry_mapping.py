from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

import yaml

from tools.p8b_generate_trajectory import DEFAULT_SEEDS, generate
from tools.p8b_geometry_model import (
    bounded_corner_sweep,
    closed_form,
    deterministic_monte_carlo,
    evaluate_3d,
    gap_ledger,
    load_config,
    nominal_summary,
)
from tools.p8b_mapping_reference import (
    Direction,
    EpochCommitModel,
    candidate_mapping,
    candidate_path,
    current_mapping,
    exhaustive_records,
    exhaustive_summary,
    inverse_bank_owners,
    validate_mapping,
)


class MappingTests(unittest.TestCase):
    def test_exhaustive_all_m0_lanes_and_directions(self):
        rows = exhaustive_records()
        self.assertEqual(len(rows), 512)
        summary = exhaustive_summary()
        self.assertEqual(summary["lane_current_tuples"], 256)
        self.assertTrue(all(summary["boundaries"].values()))

    def test_inverse_round_trip_and_formula(self):
        for m0 in range(32):
            q, s = m0 % 4, m0 // 4
            current = current_mapping(m0)
            owners = inverse_bank_owners(current)
            for path in current:
                self.assertEqual(path.bank, (s + path.lane) % 8)
                self.assertEqual(path.slot, q)
                self.assertEqual(owners[path.bank], path.lane)
            for direction in (Direction.FORWARD, Direction.REVERSE):
                candidate = candidate_mapping(m0, direction)
                self.assertTrue(validate_mapping(candidate))
                candidate_owners = inverse_bank_owners(candidate)
                for path in candidate:
                    self.assertEqual(candidate_owners[path.bank], path.lane)

    def test_direct_wrap_boundaries(self):
        self.assertEqual(candidate_path(3, 0, Direction.FORWARD).slot, 0)
        self.assertEqual(candidate_path(31, 0, Direction.FORWARD).fixed_index, 0)
        self.assertEqual(candidate_path(0, 0, Direction.REVERSE).fixed_index, 31)
        self.assertEqual(candidate_path(0, 7, Direction.REVERSE).bank, 6)

    def test_invalid_inputs_fail_closed(self):
        for bad in (-1, 32, 1.5):
            with self.assertRaises(ValueError):
                current_mapping(bad)
        with self.assertRaises(ValueError):
            candidate_mapping(0, Direction.UNKNOWN)
        with self.assertRaises(ValueError):
            candidate_mapping(0, Direction.STOPPED)

    def test_epoch_exactly_once_reject_stale_and_wrap(self):
        model = EpochCommitModel(width=3)
        self.assertEqual(model.step(True, False), (False, True))
        self.assertEqual(model.epoch, 0)
        self.assertEqual(model.step(True, True), (False, False))
        model.step(False, True)
        for expected in (1, 2, 3, 4, 5, 6, 7, 0):
            self.assertEqual(model.step(True, True), (True, False))
            self.assertEqual(model.epoch, expected)
            self.assertTrue(model.metadata_current(expected))
            self.assertFalse(model.metadata_current((expected - 1) & 7))
            self.assertEqual(model.step(True, True), (False, False))
            model.step(False, True)


class GeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config()

    def test_nominal_closed_form_references(self):
        result = nominal_summary(self.config)
        self.assertAlmostEqual(result["nominal_worst_path_length_mm"], 200.720991, places=6)
        self.assertAlmostEqual(result["nominal_worst_rotating_angle_deg"], 8.424011, places=6)
        self.assertAlmostEqual(result["nominal_worst_fixed_angle_deg"], 2.799011, places=6)
        self.assertAlmostEqual(result["single_module_rotating_angle_limit_delta_deg"], 8.025994, places=6)
        self.assertAlmostEqual(result["nominal_two_module_overlap_deg"], 4.801987, places=6)
        self.assertAlmostEqual(result["nominal_overlap_time_at_600rpm_us"], 1333.885, places=3)
        self.assertAlmostEqual(result["fixed_module_pitch_time_at_600rpm_us"], 3125.0, places=9)

    def test_3d_nominal_matches_closed_form_high_resolution_and_lanes(self):
        for lane in range(8):
            for step in range(-5625, 5626, 25):
                delta = step / 1000.0
                result_2d = closed_form(100.0, 300.0, abs(delta))
                result_3d = evaluate_3d(self.config, delta)
                self.assertAlmostEqual(result_3d["path_length_mm"], result_2d["path_length_mm"], places=9)
                self.assertAlmostEqual(result_3d["rotating_incidence_angle_deg"], result_2d["rotating_incidence_angle_deg"], places=9)
                self.assertAlmostEqual(result_3d["fixed_incidence_angle_deg"], result_2d["fixed_incidence_angle_deg"], places=9)

    def test_missing_tolerances_are_explicit_and_corner_sweep_pending(self):
        gaps = gap_ledger(self.config)
        self.assertGreaterEqual(len(gaps), 10)
        self.assertTrue(all(gap["value"] is None for gap in gaps))
        self.assertEqual(bounded_corner_sweep(self.config, {})["status"], "PENDING_WITH_EXPLICIT_GAPS")
        self.assertEqual(deterministic_monte_carlo(self.config, {}, 20260717, 10)["status"], "PENDING_WITH_EXPLICIT_GAPS")

    def test_exact_corner_sweep_and_deterministic_monte_carlo_model(self):
        bounds = {
            "radial_eccentricity_x_mm": (-0.10, 0.10),
            "axial_runout_mm": (-0.05, 0.05),
            "rotating_axis_error_deg": (-0.20, 0.20),
            "fixed_axis_error_deg": (-0.20, 0.20),
        }
        corners = bounded_corner_sweep(self.config, bounds)
        self.assertEqual(corners["corner_count"], 16)
        first = deterministic_monte_carlo(self.config, bounds, 20260717, 1024)
        second = deterministic_monte_carlo(self.config, bounds, 20260717, 1024)
        self.assertEqual(first, second)
        self.assertEqual(first["sample_count"], 1024)
        self.assertLessEqual(first["p1"], first["p5"])
        self.assertLessEqual(first["p5"], first["p50"])
        self.assertLessEqual(first["p50"], first["p95"])
        self.assertLessEqual(first["p95"], first["p99"])

    def test_invalid_geometry_is_rejected(self):
        bad = dict(self.config)
        bad["radial_gap_mm"] = 0.0
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.yaml"
            path.write_text(yaml.safe_dump(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(path)


class TrajectoryTests(unittest.TestCase):
    def test_seeded_trajectories_cover_faults_stops_and_both_directions(self):
        for seed in DEFAULT_SEEDS:
            rows = generate(seed, 256)
            self.assertEqual(len(rows), 256)
            directions = {row["direction"] for row in rows}
            self.assertTrue({"STOPPED", "FORWARD", "REVERSE"}.issubset(directions))
            self.assertTrue(any(not row["phase_valid"] for row in rows))
            self.assertTrue(any(row["encoder_fault"] for row in rows))
            self.assertTrue(all(0 <= row["speed_abs_rpm"] <= 600 for row in rows))
            self.assertTrue(all(0 <= row["phase_mdeg"] < 360_000 for row in rows))


if __name__ == "__main__":
    unittest.main()
