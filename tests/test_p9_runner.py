from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "p9_runner", ROOT / "scripts/run_p9_z7010_stationary_2lane.py"
)
assert SPEC and SPEC.loader
P9 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P9)

HW_SPEC = importlib.util.spec_from_file_location(
    "p9_hardware_runtime", ROOT / "scripts/p9_hardware_runtime.py"
)
assert HW_SPEC and HW_SPEC.loader
P9_HW = importlib.util.module_from_spec(HW_SPEC)
sys.modules[HW_SPEC.name] = P9_HW
HW_SPEC.loader.exec_module(P9_HW)


class P9AuthorizationTests(unittest.TestCase):
    def write_record(self, updates: dict | None = None) -> Path:
        source = json.loads((ROOT / "config/p9_current_run_authorization.json").read_text())
        source.update(updates or {})
        temporary = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        json.dump(source, temporary)
        temporary.close()
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return Path(temporary.name)

    def validate(self, path: Path, **updates):
        values = {"stage": "P9-04", "max_runtime": 1800, "lane_mask": 1,
                  "require_bound_artifacts": True}
        values.update(updates)
        return P9.validate_authorization(path, **values)

    def test_no_authorization_fails(self):
        result = self.validate(Path("missing-authorization.json"))
        self.assertEqual(result["status"], "FAIL")

    def test_unbound_hardware_authorization_fails(self):
        result = self.validate(ROOT / "config/p9_current_run_authorization.json")
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any("phase-2" in error for error in result["errors"]))

    def test_lane_mask_0x4_fails(self):
        path = self.write_record({"artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path, lane_mask=4)["status"], "FAIL")

    def test_runtime_above_1800_fails(self):
        path = self.write_record({"artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path, max_runtime=1801)["status"], "FAIL")

    def test_wrong_scope_fails(self):
        path = self.write_record({"scope": "WRONG_SCOPE", "artifact_binding_phase": "PHASE2_IMMUTABLE_ARTIFACTS_BOUND"})
        self.assertEqual(self.validate(path)["status"], "FAIL")


class P9HardwareDutyEvaluatorTests(unittest.TestCase):
    @staticmethod
    def safe_idle_observation() -> tuple[dict, list[int]]:
        row = {
            "label": "duty_boundary", "command": 1, "expected_status": 0,
            "sequence": 1001, "lane": 0, "direction": 0, "rate": 0,
            "size": 0, "window": "NA",
        }
        words = [0] * 256
        words[0] = 0x424D3950
        words[1] = P9_HW.P9_MAILBOX_SCHEMA
        words[2] = P9_HW.P9_FIRMWARE_BUILD_ID
        words[3] = 4
        words[7] = row["sequence"]
        words[8] = 0
        words[32] = 0x50395A10
        words[33] = P9_HW.P9_PL_BUILD_ID
        words[34] = 0x00701022
        words[35] = P9_HW.EXPECTED_REGISTER_MAP_VERSION
        words[36] = P9_HW.EXPECTED_REGISTER_MAP_HASH_LOW
        words[37] = 0xF7204221
        words[39] = 0x40400000
        words[40] = 1
        words[49] = 64
        words[50] = 32

        def set_pl(index: int, value: int) -> None:
            words[P9_HW.PL_SNAPSHOT_START + index] = value

        set_pl(0, 0x50395A10)
        set_pl(7, 0x2)
        set_pl(85, 64_000)
        set_pl(86, 12_799)
        set_pl(87, 11_520)
        return row, words

    def test_canonical_strict_duty_telemetry_passes(self):
        row, words = self.safe_idle_observation()
        errors, detail = P9_HW.evaluate_observation(row, words)
        self.assertEqual([], errors)
        self.assertEqual(64_000, detail["duty_window_cycles"])
        self.assertEqual(12_799, detail["duty_hard_max_high_cycles"])
        self.assertEqual(11_520, detail["duty_target_max_high_cycles"])

    def test_12799_is_below_strict_20_percent_but_12800_is_not(self):
        row, words = self.safe_idle_observation()
        words[P9_HW.PL_SNAPSHOT_START + 65] = 12_799
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertFalse(any("strict 20%" in error for error in errors))
        words[P9_HW.PL_SNAPSHOT_START + 65] = 12_800
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("strict 20%" in error for error in errors))

    def test_noncanonical_hard_limit_telemetry_fails(self):
        row, words = self.safe_idle_observation()
        words[P9_HW.PL_SNAPSHOT_START + 86] = 12_800
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("64000/12799/11520" in error for error in errors))

    def test_p9_counter_clear_cannot_invalidate_physical_duty_history(self):
        lane_phy = (ROOT / "rtl/tfdu_lane_phy.sv").read_text(encoding="utf-8")
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(encoding="utf-8")
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertIn("parameter integer CLEAR_STICKY_INVALIDATES_HISTORY = 1", lane_phy)
        self.assertIn(".safety_fault_clear_i(safety_fault_clear)", lane_phy)
        self.assertIn(".telemetry_clear_i(clear_sticky)", lane_phy)
        self.assertEqual(2, core.count(".CLEAR_STICKY_INVALIDATES_HISTORY(0)"))
        self.assertIn("P9 telemetry clear invalidated safety/startup state", testbench)

    def raw_observation(self, *, direction: int) -> tuple[dict, list[int]]:
        row, words = self.safe_idle_observation()
        row.update({
            "label": f"raw_direction_{direction}", "command": 2,
            "lane": 1, "direction": direction, "rawtarget": 64,
        })

        def set_pl(index: int, value: int) -> None:
            words[P9_HW.PL_SNAPSHOT_START + index] = value

        set_pl(16, 1 | (direction << 8))
        set_pl(19, 64)
        # Current stationary Z7010 policy: both same-lane receivers see the
        # exact train, while the other lane sees no pulses.
        set_pl(53, 64)
        set_pl(55, 64)
        set_pl(57 + (2 if direction else 0), 64)
        return row, words

    def test_raw_selected_lane_exact_at_both_endpoint_receivers(self):
        for direction in (0, 1):
            with self.subTest(direction=direction):
                row, words = self.raw_observation(direction=direction)
                errors, detail = P9_HW.evaluate_observation(row, words)
                self.assertEqual([], errors)
                self.assertEqual(
                    "BOTH_ENDPOINTS_EXACT_SELECTED_LANE",
                    detail["raw_rx_observation_policy"],
                )
                self.assertEqual([64, 0, 64, 0], detail["expected_raw_rx"])

    def test_raw_off_lane_pulse_still_fails_closed(self):
        row, words = self.raw_observation(direction=0)
        words[P9_HW.PL_SNAPSHOT_START + 54] = 1
        errors, _ = P9_HW.evaluate_observation(row, words)
        self.assertTrue(any("physical RX raw vector mismatch" in error for error in errors))

    def test_p9_rearm_plan_covers_both_directions_and_profile_policy_is_bound(self):
        plans = P9_HW.build_plans()
        rearm = [case for case in plans["P9-07"] if getattr(case, "label", "").startswith("p9_07_rearm_")]
        self.assertEqual([0, 1], [case.direction for case in rearm])
        config = (ROOT / "config/p9_z7010_stationary_2lane.yaml").read_text(
            encoding="utf-8"
        )
        testbench = (ROOT / "sim/tb/tb_p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        self.assertIn("policy: BOTH_ENDPOINTS_EXACT_SELECTED_LANE", config)
        self.assertEqual(2, testbench.count("~(a_txd | b_txd)"))


if __name__ == "__main__":
    unittest.main()
