#!/usr/bin/env python3
"""Cycle-accurate P8C TFDU safety and single-permit reference model."""

from __future__ import annotations

import argparse
import dataclasses
import json
import random
from collections import deque
from pathlib import Path
from typing import Any, Iterable

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tfdu_safety.yaml"
DEFAULT_SEEDS = [1, 7, 17, 31, 127, 1024, 20260718]


@dataclasses.dataclass(frozen=True)
class DerivedSafety:
    clock_hz: int
    startup_us: int
    window_us: int
    hard_percent: int
    target_percent: int
    max_high_us: int
    startup_cycles: int
    window_cycles: int
    hard_max_high_cycles: int
    target_max_high_cycles: int
    max_high_cycles: int


@dataclasses.dataclass(frozen=True)
class SafetyConfig:
    raw: dict[str, Any]

    @classmethod
    def load(cls, path: Path = CONFIG_PATH) -> "SafetyConfig":
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if raw.get("schema_version") != 1:
            raise ValueError("unsupported safety schema")
        if raw.get("mode_strategy") != "static_high_speed":
            raise ValueError("static high-speed mode is required")
        permit = raw["global_permit"]
        if permit.get("count_per_endpoint") != 1 or permit.get("active_level") != "high":
            raise ValueError("one active-high permit per endpoint is required")
        if permit.get("software_writable") is not False:
            raise ValueError("permit must be read-only to software")
        kill_reasons = raw.get("kill_reasons")
        if not isinstance(kill_reasons, dict) or kill_reasons.get("NONE") != 0:
            raise ValueError("canonical kill_reasons mapping is required")
        if len(set(int(value) for value in kill_reasons.values())) != len(kill_reasons):
            raise ValueError("kill reason values must be unique")
        return cls(raw=raw)

    @property
    def assert_filter_cycles(self) -> int:
        return int(self.raw["global_permit"]["assert_filter_cycles"])

    @property
    def kill_reasons(self) -> dict[str, int]:
        return {name: int(value) for name, value in self.raw["kill_reasons"].items()}

    def derive(
        self,
        clock_hz: int | None = None,
        startup_us: int | None = None,
        window_us: int | None = None,
        max_high_us: int | None = None,
        hard_percent: int | None = None,
        target_percent: int | None = None,
    ) -> DerivedSafety:
        clock_hz = int(clock_hz or self.raw["canonical_clock_hz"])
        startup_us = int(startup_us or self.raw["receiver_startup_us"])
        window_us = int(window_us or self.raw["rolling_duty_window_us"])
        max_high_us = int(max_high_us or self.raw["max_continuous_txd_high_us"])
        hard_percent = int(hard_percent or self.raw["rolling_duty_hard_percent_strict_lt"])
        target_percent = int(target_percent or self.raw["rolling_duty_design_percent_max"])
        products = {
            "startup": clock_hz * startup_us,
            "window": clock_hz * window_us,
            "max_high": clock_hz * max_high_us,
        }
        for name, product in products.items():
            if product <= 0 or product % 1_000_000:
                raise ValueError(f"{name} cycle conversion is not exact")
        if not (0 < target_percent < hard_percent < 100):
            raise ValueError("target percentage must be below strict hard percentage")
        if max_high_us > 1:
            raise ValueError("max continuous high must be <=1 us")
        window_cycles = products["window"] // 1_000_000
        hard_max = (window_cycles * hard_percent - 1) // 100
        target_max = window_cycles * target_percent // 100
        if hard_max * 100 >= window_cycles * hard_percent:
            raise AssertionError("strict hard threshold calculation failed")
        return DerivedSafety(
            clock_hz=clock_hz,
            startup_us=startup_us,
            window_us=window_us,
            hard_percent=hard_percent,
            target_percent=target_percent,
            max_high_us=max_high_us,
            startup_cycles=products["startup"] // 1_000_000,
            window_cycles=window_cycles,
            hard_max_high_cycles=hard_max,
            target_max_high_cycles=target_max,
            max_high_cycles=products["max_high"] // 1_000_000,
        )


class ExactDutyAccountant:
    """Exact arbitrary-alignment ring history for one physical module."""

    def __init__(self, derived: DerivedSafety, *, initially_valid: bool = False):
        self.d = derived
        self.history = [0] * derived.window_cycles
        self.ptr = 0
        self.rolling = 0
        self.rolling_max_seen = 0
        self.history_valid = initially_valid
        self.cooldown_written = derived.window_cycles if initially_valid else 0
        self.hard_fault = False
        self.hard_fault_count = 0
        self.target_throttle_count = 0
        self.charge_count = 0

    @property
    def cooldown_remaining(self) -> int:
        return 0 if self.history_valid else self.d.window_cycles - self.cooldown_written

    def invalidate(self) -> None:
        self.ptr = 0
        self.rolling = 0
        self.history_valid = False
        self.cooldown_written = 0

    def clear_fault(self) -> None:
        self.hard_fault = False
        self.invalidate()

    def step(
        self,
        *,
        charge: bool,
        target_request: bool = False,
        invalidate: bool = False,
        clear_fault: bool = False,
    ) -> dict[str, int | bool]:
        if invalidate or clear_fault:
            if clear_fault:
                self.hard_fault = False
            self.invalidate()
            return self.snapshot(target_admit=False, hard_violation=False, throttle=False)
        if not self.history_valid:
            self.history[self.ptr] = 0
            self.ptr = (self.ptr + 1) % self.d.window_cycles
            self.cooldown_written += 1
            self.rolling = 0
            if self.cooldown_written >= self.d.window_cycles:
                self.history_valid = True
                self.ptr = 0
            return self.snapshot(target_admit=False, hard_violation=False, throttle=False)

        outgoing = self.history[self.ptr]
        rolling_next = self.rolling - outgoing + int(bool(charge))
        hard_violation = rolling_next > self.d.hard_max_high_cycles
        target_admit = not self.hard_fault and rolling_next < self.d.target_max_high_cycles
        throttle = bool(target_request and not self.hard_fault and not target_admit)
        self.history[self.ptr] = int(bool(charge))
        self.ptr = (self.ptr + 1) % self.d.window_cycles
        self.rolling = rolling_next
        self.rolling_max_seen = max(self.rolling_max_seen, rolling_next)
        if charge:
            self.charge_count += 1
        if throttle:
            self.target_throttle_count += 1
        if hard_violation and not self.hard_fault:
            self.hard_fault = True
            self.hard_fault_count += 1
        return self.snapshot(
            target_admit=target_admit,
            hard_violation=hard_violation,
            throttle=throttle,
        )

    def snapshot(self, *, target_admit: bool, hard_violation: bool, throttle: bool) -> dict[str, int | bool]:
        return {
            "rolling": self.rolling,
            "rolling_max_seen": self.rolling_max_seen,
            "target_admit": target_admit,
            "hard_violation": hard_violation,
            "target_throttle": throttle,
            "hard_fault": self.hard_fault,
            "history_valid": self.history_valid,
            "cooldown_remaining": self.cooldown_remaining,
            "headroom": max(0, self.d.target_max_high_cycles - self.rolling),
            "charge_count": self.charge_count,
        }


class PhysicalModuleSafetyModel:
    def __init__(self, derived: DerivedSafety):
        self.d = derived
        self.duty = ExactDutyAccountant(derived)
        self.txd_pre_final = False
        self.startup_done = False
        self.startup_count = 0
        self.continuous = 0
        self.longest = 0
        self.stuck_fault = False
        self.stuck_fault_count = 0
        self.stuck_kill_count = 0

    def step(
        self,
        *,
        tx_request: bool,
        sd_active: bool = False,
        history_invalidate: bool = False,
        safety_fault_clear: bool = False,
    ) -> dict[str, int | bool]:
        old_startup_done = self.startup_done
        if sd_active:
            self.startup_done = False
            self.startup_count = 0
        elif not self.startup_done:
            if self.startup_count == self.d.startup_cycles - 1:
                self.startup_done = True
            else:
                self.startup_count += 1

        target_request = bool(tx_request and old_startup_done and self.duty.history_valid and not self.stuck_fault)
        duty_result = self.duty.step(
            charge=self.txd_pre_final,
            target_request=target_request,
            invalidate=history_invalidate,
            clear_fault=safety_fault_clear,
        )

        old_output = self.txd_pre_final
        continuous_after_current = self.continuous + 1 if old_output else 0
        if history_invalidate or safety_fault_clear:
            self.txd_pre_final = False
            self.continuous = 0
            if safety_fault_clear:
                self.stuck_fault = False
        else:
            self.continuous = continuous_after_current
            self.longest = max(self.longest, continuous_after_current)
            overrun_request = bool(
                tx_request and old_output and continuous_after_current >= self.d.max_high_cycles
            )
            if overrun_request and not self.stuck_fault:
                self.txd_pre_final = False
                self.stuck_fault = True
                self.stuck_fault_count += 1
                self.stuck_kill_count += 1
            elif (
                sd_active
                or not old_startup_done
                or not self.duty.history_valid
                or self.duty.hard_fault
                or duty_result["hard_violation"]
                or self.stuck_fault
            ):
                self.txd_pre_final = False
            else:
                self.txd_pre_final = bool(tx_request and duty_result["target_admit"])
        return {
            **duty_result,
            "txd_pre_final": self.txd_pre_final,
            "startup_done": self.startup_done,
            "continuous": self.continuous,
            "longest": self.longest,
            "stuck_fault": self.stuck_fault,
            "stuck_fault_count": self.stuck_fault_count,
            "stuck_kill_count": self.stuck_kill_count,
        }


class EndpointPermitModel:
    """Behavioral permit/arm/partial-frame/RX-only model for property tests."""

    def __init__(self, module_count: int, filter_cycles: int,
                 kill_reasons: dict[str, int] | None = None):
        self.module_count = module_count
        self.filter_cycles = filter_cycles
        self.kill_reasons = kill_reasons or SafetyConfig.load().kill_reasons
        self.raw_safe = False
        self.sync_pipeline = deque([False, False], maxlen=2)
        self.filter_count = 0
        self.sync_valid = False
        self.armed = False
        self.partial_block = False
        self.rise_count = 0
        self.fall_count = 0
        self.drop_during_frame_count = 0
        self.rearm_count = 0
        self._raw_prev = False

    @staticmethod
    def raw_is_safe(value: Any) -> bool:
        return value is True or value == 1

    def step(
        self,
        *,
        raw_permit: Any,
        arm_request: bool = False,
        disarm_request: bool = False,
        frame_active: bool = False,
        frame_new: bool = False,
        all_safety_ok: bool = True,
        selected_valid: bool = True,
        one_hot_valid: bool = True,
        path_epoch_valid: bool = True,
        startup_done: bool = True,
        history_valid: bool = True,
        cooldown_active: bool = False,
        duty_hard_fault: bool = False,
        stuck_high_fault: bool = False,
        fatal_fault: bool = False,
        sd_active: bool = False,
        full_shutdown: bool = False,
        waveform: Iterable[bool] | None = None,
        receive_enable: Iterable[bool] | None = None,
        rxd_low: Iterable[bool] | None = None,
    ) -> dict[str, Any]:
        raw = self.raw_is_safe(raw_permit)
        if raw and not self._raw_prev:
            self.rise_count += 1
        if not raw and self._raw_prev:
            self.fall_count += 1
            if frame_active:
                self.drop_during_frame_count += 1
                self.partial_block = True
        self._raw_prev = raw
        self.raw_safe = raw
        if not raw:
            self.sync_pipeline = deque([False, False], maxlen=2)
            self.filter_count = 0
            self.sync_valid = False
            self.armed = False
        else:
            self.sync_pipeline.append(True)
            sync = all(self.sync_pipeline)
            if sync and not self.sync_valid:
                if self.filter_count == self.filter_cycles - 1:
                    self.sync_valid = True
                else:
                    self.filter_count += 1
        if self.partial_block and not frame_active:
            self.partial_block = False
        qualified_safety = bool(
            all_safety_ok and selected_valid and one_hot_valid and path_epoch_valid
            and startup_done and history_valid and not cooldown_active
            and not duty_hard_fault and not stuck_high_fault and not fatal_fault
            and not sd_active and not full_shutdown
        )
        if disarm_request or not qualified_safety:
            if frame_active:
                self.partial_block = True
            self.armed = False
        arm_accept = False
        if arm_request:
            arm_accept = bool(
                raw and self.sync_valid and qualified_safety
                and not frame_active and not self.partial_block
            )
            self.armed = arm_accept
            if arm_accept:
                self.rearm_count += 1
        waveform_list = list(waveform or [False] * self.module_count)
        tx = [bool(raw and self.sync_valid and self.armed and qualified_safety
                   and not self.partial_block and frame_new and bit)
              for bit in waveform_list]
        receive_list = list(receive_enable or [False] * self.module_count)
        rxd_list = list(rxd_low or [False] * self.module_count)
        rx_active = [bool(receive_list[i] and rxd_list[i] and not sd_active and not full_shutdown)
                     for i in range(self.module_count)]
        if full_shutdown:
            kill_reason = "RESET_OR_FULL_SHUTDOWN"
        elif not raw or not self.sync_valid:
            kill_reason = "GLOBAL_PERMIT_LOW"
        elif fatal_fault or not all_safety_ok:
            kill_reason = "FATAL_FAULT"
        elif not selected_valid:
            kill_reason = "INVALID_SELECTED_MODULE"
        elif not one_hot_valid:
            kill_reason = "ILLEGAL_ONE_HOT"
        elif not path_epoch_valid:
            kill_reason = "STALE_OR_INVALID_PATH_EPOCH"
        elif not startup_done:
            kill_reason = "STARTUP_NOT_COMPLETE"
        elif cooldown_active or not history_valid:
            kill_reason = "HISTORY_COOLDOWN"
        elif duty_hard_fault:
            kill_reason = "DUTY_HARD_FAULT"
        elif stuck_high_fault:
            kill_reason = "STUCK_HIGH_FAULT"
        elif self.partial_block:
            kill_reason = "PARTIAL_FRAME_ABORTED"
        elif sd_active:
            kill_reason = "SD_ACTIVE"
        elif not self.armed:
            kill_reason = "NOT_ARMED"
        elif not frame_new:
            kill_reason = "FRAME_NOT_ADMITTED"
        else:
            kill_reason = "NONE"
        return {
            "raw_safe": raw,
            "sync_valid": self.sync_valid,
            "armed": self.armed,
            "arm_accept": arm_accept,
            "partial_block": self.partial_block,
            "tx": tx,
            "rx_active": rx_active,
            "kill_reason": kill_reason,
            "kill_reason_value": self.kill_reasons[kill_reason],
        }


def run_reference_campaign(config: SafetyConfig | None = None) -> dict[str, Any]:
    config = config or SafetyConfig.load()
    canonical = config.derive()
    checks: dict[str, bool] = {}

    checks["canonical_window_64000"] = canonical.window_cycles == 64_000
    checks["canonical_startup_32000"] = canonical.startup_cycles == 32_000
    checks["canonical_max_high_64"] = canonical.max_high_cycles == 64
    checks["strict_hard_12799"] = canonical.hard_max_high_cycles == 12_799
    checks["target_11520"] = canonical.target_max_high_cycles == 11_520

    reduced = config.derive(clock_hz=1_000_000, startup_us=1, window_us=100, max_high_us=1)
    direct = ExactDutyAccountant(reduced, initially_valid=True)
    for _ in range(reduced.hard_max_high_cycles):
        direct.step(charge=True)
    checks["legal_strict_hard_boundary"] = not direct.hard_fault and direct.rolling == 19
    direct.step(charge=True)
    checks["illegal_20_percent_fault"] = direct.hard_fault and direct.rolling == 20

    shaper = PhysicalModuleSafetyModel(reduced)
    for _ in range(reduced.window_cycles + reduced.startup_cycles + 2):
        shaper.step(tx_request=False)
    observed: deque[int] = deque(maxlen=reduced.window_cycles)
    max_window = 0
    for cycle in range(reduced.window_cycles * 8):
        # A one-cycle pulse every five clocks requests exactly 20%. The 18%
        # target shaper must throttle this without invoking continuous-high.
        result = shaper.step(tx_request=(cycle % 5 == 0))
        observed.append(int(bool(result["txd_pre_final"])))
        max_window = max(max_window, sum(observed))
    checks["target_shaper_le18"] = max_window <= reduced.target_max_high_cycles
    checks["target_throttle_observed"] = shaper.duty.target_throttle_count > 0
    checks["hard_fault_absent_normal"] = not shaper.duty.hard_fault

    target_boundary = ExactDutyAccountant(reduced, initially_valid=True)
    for _ in range(reduced.target_max_high_cycles):
        target_boundary.step(charge=True)
    at_target = target_boundary.step(charge=False, target_request=True)
    checks["exact_design_target"] = target_boundary.rolling == reduced.target_max_high_cycles
    checks["design_target_plus_one_request_throttled"] = (
        not at_target["target_admit"] and at_target["target_throttle"]
    )

    # A legal pulse train with multi-cycle pulses exercises normal 4PPM-like
    # traffic without relying on one-cycle impulses.  At 10 MHz, four HIGH
    # cycles are 0.4 us and therefore below the independent 1 us guard.
    pulse_derived = config.derive(
        clock_hz=10_000_000, startup_us=1, window_us=100, max_high_us=1
    )
    pulse_model = PhysicalModuleSafetyModel(pulse_derived)
    for _ in range(pulse_derived.window_cycles + pulse_derived.startup_cycles + 2):
        pulse_model.step(tx_request=False)
    pulse_requested = 0
    pulse_admitted = 0
    for cycle in range(pulse_derived.window_cycles * 5):
        request = (cycle % 40) < 4
        result = pulse_model.step(tx_request=request)
        pulse_requested += int(request)
        pulse_admitted += int(bool(result["txd_pre_final"]))
    checks["long_periodic_4ppm_like_train_not_truncated"] = (
        pulse_admitted == pulse_requested
        and pulse_model.longest == 4
        and not pulse_model.stuck_fault
        and pulse_model.duty.rolling_max_seen <= pulse_derived.target_max_high_cycles
    )

    # Exhaustively enumerate a reduced exact-window configuration.  For every
    # 12-cycle binary trace, compare the ring sum and sticky strict-limit fault
    # against the direct last-10-cycle mathematical definition.
    exhaustive = config.derive(
        clock_hz=1_000_000, startup_us=1, window_us=10, max_high_us=1
    )
    exhaustive_cases = 0
    exhaustive_ok = True
    for vector in range(1 << 12):
        exact = ExactDutyAccountant(exhaustive, initially_valid=True)
        direct_window: deque[int] = deque(maxlen=exhaustive.window_cycles)
        direct_fault = False
        for bit_index in range(12):
            bit = (vector >> bit_index) & 1
            direct_window.append(bit)
            direct_sum = sum(direct_window)
            direct_fault = direct_fault or direct_sum > exhaustive.hard_max_high_cycles
            observed_step = exact.step(charge=bool(bit))
            if exact.rolling != direct_sum or bool(observed_step["hard_fault"]) != direct_fault:
                exhaustive_ok = False
                break
        exhaustive_cases += 1
        if not exhaustive_ok:
            break
    checks["reduced_exact_window_exhaustive"] = exhaustive_ok and exhaustive_cases == (1 << 12)

    cross = ExactDutyAccountant(reduced, initially_valid=True)
    pattern = [0] * 90 + [1] * 10 + [1] * 10 + [0] * 90
    maxima = []
    for bit in pattern:
        maxima.append(int(cross.step(charge=bool(bit))["rolling"]))
    checks["cross_bucket_attack_detected_exactly"] = max(maxima) == 20 and cross.hard_fault
    legacy_bucket_counts = [sum(pattern[offset:offset + reduced.window_cycles])
                            for offset in range(0, len(pattern), reduced.window_cycles)]
    checks["legacy_fixed_bucket_misses_cross_boundary_attack"] = (
        max(legacy_bucket_counts) == 10 and max(maxima) == 20
    )

    history = ExactDutyAccountant(reduced, initially_valid=True)
    history.step(charge=True)
    before = list(history.history)
    for _ in range(7):
        history.step(charge=False)
    checks["history_persists_transitions"] = sum(before) == 1 and sum(history.history) == 1
    history.invalidate()
    for _ in range(reduced.window_cycles - 1):
        history.step(charge=False)
    checks["cooldown_full_window_required"] = not history.history_valid and history.cooldown_remaining == 1
    history.step(charge=False)
    checks["cooldown_completes_at_window"] = history.history_valid

    models = [ExactDutyAccountant(reduced, initially_valid=True) for _ in range(32)]
    for cycle in range(250):
        for index, model in enumerate(models):
            model.step(charge=(index == 17 and cycle % 5 == 0))
    checks["physical_identity_independent"] = (
        models[17].rolling == 20 and all(model.rolling == 0 for index, model in enumerate(models) if index != 17)
    )

    random_cases = 0
    random_first_failure: dict[str, Any] | None = None
    for seed in DEFAULT_SEEDS:
        rng = random.Random(seed)
        model = PhysicalModuleSafetyModel(reduced)
        for _ in range(reduced.window_cycles + 2):
            model.step(tx_request=False)
        window: deque[int] = deque(maxlen=reduced.window_cycles)
        for cycle in range(5000):
            request = rng.randrange(100) < 37
            result = model.step(tx_request=request)
            window.append(int(bool(result["txd_pre_final"])))
            random_cases += 1
            if sum(window) > reduced.target_max_high_cycles or model.longest > reduced.max_high_cycles:
                random_first_failure = {
                    "seed": seed,
                    "cycle": cycle,
                    "window_high": sum(window),
                    "longest": model.longest,
                }
                break
        if random_first_failure:
            break
    checks["random_adversarial_safety"] = random_first_failure is None

    continuous = PhysicalModuleSafetyModel(pulse_derived)
    for _ in range(pulse_derived.window_cycles + pulse_derived.startup_cycles + 2):
        continuous.step(tx_request=False)
    zero = continuous.step(tx_request=False)
    one = continuous.step(tx_request=True)
    continuous.step(tx_request=False)
    for _ in range(pulse_derived.max_high_cycles * 2):
        very_long = continuous.step(tx_request=True)
    checks["continuous_zero_cycle_vector"] = not zero["txd_pre_final"]
    checks["continuous_one_cycle_vector"] = bool(one["txd_pre_final"])
    checks["continuous_2x_max_remains_killed"] = (
        very_long["stuck_fault"]
        and not very_long["txd_pre_final"]
        and continuous.stuck_fault_count == 1
        and continuous.longest == pulse_derived.max_high_cycles
    )

    endpoint = EndpointPermitModel(2, config.assert_filter_cycles)
    low = endpoint.step(
        raw_permit=False,
        waveform=[True, True],
        receive_enable=[True, True],
        rxd_low=[True, False],
    )
    checks["permit_low_all_tx_off"] = low["tx"] == [False, False]
    checks["receive_only_permit_low"] = low["rx_active"] == [True, False]
    for _ in range(config.assert_filter_cycles + 3):
        endpoint.step(raw_permit=True)
    no_arm = endpoint.step(raw_permit=True, frame_new=True, waveform=[True, False])
    checks["permit_high_no_auto_arm"] = not any(no_arm["tx"])
    armed = endpoint.step(raw_permit=True, arm_request=True)
    fresh = endpoint.step(raw_permit=True, frame_new=True, waveform=[True, False])
    checks["explicit_arm_required"] = armed["arm_accept"] and fresh["tx"][0]
    dropped = endpoint.step(raw_permit=False, frame_active=True, frame_new=True, waveform=[True, False])
    checks["raw_drop_kills"] = not any(dropped["tx"]) and not dropped["armed"]
    for _ in range(config.assert_filter_cycles + 3):
        endpoint.step(raw_permit=True, frame_active=True)
    rejected_midframe = endpoint.step(raw_permit=True, arm_request=True, frame_active=True)
    checks["partial_frame_not_resumed"] = not rejected_midframe["arm_accept"]
    endpoint.step(raw_permit=True, frame_active=False)
    rearmed = endpoint.step(raw_permit=True, arm_request=True)
    checks["explicit_rearm_after_frame_boundary"] = rearmed["arm_accept"]
    x_state = endpoint.step(raw_permit="X", frame_new=True, waveform=[True, True])
    checks["permit_x_fail_low"] = not x_state["raw_safe"] and not any(x_state["tx"])

    gating_endpoint = EndpointPermitModel(2, config.assert_filter_cycles, config.kill_reasons)
    for _ in range(config.assert_filter_cycles + 3):
        gating_endpoint.step(raw_permit=True)
    gating_endpoint.step(raw_permit=True, arm_request=True)
    invalid_one_hot = gating_endpoint.step(
        raw_permit=True, one_hot_valid=False, frame_new=True, waveform=[True, False]
    )
    invalid_path = gating_endpoint.step(
        raw_permit=True, arm_request=True, path_epoch_valid=False,
        frame_new=True, waveform=[True, False]
    )
    invalid_selected = gating_endpoint.step(
        raw_permit=True, arm_request=True, selected_valid=False,
        one_hot_valid=False, path_epoch_valid=False,
    )
    checks["one_hot_gating_and_reason"] = (
        not any(invalid_one_hot["tx"]) and invalid_one_hot["kill_reason"] == "ILLEGAL_ONE_HOT"
    )
    checks["path_epoch_gating_and_reason"] = (
        not any(invalid_path["tx"]) and invalid_path["kill_reason"] == "STALE_OR_INVALID_PATH_EPOCH"
    )
    checks["invalid_selected_reason_precedes_one_hot"] = (
        invalid_selected["kill_reason"] == "INVALID_SELECTED_MODULE"
    )
    shutdown_priority = gating_endpoint.step(
        raw_permit=False, full_shutdown=True, fatal_fault=True,
        selected_valid=False, one_hot_valid=False, path_epoch_valid=False,
    )
    permit_priority = gating_endpoint.step(
        raw_permit=False, fatal_fault=True, selected_valid=False,
        one_hot_valid=False, path_epoch_valid=False,
    )
    checks["fault_kill_reason_priority"] = (
        shutdown_priority["kill_reason"] == "RESET_OR_FULL_SHUTDOWN"
        and permit_priority["kill_reason"] == "GLOBAL_PERMIT_LOW"
        and shutdown_priority["kill_reason_value"] == config.kill_reasons["RESET_OR_FULL_SHUTDOWN"]
    )

    profile_counts = {
        name: int(profile["physical_module_count"])
        for name, profile in config.raw["physical_profiles"].items()
    }
    checks["profile_2"] = profile_counts.get("Z7010_2LANE_DEV") == 2
    checks["profile_8"] = profile_counts.get("Z7020_ROTATING_8LANE_MODEL") == 8
    checks["profile_32"] = profile_counts.get("Z7020_FIXED_32MODULE_ACCOUNTING_MODEL") == 32

    status = "PASS" if all(checks.values()) else "FAIL"
    return {
        "schema_version": 1,
        "stage": "P8C_TFDU_SAFETY_EXACT_DUTY_SINGLE_GLOBAL_PERMIT",
        "test_id": "P8C-PYTHON-REFERENCE-CAMPAIGN",
        "profile": "P8C_MULTI_PROFILE_OFFLINE",
        "status": status,
        "checks": checks,
        "canonical": dataclasses.asdict(canonical),
        "random_seeds": DEFAULT_SEEDS,
        "random_cases": random_cases,
        "reduced_exhaustive_cases": exhaustive_cases,
        "first_mismatch": random_first_failure,
        "physical_profile_counts": profile_counts,
        "NO_HARDWARE_ACTIONS_EXECUTED": True,
        "CURRENT_RUN_HARDWARE_AUTHORIZATION": False,
        "HARDWARE_SCOPE_PROMOTED": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--json-summary", action="store_true")
    args = parser.parse_args(argv)
    summary = run_reference_campaign()
    text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(text, encoding="utf-8", newline="\n")
    if args.json_summary:
        print(text, end="")
    else:
        print(f"P8C_REFERENCE_STATUS={summary['status']}")
        print(f"P8C_REFERENCE_RANDOM_CASES={summary['random_cases']}")
        print(f"P8C_REFERENCE_FIRST_MISMATCH={summary['first_mismatch']}")
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
