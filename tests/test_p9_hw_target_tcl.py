from __future__ import annotations

import tempfile
import tkinter
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = ROOT / "scripts/hw/p9_hw_preflight.tcl"
SHUTDOWN = ROOT / "scripts/hw/p9_program_shutdown.tcl"
XSDB_STAGE = ROOT / "scripts/hw/p9_xsdb_stage.tcl"
TARGET = "localhost:3121/xilinx_tcf/Digilent/210512180081"
BOARD_ID = "210512180081"
PART = "xc7z010clg400-1"

DEVICE_PROPERTIES = {
    "arm_dap_0": ("arm_dap", "arm_dap_0", "01001011101000000000010001110111"),
    "xc7z010_1": ("xc7z010", "xc7z010_1", "00010011011100100010000010010011"),
    "xc7z010_clone": ("xc7z010", "xc7z010_1", "13722093"),
    "xc7z020_2": ("xc7z020", "xc7z020_2", "13727093"),
}


class P9HardwareTargetTclTests(unittest.TestCase):
    def run_script(self, script: Path, devices: tuple[str, ...]) -> tuple[int, str, tuple[str, ...]]:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            authorization = directory / "phase2.json"
            bitstream = directory / "shutdown.bit"
            result = directory / "result.txt"
            authorization.write_text("{}\n", encoding="ascii")
            bitstream.write_bytes(b"immutable-shutdown-test")

            interp = tkinter.Tcl()
            interp.setvar("env(RF_COMM_P9_HW_AUTH)", "P9_PHASE2_IMMUTABLE_AUTHORIZED")
            interp.setvar("p9_stub_target", TARGET)
            interp.setvar("p9_stub_devices", devices)
            for device, (part, name, idcode) in DEVICE_PROPERTIES.items():
                interp.setvar(f"p9_part({device})", part)
                interp.setvar(f"p9_name({device})", name)
                interp.setvar(f"p9_idcode({device})", idcode)
            interp.eval(
                """
                proc exit {{code 0}} {
                  set ::p9_exit_code $code
                  error "__P9_CAPTURED_EXIT__$code"
                }
                set ::p9_programmed {}
                proc open_hw_manager {args} {}
                proc connect_hw_server {args} {}
                proc get_hw_targets {args} {return [list $::p9_stub_target]}
                proc current_hw_target {args} {}
                proc open_hw_target {args} {}
                proc get_hw_devices {args} {return $::p9_stub_devices}
                proc get_property {property object} {
                  switch -- $property {
                    PART {return $::p9_part($object)}
                    NAME {return $::p9_name($object)}
                    IDCODE {return $::p9_idcode($object)}
                    default {error "unexpected property $property"}
                  }
                }
                proc current_hw_device {args} {}
                proc refresh_hw_device {args} {}
                proc set_property {args} {}
                proc program_hw_devices {device} {lappend ::p9_programmed $device}
                proc close_hw_target {args} {}
                proc disconnect_hw_server {args} {}
                proc close_hw_manager {args} {}
                """
            )
            arguments = ["localhost:3121", TARGET, BOARD_ID, PART, str(authorization)]
            if script == SHUTDOWN:
                arguments.append(str(bitstream))
            arguments.append(str(result))
            interp.setvar("argv", tuple(arguments))

            with self.assertRaises(tkinter.TclError) as captured:
                interp.eval(script.read_text(encoding="utf-8"))
            self.assertIn("__P9_CAPTURED_EXIT__", str(captured.exception))
            exit_code = int(interp.getvar("p9_exit_code"))
            programmed = tuple(interp.splitlist(interp.getvar("p9_programmed")))
            return exit_code, result.read_text(encoding="utf-8"), programmed

    def test_expected_arm_dap_and_one_exact_fpga_are_accepted(self) -> None:
        devices = ("arm_dap_0", "xc7z010_1")
        for script in (PREFLIGHT, SHUTDOWN):
            with self.subTest(script=script.name):
                code, result, programmed = self.run_script(script, devices)
                self.assertEqual(0, code)
                self.assertIn("HW_OBJECT_COUNT=2", result)
                self.assertIn("EXACT_FPGA_MATCH_COUNT=1", result)
                self.assertIn("AUXILIARY_DAP_COUNT=1", result)
                self.assertIn("UNEXPECTED_HW_OBJECT_COUNT=0", result)
                self.assertIn("arm_dap_0|PART=arm_dap|NAME=arm_dap_0", result)
                self.assertIn("xc7z010_1|PART=xc7z010|NAME=xc7z010_1", result)
                self.assertEqual(("xc7z010_1",) if script == SHUTDOWN else (), programmed)

    def test_two_exact_fpgas_fail_before_programming(self) -> None:
        devices = ("arm_dap_0", "xc7z010_1", "xc7z010_clone")
        for script in (PREFLIGHT, SHUTDOWN):
            with self.subTest(script=script.name):
                code, result, programmed = self.run_script(script, devices)
                self.assertNotEqual(0, code)
                self.assertIn("EXACT_FPGA_MATCH_COUNT=2", result)
                self.assertIn("RESULT=FAIL", result)
                self.assertEqual((), programmed)

    def test_unexpected_hardware_object_fails_before_programming(self) -> None:
        devices = ("arm_dap_0", "xc7z010_1", "xc7z020_2")
        for script in (PREFLIGHT, SHUTDOWN):
            with self.subTest(script=script.name):
                code, result, programmed = self.run_script(script, devices)
                self.assertNotEqual(0, code)
                self.assertIn("EXACT_FPGA_MATCH_COUNT=1", result)
                self.assertIn("UNEXPECTED_HW_OBJECT_COUNT=1", result)
                self.assertIn("RESULT=FAIL", result)
                self.assertEqual((), programmed)

    def test_preflight_remains_read_only_and_both_scripts_filter_exactly(self) -> None:
        preflight = PREFLIGHT.read_text(encoding="utf-8")
        shutdown = SHUTDOWN.read_text(encoding="utf-8")
        self.assertNotIn("program_hw_devices", preflight)
        for text in (preflight, shutdown):
            self.assertIn("if {$exact_device_count != 1}", text)
            self.assertIn("if {$unexpected_device_count != 0}", text)
            self.assertNotIn("[llength $all_devices] != 1", text)
            self.assertNotIn("[llength $devices] != 1", text)

    def xsdb_identity_interp(self) -> tkinter.Tcl:
        interp = tkinter.Tcl()
        source = XSDB_STAGE.read_text(encoding="utf-8")
        interp.eval(source[: source.index("if {[llength $argv] != 12}")])
        return interp

    def test_xsdb_accepts_dap_tap_plus_one_exact_zynq_tap(self) -> None:
        interp = self.xsdb_identity_interp()
        interp.eval(
            f"""
            set records [list \
              [dict create level 0 jtag_cable_serial {BOARD_ID}] \
              [dict create node_id 1 name arm_dap idcode 4BA00477] \
              [dict create node_id 2 name xc7z010 idcode 13722093]]
            set identity [p9_select_jtag_identity $records {BOARD_ID}]
            """
        )
        self.assertEqual("2", interp.eval("llength [dict get $identity device_nodes]"))
        self.assertEqual("1", interp.eval("llength [dict get $identity exact_device_matches]"))
        self.assertEqual("2", interp.eval("dict get [dict get $identity device] node_id"))

    def test_xsdb_rejects_duplicate_exact_zynq_taps(self) -> None:
        interp = self.xsdb_identity_interp()
        with self.assertRaises(tkinter.TclError):
            interp.eval(
                f"""
                p9_select_jtag_identity [list \
                  [dict create level 0 jtag_cable_serial {BOARD_ID}] \
                  [dict create node_id 1 name arm_dap idcode 4BA00477] \
                  [dict create node_id 2 name xc7z010 idcode 13722093] \
                  [dict create node_id 3 name xc7z010 idcode 0x13722093]] {BOARD_ID}
                """
            )

    def test_xsdb_rejects_second_or_wrong_cable_root(self) -> None:
        interp = self.xsdb_identity_interp()
        with self.assertRaises(tkinter.TclError):
            interp.eval(
                f"""
                p9_select_jtag_identity [list \
                  [dict create level 0 jtag_cable_serial {BOARD_ID}] \
                  [dict create level 0 jtag_cable_serial 999999999999] \
                  [dict create node_id 2 name xc7z010 idcode 13722093]] {BOARD_ID}
                """
            )

    def test_xsdb_waits_for_complete_authorized_chain(self) -> None:
        interp = self.xsdb_identity_interp()
        interp.eval(
            f"""
            set ::p9_jtag_calls 0
            set ::p9_jtag_snapshots [list \
              [list] \
              [list \
                [dict create level 0 jtag_cable_serial {BOARD_ID}] \
                [dict create node_id 1 name arm_dap idcode 4BA00477]] \
              [list \
                [dict create level 0 jtag_cable_serial {BOARD_ID}] \
                [dict create node_id 1 name arm_dap idcode 4BA00477] \
                [dict create node_id 2 name xc7z010 idcode 13722093]]]
            proc jtag {{subcommand args}} {{
              incr ::p9_jtag_calls
              return [lindex $::p9_jtag_snapshots [expr {{$::p9_jtag_calls - 1}}]]
            }}
            set identity [p9_wait_jtag_identity {BOARD_ID} 3 0]
            """
        )
        self.assertEqual("3", interp.eval("dict get $identity discovery_attempts"))
        self.assertEqual("3", interp.eval("set ::p9_jtag_calls"))
        self.assertEqual("2", interp.eval("llength [dict get $identity device_nodes]"))

    def test_xsdb_wait_rejects_ambiguous_root_immediately(self) -> None:
        interp = self.xsdb_identity_interp()
        interp.eval(
            f"""
            set ::p9_jtag_calls 0
            proc jtag {{subcommand args}} {{
              incr ::p9_jtag_calls
              return [list \
                [dict create level 0 jtag_cable_serial {BOARD_ID}] \
                [dict create level 0 jtag_cable_serial 999999999999] \
                [dict create node_id 1 name arm_dap idcode 4BA00477] \
                [dict create node_id 2 name xc7z010 idcode 13722093]]
            }}
            """
        )
        with self.assertRaises(tkinter.TclError):
            interp.eval(f"p9_wait_jtag_identity {BOARD_ID} 3 0")
        self.assertEqual("1", interp.eval("set ::p9_jtag_calls"))


if __name__ == "__main__":
    unittest.main()
