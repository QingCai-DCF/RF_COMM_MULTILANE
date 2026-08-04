from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import archive_p10_fault_forensics as archive  # noqa: E402
import run_p10_3f_staircase_hardware as runner  # noqa: E402


def frozen_psv(role: str = "fixed") -> str:
    caps = 0x46440840
    status = 0x000001CF
    snapshot = [0] * 64
    snapshot[0] = archive.SNAPSHOT_MAGIC
    snapshot[1] = archive.SNAPSHOT_SCHEMA
    snapshot[2] = 64
    snapshot[3] = 0x01000844
    snapshot[4] = 0x12345678
    snapshot[5] = 0x9ABCDEF0
    snapshot[6] = 0x00000008
    snapshot[7] = 0x060F0F00
    snapshot[8] = 0x73000001
    snapshot[11] = 0x00110022
    snapshot[12] = 0x04030033
    snapshot[13] = 0x00000033
    snapshot[14] = 0x0000FFFF
    for module in range(4):
        base = 24 + module * 10
        snapshot[base:base + 10] = [
            100 + module, 0, 32, 9000, 10000, 1520, 0,
            (module << 12) | 0x0262, 200 + module, 3,
        ]
    events = [
        [0x46460700, 1, 0, 0x00000000, 0x73000001, 0x00110022, 2, 0xF3000100],
        [0x4646F100, 2, 0, 0x070F0F00, 0x73000001, 0x00110022, 2, 0x00000008],
    ]
    lines = [f"P10_FF_PSV|1|{role}"]
    meta = {
        "capabilities": caps,
        "status": status,
        "fault_sequence": 1,
        "fault_timestamp_low": snapshot[4],
        "fault_timestamp_high": snapshot[5],
        "fault_cause": snapshot[6],
        "snapshot_words": 64,
        "pre_event_count": 1,
        "post_event_count": 1,
        "total_event_count": 2,
        "event_depth": 256,
        "event_words": 8,
    }
    lines.extend(f"META|{key}|0x{value:08X}" for key, value in meta.items())
    lines.extend(f"SNAPSHOT|{index}|0x{value:08X}"
                 for index, value in enumerate(snapshot))
    lines.extend(f"EVENT|{entry}|{word}|0x{value:08X}"
                 for entry, event in enumerate(events)
                 for word, value in enumerate(event))
    lines.append(f"END|{role}")
    return "\n".join(lines) + "\n"


def no_fault_psv(role: str = "fixed") -> str:
    meta = {
        "capabilities": 0x46440840,
        "status": 0x00000180,
        "fault_sequence": 0,
        "fault_timestamp_low": 0,
        "fault_timestamp_high": 0,
        "fault_cause": 0,
        "snapshot_words": 64,
        "pre_event_count": 0,
        "post_event_count": 0,
        "total_event_count": 0,
        "event_depth": 256,
        "event_words": 8,
    }
    return "\n".join([
        f"P10_FF_PSV|1|{role}",
        *(f"META|{key}|0x{value:08X}" for key, value in meta.items()),
        f"END|{role}",
        "",
    ])


class FaultForensicsTests(unittest.TestCase):
    def test_frozen_psv_binary_json_round_trip(self) -> None:
        with self.subTest("canonical frozen archive"):
            from tempfile import TemporaryDirectory
            with TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                source = tmp_path / "fixed.psv"
                source.write_text(frozen_psv(), encoding="utf-8")
                record = archive.parse_psv(source)
                result = archive.write_archive(record, tmp_path / "archive")
                self.assertEqual(result["status"], "FROZEN")
                binary = Path(result["binary"]).read_bytes()
                parsed = archive.parse_binary(binary)
                self.assertEqual(parsed["role"], "fixed")
                self.assertEqual(parsed["event_records"][0][7], 0xF3000100)
                decoded = json.loads(Path(result["json"]).read_text(encoding="utf-8"))
                self.assertEqual(decoded["snapshot"]["modules"][3]["physical_tx_count"], 103)
                self.assertEqual(decoded["snapshot"]["modules"][0]["continuous_high_max_cycles"], 32)
                self.assertEqual(decoded["events"][0]["tag"], "0xF3000100")
                self.assertEqual(len(result["digest_words_little_endian"]), 8)

    def test_no_fault_status_has_header_only_binary(self) -> None:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "rotating.psv"
            source.write_text(no_fault_psv("rotating"), encoding="utf-8")
            result = archive.write_archive(archive.parse_psv(source), tmp_path / "archive")
            self.assertEqual(result["status"], "NO_FAULT")
            self.assertEqual(len(Path(result["binary"]).read_bytes()), archive.HEADER_WORDS * 4)

    def test_incomplete_ordered_read_is_rejected(self) -> None:
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            source = tmp_path / "bad.psv"
            lines = frozen_psv().splitlines()
            source.write_text(
                "\n".join(line for line in lines if not line.startswith("SNAPSHOT|63|")) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "snapshot ordered read"):
                archive.parse_psv(source)

    def test_staircase_and_formal_plans_are_bounded(self) -> None:
        observed = []
        for level, size, tag in runner.LEVELS:
            plan = runner.staircase_plan(level, size, tag)
            cases = [line.split() for line in plan.splitlines() if line.startswith("CASE ")]
            self.assertEqual(len(cases), 2)
            self.assertEqual({int(fields[6]) for fields in cases}, {0, 1})
            self.assertEqual({int(fields[9]) for fields in cases}, {size})
            self.assertTrue(all(int(fields[5]) == 15 for fields in cases))
            observed.append(size)
        self.assertEqual(observed, [1024, 4096, 16384, 65536, 262144])
        formal = runner.formal_plan()
        self.assertIn("P10FF_FORMAL stationary_30min 1800", formal)
        self.assertNotIn("67108864", formal)

    def test_forensic_rtl_has_no_capture_clearing_reset_branch(self) -> None:
        text = (ROOT / "rtl/p10_fault_forensics.sv").read_text(encoding="utf-8")
        self.assertNotIn("always @(posedge clk or", text)
        self.assertIn("assign first_fault_hold_o = frozen_q", text)
        self.assertIn("if (clear_key_i == CLEAR_KEY_COMMIT", text)
        self.assertIn("clear_arm_timeout_q <= CLK_HZ", text)
        self.assertIn("module p10_fault_event_bram", text)
        self.assertIn('(* ram_style = "block" *) reg [31:0] memory', text)
        self.assertNotIn("event_mem [0:EVENT_DEPTH-1]", text)
        transport = (ROOT / "rtl/p9_optical_transport_core.sv").read_text(encoding="utf-8")
        self.assertIn("detected_safety_fault || forensic_fault_hold_i", transport)
        self.assertIn("!any_safety_fault", transport)

    def test_hardware_tools_do_not_program_or_run(self) -> None:
        text = (ROOT / "scripts/hw/p10_3f_fault_forensics.tcl").read_text(
            encoding="utf-8"
        )
        for forbidden in ("fpga -file", " dow ", " con\n", "rst -system"):
            self.assertNotIn(forbidden, text)

    def test_hardware_runner_fails_closed_without_immutable_authorization(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts/run_p10_3f_staircase_hardware.py"),
                "--run-id", "p10_3f_20260804T000000Z_deadbeef",
                "--authorization", str(ROOT / "config/does_not_exist.json"),
                "--validate-only",
            ],
            cwd=ROOT,
            env={**os.environ, "NO_HARDWARE": "1",
                 "CURRENT_RUN_HARDWARE_AUTHORIZATION": "false"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("authorization/freeze read failed", result.stdout)

    def test_requirement_ids_and_manual_scope_are_explicit(self) -> None:
        requirements = (ROOT / "config/project_requirements.yaml").read_text(
            encoding="utf-8"
        )
        for requirement_id in (
            "P10_3F-OFF-001", "P10_3F-OFF-002", "P10_3F-OFF-003",
            "P10_3F-OFF-004", "P10_3F-HW-001", "P10_3F-HW-002",
            "P10_3F-HW-003",
        ):
            self.assertEqual(requirements.count(f"requirement_id: {requirement_id}"), 1)
        staircase = (ROOT / "config/performance/p10_3f_staircase.yaml").read_text(
            encoding="utf-8"
        )
        self.assertIn("oscilloscope: OMITTED_BY_USER", staircase)
        self.assertIn("photodiode_probe: OMITTED_BY_USER", staircase)


if __name__ == "__main__":
    unittest.main()
