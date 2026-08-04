from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts/run_p10_3_ax7020_4lane_hardware.py"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"


def load_runner():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    spec = importlib.util.spec_from_file_location("p10_3_hardware_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class P103HardwareAcceptanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runner = load_runner()

    def test_scope_and_plan_are_four_lane_stationary_only(self) -> None:
        plans = self.runner.build_plans()
        self.assertEqual(tuple(plans), self.runner.STAGES)
        self.assertEqual(self.runner.validate_plans(plans), [])
        self.assertEqual(self.runner.MODULES,
                         ("F0", "F1", "F2", "F3", "R0", "R1", "R2", "R3"))
        masks = set()
        for stage, items in plans.items():
            self.assertTrue(items, stage)
            self.runner.plan_text(items).encode("ascii")
            for item in items:
                if isinstance(item, self.runner.Case):
                    item.plan_line()
                    self.assertLessEqual(item.lane, 0xF)
                    self.assertLessEqual(item.unavailable, 0xF)
                    self.assertLessEqual(item.injectmask, 0xF)
                    self.assertIn(item.direction, (0, 1))
                    if stage == "mask_matrix":
                        masks.add(item.lane)
        self.assertEqual(masks, set(range(1, 16)))
        self.assertEqual(plans["formal_30min"],
                         [("P101_FORMAL", "stationary_30min", "1800")])

    def test_degrade_vectors_really_apply_streaming_lane_faults(self) -> None:
        cases = [item for item in self.runner.build_plans()["degrade"]
                 if isinstance(item, self.runner.Case)]
        injected = [item for item in cases if item.injectmask]
        self.assertEqual({item.injectmask for item in injected}, {1, 2, 4, 8})
        self.assertTrue(all(item.command == 3 and item.injectdelay == 100
                            for item in injected))
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("$command in {3 13} && [dict get $d injectmask] != 0", tcl)
        self.assertIn("set prior_fault [p10_read32 $sender 0x43C0073C]", tcl)
        self.assertIn("P10_ASYNC_LANE_INJECTION=", tcl)

    def test_command13_fields_and_object_ids_are_unambiguous(self) -> None:
        plans = self.runner.build_plans()
        intervals = []
        for stage, items in plans.items():
            for item in items:
                if not isinstance(item, self.runner.Case):
                    continue
                self.assertEqual(self.runner.case_semantic_errors(item), [])
                if item.command == 13:
                    self.assertEqual(item.dropdata,
                                     self.runner.STREAM_ACK_THRESHOLD)
                    self.assertEqual(item.dropack,
                                     self.runner.STREAM_OUTSTANDING)
                    count = self.runner.stream_object_count(item.size)
                elif item.command == 3:
                    count = 1
                else:
                    continue
                intervals.append((item.object, item.object + count - 1,
                                  f"{stage}:{item.label}"))
        intervals.sort()
        for previous, current in zip(intervals, intervals[1:]):
            self.assertLess(previous[1], current[0],
                            f"object-ID overlap: {previous[2]} / {current[2]}")

    def test_atomic_four_lane_snapshot_prefix_order(self) -> None:
        words = [0] * 128
        words[0] = (247 << 24) | (32 << 16) | (4 << 8) | 8
        words[124] = 64000
        words[125] = self.runner.HARD_DUTY_MAX_CYCLES
        words[126] = self.runner.TARGET_DUTY_CYCLES
        words[127] = self.runner.P103_SCHEMA
        generation = 2
        values = [generation, self.runner.P103_SCHEMA, *words]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.psv"
            path.write_text("|".join(str(value) for value in values) + "\n",
                            encoding="ascii")
            parsed = self.runner.parse_p103(path)
        self.assertEqual(parsed["generation"], generation)
        self.assertEqual(parsed["schema"], "0x50310201")
        self.assertEqual(parsed["duty_window_cycles"], 64000)
        self.assertEqual(parsed["payload_bytes"], 247)
        self.assertEqual(parsed["window_size"], 32)

    def test_formal_window_is_bounded_and_tracks_actual_object_ranges(self) -> None:
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("incr next_object_id $consumed_ids", tcl)
        self.assertIn("$active_ms < 798000", tcl)
        self.assertIn("duration_sec != 840", tcl)
        self.assertIn("formal autonomous stream exceeded its bounded deadline", tcl)

    def test_ps_gpio_evidence_samples_safe_boot_activity_and_shutdown(self) -> None:
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("0xE000A060", tcl)
        self.assertIn("0xE000A204", tcl)
        self.assertIn("0xE000A208", tcl)
        self.assertIn("p10_record_ps_gpio 0 SAFE_BOOT", tcl)
        self.assertIn('p10_record_ps_gpio $sequence "[dict get $d label]_terminal"',
                      tcl)
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn("def load_ps_gpio", source)
        self.assertIn("PS TX LED active-low state not sampled", source)
        self.assertIn("PS RX LED active-low state not sampled", source)

    def test_authorization_and_artifact_scope_exclude_forbidden_actions(self) -> None:
        source = RUNNER.read_text(encoding="utf-8")
        self.assertIn('"maximum_lane_mask": 15', source)
        self.assertIn('"maximum_single_formal_run_seconds": 1800', source)
        self.assertIn('"old_f1_selected": False', source)
        self.assertIn('"fixed": "AX7020-F/JTAG:210249855178"', source)
        self.assertIn('"rotating": "AX7020-R/JTAG:210512180081"', source)
        self.assertIn('"on_error": True', source)
        self.assertIn('"on_timeout": True', source)
        self.assertIn('"on_ctrl_c": True', source)
        self.assertIn('"on_normal_exit": True', source)
        self.assertIn('"network_used": False', source)
        self.assertIn('"movement": False', source)
        self.assertIn('"rotation": False', source)
        self.assertIn('"rewiring": False', source)
        self.assertIn('"two_hour_test": False', source)
        self.assertIn('"p11": False', source)

    def test_xsdb_register_map_identity_matches_generated_manifest(self) -> None:
        manifest = json.loads((
            ROOT / "config/register_map/generated/ir_regs_manifest.json"
        ).read_text(encoding="utf-8"))
        source = STAGE_TCL.read_text(encoding="utf-8")
        version = re.search(
            r"^set p10_expected_register_map_version (0x[0-9A-Fa-f]{8})$",
            source,
            flags=re.MULTILINE,
        )
        hash_low = re.search(
            r"^set p10_expected_register_map_hash_low (0x[0-9A-Fa-f]{8})$",
            source,
            flags=re.MULTILINE,
        )
        self.assertIsNotNone(version)
        self.assertIsNotNone(hash_low)
        self.assertEqual(
            version.group(1).upper(),
            manifest["register_map_version_value"].upper(),
        )
        self.assertEqual(hash_low.group(1).upper(), manifest["hash_low"].upper())

    def test_strict_duty_boundary_matches_generated_rtl_contract(self) -> None:
        safety = (
            ROOT / "rtl/generated/tfdu_safety_config.svh"
        ).read_text(encoding="utf-8")
        hard_max = re.search(
            r"TFDU_SAFETY_CANONICAL_HARD_MAX_HIGH_CYCLES (\d+)", safety
        )
        target_max = re.search(
            r"TFDU_SAFETY_CANONICAL_TARGET_MAX_HIGH_CYCLES (\d+)", safety
        )
        self.assertIsNotNone(hard_max)
        self.assertIsNotNone(target_max)
        self.assertEqual(self.runner.HARD_DUTY_MAX_CYCLES, int(hard_max.group(1)))
        self.assertEqual(self.runner.TARGET_DUTY_CYCLES, int(target_max.group(1)))

        module = {"tx_high_max": 0, "duty_high_max": 12799, "hard_fault": 0}
        snapshot = {
            "schema": self.runner.P103_SCHEMA,
            "payload_bytes": 247,
            "window_size": 32,
            "lane_count": 4,
            "module_count": 8,
            "safety_fault_mask": 0,
            "overlap_violation": 0,
            "admission_violation": 0,
            "non_target_accepted": 0,
            "cross_lane_accepted": 0,
            "duty_window_cycles": 64000,
            "hard_limit_cycles": 12799,
            "target_limit_cycles": 11520,
            "modules": [dict(module) for _ in range(8)],
        }
        at_max = self.runner.snapshot_errors("boundary", "fixed", snapshot)
        self.assertFalse(any("configuration mismatch" in item for item in at_max))
        self.assertFalse(any("hard duty violation" in item for item in at_max))
        snapshot["modules"][0]["duty_high_max"] = 12800
        above_max = self.runner.snapshot_errors("boundary", "fixed", snapshot)
        self.assertTrue(any("hard duty violation" in item for item in above_max))


if __name__ == "__main__":
    unittest.main()
