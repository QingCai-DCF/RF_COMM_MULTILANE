from __future__ import annotations

import importlib.util
import json
import re
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "scripts/p10_hardware_runtime.py"
SHUTDOWN_TCL = ROOT / "scripts/hw/p10_program_dual_shutdown.tcl"
STAGE_TCL = ROOT / "scripts/hw/p10_dual_xsdb_stage.tcl"


def load_runtime():
    spec = importlib.util.spec_from_file_location("p10_hardware_runtime", RUNTIME)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class P10HardwareRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = load_runtime()

    def test_formal_plan_covers_required_stages_and_masks(self) -> None:
        plans = self.runtime.build_plans()
        self.assertEqual(set(self.runtime.ALL_FORMAL_STAGES),
                         {key for key in plans if re.fullmatch(r"P10-[A-J]", key)})
        for stage in self.runtime.ALL_FORMAL_STAGES:
            self.assertTrue(plans[stage])
            for item in plans[stage]:
                if isinstance(item, self.runtime.Case):
                    item.validate()
                    self.assertLessEqual(item.lane, 3)
                    self.assertLessEqual(item.unavailable, 3)
                    self.assertLessEqual(item.injectmask, 3)
        self.assertEqual(
            [item.rawtarget for item in plans["P10-B"]
             if isinstance(item, self.runtime.Case)],
            [64, 1024, 64, 1024, 64, 1024, 64, 1024],
        )
        object_sizes = {item.size for item in plans["P10-F"]
                        if isinstance(item, self.runtime.Case)}
        self.assertEqual(object_sizes, {4096, 65536, 1048576, 16 * 1048576})
        self.assertEqual(plans["P10-J"], [("SOAK", "stationary_30min", "1800")])

    def test_plan_hashes_are_deterministic_and_ascii(self) -> None:
        first = self.runtime.plan_hashes(self.runtime.ALL_FORMAL_STAGES)
        second = self.runtime.plan_hashes(self.runtime.ALL_FORMAL_STAGES)
        self.assertEqual(first, second)
        for stage, digest in first.items():
            self.assertRegex(digest, r"^[0-9a-f]{64}$")
            self.runtime.plan_text(self.runtime.build_plans()[stage]).encode("ascii")

    def test_dynamic_soak_observations_expand_the_immutable_plan(self) -> None:
        rows = []
        for index in range(6):
            size = self.runtime.P10_J_SOAK_SIZES[index % 3]
            direction = index & 1
            rows.append({
                "label": f"soak_{index:05d}_{size}_d{direction}",
                "command": 3,
                "expected_status": 0,
                "flags": 2,
                "lane": 3,
                "direction": direction,
                "rate": 2,
                "size": size,
                "ring": 32,
                "cache": 1,
                "session": 0xA0100001,
                "path": 10,
                "object": 0x3A000000 + index,
                "window": "ACCEPTANCE",
            })
        rows.append({"label": "P10-J_endpoint_shutdown"})
        self.assertEqual(
            self.runtime.validate_observation_shape(
                "P10-J", [self.runtime.P10_J_SOAK_PLAN], rows),
            [],
        )

        rows[2] = {**rows[2], "direction": 1}
        self.assertIn(
            "stationary soak fields mismatch at index 2",
            self.runtime.validate_observation_shape(
                "P10-J", [self.runtime.P10_J_SOAK_PLAN], rows),
        )

    def test_reboot_directives_do_not_create_mailbox_observations(self) -> None:
        plan = self.runtime.build_plans()["P10-G"]
        rows = [{"label": item.label} for item in plan
                if isinstance(item, self.runtime.Case)]
        rows.append({"label": "P10-G_endpoint_shutdown"})
        self.assertEqual(
            self.runtime.validate_observation_shape("P10-G", plan, rows),
            [],
        )

    def test_shutdown_tcl_requires_both_exact_roles(self) -> None:
        text = SHUTDOWN_TCL.read_text(encoding="utf-8")
        for marker in (
            "RF_COMM_P10_HW_AUTH", "P10_FASTTRACK_IMMUTABLE_AUTHORIZED",
            "xc7z020clg400-2", "23727093", "4BA00477",
            "^xc7z020_1(_[0-9]+)?$", "^arm_dap_0(_[0-9]+)?$",
            "SHUTDOWN_FIXED", "SHUTDOWN_ROTATING",
            "TFDU_SHUTDOWN_PROGRAMMED=1", "SHUTDOWN_EXIT=0",
            "P10_SHUTDOWN_${role}_TXD_OUTPUT_INTENT=0",
        ):
            self.assertIn(marker, text)
        self.assertNotRegex(text.lower(), r"(?m)^\s*dow\s")
        self.assertNotRegex(text.lower(), r"(?m)^\s*rst\s")
        self.assertNotRegex(text.lower(), r"(?m)^\s*mwr\s")

    def test_stage_tcl_is_dual_serial_and_fail_closed(self) -> None:
        text = STAGE_TCL.read_text(encoding="utf-8")
        for marker in (
            "p10_fixed_serial", "p10_rotating_serial", "jtag_cable_serial",
            "P10_SAFE_BOOT=PASS", "P10_ENDPOINT_SHUTDOWN_FIXED=PASS",
            "P10_ENDPOINT_SHUTDOWN_ROTATING=PASS",
            "P10_ENDPOINT_SHUTDOWN_REQUESTED_ON_ERROR=1",
            "p10_prime_base_ms", "p10_prime_per_mib_ms",
            "0x0000001A", "0x00000F00", "0x0003FFFF",
        ):
            self.assertIn(marker, text)
        self.assertNotIn("socket", text.lower())
        self.assertNotIn("ethernet", text.lower())
        self.assertNotRegex(text.lower(), r"lane[^\n]*0x[4-9a-f]")

    def test_hardware_identity_uses_canonical_register_map(self) -> None:
        manifest = json.loads(
            (
                ROOT / "config/register_map/generated/ir_regs_manifest.json"
            ).read_text(encoding="utf-8")
        )
        expected_version = int(manifest["register_map_version_value"], 0)
        expected_hash = int(manifest["hash_low"], 0)
        self.assertEqual(
            self.runtime.EXPECTED_REGISTER_MAP_VERSION, expected_version
        )
        self.assertEqual(
            self.runtime.EXPECTED_REGISTER_MAP_HASH_LOW, expected_hash
        )
        text = STAGE_TCL.read_text(encoding="utf-8")
        self.assertIn(
            f"set p10_expected_register_map_version 0x{expected_version:08X}",
            text,
        )
        self.assertIn(
            f"set p10_expected_register_map_hash_low 0x{expected_hash:08X}",
            text,
        )
        self.assertNotIn("0x09000003", text)
        self.assertNotIn("0xCF35F13A", text)

    def test_runtime_requires_explicit_hardware_enable_and_finally_shutdown(self) -> None:
        text = RUNTIME.read_text(encoding="utf-8")
        for marker in (
            "--execute-hardware", "NO_HARDWARE", "CURRENT_RUN_HARDWARE_AUTHORIZATION",
            "P10_FASTTRACK_IMMUTABLE_AUTHORIZED", "finally_emergency",
            "SHUTDOWN_FIXED", "SHUTDOWN_ROTATING", "maximum_lane_mask",
            'git("status", "--porcelain")',
        ):
            self.assertIn(marker, text)
        self.assertNotIn("git reset --hard", text)
        self.assertNotIn("git push", text)


if __name__ == "__main__":
    unittest.main()
