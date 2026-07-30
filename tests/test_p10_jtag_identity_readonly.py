from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/run_p10_jtag_identity_readonly.py"
TCL = ROOT / "scripts/hw/p10_jtag_identity_readonly.tcl"


def load_module():
    spec = importlib.util.spec_from_file_location("p10_jtag_identity_readonly", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class P10JtagIdentityReadonlyTests(unittest.TestCase):
    def test_tcl_has_only_read_only_jtag_discovery(self) -> None:
        text = TCL.read_text(encoding="utf-8")
        executable = "\n".join(
            line.strip() for line in text.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ).lower()
        self.assertEqual(executable.count("jtag targets -target-properties"), 1)
        self.assertIn("connect -url", executable)
        self.assertIn("disconnect", executable)
        for forbidden in (
            "program_hw_devices", "open_hw_target", "fpga -file", "dow ",
            "rst ", "mrd ", "mwr ", "targets -set", "targets -filter",
            "con ", "stop ", "bpadd", "after ",
        ):
            self.assertNotIn(forbidden, executable)

    def test_marker_parser_preserves_two_serials_and_four_devices(self) -> None:
        module = load_module()
        content = "\n".join([
            "P10_JTAG_CABLE_1_SERIAL=SERIAL_A",
            "P10_JTAG_CABLE_2_SERIAL=SERIAL_B",
            "P10_JTAG_DEVICE_COUNT=4",
            "P10_JTAG_DEVICE_1_CABLE_SERIAL=SERIAL_A",
            "P10_JTAG_DEVICE_1_NAME=arm_dap",
            "P10_JTAG_DEVICE_1_IDCODE=4BA00477",
            "P10_JTAG_DEVICE_2_CABLE_SERIAL=SERIAL_A",
            "P10_JTAG_DEVICE_2_NAME=xc7z020",
            "P10_JTAG_DEVICE_2_IDCODE=23727093",
            "P10_JTAG_DEVICE_3_CABLE_SERIAL=SERIAL_B",
            "P10_JTAG_DEVICE_3_NAME=arm_dap",
            "P10_JTAG_DEVICE_3_IDCODE=4BA00477",
            "P10_JTAG_DEVICE_4_CABLE_SERIAL=SERIAL_B",
            "P10_JTAG_DEVICE_4_NAME=xc7z020",
            "P10_JTAG_DEVICE_4_IDCODE=23727093",
            "P10_JTAG_IDENTITY_RESULT=PASS",
        ]) + "\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "result.txt"
            path.write_text(content, encoding="utf-8")
            markers = module.parse_markers(path)
        serials, devices = module.marker_inventory(markers)
        self.assertEqual(serials, ["SERIAL_A", "SERIAL_B"])
        self.assertEqual(len(devices), 4)
        self.assertEqual(devices[1]["name"], "xc7z020")
        self.assertEqual(devices[3]["cable_serial"], "SERIAL_B")

    def test_run_id_and_authorization_are_bounded(self) -> None:
        module = load_module()
        self.assertTrue(module.RUN_ID_RE.fullmatch("p10_jtag_identity_20260730T120000Z_deadbeef"))
        self.assertFalse(module.RUN_ID_RE.fullmatch("../p10_jtag_identity_20260730T120000Z_deadbeef"))
        self.assertEqual(module.AUTH_MARKER, "P10_FASTTRACK_READ_ONLY_IDENTITY")
        self.assertEqual(module.GOAL_SHA256, "b7cf8f1e10d737ce587f81160df592c8f863825b009760bd32845e019c3b7603")


if __name__ == "__main__":
    unittest.main()
