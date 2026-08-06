from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "check_m4_static_subject", ROOT / "scripts/check_m4_static.py"
)
assert SPEC is not None and SPEC.loader is not None
subject = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = subject
SPEC.loader.exec_module(subject)


class M4RegisterOwnershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        register_map = json.loads(
            (ROOT / "config/register_map/ir_axi_regs.yaml").read_text(
                encoding="utf-8"
            )
        )
        cls.offsets = {
            item["name"]: int(item["offset"], 16)
            for item in register_map["registers"]
        }
        cls.endpoint_rtl = (
            ROOT / "rtl/p9_axi_dma_peripheral.sv"
        ).read_text(encoding="utf-8")
        cls.performance_rtl = (
            ROOT / "rtl/p10_1_perf_monitor.sv"
        ).read_text(encoding="utf-8")

    def test_p10_2_snapshot_window_is_range_and_depth_proven(self) -> None:
        names = [name for name in self.offsets if name.startswith("P10_2_")]
        self.assertEqual(4, len(names))
        for name in names:
            self.assertTrue(
                subject.p10_2_rtl_consumes_register(
                    name, self.offsets[name], self.endpoint_rtl
                ),
                name,
            )
        base = self.offsets["P10_2_SNAPSHOT_DATA_BASE"]
        self.assertFalse(
            subject.p10_2_rtl_consumes_register(
                "P10_2_SNAPSHOT_DATA_BASE", base + 4, self.endpoint_rtl
            )
        )
        self.assertFalse(
            subject.p10_2_rtl_consumes_register(
                "P10_2_SNAPSHOT_DATA_BASE",
                base,
                self.endpoint_rtl.replace("reg_rd_addr <= 12'hD08", "1'b0"),
            )
        )

    def test_first_fault_window_is_owned_by_endpoint_decoder(self) -> None:
        names = [name for name in self.offsets if name.startswith("P10_FF_")]
        self.assertEqual(29, len(names))
        for name in names:
            self.assertTrue(
                subject.p9_rtl_consumes_register(
                    name, self.offsets[name], self.endpoint_rtl
                ),
                name,
            )
        target = "P10_FF_CAPABILITIES"
        self.assertFalse(
            subject.p9_rtl_consumes_register(
                target,
                self.offsets[target],
                self.endpoint_rtl.replace(f"`IR_REG_{target}", "`REMOVED", 1),
            )
        )
        self.assertFalse(
            subject.p9_rtl_consumes_register(
                "P10_FF_ARCHIVE_DIGEST0",
                self.offsets["P10_FF_ARCHIVE_DIGEST0"],
                "assign index = address - `IR_REG_P10_FF_ARCHIVE_DIGEST0;",
            )
        )

    def test_p10_4_counters_require_monitor_decode_and_endpoint_route(self) -> None:
        names = [
            name
            for name, offset in self.offsets.items()
            if name.startswith("P10_4_") and 0xD84 <= offset <= 0xDAC
        ]
        self.assertEqual(11, len(names))
        for name in names:
            self.assertTrue(
                subject.p10_4_rtl_consumes_register(
                    name,
                    self.offsets[name],
                    self.endpoint_rtl,
                    self.performance_rtl,
                ),
                name,
            )
        target = "P10_4_COUNTER_SCHEMA"
        self.assertFalse(
            subject.p10_4_rtl_consumes_register(
                target,
                self.offsets[target],
                self.endpoint_rtl.replace("reg_rd_addr <= 12'hDAC", "1'b0"),
                self.performance_rtl,
            )
        )
        self.assertFalse(
            subject.p10_4_rtl_consumes_register(
                target,
                self.offsets[target],
                self.endpoint_rtl,
                self.performance_rtl.replace(f"`IR_REG_{target}", "`REMOVED", 1),
            )
        )

    def test_p10_4_local_source_registers_require_endpoint_decode(self) -> None:
        names = [
            name
            for name, offset in self.offsets.items()
            if name.startswith("P10_4_") and 0xDB0 <= offset <= 0xDBC
        ]
        self.assertEqual(4, len(names))
        for name in names:
            self.assertTrue(
                subject.p10_4_rtl_consumes_register(
                    name,
                    self.offsets[name],
                    self.endpoint_rtl,
                    self.performance_rtl,
                ),
                name,
            )
        target = "P10_4_LOCAL_SOURCE_TEST_STATUS"
        self.assertFalse(
            subject.p10_4_rtl_consumes_register(
                target,
                self.offsets[target],
                self.endpoint_rtl.replace(f"`IR_REG_{target}", "`REMOVED", 1),
                self.performance_rtl,
            )
        )


if __name__ == "__main__":
    unittest.main()
