#!/usr/bin/env python3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "models"))

from tfdu6102_reference import Tfdu6102Reference


def ready_model() -> Tfdu6102Reference:
    model = Tfdu6102Reference()
    model.set_shutdown(False)
    model.advance_us(500)
    return model


def test_reset_shutdown_idle():
    model = Tfdu6102Reference()
    assert model.shutdown
    assert model.rxd_idle_high
    assert model.txd_default_low
    assert not model.startup_done


def test_static_high_speed_mode():
    model = ready_model()
    assert model.mode_high
    pulse = model.receive_optical_pulse(125)
    assert pulse.rxd_low


def test_startup_delay_500_us():
    model = Tfdu6102Reference(startup_us=500)
    model.set_shutdown(False)
    model.advance_us(499)
    assert not model.startup_done
    model.advance_us(1)
    assert model.startup_done


def test_txd_high_active():
    model = ready_model()
    assert model.transmit_txd_high(1.0)
    assert model.transmitted_pulses == 1


def test_rxd_low_active():
    model = ready_model()
    pulse = model.receive_optical_pulse(125)
    assert pulse.rxd_low
    assert pulse.width_ns > 0


def test_txd_over_80_us_protection():
    model = ready_model()
    assert not model.transmit_txd_high(80.0)
    assert model.protection_fault
    assert not model.transmit_txd_high(1.0)


def test_125_ns_pulse_mapping():
    model = ready_model()
    pulse = model.receive_optical_pulse(125)
    assert pulse.rxd_low
    assert 100 <= pulse.width_ns <= 140


def test_250_ns_pulse_mapping():
    model = ready_model()
    pulse = model.receive_optical_pulse(250)
    assert pulse.rxd_low
    assert 225 <= pulse.width_ns <= 275


def test_mode_low_drops_fir_pulse():
    model = ready_model()
    model.set_mode_high(False)
    pulse = model.receive_optical_pulse(125)
    assert pulse.dropped
    assert pulse.reason == "mode_low_fir_drop"


def test_shutdown_blocks_transmitter():
    model = Tfdu6102Reference()
    assert not model.transmit_txd_high(1.0)


def test_startup_not_done_drops_receiver_pulses():
    model = Tfdu6102Reference()
    model.set_shutdown(False)
    model.advance_us(100)
    pulse = model.receive_optical_pulse(125)
    assert pulse.dropped
    assert pulse.reason == "startup_not_done"
