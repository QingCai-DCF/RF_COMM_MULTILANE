from __future__ import annotations

import contextlib
import hashlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import p7_hardware_safety as safety  # noqa: E402
import run_p7_authorized_hardware_sequence as sequence  # noqa: E402


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class P7HardwareSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.artifact_temp = tempfile.TemporaryDirectory()
        self.authorization_temp = tempfile.TemporaryDirectory(dir=ROOT / ".hardware_authorization")
        self.artifact_dir = Path(self.artifact_temp.name)
        self.authorization_dir = Path(self.authorization_temp.name)
        self.source_commit = "a" * 40
        self.artifacts: dict[str, Path] = {}
        for name in (
            "plan",
            "bitstream",
            "xsa",
            "elf",
            "profile",
            "active_xdc",
            "pinmap",
            "register_map",
            "shutdown_bitstream",
        ):
            path = self.artifact_dir / f"{name}.bin"
            path.write_bytes((name + "\n").encode("utf-8"))
            self.artifacts[name] = path
        self.vivado = self.artifact_dir / "vivado.bat"
        self.vivado.write_text("offline test placeholder\n", encoding="utf-8")
        self.abort_file = self.authorization_dir / "ABORT_NOW.txt"
        self.auth_file = self.authorization_dir / "P7_STATIONARY_APP_LAYER_APPROVED.txt"
        auth_lines = [
            safety.AUTH_MARKER,
            f"AUTHORIZED_STAGE={safety.AUTHORIZED_STAGE}",
            "USER_HARDWARE_AUTHORIZATION_FOR_P7=GRANTED",
            "BOARD_ID=210512180081",
            "EXPECTED_PART=xc7z010clg400-1",
            "EXPECTED_TARGET=localhost:3121/xilinx_tcf/Digilent/210512180081",
            f"SOURCE_COMMIT={self.source_commit}",
            "MAX_RUNTIME_SEC=1800",
            "SHUTDOWN_ON_EXIT=required",
            "NO_ETHERNET=true",
            "NO_MOTION=true",
            "LANE_COUNT=2",
            "MAX_LANE_MASK=0x3",
        ]
        auth_keys = {
            "plan": ("P7_PLAN_PATH", "P7_PLAN_SHA256"),
            "bitstream": ("BITSTREAM_PATH", "BITSTREAM_SHA256"),
            "xsa": ("XSA_PATH", "XSA_SHA256"),
            "elf": ("ELF_PATH", "ELF_SHA256"),
            "profile": ("PROFILE_PATH", "PROFILE_SHA256"),
            "active_xdc": ("ACTIVE_XDC_PATH", "ACTIVE_XDC_SHA256"),
            "pinmap": ("PINMAP_PATH", "PINMAP_SHA256"),
            "register_map": ("REGISTER_MAP_PATH", "REGISTER_MAP_SHA256"),
            "shutdown_bitstream": ("SHUTDOWN_BITSTREAM_PATH", "SHUTDOWN_BITSTREAM_SHA256"),
        }
        for name, (path_key, sha_key) in auth_keys.items():
            path = self.artifacts[name]
            auth_lines.append(f"{path_key}={path}")
            auth_lines.append(f"{sha_key}={file_sha(path)}")
        self.auth_file.write_text("\n".join(auth_lines) + "\n", encoding="utf-8")

    def test_hardware_execution_lock_is_exclusive_and_never_steals(self) -> None:
        lock_path = self.authorization_dir / "P7_HARDWARE_EXECUTION.lock"
        first = safety.HardwareExecutionLock.acquire(
            owner={"wrapper": "first", "acquired_at_utc": "test"}, path=lock_path
        )
        self.assertTrue(lock_path.is_file())
        self.assertTrue(first.record()["acquired"])
        with self.assertRaisesRegex(RuntimeError, "already exists"):
            safety.HardwareExecutionLock.acquire(
                owner={"wrapper": "second", "acquired_at_utc": "test"}, path=lock_path
            )
        first.release()
        self.assertFalse(lock_path.exists())
        second = safety.HardwareExecutionLock.acquire(
            owner={"wrapper": "second", "acquired_at_utc": "test"}, path=lock_path
        )
        second.release()

    def tearDown(self) -> None:
        self.authorization_temp.cleanup()
        self.artifact_temp.cleanup()

    def valid_argv(self) -> list[str]:
        values = [
            "--execute-hardware",
            "--authorization-file",
            str(self.auth_file),
            "--authorization-sha256",
            file_sha(self.auth_file),
            "--board-id",
            "210512180081",
            "--expected-part",
            "xc7z010clg400-1",
            "--expected-target",
            "localhost:3121/xilinx_tcf/Digilent/210512180081",
            "--source-commit",
            self.source_commit,
            "--max-runtime-sec",
            "1800",
            "--shutdown-on-exit",
            "--no-ethernet",
            "--no-motion",
            "--lane-count",
            "2",
            "--max-lane-mask",
            "0x3",
            "--abort-file",
            str(self.abort_file),
            "--vivado-path",
            str(self.vivado),
        ]
        flags = {
            "plan": ("plan-file", "plan-sha256"),
            "bitstream": ("bitstream", "bitstream-sha256"),
            "xsa": ("xsa", "xsa-sha256"),
            "elf": ("elf", "elf-sha256"),
            "profile": ("profile", "profile-sha256"),
            "active_xdc": ("active-xdc", "active-xdc-sha256"),
            "pinmap": ("pinmap", "pinmap-sha256"),
            "register_map": ("register-map", "register-map-sha256"),
            "shutdown_bitstream": ("shutdown-bitstream", "shutdown-bitstream-sha256"),
        }
        for name, (path_flag, sha_flag) in flags.items():
            values.extend(
                [
                    f"--{path_flag}",
                    str(self.artifacts[name]),
                    f"--{sha_flag}",
                    file_sha(self.artifacts[name]),
                ]
            )
        return values

    def test_valid_controls_require_external_environment(self) -> None:
        args = safety.build_parser().parse_args(self.valid_argv())
        with mock.patch.object(safety, "current_git_state", return_value=(self.source_commit, [], None)):
            with mock.patch.dict(os.environ, {}, clear=True):
                blocked = safety.validate_request(args)
            with mock.patch.dict(os.environ, {safety.AUTH_ENV: safety.AUTH_ENV_VALUE}, clear=True):
                passed = safety.validate_request(args)
        self.assertIn(
            f"external environment authorization required: {safety.AUTH_ENV}={safety.AUTH_ENV_VALUE}",
            blocked["errors"],
        )
        self.assertEqual([], passed["errors"])
        self.assertTrue(passed["ready_for_hardware_preflight"])
        self.assertFalse(passed["hardware_actions_executed"])

    def test_runtime_above_1800_and_abort_file_block(self) -> None:
        argv = self.valid_argv()
        runtime_index = argv.index("--max-runtime-sec") + 1
        argv[runtime_index] = "1801"
        self.abort_file.write_text("stop\n", encoding="utf-8")
        args = safety.build_parser().parse_args(argv)
        with mock.patch.object(safety, "current_git_state", return_value=(self.source_commit, [], None)):
            with mock.patch.dict(os.environ, {safety.AUTH_ENV: safety.AUTH_ENV_VALUE}, clear=True):
                report = safety.validate_request(args)
        self.assertTrue(any("max runtime must be in 1..1800" in item for item in report["errors"]))
        self.assertTrue(any("abort file is present" in item for item in report["errors"]))

    def test_nonzero_preflight_exit_can_never_pass_by_marker(self) -> None:
        result = "\n".join(
            [
                "P7_HW_PREFLIGHT_AUTHORIZED=1",
                "P7_HW_PREFLIGHT_READ_ONLY=1",
                "P7_HW_PREFLIGHT_BOARD_ID=board",
                "P7_HW_PREFLIGHT_TARGET=target",
                f"P7_HW_PREFLIGHT_PART={sequence.CANONICAL_FULL_PART}",
                f"P7_HW_PREFLIGHT_DEVICE={sequence.CANONICAL_LIVE_DEVICE}",
                f"P7_HW_PREFLIGHT_IDCODE={sequence.CANONICAL_LIVE_IDCODE_BINARY}",
                f"P7_HW_PREFLIGHT_CANONICAL_PART={sequence.CANONICAL_FULL_PART}",
                f"P7_HW_PREFLIGHT_LIVE_PART={sequence.CANONICAL_LIVE_PART}",
                f"P7_HW_PREFLIGHT_LIVE_DEVICE={sequence.CANONICAL_LIVE_DEVICE}",
                f"P7_HW_PREFLIGHT_LIVE_IDCODE={sequence.CANONICAL_LIVE_IDCODE_BINARY}",
                "P7_HW_PREFLIGHT_RESULT=PASS",
            ]
        )
        passed, failures = sequence.evaluate_preflight(
            returncode=125,
            stdout="P7_HW_PREFLIGHT_RESULT=PASS\n",
            result_text=result,
            expected_board_id="board",
            expected_part=sequence.CANONICAL_FULL_PART,
            expected_target="target",
        )
        self.assertFalse(passed)
        self.assertTrue(any("nonzero exit code" in item for item in failures))

    def test_preflight_requires_exact_canonical_live_identity(self) -> None:
        valid_lines = [
            "P7_HW_PREFLIGHT_AUTHORIZED=1",
            "P7_HW_PREFLIGHT_READ_ONLY=1",
            "P7_HW_PREFLIGHT_BOARD_ID=board",
            "P7_HW_PREFLIGHT_TARGET=target",
            f"P7_HW_PREFLIGHT_PART={sequence.CANONICAL_FULL_PART}",
            f"P7_HW_PREFLIGHT_DEVICE={sequence.CANONICAL_LIVE_DEVICE}",
            f"P7_HW_PREFLIGHT_IDCODE={sequence.CANONICAL_LIVE_IDCODE_BINARY}",
            f"P7_HW_PREFLIGHT_CANONICAL_PART={sequence.CANONICAL_FULL_PART}",
            f"P7_HW_PREFLIGHT_LIVE_PART={sequence.CANONICAL_LIVE_PART}",
            f"P7_HW_PREFLIGHT_LIVE_DEVICE={sequence.CANONICAL_LIVE_DEVICE}",
            f"P7_HW_PREFLIGHT_LIVE_IDCODE=0x{sequence.CANONICAL_LIVE_IDCODE_HEX}",
            "P7_HW_PREFLIGHT_RESULT=PASS",
        ]
        passed, failures = sequence.evaluate_preflight(
            returncode=0,
            stdout="P7_HW_PREFLIGHT_RESULT=PASS\n",
            result_text="\n".join(valid_lines),
            expected_board_id="board",
            expected_part=sequence.CANONICAL_FULL_PART,
            expected_target="target",
        )
        self.assertTrue(passed, failures)
        for replacement in (
            f"P7_HW_PREFLIGHT_LIVE_PART={sequence.CANONICAL_LIVE_PART}x",
            "P7_HW_PREFLIGHT_LIVE_DEVICE=xc7z020_1",
            "P7_HW_PREFLIGHT_LIVE_IDCODE=0x03722093",
        ):
            mutated = list(valid_lines)
            key = replacement.split("=", 1)[0]
            mutated = [replacement if line.startswith(key + "=") else line for line in mutated]
            rejected, identity_failures = sequence.evaluate_preflight(
                returncode=0,
                stdout="P7_HW_PREFLIGHT_RESULT=PASS\n",
                result_text="\n".join(mutated),
                expected_board_id="board",
                expected_part=sequence.CANONICAL_FULL_PART,
                expected_target="target",
            )
            self.assertFalse(rejected)
            self.assertTrue(identity_failures)

    def test_default_sequence_is_dry_run_and_launches_nothing(self) -> None:
        output = io.StringIO()
        with mock.patch.object(sequence.subprocess, "run") as run_mock:
            with contextlib.redirect_stdout(output):
                returncode = sequence.main(["--json-summary"])
        self.assertEqual(0, returncode)
        self.assertFalse(run_mock.called)
        self.assertIn('"P7_AUTHORIZED_HARDWARE_SEQUENCE": "DRY_RUN_ONLY"', output.getvalue())

    def test_tcl_is_read_only_and_checks_authorization_before_connect(self) -> None:
        tcl = (ROOT / "scripts/hw/p7_hw_preflight.tcl").read_text(encoding="utf-8")
        lower = tcl.lower()
        for forbidden in (
            "program_hw_devices",
            "set_property program.file",
            "run_hw_ila",
            "create_hw_axi_txn",
            " mwr ",
            " dow ",
        ):
            self.assertNotIn(forbidden, lower)
        self.assertLess(tcl.index("RF_COMM_HW_AUTH"), tcl.index("connect_hw_server"))
        self.assertIn("P7_HW_PREFLIGHT_READ_ONLY=1", tcl)
        self.assertIn('set p7_canonical_part "xc7z010clg400-1"', tcl)
        self.assertIn('set p7_live_part "xc7z010"', tcl)
        self.assertIn('set p7_live_device "xc7z010_1"', tcl)
        self.assertIn('set p7_live_idcode "13722093"', tcl)
        self.assertNotIn("string match -nocase *xc7z010*", tcl)

    def test_p7_code_does_not_self_set_hardware_authorization(self) -> None:
        combined = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "tools/p7_hardware_safety.py",
                "tools/run_p7_authorized_hardware_sequence.py",
                "tools/run_p7_authorized_hardware_sequence.ps1",
            )
        )
        self.assertNotIn('env["RF_COMM_HW_AUTH"] =', combined)
        self.assertNotIn("$env:RF_COMM_HW_AUTH =", combined)


if __name__ == "__main__":
    unittest.main()
