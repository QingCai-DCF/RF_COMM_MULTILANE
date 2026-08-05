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
        self.assertTrue(all(item.command == 3 and item.injectdelay == 0
                            for item in injected))
        self.assertTrue(all(
            item.dropack == self.runner.MIGRATION_ACK_SUPPRESSION == 0
            for item in injected
        ))
        self.assertEqual(
            {item.injectmask: item.weights for item in injected},
            self.runner.MIGRATION_TARGET_WEIGHTS,
        )
        self.assertTrue(all(
            item.unavailable == 0
            for item in injected
        ))
        self.assertTrue(all(
            item.faultflags == self.runner.migration_protocol_fault_flags(
                item.injectmask
            )
            for item in injected
        ))
        self.assertEqual(
            self.runner.MIGRATION_PROTOCOL_FAULT_FLAGS,
            (1 << 4) | (1 << 16),
        )
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn("$command in {3 13} && [dict get $d injectmask] != 0", tcl)
        self.assertIn("P10_ATOMIC_LANE_INJECTION=", tcl)
        self.assertIn("set injection_atomic_status [p10_read32 $sender 0x43C008BC]", tcl)
        self.assertIn("$injection_trigger_ack_base != $injection_initial_sequence", tcl)
        self.assertIn("$injection_trigger_physical_tx_count <=", tcl)
        self.assertIn("$injection_trigger_migration_count != 0", tcl)
        self.assertIn("$injection_pre_target_crc_bad <= 0", tcl)

    def test_degrade_static_mask_classifier_excludes_inflight_setup_masks(self) -> None:
        cases = [item for item in self.runner.build_plans()["degrade"]
                 if isinstance(item, self.runner.Case)]
        details = [
            {"unavailable": item.unavailable, "injectmask": item.injectmask}
            for item in cases
        ]
        self.assertEqual(
            self.runner.static_degrade_unavailable_masks(details),
            [1, 2, 4, 8, 3, 7],
        )
        self.assertEqual(
            [detail["unavailable"] for detail in details
             if detail["injectmask"]],
            [0, 0, 0, 0],
        )

    def test_module_intake_proves_both_raw_directions_before_frames(self) -> None:
        cases = [item for item in self.runner.build_plans()["module_intake"]
                 if isinstance(item, self.runner.Case)]
        labels = [item.label for item in cases]
        raw_labels = [
            f"intake_{module}_raw_{count}"
            for module in ("F0", "R0", "F1", "R1", "F2", "R2", "F3", "R3")
            for count in (64, 1024)
        ]
        self.assertEqual(labels[1:1 + len(raw_labels)], raw_labels)
        self.assertEqual(
            {item.lane for item in cases if item.command == 2},
            {1, 2, 4, 8},
        )
        first_frame = min(index for index, item in enumerate(cases)
                          if item.command == 3)
        last_raw = max(index for index, item in enumerate(cases)
                       if item.command == 2)
        self.assertGreater(first_frame, last_raw)

    def test_four_lane_phy_safety_mask_does_not_alias_startup(self) -> None:
        tcl = STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn(
            "set p10_phy_field_width [expr {2 * $p10_lane_count}]", tcl
        )
        self.assertIn("($phy & $p10_phy_safety_mask)", tcl)
        self.assertNotIn("($phy & 0x00000F00)", tcl)

        for lane_count, expected in ((2, 0x00000F00), (4, 0x00FF0000)):
            field_width = 2 * lane_count
            mask = ((1 << field_width) - 1) << (2 * field_width)
            self.assertEqual(mask, expected)
            startup_mask = ((1 << field_width) - 1) << field_width
            self.assertEqual(mask & startup_mask, 0)

        self.assertEqual(self.runner.mailbox_detail.__module__,
                         "p10_hardware_runtime")
        import p10_hardware_runtime as runtime
        self.assertEqual(runtime.phy_safety_mask(2), 0x00000F00)
        self.assertEqual(runtime.phy_safety_mask(4), 0x00FF0000)
        with self.assertRaises(ValueError):
            runtime.phy_safety_mask(8)

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

    def test_xsdb_register_map_identity_is_backward_compatible_and_overridable(self) -> None:
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
        # The defaults remain the frozen P10.3 identity so historical P10.3
        # replay is unchanged.  P10.4 passes its immutable map identity via
        # the new 20-argument interface.
        self.assertEqual(
            version.group(1).upper(),
            "0X0A000003",
        )
        self.assertEqual(hash_low.group(1).upper(), "0XFFA1C1B3")
        self.assertIn("if {[llength $argv] == 20}", source)
        self.assertIn("p10_expected_register_map_version 18", source)
        self.assertIn("p10_expected_register_map_hash_low 19", source)
        p104 = (ROOT / "scripts/run_p10_4_hardware.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            f"REGISTER_MAP_VERSION = {manifest['register_map_version_value']}",
            p104,
        )
        self.assertIn(
            f"REGISTER_MAP_HASH_LOW = {manifest['hash_low']}", p104
        )

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

    def test_terminal_sequence_register_is_decoded_before_wrap_comparison(self) -> None:
        state = self.runner.terminal_transport_state({
            "terminal_tx_sequence_base": 0x005E005E,
            "terminal_window_status": (32 << 22) | 0xFFFE,
        })
        self.assertEqual(state["tx_next_sequence"], 0x005E)
        self.assertEqual(state["tx_ack_base"], 0x005E)
        self.assertEqual(state["rx_base_sequence"], 0xFFFE)
        self.assertEqual(state["tx_outstanding"], 0)
        self.assertEqual(state["tx_outstanding_high_watermark"], 32)

    def test_ack_loss_can_drain_by_later_cumulative_ack_without_retry(self) -> None:
        frames = 512
        detail = {
            "label": "arq_ack_loss",
            "direction": 1,
            "plan_fields": {"size": 247 * frames, "initialseq": 0},
            "fixed": {
                "ack_aggregation": frames,
                "transport": {
                    "physical_drop_ack": 1,
                    "rx_delivery": frames,
                    "rx_base_sequence": frames,
                },
            },
            "rotating": {
                "terminal_tx_sequence_base": (frames << 16) | frames,
                "terminal_window_status": 32 << 22,
                "physical_ack_good": 16,
                "tx_attempts": frames,
                "tx_retries": 0,
                "retry_exhausted": 0,
                "transport": {},
            },
        }
        errors, recovery = self.runner.ack_loss_recovery_errors(detail)
        self.assertEqual(errors, [])
        self.assertEqual(
            recovery["recovery_mode"],
            "later_cumulative_ack_without_retransmission",
        )

        detail["rotating"]["terminal_tx_sequence_base"] = (
            ((frames - 1) << 16) | frames
        )
        errors, _ = self.runner.ack_loss_recovery_errors(detail)
        self.assertTrue(any("terminal sequence state mismatch" in error
                            for error in errors))


if __name__ == "__main__":
    unittest.main()
