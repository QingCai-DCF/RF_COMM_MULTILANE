from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import tkinter
except ImportError:  # pragma: no cover - Tcl runtime is optional outside release gates.
    tkinter = None


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "hw" / "run_p7_jtag_axi_stage_safe.py"
SPEC = importlib.util.spec_from_file_location("p7_jtag_stage", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
stage = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = stage
SPEC.loader.exec_module(stage)

sys.path.insert(0, str(ROOT / "tools"))
import p7_jtag_backend as backend  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tcl_interpreter():
    if tkinter is None:
        raise unittest.SkipTest("Python Tcl runtime is unavailable")
    try:
        return tkinter.Tcl()
    except Exception as exc:  # pragma: no cover - platform Tcl installation failure.
        raise unittest.SkipTest(f"Python Tcl runtime is unavailable: {exc}") from exc


def install_captured_tcl_exit(interp) -> None:
    interp.eval(
        "proc exit {code} {\n"
        "  set ::p7_captured_exit_code $code\n"
        "  return -code error \"__P7_CAPTURED_EXIT__$code\"\n"
        "}"
    )


HELPER_PATHS = [
    r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\cs_server.exe",
    r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\rdi_xsdb.exe",
    r"C:\Windows\System32\cmd.exe",
    r"C:\Windows\System32\conhost.exe",
]
HELPER_HASHES = dict(stage.EXPECTED_VIVADO_HELPER_SHA256_BY_ROLE)


def helper_process(
    role: str,
    pid: int,
    parent_pid: int,
    *,
    parent_active: bool = False,
    created: int | None = None,
):
    return {
        "pid": pid,
        "parent_pid": parent_pid,
        "parent_active_globally": parent_active,
        "image_path": HELPER_PATHS[stage.EXPECTED_HELPER_ROLES.index(role)],
        "creation_time_100ns": created if created is not None else 10_000_000 + pid,
    }


def exact_r2_forest() -> list[dict[str, object]]:
    return [
        helper_process("conhost", 26780, 43148),
        helper_process("cs_server", 29740, 43676),
        helper_process("cs_server", 39216, 29740, parent_active=True),
        helper_process("cmd", 30352, 35356),
        helper_process("conhost", 33772, 30352, parent_active=True),
        helper_process("rdi_xsdb", 45200, 30352, parent_active=True),
    ]


def approved_containment_details() -> dict[str, object]:
    return {
        **stage._containment_detail_defaults(expected_paths=HELPER_PATHS),
        "expected_tool_daemon_prelaunch_hashes_verified": True,
        "expected_tool_daemon_prelaunch_sha256_by_role": HELPER_HASHES,
        "expected_tool_daemon_prelaunch_hash_error": "",
    }


class FakeExitedProcess:
    def __init__(self, pid: int = 5151) -> None:
        self.pid = pid

    @staticmethod
    def poll():
        return 0


def verify_fake_job(
    job: object,
    *,
    details: dict[str, object] | None = None,
    post_hash_result: tuple[bool, dict[str, str], str] | None = None,
) -> tuple[bool, dict[str, object]]:
    process = FakeExitedProcess()
    stage._WINDOWS_JOBS[process] = job
    stage._CONTAINMENT_DETAILS[process] = details or approved_containment_details()
    result = post_hash_result or (True, HELPER_HASHES, "")
    try:
        with mock.patch.object(
            stage, "verify_expected_tool_daemon_binary_hashes", return_value=result
        ):
            passed = stage.verify_process_tree_reaped(process)
        record = stage.containment_record(process)
        return passed, record
    finally:
        stage._WINDOWS_JOBS.pop(process, None)
        stage._CONTAINMENT_RESULTS.pop(process, None)
        stage._CONTAINMENT_DETAILS.pop(process, None)


class P7JtagAxiStageTests(unittest.TestCase):
    def valid_transaction(self, path: Path) -> None:
        path.write_text(
            "\n".join(
                [
                    stage.TRANSACTION_MAGIC,
                    "META BACKEND p7_jtag_backend",
                    "W32 0x43c00100 0x00000002",
                    "W32 0x43c00200 0x04030201",
                    "W32 0x43c00108 0x00002201",
                    "W32 0x43c0010c 0x00000003",
                    "W32 0x43c00110 0x00000003",
                    "W32 0x43c00114 0x00000004",
                    "W32 0x43c0015c 0x0061a800",
                    "W32 0x43c00100 0x00000004",
                    "POLL32 0x43c00104 0x00000004 0x00000004 2000 1 COMMITTED",
                    "W32 0x43c00100 0x00000008",
                    "POLL32 0x43c00104 0x00000010 0x00000010 10000 1 DONE",
                    "ASSERT32 0x43c00150 0xffffffff 0x00000000 DUTY_CLEAN",
                    "R32 0x43c00138 CRC_BAD",
                    "W32 0x43c00100 0x00000030",
                    "END",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def safe_idle_transaction(self, path: Path) -> None:
        lines = [stage.TRANSACTION_MAGIC, "META EVIDENCE_KIND safe_idle"]
        addresses = {
            "SAFE_STATUS": "0x43c00104",
            "SAFE_TX_COUNT": "0x43c0012c",
            "SAFE_RX_GOOD_L0": "0x43c00130",
            "SAFE_RX_GOOD_L1": "0x43c00134",
            "SAFE_CRC_BAD": "0x43c00138",
            "SAFE_PAYLOAD_MISMATCH": "0x43c0013c",
            "SAFE_RETRY_EXHAUSTED": "0x43c00144",
            "SAFE_TX_FAIL": "0x43c00148",
            "SAFE_TXD_HIGH_MAX": "0x43c0014c",
            "SAFE_DUTY_VIOLATION": "0x43c00150",
            "SAFE_ERROR_CODE": "0x43c00160",
            "SAFE_STICKY_ERROR": "0x43c00164",
        }
        for key, address in addresses.items():
            mask = "0x000000e8" if key == "SAFE_STATUS" else "0xffffffff"
            lines.append(f"ASSERT32 {address} {mask} 0x00000000 {key}")
        lines.extend(["W32 0x43c00100 0x00000030", "END", ""])
        path.write_text("\n".join(lines), encoding="utf-8")

    def test_strict_transaction_format_accepts_bounded_valid_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "transactions.txt"
            self.valid_transaction(path)
            report = stage.validate_transaction_file(str(path), sha256(path))
        self.assertEqual([], report["errors"])
        self.assertTrue(report["valid"])
        self.assertEqual("p7_jtag_backend", report["metadata"]["BACKEND"])

    def test_generated_4k_transaction_full_stream_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transaction = root / "4k.transactions.txt"
            manifest_path = root / "4k.manifest.json"
            manifest = backend.generate_bundle(
                bytes(index & 0xFF for index in range(4096)),
                transaction_path=transaction,
                manifest_path=manifest_path,
                session_epoch=0x50370001,
                object_id=7,
                lane_policy="STRIPE_ROUND_ROBIN",
            )
            report = stage.validate_transaction_file(
                str(transaction), manifest["transaction_sha256"]
            )
        self.assertTrue(report["valid"], report["errors"])
        self.assertEqual(4269, report["operation_count"])
        self.assertEqual(manifest["transaction_operation_count"], report["operation_count"])
        self.assertEqual(manifest["transaction_file_bytes"], report["size_bytes"])
        self.assertEqual(40, report["poll_operation_count"])

    def test_safe_idle_semantics_forbid_transmission_and_parse_zero_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "safe_idle.transactions.txt"
            self.safe_idle_transaction(path)
            report = stage.validate_transaction_file(str(path), sha256(path))
            args = stage.build_parser().parse_args(
                [
                    "--semantic-mode", "safe-idle",
                    "--transaction-file", str(path),
                    "--transaction-sha256", sha256(path),
                ]
            )
            self.assertEqual([], report["errors"])
            self.assertEqual(0, report["start_operation_count"])
            self.assertEqual(0, report["commit_operation_count"])
            self.assertEqual(0, report["payload_write_count"])
            self.assertEqual([], stage._safe_idle_transaction_errors(args, report))
            raw = [
                "P7_TXN_META_EVIDENCE_KIND=safe_idle",
                f"P7_TRANSACTION_COUNT={report['operation_count']}",
            ]
            raw.extend(f"{key}=0x00000000" for key in sorted(stage.SAFE_IDLE_REQUIRED_KEYS))
            parsed = stage.evaluate_safe_idle_raw(
                "\n".join(raw), expected_operation_count=report["operation_count"]
            )
        self.assertEqual("PASS", parsed["P7_SAFE_IDLE_PARSE"])
        self.assertFalse(parsed["drove_tfdu_txd"])
        self.assertFalse(parsed["enabled_tfdu_receiver"])

    def test_safe_idle_semantics_reject_start_and_nonzero_counter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "unsafe_idle.transactions.txt"
            self.valid_transaction(path)
            report = stage.validate_transaction_file(str(path), sha256(path))
            args = stage.build_parser().parse_args(["--semantic-mode", "safe-idle"])
            errors = stage._safe_idle_transaction_errors(args, report)
        self.assertTrue(any("start_operation_count" in item for item in errors))
        raw = [
            "P7_TXN_META_EVIDENCE_KIND=safe_idle",
            "P7_TRANSACTION_COUNT=13",
        ]
        raw.extend(
            f"{key}={'0x00000001' if key == 'SAFE_TX_COUNT' else '0x00000000'}"
            for key in sorted(stage.SAFE_IDLE_REQUIRED_KEYS)
        )
        parsed = stage.evaluate_safe_idle_raw("\n".join(raw), expected_operation_count=13)
        self.assertEqual("FAIL", parsed["P7_SAFE_IDLE_PARSE"])
        self.assertTrue(any("SAFE_TX_COUNT" in item for item in parsed["failures"]))

    def test_backend_manifest_is_hash_path_frequency_and_runtime_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            transaction = root / "object.transactions.txt"
            manifest_path = root / "object.manifest.json"
            manifest = backend.generate_bundle(
                bytes(range(251)),
                transaction_path=transaction,
                manifest_path=manifest_path,
                session_epoch=0x50370001,
                object_id=9,
                lane_policy="LANE0_ONLY",
                authorized_runtime_sec=1800,
            )
            args = stage.build_parser().parse_args(
                [
                    "--max-runtime-sec", "1800",
                    "--jtag-frequency-hz", "1000000",
                    "--transaction-file", str(transaction),
                    "--transaction-sha256", manifest["transaction_sha256"],
                    "--backend-manifest", str(manifest_path),
                    "--backend-manifest-sha256", sha256(manifest_path),
                ]
            )
            transaction_report = stage.validate_transaction_file(
                str(transaction), manifest["transaction_sha256"]
            )
            errors, details = stage._backend_manifest_errors(args, transaction_report)
            self.assertEqual([], errors)
            self.assertEqual(251, details["input_length"])
            args.jtag_frequency_hz = 2_000_000
            errors, _ = stage._backend_manifest_errors(args, transaction_report)
            self.assertTrue(any("frequency" in item.lower() for item in errors))

    def test_wrapper_requires_strict_backend_parse_for_final_pass(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn("parse_raw_result(", source)
        self.assertIn("backend_parse_ok", source)
        self.assertIn(
            "before_ok and stage_ok and after_ok and backend_parse_ok",
            source,
        )
        self.assertLess(source.index("shutdown_after_finished"), source.index("parse_raw_result("))

    def test_sparse_oversize_file_is_rejected_without_large_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "oversize.transactions.txt"
            with path.open("wb") as handle:
                handle.seek(stage.MAX_TRANSACTION_BYTES)
                handle.write(b"X")
            report = stage.validate_transaction_file(str(path), "0" * 64)
        self.assertTrue(any("file size" in item for item in report["errors"]))

    def test_runtime_estimate_and_global_budget_fail_closed(self) -> None:
        operation_count = backend.transaction_shape(1048576)["operation_count"]
        transaction = {"operation_count": operation_count}
        args = stage.build_parser().parse_args(
            [
                "--max-runtime-sec", "1800",
                "--jtag-frequency-hz", "100000",
                "--stage-timeout-sec", "1500",
                "--preflight-timeout-sec", "60",
                "--shutdown-timeout-sec", "60",
            ]
        )
        errors = stage.transaction_runtime_errors(args, transaction)
        self.assertTrue(errors)
        self.assertFalse(transaction["global_runtime_budget"]["feasible"])
        feasible_transaction = {"operation_count": operation_count}
        feasible_args = stage.build_parser().parse_args(
            [
                "--max-runtime-sec", "1800",
                "--jtag-frequency-hz", "1000000",
                "--stage-timeout-sec", "1400",
                "--preflight-timeout-sec", "60",
                "--shutdown-timeout-sec", "60",
            ]
        )
        self.assertEqual(
            [], stage.transaction_runtime_errors(feasible_args, feasible_transaction)
        )
        budget = feasible_transaction["global_runtime_budget"]
        self.assertTrue(budget["feasible"])
        self.assertEqual(120, budget["containment_allowance_seconds"])
        self.assertEqual(65, budget["other_guard_seconds"])
        self.assertEqual(45, budget["bookkeeping_guard_seconds"])
        self.assertEqual(40, budget["containment_failure_bound_seconds_each"])
        self.assertEqual(20, budget["forced_cleanup_reserve_seconds"])
        self.assertEqual(1765, budget["configured_global_timeout_ceiling_sec"])
        self.assertEqual(35, budget["configured_unallocated_margin_seconds"])
        self.assertEqual(1372, feasible_transaction["runtime_feasibility"]["minimum_stage_runtime_sec"])
        overflow_transaction = {"operation_count": operation_count}
        overflow_args = stage.build_parser().parse_args(
            [
                "--max-runtime-sec", "1800",
                "--jtag-frequency-hz", "1000000",
                "--stage-timeout-sec", "1450",
                "--preflight-timeout-sec", "60",
                "--shutdown-timeout-sec", "60",
            ]
        )
        overflow_errors = stage.transaction_runtime_errors(overflow_args, overflow_transaction)
        self.assertTrue(any("configured process timeout ceiling" in item for item in overflow_errors))
        self.assertEqual(
            1815,
            overflow_transaction["global_runtime_budget"]["configured_global_timeout_ceiling_sec"],
        )
        self.assertEqual([0, 30, 60, 90, 120], [stage.containment_allowance(i) for i in range(5)])
        with mock.patch.object(stage.time, "monotonic", return_value=0.0):
            self.assertEqual(
                60,
                stage.deadline_timeout(
                    60,
                    1800.0,
                    reserve_sec=2 * 60 + 1400 + stage.containment_allowance(3) + 65,
                ),
            )
            self.assertEqual(
                60,
                stage.deadline_timeout(
                    60,
                    1800.0,
                    reserve_sec=1400 + 60 + stage.containment_allowance(2) + 65,
                ),
            )
            self.assertEqual(
                1400,
                stage.deadline_timeout(
                    1400,
                    1800.0,
                    reserve_sec=60 + stage.containment_allowance(1) + 65,
                ),
            )
            self.assertEqual(
                60,
                stage.deadline_timeout(60, 1800.0, reserve_sec=65),
            )


    def test_transaction_format_rejects_command_injection_and_unlisted_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.txt"
            path.write_text(
                "\n".join(
                    [
                        stage.TRANSACTION_MAGIC,
                        "source attacker.tcl",
                        "W32 0x43c00000 0x00000001",
                        "W32 0x43c00100 0x00000030;exec",
                        "END",
                    ]
                ),
                encoding="utf-8",
            )
            report = stage.validate_transaction_file(str(path), sha256(path))
        self.assertTrue(any("unsupported operation" in item for item in report["errors"]))
        self.assertTrue(any("write offset" in item for item in report["errors"]))
        self.assertTrue(any("eight hex digits" in item for item in report["errors"]))

    def test_transaction_requires_in_band_stop_shutdown_as_final_operation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad_end.txt"
            path.write_text(
                f"{stage.TRANSACTION_MAGIC}\nR32 0x43c00104 STATUS\nEND\n",
                encoding="utf-8",
            )
            report = stage.validate_transaction_file(str(path), sha256(path))
        self.assertTrue(any("final operation" in item for item in report["errors"]))

    def test_nonzero_stage_exit_can_never_pass_markers(self) -> None:
        result = "\n".join(
            [
                "P7_JTAG_STAGE_RESULT=PASS",
                "P7_CANDIDATE_PROGRAMMED=1",
                "P7_JTAG_AXI_TRANSACTIONS=PASS",
                "P7_HW_TARGET=target",
                f"P7_HW_PART={stage.CANONICAL_FULL_PART}",
                f"P7_HW_DEVICE={stage.CANONICAL_LIVE_DEVICE}",
                f"P7_HW_IDCODE={stage.CANONICAL_LIVE_IDCODE_BINARY}",
                f"P7_HW_CANONICAL_PART={stage.CANONICAL_FULL_PART}",
                f"P7_HW_LIVE_PART={stage.CANONICAL_LIVE_PART}",
                f"P7_HW_LIVE_DEVICE={stage.CANONICAL_LIVE_DEVICE}",
                f"P7_HW_LIVE_IDCODE={stage.CANONICAL_LIVE_IDCODE_BINARY}",
            ]
        )
        passed, failures = stage.evaluate_stage(
            125,
            "P7_JTAG_STAGE_RESULT=PASS\n",
            result,
            expected_target="target",
            expected_part=stage.CANONICAL_FULL_PART,
        )
        self.assertFalse(passed)
        self.assertTrue(any("nonzero exit code" in item for item in failures))

    def test_stage_requires_exact_canonical_live_identity(self) -> None:
        lines = [
            "P7_JTAG_STAGE_RESULT=PASS",
            "P7_CANDIDATE_PROGRAMMED=1",
            "P7_JTAG_AXI_TRANSACTIONS=PASS",
            "P7_HW_TARGET=target",
            f"P7_HW_PART={stage.CANONICAL_FULL_PART}",
            f"P7_HW_DEVICE={stage.CANONICAL_LIVE_DEVICE}",
            f"P7_HW_IDCODE={stage.CANONICAL_LIVE_IDCODE_BINARY}",
            f"P7_HW_CANONICAL_PART={stage.CANONICAL_FULL_PART}",
            f"P7_HW_LIVE_PART={stage.CANONICAL_LIVE_PART}",
            f"P7_HW_LIVE_DEVICE={stage.CANONICAL_LIVE_DEVICE}",
            f"P7_HW_LIVE_IDCODE=0x{stage.CANONICAL_LIVE_IDCODE_HEX}",
        ]
        passed, failures = stage.evaluate_stage(
            0,
            "P7_JTAG_STAGE_RESULT=PASS\n",
            "\n".join(lines),
            expected_target="target",
            expected_part=stage.CANONICAL_FULL_PART,
        )
        self.assertTrue(passed, failures)
        mutated = [
            "P7_HW_LIVE_DEVICE=xc7z020_1" if line.startswith("P7_HW_LIVE_DEVICE=") else line
            for line in lines
        ]
        passed, failures = stage.evaluate_stage(
            0,
            "P7_JTAG_STAGE_RESULT=PASS\n",
            "\n".join(mutated),
            expected_target="target",
            expected_part=stage.CANONICAL_FULL_PART,
        )
        self.assertFalse(passed)
        self.assertTrue(any("identity marker mismatch" in item for item in failures))

    def test_shutdown_requires_both_zero_exit_and_marker(self) -> None:
        valid_result = "\n".join(
            [
                "P7_TCL_PROGRAMMING_ATTEMPTED=1",
                "TFDU_SHUTDOWN_PROGRAMMED=C:/shutdown.bit",
                "P7_SHUTDOWN_RESULT=PASS",
                "",
            ]
        )
        passed, failures = stage.evaluate_shutdown(
            125,
            valid_result,
            expected_shutdown_bit="C:/shutdown.bit",
        )
        self.assertFalse(passed)
        self.assertTrue(any("nonzero exit code" in item for item in failures))
        passed, failures = stage.evaluate_shutdown(
            0,
            valid_result,
            expected_shutdown_bit="C:/shutdown.bit",
        )
        self.assertTrue(passed, failures)
        self.assertTrue(stage.shutdown_programming_attempted("P7_TCL_PROGRAMMING_ATTEMPTED=1\n"))
        for duplicate_line in (
            "P7_TCL_PROGRAMMING_ATTEMPTED=1",
            "TFDU_SHUTDOWN_PROGRAMMED=C:/shutdown.bit",
            "P7_SHUTDOWN_RESULT=PASS",
        ):
            duplicate_result = valid_result + duplicate_line + "\n"
            passed, failures = stage.evaluate_shutdown(
                0,
                duplicate_result,
                expected_shutdown_bit="C:/shutdown.bit",
            )
            self.assertFalse(passed)
            self.assertTrue(any("duplicate markers" in item for item in failures))
        self.assertIsNone(
            stage.shutdown_programming_attempted(
                valid_result + "P7_TCL_PROGRAMMING_ATTEMPTED=1\n"
            )
        )
        for result_text, expected_attempted in (
            ("P7_SHUTDOWN_RESULT=PASS\n", None),
            ("P7_TCL_PROGRAMMING_ATTEMPTED=0\nP7_SHUTDOWN_RESULT=PASS\n", False),
            ("P7_TCL_PROGRAMMING_ATTEMPTED=unknown\nP7_SHUTDOWN_RESULT=PASS\n", None),
        ):
            passed, failures = stage.evaluate_shutdown(
                0,
                "TFDU_SHUTDOWN_PROGRAMMED=C:/shutdown.bit\n" + result_text,
                expected_shutdown_bit="C:/shutdown.bit",
            )
            self.assertFalse(passed)
            self.assertTrue(any("P7_TCL_PROGRAMMING_ATTEMPTED=1" in item for item in failures))
            self.assertIs(expected_attempted, stage.shutdown_programming_attempted(result_text))
        stdout_echo_spoof = "\n".join(
            [
                "P7_TCL_PROGRAMMING_ATTEMPTED=1",
                'puts "TFDU_SHUTDOWN_PROGRAMMED=C:/shutdown.bit"',
                "P7_SHUTDOWN_RESULT=PASS",
            ]
        )
        passed, failures = stage.evaluate_shutdown(
            0,
            stdout_echo_spoof,
            expected_shutdown_bit="C:/shutdown.bit",
        )
        self.assertFalse(passed)
        self.assertTrue(any("fresh result file" in item for item in failures))
        passed, failures = stage.evaluate_shutdown(
            0,
            valid_result.replace("C:/shutdown.bit", "C:/wrong.bit"),
            expected_shutdown_bit="C:/shutdown.bit",
        )
        self.assertFalse(passed)
        self.assertTrue(any("authorized shutdown bit" in item for item in failures))
        passed, failures = stage.evaluate_shutdown(
            0,
            "P7_SHUTDOWN_RESULT=PASS\n",
            expected_shutdown_bit="C:/shutdown.bit",
        )
        self.assertFalse(passed)
        self.assertTrue(any("marker missing" in item for item in failures))

    def test_default_and_blocked_execute_paths_launch_no_process(self) -> None:
        for argv, expected in (
            (["--json-summary"], '"P7_JTAG_AXI_SAFE_STAGE": "DRY_RUN_ONLY"'),
            (["--execute-hardware", "--json-summary"], '"P7_JTAG_AXI_SAFE_STAGE": "BLOCKED"'),
        ):
            output = io.StringIO()
            with mock.patch.object(stage.subprocess, "Popen") as popen:
                with contextlib.redirect_stdout(output):
                    returncode = stage.main(argv)
            self.assertFalse(popen.called)
            self.assertIn(expected, output.getvalue())
            self.assertEqual(0 if "DRY_RUN" in expected else 2, returncode)

    def test_dynamic_abort_terminates_process_tree(self) -> None:
        class FakeProcess:
            pid = 4242
            returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.returncode = -9
                return -9

        abort_file = mock.Mock()
        abort_file.exists.return_value = True
        with tempfile.TemporaryDirectory() as temp:
            temp_path = Path(temp)
            fake = FakeProcess()
            with mock.patch.object(stage, "launch_contained_process", return_value=fake):
                with mock.patch.object(
                    stage,
                    "terminate_process_tree",
                    side_effect=lambda process: setattr(process, "returncode", -9) is None,
                ) as terminate, mock.patch.object(
                    stage, "verify_process_tree_reaped", return_value=True
                ):
                    result = stage.run_bounded_process(
                        name="offline_fake",
                        command=["fixed.exe", "fixed-argument"],
                        stdout_path=temp_path / "stdout.log",
                        stderr_path=temp_path / "stderr.log",
                        timeout_sec=10,
                        abort_file=abort_file,
                        watch_abort=True,
                    )
        self.assertEqual(130, result.returncode)
        self.assertTrue(result.abort_seen)
        self.assertTrue(result.process_tree_terminated)
        self.assertTrue(result.process_tree_reaped)
        self.assertEqual(["fixed.exe", "fixed-argument"], result.argv)
        self.assertIn(".", result.started_at_utc)
        self.assertIn(".", result.ended_at_utc)
        terminate.assert_called_once()

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object containment test")
    def test_job_containment_rejects_and_kills_lingering_descendant(self) -> None:
        child_code = (
            "import subprocess,sys; "
            "subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'])"
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = stage.run_bounded_process(
                name="job_descendant_test",
                command=[sys.executable, "-c", child_code],
                stdout_path=root / "stdout.log",
                stderr_path=root / "stderr.log",
                timeout_sec=10,
                abort_file=root / "ABORT_NOW.txt",
                watch_abort=False,
            )
            # Windows releases inherited log handles just after the Job
            # accounting count reaches zero; allow that kernel teardown to
            # settle before TemporaryDirectory removes the files.
            import time
            time.sleep(0.2)
        self.assertEqual(125, result.returncode)
        self.assertFalse(result.process_tree_reaped)
        self.assertTrue(result.process_tree_terminated)
        self.assertFalse(result.expected_tool_daemon_grace_used)
        self.assertIsInstance(result.process_exit_race_rechecked, bool)
        self.assertIsInstance(result.process_identity_query_retried, bool)
        self.assertIsInstance(result.containment_query_error, str)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object topology contract test")
    def test_initial_topology_classifier_accepts_only_exact_cs_or_full_r2_forest(self) -> None:
        self.assertEqual(
            [],
            stage._expected_tool_daemon_paths(
                [r"D:\Xilinx\Vivado\2023.1\bin\vivado.exe"]
            ),
        )
        self.assertEqual(
            4,
            len(
                stage._expected_tool_daemon_paths(
                    [r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat"]
                )
            ),
        )
        direct_args = stage.build_parser().parse_args(
            ["--vivado-path", r"D:\Xilinx\Vivado\2023.1\bin\vivado.exe"]
        )
        direct_errors, _transaction = stage._stage_control_errors(direct_args)
        self.assertTrue(any("vivado.exe is forbidden" in item for item in direct_errors))
        singleton = [helper_process("cs_server", 10, 9)]
        pair = [
            helper_process("cs_server", 10, 9),
            helper_process("cs_server", 11, 10, parent_active=True),
        ]
        self.assertEqual(
            "SINGLE_EXACT_CS_SERVER",
            stage.classify_expected_tool_daemons(singleton, HELPER_PATHS),
        )
        self.assertEqual(
            "DIRECT_PARENT_CHILD_EXACT_CS_SERVER",
            stage.classify_expected_tool_daemons(pair, HELPER_PATHS),
        )
        self.assertEqual(
            "EXACT_R2_VIVADO_EXIT_HELPER_FOREST",
            stage.classify_expected_tool_daemons(exact_r2_forest(), HELPER_PATHS),
        )
        invalid_cases = []
        wrong_path = exact_r2_forest()
        wrong_path[0] = {**wrong_path[0], "image_path": r"C:\attacker\conhost.exe"}
        invalid_cases.append(wrong_path)
        extra = exact_r2_forest() + [
            helper_process("conhost", 50000, 30352, parent_active=True)
        ]
        invalid_cases.append(extra)
        wrong_edge = exact_r2_forest()
        wrong_edge[5] = {**wrong_edge[5], "parent_pid": 29740}
        invalid_cases.append(wrong_edge)
        shared_root = exact_r2_forest()
        shared_root[0] = {**shared_root[0], "parent_pid": 43676}
        invalid_cases.append(shared_root)
        bool_pid = exact_r2_forest()
        bool_pid[0] = {**bool_pid[0], "pid": True}
        invalid_cases.append(bool_pid)
        bool_creation = exact_r2_forest()
        bool_creation[0] = {**bool_creation[0], "creation_time_100ns": True}
        invalid_cases.append(bool_creation)
        active_root = exact_r2_forest()
        active_root[0] = {**active_root[0], "parent_active_globally": True}
        invalid_cases.append(active_root)
        inactive_internal_parent = exact_r2_forest()
        inactive_internal_parent[2] = {
            **inactive_internal_parent[2],
            "parent_active_globally": False,
        }
        invalid_cases.append(inactive_internal_parent)
        non_boolean_parent_state = exact_r2_forest()
        non_boolean_parent_state[0] = {
            **non_boolean_parent_state[0],
            "parent_active_globally": 0,
        }
        invalid_cases.append(non_boolean_parent_state)
        self_parent = exact_r2_forest()
        self_parent[0] = {**self_parent[0], "parent_pid": self_parent[0]["pid"]}
        invalid_cases.append(self_parent)
        # An arbitrary power-set member is not an independently admitted initial state.
        invalid_cases.append(exact_r2_forest()[:-1])
        for identities in invalid_cases:
            self.assertEqual(
                "UNAPPROVED",
                stage.classify_expected_tool_daemons(identities, HELPER_PATHS),
            )

        initial_pair = [
            helper_process("cs_server", 70, 60),
            helper_process("cs_server", 71, 70, parent_active=True),
        ]
        normalized_pair = stage._normalized_helper_identities(initial_pair, HELPER_PATHS)
        assert normalized_pair is not None
        child_after_parent_exit = [
            helper_process("cs_server", 71, 70, parent_active=False)
        ]
        self.assertEqual(
            "STRICT_SHRINK_SUBSET_OF_DIRECT_PARENT_CHILD_EXACT_CS_SERVER",
            stage.classify_expected_tool_daemon_subset(
                child_after_parent_exit,
                approved_paths=HELPER_PATHS,
                initial_identities=normalized_pair,
                previous_process_ids={70, 71},
                initial_classification="DIRECT_PARENT_CHILD_EXACT_CS_SERVER",
            ),
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object grace test")
    def test_exact_cs_singleton_and_pair_exit_naturally_with_terminal_empty_snapshot(self) -> None:
        class FakeJob:
            def __init__(self, identities):
                self.identities = identities
                self.waits = []
                self.closed = False

            def wait_empty(self, timeout_sec):
                self.waits.append(timeout_sec)
                return len(self.waits) >= 2

            def active_process_identities(self):
                return self.identities

            def terminate(self):
                raise AssertionError("approved naturally empty topology must not be terminated")

            def close(self):
                self.closed = True

        for identities, expected_classification in (
            ([helper_process("cs_server", 6161, 5151)], "SINGLE_EXACT_CS_SERVER"),
            (
                [
                    helper_process("cs_server", 2222, 1111),
                    helper_process("cs_server", 3333, 2222, parent_active=True),
                ],
                "DIRECT_PARENT_CHILD_EXACT_CS_SERVER",
            ),
        ):
            job = FakeJob(identities)
            passed, record = verify_fake_job(job)
            self.assertTrue(passed)
            self.assertTrue(job.closed)
            self.assertEqual(0.0, job.waits[0])
            self.assertLessEqual(max(job.waits[1:]), stage.CONTAINMENT_TOPOLOGY_REVALIDATION_INTERVAL_SECONDS)
            self.assertEqual(expected_classification, record["expected_tool_daemon_classification"])
            self.assertEqual("EMPTY", record["expected_tool_daemon_topology_snapshots"][-1]["classification"])
            self.assertTrue(record["expected_tool_daemon_topology_terminal_empty"])
            self.assertTrue(record["expected_tool_daemon_hashes_verified"])
            self.assertFalse(record["containment_cleanup_attempted"])
            self.assertEqual("", record["containment_query_error"])

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object r2 topology test")
    def test_full_r2_forest_may_only_shrink_with_immutable_identity(self) -> None:
        full = exact_r2_forest()
        shrink_one = [item for item in full if item["pid"] != 39216]
        shrink_two = [item for item in shrink_one if item["pid"] != 29740]

        class FakeJob:
            def __init__(self):
                self.query_index = 0
                self.wait_index = 0
                self.terminated = False

            def wait_empty(self, _timeout_sec):
                self.wait_index += 1
                return self.wait_index >= 4

            def active_process_identities(self):
                values = [full, shrink_one, shrink_two]
                value = values[min(self.query_index, len(values) - 1)]
                self.query_index += 1
                return value

            def terminate(self):
                self.terminated = True
                return True

            @staticmethod
            def close():
                pass

        job = FakeJob()
        passed, record = verify_fake_job(job)
        self.assertTrue(passed)
        self.assertFalse(job.terminated)
        snapshots = record["expected_tool_daemon_topology_snapshots"]
        self.assertEqual("EXACT_R2_VIVADO_EXIT_HELPER_FOREST", snapshots[0]["classification"])
        self.assertTrue(snapshots[1]["classification"].startswith("STRICT_SHRINK_SUBSET_OF_"))
        self.assertEqual("EMPTY", snapshots[-1]["classification"])
        self.assertTrue(all("creation_time_100ns" in item for snap in snapshots[:-1] for item in snap["processes"]))
        self.assertTrue(record["expected_tool_daemon_topology_monotonic"])
        self.assertGreaterEqual(record["expected_tool_daemon_topology_revalidation_count"], 3)
        self.assertLessEqual(record["expected_tool_daemon_topology_max_sample_gap_seconds"], 0.25)

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object tamper test")
    def test_growth_reappearance_and_identity_mutation_are_forced_cleanup_failures(self) -> None:
        full = exact_r2_forest()
        shrunk = full[:-1]
        mutated = [{**item} for item in shrunk]
        mutated[0]["creation_time_100ns"] = int(mutated[0]["creation_time_100ns"]) + 1
        scenarios = (
            [
                full,
                full
                + [helper_process("conhost", 60000, 30352, parent_active=True)],
            ],
            [full, shrunk, full],
            [full, mutated],
        )

        class FakeJob:
            def __init__(self, snapshots):
                self.snapshots = snapshots
                self.index = 0
                self.terminated = False

            def wait_empty(self, timeout_sec):
                return timeout_sec == stage.CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS

            def active_process_identities(self):
                value = self.snapshots[min(self.index, len(self.snapshots) - 1)]
                self.index += 1
                return value

            def terminate(self):
                self.terminated = True
                return False

            @staticmethod
            def close():
                pass

        for snapshots in scenarios:
            job = FakeJob(snapshots)
            passed, record = verify_fake_job(job)
            self.assertFalse(passed)
            self.assertTrue(job.terminated)
            self.assertTrue(record["containment_cleanup_attempted"])
            self.assertFalse(record["containment_cleanup_terminated"])
            self.assertIn("grew, reappeared, mutated", record["expected_tool_daemon_topology_error"])

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object query/hash test")
    def test_query_retry_is_global_once_and_hash_tamper_cannot_pass(self) -> None:
        class RetryJob:
            def __init__(self, fail_twice: bool):
                self.fail_twice = fail_twice
                self.queries = 0
                self.waits = 0
                self.terminated = False

            def wait_empty(self, timeout_sec):
                self.waits += 1
                if timeout_sec == stage.CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS:
                    return True
                return self.waits >= 4 and not self.fail_twice

            def active_process_identities(self):
                self.queries += 1
                if self.queries == 1 or (self.fail_twice and self.queries >= 3):
                    raise OSError("identity unavailable")
                return [helper_process("cs_server", 9494, 9393)]

            def terminate(self):
                self.terminated = True
                return True

            @staticmethod
            def close():
                pass

        good = RetryJob(False)
        passed, record = verify_fake_job(good)
        self.assertTrue(passed)
        self.assertEqual(1, record["process_identity_query_retry_count"])
        self.assertEqual("", record["containment_query_error"])
        bad = RetryJob(True)
        passed, record = verify_fake_job(bad)
        self.assertFalse(passed)
        self.assertTrue(record["containment_cleanup_attempted"])
        self.assertIn("identity unavailable", record["containment_query_error"])

        class ImmediatelyEmptyJob:
            @staticmethod
            def wait_empty(_timeout_sec):
                return True

            @staticmethod
            def terminate():
                raise AssertionError("empty Job must not be terminated")

            @staticmethod
            def close():
                pass

        passed, record = verify_fake_job(
            ImmediatelyEmptyJob(),
            post_hash_result=(False, {"cs_server": "0" * 64}, "post hash mismatch"),
        )
        self.assertFalse(passed)
        self.assertFalse(record["expected_tool_daemon_hashes_verified"])
        self.assertIn("post hash mismatch", record["expected_tool_daemon_hash_error"])
        self.assertFalse(record["containment_cleanup_attempted"])

    @unittest.skipUnless(sys.platform == "win32", "Windows prelaunch binding test")
    def test_prelaunch_hash_failure_never_releases_contained_launcher(self) -> None:
        class FakeStdin:
            def __init__(self):
                self.writes = []

            def write(self, value):
                self.writes.append(value)

            @staticmethod
            def flush():
                pass

            @staticmethod
            def close():
                pass

        class FakeProcess:
            pid = 7001

            def __init__(self):
                self.stdin = FakeStdin()

            @staticmethod
            def poll():
                return 0

        class FakeJob:
            closed = False

            @staticmethod
            def assign(_process):
                pass

            def close(self):
                self.closed = True

        process = FakeProcess()
        job = FakeJob()
        with mock.patch.object(stage, "_WindowsJobContainment", return_value=job), mock.patch.object(
            stage.subprocess, "Popen", return_value=process
        ), mock.patch.object(
            stage,
            "verify_expected_tool_daemon_binary_hashes",
            return_value=(False, {"cs_server": "0" * 64}, "source hash mismatch"),
        ):
            with self.assertRaisesRegex(OSError, "before P7_GO"):
                stage.launch_contained_process(
                    [r"D:\Xilinx\Vivado\2023.1\bin\vivado.bat", "-mode", "batch"],
                    stdout=mock.Mock(),
                    stderr=mock.Mock(),
                    popen_args={},
                )
        self.assertEqual([], process.stdin.writes)
        self.assertTrue(job.closed)

    @unittest.skipUnless(sys.platform == "win32", "Windows fixed-deadline test")
    def test_natural_exit_window_is_one_fixed_deadline_and_timeout_cleanup_never_passes(self) -> None:
        class FakeJob:
            terminated = False

            @staticmethod
            def wait_empty(timeout_sec):
                return timeout_sec == stage.CONTAINMENT_FORCED_CLEANUP_WAIT_SECONDS

            @staticmethod
            def active_process_identities():
                return [helper_process("cs_server", 8100, 8000)]

            def terminate(self):
                self.terminated = True
                return True

            @staticmethod
            def close():
                pass

        job = FakeJob()
        with mock.patch.object(stage, "EXPECTED_TOOL_DAEMON_GRACE_SECONDS", 0.02), mock.patch.object(
            stage, "CONTAINMENT_TOPOLOGY_REVALIDATION_INTERVAL_SECONDS", 0.005
        ):
            passed, record = verify_fake_job(job)
        self.assertFalse(passed)
        self.assertTrue(job.terminated)
        self.assertTrue(record["containment_cleanup_attempted"])
        self.assertTrue(record["containment_cleanup_terminated"])
        self.assertEqual(0.02, record["expected_tool_daemon_grace_seconds"])
        self.assertLessEqual(record["expected_tool_daemon_grace_elapsed_seconds"], 0.02)

    @unittest.skipUnless(sys.platform == "win32", "Windows stable snapshot test")
    def test_job_identity_snapshot_rejects_pid_set_churn_across_a_b_queries(self) -> None:
        job = object.__new__(stage._WindowsJobContainment)
        with mock.patch.object(job, "active_process_ids", side_effect=[[11], [11, 12]]), mock.patch.object(
            job, "process_parent_state", return_value=({11: 10}, {10, 11})
        ), mock.patch.object(
            job, "process_identity", return_value=(HELPER_PATHS[0], 123456)
        ):
            with self.assertRaisesRegex(OSError, "changed across identity snapshot"):
                job.active_process_identities()

    @unittest.skipUnless(sys.platform == "win32", "Windows cleanup deadline test")
    def test_forced_termination_uses_one_shared_ten_second_job_deadline(self) -> None:
        class FakeProcess:
            pid = 9911
            returncode = None

            def __init__(self):
                self.waits = []

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.waits.append(timeout)
                self.returncode = -9
                return -9

        class FakeJob:
            def __init__(self, process):
                self.process = process
                self.waits = []

            @staticmethod
            def terminate():
                return True

            def wait_empty(self, timeout_sec):
                self.waits.append(timeout_sec)
                return True

            @staticmethod
            def close():
                pass

        process = FakeProcess()
        job = FakeJob(process)
        stage._WINDOWS_JOBS[process] = job
        stage._CONTAINMENT_DETAILS[process] = stage._containment_detail_defaults()
        try:
            with mock.patch.object(
                stage.time, "monotonic", side_effect=[100.0, 101.0, 102.0]
            ):
                self.assertTrue(stage.terminate_process_tree(process))
            record = stage.containment_record(process)
        finally:
            stage._WINDOWS_JOBS.pop(process, None)
            stage._CONTAINMENT_RESULTS.pop(process, None)
            stage._CONTAINMENT_DETAILS.pop(process, None)
        self.assertEqual([9.0], job.waits)
        self.assertEqual([8.0], process.waits)
        self.assertTrue(record["containment_cleanup_attempted"])
        self.assertTrue(record["containment_cleanup_terminated"])

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object race resolution test")
    def test_job_identity_exit_race_passes_only_after_empty_recheck(self) -> None:
        class FakeProcess:
            pid = 9292

            @staticmethod
            def poll():
                return 0

        class FakeJob:
            def __init__(self, query_raises: bool) -> None:
                self.query_raises = query_raises
                self.waits: list[float] = []

            def wait_empty(self, timeout_sec: float) -> bool:
                self.waits.append(timeout_sec)
                return timeout_sec == stage.PROCESS_EXIT_RACE_RECHECK_SECONDS

            def active_process_identities(self):
                if self.query_raises:
                    raise OSError("PID exited during image lookup")
                return []

            @staticmethod
            def terminate():
                raise AssertionError("an empty rechecked job must not be terminated")

            @staticmethod
            def close():
                pass

        for query_raises in (False, True):
            process = FakeProcess()
            job = FakeJob(query_raises)
            stage._WINDOWS_JOBS[process] = job
            stage._CONTAINMENT_DETAILS[process] = {
                "expected_tool_daemon_paths": [],
                "expected_tool_daemon_grace_used": False,
                "descendant_paths_seen": [],
                "containment_cleanup_terminated": False,
            }
            try:
                self.assertTrue(stage.verify_process_tree_reaped(process))
                record = stage.containment_record(process)
            finally:
                stage._WINDOWS_JOBS.pop(process, None)
                stage._CONTAINMENT_RESULTS.pop(process, None)
                stage._CONTAINMENT_DETAILS.pop(process, None)
            self.assertTrue(record["process_exit_race_rechecked"])
            self.assertEqual(0, record["descendant_count_after"])
            self.assertFalse(record["containment_cleanup_terminated"])

    def test_post_launch_exception_reaps_before_return(self) -> None:
        class FakeProcess:
            pid = 4343
            returncode = None

            def poll(self):
                return self.returncode

            def wait(self, timeout=None):
                self.returncode = -9
                return -9

        fake = FakeProcess()
        abort_file = mock.Mock()
        abort_file.exists.side_effect = OSError("post-launch probe failure")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with mock.patch.object(stage, "launch_contained_process", return_value=fake), mock.patch.object(
                stage,
                "terminate_process_tree",
                side_effect=lambda process: setattr(process, "returncode", -9) is None,
            ) as terminate, mock.patch.object(stage, "verify_process_tree_reaped", return_value=True):
                result = stage.run_bounded_process(
                    name="exception_reap",
                    command=["fixed.exe", "fixed"],
                    stdout_path=root / "stdout.log",
                    stderr_path=root / "stderr.log",
                    timeout_sec=10,
                    abort_file=abort_file,
                    watch_abort=True,
                )
        self.assertEqual(127, result.returncode)
        self.assertTrue(result.process_tree_reaped)
        terminate.assert_called_once_with(fake)

    def test_json_summary_commit_is_atomic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "summary.json"
            stage.write_json(path, {"value": 1})
            self.assertEqual({"value": 1}, json.loads(path.read_text(encoding="utf-8")))
            self.assertEqual([], list(path.parent.glob("*.partial")))

    def test_tcl_is_authorized_strict_data_parser_with_emergency_shutdown(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_jtag_axi_transactions.tcl").read_text(encoding="utf-8")
        lower = tcl.lower()
        self.assertLess(tcl.index("RF_COMM_HW_AUTH"), tcl.index("open_hw_manager"))
        self.assertLess(tcl.index("ABORT_NOW.txt"), tcl.index("open_hw_manager"))
        self.assertNotIn("source $txn", lower)
        self.assertNotIn("eval $", lower)
        self.assertNotIn("exec $", lower)
        self.assertIn("P7_JTAG_AXI_TRANSACTIONS_V1", tcl)
        self.assertIn("P7_TCL_EMERGENCY_TFDU_SHUTDOWN_PROGRAMMED", tcl)
        self.assertIn("program_hw_devices", tcl)
        self.assertIn("while {[gets $txn_handle raw_line] >= 0}", tcl)
        self.assertNotIn('split [read $txn_handle]', tcl)
        self.assertIn("1100000", tcl)
        self.assertIn("134217728", tcl)
        self.assertIn('set p7_canonical_part "xc7z010clg400-1"', tcl)
        self.assertIn('set p7_live_part "xc7z010"', tcl)
        self.assertIn('set p7_live_device "xc7z010_1"', tcl)
        self.assertIn('set p7_live_idcode "13722093"', tcl)
        self.assertIn("P7_HW_CANONICAL_PART=", tcl)
        self.assertIn("P7_HW_LIVE_PART=", tcl)
        self.assertNotIn("string match -nocase *xc7z010*", tcl)
        self.assertNotIn(r"string map {\ /}", tcl)
        self.assertEqual(3, tcl.count('string map [list "\\\\" "/"]'))
        self.assertEqual(2, tcl.count("P7_JTAG_STAGE_ERROR=[p7_sanitize_error $error_text]"))
        self.assertNotIn("P7_JTAG_STAGE_ERROR=[string map", tcl)
        self.assertGreaterEqual(tcl.count("P7_TCL_PROGRAMMING_ATTEMPTED="), 5)
        attempt_assignments = [
            match.start()
            for match in re.finditer("set candidate_programming_attempted 1", tcl)
        ]
        self.assertEqual(2, len(attempt_assignments))
        program_calls = [
            match.start()
            for match in re.finditer("program_hw_devices \\$selected_device", tcl)
        ]
        self.assertGreaterEqual(len(program_calls), 3)
        self.assertLess(attempt_assignments[0], program_calls[0])
        self.assertLess(attempt_assignments[1], program_calls[1])
        wrapper = MODULE_PATH.read_text(encoding="utf-8")
        self.assertIn('markers.get("P7_TCL_PROGRAMMING_ATTEMPTED") != "1"', wrapper)
        self.assertEqual(2, wrapper.count('"programming_attempted": shutdown_programming_attempted('))
        self.assertNotIn("combined = stdout", wrapper)
        self.assertEqual(2, wrapper.count("expected_shutdown_bit=shutdown_bit"))

    def test_tcl_path_mapping_and_error_sanitizer_execute_in_tcl(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_jtag_axi_transactions.tcl").read_text(encoding="utf-8")
        interp = tcl_interpreter()
        self.assertEqual(1, int(interp.call("info", "complete", tcl)))
        prefix = tcl[: tcl.index("proc p7_require_auth_path")]
        interp.eval(prefix)
        normalized = str(interp.call("p7_normal_path", r"C:\Temp\TFDU Shutdown.bit"))
        self.assertNotIn("\\", normalized)
        self.assertTrue(normalized.endswith("c:/temp/tfdu shutdown.bit"), normalized)
        original = "ORIGINAL_FAILURE first line\nsecond line\rthird line"
        self.assertEqual(
            "ORIGINAL_FAILURE first line second line third line",
            str(interp.call("p7_sanitize_error", original)),
        )
        with self.assertRaises(tkinter.TclError):
            interp.eval(r"string map {\ /} {C:\Temp\broken.bit}")
        interp.eval(tcl[: tcl.index("proc p7_axi_write")])
        for offset, data in (
            (0x100, 0x30),
            (0x108, 0x2201),
            (0x10C, 0x3),
            (0x110, 0x3),
            (0x114, 247),
            (0x118, 0),
            (0x11C, 0),
            (0x15C, 1),
            (0x16C, 0),
            (0x170, 0),
            (0x174, 0),
            (0x200, 0),
        ):
            interp.call("p7_validate_write", offset, data)

    def test_tcl_failure_result_preserves_original_error_before_hardware(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_jtag_axi_transactions.tcl").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result_path = root / "failure.txt"
            interp = tcl_interpreter()
            install_captured_tcl_exit(interp)
            interp.setvar("env(RF_COMM_HW_AUTH)", "P7_STATIONARY_APP_LAYER_APPROVED")
            interp.setvar(
                "argv",
                (
                    str(root),
                    "SHUTDOWN",
                    str(root / "missing-auth.txt"),
                    "210512180081",
                    "xc7z010clg400-1",
                    "localhost:3121/xilinx_tcf/Digilent/210512180081",
                    "localhost:3121",
                    "1000000",
                    str(root / "missing.bit"),
                    "-",
                    "-",
                    str(result_path),
                    "0x43c00000",
                    "1",
                    "1",
                    "0",
                    str(root / "missing.bit"),
                ),
            )
            with self.assertRaises(tkinter.TclError) as raised:
                interp.eval(tcl)
            self.assertIn("__P7_CAPTURED_EXIT__41", str(raised.exception))
            self.assertEqual("41", str(interp.getvar("p7_captured_exit_code")))
            result = result_path.read_text(encoding="utf-8")
        self.assertIn("P7_JTAG_STAGE_RESULT=FAIL", result)
        self.assertIn("P7_TCL_PROGRAMMING_ATTEMPTED=0", result)
        self.assertIn("P7_JTAG_STAGE_ERROR=P7 max runtime must be in 1..1800 seconds", result)
        self.assertNotIn("char map list unbalanced", result)

    def test_tcl_shutdown_path_reaches_pass_with_offline_command_stubs(self) -> None:
        tcl = (ROOT / "scripts" / "hw" / "p7_jtag_axi_transactions.tcl").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            auth_dir = root / ".hardware_authorization"
            auth_dir.mkdir()
            shutdown_bit = root / "tfdu_shutdown.bit"
            shutdown_bit.write_bytes(b"offline-tcl-fixture")
            result_path = root / "shutdown_result.txt"
            board_id = "210512180081"
            target = f"localhost:3121/xilinx_tcf/Digilent/{board_id}"
            auth_path = auth_dir / "offline_shutdown.txt"
            auth_path.write_text(
                "\n".join(
                    [
                        "P7_STATIONARY_APP_LAYER_APPROVED",
                        "AUTHORIZED_STAGE=P7_STATIONARY_LOCAL_APPLICATION_LAYER_NO_ETHERNET",
                        "USER_HARDWARE_AUTHORIZATION_FOR_P7=GRANTED",
                        f"BOARD_ID={board_id}",
                        "EXPECTED_PART=xc7z010clg400-1",
                        f"EXPECTED_TARGET={target}",
                        "SHUTDOWN_ON_EXIT=required",
                        "NO_ETHERNET=true",
                        "NO_MOTION=true",
                        "LANE_COUNT=2",
                        "MAX_LANE_MASK=0x3",
                        f"SHUTDOWN_BITSTREAM_PATH={shutdown_bit}",
                        "MAX_RUNTIME_SEC=30",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            interp = tcl_interpreter()
            install_captured_tcl_exit(interp)
            interp.setvar("env(RF_COMM_HW_AUTH)", "P7_STATIONARY_APP_LAYER_APPROVED")
            interp.setvar("p7_stub_target", target)
            stub_prelude = (
                "set ::p7_stub_calls {}\n"
                "proc open_hw_manager {} {lappend ::p7_stub_calls open_hw_manager}\n"
                "proc connect_hw_server {args} {lappend ::p7_stub_calls connect_hw_server}\n"
                "proc get_hw_targets {args} {return $::p7_stub_target}\n"
                "proc current_hw_target {args} {}\n"
                "proc set_property {args} {}\n"
                "proc open_hw_target {args} {}\n"
                "proc get_hw_devices {args} {return xc7z010_1}\n"
                "proc get_property {property object} {\n"
                "  switch -- $property {\n"
                "    PART {return xc7z010}\n"
                "    NAME {return xc7z010_1}\n"
                "    IDCODE {return 13722093}\n"
                "    default {error \"unexpected property $property\"}\n"
                "  }\n"
                "}\n"
                "proc current_hw_device {args} {}\n"
                "proc program_hw_devices {args} {lappend ::p7_stub_calls program_hw_devices}\n"
                "proc refresh_hw_device {args} {}\n"
                "proc close_hw_target {args} {}\n"
                "proc disconnect_hw_server {args} {}\n"
                "proc close_hw_manager {args} {}"
            )
            interp.eval(stub_prelude)
            interp.setvar(
                "argv",
                (
                    str(root),
                    "SHUTDOWN",
                    str(auth_path),
                    board_id,
                    "xc7z010clg400-1",
                    target,
                    "localhost:3121",
                    "1000000",
                    str(shutdown_bit),
                    "-",
                    "-",
                    str(result_path),
                    "0x43c00000",
                    "1",
                    "4096",
                    "30",
                    str(shutdown_bit),
                ),
            )
            with self.assertRaises(tkinter.TclError) as raised:
                interp.eval(tcl)
            self.assertIn("__P7_CAPTURED_EXIT__0", str(raised.exception))
            self.assertEqual("0", str(interp.getvar("p7_captured_exit_code")))
            calls = tuple(interp.splitlist(interp.getvar("p7_stub_calls")))
            result = result_path.read_text(encoding="utf-8")
            self.assertEqual(("open_hw_manager", "connect_hw_server", "program_hw_devices"), calls)
            self.assertIn("P7_TCL_PROGRAMMING_ATTEMPTED=1", result)
            self.assertIn("TFDU_SHUTDOWN_PROGRAMMED=", result)
            self.assertIn("P7_SHUTDOWN_RESULT=PASS", result)
            self.assertNotIn("char map list unbalanced", result)
            passed, failures = stage.evaluate_shutdown(
                0,
                result,
                expected_shutdown_bit=shutdown_bit,
            )
            self.assertTrue(passed, failures)

            failure_result_path = root / "shutdown_failure_result.txt"
            failure_interp = tcl_interpreter()
            install_captured_tcl_exit(failure_interp)
            failure_interp.setvar("env(RF_COMM_HW_AUTH)", "P7_STATIONARY_APP_LAYER_APPROVED")
            failure_interp.setvar("p7_stub_target", target)
            failure_interp.eval(
                stub_prelude.replace(
                    "proc program_hw_devices {args} {lappend ::p7_stub_calls program_hw_devices}",
                    "proc program_hw_devices {args} {error synthetic_program_failure}",
                )
            )
            failure_interp.setvar(
                "argv",
                (
                    str(root),
                    "SHUTDOWN",
                    str(auth_path),
                    board_id,
                    "xc7z010clg400-1",
                    target,
                    "localhost:3121",
                    "1000000",
                    str(shutdown_bit),
                    "-",
                    "-",
                    str(failure_result_path),
                    "0x43c00000",
                    "1",
                    "4096",
                    "30",
                    str(shutdown_bit),
                ),
            )
            with self.assertRaises(tkinter.TclError) as raised:
                failure_interp.eval(tcl)
            self.assertIn("__P7_CAPTURED_EXIT__41", str(raised.exception))
            failure_result = failure_result_path.read_text(encoding="utf-8")
            self.assertIn("P7_TCL_PROGRAMMING_ATTEMPTED=1", failure_result)
            self.assertIn("P7_JTAG_STAGE_RESULT=FAIL", failure_result)
            self.assertIn("synthetic_program_failure", failure_result)
            self.assertNotIn("TFDU_SHUTDOWN_PROGRAMMED=", failure_result)
            self.assertNotIn("P7_SHUTDOWN_RESULT=PASS", failure_result)

    def test_wrapper_never_sets_external_hardware_authorization(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('os.environ["RF_COMM_HW_AUTH"] =', text)
        self.assertNotIn('env["RF_COMM_HW_AUTH"] =', text)


if __name__ == "__main__":
    unittest.main()
