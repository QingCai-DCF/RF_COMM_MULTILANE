#!/usr/bin/env python3
"""Dependency-free TFDU6102 digital behavior reference for P2 offline checks."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RxPulse:
    rxd_low: bool
    width_ns: int
    dropped: bool = False
    reason: str = ""


class Tfdu6102Reference:
    """Small digital contract model, not an electrical or optical model."""

    def __init__(
        self,
        *,
        clk_hz: int = 64_000_000,
        startup_us: int = 500,
        txd_protect_us: int = 80,
        mode_high: bool = True,
        jitter_cycles: int = 0,
        drop_every_n_pulse: int = 0,
    ) -> None:
        if clk_hz <= 0:
            raise ValueError("clk_hz must be positive")
        self.clk_hz = clk_hz
        self.startup_us = startup_us
        self.txd_protect_us = txd_protect_us
        self.mode_high = mode_high
        self.jitter_cycles = jitter_cycles
        self.drop_every_n_pulse = drop_every_n_pulse
        self.shutdown = True
        self.elapsed_us_after_shutdown_exit = 0
        self.protection_fault = False
        self.transmitted_pulses = 0
        self.received_pulses = 0

    @property
    def startup_done(self) -> bool:
        return (not self.shutdown) and self.elapsed_us_after_shutdown_exit >= self.startup_us

    @property
    def rxd_idle_high(self) -> bool:
        return True

    @property
    def txd_default_low(self) -> bool:
        return True

    def reset(self) -> None:
        self.shutdown = True
        self.elapsed_us_after_shutdown_exit = 0
        self.protection_fault = False
        self.transmitted_pulses = 0
        self.received_pulses = 0

    def set_shutdown(self, enabled: bool) -> None:
        self.shutdown = enabled
        if enabled:
            self.elapsed_us_after_shutdown_exit = 0

    def set_mode_high(self, enabled: bool) -> None:
        self.mode_high = enabled

    def advance_us(self, amount_us: int) -> None:
        if amount_us < 0:
            raise ValueError("amount_us must be non-negative")
        if not self.shutdown:
            self.elapsed_us_after_shutdown_exit += amount_us

    def transmit_txd_high(self, width_us: float) -> bool:
        """Return True when a bounded high-active Txd pulse can emit light."""
        if width_us < 0:
            raise ValueError("width_us must be non-negative")
        if width_us >= self.txd_protect_us:
            self.protection_fault = True
            return False
        if self.shutdown or not self.startup_done or self.protection_fault:
            return False
        self.transmitted_pulses += 1
        return True

    def receive_optical_pulse(self, width_ns: int) -> RxPulse:
        if width_ns <= 0:
            raise ValueError("width_ns must be positive")
        self.received_pulses += 1
        if self.shutdown:
            return RxPulse(False, 0, True, "shutdown")
        if not self.startup_done:
            return RxPulse(False, 0, True, "startup_not_done")
        if not self.mode_high:
            return RxPulse(False, 0, True, "mode_low_fir_drop")
        if self.drop_every_n_pulse and self.received_pulses % self.drop_every_n_pulse == 0:
            return RxPulse(False, 0, True, "loss_injection")

        if width_ns <= 180:
            mapped = 120
        else:
            mapped = 250
        if self.jitter_cycles:
            mapped += round((self.jitter_cycles * 1_000_000_000) / self.clk_hz)
        return RxPulse(True, mapped)
