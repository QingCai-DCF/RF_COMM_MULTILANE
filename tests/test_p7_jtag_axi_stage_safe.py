from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


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
                "--stage-timeout-sec", "1450",
                "--preflight-timeout-sec", "120",
                "--shutdown-timeout-sec", "60",
            ]
        )
        self.assertEqual(
            [], stage.transaction_runtime_errors(feasible_args, feasible_transaction)
        )
        budget = feasible_transaction["global_runtime_budget"]
        self.assertTrue(budget["feasible"])
        self.assertEqual(44, budget["containment_allowance_seconds"])
        self.assertEqual(45, budget["other_guard_seconds"])
        self.assertEqual(1779, budget["configured_global_timeout_ceiling_sec"])
        self.assertEqual(21, budget["configured_unallocated_margin_seconds"])
        self.assertEqual(1372, feasible_transaction["runtime_feasibility"]["minimum_stage_runtime_sec"])
        overflow_transaction = {"operation_count": operation_count}
        overflow_args = stage.build_parser().parse_args(
            [
                "--max-runtime-sec", "1800",
                "--jtag-frequency-hz", "1000000",
                "--stage-timeout-sec", "1500",
                "--preflight-timeout-sec", "120",
                "--shutdown-timeout-sec", "60",
            ]
        )
        overflow_errors = stage.transaction_runtime_errors(overflow_args, overflow_transaction)
        self.assertTrue(any("configured process timeout ceiling" in item for item in overflow_errors))
        self.assertEqual(
            1829,
            overflow_transaction["global_runtime_budget"]["configured_global_timeout_ceiling_sec"],
        )
        self.assertEqual([0, 11, 22, 33, 44], [stage.containment_allowance(i) for i in range(5)])
        with mock.patch.object(stage.time, "monotonic", return_value=0.0):
            self.assertEqual(
                120,
                stage.deadline_timeout(
                    120,
                    1800.0,
                    reserve_sec=2 * 60 + 1450 + stage.containment_allowance(3) + 45,
                ),
            )
            self.assertEqual(
                60,
                stage.deadline_timeout(
                    60,
                    1800.0,
                    reserve_sec=1450 + 60 + stage.containment_allowance(2) + 45,
                ),
            )
            self.assertEqual(
                1450,
                stage.deadline_timeout(
                    1450,
                    1800.0,
                    reserve_sec=60 + stage.containment_allowance(1) + 45,
                ),
            )
            self.assertEqual(
                60,
                stage.deadline_timeout(60, 1800.0, reserve_sec=45),
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
        passed, failures = stage.evaluate_shutdown(
            125,
            "TFDU_SHUTDOWN_PROGRAMMED=C:/shutdown.bit\n",
            "P7_SHUTDOWN_RESULT=PASS\n",
        )
        self.assertFalse(passed)
        self.assertTrue(any("nonzero exit code" in item for item in failures))
        passed, failures = stage.evaluate_shutdown(0, "", "P7_SHUTDOWN_RESULT=PASS\n")
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

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object daemon classification test")
    def test_exact_vivado_cs_server_may_exit_naturally_during_bounded_grace(self) -> None:
        class FakeProcess:
            pid = 5151

            @staticmethod
            def poll():
                return 0

        class FakeJob:
            def __init__(self, path: str) -> None:
                self.path = path
                self.waits: list[float] = []
                self.closed = False

            def wait_empty(self, timeout_sec: float) -> bool:
                self.waits.append(timeout_sec)
                return len(self.waits) >= 2

            def active_process_identities(self):
                return [{"pid": 6161, "parent_pid": 5151, "image_path": self.path}]

            def terminate(self):
                raise AssertionError("naturally exiting exact daemon must not be terminated")

            def close(self):
                self.closed = True

        process = FakeProcess()
        expected = str(
            Path(r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\cs_server.exe")
        )
        job = FakeJob(expected)
        stage._WINDOWS_JOBS[process] = job
        stage._CONTAINMENT_DETAILS[process] = {
            "expected_tool_daemon_paths": [expected],
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
        self.assertEqual([1.0, stage.EXPECTED_TOOL_DAEMON_GRACE_SECONDS], job.waits)
        self.assertTrue(job.closed)
        self.assertTrue(record["expected_tool_daemon_grace_used"])
        self.assertEqual(
            stage.EXPECTED_TOOL_DAEMON_GRACE_SECONDS,
            record["expected_tool_daemon_grace_seconds"],
        )
        self.assertEqual([expected], record["descendant_paths_seen"])
        self.assertEqual("SINGLE_EXACT_CS_SERVER", record["expected_tool_daemon_classification"])
        self.assertEqual(6161, record["descendant_processes_seen"][0]["pid"])
        self.assertFalse(record["containment_cleanup_terminated"])

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object daemon topology test")
    def test_exact_direct_parent_child_cs_servers_may_exit_during_grace(self) -> None:
        class FakeProcess:
            pid = 1111

            @staticmethod
            def poll():
                return 0

        class FakeJob:
            def __init__(self, path: str) -> None:
                self.path = path
                self.waits: list[float] = []

            def wait_empty(self, timeout_sec: float) -> bool:
                self.waits.append(timeout_sec)
                return len(self.waits) >= 2

            def active_process_identities(self):
                return [
                    {"pid": 2222, "parent_pid": 1111, "image_path": self.path},
                    {"pid": 3333, "parent_pid": 2222, "image_path": self.path},
                ]

            @staticmethod
            def terminate():
                raise AssertionError("exact direct parent-child topology must not be terminated")

            @staticmethod
            def close():
                pass

        expected = r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\cs_server.exe"
        process = FakeProcess()
        job = FakeJob(expected)
        stage._WINDOWS_JOBS[process] = job
        stage._CONTAINMENT_DETAILS[process] = {
            "expected_tool_daemon_paths": [expected],
            "expected_tool_daemon_grace_used": False,
            "containment_cleanup_terminated": False,
        }
        try:
            self.assertTrue(stage.verify_process_tree_reaped(process))
            record = stage.containment_record(process)
        finally:
            stage._WINDOWS_JOBS.pop(process, None)
            stage._CONTAINMENT_RESULTS.pop(process, None)
            stage._CONTAINMENT_DETAILS.pop(process, None)
        self.assertEqual(
            "DIRECT_PARENT_CHILD_EXACT_CS_SERVER",
            record["expected_tool_daemon_classification"],
        )
        self.assertEqual([2222, 3333], [item["pid"] for item in record["descendant_processes_seen"]])
        self.assertTrue(record["expected_tool_daemon_grace_used"])
        self.assertFalse(record["containment_cleanup_terminated"])
        self.assertEqual(
            "UNAPPROVED",
            stage.classify_expected_tool_daemons(
                [{"pid": True, "parent_pid": 1, "image_path": expected}],
                [expected],
            ),
        )
        self.assertEqual(
            "UNAPPROVED",
            stage.classify_expected_tool_daemons(
                [{"pid": 7, "parent_pid": 7, "image_path": expected}],
                [expected],
            ),
        )

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object daemon classification test")
    def test_wrong_path_and_daemon_grace_timeout_remain_fail_closed(self) -> None:
        class FakeProcess:
            pid = 7171

            @staticmethod
            def poll():
                return 0

        class FakeJob:
            def __init__(self, identities: list[dict[str, object]], *, grace_exits: bool) -> None:
                self.identities = identities
                self.grace_exits = grace_exits
                self.waits: list[float] = []
                self.terminated = False

            def wait_empty(self, timeout_sec: float) -> bool:
                self.waits.append(timeout_sec)
                if len(self.waits) == 1:
                    return False
                if len(self.waits) == 2:
                    return self.grace_exits
                return True

            def active_process_identities(self):
                return self.identities

            def terminate(self):
                self.terminated = True
                return True

            def close(self):
                pass

        expected = str(
            Path(r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\cs_server.exe")
        )
        for identities, grace_exits, expected_grace in (
            ([{"pid": 8181, "parent_pid": 7171, "image_path": r"C:\attacker\cs_server.exe"}], True, False),
            ([
                {"pid": 8181, "parent_pid": 7171, "image_path": expected},
                {"pid": 8182, "parent_pid": 7171, "image_path": expected},
            ], True, False),
            ([
                {"pid": 8181, "parent_pid": 7171, "image_path": expected},
                {"pid": 8182, "parent_pid": 8181, "image_path": expected},
                {"pid": 8183, "parent_pid": 8182, "image_path": expected},
            ], True, False),
            ([{"pid": 8181, "parent_pid": 7171, "image_path": expected}], False, True),
        ):
            process = FakeProcess()
            job = FakeJob(identities, grace_exits=grace_exits)
            stage._WINDOWS_JOBS[process] = job
            stage._CONTAINMENT_DETAILS[process] = {
                "expected_tool_daemon_paths": [expected],
                "expected_tool_daemon_grace_used": False,
                "descendant_paths_seen": [],
                "containment_cleanup_terminated": False,
            }
            try:
                self.assertFalse(stage.verify_process_tree_reaped(process))
                record = stage.containment_record(process)
            finally:
                stage._WINDOWS_JOBS.pop(process, None)
                stage._CONTAINMENT_RESULTS.pop(process, None)
                stage._CONTAINMENT_DETAILS.pop(process, None)
            self.assertTrue(job.terminated)
            self.assertTrue(record["containment_cleanup_terminated"])
            self.assertEqual(expected_grace, record["expected_tool_daemon_grace_used"])
            if expected_grace:
                self.assertEqual(3, len(job.waits))
            else:
                self.assertEqual(2, len(job.waits))

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object daemon classification test")
    def test_job_process_identity_query_error_is_terminated_and_rejected(self) -> None:
        class FakeProcess:
            pid = 9191

            @staticmethod
            def poll():
                return 0

        class FakeJob:
            def __init__(self) -> None:
                self.terminated = False

            @staticmethod
            def wait_empty(timeout_sec: float) -> bool:
                return timeout_sec == 10.0

            @staticmethod
            def active_process_identities():
                raise OSError("identity unavailable")

            def terminate(self):
                self.terminated = True
                return True

            @staticmethod
            def close():
                pass

        process = FakeProcess()
        job = FakeJob()
        stage._WINDOWS_JOBS[process] = job
        stage._CONTAINMENT_DETAILS[process] = {
            "expected_tool_daemon_paths": [r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\cs_server.exe"],
            "expected_tool_daemon_grace_used": False,
            "descendant_paths_seen": [],
            "containment_cleanup_terminated": False,
        }
        try:
            self.assertFalse(stage.verify_process_tree_reaped(process))
            record = stage.containment_record(process)
        finally:
            stage._WINDOWS_JOBS.pop(process, None)
            stage._CONTAINMENT_RESULTS.pop(process, None)
            stage._CONTAINMENT_DETAILS.pop(process, None)
        self.assertTrue(job.terminated)
        self.assertTrue(record["containment_cleanup_terminated"])
        self.assertIn("identity unavailable", record["containment_query_error"])

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

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object topology race test")
    def test_parent_exit_query_race_retries_to_exact_singleton_then_grace(self) -> None:
        class FakeProcess:
            pid = 9393

            @staticmethod
            def poll():
                return 0

        class FakeJob:
            def __init__(self, path: str) -> None:
                self.path = path
                self.queries = 0
                self.waits: list[float] = []

            def wait_empty(self, timeout_sec: float) -> bool:
                self.waits.append(timeout_sec)
                return timeout_sec == stage.EXPECTED_TOOL_DAEMON_GRACE_SECONDS

            def active_process_identities(self):
                self.queries += 1
                if self.queries == 1:
                    raise OSError("parent exited during Toolhelp snapshot")
                return [{"pid": 9494, "parent_pid": 9393, "image_path": self.path}]

            @staticmethod
            def terminate():
                raise AssertionError("retried exact singleton must not be terminated")

            @staticmethod
            def close():
                pass

        expected = r"D:\Xilinx\Vivado\2023.1\bin\unwrapped\win64.o\cs_server.exe"
        process = FakeProcess()
        job = FakeJob(expected)
        stage._WINDOWS_JOBS[process] = job
        stage._CONTAINMENT_DETAILS[process] = {
            "expected_tool_daemon_paths": [expected],
            "expected_tool_daemon_grace_used": False,
            "containment_cleanup_terminated": False,
        }
        try:
            self.assertTrue(stage.verify_process_tree_reaped(process))
            record = stage.containment_record(process)
        finally:
            stage._WINDOWS_JOBS.pop(process, None)
            stage._CONTAINMENT_RESULTS.pop(process, None)
            stage._CONTAINMENT_DETAILS.pop(process, None)
        self.assertEqual(2, job.queries)
        self.assertTrue(record["process_identity_query_retried"])
        self.assertEqual("SINGLE_EXACT_CS_SERVER", record["expected_tool_daemon_classification"])
        self.assertTrue(record["expected_tool_daemon_grace_used"])

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

    def test_wrapper_never_sets_external_hardware_authorization(self) -> None:
        text = MODULE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('os.environ["RF_COMM_HW_AUTH"] =', text)
        self.assertNotIn('env["RF_COMM_HW_AUTH"] =', text)


if __name__ == "__main__":
    unittest.main()
