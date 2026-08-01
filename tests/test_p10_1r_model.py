from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "model_p10_1r", ROOT / "scripts/model_p10_1r.py"
)
assert SPEC and SPEC.loader
MODEL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODEL
SPEC.loader.exec_module(MODEL)


class P101RModelTests(unittest.TestCase):
    def test_source_identity_encoding_is_airtime_neutral(self) -> None:
        self.assertEqual(MODEL.encode_data_lane_byte(1, 0), 0x04)
        self.assertEqual(MODEL.encode_data_lane_byte(2, 1), 0x09)
        self.assertEqual(MODEL.encode_ack_direction_byte(1, 1), 0x05)
        self.assertEqual(MODEL.encode_ack_direction_byte(2, 0), 0x08)

    def test_performance_model_closes_four_mbit_gate(self) -> None:
        result = MODEL.performance_model()
        self.assertTrue(result["gate_pass"])
        self.assertGreaterEqual(result["modeled_fixed_to_rotating_bps"], 4_000_000)
        self.assertGreaterEqual(result["modeled_rotating_to_fixed_bps"], 4_000_000)
        self.assertTrue(result["overhead_counters_overlap"])

    def test_required_random_event_counts_and_seeds(self) -> None:
        admission = MODEL.stress_admission()
        ack = MODEL.stress_ack_window()
        reset_fault = MODEL.stress_reset_fault()
        self.assertEqual(admission["event_count"], 50_000)
        self.assertEqual(ack["event_count"], 50_000)
        self.assertEqual(reset_fault["event_count"], 25_000)
        self.assertEqual(admission["seeds"], list(MODEL.SEEDS))
        self.assertTrue(admission["pass"])
        self.assertTrue(ack["pass"])
        self.assertTrue(reset_fault["pass"])

    def test_register_map_is_additive_and_versioned(self) -> None:
        register_map = json.loads(
            (ROOT / "config/register_map/ir_axi_regs.yaml").read_text(encoding="utf-8")
        )
        by_name = {item["name"]: int(item["offset"], 0)
                   for item in register_map["registers"]}
        self.assertEqual(register_map["register_map_version"], "P10-2")
        self.assertEqual(by_name["P10_1R_SNAPSHOT_CONTROL"], 0x0A00)
        self.assertEqual(by_name["P10_1R_SNAPSHOT_GENERATION"], 0x0A04)
        self.assertEqual(by_name["P10_1R_CROSS_LANE_ACCEPTED"], 0x0A94)

    def test_runtime_has_no_active_per_object_optical_ready_roundtrip(self) -> None:
        runtime = (ROOT / "software/ps_driver/p10_1_runtime_extension.inc").read_text(
            encoding="utf-8"
        )
        active = runtime.split("#endif", 1)[1]
        # The only active send/wait calls are the single stream-level remote
        # commit confirmation, not object-loop readiness handshakes.
        self.assertEqual(active.count("p10_1_send_signal("), 1)
        self.assertEqual(active.count("p10_1_wait_signal("), 1)
        self.assertIn("next_object_prestarted", active)
        self.assertIn("result->host_command_count = 1U", active)

    def test_admission_is_triggered_from_final_physical_txd(self) -> None:
        rtl = (ROOT / "rtl/p10_1r_rx_admission.sv").read_text(encoding="utf-8")
        self.assertIn("final_physical_txd_i", rtl)
        self.assertIn("!final_physical_txd_i", rtl)
        self.assertIn("sat_inc32", rtl)
        self.assertNotIn(
            "fail_closed_q <= 1'b0;\n        raw_pulse_count_o",
            rtl,
        )
        self.assertNotIn("GLOBAL_PERMIT", rtl.replace("// it has no path to GLOBAL_PERMIT", ""))

    def test_remediation_defaults_are_frozen(self) -> None:
        pipeline = (ROOT / "config/performance/p10_1_pipeline.yaml").read_text(
            encoding="utf-8"
        )
        runtime = (
            ROOT / "config/performance/p10_1r_hardware_runtime.yaml"
        ).read_text(encoding="utf-8")
        core = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(
            encoding="utf-8"
        )
        for marker in (
            "descriptor_ring_depth: 32", "descriptor_batch: 8",
            "ack_aggregation_threshold: 32", "outstanding_frames: 32",
        ):
            self.assertIn(marker, pipeline)
        for marker in (
            "endpoint_burst_frames: 32", "ack_threshold: 32",
            "per_object_optical_ready_roundtrip: false",
            "minimum_concurrent_host_objects_or_equivalent: 4",
        ):
            self.assertIn(marker, runtime)
        self.assertIn("dp_attempt_descriptor[0] || dp_attempt_retry", core)


if __name__ == "__main__":
    unittest.main()
