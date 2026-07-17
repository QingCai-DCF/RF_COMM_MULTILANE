from __future__ import annotations

import unittest

from tools.p8c_tfdu_safety_reference import (
    DEFAULT_SEEDS,
    EndpointPermitModel,
    ExactDutyAccountant,
    PhysicalModuleSafetyModel,
    SafetyConfig,
    run_reference_campaign,
)


class SafetyMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = SafetyConfig.load()

    def test_canonical_exact_conversions(self) -> None:
        d = self.config.derive()
        self.assertEqual(d.window_cycles, 64_000)
        self.assertEqual(d.startup_cycles, 32_000)
        self.assertEqual(d.max_high_cycles, 64)

    def test_strict_thresholds(self) -> None:
        d = self.config.derive()
        self.assertEqual(d.hard_max_high_cycles, 12_799)
        self.assertLess(d.hard_max_high_cycles * 100, d.window_cycles * 20)
        self.assertEqual(d.target_max_high_cycles, 11_520)

    def test_non_divisible_clock_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            self.config.derive(clock_hz=1_000_001)

    def test_invalid_target_fails(self) -> None:
        with self.assertRaises(ValueError):
            self.config.derive(target_percent=20)


class ExactDutyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = SafetyConfig.load()
        self.d = self.config.derive(clock_hz=1_000_000, startup_us=1, window_us=100, max_high_us=1)

    def test_zero_and_single_pulse(self) -> None:
        model = ExactDutyAccountant(self.d, initially_valid=True)
        for _ in range(7):
            model.step(charge=False)
        self.assertEqual(model.rolling, 0)
        model.step(charge=True)
        self.assertEqual(model.rolling, 1)

    def test_strict_20_percent_boundary(self) -> None:
        model = ExactDutyAccountant(self.d, initially_valid=True)
        for _ in range(19):
            model.step(charge=True)
        self.assertFalse(model.hard_fault)
        model.step(charge=True)
        self.assertTrue(model.hard_fault)

    def test_cross_bucket_attack(self) -> None:
        model = ExactDutyAccountant(self.d, initially_valid=True)
        sequence = [0] * 90 + [1] * 10 + [1] * 10 + [0] * 90
        maxima = [int(model.step(charge=bool(bit))["rolling"]) for bit in sequence]
        self.assertEqual(max(maxima), 20)
        self.assertTrue(model.hard_fault)

    def test_ring_wrap_and_expiration(self) -> None:
        model = ExactDutyAccountant(self.d, initially_valid=True)
        model.step(charge=True)
        for _ in range(self.d.window_cycles - 1):
            model.step(charge=False)
        self.assertEqual(model.rolling, 1)
        model.step(charge=False)
        self.assertEqual(model.rolling, 0)

    def test_history_invalidation_requires_full_cooldown(self) -> None:
        model = ExactDutyAccountant(self.d, initially_valid=True)
        model.invalidate()
        for _ in range(self.d.window_cycles - 1):
            model.step(charge=False)
        self.assertFalse(model.history_valid)
        self.assertEqual(model.cooldown_remaining, 1)
        model.step(charge=False)
        self.assertTrue(model.history_valid)

    def test_physical_histories_are_independent(self) -> None:
        models = [ExactDutyAccountant(self.d, initially_valid=True) for _ in range(32)]
        for _ in range(12):
            models[9].step(charge=True)
            for index, model in enumerate(models):
                if index != 9:
                    model.step(charge=False)
        self.assertEqual(models[9].rolling, 12)
        self.assertTrue(all(model.rolling == 0 for index, model in enumerate(models) if index != 9))

    def test_design_target_and_next_requested_cycle(self) -> None:
        model = ExactDutyAccountant(self.d, initially_valid=True)
        for _ in range(self.d.target_max_high_cycles):
            model.step(charge=True)
        result = model.step(charge=False, target_request=True)
        self.assertEqual(model.rolling, self.d.target_max_high_cycles)
        self.assertFalse(result["target_admit"])
        self.assertTrue(result["target_throttle"])

    def test_reduced_window_exhaustive_sequences(self) -> None:
        d = self.config.derive(clock_hz=1_000_000, startup_us=1, window_us=10, max_high_us=1)
        for vector in range(1 << 12):
            model = ExactDutyAccountant(d, initially_valid=True)
            direct: list[int] = []
            sticky_fault = False
            for index in range(12):
                bit = (vector >> index) & 1
                direct.append(bit)
                direct = direct[-d.window_cycles:]
                sticky_fault = sticky_fault or sum(direct) > d.hard_max_high_cycles
                model.step(charge=bool(bit))
                self.assertEqual(model.rolling, sum(direct))
                self.assertEqual(model.hard_fault, sticky_fault)


class ContinuousHighTests(unittest.TestCase):
    def setUp(self) -> None:
        config = SafetyConfig.load()
        self.d = config.derive(clock_hz=10_000_000, startup_us=1, window_us=100, max_high_us=1)

    def ready_model(self) -> PhysicalModuleSafetyModel:
        model = PhysicalModuleSafetyModel(self.d)
        for _ in range(self.d.window_cycles + self.d.startup_cycles + 4):
            model.step(tx_request=False)
        return model

    def test_max_minus_one_and_max_allowed(self) -> None:
        model = self.ready_model()
        for _ in range(self.d.max_high_cycles):
            model.step(tx_request=True)
        self.assertFalse(model.stuck_fault)
        self.assertTrue(model.txd_pre_final)

    def test_max_plus_one_requested_is_killed_and_latched(self) -> None:
        model = self.ready_model()
        for _ in range(self.d.max_high_cycles + 2):
            model.step(tx_request=True)
        self.assertTrue(model.stuck_fault)
        self.assertFalse(model.txd_pre_final)
        self.assertEqual(model.longest, self.d.max_high_cycles)

    def test_clear_starts_cooldown(self) -> None:
        model = self.ready_model()
        for _ in range(self.d.max_high_cycles + 2):
            model.step(tx_request=True)
        model.step(tx_request=False, safety_fault_clear=True)
        self.assertFalse(model.stuck_fault)
        self.assertFalse(model.duty.history_valid)
        self.assertEqual(model.duty.cooldown_remaining, self.d.window_cycles)

    def test_zero_one_normal_pulse_and_very_long_request(self) -> None:
        model = self.ready_model()
        self.assertFalse(model.step(tx_request=False)["txd_pre_final"])
        self.assertTrue(model.step(tx_request=True)["txd_pre_final"])
        model.step(tx_request=False)
        for _ in range(4):
            self.assertTrue(model.step(tx_request=True)["txd_pre_final"])
        model.step(tx_request=False)
        self.assertFalse(model.stuck_fault)
        for _ in range(self.d.max_high_cycles * 2):
            result = model.step(tx_request=True)
        self.assertTrue(result["stuck_fault"])
        self.assertFalse(result["txd_pre_final"])
        self.assertEqual(model.stuck_fault_count, 1)
        self.assertEqual(model.longest, self.d.max_high_cycles)


class PermitTests(unittest.TestCase):
    def setUp(self) -> None:
        config = SafetyConfig.load()
        self.endpoint = EndpointPermitModel(2, config.assert_filter_cycles)

    def stabilize_high(self) -> None:
        for _ in range(self.endpoint.filter_cycles + 3):
            self.endpoint.step(raw_permit=True)

    def test_power_up_low_and_xz_fail_low(self) -> None:
        for value in (False, "X", "Z", None):
            result = self.endpoint.step(raw_permit=value, frame_new=True, waveform=[True, True])
            self.assertFalse(result["raw_safe"])
            self.assertEqual(result["tx"], [False, False])

    def test_high_filter_and_explicit_arm(self) -> None:
        self.stabilize_high()
        result = self.endpoint.step(raw_permit=True, frame_new=True, waveform=[True, False])
        self.assertFalse(any(result["tx"]))
        armed = self.endpoint.step(raw_permit=True, arm_request=True)
        self.assertTrue(armed["arm_accept"])
        fresh = self.endpoint.step(raw_permit=True, frame_new=True, waveform=[True, False])
        self.assertEqual(fresh["tx"], [True, False])

    def test_drop_midframe_requires_new_boundary_and_rearm(self) -> None:
        self.stabilize_high()
        self.endpoint.step(raw_permit=True, arm_request=True)
        dropped = self.endpoint.step(raw_permit=False, frame_active=True, frame_new=True, waveform=[True, False])
        self.assertFalse(any(dropped["tx"]))
        self.assertTrue(dropped["partial_block"])
        self.stabilize_high()
        rejected = self.endpoint.step(raw_permit=True, arm_request=True, frame_active=True)
        self.assertFalse(rejected["arm_accept"])
        self.endpoint.step(raw_permit=True, frame_active=False)
        self.assertTrue(self.endpoint.step(raw_permit=True, arm_request=True)["arm_accept"])

    def test_receive_only_with_permit_low(self) -> None:
        result = self.endpoint.step(
            raw_permit=False,
            waveform=[True, True],
            receive_enable=[True, True],
            rxd_low=[True, False],
        )
        self.assertEqual(result["tx"], [False, False])
        self.assertEqual(result["rx_active"], [True, False])

    def test_one_hot_path_gating_and_kill_reason_priority(self) -> None:
        self.stabilize_high()
        self.endpoint.step(raw_permit=True, arm_request=True)
        one_hot = self.endpoint.step(
            raw_permit=True, one_hot_valid=False,
            frame_new=True, waveform=[True, False],
        )
        self.assertFalse(any(one_hot["tx"]))
        self.assertEqual(one_hot["kill_reason"], "ILLEGAL_ONE_HOT")
        stale = self.endpoint.step(
            raw_permit=True, arm_request=True, path_epoch_valid=False,
            frame_new=True, waveform=[True, False],
        )
        self.assertFalse(any(stale["tx"]))
        self.assertEqual(stale["kill_reason"], "STALE_OR_INVALID_PATH_EPOCH")
        selected = self.endpoint.step(
            raw_permit=True, arm_request=True, selected_valid=False,
            one_hot_valid=False, path_epoch_valid=False,
        )
        self.assertEqual(selected["kill_reason"], "INVALID_SELECTED_MODULE")
        priority = self.endpoint.step(
            raw_permit=False, full_shutdown=True, fatal_fault=True,
            selected_valid=False, one_hot_valid=False, path_epoch_valid=False,
        )
        self.assertEqual(priority["kill_reason"], "RESET_OR_FULL_SHUTDOWN")


class CampaignTests(unittest.TestCase):
    def test_full_reference_campaign(self) -> None:
        result = run_reference_campaign()
        self.assertEqual(result["status"], "PASS", result.get("first_mismatch"))
        self.assertEqual(result["random_seeds"], DEFAULT_SEEDS)
        self.assertTrue(all(result["checks"].values()))


if __name__ == "__main__":
    unittest.main()
